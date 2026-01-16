"""
FastAPI application entry point.

This module serves as the application entry point. It handles early initialization
and creates the FastAPI application instance using the application factory pattern.

The application setup is organized into separate modules:
- `app/core/setup.py`: Early initialization (env, Sentry, logging, security)
- `app/core/application.py`: Application factory and configuration
- `app/api/routes/`: Route handlers organized by domain

**Documentation References:**
- Application Factory: See `app/core/application.py` for app creation logic
- Application Setup: See `app/core/setup.py` for initialization logic
- API Endpoints: See `API_DOCUMENTATION.md` for complete API reference
- Route Handlers: See `app/api/routes/` for endpoint implementations
- Middleware: See `app/api/middleware/` for middleware implementations
- Configuration: See `app/config/` for configuration modules
- Development: See `README.md` and `.cursorrules` for development guidelines

**Quick Reference:**
- Adding new routes: See `.cursorrules` → "API Design" section
- Error handling: See `.cursorrules` → "Error Handling" section
- Security: See `SECURITY.md` and `app/config/security.py`
"""
from app.core.setup import setup_application
from app.core.application import create_application

# Initialize application environment and configuration
# This must be done before creating the FastAPI app instance
setup_application()

# Create and configure FastAPI application
app = create_application()

