import os
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

# Retry logic removed to avoid pickle issues with decorators
from src.ingestion.progress_tracker import get_progress_tracker, Stage, log_memory_usage
from .get_sharepoint_files import SharePoint
from .llm_semantic_splitter import semantic_split
from .translate import is_english, translate_file

logger = logging.getLogger(__name__)

def print_progress_summary(current: int, total: int, phase: str, start_time: float):
    """Print progress summary every 10%."""
    if total == 0:
        return
    
    progress = (current / total) * 100
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 else 0
    
    if current < total and rate > 0:
        remaining = (total - current) / rate
        eta = f"ETA: {remaining:.0f}s"
    else:
        eta = "Complete"
    
    print(f"📊 {phase}: {current}/{total} ({progress:.0f}%) | {eta} | {rate:.1f}/s")

def should_show_progress(current: int, total: int, last_shown_percent: int) -> tuple[bool, int]:
    """Determine if we should show progress and return new last_shown_percent."""
    if total == 0:
        return False, last_shown_percent
    
    current_percent = int((current / total) * 100)
    
    # Show at 10% intervals or completion
    target_percents = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    
    for target in target_percents:
        if current_percent >= target and last_shown_percent < target:
            return True, target
    
    return False, last_shown_percent

# Standalone functions to avoid pickle issues with class methods

def _convert_single_file_standalone(file_path: str) -> Optional[str]:
    """Convert a single file to text - standalone function to avoid pickle issues."""
    try:
        # Import inside function to avoid pickle issues
        import src.ingestion.convert_files as cvf
        
        filename = os.path.basename(file_path)
        input_path = Path(file_path).parent
        raw_text = cvf.convert_files(filename, input_path)
        return raw_text
    except Exception as e:
        logger.error(f"Error converting {file_path}: {e}")
        return None

