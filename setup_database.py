#!/usr/bin/env python3
"""Database setup helper script."""
import os
import sys
import subprocess
from pathlib import Path
import secrets
import string
import shlex

def generate_secret_key(length=32):
    """Generate a random secret key."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def run_subprocess(cmd, timeout=5):
    """
    Run a subprocess command with consistent error handling.
    
    Args:
        cmd: Command to run as a list of strings
        timeout: Timeout in seconds (default: 5)
        
    Returns:
        str: Command output (stdout) if successful
        
    Raises:
        subprocess.CalledProcessError: If command returns non-zero exit code
        FileNotFoundError: If command not found
        subprocess.TimeoutExpired: If command times out
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # We'll handle return codes manually
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise e


def check_postgresql():
    """Check if PostgreSQL is installed and running."""
    print("🔍 Checking PostgreSQL installation...")
    
    # Try common PostgreSQL paths
    psql_paths = [
        "/usr/local/bin/psql",
        "/opt/homebrew/bin/psql",
        "/usr/bin/psql",
        "psql"
    ]
    
    psql_path = None
    for path in psql_paths:
        if os.path.exists(path) or path == "psql":
            try:
                output = run_subprocess([path, "--version"])
                psql_path = path
                print(f"✅ Found PostgreSQL: {output}")
                break
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                continue
            except subprocess.CalledProcessError as e:
                # Consistent error reporting
                error_msg = e.stderr.strip() if e.stderr else (e.stdout.strip() if e.stdout else str(e))
                print(f"⚠️  Error checking PostgreSQL at {path}: {error_msg}")
                continue
    
    if not psql_path:
        print("❌ PostgreSQL not found in common locations")
        print("\n💡 To install PostgreSQL on macOS:")
        print("   brew install postgresql@14")
        print("   brew services start postgresql@14")
        return None
    
    return psql_path

def check_postgres_running(psql_path):
    """Check if PostgreSQL server is running."""
    print("\n🔍 Checking if PostgreSQL server is running...")
    
    try:
        # Try to connect as current user
        username = os.getenv("DATABASE_USER", os.getenv("USER", "postgres"))
        run_subprocess(
            [psql_path, "-U", username, "-d", "postgres", "-c", "SELECT 1"]
        )
        print("✅ PostgreSQL server is running")
        return True
    except subprocess.CalledProcessError as e:
        # Consistent error reporting
        error_msg = e.stderr.strip() if e.stderr else (e.stdout.strip() if e.stdout else str(e))
        print(f"⚠️  PostgreSQL connection failed: {error_msg}")
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"⚠️  Could not check PostgreSQL status: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Could not check PostgreSQL status: {e}")
        return False

