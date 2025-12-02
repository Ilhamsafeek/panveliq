# ============================================
# COMPLETE app/core/security.py
# Copy this ENTIRE file and replace your existing security.py
# ============================================

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional
import pymysql

from app.core.config import settings

# Make token optional so we can also check cookies
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/{settings.API_VERSION}/auth/login", auto_error=False)


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


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme)
):
    """
    Get current authenticated user from token
    Checks both Authorization header and cookies
    """
    print("\n" + "="*60)
    print("[AUTH DEBUG] Starting authentication")
    print("="*60)
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Debug: Print all headers
    print("[AUTH DEBUG] Request headers:")
    for key, value in request.headers.items():
        if key.lower() == 'authorization':
            print(f"  {key}: {value[:50]}..." if len(value) > 50 else f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")
    
    # Debug: Print cookies
    print("[AUTH DEBUG] Cookies:", dict(request.cookies))
    
    # Try to get token from different sources
    auth_token = token
    print(f"[AUTH DEBUG] Token from OAuth2 dependency: {auth_token[:50] if auth_token else 'None'}")
    
    # If no token from header, try cookies
    if not auth_token:
        auth_token = request.cookies.get("access_token")
        print(f"[AUTH DEBUG] Token from cookies: {auth_token[:50] if auth_token else 'None'}")
    
    # Also try to manually extract from Authorization header
    if not auth_token:
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        print(f"[AUTH DEBUG] Raw Authorization header: {auth_header}")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:]
            print(f"[AUTH DEBUG] Token extracted manually: {auth_token[:50] if auth_token else 'None'}")
    
    # If still no token, raise exception
    if not auth_token:
        print("[AUTH DEBUG] ERROR: No token found anywhere!")
        print("="*60 + "\n")
        raise credentials_exception
    
    print(f"[AUTH DEBUG] Final token to validate (length={len(auth_token)})")
    
    connection = None
    cursor = None
    
    try:
        # Decode token
        print(f"[AUTH DEBUG] Decoding with SECRET_KEY: {settings.SECRET_KEY[:10]}...")
        
        payload = jwt.decode(auth_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        print(f"[AUTH DEBUG] Token payload: {payload}")
        
        email = payload.get("sub")
        user_id = payload.get("user_id")
        
        print(f"[AUTH DEBUG] Extracted - email: {email}, user_id: {user_id}")
        
        if email is None or user_id is None:
            print("[AUTH DEBUG] ERROR: Invalid payload")
            print("="*60 + "\n")
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
            print(f"[AUTH DEBUG] ERROR: User not found: {user_id}")
            print("="*60 + "\n")
            raise credentials_exception
        
        print(f"[AUTH DEBUG] User found: {user}")
        
        if user['status'] == 'suspended':
            print("[AUTH DEBUG] ERROR: User suspended")
            print("="*60 + "\n")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended"
            )
        
        print(f"[AUTH DEBUG] SUCCESS: {user['email']} ({user['role']})")
        print("="*60 + "\n")
        return user
    
    except JWTError as e:
        print(f"[AUTH DEBUG] JWT ERROR: {e}")
        print("="*60 + "\n")
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH DEBUG] ERROR: {e}")
        print("="*60 + "\n")
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
    """Require admin role"""
    if current_user['role'] != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_admin_or_employee(current_user: dict = Depends(get_current_user)):
    """Require admin or employee role"""
    if current_user['role'] not in ['admin', 'employee']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Employee access required"
        )
    return current_user


async def require_client(current_user: dict = Depends(get_current_user)):
    """Require client role"""
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