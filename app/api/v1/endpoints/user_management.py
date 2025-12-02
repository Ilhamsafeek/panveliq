"""
User Management & Access Control API
File: app/api/v1/endpoints/user_management.py

Complete user management with granular access control
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import pymysql
import json
from passlib.context import CryptContext

from app.core.config import settings
from app.core.security import require_admin, get_current_user, get_db_connection

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ========== PYDANTIC MODELS ==========

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    role: str = Field(pattern="^(client|admin|employee)$")
    phone: Optional[str] = None
    status: str = Field(default="active", pattern="^(active|suspended|inactive)$")


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(client|admin|employee)$")
    status: Optional[str] = Field(None, pattern="^(active|suspended|inactive)$")


class PasswordChange(BaseModel):
    new_password: str = Field(min_length=8)


class PermissionAssign(BaseModel):
    user_id: int
    permission_ids: List[int]
    expires_at: Optional[str] = None


class PermissionRevoke(BaseModel):
    user_id: int
    permission_ids: List[int]


# ========== HELPER FUNCTIONS ==========

def log_audit(cursor, connection, user_id: int, action: str, details: dict, 
              target_user_id: int = None, permission_id: int = None, 
              ip_address: str = None):
    """Log access control audit entry"""
    try:
        cursor.execute("""
            INSERT INTO access_control_audit 
            (user_id, action, target_user_id, permission_id, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, action, target_user_id, permission_id, 
              json.dumps(details), ip_address))
        connection.commit()
    except Exception as e:
        print(f"Audit log error: {e}")


def check_permission(cursor, user_id: int, permission_key: str) -> bool:
    """Check if user has specific permission"""
    try:
        # Get user role
        cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return False
        
        role = user['role']
        
        # Get permission ID
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key = %s",
            (permission_key,)
        )
        perm = cursor.fetchone()
        if not perm:
            return False
        
        permission_id = perm['permission_id']
        
        # Check for custom user permission (overrides role)
        cursor.execute("""
            SELECT granted FROM user_permissions 
            WHERE user_id = %s AND permission_id = %s
            AND (expires_at IS NULL OR expires_at > NOW())
        """, (user_id, permission_id))
        
        user_perm = cursor.fetchone()
        if user_perm:
            return user_perm['granted']
        
        # Check role permission
        cursor.execute("""
            SELECT COUNT(*) as has_perm FROM role_permissions 
            WHERE role = %s AND permission_id = %s
        """, (role, permission_id))
        
        result = cursor.fetchone()
        return result['has_perm'] > 0
        
    except Exception as e:
        print(f"Permission check error: {e}")
        return False


# ========== USER MANAGEMENT ENDPOINTS ==========

