# What's Next? - Prioritized Action Plan

**Last Updated:** 2025-12-26  
**Status:** Ready to Execute

## ✅ What We've Accomplished

1. **Verified 12 issues as FIXED** in the codebase
2. **Created status tracking** - Now you can see what's done vs outstanding
3. **Updated audit report** with accurate status markers
4. **Identified false positives** - Some issues are already fixed (e.g., episodes N+1 query)

## 🎯 Recommended Next Steps (In Priority Order)

### Option 1: Quick Wins (2-3 hours) ⚡
**Best if you want immediate progress**

1. **Verify Deployment Scripts** (30 min)
   - ✅ Actually already secure! Passwords saved to root-only files
   - ⚠️ Just need to verify Redis config and add error handling
   - **Impact:** Medium (security hardening)

2. **Fix CORS Documentation** (30 min)
   - Add clear dev vs prod documentation
   - Verify production validation works
   - **Impact:** Low-Medium (clarity)

3. **Fix Cache Invalidation** (1-2 hours)
   - Ensure cache cleared after episode updates
   - **Impact:** Medium (performance)

### Option 2: High Impact Performance (1-2 days) 🚀
**Best if you want to improve app performance**

1. **Fix Remaining N+1 Queries** (4-6 hours)
   - Pattern detection queries
   - Notification sending
   - Episode linker queries
   - **Impact:** HIGH (performance)

2. **Fix Cache Invalidation** (1-2 hours)
   - Episode status updates
   - **Impact:** Medium (consistency)

3. **Optimize String Operations** (2-3 hours)
   - Inefficient concatenation
   - Date parsing optimizations
   - **Impact:** Medium (performance)

### Option 3: Test Coverage (1-2 weeks) 🧪
**Best if you want to improve code quality**

1. **Analyze Coverage Gaps** (1 hour)
   - Identify modules with <80% coverage
   - Prioritize critical paths

2. **Add Critical Tests** (1 week)
   - Error handling paths
   - Security-critical code
   - Business logic

3. **Add Integration Tests** (1 week)
   - API endpoints
   - End-to-end flows

### Option 4: Documentation (Ongoing) 📝
**Best if you want to improve maintainability**

- Add docstrings incrementally as you touch code
- 69 documentation issues - tackle 5-10 per week
- **Impact:** Low-Medium (maintainability)

---

## 🎲 My Recommendation

**Start with Option 1 (Quick Wins)** to build momentum, then move to **Option 2 (Performance)** for high impact.

### This Week's Focus:
1. ✅ Verify deployment scripts (30 min) - mostly done, just verify
2. ✅ Fix CORS documentation (30 min)
3. ✅ Fix cache invalidation (1-2 hours)
4. ✅ Fix one N+1 query issue (1-2 hours)

**Total Time:** ~4-5 hours  
**Impact:** Medium-High

---

## 📋 Detailed Task List

### Immediate (Today/Tomorrow)
- [ ] Verify Redis configuration security in deployment scripts
- [ ] Add error handling to systemd service management
- [ ] Document CORS dev vs prod behavior
- [ ] Fix cache invalidation after episode status updates

### This Week
- [ ] Fix N+1 query in pattern detection (`app/services/learning/pattern_detector.py`)
- [ ] Fix N+1 query in notification sending (`app/services/queue/tasks.py`)
- [ ] Fix N+1 query in episode linker (`app/services/episodes/linker.py`)
- [ ] Optimize string operations in EDI parser

### Next Week
- [ ] Analyze test coverage gaps
- [ ] Add tests for error handling paths
- [ ] Add negative test cases
- [ ] Start documentation improvements

---

## 🔍 Issues Already Fixed (Don't Need to Do)

- ✅ Episodes N+1 query - Already uses `subqueryload`
- ✅ Rate limiting optimization - Uses binary search
- ✅ Database indexes - All foreign keys indexed
- ✅ WebSocket error recovery - Comprehensive error handling
- ✅ PHI exposure - Uses hashing in AuditMiddleware
- ✅ Sentry before_send - Properly implemented
- ✅ Security key validation - Prevents defaults at startup

---

## 💡 Tips

1. **Focus on impact** - Security and performance first
2. **Incremental progress** - Don't try to fix everything at once
3. **Verify before fixing** - Some issues may already be addressed
4. **Document as you go** - Add docstrings when touching code

---

**Which option would you like to start with?** I can help implement any of these!

