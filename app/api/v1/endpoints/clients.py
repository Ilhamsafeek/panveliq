"""
Client Management API Endpoints
File: app/api/v1/endpoints/clients.py
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import pymysql

from app.core.config import settings
from app.core.security import get_current_user, require_admin, require_admin_or_employee, get_db_connection

router = APIRouter()


# ========== PYDANTIC MODELS ==========

class ClientListResponse(BaseModel):
    client_id: int
    full_name: str
    email: str
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    website_url: Optional[str] = None
    package_name: Optional[str] = None
    package_tier: Optional[str] = None
    subscription_status: Optional[str] = None
    subscription_end_date: Optional[str] = None
    assigned_employee_name: Optional[str] = None
    assigned_employee_id: Optional[int] = None
    status: str
    created_at: str


class ClientDetailResponse(BaseModel):
    client_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    website_url: Optional[str] = None
    current_budget: Optional[float] = None
    package_name: Optional[str] = None
    package_tier: Optional[str] = None
    package_price: Optional[float] = None
    billing_cycle: Optional[str] = None
    subscription_status: Optional[str] = None
    subscription_start_date: Optional[str] = None
    subscription_end_date: Optional[str] = None
    assigned_employees: List[dict] = []
    active_tasks_count: int = 0
    completed_tasks_count: int = 0
    status: str
    created_at: str


class AssignEmployeeRequest(BaseModel):
    client_id: int
    employee_id: int


class UpdateClientProfileRequest(BaseModel):
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    website_url: Optional[str] = None
    current_budget: Optional[float] = None


# ========== LIST ENDPOINT (FOR COMMUNICATION MODULE) ==========

@router.get("/list", summary="Get accessible clients for dropdowns")
async def list_clients(
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get list of clients for dropdowns in communication module
    Admin: All active clients
    Employee: Assigned clients only
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        if current_user['role'] == 'admin':
            # Admin: Get all active clients
            cursor.execute("""
                SELECT 
                    u.user_id,
                    u.full_name,
                    u.email,
                    u.phone,
                    u.status,
                    cp.business_name,
                    cp.business_type,
                    cp.website_url,
                    u.created_at
                FROM users u
                LEFT JOIN client_profiles cp ON u.user_id = cp.client_id
                WHERE u.role = 'client' AND u.status = 'active'
                ORDER BY u.created_at DESC
            """)
        else:
            # Employee: only assigned clients
            cursor.execute("""
                SELECT 
                    u.user_id,
                    u.full_name,
                    u.email,
                    u.phone,
                    u.status,
                    cp.business_name,
                    cp.business_type,
                    cp.website_url,
                    ea.assigned_at
                FROM employee_assignments ea
                JOIN users u ON ea.client_id = u.user_id
                LEFT JOIN client_profiles cp ON u.user_id = cp.client_id
                WHERE ea.employee_id = %s AND u.status = 'active'
                ORDER BY ea.assigned_at DESC
            """, (current_user['user_id'],))
        
        clients = cursor.fetchall()
        
        # Convert datetime objects to ISO format strings
        for client in clients:
            if client.get('created_at'):
                client['created_at'] = client['created_at'].isoformat() if hasattr(client['created_at'], 'isoformat') else str(client['created_at'])
            if client.get('assigned_at'):
                client['assigned_at'] = client['assigned_at'].isoformat() if hasattr(client['assigned_at'], 'isoformat') else str(client['assigned_at'])
        
        return {
            "success": True,
            "clients": clients,
            "total": len(clients)
        }
        
    except Exception as e:
        print(f"Error fetching clients list: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch clients: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== ADMIN ENDPOINTS ==========

@router.get("/all", summary="Get all clients (Admin only)")
async def get_all_clients(
    status_filter: Optional[str] = None,
    package_tier: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """
    Admin endpoint to get all clients with filters
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                u.user_id as client_id,
                u.full_name,
                u.email,
                u.status,
                u.created_at,
                cp.business_name,
                cp.business_type,
                cp.website_url,
                p.package_name,
                p.package_tier,
                cs.status as subscription_status,
                cs.end_date as subscription_end_date,
                emp.full_name as assigned_employee_name,
                emp.user_id as assigned_employee_id
            FROM users u
            LEFT JOIN client_profiles cp ON u.user_id = cp.client_id
            LEFT JOIN client_subscriptions cs ON u.user_id = cs.client_id 
                AND cs.status = 'active'
            LEFT JOIN packages p ON cs.package_id = p.package_id
            LEFT JOIN employee_assignments ea ON u.user_id = ea.client_id
            LEFT JOIN users emp ON ea.employee_id = emp.user_id
            WHERE u.role = 'client'
        """
        
        params = []
        
        if status_filter:
            query += " AND u.status = %s"
            params.append(status_filter)
        
        if package_tier:
            query += " AND p.package_tier = %s"
            params.append(package_tier)
        
        query += " ORDER BY u.created_at DESC"
        
        cursor.execute(query, params if params else None)
        clients = cursor.fetchall()
        
        # Convert datetime
        for client in clients:
            if client.get('created_at'):
                client['created_at'] = client['created_at'].isoformat()
            if client.get('subscription_end_date'):
                client['subscription_end_date'] = client['subscription_end_date'].isoformat()
        
        return {
            "success": True,
            "clients": clients,
            "total": len(clients)
        }
        
    except Exception as e:
        print(f"Error fetching clients: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch clients: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== EMPLOYEE ENDPOINTS ==========

@router.get("/my-clients")
async def get_my_clients(current_user: dict = Depends(require_admin_or_employee)):
    """Get employee's assigned clients"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        if current_user['role'] == 'admin':
            cursor.execute("""
                SELECT 
                    u.user_id as client_id,
                    u.full_name,
                    u.email,
                    u.status,
                    u.created_at,
                    cp.business_name,
                    cp.business_type,
                    p.package_name,
                    p.package_tier,
                    cs.status as subscription_status,
                    cs.end_date as subscription_end_date
                FROM users u
                LEFT JOIN client_profiles cp ON u.user_id = cp.client_id
                LEFT JOIN client_subscriptions cs ON u.user_id = cs.client_id AND cs.status = 'active'
                LEFT JOIN packages p ON cs.package_id = p.package_id
                WHERE u.role = 'client' AND u.status = 'active'
                ORDER BY u.created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT 
                    u.user_id as client_id,
                    u.full_name,
                    u.email,
                    u.status,
                    u.created_at,
                    cp.business_name,
                    cp.business_type,
                    p.package_name,
                    p.package_tier,
                    cs.status as subscription_status,
                    cs.end_date as subscription_end_date,
                    ea.assigned_at
                FROM employee_assignments ea
                JOIN users u ON ea.client_id = u.user_id
                LEFT JOIN client_profiles cp ON u.user_id = cp.client_id
                LEFT JOIN client_subscriptions cs ON u.user_id = cs.client_id AND cs.status = 'active'
                LEFT JOIN packages p ON cs.package_id = p.package_id
                WHERE ea.employee_id = %s AND u.status = 'active'
                ORDER BY ea.assigned_at DESC
            """, (current_user['user_id'],))
        
        clients = cursor.fetchall()
        
        for client in clients:
            if client.get('created_at'):
                client['created_at'] = client['created_at'].isoformat()
            if client.get('assigned_at'):
                client['assigned_at'] = client['assigned_at'].isoformat()
            if client.get('subscription_end_date'):
                client['subscription_end_date'] = client['subscription_end_date'].isoformat()
        
        return {"success": True, "clients": clients, "total": len(clients)}
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



