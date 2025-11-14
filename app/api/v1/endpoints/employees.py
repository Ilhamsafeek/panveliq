"""
Employee-specific API Endpoints
File: app/api/v1/endpoints/employees.py
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import pymysql

from app.core.config import settings
from app.core.security import get_current_user, require_admin_or_employee, get_db_connection

router = APIRouter()


# ========== PYDANTIC MODELS ==========

class TaskResponse(BaseModel):
    task_id: int
    title: str
    description: Optional[str] = None
    client_name: Optional[str] = None
    status: str
    priority: str
    due_date: Optional[str] = None


@router.get("/my-tasks", summary="Get employee's tasks")
async def get_my_tasks(
    status: Optional[str] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get all tasks assigned to the current employee
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                t.task_id,
                t.title,
                t.description,
                t.status,
                t.priority,
                t.due_date,
                u.full_name as client_name
            FROM tasks t
            LEFT JOIN users u ON t.client_id = u.user_id
            WHERE t.assigned_to = %s
        """
        
        params = [current_user['user_id']]
        
        if status:
            query += " AND t.status = %s"
            params.append(status)
        
        query += " ORDER BY t.due_date ASC, t.priority DESC"
        
        cursor.execute(query, params)
        tasks = cursor.fetchall()
        
        # Convert datetime to string
        for task in tasks:
            if task.get('due_date'):
                task['due_date'] = task['due_date'].isoformat()
        
        return {
            "success": True,
            "tasks": tasks,
            "total": len(tasks)
        }
        
    except Exception as e:
        print(f"Error fetching tasks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tasks: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/dashboard-stats", summary="Get employee dashboard statistics")
async def get_dashboard_stats(
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get statistics for employee dashboard
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        stats = {}
        
        # Total assigned clients
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM employee_assignments 
            WHERE employee_id = %s
        """, (current_user['user_id'],))
        stats['total_clients'] = cursor.fetchone()['count']
        
        # Active tasks
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM tasks 
            WHERE assigned_to = %s AND status != 'completed'
        """, (current_user['user_id'],))
        stats['active_tasks'] = cursor.fetchone()['count']
        
        # Completed tasks
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM tasks 
            WHERE assigned_to = %s AND status = 'completed'
        """, (current_user['user_id'],))
        stats['completed_tasks'] = cursor.fetchone()['count']
        
        # Overdue tasks
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM tasks 
            WHERE assigned_to = %s 
            AND status != 'completed'
            AND due_date < CURDATE()
        """, (current_user['user_id'],))
        stats['overdue_tasks'] = cursor.fetchone()['count']
        
        return {
            "success": True,
            "statistics": stats
        }
        
    except Exception as e:
        print(f"Error fetching dashboard stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard statistics: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()