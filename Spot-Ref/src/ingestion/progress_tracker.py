import time
import logging
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import os

logger = logging.getLogger(__name__)

class Stage(Enum):
    """Ingestion pipeline stages."""
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    TRANSLATING = "translating"
    SPLITTING = "splitting"
    EMBEDDING = "embedding"
    COMPLETE = "complete"

@dataclass
class StageProgress:
    """Progress tracking for a single stage."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100
    
    @property
    def duration(self) -> float:
        """Calculate stage duration."""
        if self.start_time is None:
            return 0.0
        end_time = self.end_time or time.time()
        return end_time - self.start_time
    
    @property
    def rate_per_second(self) -> float:
        """Calculate processing rate."""
        if self.duration == 0 or self.completed == 0:
            return 0.0
        return self.completed / self.duration
    
    @property
    def eta_seconds(self) -> float:
        """Calculate estimated time to completion."""
        if self.rate_per_second == 0 or self.completed == 0:
            return 0.0
        remaining = self.total - self.completed
        return remaining / self.rate_per_second

class ProgressTracker:
    """Tracks progress across all ingestion stages."""
    
    def __init__(self, enable_tracking: bool = True):
        self.enable_tracking = enable_tracking
        self.stages: Dict[Stage, StageProgress] = {}
        self.current_stage: Optional[Stage] = None
        self.overall_start_time: Optional[float] = None
        self.overall_end_time: Optional[float] = None
        self.lock = threading.Lock()
        
        # Initialize all stages
        for stage in Stage:
            self.stages[stage] = StageProgress()
    
    def start_overall(self):
        """Start tracking overall progress."""
        if not self.enable_tracking:
            return
        
        with self.lock:
            self.overall_start_time = time.time()
            logger.info("🚀 Starting parallel ingestion workflow")
    
    def end_overall(self):
        """End tracking overall progress."""
        if not self.enable_tracking:
            return
        
        with self.lock:
            self.overall_end_time = time.time()
            duration = self.overall_end_time - (self.overall_start_time or self.overall_end_time)
            logger.info(f"✅ Parallel ingestion completed in {duration:.2f} seconds")
            self._log_final_summary()
    
    def start_stage(self, stage: Stage, total_items: int):
        """Start tracking a specific stage."""
        if not self.enable_tracking:
            return
        
        with self.lock:
            self.current_stage = stage
            stage_progress = self.stages[stage]
            stage_progress.total = total_items
            stage_progress.completed = 0
            stage_progress.failed = 0
            stage_progress.start_time = time.time()
            stage_progress.end_time = None
            
            logger.info(f"📊 Starting {stage.value} stage with {total_items} items")
    
    def end_stage(self, stage: Stage):
        """End tracking a specific stage."""
        if not self.enable_tracking:
            return
        
        with self.lock:
            stage_progress = self.stages[stage]
            stage_progress.end_time = time.time()
            
            logger.info(f"✅ Completed {stage.value} stage: "
                       f"{stage_progress.completed}/{stage_progress.total} items "
                       f"({stage_progress.failed} failed) in {stage_progress.duration:.2f}s")
    
    def update_stage_progress(self, stage: Stage, completed: int = 1, failed: int = 0):
        """Update progress for a specific stage."""
        if not self.enable_tracking:
            return
        
        with self.lock:
            stage_progress = self.stages[stage]
            stage_progress.completed += completed
            stage_progress.failed += failed
            
            # Log periodic updates
            if self._should_log_update(stage_progress):
                self._log_stage_update(stage, stage_progress)
    
    def get_overall_progress(self) -> Dict[str, Any]:
        """Get overall progress statistics."""
        if not self.enable_tracking:
            return {}
        
        with self.lock:
            total_items = sum(stage.total for stage in self.stages.values())
            completed_items = sum(stage.completed for stage in self.stages.values())
            failed_items = sum(stage.failed for stage in self.stages.values())
            
            overall_percent = (completed_items / total_items * 100) if total_items > 0 else 0
            
            return {
                "total_items": total_items,
                "completed_items": completed_items,
                "failed_items": failed_items,
                "overall_percent": overall_percent,
                "current_stage": self.current_stage.value if self.current_stage else None,
                "duration": self._get_overall_duration(),
                "stages": {stage.value: {
                    "total": prog.total,
                    "completed": prog.completed,
                    "failed": prog.failed,
                    "progress_percent": prog.progress_percent,
                    "eta_seconds": prog.eta_seconds
                } for stage, prog in self.stages.items()}
            }
    
    def _should_log_update(self, stage_progress: StageProgress) -> bool:
        """Determine if we should log a progress update."""
        if stage_progress.total == 0:
            return False
        
        # Log every 10% progress or every 10 items, whichever is more frequent
        progress_threshold = max(1, stage_progress.total // 10)
        return stage_progress.completed % progress_threshold == 0
    
    def _log_stage_update(self, stage: Stage, stage_progress: StageProgress):
        """Log a stage progress update."""
        eta_str = ""
        if stage_progress.eta_seconds > 0:
            eta_str = f", ETA: {stage_progress.eta_seconds:.0f}s"
        
        logger.info(f"📈 {stage.value}: {stage_progress.completed}/{stage_progress.total} "
                   f"({stage_progress.progress_percent:.1f}%){eta_str}")
    
    def _get_overall_duration(self) -> float:
        """Get overall duration."""
        if self.overall_start_time is None:
            return 0.0
        end_time = self.overall_end_time or time.time()
        return end_time - self.overall_start_time
    
    def _log_final_summary(self):
        """Log final summary of all stages."""
        logger.info("📋 Final Summary:")
        for stage, progress in self.stages.items():
            if progress.total > 0:
                success_rate = ((progress.completed - progress.failed) / progress.total) * 100
                logger.info(f"  {stage.value}: {progress.completed}/{progress.total} "
                           f"({progress.failed} failed, {success_rate:.1f}% success rate)")

# Global progress tracker instance
_progress_tracker: Optional[ProgressTracker] = None

def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker instance."""
    global _progress_tracker
    if _progress_tracker is None:
        enable_tracking = os.getenv('ENABLE_PROGRESS_TRACKING', 'true').lower() == 'true'
        _progress_tracker = ProgressTracker(enable_tracking=enable_tracking)
    return _progress_tracker

def log_memory_usage():
    """Log current memory usage if available."""
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        logger.info(f"💾 Memory usage: {memory_mb:.1f} MB")
    except ImportError:
        # psutil not available, skip memory logging
        pass
    except Exception as e:
        logger.warning(f"Could not get memory usage: {e}")

def format_duration(seconds: float) -> str:
    """Format duration in a human-readable way."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h" 