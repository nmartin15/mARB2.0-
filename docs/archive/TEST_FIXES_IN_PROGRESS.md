# Test Fixes In Progress

## Status

We're working on fixing the 11 failing tests. The main issues are:

1. **Cache persistence between tests** - Cached responses from previous tests are affecting later tests
2. **Null field handling** - Tests expecting None values but getting cached values with dates
3. **Relationship loading** - Claim lines not being loaded properly in some cases

## Fixes Applied

### ✅ Fixed Tests
- `test_get_claim_with_null_fields` - Fixed by clearing cache and creating claim directly

### 🔄 In Progress
- `test_get_claim_with_claim_lines` - Added cache clearing, needs verification
- `test_get_remit_with_null_fields` - Added cache clearing, needs verification
- `test_get_claim_success` - Cache collision issue, needs unique IDs or cache clearing

### 📋 Remaining Tests to Fix
- `test_get_risk_score_not_calculated`
- `test_get_risk_score_multiple_scores_returns_latest`
- Integration tests in `test_remittance_upload_flow_integration.py`
- Integration tests in `test_upload_flow_integration.py`

## Solution Approach

1. **Clear cache in tests** - Add cache clearing for endpoints that use caching
2. **Use unique IDs** - Ensure each test uses unique claim/remittance IDs
3. **Fix relationship loading** - Ensure claim_lines are properly loaded

## Next Steps

1. Add cache clearing fixture to conftest.py for all tests
2. Fix remaining API tests
3. Fix integration tests
4. Run full test suite to verify all fixes

