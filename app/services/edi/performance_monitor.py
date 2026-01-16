"""Performance monitoring utilities for EDI parsing."""
import time
import sys
import os
from typing import Dict, Optional, Callable
from app.utils.logger import get_logger
from app.utils.memory_monitor import (
    get_memory_usage,
    get_memory_stats,
    check_memory_thresholds,
    MemoryStats,
)

logger = get_logger(__name__)

# Try to import psutil, but make it optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


class PerformanceMonitor:
    """Monitor performance metrics during EDI parsing with enhanced memory tracking."""

    def __init__(self, operation_name: str = "edi_parsing"):
        self.operation_name = operation_name
        self.start_time = None
        self.start_memory = None
        self.peak_memory = None
        self.process = psutil.Process(os.getpid()) if PSUTIL_AVAILABLE else None
        self.checkpoints = []

    def start(self) -> None:
        """
        Start performance monitoring.
        
        Initializes timing and memory tracking, records baseline metrics.
        """
        self.start_time = time.time()
        self.start_memory = get_memory_usage()
        self.peak_memory = self.start_memory
        
        # Get initial system memory info
        memory_stats = get_memory_stats(self.start_memory, self.peak_memory)
        
        logger.info(
            "Performance monitoring started",
            operation=self.operation_name,
            initial_memory_mb=round(self.start_memory, 2),
            system_memory_percent=(
                round(memory_stats.system_memory_percent, 2)
                if memory_stats.system_memory_percent
                else None
            ),
        )

    def checkpoint(self, name: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Record a checkpoint with current metrics and memory threshold checking.
        
        Args:
            name: Checkpoint name
            metadata: Additional metadata to log
            
        Returns:
            Dict with checkpoint metrics
        """
        elapsed = time.time() - self.start_time if self.start_time else 0
        current_memory = get_memory_usage()
        
        # Update peak memory
        if current_memory > (self.peak_memory or 0):
            self.peak_memory = current_memory
        
        # Get comprehensive memory stats
        memory_stats = get_memory_stats(self.start_memory, self.peak_memory)
        
        # Check thresholds and log warnings if needed
        threshold_results = check_memory_thresholds(memory_stats, self.operation_name, name)
        
        checkpoint_data = {
            "name": name,
            "elapsed_seconds": round(elapsed, 3),
            "memory_mb": round(memory_stats.process_memory_mb, 2),
            "memory_delta_mb": round(memory_stats.process_memory_delta_mb, 2),
            "peak_memory_mb": (
                round(memory_stats.peak_memory_mb, 2) if memory_stats.peak_memory_mb else None
            ),
            "system_memory_percent": (
                round(memory_stats.system_memory_percent, 2)
                if memory_stats.system_memory_percent
                else None
            ),
            "system_memory_available_mb": (
                round(memory_stats.system_memory_available_mb, 2)
                if memory_stats.system_memory_available_mb
                else None
            ),
            "thresholds_exceeded": {k: v for k, v in threshold_results.items() if v},
            "metadata": metadata or {},
        }
        
        self.checkpoints.append(checkpoint_data)
        
        # Log at appropriate level based on thresholds
        log_level_data = {
            "operation": self.operation_name,
            "checkpoint": name,
            "elapsed_seconds": round(elapsed, 3),
            **memory_stats.to_dict(),
            "thresholds_exceeded": checkpoint_data["thresholds_exceeded"],
            **(metadata or {}),
        }
        
        if any(threshold_results.values()):
            logger.warning("Performance checkpoint with memory warnings", **log_level_data)
        else:
            logger.info("Performance checkpoint", **log_level_data)
        
        return checkpoint_data

    def finish(self) -> Dict:
        """
        Finish monitoring and return summary with final memory check.
        
        Returns:
            Dict with performance summary
        """
        total_time = time.time() - self.start_time if self.start_time else 0
        final_memory = get_memory_usage()
        
        # Update peak if final is higher
        if final_memory > (self.peak_memory or 0):
            self.peak_memory = final_memory
        
        # Get comprehensive final memory stats
        memory_stats = get_memory_stats(self.start_memory, self.peak_memory)
        
        # Check thresholds one final time
        threshold_results = check_memory_thresholds(memory_stats, self.operation_name, "finish")
        
        summary = {
            "operation": self.operation_name,
            "total_time_seconds": round(total_time, 3),
            "initial_memory_mb": round(self.start_memory, 2) if self.start_memory else 0.0,
            "final_memory_mb": round(memory_stats.process_memory_mb, 2),
            "peak_memory_mb": (
                round(memory_stats.peak_memory_mb, 2) if memory_stats.peak_memory_mb else None
            ),
            "memory_delta_mb": round(memory_stats.process_memory_delta_mb, 2),
            "system_memory_percent": (
                round(memory_stats.system_memory_percent, 2)
                if memory_stats.system_memory_percent
                else None
            ),
            "checkpoints": self.checkpoints,
            "thresholds_exceeded": {k: v for k, v in threshold_results.items() if v},
        }
        
        # Log at appropriate level
        log_data = {
            "operation": self.operation_name,
            "total_time_seconds": round(total_time, 3),
            **memory_stats.to_dict(),
            "checkpoint_count": len(self.checkpoints),
            "thresholds_exceeded": summary["thresholds_exceeded"],
        }
        
        if any(threshold_results.values()):
            logger.warning("Performance monitoring complete with memory warnings", **log_data)
        else:
            logger.info("Performance monitoring complete", **log_data)
        
        return summary


def monitor_performance(operation_name: str = "operation"):
    """
    Decorator to monitor performance of a function.
    
    Usage:
        @monitor_performance("parse_edi_file")
        def parse_file(content: str) -> Dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            monitor = PerformanceMonitor(operation_name)
            monitor.start()
            
            try:
                result = func(*args, **kwargs)
                summary = monitor.finish()
                
                # Add performance summary to result if it's a dict
                if isinstance(result, dict):
                    result["_performance"] = summary
                
                return result
            except Exception as e:
                monitor.checkpoint("error", {"error": str(e)})
                monitor.finish()
                raise

        return wrapper

    return decorator

