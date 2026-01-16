# EDI Parsing Performance Optimization

## Overview

This document describes the performance optimizations implemented for EDI parsing, specifically targeting large file processing for production workloads.

## Optimizations Implemented

### 1. Batch Processing for Claims/Remittances

**Problem**: Previously, each claim/remittance was processed individually with a database flush after each one, causing significant overhead.

**Solution**: Implemented batch processing with configurable batch sizes (default: 50 items per batch).

**Benefits**:
- Reduced database round trips
- Improved transaction efficiency
- Better memory management
- Faster processing for large files

**Location**: `app/services/edi/parser.py` and `app/services/queue/tasks.py`

### 2. Optimized Segment Splitting

**Problem**: For very large files (>5MB), the standard string split() method could be inefficient and memory-intensive.

**Solution**: Implemented optimized segment splitting that:
- Uses character-by-character processing for very large files
- Pre-allocates lists when possible
- Reduces unnecessary string operations

**Benefits**:
- Lower memory usage for large files
- Faster segment parsing
- Better scalability

**Location**: `app/services/edi/parser.py::_split_segments()`

### 3. Progress Tracking and Logging

**Problem**: No visibility into parsing progress for large files, making it difficult to monitor and debug.

**Solution**: Added progress logging at regular intervals (every 100 items) for large files.

**Benefits**:
- Better observability
- Easier debugging
- Performance monitoring

**Location**: `app/services/edi/parser.py::_parse_837()` and `_parse_835()`

### 4. Batch Database Operations

**Problem**: Individual `db.flush()` calls after each claim/remittance created significant database overhead.

**Solution**: Replaced individual flushes with `bulk_save_objects()` for batch commits.

**Benefits**:
- Reduced database overhead
- Faster database operations
- Better transaction management

**Location**: `app/services/queue/tasks.py::process_edi_file()`

### 5. Enhanced Performance Monitoring

**Problem**: No way to track memory usage and performance metrics during parsing.

**Solution**: Implemented enhanced `PerformanceMonitor` class with:
- Memory usage tracking (initial, current, delta, peak)
- System memory monitoring (total, available, percentage)
- Automatic threshold warnings (process, delta, system)
- Processing time tracking
- Checkpoints at key stages with detailed metrics

**Benefits**:
- Performance visibility
- Memory leak detection
- Automatic warnings when thresholds exceeded
- System-wide memory awareness
- Optimization opportunities identification

**Location**: 
- `app/services/edi/performance_monitor.py` - PerformanceMonitor class
- `app/utils/memory_monitor.py` - Memory monitoring utilities

**Configuration**: See [MEMORY_MONITORING.md](MEMORY_MONITORING.md) for threshold configuration.

### 6. Memory-Efficient Processing

**Problem**: Large files could cause memory issues when loading all segments at once.

**Solution**: 
- Optimized segment splitting for large files
- Batch processing to reduce memory footprint
- Garbage collection hints after batches

**Benefits**:
- Lower memory usage
- Better handling of very large files
- Reduced risk of out-of-memory errors

## Performance Improvements

### Expected Improvements

For a file with 200 claims:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Processing Time | ~60s | ~20-30s | 50-66% faster |
| Database Operations | 200 flushes | 4 batch commits | 98% reduction |
| Memory Usage | High (all in memory) | Optimized (batched) | 30-50% reduction |
| Progress Visibility | None | Full tracking | New feature |

### Benchmarks

Run performance tests to see actual improvements:

```bash
# Run performance tests
pytest tests/test_performance.py -m performance -v

# Run large file optimization tests
pytest tests/test_large_file_optimization.py -v
```

## Configuration

### Batch Size

The batch size for processing claims/remittances is configurable:

- **Default**: 50 items per batch
- **Location**: `app/services/edi/parser.py` (BATCH_SIZE constant)
- **Adjustment**: Modify based on your system's memory and database performance

### Large File Threshold

Files larger than 10MB automatically use optimized processing:

- **Threshold**: 10MB (LARGE_FILE_THRESHOLD)
- **Location**: `app/services/edi/parser_optimized.py`
- **Note**: Currently, the optimized parser is available but the main parser uses batch processing for all files

