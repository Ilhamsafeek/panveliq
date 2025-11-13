"""
Role-Based Access Control
File: app/core/security.py (UPDATE EXISTING FILE)

Add these functions for role-based access control
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional
import pymysql

from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/{settings.API_VERSION}/auth/login")


def get_db_connection():
    """Get MySQL database connection"""
    try:
        connection = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {str(e)}"
        )


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Get current authenticated user from token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    connection = None
    cursor = None
    
    try:
        # Decode token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if email is None or user_id is None:
            raise credentials_exception
        
        # Get user from database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(
            "SELECT user_id, email, full_name, role, status FROM users WHERE user_id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        
        if user is None:
            raise credentials_exception
        
        # Check if user is active
        if user['status'] == 'suspended':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended"
            )
        
        return user
    
    except JWTError:
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


async def require_admin(current_user: dict = Depends(get_current_user)):
    """
    Require admin role
    Use as dependency: Depends(require_admin)
    """
    if current_user['role'] != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_admin_or_employee(current_user: dict = Depends(get_current_user)):
    """
    Require admin or employee role
    Use as dependency: Depends(require_admin_or_employee)
    """
    if current_user['role'] not in ['admin', 'employee']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Employee access required"
        )
    return current_user


async def require_client(current_user: dict = Depends(get_current_user)):
    """
    Require client role
    Use as dependency: Depends(require_client)
    """
    if current_user['role'] != 'client':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client access required"
        )
    return current_user


def check_role(allowed_roles: list):
    """
    Generic role checker
    Usage: Depends(check_role(['admin', 'employee']))
    """
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user['role'] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker