# Contributing to mARB 2.0

Thank you for contributing to mARB 2.0! This guide will help you get started.

## 📚 Documentation First

**CRITICAL**: When making code changes, documentation MUST be updated as part of the same change.

### Documentation Update Checklist

- [ ] **Inline Documentation**: Updated docstrings, comments, and type hints
- [ ] **API Documentation**: Updated `API_DOCUMENTATION.md` if adding/modifying endpoints
- [ ] **Module Documentation**: Updated module-level docstrings if behavior changed
- [ ] **Project Documentation**: Updated `README.md` or relevant guides if features changed
- [ ] **Quick Reference**: Updated `DOCUMENTATION_QUICK_REFERENCE.md` if adding new patterns

See `.cursorrules` → "Documentation Update Requirement" for details.

## 🚀 Getting Started

### 1. Setup Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd mARB-2.0

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Set up database
alembic upgrade head
```

See `SETUP.md` for detailed setup instructions.

### 2. Understand the Codebase

- **Start Here**: Read `README.md` for project overview
- **Coding Standards**: Read `.cursorrules` for all coding patterns and standards
- **API Reference**: See `API_DOCUMENTATION.md` for API endpoints
- **Quick Reference**: See `DOCUMENTATION_QUICK_REFERENCE.md` for task-based doc links
- **Project Structure**: See `README.md` → "Project Structure" section

### 3. Find Relevant Documentation

Use `DOCUMENTATION_QUICK_REFERENCE.md` to quickly find documentation by:
- **Task** (e.g., "I'm adding a new API endpoint")
- **Module/Component** (e.g., `app/api/routes/`)
- **Topic** (e.g., "Authentication & Security")

## 📝 Development Workflow

### Before You Start

1. **Read the relevant documentation**:
   - Check `DOCUMENTATION_QUICK_REFERENCE.md` for your task
   - Review `.cursorrules` for coding patterns
   - Look at similar existing code for examples

2. **Understand the context**:
   - Read module docstrings (they're comprehensive!)
   - Check related files and their documentation
   - Review API documentation if working on endpoints

### While Coding

1. **Follow coding standards** (see `.cursorrules`):
   - Use type hints for all functions
   - Write Google-style docstrings
   - Follow error handling patterns
   - Use structured logging

2. **Update documentation as you code**:
   - Add/update docstrings immediately
   - Update `API_DOCUMENTATION.md` for endpoint changes
   - Update module docstrings for behavior changes

3. **Reference documentation in code**:
   - Add doc links in module docstrings (see `app/main.py` for example)
   - Reference related documentation in comments when helpful

### Before Committing

1. **Run code quality checks**:
   ```bash
   black .                    # Format code
   ruff check .               # Lint code
   pytest                     # Run tests
   ```

2. **Verify documentation**:
   - All new code has docstrings
   - API documentation is updated
   - Module docstrings reflect changes
   - Quick reference is updated if needed

3. **Test your changes**:
   ```bash
   pytest tests/              # Run all tests
   pytest tests/test_your_feature.py  # Run specific tests
   ```

## 🎯 Common Tasks

### Adding a New API Endpoint

1. **Read**: `.cursorrules` → "API Design" section
2. **See Examples**: `app/api/routes/` (existing route handlers)
3. **Document**: Add to `API_DOCUMENTATION.md`
4. **Test**: Add tests in `tests/test_*_api.py`
5. **Reference**: See `DOCUMENTATION_QUICK_REFERENCE.md` → "I'm adding a new API endpoint"

### Creating a New Service

1. **Read**: `.cursorrules` → "Service Layer" section
2. **See Examples**: `app/services/` (existing services)
3. **Document**: Add comprehensive module docstring
4. **Test**: Add tests in `tests/test_services/`
5. **Reference**: See `DOCUMENTATION_QUICK_REFERENCE.md` → "I'm creating a new service"

### Working with Database Models

1. **Read**: `.cursorrules` → "Model Changes" section
2. **See Examples**: `app/models/database.py` (all models documented)
3. **Create Migration**: `alembic revision --autogenerate -m "description"`
4. **Document**: Add comprehensive class docstring
5. **Reference**: See `DOCUMENTATION_QUICK_REFERENCE.md` → "I'm working with database models"

### Processing EDI Files

1. **Read**: `.cursorrules` → "EDI Processing" section
2. **See Examples**: `app/services/edi/parser.py` and extractors
3. **Format Guide**: See `EDI_FORMAT_GUIDE.md`
4. **Document**: Update parser/extractor docstrings
5. **Reference**: See `DOCUMENTATION_QUICK_REFERENCE.md` → "I'm processing EDI files"

## 📖 Documentation Standards

### Module Docstrings

Include:
- Brief summary (first line)
- Detailed description
- **Documentation References** section (links to relevant docs)
- Key features/capabilities
- Usage examples if helpful

Example (see `app/main.py`):
```python
"""
Module description.

Detailed description of what this module does.

**Documentation References:**
- Related Guide: `docs/guides/RELATED_GUIDE.md`
- API Docs: `API_DOCUMENTATION.md` → "Section Name"
- Config: `app/config/related_config.py`
"""
```

### Function/Class Docstrings

Use Google-style docstrings:
```python
def function_name(param1: int, param2: str) -> dict:
    """
    Brief description.
    
    Detailed description if needed.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        NotFoundError: When resource not found
        AppError: When operation fails
        
    Example:
        >>> result = function_name(1, "test")
        >>> print(result)
        {'status': 'success'}
    """
