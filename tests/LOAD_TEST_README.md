# Load Testing for Large Files

## Overview

Comprehensive load testing suite for validating the system's ability to handle large EDI files (100MB+) with reasonable memory usage.

## Test Structure

### Test Classes

1. **TestLargeFileProcessing**: Core tests for large file processing
   - File-based processing validation (837 and 835)
   - Memory usage monitoring
   - File cleanup verification
   - Sequential processing (no memory leaks)

2. **TestFileSizeThresholds**: Tests for size threshold behavior
   - Small files (<50MB) use memory-based processing
   - Medium/large files (>50MB) use file-based processing

3. **TestLargeFileAPIIntegration**: API endpoint integration tests
   - Upload large files via API
   - Verify correct processing mode

4. **TestLargeFileErrorHandling**: Error handling tests
   - Nonexistent file paths
   - Invalid file content
   - Empty files

5. **TestLargeFileEdgeCases**: Edge case tests
   - Very large files (200MB+)
   - Files with many segments

6. **TestLargeFileMemoryEfficiency**: Memory efficiency tests
   - Linear memory scaling
   - Memory ratio validation

## Running Tests

### Quick Tests (Fast Mode)

For faster testing with smaller files:

```bash
TEST_FAST=true pytest tests/test_large_file_load.py -v -m load_test
```

### Full Tests (100MB+ files)

For comprehensive testing with full-size files:

```bash
pytest tests/test_large_file_load.py -v -m load_test
```

### Specific Test Classes

```bash
# Test file size thresholds
pytest tests/test_large_file_load.py::TestFileSizeThresholds -v

# Test API integration
pytest tests/test_large_file_load.py::TestLargeFileAPIIntegration -v

# Test error handling
pytest tests/test_large_file_load.py::TestLargeFileErrorHandling -v
```

### Skip Very Large File Tests

```bash
pytest tests/test_large_file_load.py -v -k "not very_large_file_200mb"
```

## Test Markers

- `@pytest.mark.performance`: Performance-related tests
- `@pytest.mark.load_test`: Load testing tests
- `@pytest.mark.integration`: Integration tests

## Memory Validation

### Criteria

- **Peak memory delta**: < 2000MB for 100MB files
- **Memory ratio**: < 20x file size
- **Memory per claim**: < 0.05MB
- **Memory per remittance**: < 0.05MB

### Fast Mode Adjustments

When `TEST_FAST=true`:
- Files are ~60MB instead of 100MB+
- Minimum size threshold is 10MB instead of 50MB
- Some very large file tests are skipped

## Expected Test Results

### Passing Tests

All tests should pass with:
- ✅ File-based processing used for large files
- ✅ Memory usage within limits
- ✅ No memory leaks in sequential processing
- ✅ Proper error handling
- ✅ API endpoints working correctly

### Common Issues

1. **File size too small**: Adjust `num_claims`/`num_remittances` in fixtures
2. **Memory limit exceeded**: Check system resources and batch processing settings
3. **psutil not available**: Install with `pip install psutil`
4. **Tests taking too long**: Use `TEST_FAST=true` for faster testing

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Run Load Tests (Fast Mode)
  run: |
    TEST_FAST=true pytest tests/test_large_file_load.py -v -m load_test --no-cov
  timeout-minutes: 30
```

### Full Load Tests (Nightly)

```yaml
- name: Run Full Load Tests
  run: |
    pytest tests/test_large_file_load.py -v -m load_test --no-cov -k "not very_large_file_200mb"
  timeout-minutes: 60
```

## Performance Benchmarks

### Expected Performance (100MB file)

| Metric | Target | Notes |
|--------|--------|-------|
| Processing time | < 5 minutes | Depends on system |
| Memory delta | < 2000MB | Peak memory increase |
| Memory ratio | < 20x | Memory delta / file size |
| Claims/second | > 100 | Processing throughput |

## Troubleshooting

### Tests Failing

1. **Check file sizes**: Verify generated files meet size requirements
2. **Check memory**: Ensure sufficient system memory available
3. **Check psutil**: Verify `psutil` is installed
4. **Check database**: Ensure test database is accessible

### Memory Issues

1. **Reduce batch size**: Modify `BATCH_SIZE` in `app/services/queue/tasks.py`
2. **Increase system memory**: Ensure adequate RAM available
3. **Use fast mode**: Set `TEST_FAST=true` for smaller files

### Timeout Issues

1. **Use fast mode**: `TEST_FAST=true` for faster tests
2. **Skip very large tests**: Use `-k "not very_large_file_200mb"`
3. **Increase timeout**: Adjust CI/CD timeout settings

## Related Files

- `scripts/load_test_large_files.py`: Manual load testing script
- `scripts/generate_large_edi_files.py`: Test file generator
- `app/api/routes/claims.py`: Claim upload endpoint
- `app/api/routes/remits.py`: Remittance upload endpoint
- `app/services/queue/tasks.py`: Celery processing task

## Summary

The load testing suite provides comprehensive validation of:
- ✅ File-based processing path
- ✅ Memory usage efficiency
- ✅ Error handling
- ✅ API integration
- ✅ Edge cases
- ✅ Memory leak detection

All tests are designed to be runnable in both fast mode (for CI/CD) and full mode (for comprehensive validation).