## Usage

### Automatic Optimization

The optimizations are automatically applied:

1. **Batch Processing**: Always enabled for files with multiple claims/remittances
2. **Performance Monitoring**: Enabled for files >1MB
3. **Optimized Segment Splitting**: Enabled for files >5MB

### Performance Data

Performance metrics are included in parsing results:

```python
result = parser.parse(file_content, filename)

# Access performance data
if "_performance" in result:
    perf = result["_performance"]
    print(f"Total time: {perf['total_time_seconds']}s")
    print(f"Memory delta: {perf['memory_delta_mb']} MB")
    print(f"Checkpoints: {len(perf['checkpoints'])}")
```

## Monitoring

### Logs

Performance metrics are logged at INFO level:

```
[INFO] Processing claim blocks total_blocks=200 batch_size=50
[INFO] Parsing progress processed=100 total=200 progress_pct=50.0
[INFO] 837 file parsing complete claims_parsed=200 warnings_count=0
```

### Performance Checkpoints

Key checkpoints are tracked:
- `start`: Parsing started
- `segments_split`: Segments split into list
- `envelope_parsed`: Envelope information extracted
- `parsing_complete`: All claims/remittances parsed
- `database_commit_complete`: Database operations completed

## Best Practices

### 1. Monitor Performance

Use the performance monitoring data to:
- Identify bottlenecks
- Track memory usage
- Optimize batch sizes

### 2. Adjust Batch Size

If you experience:
- **High memory usage**: Reduce batch size (e.g., 25)
- **Slow processing**: Increase batch size (e.g., 100)
- **Database timeouts**: Reduce batch size

### 3. Large File Handling

For very large files (>100MB):
- Consider splitting files before processing
- Monitor memory usage
- Use Celery workers with appropriate memory limits

### 4. Database Optimization

Ensure database is optimized:
- Proper indexes on frequently queried columns
- Connection pooling configured correctly
- Transaction isolation levels appropriate

## Future Optimizations

Potential areas for further improvement:

1. **Streaming Parser**: Full streaming implementation for very large files
2. **Parallel Processing**: Process multiple claims in parallel (with thread safety)
3. **Caching**: Cache parsed segments for repeated processing
4. **Database Connection Pooling**: Optimize connection usage
5. **Async Processing**: Use async/await for I/O operations

## Testing

### Run Performance Tests

```bash
# All performance tests
pytest tests/test_performance.py -m performance -v

# Large file optimization tests
pytest tests/test_large_file_optimization.py -v

# With coverage
pytest tests/test_performance.py tests/test_large_file_optimization.py --cov=app/services/edi -v
```

### Performance Test Thresholds

- **Small file**: < 1 second
- **Large file (50 claims)**: < 10 seconds
- **Very large file (200 claims)**: < 30 seconds
- **Memory delta**: < 500MB for 200 claims

## Troubleshooting

### High Memory Usage

**Symptoms**: Memory usage exceeds expectations

**Solutions**:
- Reduce batch size
- Process files in smaller chunks
- Increase available memory
- Check for memory leaks in custom extractors

### Slow Processing

**Symptoms**: Processing takes longer than expected

**Solutions**:
- Check database performance
- Verify indexes are in place
- Increase batch size (if memory allows)
- Profile code to identify bottlenecks

### Database Timeouts

**Symptoms**: Database operations timeout

**Solutions**:
- Reduce batch size
- Increase database timeout settings
- Optimize database queries
- Check database connection pool settings

## Dependencies

New dependency added:
- `psutil==5.9.6`: For memory monitoring (optional, parser works without it)

## Migration Notes

### Backward Compatibility

All optimizations are backward compatible:
- Existing code continues to work
- No API changes
- Performance monitoring is optional

### Configuration Changes

No configuration changes required. Optimizations are automatic.

## References

- [Performance Testing Guide](PERFORMANCE.md)
- [EDI Parser Documentation](app/services/edi/README.md)
- [Celery Task Documentation](app/services/queue/README.md)

