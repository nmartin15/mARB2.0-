# Memory Monitoring Configuration

This document describes the enhanced memory monitoring system implemented in mARB 2.0.

## Overview

The memory monitoring system provides:
- **Detailed memory tracking** at key checkpoints during processing
- **Automatic threshold warnings** when memory usage exceeds configured limits
- **System-wide memory monitoring** (not just process memory)
- **Peak memory tracking** to identify maximum usage during operations
- **Comprehensive logging** with structured data for analysis

## Features

### 1. Process Memory Monitoring
- Tracks RSS (Resident Set Size) memory usage in MB
- Monitors memory deltas (increase from start)
- Tracks peak memory usage during operations

### 2. System Memory Monitoring
- Monitors total system memory
- Tracks available system memory
- Calculates system memory usage percentage

### 3. Threshold Warnings
- **Process memory thresholds**: Warn when process memory exceeds limits
- **Memory delta thresholds**: Warn when memory increases significantly
- **System memory thresholds**: Warn when system memory is running low

### 4. Checkpoint Tracking
Memory is logged at key checkpoints:
- **EDI Processing**: File parsing, segment splitting, database commits
- **ML Operations**: Model loading, feature extraction, predictions
- **Celery Tasks**: Episode linking, pattern detection
- **Risk Scoring**: Component calculations, ML predictions

## Configuration

Memory monitoring thresholds can be configured via environment variables in your `.env` file:

### Process Memory Thresholds

```bash
# Process memory warning threshold (MB)
# Default: 512 MB
MEMORY_WARNING_THRESHOLD_MB=512

# Process memory critical threshold (MB)
# Default: 1024 MB (1 GB)
MEMORY_CRITICAL_THRESHOLD_MB=1024
```

### Memory Delta Thresholds

```bash
# Memory increase warning threshold (MB)
# Warns when memory increases by this amount from start
# Default: 256 MB
MEMORY_DELTA_WARNING_MB=256

# Memory increase critical threshold (MB)
# Default: 512 MB
MEMORY_DELTA_CRITICAL_MB=512
```

### System Memory Thresholds

```bash
# System memory warning threshold (percentage)
# Warns when system memory usage exceeds this percentage
# Default: 75%
SYSTEM_MEMORY_WARNING_PCT=75.0

# System memory critical threshold (percentage)
# Default: 90%
SYSTEM_MEMORY_CRITICAL_PCT=90.0
```

## Usage

### Automatic Monitoring

Memory monitoring is automatically enabled for:
- **EDI file processing** (files > 1MB)
- **ML model loading and predictions**
- **Celery tasks** (episode linking, pattern detection)

### Manual Monitoring

You can manually add memory checkpoints in your code:

```python
from app.utils.memory_monitor import log_memory_checkpoint, get_memory_usage

# At the start of an operation
start_memory = get_memory_usage()

# At checkpoints
log_memory_checkpoint(
    "my_operation",
    "checkpoint_name",
    start_memory_mb=start_memory,
    metadata={"additional": "data"},
)
```

### Using PerformanceMonitor

For comprehensive monitoring with timing:

```python
from app.services.edi.performance_monitor import PerformanceMonitor

monitor = PerformanceMonitor("my_operation")
monitor.start()

# Your code here
monitor.checkpoint("step1", {"data": "value"})
monitor.checkpoint("step2")

summary = monitor.finish()
# Summary includes memory stats, timing, and threshold warnings
```

## Log Output

Memory monitoring logs structured data at INFO and WARNING levels:

### Normal Operation (INFO)
```json
{
  "event": "Memory checkpoint",
  "operation": "ml_prediction",
  "checkpoint": "features_extracted",
  "process_memory_mb": 245.32,
  "process_memory_delta_mb": 12.45,
  "system_memory_percent": 45.2,
  "system_memory_available_mb": 8192.0
}
```

### Threshold Exceeded (WARNING)
```json
{
  "event": "Memory checkpoint with threshold warnings",
  "operation": "process_edi_file",
  "checkpoint": "parsing_complete",
  "process_memory_mb": 768.45,
  "process_memory_delta_mb": 512.32,
  "system_memory_percent": 82.5,
  "thresholds_exceeded": {
    "process_warning": true,
    "delta_critical": true,
    "system_warning": true
  }
}
```

