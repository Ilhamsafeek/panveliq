"""
PASTE THIS INTO: app/api/v1/endpoints/auth.py (existing file)
COMPLETE FIXED VERSION
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional
import pymysql
from pymysql import Error

from app.core.config import settings

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/{settings.API_VERSION}/auth/login")


# ========== PYDANTIC MODELS ==========

class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = None
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str
    remember: Optional[bool] = False


class UserResponse(BaseModel):
    """Schema for user response"""
    user_id: int
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    status: str


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str
    user: UserResponse



class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request"""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Schema for reset password request"""
    token: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

# ========== DATABASE FUNCTIONS ==========

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
        print(f"Database connection error: {e}")
        print(f"Host: {settings.DB_HOST}")
        print(f"Port: {settings.DB_PORT}")
        print(f"User: {settings.DB_USER}")
        print(f"Database: {settings.DB_NAME}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {str(e)}"
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


# ========== API ENDPOINTS ==========

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate):
    """
    Register a new user
    
    - **email**: Valid email address
    - **password**: Minimum 8 characters
    - **full_name**: User's full name
    - **phone**: Optional phone number
    """
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (user.email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = get_password_hash(user.password)
        
        # Insert new user (let MySQL handle timestamps)
        insert_query = """
            INSERT INTO users (email, password_hash, full_name, phone, role, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (
            user.email,
            hashed_password,
            user.full_name,
            user.phone,
            'client',
            'active'
        ))
        
        connection.commit()
        user_id = cursor.lastrowid
        
        return {
            "user_id": user_id,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": "client",
            "status": "pending"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """
    Login with email and password
    
    Returns JWT access token and user information
    ⚠️ Users with status='pending' cannot login
    """
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get user by email
        query = "SELECT * FROM users WHERE email = %s"
        cursor.execute(query, (user_credentials.email,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(user_credentials.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # ⭐ NEW: Check user status BEFORE allowing login
        if user['status'] == 'pending':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is pending verification. Please wait for admin approval."
            )
        
        if user['status'] == 'suspended':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been suspended. Please contact support."
            )
        
        if user['status'] == 'inactive':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is inactive. Please contact support."
            )
        
        # Only allow login for 'active' users
        if user['status'] != 'active':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account cannot login at this time. Please contact support."
            )
        
        # User is active, create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user['email'],
                "user_id": user['user_id'],
                "role": user['role']
            },
            expires_delta=access_token_expires
        )
        
        # Update last login
        update_query = "UPDATE users SET last_login = NOW() WHERE user_id = %s"
        cursor.execute(update_query, (user['user_id'],))
        connection.commit()
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "user_id": user['user_id'],
                "email": user['email'],
                "full_name": user['full_name'],
                "phone": user['phone'],
                "role": user['role'],
                "status": user['status']
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error details: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
@router.post("/logout")
async def logout():
    """Logout user (client-side token removal)"""
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(token: str = Depends(oauth2_scheme)):
    """Get current user information"""
    
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
        if email is None:
            raise credentials_exception
        
        # Get user from database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user is None:
            raise credentials_exception
        
        return {
            "user_id": user['user_id'],
            "email": user['email'],
            "full_name": user['full_name'],
            "phone": user['phone'],
            "role": user['role'],
            "status": user['status']
        }
    
    except JWTError:
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



# ========== PASSWORD RECOVERY ENDPOINTS ==========

@router.post("/forgot-password", summary="Request password reset")
async def forgot_password(request: ForgotPasswordRequest):
    """
    Request password reset - generates token and sends email
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute(
            "SELECT user_id, email, full_name FROM users WHERE email = %s",
            (request.email,)
        )
        user = cursor.fetchone()
        
        # Always return success even if user doesn't exist (security best practice)
        # This prevents email enumeration attacks
        if not user:
            return {
                "status": "success",
                "message": "If the email exists, a password reset link has been sent"
            }
        
        # Generate secure reset token
        reset_token = secrets.token_urlsafe(32)
        
        # Token expires in 1 hour
        expires_at = datetime.now() + timedelta(hours=1)
        
        # Store reset token in database
        cursor.execute(
            """
            INSERT INTO password_reset_tokens 
            (user_id, reset_token, expires_at)
            VALUES (%s, %s, %s)
            """,
            (user['user_id'], reset_token, expires_at)
        )
        
        connection.commit()
        
        # In production, send email with reset link here
        # For now, we'll return the token for testing
        # reset_link = f"http://yourdomain.com/auth/reset-password?token={reset_token}"
        
        # TODO: Send email using SMTP or email service
        # send_reset_email(user['email'], user['full_name'], reset_link)
        
        print(f"🔐 Password reset token for {request.email}: {reset_token}")
        print(f"   Expires at: {expires_at}")
        
        return {
            "status": "success",
            "message": "If the email exists, a password reset link has been sent",
            # For development/testing only - remove in production!
            "debug_token": reset_token if settings.DEBUG else None
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error in forgot password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process password reset request"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/reset-password", summary="Reset password with token")
async def reset_password(request: ResetPasswordRequest):
    """
    Reset password using valid token
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify token exists and is valid
        cursor.execute(
            """
            SELECT prt.token_id, prt.user_id, prt.expires_at, prt.is_used,
                   u.email, u.full_name
            FROM password_reset_tokens prt
            JOIN users u ON prt.user_id = u.user_id
            WHERE prt.reset_token = %s
            """,
            (request.token,)
        )
        
        token_data = cursor.fetchone()
        
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Check if token is already used
        if token_data['is_used']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset token has already been used"
            )
        
        # Check if token is expired
        if datetime.now() > token_data['expires_at']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired. Please request a new one"
            )
        
        # Hash new password
        new_password_hash = pwd_context.hash(request.new_password)
        
        # Update user password
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE user_id = %s",
            (new_password_hash, token_data['user_id'])
        )
        
        # Mark token as used
        cursor.execute(
            "UPDATE password_reset_tokens SET is_used = TRUE, used_at = %s WHERE token_id = %s",
            (datetime.now(), token_data['token_id'])
        )
        
        connection.commit()
        
        print(f"✅ Password reset successful for user: {token_data['email']}")
        
        # TODO: Send confirmation email
        # send_password_changed_email(token_data['email'], token_data['full_name'])
        
        return {
            "status": "success",
            "message": "Password has been reset successfully. You can now login with your new password."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error in reset password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/verify-reset-token", summary="Verify reset token validity")
async def verify_reset_token(token: str):
    """
    Verify if a reset token is valid (for frontend validation)
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(
            """
            SELECT expires_at, is_used
            FROM password_reset_tokens
            WHERE reset_token = %s
            """,
            (token,)
        )
        
        token_data = cursor.fetchone()
        
        if not token_data:
            return {
                "valid": False,
                "message": "Invalid token"
            }
        
        if token_data['is_used']:
            return {
                "valid": False,
                "message": "Token already used"
            }
        
        if datetime.now() > token_data['expires_at']:
            return {
                "valid": False,
                "message": "Token expired"
            }
        
        return {
            "valid": True,
            "message": "Token is valid",
            "expires_at": token_data['expires_at'].isoformat()
        }
    
    except Exception as e:
        print(f"❌ Error verifying token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify token"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()