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



@router.get("/admin/dashboard-stats", summary="Get admin dashboard statistics")
async def get_dashboard_stats(current_user: dict = Depends(require_admin)):
    """Get statistics for admin dashboard"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']
        
        # Active clients
        cursor.execute("""
            SELECT COUNT(*) as count FROM users 
            WHERE role = 'client' AND status = 'active'
        """)
        active_clients = cursor.fetchone()['count']
        
        # Total revenue (from financial_transactions)
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total 
            FROM financial_transactions 
            WHERE transaction_type = 'revenue'
        """)
        total_revenue = float(cursor.fetchone()['total'] or 0)
        
        # Pending tasks
        cursor.execute("""
            SELECT COUNT(*) as count FROM tasks 
            WHERE status = 'pending'
        """)
        pending_tasks = cursor.fetchone()['count']
        
        # Active employees
        cursor.execute("""
            SELECT COUNT(*) as count FROM users 
            WHERE role = 'employee' AND status = 'active'
        """)
        active_employees = cursor.fetchone()['count']
        
        # This month's revenue
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total 
            FROM financial_transactions 
            WHERE transaction_type = 'revenue'
            AND MONTH(transaction_date) = MONTH(CURRENT_DATE())
            AND YEAR(transaction_date) = YEAR(CURRENT_DATE())
        """)
        monthly_revenue = float(cursor.fetchone()['total'] or 0)
        
        return {
            "success": True,
            "stats": {
                "total_users": total_users,
                "active_clients": active_clients,
                "active_employees": active_employees,
                "total_revenue": total_revenue,
                "monthly_revenue": monthly_revenue,
                "pending_tasks": pending_tasks
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard stats: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/admin/recent-activity", summary="Get recent platform activity")
async def get_recent_activity(
    limit: int = 10,
    current_user: dict = Depends(require_admin)
):
    """Get recent activity across the platform"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # First check if activity_logs table exists and has data
        cursor.execute("""
            SELECT 
                al.log_id,
                al.user_id,
                al.activity_type,
                al.activity_description,
                al.created_at,
                u.full_name as user_name,
                u.email as user_email
            FROM activity_logs al
            LEFT JOIN users u ON al.user_id = u.user_id
            ORDER BY al.created_at DESC
            LIMIT %s
        """, (limit,))
        
        activities = cursor.fetchall()
        
        # If no activities in activity_logs, gather from other sources
        if not activities:
            all_activities = []
            
            # Recent user registrations
            cursor.execute("""
                SELECT 
                    user_id,
                    full_name as user_name,
                    'user_created' as activity_type,
                    CONCAT('New user registered: ', full_name) as activity_description,
                    created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT 5
            """)
            all_activities.extend(cursor.fetchall())
            
            # Recent tasks
            cursor.execute("""
                SELECT 
                    t.task_id,
                    u.full_name as user_name,
                    'task_created' as activity_type,
                    CONCAT('Task created: ', t.task_title) as activity_description,
                    t.created_at
                FROM tasks t
                LEFT JOIN users u ON t.assigned_by = u.user_id
                ORDER BY t.created_at DESC
                LIMIT 5
            """)
            all_activities.extend(cursor.fetchall())
            
            # Recent content
            cursor.execute("""
                SELECT 
                    c.content_id,
                    u.full_name as user_name,
                    'content_created' as activity_type,
                    CONCAT('Content created: ', COALESCE(c.title, 'Untitled')) as activity_description,
                    c.created_at
                FROM content_library c
                LEFT JOIN users u ON c.created_by = u.user_id
                ORDER BY c.created_at DESC
                LIMIT 5
            """)
            all_activities.extend(cursor.fetchall())
            
            # Recent campaigns
            cursor.execute("""
                SELECT 
                    ec.email_campaign_id,
                    u.full_name as user_name,
                    'campaign_created' as activity_type,
                    CONCAT('Email campaign: ', ec.campaign_name) as activity_description,
                    ec.created_at
                FROM email_campaigns ec
                LEFT JOIN users u ON ec.created_by = u.user_id
                ORDER BY ec.created_at DESC
                LIMIT 5
            """)
            all_activities.extend(cursor.fetchall())
            
            # Sort all activities by created_at and limit
            all_activities.sort(key=lambda x: x['created_at'] if x['created_at'] else datetime.min, reverse=True)
            activities = all_activities[:limit]
        
        # Convert datetime objects
        for activity in activities:
            if activity.get('created_at'):
                activity['created_at'] = activity['created_at'].isoformat()
        
        return {
            "success": True,
            "activities": activities
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recent activity: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/tasks/pending", summary="Get pending tasks")
async def get_pending_tasks(
    limit: int = 5,
    current_user: dict = Depends(require_admin)
):
    """Get pending tasks for admin dashboard"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT 
                t.task_id,
                t.task_title,
                t.task_description,
                t.priority,
                t.status,
                t.due_date,
                t.created_at,
                u.full_name as assigned_to_name,
                c.full_name as client_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_to = u.user_id
            LEFT JOIN users c ON t.client_id = c.user_id
            WHERE t.status IN ('pending', 'in_progress')
            ORDER BY 
                CASE t.priority 
                    WHEN 'urgent' THEN 1 
                    WHEN 'high' THEN 2 
                    WHEN 'medium' THEN 3 
                    WHEN 'low' THEN 4 
                END,
                t.due_date ASC
            LIMIT %s
        """, (limit,))
        
        tasks = cursor.fetchall()
        
        # Convert datetime objects
        for task in tasks:
            if task.get('due_date'):
                task['due_date'] = task['due_date'].isoformat()
            if task.get('created_at'):
                task['created_at'] = task['created_at'].isoformat()
        
        return {
            "success": True,
            "tasks": tasks
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending tasks: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ============================================
# HELPER: Log Activity Function
# Call this from other endpoints to log activities
# ============================================

def log_activity(user_id: int, activity_type: str, description: str):
    """Helper function to log user activity"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO activity_logs (user_id, activity_type, activity_description)
            VALUES (%s, %s, %s)
        """, (user_id, activity_type, description))
        
        connection.commit()
        
    except Exception as e:
        print(f"Failed to log activity: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()