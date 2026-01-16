"""JWT authentication middleware."""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.security import get_jwt_secret, get_jwt_algorithm, get_jwt_access_token_expire_minutes
from app.utils.errors import UnauthorizedError

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=get_jwt_access_token_expire_minutes())
    
    # Convert datetime to timestamp (JWT exp claim must be numeric)
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, get_jwt_secret(), algorithm=get_jwt_algorithm())
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """Get current authenticated user from JWT token."""
    credentials_exception = UnauthorizedError("Could not validate credentials")
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[get_jwt_algorithm()])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # TODO: Load user from database
    # For now, return payload
    return {"user_id": user_id, "payload": payload}


def require_auth():
    """Dependency to require authentication."""
    return Depends(get_current_user)

