"""
AI Project Planner - API Endpoints
COPY THIS ENTIRE FILE to: app/api/v1/endpoints/project_planner.py
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict
import pymysql
import json

from app.core.config import settings
from app.services.ai_service import AIService
from app.core.security import require_admin_or_employee

router = APIRouter()


# ========== PYDANTIC MODELS ==========

class ProjectInput(BaseModel):
    """Lead/Prospect project discovery input - NO client_id needed"""
    lead_name: str = Field(..., min_length=2, max_length=255, description="Lead's full name")
    lead_email: EmailStr = Field(..., description="Lead's email address")
    company_name: str = Field(..., min_length=2, max_length=255, description="Company name")
    business_type: str = Field(..., min_length=2, max_length=100, description="Type of business")
    budget: float = Field(..., gt=0, description="Marketing budget in USD")
    challenges: str = Field(..., min_length=10, description="Current marketing challenges")
    target_audience: str = Field(..., min_length=10, description="Target audience description")
    existing_presence: Dict = Field(default_factory=dict, description="Existing digital presence")


# ========== DATABASE CONNECTION ==========

def get_db_connection():
    """Get MySQL database connection"""
    try:
        connection = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {str(e)}"
        )


# ========== API ENDPOINTS ==========

@router.post("/generate-proposal")
async def generate_proposal(
    project_input: ProjectInput,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Generate AI-powered project proposal for a lead/prospect
    
    **Access**: Admin and Employee only
    
    **Request Body**:
    - lead_name: Lead's full name
    - lead_email: Lead's email
    - company_name: Company name
    - business_type: Type of business (e.g., E-commerce, SaaS)
    - budget: Marketing budget in USD
    - challenges: Current marketing challenges
    - target_audience: Target audience description
    - existing_presence: Dict with platforms list
    """
    connection = None
    cursor = None
    
    try:
        print(f"[PROPOSAL] === Received Request ===")
        print(f"[PROPOSAL] Lead: {project_input.lead_name} ({project_input.lead_email})")
        print(f"[PROPOSAL] Company: {project_input.company_name}")
        print(f"[PROPOSAL] Business Type: {project_input.business_type}")
        print(f"[PROPOSAL] Budget: ${project_input.budget}")
        print(f"[PROPOSAL] User: {current_user.get('email', 'Unknown')} (ID: {current_user.get('user_id', 'Unknown')})")
        print(f"[PROPOSAL] Starting generation for: {project_input.lead_email}")
        
        # Initialize AI Service
        ai_service = AIService()
        
        # Generate AI Strategy
        strategy_prompt = f"""
        Generate a comprehensive digital marketing strategy for:
        
        Company: {project_input.company_name}
        Business Type: {project_input.business_type}
        Budget: ${project_input.budget}
        Challenges: {project_input.challenges}
        Target Audience: {project_input.target_audience}
        Current Presence: {json.dumps(project_input.existing_presence)}
        
        Provide a detailed strategy including:
        1. Recommended campaigns (paid ads, email, SEO, social media)
        2. Platform recommendations with justification
        3. Creative formats and content types
        4. Automation tools to leverage
        5. Expected timeline and milestones
        6. Key performance indicators (KPIs)
        
        Format as JSON with clear sections.
        """
        
        print("[PROPOSAL] Generating AI strategy...")
        ai_strategy = await ai_service.generate_strategy(strategy_prompt)
        
        # Generate Competitive Differentiators
        differentiator_prompt = f"""
        Based on this project:
        Business: {project_input.business_type}
        Budget: ${project_input.budget}
        
        Highlight competitive differentiators that our agency offers:
        - Faster deployment with automation
        - AI-personalized targeting
        - Hybrid online-offline approach
        - Cost-efficiency via optimized media spend
        - Advanced performance tracking with predictive insights
        
        Make it compelling and specific to this client's needs.
        Format as JSON.
        """
        
        print("[PROPOSAL] Generating differentiators...")
        differentiators = await ai_service.generate_differentiators(differentiator_prompt)
        
        # Generate Timeline
        timeline_prompt = f"""
        Create a realistic project timeline for:
        Budget: ${project_input.budget}
        Strategy: {json.dumps(ai_strategy)}
        
        Include:
        - Phase-wise breakdown
        - Milestones with dates
        - Deliverables per phase
        - Expected results timeline
        
        Format as JSON with phases and dates.
        """
        
        print("[PROPOSAL] Generating timeline...")
        timeline = await ai_service.generate_timeline(timeline_prompt)
        
        # Save to Database
        print("[PROPOSAL] Saving to database...")
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if lead exists as user
        check_lead = "SELECT user_id FROM users WHERE email = %s"
        cursor.execute(check_lead, (project_input.lead_email,))
        lead_user = cursor.fetchone()
        
        if not lead_user:
            # Create a pending user record for the lead
            print(f"[PROPOSAL] Creating new lead user: {project_input.lead_email}")
            insert_lead = """
                INSERT INTO users (email, password_hash, full_name, role, status)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_lead, (
                project_input.lead_email,
                '',  # No password yet
                project_input.lead_name,
                'client',
                'pending'
            ))
            connection.commit()
            lead_user_id = cursor.lastrowid
            print(f"[PROPOSAL] Created lead user with ID: {lead_user_id}")
        else:
            lead_user_id = lead_user['user_id']
            print(f"[PROPOSAL] Using existing user ID: {lead_user_id}")
        
        # Insert the proposal
        insert_query = """
            INSERT INTO project_proposals 
            (client_id, created_by, business_type, budget, challenges, 
             target_audience, existing_presence, ai_generated_strategy, 
             competitive_differentiators, suggested_timeline, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            lead_user_id,
            current_user['user_id'],
            project_input.business_type,
            project_input.budget,
            project_input.challenges,
            project_input.target_audience,
            json.dumps(project_input.existing_presence),
            json.dumps(ai_strategy),
            json.dumps(differentiators),
            json.dumps(timeline),
            'draft'
        ))
        
        connection.commit()
        proposal_id = cursor.lastrowid
        
        print(f"[PROPOSAL] ✅ Success! Proposal ID: {proposal_id}")
        
        return {
            "success": True,
            "message": "Project proposal generated successfully",
            "proposal_id": proposal_id,
            "data": {
                "strategy": ai_strategy,
                "differentiators": differentiators,
                "timeline": timeline
            }
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"[PROPOSAL] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate proposal: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/proposals/list")
async def list_proposals(
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get all proposals - Admin and Employee only"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT p.*, u.full_name as client_name, u.email as client_email
            FROM project_proposals p
            JOIN users u ON p.client_id = u.user_id
            ORDER BY p.created_at DESC
        """
        cursor.execute(query)
        proposals = cursor.fetchall()
        
        # Convert datetime and JSON fields
        for proposal in proposals:
            if proposal['created_at']:
                proposal['created_at'] = proposal['created_at'].isoformat()
            if proposal['updated_at']:
                proposal['updated_at'] = proposal['updated_at'].isoformat()
            if proposal['sent_at']:
                proposal['sent_at'] = proposal['sent_at'].isoformat()
            
            # Parse JSON fields safely
            for json_field in ['existing_presence', 'ai_generated_strategy', 
                             'competitive_differentiators', 'suggested_timeline']:
                if proposal[json_field]:
                    try:
                        proposal[json_field] = json.loads(proposal[json_field])
                    except:
                        proposal[json_field] = {}
        
        return {
            "success": True,
            "proposals": proposals,
            "total": len(proposals)
        }
    
    except Exception as e:
        print(f"Error fetching proposals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch proposals: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get specific proposal details"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT p.*, 
                   u.full_name as client_name, 
                   u.email as client_email,
                   u.phone as client_phone
            FROM project_proposals p
            JOIN users u ON p.client_id = u.user_id
            WHERE p.proposal_id = %s
        """
        cursor.execute(query, (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )
        
        # Convert datetime
        for date_field in ['created_at', 'updated_at', 'sent_at']:
            if proposal[date_field]:
                proposal[date_field] = proposal[date_field].isoformat()
        
        # Parse JSON fields
        for json_field in ['existing_presence', 'ai_generated_strategy', 
                         'competitive_differentiators', 'suggested_timeline']:
            if proposal[json_field]:
                try:
                    proposal[json_field] = json.loads(proposal[json_field])
                except:
                    proposal[json_field] = {}
        
        return {
            "success": True,
            "proposal": proposal
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch proposal: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/proposals/{proposal_id}/send")
async def send_proposal(
    proposal_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Mark proposal as sent to lead"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(
            "UPDATE project_proposals SET status = 'sent', sent_at = NOW() WHERE proposal_id = %s",
            (proposal_id,)
        )
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Proposal sent successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send proposal: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/proposals/{proposal_id}/export")
async def export_proposal_pdf(
    proposal_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Export proposal data for PDF generation"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT p.*, 
                   u.full_name as client_name, 
                   u.email as client_email,
                   u.phone as client_phone
            FROM project_proposals p
            JOIN users u ON p.client_id = u.user_id
            WHERE p.proposal_id = %s
        """
        cursor.execute(query, (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )
        
        export_data = {
            "proposal_id": proposal['proposal_id'],
            "client_name": proposal['client_name'],
            "client_email": proposal['client_email'],
            "client_phone": proposal['client_phone'],
            "business_type": proposal['business_type'],
            "budget": float(proposal['budget']),
            "challenges": proposal['challenges'],
            "target_audience": proposal['target_audience'],
            "strategy": json.loads(proposal['ai_generated_strategy']) if proposal['ai_generated_strategy'] else {},
            "differentiators": json.loads(proposal['competitive_differentiators']) if proposal['competitive_differentiators'] else {},
            "timeline": json.loads(proposal['suggested_timeline']) if proposal['suggested_timeline'] else {},
            "created_at": proposal['created_at'].isoformat() if proposal['created_at'] else None
        }
        
        return {
            "success": True,
            "export_data": export_data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export proposal: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()