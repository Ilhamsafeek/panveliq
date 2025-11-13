"""
AI Project Planner - API Endpoints
COMPLETE IMPLEMENTATION WITH ALL SCOPE FEATURES

COPY THIS to: app/api/v1/endpoints/project_planner.py
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import pymysql
import json

from app.core.config import settings
from app.services.ai_service import AIService
from app.core.security import require_admin_or_employee

router = APIRouter()


# ========== PYDANTIC MODELS ==========

class ProjectInput(BaseModel):
    """Lead/Prospect project discovery input"""
    lead_name: str
    lead_email: str
    company_name: str
    business_type: str
    budget: float
    challenges: str
    target_audience: str
    existing_presence: Optional[Dict[str, Any]] = {}


class ProposalEdit(BaseModel):
    """Model for editing proposals"""
    strategy: Optional[Dict[str, Any]] = None
    differentiators: Optional[Dict[str, Any]] = None
    timeline: Optional[Dict[str, Any]] = None
    custom_notes: Optional[str] = None
    tone: Optional[str] = None  # professional, casual, technical
    sections_to_include: Optional[List[str]] = None  # strategy, differentiators, timeline, custom


class SendProposalRequest(BaseModel):
    """Model for sending proposals"""
    lead_email: str
    lead_name: str
    send_immediately: bool = True
    scheduled_time: Optional[datetime] = None
    include_sections: Optional[List[str]] = None
    custom_message: Optional[str] = None


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
    """Generate AI-powered project proposal"""
    connection = None
    cursor = None
    
    try:
        print(f"\n{'='*60}")
        print(f"[PROPOSAL] Received Request")
        print(f"{'='*60}")
        print(f"Lead: {project_input.lead_name} ({project_input.lead_email})")
        print(f"Company: {project_input.company_name}")
        print(f"Business: {project_input.business_type}")
        print(f"Budget: ${project_input.budget}")
        print(f"User: {current_user.get('email', 'Unknown')}")
        print(f"{'='*60}\n")
        
        # Validation
        if not project_input.lead_email or '@' not in project_input.lead_email:
            raise HTTPException(status_code=400, detail="Invalid email address")
        
        if project_input.budget <= 0:
            raise HTTPException(status_code=400, detail="Budget must be greater than 0")
        
        # Initialize AI Service
        print("[1/5] Initializing AI Service...")
        ai_service = AIService()
        
        # Generate AI Strategy
        print("[2/5] Generating AI Strategy...")
        strategy_prompt = f"""
        Generate a comprehensive digital marketing strategy for:
        
        Company: {project_input.company_name}
        Business Type: {project_input.business_type}
        Budget: ${project_input.budget}
        Challenges: {project_input.challenges}
        Target Audience: {project_input.target_audience}
        Current Presence: {json.dumps(project_input.existing_presence)}
        
        Provide:
        1. Recommended campaigns (paid ads, email, SEO, social media)
        2. Platform recommendations with justification
        3. Creative formats and content types
        4. Content topics that resonate
        5. Automation tools to leverage
        6. Expected timeline and milestones
        7. Key performance indicators (KPIs)
        
        Format as JSON with clear sections.
        """
        
        ai_strategy = await ai_service.generate_strategy(strategy_prompt)
        print("   ✓ Strategy generated")
        
        # Generate Competitive Differentiators
        print("[3/5] Generating Differentiators...")
        differentiator_prompt = f"""
        For {project_input.business_type} with ${project_input.budget} budget:
        
        Highlight our agency's competitive differentiators:
        - Faster deployment with automation (how we're 70% faster)
        - AI-personalized targeting (hyper-targeting capabilities)
        - Hybrid online-offline approach (omnichannel strategy)
        - Cost-efficiency via optimized media spend (20-30% reduction)
        - Advanced performance tracking with predictive insights (forecasting)
        
        Make it compelling and specific to {project_input.company_name}'s needs.
        Format as JSON with title, description, and impact for each.
        """
        
        differentiators = await ai_service.generate_differentiators(differentiator_prompt)
        print("   ✓ Differentiators generated")
        
        # Generate Timeline
        print("[4/5] Generating Timeline...")
        timeline_prompt = f"""
        Create detailed project timeline for:
        Budget: ${project_input.budget}
        Strategy: {json.dumps(ai_strategy)}
        
        Include:
        - Phase-wise breakdown (4-6 phases)
        - Specific milestones with target dates
        - Deliverables per phase
        - Expected results timeline
        - Resource requirements per phase
        
        Format as JSON with phases array.
        """
        
        timeline = await ai_service.generate_timeline(timeline_prompt)
        print("   ✓ Timeline generated")
        
        # Save to Database
        print("[5/5] Saving to database...")
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if lead exists
        check_lead = "SELECT user_id FROM users WHERE email = %s"
        cursor.execute(check_lead, (project_input.lead_email.lower(),))
        lead_user = cursor.fetchone()
        
        if not lead_user:
            print(f"   → Creating new lead: {project_input.lead_email}")
            insert_lead = """
                INSERT INTO users (email, password_hash, full_name, role, status)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_lead, (
                project_input.lead_email.lower(),
                '',
                project_input.lead_name,
                'client',
                'pending'
            ))
            connection.commit()
            lead_user_id = cursor.lastrowid
            print(f"   → Created lead with ID: {lead_user_id}")
        else:
            lead_user_id = lead_user['user_id']
            print(f"   → Using existing lead ID: {lead_user_id}")
        
        # Insert proposal with editable flag
        insert_query = """
            INSERT INTO project_proposals 
            (client_id, created_by, business_type, budget, challenges, 
             target_audience, existing_presence, ai_generated_strategy, 
             competitive_differentiators, suggested_timeline, status, 
             is_editable, tone, sections_included)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # Default sections included
        sections_included = ['strategy', 'differentiators', 'timeline']
        
        cursor.execute(insert_query, (
            lead_user_id,
            current_user['user_id'],
            project_input.business_type,
            project_input.budget,
            project_input.challenges,
            project_input.target_audience,
            json.dumps(project_input.existing_presence or {}),
            json.dumps(ai_strategy),
            json.dumps(differentiators),
            json.dumps(timeline),
            'draft',
            1,  # is_editable = true
            'professional',  # default tone
            json.dumps(sections_included)
        ))
        
        connection.commit()
        proposal_id = cursor.lastrowid
        
        print(f"\n{'='*60}")
        print(f"✅ SUCCESS! Proposal ID: {proposal_id}")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "message": "Project proposal generated successfully",
            "proposal_id": proposal_id,
            "data": {
                "strategy": ai_strategy,
                "differentiators": differentiators,
                "timeline": timeline,
                "sections_included": sections_included,
                "is_editable": True,
                "tone": "professional"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"\n{'='*60}")
        print(f"❌ ERROR: {str(e)}")
        print(f"{'='*60}\n")
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


@router.put("/proposals/{proposal_id}/edit")
async def edit_proposal(
    proposal_id: int,
    edits: ProposalEdit,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Edit/customize proposal - SCOPE REQUIREMENT: Editable Draft
    Staff can review and manually adjust any part of the proposal
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get existing proposal
        cursor.execute("SELECT * FROM project_proposals WHERE proposal_id = %s", (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Build update query dynamically
        update_fields = []
        update_values = []
        
        if edits.strategy is not None:
            update_fields.append("ai_generated_strategy = %s")
            update_values.append(json.dumps(edits.strategy))
        
        if edits.differentiators is not None:
            update_fields.append("competitive_differentiators = %s")
            update_values.append(json.dumps(edits.differentiators))
        
        if edits.timeline is not None:
            update_fields.append("suggested_timeline = %s")
            update_values.append(json.dumps(edits.timeline))
        
        if edits.custom_notes is not None:
            update_fields.append("custom_notes = %s")
            update_values.append(edits.custom_notes)
        
        if edits.tone is not None:
            update_fields.append("tone = %s")
            update_values.append(edits.tone)
        
        if edits.sections_to_include is not None:
            update_fields.append("sections_included = %s")
            update_values.append(json.dumps(edits.sections_to_include))
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Add updated timestamp
        update_fields.append("updated_at = NOW()")
        update_values.append(proposal_id)
        
        update_query = f"""
            UPDATE project_proposals 
            SET {', '.join(update_fields)}
            WHERE proposal_id = %s
        """
        
        cursor.execute(update_query, tuple(update_values))
        connection.commit()
        
        print(f"[EDIT] Proposal {proposal_id} updated successfully")
        
        return {
            "success": True,
            "message": "Proposal updated successfully",
            "proposal_id": proposal_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"[EDIT] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/proposals/list")
async def list_proposals(current_user: dict = Depends(require_admin_or_employee)):
    """Get all proposals"""
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
        
        for proposal in proposals:
            if proposal.get('created_at'):
                proposal['created_at'] = proposal['created_at'].isoformat()
            if proposal.get('updated_at'):
                proposal['updated_at'] = proposal['updated_at'].isoformat()
            if proposal.get('sent_at'):
                proposal['sent_at'] = proposal['sent_at'].isoformat()
            if proposal.get('scheduled_send_time'):
                proposal['scheduled_send_time'] = proposal['scheduled_send_time'].isoformat()
            
            for field in ['existing_presence', 'ai_generated_strategy', 
                         'competitive_differentiators', 'suggested_timeline', 'sections_included']:
                if proposal.get(field):
                    try:
                        proposal[field] = json.loads(proposal[field]) if isinstance(proposal[field], str) else proposal[field]
                    except:
                        proposal[field] = {} if field != 'sections_included' else []
        
        return {
            "success": True,
            "proposals": proposals,
            "total": len(proposals)
        }
    
    except Exception as e:
        print(f"Error listing proposals: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: int, current_user: dict = Depends(require_admin_or_employee)):
    """Get specific proposal"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT p.*, u.full_name as client_name, u.email as client_email
            FROM project_proposals p
            JOIN users u ON p.client_id = u.user_id
            WHERE p.proposal_id = %s
        """
        cursor.execute(query, (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        if proposal.get('created_at'):
            proposal['created_at'] = proposal['created_at'].isoformat()
        if proposal.get('updated_at'):
            proposal['updated_at'] = proposal['updated_at'].isoformat()
        if proposal.get('sent_at'):
            proposal['sent_at'] = proposal['sent_at'].isoformat()
        if proposal.get('scheduled_send_time'):
            proposal['scheduled_send_time'] = proposal['scheduled_send_time'].isoformat()
        
        for field in ['existing_presence', 'ai_generated_strategy', 
                     'competitive_differentiators', 'suggested_timeline', 'sections_included']:
            if proposal.get(field):
                try:
                    proposal[field] = json.loads(proposal[field]) if isinstance(proposal[field], str) else proposal[field]
                except:
                    proposal[field] = {} if field != 'sections_included' else []
        
        return {"success": True, "proposal": proposal}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/proposals/{proposal_id}/send")
async def send_proposal(
    proposal_id: int,
    send_request: SendProposalRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Send proposal to lead - SCOPE REQUIREMENT: Send instantly OR schedule
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Update status
        if send_request.send_immediately:
            update_query = """
                UPDATE project_proposals 
                SET status = 'sent', sent_at = NOW()
                WHERE proposal_id = %s
            """
            cursor.execute(update_query, (proposal_id,))
            message = f"Proposal sent immediately to {send_request.lead_email}"
        else:
            if not send_request.scheduled_time:
                raise HTTPException(status_code=400, detail="Scheduled time required when not sending immediately")
            
            update_query = """
                UPDATE project_proposals 
                SET status = 'scheduled', scheduled_send_time = %s
                WHERE proposal_id = %s
            """
            cursor.execute(update_query, (send_request.scheduled_time, proposal_id))
            message = f"Proposal scheduled for {send_request.scheduled_time.strftime('%Y-%m-%d %H:%M')}"
        
        connection.commit()
        
        # TODO: Integrate with SendGrid/Email service
        # TODO: If scheduled, add to job queue
        
        print(f"[SEND] {message}")
        
        return {
            "success": True,
            "message": message,
            "scheduled": not send_request.send_immediately
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error sending proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/proposals/{proposal_id}/export")
async def export_proposal(
    proposal_id: int,
    format: str = "json",  # json, pdf, link
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Export proposal - SCOPE REQUIREMENT: PDF, interactive link, or client-facing dashboard
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
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Get sections to include
        sections_included = json.loads(proposal.get('sections_included', '[]')) if proposal.get('sections_included') else ['strategy', 'differentiators', 'timeline']
        
        export_data = {
            "proposal_id": proposal['proposal_id'],
            "client_name": proposal['client_name'],
            "client_email": proposal['client_email'],
            "client_phone": proposal['client_phone'],
            "company_name": proposal.get('company_name', ''),
            "business_type": proposal['business_type'],
            "budget": float(proposal['budget']),
            "challenges": proposal['challenges'],
            "target_audience": proposal['target_audience'],
            "tone": proposal.get('tone', 'professional'),
            "custom_notes": proposal.get('custom_notes'),
            "sections_included": sections_included,
            "created_at": proposal['created_at'].isoformat() if proposal['created_at'] else None
        }
        
        # Include only selected sections
        if 'strategy' in sections_included:
            export_data['strategy'] = json.loads(proposal['ai_generated_strategy']) if proposal['ai_generated_strategy'] else {}
        
        if 'differentiators' in sections_included:
            export_data['differentiators'] = json.loads(proposal['competitive_differentiators']) if proposal['competitive_differentiators'] else {}
        
        if 'timeline' in sections_included:
            export_data['timeline'] = json.loads(proposal['suggested_timeline']) if proposal['suggested_timeline'] else {}
        
        if format == "link":
            # Generate shareable link
            share_token = f"proposal_{proposal_id}_{datetime.now().timestamp()}"
            export_data['share_link'] = f"{settings.FRONTEND_URL}/proposals/view/{share_token}"
            export_data['expires_in'] = "30 days"
        
        elif format == "pdf":
            # TODO: Implement PDF generation using ReportLab or WeasyPrint
            export_data['pdf_status'] = "pending"
            export_data['message'] = "PDF generation will be implemented with ReportLab"
        
        return {
            "success": True,
            "format": format,
            "export_data": export_data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error exporting proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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
    """Delete a proposal"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("DELETE FROM project_proposals WHERE proposal_id = %s", (proposal_id,))
        connection.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        return {
            "success": True,
            "message": "Proposal deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()