## Monitoring Locations

### EDI Processing
- **File**: `app/services/queue/tasks.py` - `process_edi_file` task
- **Checkpoints**: 
  - `task_started`
  - `parsing_complete`
  - `database_commit_complete`

### ML Operations
- **File**: `app/services/risk/ml_service.py`
- **Checkpoints**:
  - `before_load` / `after_load` (model loading)
  - `start` / `features_extracted` / `prediction_complete` (predictions)

### Episode Linking
- **File**: `app/services/queue/tasks.py` - `link_episodes` task
- **Checkpoints**:
  - `task_started`
  - `remittance_loaded`
  - `control_number_matching_complete`
  - `patient_date_matching_complete`
  - `task_complete`

### Pattern Detection
- **File**: `app/services/queue/tasks.py` - `detect_patterns` task
- **Checkpoints**:
  - `task_started`
  - `before_detection`
  - `detection_complete`

## Best Practices

### 1. Adjust Thresholds for Your Environment

Default thresholds are conservative. Adjust based on:
- Available system memory
- Typical workload sizes
- Number of concurrent workers

**For high-memory systems:**
```bash
MEMORY_WARNING_THRESHOLD_MB=2048
MEMORY_CRITICAL_THRESHOLD_MB=4096
MEMORY_DELTA_WARNING_MB=512
MEMORY_DELTA_CRITICAL_MB=1024
```

**For low-memory systems:**
```bash
MEMORY_WARNING_THRESHOLD_MB=256
MEMORY_CRITICAL_THRESHOLD_MB=512
MEMORY_DELTA_WARNING_MB=128
MEMORY_DELTA_CRITICAL_MB=256
```

### 2. Monitor System Memory

Set system memory thresholds based on your server capacity:

```bash
# For 8GB system
SYSTEM_MEMORY_WARNING_PCT=75.0
SYSTEM_MEMORY_CRITICAL_PCT=90.0

# For 16GB+ system
SYSTEM_MEMORY_WARNING_PCT=80.0
SYSTEM_MEMORY_CRITICAL_PCT=95.0
```

### 3. Analyze Logs

Use structured logging to analyze memory patterns:

```bash
# Find operations with memory warnings
grep "thresholds_exceeded" logs/app.log | jq '.operation, .checkpoint, .process_memory_mb'

# Track memory growth over time
grep "Memory checkpoint" logs/app.log | jq '.operation, .checkpoint, .process_memory_delta_mb'
```

### 4. Alert on Critical Thresholds

Set up alerts for critical memory thresholds:
- Process memory > critical threshold
- System memory > critical threshold
- Memory delta > critical threshold

## Troubleshooting

### High Memory Usage

If you see frequent memory warnings:

1. **Check for memory leaks**: Look for operations with consistently increasing memory deltas
2. **Review batch sizes**: Reduce batch sizes in EDI processing
3. **Monitor system memory**: Ensure system has adequate memory
4. **Check concurrent operations**: Too many concurrent workers can exhaust memory

### Memory Monitoring Not Working

If memory monitoring shows 0.0 or no data:

1. **Check psutil installation**: `pip install psutil`
2. **Verify permissions**: Process must have permission to read `/proc/self/status`
3. **Check logs**: Look for "Failed to get memory usage" messages

### False Positives

If you get warnings for normal operations:

1. **Adjust thresholds**: Increase thresholds to match your workload
2. **Review checkpoints**: Some operations naturally use more memory
3. **Consider operation context**: Large file processing will use more memory

## Dependencies

Memory monitoring requires:
- `psutil>=5.9.6` (already in requirements.txt)

The system gracefully degrades if psutil is not available (returns 0.0 for memory values).

## Future Enhancements

Potential improvements:
- Memory profiling integration
- Automatic memory leak detection
- Memory usage trend analysis
- Integration with monitoring systems (Prometheus, Grafana)
- Memory usage dashboards

