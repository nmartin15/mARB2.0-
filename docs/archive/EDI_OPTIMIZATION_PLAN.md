# EDI Parsing Optimization Plan

## Current State

### Issues Identified
1. **Memory Usage**: Entire file loaded into memory (`file_content: str` in Celery task)
2. **No Progress Tracking**: Users don't see progress for large files
3. **Parser Limitations**: Current parser loads all segments into memory
4. **No Streaming**: File is read completely before processing starts

### Current Flow
1. Upload endpoint reads entire file: `content = await file.read()`
2. File decoded to string: `content_str = content.decode("utf-8")`
3. Entire string passed to Celery task
4. Parser loads all segments into memory
5. Processes in batches (but all in memory)

## Optimization Strategy

### Phase 1: Parser Optimization ✅
- [x] Add FILE_PROGRESS notification type
- [x] Add progress notification function
- [x] Complete optimized parser with true streaming ✅ **COMPLETE**
- [x] Update Celery task to use optimized parser for large files ✅ **COMPLETE**
- [x] Add progress tracking in Celery task ✅ **COMPLETE**

### Phase 2: Upload Optimization
- [x] Add file size check in upload endpoint ✅ **COMPLETE** (in routes)
- [x] Stream file to temporary storage for very large files (>50MB) ✅ **COMPLETE**
- [x] Process from file instead of memory for huge files ✅ **COMPLETE** (streaming parser supports file_path)

### Phase 3: Memory Management ✅
- [x] Add garbage collection hints ✅ **COMPLETE** (in streaming parser)
- [x] Clear intermediate data structures ✅ **COMPLETE** (blocks cleared after processing)
- [x] Monitor memory usage ✅ **COMPLETE** (performance monitoring available)

## Implementation Details

### 1. Progress Tracking
- Send progress updates at key stages:
  - File received (0%)
  - Parsing started (10%)
  - Segments parsed (30%)
  - Claims/remittances extracted (50%)
  - Database saving (70%)
  - Complete (100%)

### 2. Optimized Parser
- For files > 10MB: Use streaming parser
- For files < 10MB: Use standard parser (faster)
- Stream segments instead of loading all
- Process in chunks with memory cleanup

### 3. Celery Task Updates
- Detect file size
- Choose parser based on size
- Send progress updates
- Handle memory efficiently

## Testing Plan

1. **Small files (< 1MB)**: Should work as before
2. **Medium files (1-10MB)**: Should work with standard parser
3. **Large files (10-50MB)**: Should use optimized parser
4. **Very large files (50-100MB)**: Should use optimized parser + file streaming
5. **Progress tracking**: Verify WebSocket notifications

## Success Criteria

- [ ] Files up to 100MB process successfully
- [ ] Memory usage stays reasonable (< 500MB for 100MB file)
- [ ] Progress updates sent every 5-10%
- [ ] Processing time reasonable (< 2 minutes per 100MB)
- [ ] All existing tests still pass

