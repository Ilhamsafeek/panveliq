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
            'pending'
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
    """
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get user by email - FIXED: use user_credentials.email
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
        
        # Check if user is active
        if user['status'] == 'suspended':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended. Please contact support."
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user['email'],
                "user_id": user['user_id'],
                "role": user['role']
            },
            expires_delta=access_token_expires
        )
        
        # Update last login - FIXED: simpler query
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
        print(f"Login error details: {e}")  # Debug print
        import traceback
        traceback.print_exc()  # Print full traceback
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