"""
API dependencies for authentication and database sessions.
"""
from typing import Generator, Optional
from datetime import datetime
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_token, verify_api_key
from app.models import User, APIKey
from app.schemas.user import TokenData

security = HTTPBearer()


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = verify_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except Exception:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_user_from_api_key(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> User:
    """Get current user from API key."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    api_key = credentials.credentials
    if not api_key.startswith("wf_"):
        raise credentials_exception
    
    # Find API key in database
    api_key_obj = db.query(APIKey).filter(APIKey.key_hash == api_key).first()
    if not api_key_obj:
        # Try to verify against hashed keys
        api_keys = db.query(APIKey).all()
        for key_obj in api_keys:
            if verify_api_key(api_key, key_obj.key_hash):
                api_key_obj = key_obj
                break
    
    if not api_key_obj:
        raise credentials_exception
    
    # Check if API key is expired
    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key expired"
        )
    
    user = db.query(User).filter(User.id == api_key_obj.user_id).first()
    if not user:
        raise credentials_exception
    
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user."""
    return current_user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current admin user."""
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user