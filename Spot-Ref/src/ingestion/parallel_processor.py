"""
parallel_processor.py

Main orchestrator for parallel ingestion workflow.
Coordinates all stages: download → convert → translate → split → embed
"""

import logging
import tempfile
import time
from typing import List, Dict, Any

from .worker_pool import WorkerPool
from .progress_tracker import get_progress_tracker
from src.vector_db.vector_store_ingestor import QdrantIngestor
from .get_sharepoint_files import SharePoint

logger = logging.getLogger(__name__)

def print_section(title: str):
    """Print a clean section header."""
    print(f"\n📋 {title}")
    print("-" * 50)

class ParallelIngestor:
    """Main class for parallel ingestion workflow."""
    
    def __init__(self):
        self.worker_pool = WorkerPool()
        self.progress_tracker = get_progress_tracker()
        self.sharepoint_client = None
        
        print("🚀 Parallel ingestion system initialized")
    
    def run(self, args):
        """Execute the parallel ingestion workflow."""
        print(f"📊 Collection: {args.collection}")
        print(f"🔗 Qdrant: {args.host}:{args.port}")
        print(f"📦 Batch size: {args.batch_size}")
        print(f"📁 Mode: {args.mode}")
        
        self.progress_tracker.start_overall()
        
        try:
            print_section("FETCHING FILES FROM SHAREPOINT")
            
            # Stage 1: Get file list from SharePoint
            ppt_files = self._get_sharepoint_files(args.mode)
            if not ppt_files:
                print("❌ No files found to process")
                return
            
            print(f"📋 Found {len(ppt_files)} files to process")
            
            # Stage 2: Download files in parallel
            with tempfile.TemporaryDirectory() as temp_dir:
                print_section("DOWNLOADING FILES (PARALLEL)")
                
                downloaded_files, sharepoint_url_map = self.worker_pool.download_files_parallel(
                    ppt_files, temp_dir
                )
                
                if not downloaded_files:
                    print("❌ No files downloaded successfully")
                    return
                
                print(f"✅ Downloaded {len(downloaded_files)} files")
                
                print_section("CONVERTING FILES (PARALLEL)")
                
                # Stage 3: Convert files to text in parallel
                file_paths = list(downloaded_files.values())
                converted_texts = self.worker_pool.convert_files_parallel(file_paths)
                
                if not converted_texts:
                    print("❌ No files converted successfully")
                    return
                
                print(f"✅ Converted {len(converted_texts)} files to text")
                
                print_section("TRANSLATING FILES (PARALLEL)")
                
                # Stage 4: Translate texts in parallel (if needed)
                translated_texts = self.worker_pool.translate_texts_parallel(converted_texts)
                
                print(f"✅ Processed {len(translated_texts)} texts for translation")
                
                print_section("SEMANTIC SPLITTING (PARALLEL)")
                
                # Stage 5: Split texts into semantic chunks in parallel
                all_texts, all_metadata = self.worker_pool.split_texts_parallel(
                    translated_texts, sharepoint_url_map
                )
                
                if not all_texts:
                    print("❌ No texts split successfully")
                    return
                
                print(f"✅ Split into {len(all_texts)} semantic chunks")
                
                print_section("INGESTING TO VECTOR DATABASE")
                
                # Stage 6: Embed and store in vector database
                ingestor = QdrantIngestor(
                    collection_name=args.collection,
                    host=args.host,
                    port=args.port
                )
                
                print(f"📤 Ingesting {len(all_texts)} chunks to Qdrant...")
                ingestion_start_time = time.time()
                
                success = self.worker_pool.embed_and_store_parallel(
                    all_texts, all_metadata, ingestor, args.batch_size
                )
                
                ingestion_time = time.time() - ingestion_start_time
                
                if success:
                    print_section("INGESTION COMPLETE")
                    print(f"✅ Successfully ingested {len(all_texts)} chunks")
                    print(f"📊 Total files processed: {len(converted_texts)}")
                    print(f"🎯 Collection: {args.collection}")
                    print(f"⏱️  Ingestion time: {ingestion_time:.1f}s")
                    print(f"🚀 Processing rate: {len(all_texts)/ingestion_time:.1f} chunks/s")
                    print("=" * 60)
                else:
                    print("❌ Failed to ingest chunks to vector database")
                    return
                
                # Monitor resources
                self.worker_pool.monitor_resources()
        
        except Exception as e:
            logger.error(f"❌ Parallel ingestion failed: {e}")
            raise
        finally:
            # Clean up resources
            self.worker_pool.cleanup()
            self.progress_tracker.end_overall()
    
    def _get_sharepoint_files(self, mode: str) -> List[str]:
        """Get list of files from SharePoint based on mode."""
        try:
            if not self.sharepoint_client:
                self.sharepoint_client = SharePoint()
            
            # Get all pptx files from SharePoint
            ppt_files = self.sharepoint_client.list_ppt_files()
            
            if not ppt_files:
                print("❌ No PPT files found in SharePoint")
                return []
            
            # Filter based on mode
            if mode == '5':
                return ppt_files[:5]
            elif mode == 'all':
                return ppt_files
            else:
                raise ValueError(f"Unknown mode: {mode}")
        
        except Exception as e:
            logger.error(f"Failed to get SharePoint files: {e}")
            return []
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get current progress summary."""
        return self.progress_tracker.get_overall_progress()

def run_parallel_ingestion(args):
    """Entry point for parallel ingestion."""
    processor = ParallelIngestor()
    processor.run(args)
