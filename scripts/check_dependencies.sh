#!/bin/bash
# Dependency check script for mARB 2.0
# Run this before using any scripts or deployment procedures

set -e

echo "=========================================="
echo "mARB 2.0 - Dependency Check"
echo "=========================================="
echo ""
echo "For detailed dependency information, see: DEPENDENCIES.md"
echo ""

ERRORS=0
WARNINGS=0

# Check function
check_dependency() {
    if command -v "$1" &> /dev/null; then
        VERSION=$($1 --version 2>/dev/null | head -1 || echo "installed")
        echo "✓ $1: $VERSION"
        return 0
    else
        echo "✗ $1: NOT FOUND"
        ((ERRORS++))
        return 1
    fi
}

check_python_package() {
    if python -c "import $1" 2>/dev/null; then
        VERSION=$(python -c "try:
    import $1
    print($1.__version__)
except AttributeError:
    print('installed')
except Exception:
    print('installed')" 2>/dev/null || echo "installed")
        if [ -z "$VERSION" ]; then
            VERSION="installed (version unknown)"
        fi
        echo "✓ Python package $1: $VERSION"
        return 0
    else
        echo "✗ Python package $1: NOT INSTALLED"
        ((ERRORS++))
        return 1
    fi
}

check_file() {
    if [ -f "$1" ]; then
        echo "✓ File exists: $1"
        return 0
    else
        echo "✗ File missing: $1"
        ((WARNINGS++))
        return 1
    fi
}

check_directory() {
    if [ -d "$1" ]; then
        if [ -w "$1" ]; then
            echo "✓ Directory exists and is writable: $1"
        else
            echo "⚠ Directory exists but not writable: $1"
            ((WARNINGS++))
        fi
        return 0
    else
        echo "✗ Directory missing: $1"
        ((WARNINGS++))
        return 1
    fi
}

echo "=== System Dependencies ==="
check_dependency python3
check_dependency psql
check_dependency pg_dump
check_dependency pg_restore
check_dependency redis-cli
check_dependency nginx
check_dependency git
check_dependency gzip
check_dependency find
check_dependency curl
echo ""

echo "=== Python Environment ==="
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✓ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "⚠ Virtual environment not activated"
    echo "  Run: source venv/bin/activate"
    ((WARNINGS++))
fi

if [ -n "$VIRTUAL_ENV" ] || [ -f "venv/bin/python" ]; then
    PYTHON_CMD="${VIRTUAL_ENV}/bin/python"
    [ -z "$VIRTUAL_ENV" ] && PYTHON_CMD="venv/bin/python"
    
    echo ""
    echo "=== Python Packages ==="
    check_python_package fastapi
    check_python_package sqlalchemy
    check_python_package alembic
    check_python_package celery
    check_python_package redis
    check_python_package sentry_sdk || echo "⚠ sentry_sdk: Optional (for error tracking)"
    check_python_package pydantic
    check_python_package structlog
    echo ""
    
    echo "=== Test Dependencies ==="
    check_python_package pytest || echo "⚠ pytest: Optional (for running tests)"
    check_python_package factory_boy || echo "⚠ factory_boy: Optional (for test factories)"
fi

echo ""
echo "=== Configuration Files ==="
check_file ".env"
check_file "requirements.txt"
check_file "alembic.ini"
echo ""

echo "=== Scripts ==="
check_file "scripts/backup_db.sh"
check_file "scripts/verify_env.py"
check_file "scripts/validate_production_security.py"
echo ""

echo "=== Directories ==="
check_directory "backups"
check_directory "logs"
check_directory "alembic/versions"
echo ""

echo "=== Database Connection ==="
if [ -f ".env" ]; then
    # Try to load DATABASE_URL from .env
    if grep -q "DATABASE_URL" .env; then
        # Extract DATABASE_URL (simple extraction, may not handle all cases)
        DB_URL=$(grep "^DATABASE_URL=" .env | cut -d'=' -f2- | tr -d '"' | tr -d "'")
        if [ -n "$DB_URL" ]; then
            if psql "$DB_URL" -c "SELECT 1;" &> /dev/null; then
                echo "✓ Database connection: OK"
            else
                echo "✗ Database connection: FAILED"
                echo "  Check DATABASE_URL in .env file"
                ((ERRORS++))
            fi
        else
            echo "⚠ DATABASE_URL not set in .env"
            ((WARNINGS++))
        fi
    else
        echo "⚠ DATABASE_URL not found in .env"
        ((WARNINGS++))
    fi
else
    echo "⚠ .env file not found, cannot check database connection"
    ((WARNINGS++))
fi

echo ""
echo "=== Redis Connection ==="
if redis-cli ping &> /dev/null; then
    echo "✓ Redis connection: OK"
else
    echo "✗ Redis connection: FAILED"
    echo "  Check if Redis is running: redis-cli ping"
    ((ERRORS++))
fi

echo ""
echo "=========================================="
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✓ All dependencies satisfied!"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠ Some warnings (non-critical)"
    echo "  You can proceed, but review warnings above"
    exit 0
else
    echo "✗ Missing required dependencies"
    echo "  Fix errors above before proceeding"
    echo ""
    echo "  See ./DEPENDENCIES.md for installation instructions"
    echo "  Full documentation: $(pwd)/DEPENDENCIES.md"
    exit 1
fi

