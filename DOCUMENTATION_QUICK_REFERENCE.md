# Documentation Quick Reference

**Quick links to find the right documentation when coding.**

## 🎯 By Task

### I'm adding a new API endpoint
- **API Design Patterns**: `.cursorrules` → "API Design" section
- **Endpoint Documentation**: `API_DOCUMENTATION.md` (add your endpoint here!)
- **Route Handler Examples**: `app/api/routes/` (see existing routes)
- **Error Handling**: `.cursorrules` → "Error Handling" section
- **Testing**: `tests/README.md` → "API Testing" section

### I'm working with database models
- **Model Patterns**: `.cursorrules` → "Model Changes" section
- **Model Examples**: `app/models/database.py` (see existing models)
- **Migrations**: `.cursorrules` → "Alembic Migrations" section
- **Database Config**: `app/config/database.py` (module docstring)
- **Query Patterns**: `.cursorrules` → "Database Operations" section

### I'm creating a new service
- **Service Layer Patterns**: `.cursorrules` → "Service Layer" section
- **Service Examples**: `app/services/` (see existing services)
- **Error Handling**: `app/utils/errors.py` (module docstring)
- **Logging**: `.cursorrules` → "Logging" section
- **Testing**: `tests/README.md` → "Service Testing" section

### I'm processing EDI files
- **EDI Processing**: `.cursorrules` → "EDI Processing" section
- **Parser Examples**: `app/services/edi/parser.py`
- **Format Guide**: `EDI_FORMAT_GUIDE.md`
- **Format Detection**: `app/services/edi/FORMAT_DETECTION.md`
- **Extractors**: `app/services/edi/extractors/` (see extractor classes)

### I'm working with Celery tasks
- **Celery Patterns**: `.cursorrules` → "Celery Tasks" section
- **Task Examples**: `app/services/queue/tasks.py` (module docstring)
- **Task Configuration**: `app/config/celery.py`
- **Monitoring**: `deployment/MONITORING_DASHBOARD_SETUP.md`

### I'm implementing risk scoring
- **Risk Scoring**: `app/services/risk/scorer.py` (module docstring)
- **Risk Rules**: `app/services/risk/rules/` (see rule engines)
- **ML Integration**: `ml/README.md`
- **Risk Weights**: `app/config/risk_weights.py`

### I'm adding authentication/security
- **Security Config**: `app/config/security.py` (module docstring)
- **Security Guide**: `SECURITY.md`
- **HIPAA Compliance**: `SECURITY.md` → "HIPAA Compliance" section
- **Audit Logging**: `app/api/middleware/audit.py` (module docstring)
- **Production Security**: `deployment/PRODUCTION_SECURITY_CHECKLIST.md`

### I'm working with caching
- **Cache Utilities**: `app/utils/cache.py` (module docstring)
- **Cache TTL Config**: `app/config/cache_ttl.py`
- **Redis Config**: `app/config/redis.py`
- **Cache Patterns**: `.cursorrules` → "Caching" section

### I'm deploying to production
- **Deployment Guide**: `deployment/DEPLOYMENT.md`
- **Deployment Runbook**: `deployment/DEPLOYMENT_RUNBOOK.md`
- **Security Checklist**: `deployment/PRODUCTION_SECURITY_CHECKLIST.md`
- **HTTPS Setup**: `deployment/SETUP_HTTPS.md`
- **Backup/Restore**: `deployment/BACKUP_RESTORE.md`

### I'm debugging an issue
- **Troubleshooting**: `TROUBLESHOOTING.md`
- **Error Handling**: `.cursorrules` → "Error Handling" section
- **Logging**: `.cursorrules` → "Logging" section
- **Sentry Setup**: `docs/guides/SENTRY_SETUP.md`
- **Memory Monitoring**: `MEMORY_MONITORING.md`

### I'm writing tests
- **Test Structure**: `.cursorrules` → "Testing" section
- **Test Examples**: `tests/` (see existing test files)
- **Test README**: `tests/README.md`
- **Fixtures**: `tests/conftest.py`
- **Coverage**: `tests/COVERAGE_COMMANDS.md`

## 📁 By Module/Component

### `app/api/routes/`
- **API Documentation**: `API_DOCUMENTATION.md`
- **API Design**: `.cursorrules` → "API Design" section
- **Error Handling**: `.cursorrules` → "Error Handling" section

### `app/api/middleware/`
- **Middleware Patterns**: See existing middleware files
- **Auth Middleware**: `app/api/middleware/auth_middleware.py`
- **Rate Limiting**: `app/api/middleware/rate_limit.py`
- **Audit Logging**: `app/api/middleware/audit.py`

### `app/models/`
- **Model Patterns**: `.cursorrules` → "Model Changes" section
- **Model Examples**: `app/models/database.py` (all models documented)
- **Migrations**: `.cursorrules` → "Alembic Migrations" section

### `app/services/edi/`
- **EDI Processing**: `.cursorrules` → "EDI Processing" section
- **Format Guide**: `EDI_FORMAT_GUIDE.md`
- **Format Detection**: `app/services/edi/FORMAT_DETECTION.md`
- **Parser**: `app/services/edi/parser.py` (module docstring)
- **Extractors**: `app/services/edi/extractors/` (see individual extractors)