```

### API Endpoint Documentation

When adding/modifying endpoints:
1. Update `API_DOCUMENTATION.md` with:
   - Endpoint path and method
   - Request/response examples
   - Query/path parameters
   - Error cases
   - Notes and usage tips

2. Add comprehensive docstring to route handler:
   - Description
   - Parameters
   - Response format
   - Error cases
   - Example usage

## 🧪 Testing

### Test Structure

- **Location**: All tests in `tests/` directory
- **Naming**: `test_*.py` for test files, `test_*` for test functions
- **Fixtures**: Use `tests/conftest.py` for shared fixtures
- **Coverage**: Maintain minimum 80% code coverage

### Writing Tests

1. **Read**: `.cursorrules` → "Testing" section
2. **See Examples**: `tests/` (existing test files)
3. **Use Fixtures**: See `tests/conftest.py` for available fixtures
4. **Test Patterns**: See `tests/README.md` for test patterns

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_claims_api.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test
pytest tests/test_claims_api.py::test_get_claim
```

## 🔍 Finding Help

### Documentation Resources

1. **Quick Reference**: `DOCUMENTATION_QUICK_REFERENCE.md` - Task-based doc links
2. **Documentation Index**: `docs/README.md` - Complete documentation index
3. **Coding Standards**: `.cursorrules` - All coding patterns and standards
4. **API Reference**: `API_DOCUMENTATION.md` - Complete API documentation
5. **Troubleshooting**: `TROUBLESHOOTING.md` - Common issues and solutions

### Code Examples

- **Route Handlers**: `app/api/routes/` - See existing endpoints
- **Services**: `app/services/` - See service implementations
- **Models**: `app/models/database.py` - See model definitions
- **Middleware**: `app/api/middleware/` - See middleware implementations
- **Tests**: `tests/` - See test examples

### Module Docstrings

Most modules have comprehensive docstrings. View them:
```python
import app.services.risk.scorer
print(app.services.risk.scorer.__doc__)
```

Or in your IDE, hover over imports to see docstrings.

## ✅ Checklist Before Submitting

- [ ] Code follows `.cursorrules` standards
- [ ] All functions have type hints and docstrings
- [ ] Module docstrings are updated
- [ ] API documentation updated (if applicable)
- [ ] Tests written and passing
- [ ] Code formatted with `black`
- [ ] Code linted with `ruff` (no errors)
- [ ] Documentation references added to module docstrings
- [ ] Quick reference updated (if adding new patterns)

## 📞 Getting Help

- **Documentation**: Start with `DOCUMENTATION_QUICK_REFERENCE.md`
- **Coding Standards**: See `.cursorrules`
- **Examples**: Check existing code in the codebase
- **Issues**: Check `TROUBLESHOOTING.md` for common issues

---

**Remember**: Good documentation makes the codebase maintainable. Update it as you code!

