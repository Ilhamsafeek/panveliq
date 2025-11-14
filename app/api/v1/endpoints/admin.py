"""
Admin Management API Endpoints
File: app/api/v1/endpoints/admin.py
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from datetime import datetime
import pymysql
from passlib.context import CryptContext

from app.core.config import settings
from app.core.security import get_current_user, require_admin, get_db_connection

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ========== PYDANTIC MODELS ==========

class EmployeeResponse(BaseModel):
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    status: str
    created_at: str


class EmployeeCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None


class UserStatusUpdate(BaseModel):
    status: str


# ========== EMPLOYEE ENDPOINTS ==========

@router.get("/employees", summary="Get all employees (Admin only)")
async def get_all_employees(
    status: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """
    Get all employees in the system
    Admin can filter by status
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                user_id,
                full_name,
                email,
                phone,
                status,
                created_at,
                last_login
            FROM users
            WHERE role = 'employee'
        """
        
        params = []
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        employees = cursor.fetchall()
        
        # Convert datetime to string
        for emp in employees:
            if emp.get('created_at'):
                emp['created_at'] = emp['created_at'].isoformat()
            if emp.get('last_login'):
                emp['last_login'] = emp['last_login'].isoformat()
        
        return {
            "success": True,
            "employees": employees,
            "total": len(employees)
        }
        
    except Exception as e:
        print(f"Error fetching employees: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employees: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/employees/{employee_id}", summary="Get employee details (Admin only)")
async def get_employee_details(
    employee_id: int,
    current_user: dict = Depends(require_admin)
):
    """
    Get detailed information about a specific employee
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Fetch employee details
        cursor.execute("""
            SELECT 
                user_id,
                full_name,
                email,
                phone,
                status,
                created_at,
                updated_at,
                last_login
            FROM users
            WHERE user_id = %s AND role = 'employee'
        """, (employee_id,))
        
        employee = cursor.fetchone()
        
        if not employee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Convert datetime to string
        if employee.get('created_at'):
            employee['created_at'] = employee['created_at'].isoformat()
        if employee.get('updated_at'):
            employee['updated_at'] = employee['updated_at'].isoformat()
        if employee.get('last_login'):
            employee['last_login'] = employee['last_login'].isoformat()
        
        # Fetch assigned clients
        cursor.execute("""
            SELECT 
                u.user_id as client_id,
                u.full_name,
                u.email,
                cp.business_name,
                ea.assigned_at
            FROM employee_assignments ea
            JOIN users u ON ea.client_id = u.user_id
            LEFT JOIN client_profiles cp ON u.user_id = cp.client_id
            WHERE ea.employee_id = %s
            ORDER BY ea.assigned_at DESC
        """, (employee_id,))
        
        assigned_clients = cursor.fetchall()
        
        # Convert datetime
        for client in assigned_clients:
            if client.get('assigned_at'):
                client['assigned_at'] = client['assigned_at'].isoformat()
        
        # Fetch task statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_tasks
            FROM tasks
            WHERE assigned_to = %s
        """, (employee_id,))
        
        task_stats = cursor.fetchone()
        
        employee['assigned_clients'] = assigned_clients
        employee['total_clients'] = len(assigned_clients)
        employee['total_tasks'] = task_stats['total_tasks'] or 0
        employee['completed_tasks'] = task_stats['completed_tasks'] or 0
        employee['in_progress_tasks'] = task_stats['in_progress_tasks'] or 0
        
        return {
            "success": True,
            "employee": employee
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching employee details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch employee details: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/employees", summary="Create new employee (Admin only)")
async def create_employee(
    employee: EmployeeCreate,
    current_user: dict = Depends(require_admin)
):
    """
    Create a new employee account
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (employee.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = pwd_context.hash(employee.password)
        
        # Insert new employee
        cursor.execute("""
            INSERT INTO users (email, password_hash, full_name, phone, role, status)
            VALUES (%s, %s, %s, %s, 'employee', 'active')
        """, (employee.email, hashed_password, employee.full_name, employee.phone))
        
        connection.commit()
        employee_id = cursor.lastrowid
        
        return {
            "success": True,
            "message": "Employee created successfully",
            "employee_id": employee_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error creating employee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create employee: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/employees/{employee_id}/status", summary="Update employee status (Admin only)")
async def update_employee_status(
    employee_id: int,
    status_update: UserStatusUpdate,
    current_user: dict = Depends(require_admin)
):
    """
    Update employee status (active, suspended, etc.)
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify employee exists
        cursor.execute("""
            SELECT user_id FROM users 
            WHERE user_id = %s AND role = 'employee'
        """, (employee_id,))
        
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Update status
        cursor.execute("""
            UPDATE users 
            SET status = %s, updated_at = NOW()
            WHERE user_id = %s
        """, (status_update.status, employee_id))
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Employee status updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error updating employee status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee status: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.delete("/employees/{employee_id}", summary="Delete employee (Admin only)")
async def delete_employee(
    employee_id: int,
    current_user: dict = Depends(require_admin)
):
    """
    Delete an employee account
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify employee exists
        cursor.execute("""
            SELECT user_id FROM users 
            WHERE user_id = %s AND role = 'employee'
        """, (employee_id,))
        
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found"
            )
        
        # Delete employee (cascading will handle assignments)
        cursor.execute("DELETE FROM users WHERE user_id = %s", (employee_id,))
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Employee deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error deleting employee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete employee: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== USER MANAGEMENT ENDPOINTS ==========

@router.get("/users", summary="Get all users (Admin only)")
async def get_all_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """
    Get all users with optional filters
    """
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
                created_at,
                last_login
            FROM users
            WHERE 1=1
        """
        
        params = []
        
        if role:
            query += " AND role = %s"
            params.append(role)
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        users = cursor.fetchall()
        
        # Convert datetime to string
        for user in users:
            if user.get('created_at'):
                user['created_at'] = user['created_at'].isoformat()
            if user.get('last_login'):
                user['last_login'] = user['last_login'].isoformat()
        
        return {
            "success": True,
            "users": users,
            "total": len(users)
        }
        
    except Exception as e:
        print(f"Error fetching users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/stats", summary="Get admin statistics (Admin only)")
async def get_admin_statistics(
    current_user: dict = Depends(require_admin)
):
    """
    Get overall system statistics for admin dashboard
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        stats = {}
        
        # Total users by role
        cursor.execute("""
            SELECT role, COUNT(*) as count 
            FROM users 
            GROUP BY role
        """)
        role_counts = cursor.fetchall()
        stats['users_by_role'] = {row['role']: row['count'] for row in role_counts}
        
        # Total users by status
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM users 
            GROUP BY status
        """)
        status_counts = cursor.fetchall()
        stats['users_by_status'] = {row['status']: row['count'] for row in status_counts}
        
        # Active subscriptions
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM client_subscriptions 
            WHERE status = 'active'
        """)
        stats['active_subscriptions'] = cursor.fetchone()['count']
        
        # Pending verifications
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM onboarding_sessions 
            WHERE verification_status = 'pending'
        """)
        stats['pending_verifications'] = cursor.fetchone()['count']
        
        # Total revenue
        cursor.execute("""
            SELECT SUM(p.price) as revenue
            FROM client_subscriptions cs
            JOIN packages p ON cs.package_id = p.package_id
            WHERE cs.status = 'active'
        """)
        revenue_result = cursor.fetchone()
        stats['total_revenue'] = float(revenue_result['revenue'] or 0)
        
        return {
            "success": True,
            "statistics": stats
        }
        
    except Exception as e:
        print(f"Error fetching statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()