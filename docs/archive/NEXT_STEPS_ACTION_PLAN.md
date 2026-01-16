# Next Steps Action Plan

**Created:** 2025-12-26  
**Status:** Ready to Execute

## 🎯 Priority Order

### Phase 1: Critical Security & High Priority (This Week)

#### 1. ✅ COMPLETE: Fix Deployment Script Security Issues
**Priority:** 🔴 CRITICAL  
**Estimated Time:** 2-3 hours

**Issues to Fix:**
- [ ] Review `deployment/setup_droplet.sh` - passwords saved securely but verify no plaintext display
- [ ] Review `deployment/deploy_app.sh` - check `/tmp/marb_keys.txt` permissions
- [ ] Review `deployment/systemd-services.sh` - hardcoded paths
- [ ] Secure Redis configuration against external access
- [ ] Add error handling for systemd service management

**Files:**
- `deployment/setup_droplet.sh`
- `deployment/deploy_app.sh`
- `deployment/systemd-services.sh`

#### 2. ⚠️ IN PROGRESS: Improve Test Coverage
**Priority:** 🟠 HIGH  
**Estimated Time:** 1-2 weeks (incremental)

**Current Status:** 29.4% coverage (target: 80%+)

**Action Items:**
- [ ] Identify modules with lowest coverage
- [ ] Prioritize critical paths (security, error handling, business logic)
- [ ] Add unit tests for error paths
- [ ] Add integration tests for API endpoints
- [ ] Focus on performance-sensitive code

**Quick Wins:**
- Add tests for error handling paths
- Add negative test cases
- Add edge case tests

#### 3. ⚠️ TODO: Fix CORS Configuration
**Priority:** 🟡 MEDIUM-HIGH  
**Estimated Time:** 30 minutes

**Issue:** CORS origins allow localhost in development (may be acceptable, but needs documentation)

**Action:**
- [ ] Verify production validation prevents localhost
- [ ] Document development vs production behavior
- [ ] Add warning if CORS allows all in production

---

### Phase 2: Performance & Error Handling (Next Week)

#### 4. ⚠️ TODO: Fix N+1 Query Issues
**Priority:** 🟡 MEDIUM  
**Estimated Time:** 1-2 days

**Issues:**
- [ ] `/episodes` endpoint when claim_id not provided
- [ ] Pattern detection queries
- [ ] Notification sending in `process_edi_file`
- [ ] Episode linker queries

**Files:**
- `app/api/routes/episodes.py`
- `app/services/learning/pattern_detector.py`
- `app/services/queue/tasks.py`
- `app/services/episodes/linker.py`

**Solution:** Add eager loading with `joinedload()` or `selectinload()`

#### 5. ⚠️ TODO: Fix Cache Invalidation Issues
**Priority:** 🟡 MEDIUM  
**Estimated Time:** 2-3 hours

**Issues:**
- [ ] Cache invalidation after episode status/completion updates
- [ ] Verify cache keys are properly invalidated

**Files:**
- `app/api/routes/episodes.py`
- `app/utils/cache.py`

#### 6. ⚠️ TODO: Improve Error Handling
**Priority:** 🟡 MEDIUM  
**Estimated Time:** 1-2 days

**Issues:**
- [ ] Database operations in episode linker
- [ ] File operations cleanup
- [ ] Subprocess error messages (add context)

**Files:**
- `app/services/episodes/linker.py`
- `app/api/routes/claims.py`
- `app/api/routes/remits.py`
- Various scripts

---

### Phase 3: Documentation & Testing (Ongoing)

#### 7. ⚠️ TODO: Add Missing Documentation
**Priority:** 🟢 LOW-MEDIUM  
**Estimated Time:** Ongoing (incremental)

**Issues:** 69 documentation issues
- [ ] API endpoint docstrings
- [ ] Function docstrings
- [ ] Module docstrings
- [ ] Parameter documentation

**Approach:** Add incrementally as code is touched

#### 8. ⚠️ TODO: Add Missing Test Cases
**Priority:** 🟡 MEDIUM  
**Estimated Time:** Ongoing (incremental)

**Issues:** 76 testing issues
- [ ] Negative test cases
- [ ] Edge case tests
- [ ] Error path tests
- [ ] Invalid input tests

**Approach:** Add incrementally, prioritize critical paths

---

## 🚀 Quick Wins (Can Do Today)

1. **Fix CORS Documentation** (30 min)
   - Add clear documentation about dev vs prod behavior
   - Verify production validation

2. **Fix Deployment Script Security** (2-3 hours)
   - Review and secure password handling
   - Fix file permissions
   - Add error handling

3. **Add Eager Loading to Episodes Endpoint** (1 hour)
   - Fix N+1 query issue
   - Immediate performance improvement

4. **Fix Cache Invalidation** (1-2 hours)
   - Ensure cache is cleared after updates
   - Quick fix with high impact

---

## 📊 Progress Tracking

### Completed ✅
- [x] Verified 12 issues as FIXED
- [x] Created status tracking documents
- [x] Updated audit report with status markers

### In Progress 🔄
- [ ] Deployment script security fixes
- [ ] Test coverage improvement plan

### Next Up 📋
- [ ] CORS configuration review
- [ ] N+1 query fixes
- [ ] Error handling improvements

---

## 📝 Notes

- Focus on security and performance issues first (highest impact)
- Documentation can be added incrementally
- Testing should be prioritized for critical paths
- Some issues may be false positives - verify before fixing

---

**Last Updated:** 2025-12-26

