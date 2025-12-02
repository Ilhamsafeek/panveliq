"""
Packages Management API
File: app/api/v1/endpoints/packages.py
CREATE THIS NEW FILE
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import pymysql
import json

from app.core.config import settings
from app.core.security import get_current_user, require_admin
from app.core.security import get_db_connection

router = APIRouter()


# ========== PYDANTIC MODELS ==========

class PackageCreate(BaseModel):
    package_name: str = Field(..., min_length=3, max_length=100)
    package_tier: str = Field(..., pattern="^(basic|professional|enterprise)$")
    description: str = Field(..., min_length=10)
    price: float = Field(..., gt=0)
    billing_cycle: str = Field(..., pattern="^(monthly|quarterly|yearly)$")
    features: Dict[str, Any]
    is_active: bool = True


class PackageUpdate(BaseModel):
    package_name: Optional[str] = None
    package_tier: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    billing_cycle: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


# ========== ADMIN ENDPOINTS ==========

@router.get("/all", summary="Get all packages (admin)")
async def get_all_packages(current_user: dict = Depends(require_admin)):
    """Admin: Get all packages including inactive"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                package_id,
                package_name,
                package_tier,
                description,
                price,
                billing_cycle,
                features,
                is_active,
                created_at
            FROM packages
            ORDER BY 
                CASE package_tier
                    WHEN 'basic' THEN 1
                    WHEN 'professional' THEN 2
                    WHEN 'enterprise' THEN 3
                END
        """
        
        cursor.execute(query)
        packages = cursor.fetchall()
        
        # Parse features JSON
        for package in packages:
            if package['features'] and isinstance(package['features'], str):
                package['features'] = json.loads(package['features'])
        
        return {
            "status": "success",
            "packages": packages,
            "total": len(packages)
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch packages: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/create", summary="Create new package (admin)")
async def create_package(
    package: PackageCreate,
    current_user: dict = Depends(require_admin)
):
    """Admin: Create a new package"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if package name already exists
        cursor.execute(
            "SELECT package_id FROM packages WHERE package_name = %s",
            (package.package_name,)
        )
        
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Package with this name already exists"
            )
        
        # Insert package
        query = """
            INSERT INTO packages 
            (package_name, package_tier, description, price, billing_cycle, features, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            package.package_name,
            package.package_tier,
            package.description,
            package.price,
            package.billing_cycle,
            json.dumps(package.features),
            package.is_active
        ))
        
        connection.commit()
        package_id = cursor.lastrowid
        
        return {
            "status": "success",
            "message": "Package created successfully",
            "package_id": package_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create package: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/{package_id}", summary="Update package (admin)")
async def update_package(
    package_id: int,
    package_update: PackageUpdate,
    current_user: dict = Depends(require_admin)
):
    """Admin: Update an existing package"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if package exists
        cursor.execute(
            "SELECT package_id FROM packages WHERE package_id = %s",
            (package_id,)
        )
        
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package not found"
            )
        
        # Build dynamic update query
        update_fields = []
        update_values = []
        
        if package_update.package_name is not None:
            update_fields.append("package_name = %s")
            update_values.append(package_update.package_name)
        
        if package_update.package_tier is not None:
            update_fields.append("package_tier = %s")
            update_values.append(package_update.package_tier)
        
        if package_update.description is not None:
            update_fields.append("description = %s")
            update_values.append(package_update.description)
        
        if package_update.price is not None:
            update_fields.append("price = %s")
            update_values.append(package_update.price)
        
        if package_update.billing_cycle is not None:
            update_fields.append("billing_cycle = %s")
            update_values.append(package_update.billing_cycle)
        
        if package_update.features is not None:
            update_fields.append("features = %s")
            update_values.append(json.dumps(package_update.features))
        
        if package_update.is_active is not None:
            update_fields.append("is_active = %s")
            update_values.append(package_update.is_active)
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Execute update
        query = f"UPDATE packages SET {', '.join(update_fields)} WHERE package_id = %s"
        update_values.append(package_id)
        
        cursor.execute(query, tuple(update_values))
        connection.commit()
        
        return {
            "status": "success",
            "message": "Package updated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update package: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@router.delete("/{package_id}", summary="Delete package (admin)")
async def delete_package(
    package_id: int,
    current_user: dict = Depends(require_admin)
):
    """Admin: Permanently delete a package"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if package exists
        cursor.execute(
            "SELECT package_id, package_name FROM packages WHERE package_id = %s",
            (package_id,)
        )
        
        package = cursor.fetchone()
        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package not found"
            )
        
        # Check if package has ANY subscriptions (active or otherwise)
        cursor.execute(
            "SELECT COUNT(*) as count FROM client_subscriptions WHERE package_id = %s",
            (package_id,)
        )
        
        result = cursor.fetchone()
        if result['count'] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete package '{package['package_name']}'. {result['count']} subscription(s) exist. Please remove all subscriptions first."
            )
        
        # Check if package is referenced in onboarding sessions
        cursor.execute(
            "SELECT COUNT(*) as count FROM onboarding_sessions WHERE selected_package_id = %s",
            (package_id,)
        )
        
        onboarding_count = cursor.fetchone()
        if onboarding_count['count'] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete package '{package['package_name']}'. {onboarding_count['count']} onboarding session(s) reference this package."
            )
        
        # HARD DELETE - Actually remove from database
        cursor.execute(
            "DELETE FROM packages WHERE package_id = %s",
            (package_id,)
        )
        
        connection.commit()
        
        return {
            "success": True,
            "message": f"Package '{package['package_name']}' deleted permanently"
        }
    
    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete package: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            

@router.get("/{package_id}", summary="Get single package")
async def get_package(
    package_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get details of a single package"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                package_id,
                package_name,
                package_tier,
                description,
                price,
                billing_cycle,
                features,
                is_active,
                created_at
            FROM packages
            WHERE package_id = %s
        """
        
        cursor.execute(query, (package_id,))
        package = cursor.fetchone()
        
        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package not found"
            )
        
        # Parse features JSON
        if package['features'] and isinstance(package['features'], str):
            package['features'] = json.loads(package['features'])
        
        return {
            "status": "success",
            "package": package
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch package: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()