### `app/services/risk/`
- **Risk Scoring**: `app/services/risk/scorer.py` (module docstring)
- **Risk Rules**: `app/services/risk/rules/` (see rule engines)
- **ML Service**: `app/services/risk/ml_service.py`
- **ML Models**: `ml/README.md`

### `app/services/queue/`
- **Celery Tasks**: `.cursorrules` → "Celery Tasks" section
- **Task Examples**: `app/services/queue/tasks.py` (module docstring)
- **Celery Config**: `app/config/celery.py`

### `app/config/`
- **Database**: `app/config/database.py` (module docstring)
- **Security**: `app/config/security.py` (module docstring)
- **Redis**: `app/config/redis.py`
- **Celery**: `app/config/celery.py`
- **Cache TTL**: `app/config/cache_ttl.py`
- **Risk Weights**: `app/config/risk_weights.py`

### `app/utils/`
- **Errors**: `app/utils/errors.py` (module docstring)
- **Logger**: `app/utils/logger.py` (module docstring)
- **Cache**: `app/utils/cache.py` (module docstring)
- **Logging Patterns**: `.cursorrules` → "Logging" section

## 🔍 By Topic

### Authentication & Security
- `SECURITY.md` - Security and HIPAA compliance
- `app/config/security.py` - Security configuration
- `deployment/PRODUCTION_SECURITY_CHECKLIST.md` - Production security
- `.cursorrules` → "Security" section

### Database & Models
- `app/models/database.py` - All models (well documented)
- `app/config/database.py` - Database configuration
- `.cursorrules` → "Database Operations" and "Model Changes" sections
- `deployment/BACKUP_RESTORE.md` - Database backup/restore

### API Development
- `API_DOCUMENTATION.md` - Complete API reference
- `.cursorrules` → "API Design" section
- `app/api/routes/` - Route handler examples

### EDI Processing
- `EDI_FORMAT_GUIDE.md` - EDI format specifications
- `app/services/edi/FORMAT_DETECTION.md` - Format detection
- `.cursorrules` → "EDI Processing" section
- `app/services/edi/` - Parser and extractors

### Testing
- `tests/README.md` - Test suite overview
- `.cursorrules` → "Testing" section
- `tests/conftest.py` - Test fixtures
- `tests/COVERAGE_COMMANDS.md` - Coverage commands

### Deployment
- `deployment/DEPLOYMENT.md` - Deployment guide
- `deployment/DEPLOYMENT_RUNBOOK.md` - Operational procedures
- `deployment/PRODUCTION_SECURITY_CHECKLIST.md` - Security checklist
- `deployment/SETUP_HTTPS.md` - HTTPS setup

### Monitoring & Operations
- `docs/guides/SENTRY_SETUP.md` - Error tracking
- `MEMORY_MONITORING.md` - Memory monitoring
- `deployment/MONITORING_DASHBOARD_SETUP.md` - Monitoring setup

### Machine Learning
- `ml/README.md` - ML development guide
- `ml/HISTORICAL_DATA_SOURCES.md` - Data sources
- `app/services/risk/ml_service.py` - ML service integration

## 📝 Documentation Standards

### When to Update Documentation
- **Adding code**: Update relevant docstrings and `API_DOCUMENTATION.md` if adding endpoints
- **Changing behavior**: Update docstrings, module docs, and relevant guides
- **New features**: Add to appropriate documentation files
- **See**: `.cursorrules` → "Documentation Update Requirement" section

### Documentation Locations
- **Code documentation**: Inline docstrings (Google style)
- **API documentation**: `API_DOCUMENTATION.md`
- **Project documentation**: `README.md`, `docs/README.md`
- **Deployment docs**: `deployment/` directory
- **Guides**: `docs/guides/` directory

## 🚀 Quick Commands

### View Documentation
```bash
# Main README
cat README.md

# API Documentation
cat API_DOCUMENTATION.md

# Cursor Rules (coding standards)
cat .cursorrules

# Documentation Index
cat docs/README.md

# Quick Reference (this file)
cat DOCUMENTATION_QUICK_REFERENCE.md
```

### Find Documentation
```bash
# Search for documentation files
find . -name "*.md" -type f | grep -v venv | grep -v archive

# Search for specific topic in docs
grep -r "risk scoring" docs/ *.md

# View module docstrings
python -c "import app.services.risk.scorer; print(app.services.risk.scorer.__doc__)"
```

## 💡 Pro Tips

1. **Start with `.cursorrules`** - Contains all coding patterns and standards
2. **Check module docstrings** - Most modules have comprehensive docstrings
3. **Use this file** - Bookmark this quick reference for easy access
4. **Update as you go** - When you find a better doc location, update this file
5. **IDE Integration** - Most IDEs show docstrings on hover (use them!)

## 🔗 External Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org/
- **Celery Docs**: https://docs.celeryproject.org/
- **Pytest Docs**: https://docs.pytest.org/

---

**Last Updated**: 2024-12-26  
**Maintained By**: Development Team  
**See Also**: `docs/README.md` for complete documentation index

