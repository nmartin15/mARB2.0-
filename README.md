# mARB 2.0 - Real-Time Claim Risk Engine

A real-time claim risk engine that analyzes 837/835 EDI data, payer rules, and historical denial patterns to provide instant, actionable guidance before claims are submitted.

## Features

- **Resilient EDI Processing**: Handles variations and missing segments gracefully
  - Supports both 837 (claims) and 835 (remittances) EDI formats
  - Streaming parser for large files (100MB+)
  - Automatic format detection and validation
- **Real-time Risk Scoring**: Analyze claims before submission
  - Multi-component risk assessment (payer rules, coding, documentation, ML)
  - Configurable risk weights and thresholds
  - Cached results for performance
- **Episode Linking**: Connect claims with their remittance outcomes
  - Automatic linking by control numbers
  - Patient and date-based matching
  - Manual linking support
- **Pattern Learning**: Detect and learn from denial patterns
  - Historical pattern analysis
  - Payer-specific pattern detection
  - Confidence scoring and frequency tracking
- **Payer-Specific Rules**: Model plan design and benefit rules
  - Configurable payer rules engine
  - Plan-specific benefit rules
  - Practice-specific configurations
- **ML-Powered Predictions**: Integrated Python ML models for risk prediction
  - scikit-learn and PyTorch support
  - Feature extraction and model training
  - Automated model versioning
- **Enhanced Memory Monitoring**: Automatic memory tracking with threshold warnings
  - Real-time memory usage tracking
  - Configurable thresholds and alerts
  - Performance optimization insights
- **HIPAA Compliant**: Security, encryption, and audit logging
  - PHI hashing and protection
  - Comprehensive audit trail
  - JWT authentication (optional)
  - Rate limiting and CORS protection
- **WebSocket Notifications**: Real-time browser notifications
  - Real-time processing updates
  - Risk score notifications
  - Episode linking events

## Tech Stack

- **Backend**: Python + FastAPI
- **Database**: PostgreSQL + SQLAlchemy
- **Queue**: Celery + Redis
- **ML**: scikit-learn/PyTorch (integrated)
- **Security**: JWT, encryption, HIPAA audit logs

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+

### Installation

1. Clone the repository
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Set up the database:
   ```bash
   alembic upgrade head
   ```

6. Start Redis (if not running):
   ```bash
   redis-server
   ```

7. Start Celery worker (in separate terminal):
   ```bash
   celery -A app.services.queue.tasks worker --loglevel=info
   ```

8. Start the development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Project Structure

```
mARB-2.0/
├── app/                      # Main application code
│   ├── api/                  # API routes and middleware
│   │   ├── routes/           # Endpoint handlers (claims, remits, episodes, risk, etc.)
│   │   └── middleware/        # Request/response middleware (auth, rate limit, audit)
│   ├── config/               # Configuration modules (database, security, celery, redis)
│   ├── models/               # SQLAlchemy database models
│   ├── services/             # Business logic services
│   │   ├── edi/              # EDI parsing and processing
│   │   ├── episodes/         # Episode linking logic
│   │   ├── learning/         # Pattern detection
│   │   ├── queue/            # Celery task definitions
│   │   └── risk/             # Risk scoring and rules
│   └── utils/                # Shared utilities (errors, logger, cache)
├── ml/                       # Machine learning models and training
│   ├── models/               # ML model definitions
│   ├── services/             # Feature extraction
│   └── training/             # Model training scripts
├── alembic/                  # Database migrations
│   └── versions/             # Migration files
├── tests/                    # Test suite
│   ├── test_*.py             # Test files
│   └── conftest.py           # Pytest fixtures
├── deployment/               # Deployment scripts and documentation
├── docs/                     # Additional documentation
└── scripts/                  # Utility scripts
```

## Development

- `uvicorn app.main:app --reload` - Start development server
- `pytest` - Run tests
- `black .` - Format code
- `ruff check .` - Lint code
- `alembic revision --autogenerate -m "message"` - Create migration
- `alembic upgrade head` - Apply migrations
- `celery -A app.services.queue.tasks flower` - Celery monitoring

## Load Testing

The system includes comprehensive load testing for large EDI files (100MB+):

- **Quick tests**: `TEST_FAST=true pytest tests/test_large_file_load.py -v -m load_test`
- **Full tests**: `pytest tests/test_large_file_load.py -v -m load_test`
- **Manual testing**: `python scripts/load_test_large_files.py --file-size 100`

See [`LOAD_TEST_SUITE_COMPLETE.md`](LOAD_TEST_SUITE_COMPLETE.md) for details.

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

For comprehensive API documentation, see [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md).

## Documentation

📚 **[Full Documentation Index](docs/README.md)** - Complete documentation organized by category  
🚀 **[Quick Reference](DOCUMENTATION_QUICK_REFERENCE.md)** - Find docs by task, module, or topic  
📝 **[Contributing Guide](CONTRIBUTING.md)** - How to contribute and update documentation

### Quick Links

**Getting Started**
- **[Setup Guide](SETUP.md)** - Initial setup and configuration
- **[Dependencies](DEPENDENCIES.md)** - ⚠️ **READ FIRST** - Complete list of prerequisites
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

**API & Development**
- **[API Documentation](API_DOCUMENTATION.md)** - Complete API reference with examples
- **[EDI Format Guide](EDI_FORMAT_GUIDE.md)** - EDI file format specifications
- **[Development Roadmap](docs/ROADMAP.md)** - Development priorities and roadmap

**Deployment & Operations**
- **[Deployment Guide](deployment/DEPLOYMENT.md)** - Production deployment instructions
- **[Deployment Runbook](deployment/DEPLOYMENT_RUNBOOK.md)** - Step-by-step operational procedures
- **[Backup/Restore Guide](deployment/BACKUP_RESTORE.md)** - Database backup and restore procedures
- **[Production Security Checklist](deployment/PRODUCTION_SECURITY_CHECKLIST.md)** - Security checklist

**Monitoring & Tools**
- **[Sentry Setup](docs/guides/SENTRY_SETUP.md)** - Error tracking and monitoring
- **[Memory Monitoring](MEMORY_MONITORING.md)** - Memory tracking and configuration
- **[Security Guide](SECURITY.md)** - Security and HIPAA compliance

## License

Proprietary - All rights reserved

