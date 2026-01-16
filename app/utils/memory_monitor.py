"""Enhanced memory monitoring utilities with threshold warnings."""
import os
import sys
from typing import Dict, Optional, Tuple
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import psutil, but make it optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

# Memory threshold configuration (in MB)
# Can be overridden via environment variables
MEMORY_WARNING_THRESHOLD_MB = int(os.getenv("MEMORY_WARNING_THRESHOLD_MB", "512"))  # 512 MB
MEMORY_CRITICAL_THRESHOLD_MB = int(os.getenv("MEMORY_CRITICAL_THRESHOLD_MB", "1024"))  # 1 GB
MEMORY_DELTA_WARNING_MB = int(os.getenv("MEMORY_DELTA_WARNING_MB", "256"))  # 256 MB increase
MEMORY_DELTA_CRITICAL_MB = int(os.getenv("MEMORY_DELTA_CRITICAL_MB", "512"))  # 512 MB increase

# System memory thresholds (percentage)
SYSTEM_MEMORY_WARNING_PCT = float(os.getenv("SYSTEM_MEMORY_WARNING_PCT", "75.0"))  # 75%
SYSTEM_MEMORY_CRITICAL_PCT = float(os.getenv("SYSTEM_MEMORY_CRITICAL_PCT", "90.0"))  # 90%


class MemoryStats:
    """Memory statistics container."""

    def __init__(
        self,
        process_memory_mb: float,
        process_memory_delta_mb: float = 0.0,
        system_memory_total_mb: Optional[float] = None,
        system_memory_available_mb: Optional[float] = None,
        system_memory_percent: Optional[float] = None,
        peak_memory_mb: Optional[float] = None,
    ):
        self.process_memory_mb = process_memory_mb
        self.process_memory_delta_mb = process_memory_delta_mb
        self.system_memory_total_mb = system_memory_total_mb
        self.system_memory_available_mb = system_memory_available_mb
        self.system_memory_percent = system_memory_percent
        self.peak_memory_mb = peak_memory_mb

    def to_dict(self) -> Dict:
        """
        Convert MemoryStats object to a dictionary for logging or serialization.

        Returns:
            Dictionary with the following keys (all values in MB unless specified):
            - process_memory_mb: Current process memory usage (float, MB)
            - process_memory_delta_mb: Change in memory since start (float, MB)
            - system_memory_total_mb: Total system memory (float, MB, or None if unavailable)
            - system_memory_available_mb: Available system memory (float, MB, or None if unavailable)
            - system_memory_percent: System memory usage percentage (float, 0-100, or None if unavailable)
            - peak_memory_mb: Peak memory usage during operation (float, MB, or None if not tracked)
        """
        return {
            "process_memory_mb": round(self.process_memory_mb, 2),
            "process_memory_delta_mb": round(self.process_memory_delta_mb, 2),
            "system_memory_total_mb": (
                round(self.system_memory_total_mb, 2) if self.system_memory_total_mb else None
            ),
            "system_memory_available_mb": (
                round(self.system_memory_available_mb, 2)
                if self.system_memory_available_mb
                else None
            ),
            "system_memory_percent": (
                round(self.system_memory_percent, 2) if self.system_memory_percent else None
            ),
            "peak_memory_mb": (
                round(self.peak_memory_mb, 2) if self.peak_memory_mb else None
            ),
        }


def get_memory_usage(process_id: Optional[int] = None) -> float:
    """
    Get current process memory usage in MB.
    
    Args:
        process_id: Process ID (defaults to current process)
        
    Returns:
        Memory usage in MB, or 0.0 if psutil is not available or an error occurs
    """
    if not PSUTIL_AVAILABLE:
        logger.warning("psutil is not available, cannot get memory usage")
        return 0.0

    try:
        if process_id is None:
            process_id = os.getpid()
        process = psutil.Process(process_id)
        return process.memory_info().rss / (1024 * 1024)
    except psutil.NoSuchProcess as e:
        logger.warning("Process not found", process_id=process_id, error=str(e))
        return 0.0
    except psutil.AccessDenied as e:
        logger.warning("Access denied to process memory", process_id=process_id, error=str(e))
        return 0.0
    except Exception as e:
        logger.error("Failed to get memory usage", process_id=process_id, error=str(e), exc_info=True)
        return 0.0


