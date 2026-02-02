"""
ingest.py

Central entry point for semantic ingestion into Qdrant.
Configuration is controlled entirely through environment variables in .env file.
Handles semantic splitting via llm_semantic_splitter.
Uses QdrantIngestor from vector_store_ingestor.py.

Uses parallel processing for optimal performance.
"""

import os
import logging
import time
from dotenv import load_dotenv

load_dotenv()

# Configure logging for errors only - clean CLI output
logging.basicConfig(
    level=logging.ERROR,
    format='❌ %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def print_banner():
    """Print a clean banner for the ingestion process."""
    print("=" * 60)
    print("🚀 SPOT-REF DOCUMENT INGESTION")
    print("=" * 60)

def print_section(title: str):
    """Print a clean section header."""
    print(f"\n📋 {title}")
    print("-" * 50)

def print_progress_summary(current: int, total: int, phase: str, start_time: float):
    """Print progress summary every 10%."""
    if total == 0:
        return
    
    progress = (current / total) * 100
    
    # Only show on 10% intervals or at completion
    if progress % 10 == 0 or current == total:
        elapsed = time.time() - start_time
        rate = current / elapsed if elapsed > 0 else 0
        
        if current < total and rate > 0:
            remaining = (total - current) / rate
            eta = f"ETA: {remaining:.0f}s"
        else:
            eta = "Complete"
        
        print(f"📊 {phase}: {current}/{total} ({progress:.0f}%) | {eta} | {rate:.1f}/s")

def get_config_from_env():
    """Get configuration from environment variables."""
    config = {
        'mode': os.getenv('INGESTION_MODE', '5'),
        'collection': os.getenv('QDRANT_COLLECTION', 'spot-ref-docs'),
        'host': os.getenv('QDRANT_HOST', 'localhost'),
        'port': int(os.getenv('QDRANT_PORT', '6333')),
        'batch_size': int(os.getenv('BATCH_SIZE', '64'))
    }
    
    # Validate mode
    if config['mode'] not in ['5', 'all']:
        print(f"⚠️  Invalid INGESTION_MODE: {config['mode']}. Using '5' as default.")
        config['mode'] = '5'
    
    return config

def main():
    """Main ingestion function using environment variables for configuration."""
    print_banner()
    print("🚀 Mode: Parallel Processing")
    
    # Get configuration from environment variables
    config = get_config_from_env()
    
    print(f"📊 Collection: {config['collection']}")
    print(f"🔗 Qdrant: {config['host']}:{config['port']}")
    print(f"📦 Batch size: {config['batch_size']}")
    print(f"📁 Mode: {config['mode']}")
    
    try:
        from src.ingestion.parallel_processor import run_parallel_ingestion
        
        # Create a simple args object for compatibility
        class Args:
            def __init__(self, config):
                self.mode = config['mode']
                self.collection = config['collection']
                self.host = config['host']
                self.port = config['port']
                self.batch_size = config['batch_size']
        
        args = Args(config)
        run_parallel_ingestion(args)
        
    except ImportError as e:
        logger.error(f"Failed to import parallel processor: {e}")
        print("❌ Parallel processing is required but not available")
        raise
    except Exception as e:
        logger.error(f"Parallel ingestion failed: {e}")
        raise

if __name__ == '__main__':
    main()
