"""
PASTE THIS INTO: app/api/v1/endpoints/users.py (existing file)

Users Management API Endpoints - FULLY FUNCTIONAL
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
import pymysql
from passlib.context import CryptContext

from app.core.config import settings
from app.core.security import get_db_connection

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    role: str = "client"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


@router.get("/list")
async def list_users():
    """Get all users"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT user_id, email, full_name, phone, role, status, 
                   created_at, updated_at, last_login
            FROM users
            ORDER BY created_at DESC
        """
        cursor.execute(query)
        users = cursor.fetchall()
        
        # Convert datetime to string for JSON serialization
        for user in users:
            if user['created_at']:
                user['created_at'] = user['created_at'].isoformat()
            if user['updated_at']:
                user['updated_at'] = user['updated_at'].isoformat()
            if user['last_login']:
                user['last_login'] = user['last_login'].isoformat()
        
        return {
            "success": True,
            "users": users,
            "total": len(users)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/stats")
async def get_user_stats():
    """Get user statistics for admin dashboard"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']
        
        # Active clients
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'client' AND status = 'active'")
        active_clients = cursor.fetchone()['count']
        
        # Pending approval
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE status = 'pending'")
        pending_users = cursor.fetchone()['count']
        
        # Users by role
        cursor.execute("""
            SELECT role, COUNT(*) as count 
            FROM users 
            GROUP BY role
        """)
        users_by_role = cursor.fetchall()
        
        # Recent registrations (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM users 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        recent_registrations = cursor.fetchone()['count']
        
        return {
            "success": True,
            "stats": {
                "total_users": total_users,
                "active_clients": active_clients,
                "pending_users": pending_users,
                "recent_registrations": recent_registrations,
                "users_by_role": users_by_role
            }
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/create")
async def create_user(user: UserCreate):
    """Create new user"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if email exists
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (user.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = pwd_context.hash(user.password)
        
        # Insert user
        query = """
            INSERT INTO users (email, password_hash, full_name, phone, role, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            user.email,
            hashed_password,
            user.full_name,
            user.phone,
            user.role,
            'active'
        ))
        connection.commit()
        
        user_id = cursor.lastrowid
        
        return {
            "success": True,
            "message": "User created successfully",
            "user_id": user_id
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


@router.get("/{user_id}")
async def get_user(user_id: int):
    """Get specific user details"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT user_id, email, full_name, phone, role, status,
                   profile_image, created_at, updated_at, last_login
            FROM users 
            WHERE user_id = %s
        """
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Convert datetime to string
        if user['created_at']:
            user['created_at'] = user['created_at'].isoformat()
        if user['updated_at']:
            user['updated_at'] = user['updated_at'].isoformat()
        if user['last_login']:
            user['last_login'] = user['last_login'].isoformat()
        
        return {
            "success": True,
            "user": user
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/{user_id}")
async def update_user(user_id: int, user_data: UserUpdate):
    """Update user details"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Build update query dynamically
        update_fields = []
        values = []
        
        if user_data.full_name:
            update_fields.append("full_name = %s")
            values.append(user_data.full_name)
        
        if user_data.phone is not None:
            update_fields.append("phone = %s")
            values.append(user_data.phone)
        
        if user_data.role:
            if user_data.role not in ['client', 'admin', 'employee']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid role"
                )
            update_fields.append("role = %s")
            values.append(user_data.role)
        
        if user_data.status:
            if user_data.status not in ['pending', 'active', 'suspended', 'inactive']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid status"
                )
            update_fields.append("status = %s")
            values.append(user_data.status)
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Add updated_at
        update_fields.append("updated_at = NOW()")
        
        values.append(user_id)
        
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = %s"
        cursor.execute(query, values)
        connection.commit()
        
        return {
            "success": True,
            "message": "User updated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.delete("/{user_id}")
async def delete_user(user_id: int):
    """Delete a user permanently"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT email FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Delete user
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        connection.commit()
        
        return {
            "success": True,
            "message": f"User {user['email']} deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.patch("/{user_id}/status")
async def update_user_status(user_id: int, status: str):
    """Update user status only"""
    
    if status not in ['active', 'suspended', 'inactive', 'pending']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status. Must be: active, suspended, inactive, or pending"
        )
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT email FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update status
        cursor.execute(
            "UPDATE users SET status = %s, updated_at = NOW() WHERE user_id = %s",
            (status, user_id)
        )
        connection.commit()
        
        return {
            "success": True,
            "message": f"User {user['email']} status updated to {status}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update status: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()