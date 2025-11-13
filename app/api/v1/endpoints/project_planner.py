"""
AI Project Planner - API Endpoints
File: app/api/v1/endpoints/project_planner.py

UPDATED WITH ROLE-BASED ACCESS CONTROL
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import pymysql
from datetime import datetime
import json

from app.core.config import settings
from app.services.ai_service import AIService
from app.core.security import require_admin_or_employee, get_current_user

router = APIRouter()


# ========== PYDANTIC MODELS ==========

class ProjectInput(BaseModel):
    """Lead/Prospect project discovery input"""
    lead_name: str = Field(..., min_length=2, max_length=255)
    lead_email: str = Field(..., min_length=3)
    company_name: str = Field(..., min_length=2, max_length=255)
    business_type: str = Field(..., min_length=2, max_length=100)
    budget: float = Field(..., gt=0)
    challenges: str = Field(..., min_length=10)
    target_audience: str = Field(..., min_length=10)
    existing_presence: Dict = Field(default_factory=dict)


class ProposalUpdate(BaseModel):
    """Update proposal content"""
    ai_generated_strategy: Optional[Dict] = None
    competitive_differentiators: Optional[Dict] = None
    suggested_timeline: Optional[Dict] = None
    status: Optional[str] = None


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
    Generate AI-powered project proposal based on client inputs
    
    **Access**: Admin and Employee only
    """
    connection = None
    cursor = None
    
    try:
        # Initialize AI Service
        ai_service = AIService()
        
        # Generate AI Strategy
        strategy_prompt = f"""
        Generate a comprehensive digital marketing strategy for:
        
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
        
        timeline = await ai_service.generate_timeline(timeline_prompt)
        
        # Save to Database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        insert_query = """
            INSERT INTO project_proposals 
            (client_id, created_by, business_type, budget, challenges, 
             target_audience, existing_presence, ai_generated_strategy, 
             competitive_differentiators, suggested_timeline, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            project_input.client_id,
            current_user['user_id'],  # Use authenticated user ID
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
    client_id: Optional[int] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get all proposals, optionally filtered by client
    
    **Access**: Admin and Employee only
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        if client_id:
            query = """
                SELECT p.*, u.full_name as client_name, u.email as client_email
                FROM project_proposals p
                JOIN users u ON p.client_id = u.user_id
                WHERE p.client_id = %s
                ORDER BY p.created_at DESC
            """
            cursor.execute(query, (client_id,))
        else:
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
            
            # Parse JSON fields
            if proposal['existing_presence']:
                proposal['existing_presence'] = json.loads(proposal['existing_presence'])
            if proposal['ai_generated_strategy']:
                proposal['ai_generated_strategy'] = json.loads(proposal['ai_generated_strategy'])
            if proposal['competitive_differentiators']:
                proposal['competitive_differentiators'] = json.loads(proposal['competitive_differentiators'])
            if proposal['suggested_timeline']:
                proposal['suggested_timeline'] = json.loads(proposal['suggested_timeline'])
        
        return {
            "success": True,
            "proposals": proposals,
            "total": len(proposals)
        }
    
    except Exception as e:
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
    """
    Get specific proposal details
    
    **Access**: Admin and Employee only
    """
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
        
        # Convert datetime and JSON
        if proposal['created_at']:
            proposal['created_at'] = proposal['created_at'].isoformat()
        if proposal['updated_at']:
            proposal['updated_at'] = proposal['updated_at'].isoformat()
        if proposal['sent_at']:
            proposal['sent_at'] = proposal['sent_at'].isoformat()
        
        if proposal['existing_presence']:
            proposal['existing_presence'] = json.loads(proposal['existing_presence'])
        if proposal['ai_generated_strategy']:
            proposal['ai_generated_strategy'] = json.loads(proposal['ai_generated_strategy'])
        if proposal['competitive_differentiators']:
            proposal['competitive_differentiators'] = json.loads(proposal['competitive_differentiators'])
        if proposal['suggested_timeline']:
            proposal['suggested_timeline'] = json.loads(proposal['suggested_timeline'])
        
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


@router.put("/proposals/{proposal_id}")
async def update_proposal(
    proposal_id: int,
    update_data: ProposalUpdate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Update proposal content (edit draft)
    
    **Access**: Admin and Employee only
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if proposal exists
        cursor.execute(
            "SELECT proposal_id FROM project_proposals WHERE proposal_id = %s",
            (proposal_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )
        
        # Build update query
        update_fields = []
        values = []
        
        if update_data.ai_generated_strategy:
            update_fields.append("ai_generated_strategy = %s")
            values.append(json.dumps(update_data.ai_generated_strategy))
        
        if update_data.competitive_differentiators:
            update_fields.append("competitive_differentiators = %s")
            values.append(json.dumps(update_data.competitive_differentiators))
        
        if update_data.suggested_timeline:
            update_fields.append("suggested_timeline = %s")
            values.append(json.dumps(update_data.suggested_timeline))
        
        if update_data.status:
            if update_data.status not in ['draft', 'sent', 'accepted', 'rejected']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid status"
                )
            update_fields.append("status = %s")
            values.append(update_data.status)
            
            if update_data.status == 'sent':
                update_fields.append("sent_at = NOW()")
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_fields.append("updated_at = NOW()")
        values.append(proposal_id)
        
        query = f"UPDATE project_proposals SET {', '.join(update_fields)} WHERE proposal_id = %s"
        cursor.execute(query, values)
        connection.commit()
        
        return {
            "success": True,
            "message": "Proposal updated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update proposal: {str(e)}"
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
    """
    Mark proposal as sent to client
    
    **Access**: Admin and Employee only
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if proposal exists
        cursor.execute(
            "SELECT client_id FROM project_proposals WHERE proposal_id = %s",
            (proposal_id,)
        )
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )
        
        # Update status to sent
        cursor.execute(
            "UPDATE project_proposals SET status = 'sent', sent_at = NOW() WHERE proposal_id = %s",
            (proposal_id,)
        )
        connection.commit()
        
        return {
            "success": True,
            "message": "Proposal sent to client successfully"
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


@router.delete("/proposals/{proposal_id}")
async def delete_proposal(
    proposal_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Delete a proposal permanently
    
    **Access**: Admin and Employee only
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if proposal exists
        cursor.execute(
            "SELECT proposal_id FROM project_proposals WHERE proposal_id = %s",
            (proposal_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )
        
        # Delete proposal
        cursor.execute(
            "DELETE FROM project_proposals WHERE proposal_id = %s",
            (proposal_id,)
        )
        connection.commit()
        
        return {
            "success": True,
            "message": "Proposal deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete proposal: {str(e)}"
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
    """
    Export proposal as PDF
    Note: This endpoint returns the data needed for PDF generation
    Actual PDF generation would be done client-side or using a library like ReportLab
    
    **Access**: Admin and Employee only
    """
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
        
        # Format data for PDF export
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
            "export_data": export_data,
            "message": "Proposal data ready for PDF export"
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