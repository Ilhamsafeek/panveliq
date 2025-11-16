"""
Settings & Profile Management API
File: app/api/v1/endpoints/settings.py
CREATE THIS NEW FILE
"""

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from passlib.context import CryptContext
import pymysql
import json
import base64

from app.core.config import settings
from app.core.security import get_current_user, require_admin
from app.core.security import get_db_connection

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ========== PYDANTIC MODELS ==========

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class APISettingUpdate(BaseModel):
    setting_key: str
    setting_value: str


# ========== PROFILE ENDPOINTS ==========

@router.get("/profile", summary="Get current user profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's profile information"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                user_id,
                email,
                full_name,
                phone,
                role,
                status,
                profile_image,
                created_at,
                last_login
            FROM users
            WHERE user_id = %s
        """
        
        cursor.execute(query, (current_user['user_id'],))
        profile = cursor.fetchone()
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        return {
            "status": "success",
            "profile": profile
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/profile", summary="Update user profile")
async def update_profile(
    profile_update: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update current user's profile"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Build dynamic update query
        update_fields = []
        update_values = []
        
        if profile_update.full_name is not None:
            update_fields.append("full_name = %s")
            update_values.append(profile_update.full_name)
        
        if profile_update.phone is not None:
            update_fields.append("phone = %s")
            update_values.append(profile_update.phone)
        
        if profile_update.email is not None:
            # Check if email already exists
            cursor.execute(
                "SELECT user_id FROM users WHERE email = %s AND user_id != %s",
                (profile_update.email, current_user['user_id'])
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
                )
            update_fields.append("email = %s")
            update_values.append(profile_update.email)
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Execute update
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = %s"
        update_values.append(current_user['user_id'])
        
        cursor.execute(query, tuple(update_values))
        connection.commit()
        
        return {
            "status": "success",
            "message": "Profile updated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/profile/change-password", summary="Change password")
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get current password hash
        cursor.execute(
            "SELECT password_hash FROM users WHERE user_id = %s",
            (current_user['user_id'],)
        )
        
        user = cursor.fetchone()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify current password
        if not pwd_context.verify(password_data.current_password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Hash new password
        new_password_hash = pwd_context.hash(password_data.new_password)
        
        # Update password
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE user_id = %s",
            (new_password_hash, current_user['user_id'])
        )
        
        connection.commit()
        
        return {
            "status": "success",
            "message": "Password changed successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== SYSTEM SETTINGS (ADMIN ONLY) ==========

@router.get("/system", summary="Get system settings (admin)")
async def get_system_settings(current_user: dict = Depends(require_admin)):
    """Admin: Get all system settings"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                setting_id,
                setting_key,
                setting_value,
                setting_category,
                is_encrypted,
                updated_at
            FROM system_settings
            ORDER BY setting_category, setting_key
        """
        
        cursor.execute(query)
        settings_list = cursor.fetchall()
        
        # Group by category
        grouped = {
            'api': [],
            'general': [],
            'email': [],
            'notification': []
        }
        
        for setting in settings_list:
            category = setting['setting_category']
            
            # Mask encrypted values for security
            if setting['is_encrypted'] and setting['setting_value']:
                setting['setting_value'] = '••••••••'
            
            grouped[category].append(setting)
        
        return {
            "status": "success",
            "settings": grouped
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch settings: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/system", summary="Update system setting (admin)")
async def update_system_setting(
    setting_update: APISettingUpdate,
    current_user: dict = Depends(require_admin)
):
    """Admin: Update a system setting"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if setting exists
        cursor.execute(
            "SELECT setting_id, is_encrypted FROM system_settings WHERE setting_key = %s",
            (setting_update.setting_key,)
        )
        
        setting = cursor.fetchone()
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Setting not found"
            )
        
        # If encrypted, encode the value (basic encoding, use proper encryption in production)
        value_to_store = setting_update.setting_value
        if setting['is_encrypted'] and setting_update.setting_value:
            # In production, use proper encryption like Fernet
            value_to_store = base64.b64encode(setting_update.setting_value.encode()).decode()
        
        # Update setting
        cursor.execute(
            "UPDATE system_settings SET setting_value = %s, updated_by = %s WHERE setting_key = %s",
            (value_to_store, current_user['user_id'], setting_update.setting_key)
        )
        
        connection.commit()
        
        return {
            "status": "success",
            "message": "Setting updated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update setting: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/api-keys", summary="Get API keys status (admin)")
async def get_api_keys_status(current_user: dict = Depends(require_admin)):
    """Admin: Get status of all API keys (configured or not)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                setting_key,
                CASE 
                    WHEN setting_value IS NOT NULL AND setting_value != '' THEN TRUE
                    ELSE FALSE
                END as is_configured,
                updated_at
            FROM system_settings
            WHERE setting_category = 'api'
            ORDER BY setting_key
        """
        
        cursor.execute(query)
        api_keys = cursor.fetchall()
        
        return {
            "status": "success",
            "api_keys": api_keys
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch API keys status: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()