def _download_single_file_with_client(server_url: str, temp_dir: str, sharepoint_client: SharePoint) -> Optional[tuple]:
    """Download a single file from SharePoint using provided client - standalone function to avoid pickle issues."""
    # Patch apostrophes for SharePoint REST API
    patched_url = server_url.replace("'", "''")
    filename = os.path.basename(server_url)
    local_path = os.path.join(temp_dir, filename)
    
    # Simple retry logic without decorators
    max_retries = 3
    for attempt in range(max_retries):
        try:
            sharepoint_client.download_file(patched_url, local_path)
            web_url = sharepoint_client.get_file_web_url(server_url, filename)
            return local_path, web_url
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                logger.error(f"Failed to download {server_url} after {max_retries} attempts: {e}")
                return None
            else:
                logger.warning(f"Download attempt {attempt + 1} failed for {server_url}: {e}, retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff

# Thread-local storage for SharePoint clients to avoid auth conflicts
_thread_local = threading.local()

def _get_thread_sharepoint_client():
    """Get or create a SharePoint client for the current thread."""
    if not hasattr(_thread_local, 'sharepoint_client'):
        # Add a small delay to avoid simultaneous auth attempts
        time.sleep(0.1)
        _thread_local.sharepoint_client = SharePoint()
    return _thread_local.sharepoint_client

def _download_single_file_threadsafe(server_url: str, temp_dir: str) -> Optional[tuple]:
    """Download a single file from SharePoint using thread-local client - avoids auth conflicts."""
    try:
        # Get thread-local SharePoint client
        sharepoint_client = _get_thread_sharepoint_client()
        
        # Patch apostrophes for SharePoint REST API
        patched_url = server_url.replace("'", "''")
        filename = os.path.basename(server_url)
        local_path = os.path.join(temp_dir, filename)
        
        # Simple retry logic without decorators
        max_retries = 3
        for attempt in range(max_retries):
            try:
                sharepoint_client.download_file(patched_url, local_path)
                web_url = sharepoint_client.get_file_web_url(server_url, filename)
                return local_path, web_url
            except Exception as e:
                if attempt == max_retries - 1:  # Last attempt
                    logger.error(f"Failed to download {server_url} after {max_retries} attempts: {e}")
                    return None
                else:
                    logger.warning(f"Download attempt {attempt + 1} failed for {server_url}: {e}, retrying...")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
    except Exception as e:
        logger.error(f"Failed to get SharePoint client for {server_url}: {e}")
        return None

def _translate_single_text_standalone(text: str) -> Optional[str]:
    """Translate a single text - standalone function to avoid pickle issues."""
    try:
        return translate_file(text)
    except Exception as e:
        logger.error(f"Error translating text: {e}")
        return None

def _split_single_text_standalone(filename: str, text: str) -> Optional[tuple]:
    """Split a single text into semantic chunks - standalone function to avoid pickle issues."""
    try:
        chunks, metadata = semantic_split(document_source=filename, raw_document_text=text)
        return chunks, metadata
    except Exception as e:
        logger.error(f"Error splitting {filename}: {e}")
        return None

@dataclass
class WorkerConfig:
    """Configuration for worker pools."""
    download_workers: int = 10
    conversion_workers: int = 10
    translation_workers: int = 10
    splitting_workers: int = 10
    embedding_workers: int = 10
    max_memory_gb: float = 4.0
    
    @classmethod
    def from_env(cls) -> 'WorkerConfig':
        """Create configuration from environment variables."""
        return cls(
            download_workers=int(os.getenv('DOWNLOAD_WORKERS', '10')),
            conversion_workers=int(os.getenv('CONVERSION_WORKERS', '10')),
            translation_workers=int(os.getenv('TRANSLATION_WORKERS', '10')),
            splitting_workers=int(os.getenv('SPLITTING_WORKERS', '10')),
            embedding_workers=int(os.getenv('EMBEDDING_WORKERS', '10')),
            max_memory_gb=float(os.getenv('MAX_MEMORY_GB', '4.0'))
        )

class WorkerPool:
    """Manages worker pools for parallel ingestion stages."""
    
    def __init__(self, config: Optional[WorkerConfig] = None):
        self.config = config or WorkerConfig.from_env()
        self.progress_tracker = get_progress_tracker()
        self.sharepoint_client = None
        self.temp_dir = None
        
        print(f"⚙️  Worker Configuration:")
        print(f"   • Download workers: {self.config.download_workers}")
        print(f"   • Conversion workers: {self.config.conversion_workers}")
        print(f"   • Translation workers: {self.config.translation_workers}")
        print(f"   • Splitting workers: {self.config.splitting_workers}")
        print(f"   • Embedding workers: {self.config.embedding_workers}")
    
    def download_files_parallel(self, ppt_files: List[str], temp_dir: str) -> Dict[str, str]:
        """Download files from SharePoint using optimized parallel approach."""
        self.progress_tracker.start_stage(Stage.DOWNLOADING, len(ppt_files))
        
        downloaded_files = {}
        sharepoint_url_map = {}
        
        # Use reduced parallelism for SharePoint downloads to avoid authentication conflicts
        # SharePoint APIs don't handle high concurrency well
        max_workers = min(10, self.config.download_workers)  # Max 10 workers for SharePoint
        print(f"🔗 Using {max_workers} parallel workers for SharePoint downloads")
        
        download_start_time = time.time()
        completed_count = 0
        last_shown_percent = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks with rate limiting
            future_to_url = {
                executor.submit(_download_single_file_threadsafe, server_url, temp_dir): server_url
                for server_url in ppt_files
            }
            
            # Process completed downloads
            for future in as_completed(future_to_url):
                server_url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        local_path, web_url = result
                        filename = os.path.basename(server_url)
                        downloaded_files[filename] = local_path
                        sharepoint_url_map[filename] = web_url
                        completed_count += 1
                        print(f"✅ Downloaded: {filename} [{completed_count}/{len(ppt_files)}]", flush=True)
                        
                        # Show progress summary at 10% intervals
                        should_show, new_percent = should_show_progress(completed_count, len(ppt_files), last_shown_percent)
                        if should_show:
                            print_progress_summary(completed_count, len(ppt_files), "Download Progress", download_start_time)
                            last_shown_percent = new_percent
                        
                        self.progress_tracker.update_stage_progress(Stage.DOWNLOADING, completed=1)
                    else:
                        print(f"❌ Failed to download {os.path.basename(server_url)}", flush=True)
                        self.progress_tracker.update_stage_progress(Stage.DOWNLOADING, failed=1)
                except Exception as e:
                    print(f"❌ Failed to download {os.path.basename(server_url)}: {e}", flush=True)
                    self.progress_tracker.update_stage_progress(Stage.DOWNLOADING, failed=1)
        
        self.progress_tracker.end_stage(Stage.DOWNLOADING)
        return downloaded_files, sharepoint_url_map
    
    def convert_files_parallel(self, file_paths: List[str]) -> Dict[str, str]:
        """Convert files to text in parallel using threads."""
        self.progress_tracker.start_stage(Stage.CONVERTING, len(file_paths))
        
        converted_texts = {}
        print(f"🔄 Converting {len(file_paths)} files using {self.config.conversion_workers} workers...")
        
        conversion_start_time = time.time()
        completed_count = 0
        last_shown_percent = 0
        
        # Use thread pool for I/O-bound file conversion
        with ThreadPoolExecutor(max_workers=self.config.conversion_workers) as executor:
            future_to_path = {
                executor.submit(_convert_single_file_standalone, file_path): file_path
                for file_path in file_paths
            }
            
            for future in as_completed(future_to_path):
                file_path = future_to_path[future]
                try:
                    result = future.result()
                    if result:
                        filename = os.path.basename(file_path)
                        converted_texts[filename] = result
                        completed_count += 1
                        print(f"✅ Converted: {filename} [{completed_count}/{len(file_paths)}]", flush=True)
                        
                        # Show progress summary at 10% intervals
                        should_show, new_percent = should_show_progress(completed_count, len(file_paths), last_shown_percent)
                        if should_show:
                            print_progress_summary(completed_count, len(file_paths), "Conversion Progress", conversion_start_time)
                            last_shown_percent = new_percent
                        
                        self.progress_tracker.update_stage_progress(Stage.CONVERTING, completed=1)
                    else:
                        print(f"❌ Failed to convert {os.path.basename(file_path)}", flush=True)
                        self.progress_tracker.update_stage_progress(Stage.CONVERTING, failed=1)
                except Exception as e:
                    print(f"❌ Failed to convert {os.path.basename(file_path)}: {e}", flush=True)
                    self.progress_tracker.update_stage_progress(Stage.CONVERTING, failed=1)
        
        self.progress_tracker.end_stage(Stage.CONVERTING)
        return converted_texts
    
    def translate_texts_parallel(self, texts: Dict[str, str]) -> Dict[str, str]:
        """Translate texts in parallel if needed."""
        # Filter texts that need translation
        texts_to_translate = {
            filename: text for filename, text in texts.items()
            if text and not is_english(text)
        }
        
        if not texts_to_translate:
            print("📝 All texts are already in English, skipping translation")
            return texts
        
        self.progress_tracker.start_stage(Stage.TRANSLATING, len(texts_to_translate))
        
        translated_texts = texts.copy()  # Start with original texts
        print(f"🌐 Translating {len(texts_to_translate)} texts using {self.config.translation_workers} workers...")
        
        translation_start_time = time.time()
        completed_count = 0
        last_shown_percent = 0
        
        with ThreadPoolExecutor(max_workers=self.config.translation_workers) as executor:
            future_to_filename = {
                executor.submit(_translate_single_text_standalone, text): filename
                for filename, text in texts_to_translate.items()
            }
            
            for future in as_completed(future_to_filename):
                filename = future_to_filename[future]
                try:
                    result = future.result()
                    if result:
                        translated_texts[filename] = result
                        completed_count += 1
                        print(f"✅ Translated: {filename} [{completed_count}/{len(texts_to_translate)}]", flush=True)
                        
                        # Show progress summary at 10% intervals
                        should_show, new_percent = should_show_progress(completed_count, len(texts_to_translate), last_shown_percent)
                        if should_show:
                            print_progress_summary(completed_count, len(texts_to_translate), "Translation Progress", translation_start_time)
                            last_shown_percent = new_percent
                        
                        self.progress_tracker.update_stage_progress(Stage.TRANSLATING, completed=1)
                    else:
                        print(f"❌ Failed to translate {filename}", flush=True)
                        self.progress_tracker.update_stage_progress(Stage.TRANSLATING, failed=1)
                except Exception as e:
                    print(f"❌ Failed to translate {filename}: {e}", flush=True)
                    self.progress_tracker.update_stage_progress(Stage.TRANSLATING, failed=1)
        
        self.progress_tracker.end_stage(Stage.TRANSLATING)
        return translated_texts
    
    def split_texts_parallel(self, texts: Dict[str, str], sharepoint_url_map: Dict[str, str]) -> tuple:
        """Split texts into semantic chunks in parallel."""
        self.progress_tracker.start_stage(Stage.SPLITTING, len(texts))
        
        all_texts = []
        all_metadata = []
        print(f"🏗️  Splitting {len(texts)} texts using {self.config.splitting_workers} workers...")
        
        splitting_start_time = time.time()
        completed_count = 0
        last_shown_percent = 0
        
        with ThreadPoolExecutor(max_workers=self.config.splitting_workers) as executor:
            future_to_filename = {
                executor.submit(_split_single_text_standalone, filename, text): filename
                for filename, text in texts.items()
                if text  # Only process non-empty texts
            }
            
            for future in as_completed(future_to_filename):
                filename = future_to_filename[future]
                try:
                    result = future.result()
                    if result:
                        chunks, metadata = result
                        # Add SharePoint URL to metadata
                        for entry in metadata:
                            entry["sharepoint_url"] = sharepoint_url_map.get(filename, "")
                        
                        all_texts.extend(chunks)
                        all_metadata.extend(metadata)
                        completed_count += 1
                        print(f"✅ Split: {filename} -> {len(chunks)} chunks [{completed_count}/{len(texts)}]", flush=True)
                        
                        # Show progress summary at 10% intervals
                        should_show, new_percent = should_show_progress(completed_count, len(texts), last_shown_percent)
                        if should_show:
                            print_progress_summary(completed_count, len(texts), "Splitting Progress", splitting_start_time)
                            last_shown_percent = new_percent
                        
                        self.progress_tracker.update_stage_progress(Stage.SPLITTING, completed=1)
                    else:
                        print(f"❌ Failed to split {filename}", flush=True)
                        self.progress_tracker.update_stage_progress(Stage.SPLITTING, failed=1)
                except Exception as e:
                    print(f"❌ Failed to split {filename}: {e}", flush=True)
                    self.progress_tracker.update_stage_progress(Stage.SPLITTING, failed=1)
        
        self.progress_tracker.end_stage(Stage.SPLITTING)
        return all_texts, all_metadata
    
    def embed_and_store_parallel(self, texts: List[str], metadata: List[Dict[str, Any]], 
                                ingestor, batch_size: int = 64) -> bool:
        """Embed texts and store in vector database."""
        self.progress_tracker.start_stage(Stage.EMBEDDING, len(texts))
        
        try:
            # Use existing batch processing from ingestor
            ingestor.ingest_texts(texts=texts, metadata=metadata, batch_size=batch_size)
            self.progress_tracker.update_stage_progress(Stage.EMBEDDING, completed=len(texts))
            self.progress_tracker.end_stage(Stage.EMBEDDING)
            return True
        except Exception as e:
            logger.error(f"Failed to embed and store texts: {e}")
            self.progress_tracker.update_stage_progress(Stage.EMBEDDING, failed=len(texts))
            self.progress_tracker.end_stage(Stage.EMBEDDING)
            return False
    
    def monitor_resources(self):
        """Monitor resource usage during processing."""
        log_memory_usage()
        
        # Check memory usage and warn if too high
        try:
            import psutil
            process = psutil.Process()
            memory_gb = process.memory_info().rss / 1024 / 1024 / 1024
            
            if memory_gb > self.config.max_memory_gb:
                print(f"⚠️ Memory usage ({memory_gb:.1f} GB) exceeds limit ({self.config.max_memory_gb} GB)")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Could not check memory usage: {e}")
    
    def cleanup(self):
        """Clean up resources."""
        if self.temp_dir:
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                print("🧹 Cleaned up temporary directory")
            except Exception as e:
                logger.warning(f"Could not clean up temp directory: {e}") 