@router.get("/{client_id}", summary="Get client details")
async def get_client_details(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get detailed information about a specific client
    Admin: Can view any client
    Employee: Can only view assigned clients
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # If employee, verify they're assigned to this client
        if current_user['role'] == 'employee':
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM employee_assignments 
                WHERE employee_id = %s AND client_id = %s
            """, (current_user['user_id'], client_id))
            
            result = cursor.fetchone()
            if result['count'] == 0:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not assigned to this client"
                )
        
        # Fetch client details
        cursor.execute("""
            SELECT 
                u.user_id as client_id,
                u.full_name,
                u.email,
                u.phone,
                u.status,
                u.created_at,
                cp.business_name,
                cp.business_type,
                cp.website_url,
                cp.current_budget,
                p.package_name,
                p.package_tier,
                p.price as package_price,
                p.billing_cycle,
                cs.status as subscription_status,
                cs.start_date as subscription_start_date,
                cs.end_date as subscription_end_date
            FROM users u
            LEFT JOIN client_profiles cp ON u.user_id = cp.client_id
            LEFT JOIN client_subscriptions cs ON u.user_id = cs.client_id 
                AND cs.status = 'active'
            LEFT JOIN packages p ON cs.package_id = p.package_id
            WHERE u.user_id = %s AND u.role = 'client'
        """, (client_id,))
        
        client = cursor.fetchone()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Fetch assigned employees
        cursor.execute("""
            SELECT 
                u.user_id,
                u.full_name,
                u.email,
                ea.assigned_at
            FROM employee_assignments ea
            JOIN users u ON ea.employee_id = u.user_id
            WHERE ea.client_id = %s
            ORDER BY ea.assigned_at DESC
        """, (client_id,))
        
        assigned_employees = cursor.fetchall()
        
        # Convert datetime
        if client.get('created_at'):
            client['created_at'] = client['created_at'].isoformat()
        if client.get('subscription_start_date'):
            client['subscription_start_date'] = client['subscription_start_date'].isoformat()
        if client.get('subscription_end_date'):
            client['subscription_end_date'] = client['subscription_end_date'].isoformat()
        
        for emp in assigned_employees:
            if emp.get('assigned_at'):
                emp['assigned_at'] = emp['assigned_at'].isoformat()
        
        client['assigned_employees'] = assigned_employees
        client['active_tasks_count'] = 0
        client['completed_tasks_count'] = 0
        
        return {
            "success": True,
            "client": client
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching client details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch client details: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== STATISTICS ENDPOINTS ==========

@router.get("/stats/overview", summary="Get client statistics")
async def get_client_statistics(
    current_user: dict = Depends(require_admin)
):
    """
    Get overall client statistics (Admin only)
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Total clients
        cursor.execute("""
            SELECT COUNT(*) as total FROM users WHERE role = 'client'
        """)
        total_clients = cursor.fetchone()['total']
        
        # Active clients
        cursor.execute("""
            SELECT COUNT(*) as total FROM users 
            WHERE role = 'client' AND status = 'active'
        """)
        active_clients = cursor.fetchone()['total']
        
        # Clients by package tier
        cursor.execute("""
            SELECT 
                p.package_tier,
                COUNT(*) as count
            FROM client_subscriptions cs
            JOIN packages p ON cs.package_id = p.package_id
            WHERE cs.status = 'active'
            GROUP BY p.package_tier
        """)
        clients_by_tier = cursor.fetchall()
        
        # Total revenue
        cursor.execute("""
            SELECT 
                SUM(p.price) as total_revenue
            FROM client_subscriptions cs
            JOIN packages p ON cs.package_id = p.package_id
            WHERE cs.status = 'active'
        """)
        revenue_result = cursor.fetchone()
        total_revenue = float(revenue_result['total_revenue'] or 0)
        
        return {
            "success": True,
            "statistics": {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "clients_by_tier": clients_by_tier,
                "total_revenue": total_revenue
            }
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


@router.post("/assign-employee", summary="Assign employee to client")
async def assign_employee_to_client(
    request: AssignEmployeeRequest,
    current_user: dict = Depends(require_admin)
):
    """
    Assign an employee to a client (Admin only)
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if assignment already exists
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM employee_assignments 
            WHERE employee_id = %s AND client_id = %s
        """, (request.employee_id, request.client_id))
        
        if cursor.fetchone()['count'] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee is already assigned to this client"
            )
        
        # Create assignment
        cursor.execute("""
            INSERT INTO employee_assignments (employee_id, client_id, assigned_by, assigned_at)
            VALUES (%s, %s, %s, NOW())
        """, (request.employee_id, request.client_id, current_user['user_id']))
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Employee assigned successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error assigning employee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign employee: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/{client_id}/profile", summary="Update client profile")
async def update_client_profile(
    client_id: int,
    request: UpdateClientProfileRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Update client profile information
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if profile exists
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM client_profiles 
            WHERE client_id = %s
        """, (client_id,))
        
        profile_exists = cursor.fetchone()['count'] > 0
        
        if profile_exists:
            # Update existing profile
            update_fields = []
            params = []
            
            if request.business_name is not None:
                update_fields.append("business_name = %s")
                params.append(request.business_name)
            if request.business_type is not None:
                update_fields.append("business_type = %s")
                params.append(request.business_type)
            if request.website_url is not None:
                update_fields.append("website_url = %s")
                params.append(request.website_url)
            if request.current_budget is not None:
                update_fields.append("current_budget = %s")
                params.append(request.current_budget)
            
            if update_fields:
                params.append(client_id)
                query = f"""
                    UPDATE client_profiles 
                    SET {', '.join(update_fields)}
                    WHERE client_id = %s
                """
                cursor.execute(query, params)
        else:
            # Create new profile
            cursor.execute("""
                INSERT INTO client_profiles 
                (client_id, business_name, business_type, website_url, current_budget)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                client_id,
                request.business_name,
                request.business_type,
                request.website_url,
                request.current_budget
            ))
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Client profile updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error updating client profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update client profile: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

            