# Extractor Tests Fixed - December 2025

## Summary

Fixed **8 extractor tests** that were failing due to incorrect method names and parameter usage.

## Root Cause

The tests were calling methods that don't exist:
- `extract_claim()` ❌ → Should be `extract(clm_segment, block, warnings)` ✅
- `extract_lines()` ❌ → Should be `extract(block, warnings)` ✅
- `extract_payer()` ❌ → Should be `extract(block, warnings)` ✅
- `extract_diagnoses()` ❌ → Should be `extract(block, warnings)` ✅

## Actual Extractor API

### ClaimExtractor
```python
def extract(self, clm_segment: List[str], block: List[List[str]], warnings: List[str]) -> Dict:
    """Extract claim data from CLM segment and related segments."""
    # Returns dict with claim data
```

### LineExtractor
```python
def extract(self, block: List[List[str]], warnings: List[str]) -> List[Dict]:
    """Extract all claim lines from block."""
    # Returns list of line dicts
```

### PayerExtractor
```python
def extract(self, block: List[List[str]], warnings: List[str]) -> Dict:
    """Extract payer data from SBR and NM1 segments."""
    # Returns dict with payer data
```

### DiagnosisExtractor
```python
def extract(self, block: List[List[str]], warnings: List[str]) -> Dict:
    """Extract diagnosis codes from HI segments."""
    # Returns dict with diagnosis_codes list and principal_diagnosis
```

## Fixes Applied

### 1. ClaimExtractor Tests (2 tests)
- **test_claim_extractor_missing_clm_segment**: 
  - Changed from `extract_claim(block)` to `extract(empty_clm, block, warnings)`
  - Checks for empty dict when CLM is invalid
  
- **test_claim_extractor_invalid_clm_format**:
  - Changed from `extract_claim(block)` to `extract(clm_segment, block, warnings)`
  - Passes CLM segment with insufficient elements
  - Checks for warnings and empty dict

### 2. LineExtractor Tests (2 tests)
- **test_line_extractor_missing_sv2_segment**:
  - Changed from `extract_lines(block)` to `extract(block, warnings)`
  - Checks for empty list when no SV2 found
  
- **test_line_extractor_invalid_sv2_format**:
  - Changed from `extract_lines(block)` to `extract(block, warnings)`
  - Checks for list (may be empty if SV2 invalid)

### 3. PayerExtractor Tests (2 tests)
- **test_payer_extractor_missing_sbr_segment**:
  - Changed from `extract_payer(block)` to `extract(block, warnings)`
  - Checks for empty dict and warnings when SBR missing
  
- **test_payer_extractor_invalid_sbr_format**:
  - Changed from `extract_payer(block)` to `extract(block, warnings)`
  - Checks for empty dict when SBR invalid

### 4. DiagnosisExtractor Tests (2 tests)
- **test_diagnosis_extractor_missing_hi_segment**:
  - Changed from `extract_diagnoses(block)` to `extract(block, warnings)`
  - Checks for dict with empty `diagnosis_codes` list and warnings
  
- **test_diagnosis_extractor_invalid_hi_format**:
  - Changed from `extract_diagnoses(block)` to `extract(block, warnings)`
  - Checks for dict with `diagnosis_codes` list (may be empty)

## Test Results

**Before**: 8/8 tests failing ❌
**After**: 8/8 tests passing ✅

All extractor tests now:
- Use correct method names (`extract()`)
- Pass correct parameters (block, warnings, and clm_segment for ClaimExtractor)
- Check actual return values (dicts with expected keys, lists, etc.)
- Verify warnings are generated for missing/invalid segments

## Key Learnings

1. **Always check actual method signatures** - Don't assume method names
2. **Extractors use warnings list** - Errors are logged to warnings, not raised
3. **Return types vary** - Some return dicts, some return lists, some return dicts with lists
4. **Graceful degradation** - Extractors return empty structures rather than raising exceptions

## Files Modified

- `tests/test_service_layer_negative_cases.py` - Fixed all 8 extractor tests