@router.get("/users", summary="Get all users with pagination")
async def get_all_users(
    page: int = 1,
    limit: int = 20,
    role: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """Get all users with filtering and pagination (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Build query
        where_clauses = []
        params = []
        
        if role:
            where_clauses.append("role = %s")
            params.append(role)
        
        if status:
            where_clauses.append("status = %s")
            params.append(status)
        
        if search:
            where_clauses.append("(full_name LIKE %s OR email LIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get total count
        cursor.execute(f"SELECT COUNT(*) as total FROM users WHERE {where_clause}", params)
        total = cursor.fetchone()['total']
        
        # Get users with pagination
        offset = (page - 1) * limit
        params.extend([limit, offset])
        
        cursor.execute(f"""
            SELECT 
                user_id, email, full_name, phone, role, status, 
                profile_image, created_at, updated_at, last_login
            FROM users 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, params)
        
        users = cursor.fetchall()
        
        # Get user permissions for each user
        for user in users:
            cursor.execute("""
                SELECT p.permission_name, p.permission_key, up.granted
                FROM user_permissions up
                JOIN permissions p ON up.permission_id = p.permission_id
                WHERE up.user_id = %s 
                AND (up.expires_at IS NULL OR up.expires_at > NOW())
            """, (user['user_id'],))
            
            user['custom_permissions'] = cursor.fetchall()
        
        return {
            "success": True,
            "users": users,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
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


@router.get("/users/{user_id}", summary="Get user by ID with full details")
async def get_user_by_id(
    user_id: int,
    current_user: dict = Depends(require_admin)
):
    """Get comprehensive user information with related data (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get basic user info
        cursor.execute("""
            SELECT 
                user_id, email, full_name, phone, role, status,
                profile_image, created_at, updated_at, last_login
            FROM users 
            WHERE user_id = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get custom permissions
        cursor.execute("""
            SELECT 
                p.permission_id, p.permission_name, p.permission_key, 
                p.module, up.granted, up.granted_at, up.expires_at,
                granter.full_name as granted_by_name
            FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.permission_id
            LEFT JOIN users granter ON up.granted_by = granter.user_id
            WHERE up.user_id = %s
            AND (up.expires_at IS NULL OR up.expires_at > NOW())
        """, (user_id,))
        
        user['custom_permissions'] = cursor.fetchall()
        
        # Get role permissions
        cursor.execute("""
            SELECT p.permission_name, p.permission_key, p.module
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.permission_id
            WHERE rp.role = %s
        """, (user['role'],))
        
        user['role_permissions'] = cursor.fetchall()
        
        # Additional data based on role
        if user['role'] == 'client':
            # Get client profile
            cursor.execute("""
                SELECT business_name, business_type, website_url, current_budget
                FROM client_profiles
                WHERE client_id = %s
            """, (user_id,))
            user['client_profile'] = cursor.fetchone()
            
            # Get active subscription
            cursor.execute("""
                SELECT 
                    cs.subscription_id, cs.start_date, cs.end_date, cs.status,
                    p.package_name, p.package_tier, p.price, p.billing_cycle
                FROM client_subscriptions cs
                JOIN packages p ON cs.package_id = p.package_id
                WHERE cs.client_id = %s AND cs.status = 'active'
                ORDER BY cs.created_at DESC
                LIMIT 1
            """, (user_id,))
            user['subscription'] = cursor.fetchone()
            
            # Get assigned employee
            cursor.execute("""
                SELECT u.full_name as employee_name, u.email as employee_email, ea.assigned_at
                FROM employee_assignments ea
                JOIN users u ON ea.employee_id = u.user_id
                WHERE ea.client_id = %s
                LIMIT 1
            """, (user_id,))
            user['assigned_employee'] = cursor.fetchone()
            
        elif user['role'] == 'employee':
            # Get assigned clients count
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM employee_assignments
                WHERE employee_id = %s
            """, (user_id,))
            user['assigned_clients_count'] = cursor.fetchone()['count']
            
        # Get tasks count
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM tasks
            WHERE assigned_to = %s
        """, (user_id,))
        user['tasks_summary'] = cursor.fetchone()
        
        # Get recent activity count
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM activity_logs
            WHERE user_id = %s
            AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (user_id,))
        user['recent_activity_count'] = cursor.fetchone()['count']
        
        return {
            "success": True,
            "user": user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user details: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

            
@router.post("/users", summary="Create new user")
async def create_user(
    user: UserCreate,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Create a new user (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Check if email already exists
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (user.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        password_hash = pwd_context.hash(user.password)
        
        # Create user
        cursor.execute("""
            INSERT INTO users 
            (email, password_hash, full_name, phone, role, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user.email, password_hash, user.full_name, user.phone, 
              user.role, user.status))
        
        new_user_id = cursor.lastrowid
        connection.commit()
        
        # Log audit
        log_audit(
            cursor, connection, current_user['user_id'], 
            'user_created', 
            {
                'new_user_id': new_user_id,
                'email': user.email,
                'role': user.role
            },
            target_user_id=new_user_id,
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": "User created successfully",
            "user_id": new_user_id
        }
        
    except HTTPException:
        if connection:
            connection.rollback()
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


@router.put("/users/{user_id}", summary="Update user")
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Update user information (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Check if user exists
        cursor.execute("SELECT role, status FROM users WHERE user_id = %s", (user_id,))
        existing_user = cursor.fetchone()
        
        if not existing_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Build update query
        updates = []
        params = []
        changes = {}
        
        if user_update.full_name is not None:
            updates.append("full_name = %s")
            params.append(user_update.full_name)
            changes['full_name'] = user_update.full_name
        
        if user_update.phone is not None:
            updates.append("phone = %s")
            params.append(user_update.phone)
            changes['phone'] = user_update.phone
        
        if user_update.role is not None:
            updates.append("role = %s")
            params.append(user_update.role)
            changes['role'] = {'from': existing_user['role'], 'to': user_update.role}
        
        if user_update.status is not None:
            updates.append("status = %s")
            params.append(user_update.status)
            changes['status'] = {'from': existing_user['status'], 'to': user_update.status}
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Update user
        params.append(user_id)
        cursor.execute(f"""
            UPDATE users 
            SET {', '.join(updates)}, updated_at = NOW()
            WHERE user_id = %s
        """, params)
        
        connection.commit()
        
        # Log audit
        log_audit(
            cursor, connection, current_user['user_id'],
            'user_updated',
            {'changes': changes},
            target_user_id=user_id,
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": "User updated successfully"
        }
        
    except HTTPException:
        if connection:
            connection.rollback()
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


@router.delete("/users/{user_id}", summary="Delete user")
async def delete_user(
    user_id: int,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Delete a user (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Prevent self-deletion
        if user_id == current_user['user_id']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        # Get user details for audit
        cursor.execute("SELECT email, role FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete user
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        connection.commit()
        
        # Log audit
        log_audit(
            cursor, connection, current_user['user_id'],
            'user_deleted',
            {'email': user['email'], 'role': user['role']},
            target_user_id=user_id,
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": "User deleted successfully"
        }
        
    except HTTPException:
        if connection:
            connection.rollback()
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


@router.post("/users/{user_id}/change-password", summary="Change user password")
async def change_user_password(
    user_id: int,
    password_change: PasswordChange,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Change user password (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Hash new password
        password_hash = pwd_context.hash(password_change.new_password)
        
        # Update password
        cursor.execute("""
            UPDATE users 
            SET password_hash = %s, updated_at = NOW()
            WHERE user_id = %s
        """, (password_hash, user_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        connection.commit()
        
        # Log audit
        log_audit(
            cursor, connection, current_user['user_id'],
            'password_changed',
            {},
            target_user_id=user_id,
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": "Password changed successfully"
        }
        
    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/users/{user_id}/suspend", summary="Suspend/Unsuspend user")
async def toggle_user_suspension(
    user_id: int,
    suspend: bool,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Suspend or unsuspend a user (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Prevent self-suspension
        if user_id == current_user['user_id']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot suspend your own account"
            )
        
        new_status = 'suspended' if suspend else 'active'
        
        cursor.execute("""
            UPDATE users 
            SET status = %s, updated_at = NOW()
            WHERE user_id = %s
        """, (new_status, user_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        connection.commit()
        
        # Log audit
        log_audit(
            cursor, connection, current_user['user_id'],
            'user_suspended' if suspend else 'user_unsuspended',
            {},
            target_user_id=user_id,
            ip_address=request.client.host
        )
        
        return {
            "success": True,
            "message": f"User {'suspended' if suspend else 'activated'} successfully"
        }
        
    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user status: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== ACCESS CONTROL ENDPOINTS ==========

@router.get("/permissions", summary="Get all permissions")
async def get_all_permissions(
    module: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """Get all available permissions (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        if module:
            cursor.execute("""
                SELECT * FROM permissions 
                WHERE module = %s
                ORDER BY module, permission_name
            """, (module,))
        else:
            cursor.execute("""
                SELECT * FROM permissions 
                ORDER BY module, permission_name
            """)
        
        permissions = cursor.fetchall()
        
        # Group by module
        grouped = {}
        for perm in permissions:
            mod = perm['module']
            if mod not in grouped:
                grouped[mod] = []
            grouped[mod].append(perm)
        
        return {
            "success": True,
            "permissions": permissions,
            "grouped_by_module": grouped
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch permissions: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/roles/{role}/permissions", summary="Get role permissions")
async def get_role_permissions(
    role: str,
    current_user: dict = Depends(require_admin)
):
    """Get permissions for a specific role (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT p.*
            FROM role_permissions rp
            JOIN permissions p ON rp.permission_id = p.permission_id
            WHERE rp.role = %s
            ORDER BY p.module, p.permission_name
        """, (role,))
        
        permissions = cursor.fetchall()
        
        return {
            "success": True,
            "role": role,
            "permissions": permissions
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch role permissions: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/users/assign-permissions", summary="Assign custom permissions")
async def assign_custom_permissions(
    assignment: PermissionAssign,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Assign custom permissions to a user (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Verify user exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (assignment.user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        
        # Assign permissions
        for perm_id in assignment.permission_ids:
            cursor.execute("""
                INSERT INTO user_permissions 
                (user_id, permission_id, granted, granted_by, expires_at)
                VALUES (%s, %s, TRUE, %s, %s)
                ON DUPLICATE KEY UPDATE 
                granted = TRUE, granted_by = %s, granted_at = NOW(), expires_at = %s
            """, (assignment.user_id, perm_id, current_user['user_id'], 
                  assignment.expires_at, current_user['user_id'], assignment.expires_at))
            
            # Log each permission assignment
            log_audit(
                cursor, connection, current_user['user_id'],
                'permission_assigned',
                {'expires_at': assignment.expires_at},
                target_user_id=assignment.user_id,
                permission_id=perm_id,
                ip_address=request.client.host
            )
        
        connection.commit()
        
        return {
            "success": True,
            "message": f"{len(assignment.permission_ids)} permissions assigned successfully"
        }
        
    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign permissions: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/users/revoke-permissions", summary="Revoke custom permissions")
async def revoke_custom_permissions(
    revocation: PermissionRevoke,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Revoke custom permissions from a user (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Revoke permissions
        for perm_id in revocation.permission_ids:
            cursor.execute("""
                UPDATE user_permissions 
                SET granted = FALSE, granted_by = %s, granted_at = NOW()
                WHERE user_id = %s AND permission_id = %s
            """, (current_user['user_id'], revocation.user_id, perm_id))
            
            # Log audit
            log_audit(
                cursor, connection, current_user['user_id'],
                'permission_revoked',
                {},
                target_user_id=revocation.user_id,
                permission_id=perm_id,
                ip_address=request.client.host
            )
        
        connection.commit()
        
        return {
            "success": True,
            "message": f"{len(revocation.permission_ids)} permissions revoked successfully"
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke permissions: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/audit-log", summary="Get access control audit log")
async def get_audit_log(
    page: int = 1,
    limit: int = 50,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """Get access control audit log (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Build query
        where_clauses = []
        params = []
        
        if user_id:
            where_clauses.append("aca.user_id = %s OR aca.target_user_id = %s")
            params.extend([user_id, user_id])
        
        if action:
            where_clauses.append("aca.action = %s")
            params.append(action)
        
        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get total count
        cursor.execute(
            f"SELECT COUNT(*) as total FROM access_control_audit aca WHERE {where_clause}",
            params
        )
        total = cursor.fetchone()['total']
        
        # Get audit logs
        offset = (page - 1) * limit
        params.extend([limit, offset])
        
        cursor.execute(f"""
            SELECT 
                aca.*,
                u.full_name as user_name, u.email as user_email,
                tu.full_name as target_user_name, tu.email as target_user_email,
                p.permission_name
            FROM access_control_audit aca
            LEFT JOIN users u ON aca.user_id = u.user_id
            LEFT JOIN users tu ON aca.target_user_id = tu.user_id
            LEFT JOIN permissions p ON aca.permission_id = p.permission_id
            WHERE {where_clause}
            ORDER BY aca.created_at DESC
            LIMIT %s OFFSET %s
        """, params)
        
        logs = cursor.fetchall()
        
        return {
            "success": True,
            "logs": logs,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch audit log: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/users/{user_id}/activity", summary="Get user activity log")
async def get_user_activity(
    user_id: int,
    page: int = 1,
    limit: int = 50,
    current_user: dict = Depends(require_admin)
):
    """Get user activity log (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get total count
        cursor.execute(
            "SELECT COUNT(*) as total FROM user_activity_log WHERE user_id = %s",
            (user_id,)
        )
        total = cursor.fetchone()['total']
        
        # Get activity logs
        offset = (page - 1) * limit
        
        cursor.execute("""
            SELECT * FROM user_activity_log
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (user_id, limit, offset))
        
        logs = cursor.fetchall()
        
        return {
            "success": True,
            "logs": logs,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user activity: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/statistics", summary="Get user management statistics")
async def get_user_statistics(
    current_user: dict = Depends(require_admin)
):
    """Get user management statistics (Admin only)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Total users by role
        cursor.execute("""
            SELECT role, COUNT(*) as count
            FROM users
            GROUP BY role
        """)
        users_by_role = cursor.fetchall()
        
        # Users by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM users
            GROUP BY status
        """)
        users_by_status = cursor.fetchall()
        
        # Active sessions
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM user_sessions
            WHERE expires_at > NOW()
        """)
        active_sessions = cursor.fetchone()['count']
        
        # Recent activities (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM user_activity_log
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        recent_activities = cursor.fetchone()['count']
        
        # Custom permissions count
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM user_permissions
            WHERE granted = TRUE
            AND (expires_at IS NULL OR expires_at > NOW())
        """)
        custom_permissions = cursor.fetchone()['count']
        
        return {
            "success": True,
            "statistics": {
                "users_by_role": users_by_role,
                "users_by_status": users_by_status,
                "active_sessions": active_sessions,
                "recent_activities": recent_activities,
                "custom_permissions": custom_permissions
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()