def get_system_memory() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Get system memory information.
    
    Returns:
        Tuple of (total_mb, available_mb, percent_used) or (None, None, None) if unavailable or on error
    """
    if not PSUTIL_AVAILABLE:
        logger.warning("psutil is not available, cannot get system memory")
        return None, None, None

    try:
        mem = psutil.virtual_memory()
        total_mb = mem.total / (1024 * 1024)
        available_mb = mem.available / (1024 * 1024)
        percent = mem.percent
        return total_mb, available_mb, percent
    except psutil.AccessDenied as e:
        logger.warning("Access denied to system memory information", error=str(e))
        return None, None, None
    except Exception as e:
        logger.error("Failed to get system memory", error=str(e), exc_info=True)
        return None, None, None


def get_memory_stats(
    start_memory_mb: Optional[float] = None,
    peak_memory_mb: Optional[float] = None,
) -> MemoryStats:
    """
    Get comprehensive memory statistics.
    
    Args:
        start_memory_mb: Starting memory usage (for delta calculation)
        peak_memory_mb: Peak memory usage during operation
        
    Returns:
        MemoryStats object with current memory information
    """
    current_memory = get_memory_usage()
    memory_delta = current_memory - start_memory_mb if start_memory_mb else 0.0
    system_total, system_available, system_percent = get_system_memory()

    return MemoryStats(
        process_memory_mb=current_memory,
        process_memory_delta_mb=memory_delta,
        system_memory_total_mb=system_total,
        system_memory_available_mb=system_available,
        system_memory_percent=system_percent,
        peak_memory_mb=peak_memory_mb,
    )


def check_memory_thresholds(
    memory_stats: MemoryStats,
    operation_name: str = "operation",
    checkpoint_name: Optional[str] = None,
) -> Dict[str, bool]:
    """
    Check memory usage against thresholds and log warnings if exceeded.
    
    Args:
        memory_stats: MemoryStats object with current memory information
        operation_name: Name of the operation being monitored
        checkpoint_name: Optional checkpoint name
        
    Returns:
        Dict with threshold check results:
        {
            "process_warning": bool,
            "process_critical": bool,
            "delta_warning": bool,
            "delta_critical": bool,
            "system_warning": bool,
            "system_critical": bool,
        }
    """
    results = {
        "process_warning": False,
        "process_critical": False,
        "delta_warning": False,
        "delta_critical": False,
        "system_warning": False,
        "system_critical": False,
    }

    context = {
        "operation": operation_name,
        **(memory_stats.to_dict()),
    }
    if checkpoint_name:
        context["checkpoint"] = checkpoint_name

    # Check process memory thresholds
    if memory_stats.process_memory_mb >= MEMORY_CRITICAL_THRESHOLD_MB:
        results["process_critical"] = True
        results["process_warning"] = True  # Critical also implies warning
        logger.warning(
            "CRITICAL: Process memory usage exceeds critical threshold",
            **context,
            threshold_mb=MEMORY_CRITICAL_THRESHOLD_MB,
        )
    elif memory_stats.process_memory_mb >= MEMORY_WARNING_THRESHOLD_MB:
        results["process_warning"] = True
        logger.warning(
            "WARNING: Process memory usage exceeds warning threshold",
            **context,
            threshold_mb=MEMORY_WARNING_THRESHOLD_MB,
        )

    # Check memory delta thresholds
    if memory_stats.process_memory_delta_mb >= MEMORY_DELTA_CRITICAL_MB:
        results["delta_critical"] = True
        results["delta_warning"] = True  # Critical also implies warning
        logger.warning(
            "CRITICAL: Process memory increase exceeds critical threshold",
            **context,
            delta_threshold_mb=MEMORY_DELTA_CRITICAL_MB,
        )
    elif memory_stats.process_memory_delta_mb >= MEMORY_DELTA_WARNING_MB:
        results["delta_warning"] = True
        logger.warning(
            "WARNING: Process memory increase exceeds warning threshold",
            **context,
            delta_threshold_mb=MEMORY_DELTA_WARNING_MB,
        )

    # Check system memory thresholds
    if memory_stats.system_memory_percent is not None:
        if memory_stats.system_memory_percent >= SYSTEM_MEMORY_CRITICAL_PCT:
            results["system_critical"] = True
            results["system_warning"] = True  # Critical also implies warning
            logger.warning(
                "CRITICAL: System memory usage exceeds critical threshold",
                **context,
                system_threshold_pct=SYSTEM_MEMORY_CRITICAL_PCT,
            )
        elif memory_stats.system_memory_percent >= SYSTEM_MEMORY_WARNING_PCT:
            results["system_warning"] = True
            logger.warning(
                "WARNING: System memory usage exceeds warning threshold",
                **context,
                system_threshold_pct=SYSTEM_MEMORY_WARNING_PCT,
            )

    return results


def log_memory_checkpoint(
    operation_name: str,
    checkpoint_name: str,
    start_memory_mb: Optional[float] = None,
    peak_memory_mb: Optional[float] = None,
    metadata: Optional[Dict] = None,
) -> MemoryStats:
    """
    Log memory usage at a checkpoint with threshold checking.
    
    Args:
        operation_name: Name of the operation
        checkpoint_name: Name of the checkpoint
        start_memory_mb: Starting memory usage (for delta calculation)
        peak_memory_mb: Peak memory usage during operation
        metadata: Additional metadata to include in logs
        
    Returns:
        MemoryStats object with current memory information
    """
    memory_stats = get_memory_stats(start_memory_mb, peak_memory_mb)
    threshold_results = check_memory_thresholds(memory_stats, operation_name, checkpoint_name)

    log_data = {
        "operation": operation_name,
        "checkpoint": checkpoint_name,
        **memory_stats.to_dict(),
        "thresholds_exceeded": {
            k: v for k, v in threshold_results.items() if v
        },
    }
    if metadata:
        log_data.update(metadata)

    # Log at appropriate level based on thresholds
    if any(threshold_results.values()):
        logger.warning("Memory checkpoint with threshold warnings", **log_data)
    else:
        logger.info("Memory checkpoint", **log_data)

    return memory_stats

