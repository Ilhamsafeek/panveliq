"""
Task Management API Endpoints
File: app/api/v1/endpoints/tasks.py - COMPLETE IMPLEMENTATION
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, date
import pymysql

from app.core.config import settings
from app.core.security import get_current_user, require_admin, require_admin_or_employee, get_db_connection

router = APIRouter()


# ========== PYDANTIC MODELS ==========

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    client_id: int
    assigned_to: Optional[int] = None
    priority: str = "medium"  # low, medium, high, urgent
    due_date: Optional[date] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    priority: Optional[str] = None
    status: Optional[str] = None  # pending, in_progress, completed
    due_date: Optional[date] = None


# ========== TASK CRUD ENDPOINTS ==========

@router.get("/all", summary="Get all tasks (Admin only)")
async def get_all_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """
    Get all tasks in the system (Admin only)
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                t.task_id,
                t.task_title as title,
                t.task_description as description,
                t.priority,
                t.status,
                t.due_date,
                t.created_at,
                client.full_name as client_name,
                client.user_id as client_id,
                employee.full_name as assigned_to_name,
                employee.user_id as assigned_to_id,
                creator.full_name as created_by_name
            FROM tasks t
            LEFT JOIN users client ON t.client_id = client.user_id
            LEFT JOIN users employee ON t.assigned_to = employee.user_id
            LEFT JOIN users creator ON t.assigned_by = creator.user_id
            WHERE 1=1
        """
        
        params = []
        
        if status:
            query += " AND t.status = %s"
            params.append(status)
        
        if priority:
            query += " AND t.priority = %s"
            params.append(priority)
        
        query += " ORDER BY t.due_date ASC, t.priority DESC, t.created_at DESC"
        
        cursor.execute(query, params)
        tasks = cursor.fetchall()
        
        # Convert datetime to string
        for task in tasks:
            if task.get('due_date'):
                task['due_date'] = task['due_date'].isoformat()
            if task.get('created_at'):
                task['created_at'] = task['created_at'].isoformat()
        
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


@router.get("/my-tasks", summary="Get employee's assigned tasks")
async def get_my_tasks(
    status: Optional[str] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get tasks assigned to the current employee
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                t.task_id,
                t.task_title as title,
                t.task_description as description,
                t.priority,
                t.status,
                t.due_date,
                t.created_at,
                u.full_name as client_name,
                u.user_id as client_id
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
            if task.get('created_at'):
                task['created_at'] = task['created_at'].isoformat()
        
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


@router.get("/stats", summary="Get task statistics")
async def get_task_stats(
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get task statistics for current user
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        stats = {}
        
        if current_user['role'] == 'admin':
            # Admin sees all tasks
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'completed' AND DATE(updated_at) = CURDATE() THEN 1 ELSE 0 END) as completed_today,
                    SUM(CASE WHEN due_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as upcoming_deadlines
                FROM tasks
            """)
        else:
            # Employee sees only their tasks
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'completed' AND DATE(updated_at) = CURDATE() THEN 1 ELSE 0 END) as completed_today,
                    SUM(CASE WHEN due_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as upcoming_deadlines
                FROM tasks
                WHERE assigned_to = %s
            """, (current_user['user_id'],))
        
        stats = cursor.fetchone()
        
        # Get assigned clients count for employees
        if current_user['role'] == 'employee':
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM employee_assignments
                WHERE employee_id = %s
            """, (current_user['user_id'],))
            stats['assigned_clients'] = cursor.fetchone()['count']
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        print(f"Error fetching task stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch task stats: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/create", summary="Create new task (Admin only)")
async def create_task(
    task: TaskCreate,
    current_user: dict = Depends(require_admin)
):
    """
    Create a new task and assign it to an employee
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert task
        cursor.execute("""
            INSERT INTO tasks (
                client_id, assigned_to, assigned_by,
                task_title, task_description, priority, due_date, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (
            task.client_id,
            task.assigned_to,
            current_user['user_id'],
            task.title,
            task.description,
            task.priority,
            task.due_date
        ))
        
        connection.commit()
        task_id = cursor.lastrowid
        
        return {
            "success": True,
            "message": "Task created successfully",
            "task_id": task_id
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error creating task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/{task_id}", summary="Update task")
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Update task details
    Admin can update any task, employees can only update their assigned tasks
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if task exists and user has permission
        if current_user['role'] == 'employee':
            cursor.execute("""
                SELECT task_id FROM tasks 
                WHERE task_id = %s AND assigned_to = %s
            """, (task_id, current_user['user_id']))
            
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only update tasks assigned to you"
                )
        
        # Build update query
        update_fields = []
        values = []
        
        if task_update.title is not None:
            update_fields.append("task_title = %s")
            values.append(task_update.title)
        
        if task_update.description is not None:
            update_fields.append("task_description = %s")
            values.append(task_update.description)
        
        if task_update.assigned_to is not None and current_user['role'] == 'admin':
            update_fields.append("assigned_to = %s")
            values.append(task_update.assigned_to)
        
        if task_update.priority is not None:
            update_fields.append("priority = %s")
            values.append(task_update.priority)
        
        if task_update.status is not None:
            update_fields.append("status = %s")
            values.append(task_update.status)
        
        if task_update.due_date is not None:
            update_fields.append("due_date = %s")
            values.append(task_update.due_date)
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_fields.append("updated_at = NOW()")
        values.append(task_id)
        
        query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE task_id = %s"
        cursor.execute(query, values)
        connection.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        return {
            "success": True,
            "message": "Task updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error updating task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.delete("/{task_id}", summary="Delete task (Admin only)")
async def delete_task(
    task_id: int,
    current_user: dict = Depends(require_admin)
):
    """
    Delete a task
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("DELETE FROM tasks WHERE task_id = %s", (task_id,))
        connection.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        return {
            "success": True,
            "message": "Task deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error deleting task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete task: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/{task_id}", summary="Get task details")
async def get_task_details(
    task_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):

    """
    Get detailed information about a specific task
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                t.task_id,
                t.task_title as title,
                t.task_description as description,
                t.priority,
                t.status,
                t.due_date,
                t.created_at,
                t.updated_at,
                client.full_name as client_name,
                client.user_id as client_id,
                employee.full_name as assigned_to_name,
                employee.user_id as assigned_to_id,
                creator.full_name as created_by_name
            FROM tasks t
            LEFT JOIN users client ON t.client_id = client.user_id
            LEFT JOIN users employee ON t.assigned_to = employee.user_id
            LEFT JOIN users creator ON t.assigned_by = creator.user_id
            WHERE t.task_id = %s
        """, (task_id,))
        
        task = cursor.fetchone()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        # Check permission for employees
        if current_user['role'] == 'employee' and task['assigned_to_id'] != current_user['user_id']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view tasks assigned to you"
            )
        
        # Convert datetime to string
        if task.get('due_date'):
            task['due_date'] = task['due_date'].isoformat()
        if task.get('created_at'):
            task['created_at'] = task['created_at'].isoformat()
        if task.get('updated_at'):
            task['updated_at'] = task['updated_at'].isoformat()
        
        return {
            "success": True,
            "task": task
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching task details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch task details: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



