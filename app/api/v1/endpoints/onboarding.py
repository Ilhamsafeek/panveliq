"""
Onboarding API Endpoints - FIXED VERSION WITH ERROR HANDLING
Replace your current app/api/v1/endpoints/onboarding.py with this
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, date, timedelta
import pymysql
from pymysql import Error
import json
import traceback

from app.core.config import settings
from app.core.security import get_current_user
from app.core.security import get_db_connection


router = APIRouter()


# ============================================
# PYDANTIC MODELS
# ============================================

class Package(BaseModel):
    package_id: Optional[int] = None
    package_name: str
    package_tier: str
    description: str
    price: float
    billing_cycle: str
    features: dict
    is_active: bool = True

class PackageSelect(BaseModel):
    package_id: int

class OnboardingSession(BaseModel):
    onboarding_id: Optional[int] = None
    user_id: int
    selected_package_id: Optional[int] = None
    verification_data: Optional[dict] = None
    verification_status: str = 'pending'
    discussion_notes: Optional[str] = None

class VerificationUpdate(BaseModel):
    verification_status: str
    discussion_notes: Optional[str] = None

class SubscriptionCreate(BaseModel):
    client_id: int
    package_id: int
    start_date: date
    end_date: date

# ============================================
# PACKAGE ENDPOINTS
# ============================================

@router.get("/packages", summary="Get all active packages")
async def get_packages():
    """
    Retrieve all active packages for selection
    """
    connection = None
    cursor = None
    
    try:
        print("🔍 Attempting to fetch packages...")
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # First check if table exists
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = 'packages'
        """, (settings.DB_NAME,))
        
        table_check = cursor.fetchone()
        if table_check['count'] == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Packages table does not exist. Please run database migrations."
            )
        
        # Fetch packages
        query = """
            SELECT 
                package_id, 
                package_name, 
                package_tier, 
                description, 
                price, 
                billing_cycle, 
                features, 
                is_active
            FROM packages
            WHERE is_active = TRUE
            ORDER BY 
                CASE package_tier
                    WHEN 'basic' THEN 1
                    WHEN 'professional' THEN 2
                    WHEN 'enterprise' THEN 3
                END
        """
        
        cursor.execute(query)
        packages = cursor.fetchall()
        
        print(f"✅ Found {len(packages)} packages")
        
        if len(packages) == 0:
            return {
                "status": "success",
                "packages": [],
                "message": "No packages found. Please run the seed data script."
            }
        
        # Parse JSON features field
        for package in packages:
            if package.get('features'):
                try:
                    if isinstance(package['features'], str):
                        package['features'] = json.loads(package['features'])
                except json.JSONDecodeError as e:
                    print(f"⚠️ Warning: Invalid JSON in features for package {package['package_id']}")
                    package['features'] = {}
        
        return {
            "status": "success",
            "packages": packages,
            "count": len(packages)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching packages: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve packages: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@router.get("/packages/{package_id}", summary="Get specific package details")
async def get_package_by_id(package_id: int):
    """
    Retrieve specific package details
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT package_id, package_name, package_tier, description, 
                   price, billing_cycle, features, is_active
            FROM packages
            WHERE package_id = %s AND is_active = TRUE
        """
        
        cursor.execute(query, (package_id,))
        package = cursor.fetchone()
        
        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package not found"
            )
        
        # Parse JSON features
        if package.get('features'):
            try:
                if isinstance(package['features'], str):
                    package['features'] = json.loads(package['features'])
            except json.JSONDecodeError:
                package['features'] = {}
        
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
            detail=f"Failed to retrieve package: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# ============================================
# ONBOARDING SESSION ENDPOINTS
# ============================================