def create_database(psql_path, db_name="marb_risk_engine", username=None):
    """
    Create the database if it doesn't exist.
    
    Args:
        psql_path: Path to psql executable
        db_name: Name of the database to create (default: "marb_risk_engine")
        username: PostgreSQL username (default: from environment or "postgres")
        
    Returns:
        bool: True if database exists or was created successfully, False otherwise
    """
    print(f"\n📦 Creating database '{db_name}'...")
    
    if not username:
        username = os.getenv("DATABASE_USER", os.getenv("USER", "postgres"))
    
    # Validate and sanitize database name to prevent command injection
    # Only allow alphanumeric characters, underscores, and hyphens
    if not all(c.isalnum() or c in ('_', '-') for c in db_name):
        print(f"❌ Invalid database name: '{db_name}'. Only alphanumeric characters, underscores, and hyphens are allowed.")
        return False
    
    # Validate username to prevent command injection
    # Only allow alphanumeric characters, underscores, and hyphens
    if not all(c.isalnum() or c in ('_', '-') for c in username):
        print(f"❌ Invalid username: '{username}'. Only alphanumeric characters, underscores, and hyphens are allowed.")
        return False
    
    try:
        # Check if database exists - use parameterized query approach
        # Escape single quotes in db_name for SQL safety
        escaped_db_name = db_name.replace("'", "''")
        check_cmd = [
            psql_path,
            "-U", username,
            "-d", "postgres",
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname='{escaped_db_name}'"
        ]
        
        try:
            output = run_subprocess(check_cmd)
            if output == "1":
                print(f"✅ Database '{db_name}' already exists")
                return True
        except subprocess.CalledProcessError:
            # Database doesn't exist, continue to create it
            pass
        
        # Create database - use proper quoting
        # PostgreSQL identifiers can be quoted, but we've already validated the name
        create_cmd = [
            psql_path,
            "-U", username,
            "-d", "postgres",
            "-c",
            f"CREATE DATABASE \"{db_name}\";"
        ]
        
        try:
            run_subprocess(create_cmd)
            print(f"✅ Database '{db_name}' created successfully")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            print(f"❌ Failed to create database: {error_msg}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False

def create_env_file():
    """Create or update .env file with database configuration."""
    print("\n📝 Setting up .env file...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    # Get current username - allow override via DATABASE_USER env var
    username = os.getenv("DATABASE_USER", os.getenv("USER", "postgres"))
    
    # Generate secrets
    jwt_secret = generate_secret_key(64)
    encryption_key = generate_secret_key(32)
    
    # Default database URL - allow override via DATABASE_URL env var
    # Use a generic default that doesn't expose username in the default case
    if os.getenv("DATABASE_URL"):
        database_url = os.getenv("DATABASE_URL")
    else:
        # Construct URL from components, allowing full customization
        db_host = os.getenv("DATABASE_HOST", "localhost")
        db_port = os.getenv("DATABASE_PORT", "5432")
        database_name = os.getenv("DATABASE_NAME", "marb_risk_engine")
        database_url = f"postgresql://{username}@{db_host}:{db_port}/{database_name}"
    
    # Check if .env exists
    if env_file.exists():
        print("⚠️  .env file already exists")
        response = input("   Do you want to update it? (y/N): ").strip().lower()
        if response != 'y':
            print("   Skipping .env file update")
            return
    
    # Read existing .env if it exists
    env_vars = {}
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    
    # Update or set database variables
    env_vars["DATABASE_URL"] = database_url
    env_vars.setdefault("REDIS_HOST", "localhost")
    env_vars.setdefault("REDIS_PORT", "6379")
    env_vars.setdefault("JWT_SECRET_KEY", jwt_secret)
    env_vars.setdefault("ENCRYPTION_KEY", encryption_key)
    env_vars.setdefault("LOG_LEVEL", "info")
    env_vars.setdefault("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
    
    # Write .env file
    with open(env_file, "w") as f:
        f.write("# mARB 2.0 Environment Variables\n")
        f.write("# Generated by setup_database.py\n\n")
        f.write("# Database Configuration\n")
        f.write(f"DATABASE_URL={env_vars['DATABASE_URL']}\n\n")
        f.write("# Redis Configuration\n")
        f.write(f"REDIS_HOST={env_vars['REDIS_HOST']}\n")
        f.write(f"REDIS_PORT={env_vars['REDIS_PORT']}\n\n")
        f.write("# Security Configuration\n")
        f.write(f"JWT_SECRET_KEY={env_vars['JWT_SECRET_KEY']}\n")
        f.write(f"ENCRYPTION_KEY={env_vars['ENCRYPTION_KEY']}\n\n")
        f.write("# Application Configuration\n")
        f.write(f"LOG_LEVEL={env_vars['LOG_LEVEL']}\n")
        f.write(f"CORS_ORIGINS={env_vars['CORS_ORIGINS']}\n")
    
    print(f"✅ Created/updated .env file")
    print(f"   DATABASE_URL={database_url}")
    print(f"   (Secrets generated and saved)")

def test_connection():
    """Test database connection."""
    print("\n🧪 Testing database connection...")
    
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL not set in .env")
            return False
        
        from sqlalchemy import create_engine, text
        
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        print("✅ Database connection successful!")
        return True
        
    except ImportError:
        print("⚠️  python-dotenv not installed, skipping connection test")
        print("   Install with: pip install python-dotenv")
        return None
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Make sure PostgreSQL is running")
        print("   2. Check DATABASE_URL in .env file")
        print("   3. Verify database exists")
        return False

def main():
    """Main setup function."""
    print("=" * 60)
    print("mARB 2.0 - Database Setup")
    print("=" * 60)
    
    # Check PostgreSQL
    psql_path = check_postgresql()
    if not psql_path:
        print("\n❌ Cannot proceed without PostgreSQL")
        print("   Please install PostgreSQL first")
        return 1
    
    # Check if PostgreSQL is running
    if not check_postgres_running(psql_path):
        print("\n💡 To start PostgreSQL:")
        print("   brew services start postgresql@14")
        print("   # or")
        print("   pg_ctl -D /usr/local/var/postgres start")
        response = input("\n   Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            return 1
    
    # Create database
    username = os.getenv("USER", "postgres")
    if not create_database(psql_path, username=username):
        print("\n💡 You may need to:")
        print("   1. Create the database manually:")
        print(f"      createdb -U {username} marb_risk_engine")
        print("   2. Or use a different username in DATABASE_URL")
        response = input("\n   Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            return 1
    
    # Create .env file
    create_env_file()
    
    # Test connection
    test_connection()
    
    print("\n" + "=" * 60)
    print("✅ Database setup complete!")
    print("\n📋 Next steps:")
    print("   1. Run migrations: alembic upgrade head")
    print("   2. Start Redis: redis-server")
    print("   3. Start Celery: celery -A app.services.queue.tasks worker --loglevel=info")
    print("   4. Start API: python run.py")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