@router.post("/select-package", status_code=status.HTTP_201_CREATED, summary="Select package during onboarding")
async def select_package(
    package_select: PackageSelect,
    current_user: dict = Depends(get_current_user)
):
    """
    Client selects a package during onboarding
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify package exists
        cursor.execute(
            "SELECT package_id FROM packages WHERE package_id = %s AND is_active = TRUE", 
            (package_select.package_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package not found"
            )
        
        # Check if onboarding session exists
        cursor.execute(
            "SELECT onboarding_id FROM onboarding_sessions WHERE user_id = %s",
            (current_user['user_id'],)
        )
        existing_session = cursor.fetchone()
        
        if existing_session:
            # Update existing
            cursor.execute(
                "UPDATE onboarding_sessions SET selected_package_id = %s WHERE user_id = %s",
                (package_select.package_id, current_user['user_id'])
            )
            onboarding_id = existing_session['onboarding_id']
        else:
            # Create new
            cursor.execute(
                "INSERT INTO onboarding_sessions (user_id, selected_package_id, verification_status) VALUES (%s, %s, 'pending')",
                (current_user['user_id'], package_select.package_id)
            )
            onboarding_id = cursor.lastrowid
        
        connection.commit()
        
        return {
            "status": "success",
            "message": "Package selected successfully",
            "onboarding_id": onboarding_id,
            "package_id": package_select.package_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to select package: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@router.get("/my-onboarding", summary="Get current user's onboarding status")
async def get_my_onboarding(current_user: dict = Depends(get_current_user)):
    """
    Retrieve current user's onboarding session details
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                os.onboarding_id,
                os.user_id,
                os.selected_package_id,
                os.verification_data,
                os.verification_status,
                os.discussion_notes,
                os.verified_by,
                os.verified_at,
                os.created_at,
                p.package_name,
                p.package_tier,
                p.price,
                p.billing_cycle,
                u_verifier.full_name as verified_by_name
            FROM onboarding_sessions os
            LEFT JOIN packages p ON os.selected_package_id = p.package_id
            LEFT JOIN users u_verifier ON os.verified_by = u_verifier.user_id
            WHERE os.user_id = %s
        """
        
        cursor.execute(query, (current_user['user_id'],))
        session = cursor.fetchone()
        
        if not session:
            return {
                "status": "success",
                "onboarding_session": None,
                "message": "No onboarding session found"
            }
        
        # Parse JSON
        if session.get('verification_data'):
            try:
                if isinstance(session['verification_data'], str):
                    session['verification_data'] = json.loads(session['verification_data'])
            except:
                session['verification_data'] = {}
        
        return {
            "status": "success",
            "onboarding_session": session
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve onboarding session: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@router.post("/submit-verification", summary="Submit verification data")
async def submit_verification_data(
    verification_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Client submits business verification data
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        verification_json = json.dumps(verification_data)
        
        cursor.execute(
            "UPDATE onboarding_sessions SET verification_data = %s, verification_status = 'pending' WHERE user_id = %s",
            (verification_json, current_user['user_id'])
        )
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding session not found. Please select a package first."
            )
        
        connection.commit()
        
        return {
            "status": "success",
            "message": "Verification data submitted successfully. Awaiting admin review."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit verification data: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# ============================================
# ADMIN ENDPOINTS
# ============================================

@router.get("/pending-verifications", summary="Get pending verifications (Admin)")
async def get_pending_verifications(current_user: dict = Depends(get_current_user)):
    """
    Admin retrieves pending onboarding sessions
    """
    if current_user['role'] != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access pending verifications"
        )
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                os.onboarding_id,
                os.user_id,
                os.selected_package_id,
                os.verification_data,
                os.verification_status,
                os.discussion_notes,
                os.created_at,
                u.full_name,
                u.email,
                u.phone,
                p.package_name,
                p.package_tier,
                p.price,
                p.billing_cycle
            FROM onboarding_sessions os
            INNER JOIN users u ON os.user_id = u.user_id
            LEFT JOIN packages p ON os.selected_package_id = p.package_id
            WHERE os.verification_status = 'pending'
            ORDER BY os.created_at ASC
        """
        
        cursor.execute(query)
        sessions = cursor.fetchall()
        
        # Parse JSON
        for session in sessions:
            if session.get('verification_data'):
                try:
                    if isinstance(session['verification_data'], str):
                        session['verification_data'] = json.loads(session['verification_data'])
                except:
                    session['verification_data'] = {}
        
        return {
            "status": "success",
            "pending_verifications": sessions,
            "count": len(sessions)
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pending verifications: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/verify/{onboarding_id}", summary="Verify onboarding (Admin)")
async def verify_onboarding(
    onboarding_id: int,
    verification: VerificationUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Admin verifies or rejects onboarding
    - Verified: Creates subscription, activates user (status = 'active')
    - Rejected: Sets user status to 'inactive'
    """
    if current_user['role'] != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can verify onboarding"
        )
    
    if verification.verification_status not in ['verified', 'rejected']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be 'verified' or 'rejected'"
        )
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get onboarding session
        cursor.execute(
            "SELECT * FROM onboarding_sessions WHERE onboarding_id = %s",
            (onboarding_id,)
        )
        session = cursor.fetchone()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding session not found"
            )
        
        # Update onboarding session
        cursor.execute(
            """UPDATE onboarding_sessions 
               SET verification_status = %s, 
                   discussion_notes = %s, 
                   verified_by = %s, 
                   verified_at = NOW()
               WHERE onboarding_id = %s""",
            (verification.verification_status, verification.discussion_notes, 
             current_user['user_id'], onboarding_id)
        )
        
        # Handle approval vs rejection
        if verification.verification_status == 'verified':
            # APPROVAL: Create subscription and activate user
            
            # Get package billing cycle
            cursor.execute(
                "SELECT billing_cycle FROM packages WHERE package_id = %s",
                (session['selected_package_id'],)
            )
            package = cursor.fetchone()
            
            # Calculate subscription dates based on billing cycle
            start_date = datetime.now().date()
            
            if package and package['billing_cycle'] == 'monthly':
                end_date = start_date + timedelta(days=30)
            elif package and package['billing_cycle'] == 'quarterly':
                end_date = start_date + timedelta(days=90)
            elif package and package['billing_cycle'] == 'yearly':
                end_date = start_date + timedelta(days=365)
            else:
                end_date = start_date + timedelta(days=30)  # Default to monthly
            
            # Create subscription
            cursor.execute(
                """INSERT INTO client_subscriptions (client_id, package_id, start_date, end_date, status)
                   VALUES (%s, %s, %s, %s, 'active')""",
                (session['user_id'], session['selected_package_id'], start_date, end_date)
            )
            
            # Activate user
            cursor.execute(
                "UPDATE users SET status = 'active' WHERE user_id = %s", 
                (session['user_id'],)
            )
            
            print(f"✅ User {session['user_id']} APPROVED - Status set to 'active'")
            
        else:
            # REJECTION: Set user status to 'inactive'
            cursor.execute(
                "UPDATE users SET status = 'inactive' WHERE user_id = %s", 
                (session['user_id'],)
            )
            
            print(f"❌ User {session['user_id']} REJECTED - Status set to 'inactive'")
        
        connection.commit()
        
        return {
            "success": True,
            "status": "success",
            "message": f"Onboarding {verification.verification_status} successfully",
            "onboarding_id": onboarding_id,
            "user_status": "active" if verification.verification_status == 'verified' else "inactive"
        }
        
    except HTTPException:
        if connection:
            connection.rollback()
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify onboarding: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/onboarding/{onboarding_id}", summary="Get onboarding details (Admin)")
async def get_onboarding_details(
    onboarding_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed onboarding information
    """
    if current_user['role'] != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view onboarding details"
        )
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                os.*,
                u.full_name,
                u.email,
                u.phone,
                u.status as user_status,
                p.package_name,
                p.package_tier,
                p.description,
                p.price,
                p.billing_cycle,
                p.features,
                u_verifier.full_name as verified_by_name
            FROM onboarding_sessions os
            INNER JOIN users u ON os.user_id = u.user_id
            LEFT JOIN packages p ON os.selected_package_id = p.package_id
            LEFT JOIN users u_verifier ON os.verified_by = u_verifier.user_id
            WHERE os.onboarding_id = %s
        """
        
        cursor.execute(query, (onboarding_id,))
        session = cursor.fetchone()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Onboarding session not found"
            )
        
        # Parse JSON
        for field in ['verification_data', 'features']:
            if session.get(field):
                try:
                    if isinstance(session[field], str):
                        session[field] = json.loads(session[field])
                except:
                    session[field] = {}
        
        return {
            "status": "success",
            "onboarding_session": session
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve onboarding details: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()