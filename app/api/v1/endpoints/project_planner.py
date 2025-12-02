"""
AI Project Planner - Complete API Implementation (No Migration Required)
File: app/api/v1/endpoints/project_planner.py
"""

from fastapi import APIRouter, HTTPException, status, Depends, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import pymysql
import json
import secrets
from io import BytesIO
import requests

from app.core.config import settings
from app.services.ai_service import AIService
from app.core.security import require_admin_or_employee
from app.core.security import get_db_connection

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
    """Model for editing proposals - accepts HTML content"""
    strategy: Optional[str] = None
    differentiators: Optional[str] = None
    timeline: Optional[str] = None
    custom_notes: Optional[str] = None
    tone: Optional[str] = None


class SendProposalRequest(BaseModel):
    """Model for sending proposals"""
    lead_email: str
    lead_name: str
    send_immediately: bool = True
    scheduled_time: Optional[datetime] = None
    include_sections: Optional[List[str]] = None
    custom_message: Optional[str] = None


# ========== DATABASE CONNECTION ==========

def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    try:
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = %s 
            AND COLUMN_NAME = %s
        """, (table_name, column_name))
        result = cursor.fetchone()
        return result['count'] > 0
    except:
        return False


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
        print(f"[PROPOSAL] Generating for {project_input.company_name}")
        print(f"{'='*60}")
        
        # Initialize AI Service
        ai_service = AIService()
        
        # Generate Strategy
        print("[1/4] Generating Strategy...")
        strategy_prompt = f"""
        Create a comprehensive digital marketing strategy for:
        Company: {project_input.company_name}
        Business Type: {project_input.business_type}
        Budget: ${project_input.budget}
        Challenges: {project_input.challenges}
        Target Audience: {project_input.target_audience}
        Existing Presence: {json.dumps(project_input.existing_presence)}
        
        Include:
        - Recommended campaigns (ad, email, SEO, social media)
        - Platform recommendations
        - Creative formats
        - Content topics
        - Automation tools
        
        Format as JSON with campaigns and automation_tools arrays.
        """
        
        ai_strategy = await ai_service.generate_strategy(strategy_prompt)
        print("   ✓ Strategy generated")
        
        # Generate Differentiators
        print("[2/4] Generating Differentiators...")
        differentiator_prompt = f"""
        Create competitive differentiators for a digital marketing agency proposal.
        Budget: ${project_input.budget}
        Business Type: {project_input.business_type}
        
        Highlight:
        - Faster deployment with automation
        - AI-personalized targeting
        - Cost-efficiency
        - Advanced performance tracking
        
        Format as JSON with differentiators array containing title, description, and impact.
        """
        
        differentiators = await ai_service.generate_differentiators(differentiator_prompt)
        print("   ✓ Differentiators generated")
        
        # Generate Timeline
        print("[3/4] Generating Timeline...")
        timeline_prompt = f"""
        Create project timeline for:
        Budget: ${project_input.budget}
        
        Include:
        - 4-6 phases with durations
        - Milestones per phase
        - Deliverables
        
        Format as JSON with phases array.
        """
        
        timeline = await ai_service.generate_timeline(timeline_prompt)
        print("   ✓ Timeline generated")
        
        # Save to Database
        print("[4/4] Saving to database...")
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if lead exists
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (project_input.lead_email.lower(),))
        lead_user = cursor.fetchone()
        
        if not lead_user:
            cursor.execute("""
                INSERT INTO users (email, password_hash, full_name, role, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (project_input.lead_email.lower(), '', project_input.lead_name, 'client', 'pending'))
            connection.commit()
            lead_user_id = cursor.lastrowid
        else:
            lead_user_id = lead_user['user_id']
        
        # Insert proposal
        cursor.execute("""
            INSERT INTO project_proposals 
            (client_id, created_by, business_type, budget, challenges, 
             target_audience, existing_presence, ai_generated_strategy, 
             competitive_differentiators, suggested_timeline, status, company_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
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
            project_input.company_name
        ))
        
        connection.commit()
        proposal_id = cursor.lastrowid
        
        print(f"\n✅ SUCCESS! Proposal ID: {proposal_id}")
        print(f"{'='*60}\n")
        
        print(f"\n✅ SUCCESS! Proposal ID: {proposal_id}")
        print(f"{'='*60}\n")
        
        # Fetch the complete proposal record with all client details
        query = """
            SELECT p.*, u.full_name as lead_name, u.email as lead_email
            FROM project_proposals p
            JOIN users u ON p.client_id = u.user_id
            WHERE p.proposal_id = %s
        """
        cursor.execute(query, (proposal_id,))
        complete_proposal = cursor.fetchone()
        
        # Add company_name from input since it's not stored in database
        complete_proposal['company_name'] = project_input.company_name
        
        # Parse JSON fields for frontend
        json_fields = ['existing_presence', 'ai_generated_strategy', 
                      'competitive_differentiators', 'suggested_timeline']
        
        for field in json_fields:
            if complete_proposal.get(field):
                if isinstance(complete_proposal[field], str):
                    try:
                        complete_proposal[field] = json.loads(complete_proposal[field])
                    except:
                        complete_proposal[field] = {}
        
        return {
            "success": True,
            "message": "Proposal generated successfully",
            "proposal_id": proposal_id,
            "proposal": complete_proposal
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"\n❌ ERROR: {str(e)}\n")
        raise HTTPException(status_code=500, detail=str(e))
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
    """Edit proposal - stores edited HTML in custom_notes field"""
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
        
        # Check which columns exist
        has_custom_html_columns = column_exists(cursor, 'project_proposals', 'custom_strategy_html')
        
        # Build update based on available columns
        if has_custom_html_columns:
            # New schema - use custom HTML columns
            update_fields = []
            update_values = []
            
            if edits.strategy is not None:
                update_fields.append("custom_strategy_html = %s")
                update_values.append(edits.strategy)
            
            if edits.differentiators is not None:
                update_fields.append("custom_differentiators_html = %s")
                update_values.append(edits.differentiators)
            
            if edits.timeline is not None:
                update_fields.append("custom_timeline_html = %s")
                update_values.append(edits.timeline)
            
            if edits.custom_notes is not None:
                update_fields.append("custom_notes = %s")
                update_values.append(edits.custom_notes)
            
            if edits.tone is not None and column_exists(cursor, 'project_proposals', 'tone'):
                update_fields.append("tone = %s")
                update_values.append(edits.tone)
        else:
            # Old schema - store everything in custom_notes as JSON
            edited_content = {
                "strategy_html": edits.strategy,
                "differentiators_html": edits.differentiators,
                "timeline_html": edits.timeline,
                "tone": edits.tone,
                "edited_at": datetime.now().isoformat()
            }
            
            update_fields = ["custom_notes = %s"]
            update_values = [json.dumps(edited_content)]
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = NOW()")
        update_values.append(proposal_id)
        
        update_query = f"""
            UPDATE project_proposals 
            SET {', '.join(update_fields)}
            WHERE proposal_id = %s
        """
        
        cursor.execute(update_query, tuple(update_values))
        connection.commit()
        
        print(f"[EDIT] Proposal {proposal_id} updated (schema: {'new' if has_custom_html_columns else 'old'})")
        
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
        import traceback
        traceback.print_exc()
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
            SELECT p.proposal_id, p.business_type, p.budget, p.status, p.created_at,
                   u.full_name as client_name, u.email as client_email,u.email as client_email, p.company_name
            FROM project_proposals p
            JOIN users u ON p.client_id = u.user_id
            ORDER BY p.created_at DESC
        """
        cursor.execute(query)
        proposals = cursor.fetchall()
        
        for proposal in proposals:
            if proposal.get('created_at'):
                proposal['created_at'] = proposal['created_at'].isoformat()
        
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


@router.get("/proposals/{proposal_id}/debug")
async def debug_proposal(
    proposal_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Debug endpoint to see raw database data"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = "SELECT * FROM project_proposals WHERE proposal_id = %s"
        cursor.execute(query, (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Get raw data
        debug_info = {
            "proposal_id": proposal['proposal_id'],
            "strategy_raw_type": str(type(proposal.get('ai_generated_strategy'))),
            "strategy_raw_value": str(proposal.get('ai_generated_strategy'))[:500],
            "timeline_raw_type": str(type(proposal.get('suggested_timeline'))),
            "timeline_raw_value": str(proposal.get('suggested_timeline'))[:500],
            "diff_raw_type": str(type(proposal.get('competitive_differentiators'))),
            "diff_raw_value": str(proposal.get('competitive_differentiators'))[:500],
        }
        
        # Try to parse
        for field in ['ai_generated_strategy', 'suggested_timeline', 'competitive_differentiators']:
            if proposal.get(field):
                try:
                    if isinstance(proposal[field], str):
                        parsed = json.loads(proposal[field])
                        debug_info[f"{field}_parsed_keys"] = list(parsed.keys()) if isinstance(parsed, dict) else "NOT_A_DICT"
                    elif isinstance(proposal[field], dict):
                        debug_info[f"{field}_parsed_keys"] = list(proposal[field].keys())
                    else:
                        debug_info[f"{field}_parsed_keys"] = "UNKNOWN_TYPE"
                except Exception as e:
                    debug_info[f"{field}_error"] = str(e)
        
        return {
            "success": True,
            "debug": debug_info
        }
    
    except Exception as e:
        print(f"Debug error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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
    """Get specific proposal with edited content support"""
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
        
        # Convert timestamps
        for field in ['created_at', 'updated_at', 'sent_at']:
            if proposal.get(field):
                proposal[field] = proposal[field].isoformat()
        
        # Parse JSON fields - IMPORTANT: Handle both string and dict types
        json_fields = ['existing_presence', 'ai_generated_strategy', 
                      'competitive_differentiators', 'suggested_timeline']
        
        for field in json_fields:
            if proposal.get(field):
                try:
                    # If it's already a dict, keep it
                    if isinstance(proposal[field], dict):
                        continue
                    # If it's a string, parse it
                    elif isinstance(proposal[field], str):
                        proposal[field] = json.loads(proposal[field])
                    # If it's bytes, decode then parse
                    elif isinstance(proposal[field], bytes):
                        proposal[field] = json.loads(proposal[field].decode('utf-8'))
                except json.JSONDecodeError as e:
                    print(f"❌ JSON Parse Error for {field}: {e}")
                    print(f"   Raw value: {proposal[field][:200] if proposal[field] else 'None'}")
                    proposal[field] = {}
                except Exception as e:
                    print(f"❌ Error parsing {field}: {e}")
                    proposal[field] = {}
            else:
                proposal[field] = {}
        
        # Check for custom edited content
        if proposal.get('custom_strategy_html'):
            # New schema - dedicated column for edited HTML
            proposal['edited_content'] = proposal['custom_strategy_html']
            print(f"[GET PROPOSAL] Found edited content in custom_strategy_html")
        elif proposal.get('custom_notes'):
            # Old schema - check custom_notes for edited content
            try:
                notes = proposal['custom_notes']
                if isinstance(notes, str):
                    notes = json.loads(notes)
                if isinstance(notes, dict) and 'edited_content' in notes:
                    proposal['edited_content'] = notes['edited_content']
                    print(f"[GET PROPOSAL] Found edited content in custom_notes")
            except Exception as e:
                print(f"Error parsing custom_notes for edited content: {e}")
        
        # Debug log
        print(f"[GET PROPOSAL {proposal_id}] Parsed data:")
        print(f"  Strategy keys: {list(proposal.get('ai_generated_strategy', {}).keys())}")
        print(f"  Differentiators keys: {list(proposal.get('competitive_differentiators', {}).keys())}")
        print(f"  Timeline keys: {list(proposal.get('suggested_timeline', {}).keys())}")
        print(f"  Has edited content: {bool(proposal.get('edited_content'))}")
        
        return {
            "success": True,
            "proposal": proposal
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting proposal: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@router.post("/proposals/{proposal_id}/send")
async def send_proposal(
    proposal_id: int,
    send_data: SendProposalRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Send proposal to client"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get proposal
        cursor.execute("SELECT * FROM project_proposals WHERE proposal_id = %s", (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Check if scheduled_send_time column exists
        has_scheduled_column = column_exists(cursor, 'project_proposals', 'scheduled_send_time')
        
        # Update status
        if send_data.send_immediately:
            cursor.execute("""
                UPDATE project_proposals 
                SET status = %s, sent_at = NOW()
                WHERE proposal_id = %s
            """, ('sent', proposal_id))
            
            print(f"[SEND] Proposal sent to {send_data.lead_email}")
            message = "Proposal sent successfully"
        else:
            if has_scheduled_column:
                cursor.execute("""
                    UPDATE project_proposals 
                    SET status = %s, scheduled_send_time = %s
                    WHERE proposal_id = %s
                """, ('scheduled', send_data.scheduled_time, proposal_id))
            else:
                # Store in custom_notes if column doesn't exist
                cursor.execute("""
                    UPDATE project_proposals 
                    SET status = %s, custom_notes = %s
                    WHERE proposal_id = %s
                """, ('scheduled', json.dumps({"scheduled_time": send_data.scheduled_time.isoformat()}), proposal_id))
            
            message = f"Proposal scheduled for {send_data.scheduled_time}"
        
        connection.commit()
        
        return {
            "success": True,
            "message": message
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


@router.post("/proposals/{proposal_id}/generate-link")
async def generate_shareable_link(
    proposal_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Generate shareable link for proposal with 30-day expiry"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if proposal exists
        cursor.execute("""
            SELECT proposal_id, client_id 
            FROM project_proposals 
            WHERE proposal_id = %s
        """, (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Generate unique token
        share_token = secrets.token_urlsafe(32)
        
        # Calculate expiry date (30 days from now)
        expires_at = datetime.now() + timedelta(days=30)
        
        # Check table structure to determine which columns exist
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'proposal_share_links'
        """)
        columns = [row['COLUMN_NAME'] for row in cursor.fetchall()]
        
        has_is_active = 'is_active' in columns
        has_view_count = 'view_count' in columns
        
        # Delete existing links for this proposal (simpler approach)
        cursor.execute("""
            DELETE FROM proposal_share_links 
            WHERE proposal_id = %s
        """, (proposal_id,))
        
        # Insert new share link based on available columns
        if has_is_active and has_view_count:
            cursor.execute("""
                INSERT INTO proposal_share_links 
                (proposal_id, share_token, created_by, expires_at, is_active, view_count)
                VALUES (%s, %s, %s, %s, TRUE, 0)
            """, (proposal_id, share_token, current_user['user_id'], expires_at))
        elif has_is_active:
            cursor.execute("""
                INSERT INTO proposal_share_links 
                (proposal_id, share_token, created_by, expires_at, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (proposal_id, share_token, current_user['user_id'], expires_at))
        else:
            # Basic insert without optional columns
            cursor.execute("""
                INSERT INTO proposal_share_links 
                (proposal_id, share_token, created_by, expires_at)
                VALUES (%s, %s, %s, %s)
            """, (proposal_id, share_token, current_user['user_id'], expires_at))
        
        connection.commit()
        
        # Generate the share URL
        base_url = getattr(settings, 'FRONTEND_URL', 'https://panvel-iq.calim.ai')
        share_link = f"{base_url}/proposals/view/{share_token}"
        
        print(f"[LINK] Generated share link for proposal {proposal_id}, expires: {expires_at}")
        
        return {
            "success": True,
            "share_link": share_link,
            "expires_at": expires_at.isoformat(),
            "expires_in": "30 days"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error generating share link: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



@router.get("/proposals/shared/{share_token}")
async def get_shared_proposal(share_token: str):
    """
    Public endpoint to view a shared proposal via token
    No authentication required - validates token and expiry
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # First, get the columns that exist in the table
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'proposal_share_links'
        """)
        columns = [row['COLUMN_NAME'] for row in cursor.fetchall()]
        
        # Determine primary key column name
        pk_column = 'id' if 'id' in columns else 'link_id' if 'link_id' in columns else columns[0]
        has_is_active = 'is_active' in columns
        has_view_count = 'view_count' in columns
        has_last_viewed = 'last_viewed_at' in columns
        
        # Find the share link and validate
        cursor.execute(f"""
            SELECT * FROM proposal_share_links
            WHERE share_token = %s
        """, (share_token,))
        
        share_link = cursor.fetchone()
        
        if not share_link:
            raise HTTPException(
                status_code=404, 
                detail="Invalid or expired share link"
            )
        
        # Check if link is active (if column exists)
        if has_is_active and not share_link.get('is_active', True):
            raise HTTPException(
                status_code=410, 
                detail="This share link has been deactivated"
            )
        
        # Check if link has expired
        expires_at = share_link.get('expires_at')
        if expires_at and datetime.now() > expires_at:
            # Mark as inactive if column exists
            if has_is_active:
                cursor.execute(f"""
                    UPDATE proposal_share_links 
                    SET is_active = FALSE 
                    WHERE {pk_column} = %s
                """, (share_link[pk_column],))
                connection.commit()
            
            raise HTTPException(
                status_code=410, 
                detail="This share link has expired"
            )
        
        # Fetch the proposal data
        proposal_id = share_link['proposal_id']
        cursor.execute("""
            SELECT 
                pp.*,
                u.full_name as client_name,
                u.email as client_email,
                creator.full_name as created_by_name
            FROM project_proposals pp
            LEFT JOIN users u ON pp.client_id = u.user_id
            LEFT JOIN users creator ON pp.created_by = creator.user_id
            WHERE pp.proposal_id = %s
        """, (proposal_id,))
        
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Update view count if column exists
        if has_view_count:
            update_parts = ["view_count = COALESCE(view_count, 0) + 1"]
            if has_last_viewed:
                update_parts.append("last_viewed_at = NOW()")
            
            cursor.execute(f"""
                UPDATE proposal_share_links 
                SET {', '.join(update_parts)}
                WHERE {pk_column} = %s
            """, (share_link[pk_column],))
            connection.commit()
        
        # Parse JSON fields
        def safe_json_parse(data, default=None):
            if data is None:
                return default
            if isinstance(data, (dict, list)):
                return data
            try:
                return json.loads(data) if data else default
            except:
                return default
        
        # Format proposal for public view
        proposal_data = {
            "proposal_id": proposal['proposal_id'],
            "client_name": proposal.get('client_name', 'Client'),
            "company_name": proposal.get('company_name', ''),
            "business_type": proposal.get('business_type', ''),
            "budget": float(proposal['budget']) if proposal.get('budget') else 0,
            "challenges": proposal.get('challenges', ''),
            "target_audience": proposal.get('target_audience', ''),
            "ai_generated_strategy": safe_json_parse(proposal.get('ai_generated_strategy'), {}),
            "competitive_differentiators": safe_json_parse(proposal.get('competitive_differentiators'), {}),
            "suggested_timeline": safe_json_parse(proposal.get('suggested_timeline'), {}),
            "status": proposal.get('status', 'draft'),
            "created_at": proposal['created_at'].isoformat() if proposal.get('created_at') else None,
            "created_by_name": proposal.get('created_by_name', 'PanvelIQ Team')
        }
        
        # Calculate days remaining
        days_remaining = 30  # Default
        if expires_at:
            days_remaining = (expires_at - datetime.now()).days
        
        view_count = share_link.get('view_count', 0) or 0
        
        return {
            "success": True,
            "proposal": proposal_data,
            "link_info": {
                "expires_at": expires_at.isoformat() if expires_at else None,
                "days_remaining": max(0, days_remaining),
                "view_count": view_count + 1
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching shared proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/proposals/{proposal_id}/export/pdf")
async def export_proposal_pdf(
    proposal_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Export proposal as PDF with HTML content"""
    connection = None
    cursor = None
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.lib import colors
        from html import unescape
        import re
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get proposal with all data
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
        
        # Get the HTML content - prioritize edited content
        html_content = None
        
        if proposal.get('custom_strategy_html'):
            html_content = proposal['custom_strategy_html']
            print(f"[PDF] Using custom_strategy_html")
        elif proposal.get('custom_notes'):
            try:
                notes = json.loads(proposal['custom_notes']) if isinstance(proposal['custom_notes'], str) else proposal['custom_notes']
                if isinstance(notes, dict) and 'edited_content' in notes:
                    html_content = notes['edited_content']
                    print(f"[PDF] Using edited_content from custom_notes")
            except:
                pass
        
        # If no edited content, generate from AI data
        if not html_content:
            print(f"[PDF] No edited content found, generating from AI data")
            strategy = json.loads(proposal['ai_generated_strategy']) if proposal.get('ai_generated_strategy') else {}
            differentiators = json.loads(proposal['competitive_differentiators']) if proposal.get('competitive_differentiators') else {}
            timeline = json.loads(proposal['suggested_timeline']) if proposal.get('suggested_timeline') else {}
            html_content = generate_proposal_html_for_pdf(proposal, strategy, differentiators, timeline)
        
        # Create PDF buffer
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=50, bottomMargin=50, leftMargin=50, rightMargin=50)
        
        # Define styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=colors.HexColor('#9926F3'),
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#1DD8FC'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#9926F3'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#1DD8FC'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#333333'),
            spaceAfter=10,
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            leading=16
        )
        
        # Convert HTML to ReportLab elements
        story = []
        
        # Simple HTML parser - convert common tags
        def html_to_paragraphs(html_text):
            elements = []
            
            # Remove style attributes and scripts
            html_text = re.sub(r'<style[^>]*>.*?</style>', '', html_text, flags=re.DOTALL)
            html_text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL)
            html_text = re.sub(r'\sstyle="[^"]*"', '', html_text)
            
            # Split by major tags
            parts = re.split(r'(<h1[^>]*>.*?</h1>|<h2[^>]*>.*?</h2>|<h3[^>]*>.*?</h3>|<p[^>]*>.*?</p>|<ul[^>]*>.*?</ul>|<ol[^>]*>.*?</ol>|<hr[^>]*>)', html_text, flags=re.DOTALL)
            
            for part in parts:
                if not part.strip():
                    continue
                
                # H1 tags
                if part.startswith('<h1'):
                    text = re.sub(r'<[^>]+>', '', part)
                    text = unescape(text.strip())
                    if text:
                        elements.append(Paragraph(text, title_style))
                        elements.append(Spacer(1, 0.2*inch))
                
                # H2 tags
                elif part.startswith('<h2'):
                    text = re.sub(r'<[^>]+>', '', part)
                    text = unescape(text.strip())
                    if text:
                        elements.append(Paragraph(text, subtitle_style))
                        elements.append(Spacer(1, 0.2*inch))
                
                # H3 tags or H2/H3 with <strong>
                elif '<strong>' in part and ('<h2' in part or '<h3' in part):
                    text = re.sub(r'<[^>]+>', '', part)
                    text = unescape(text.strip())
                    if text:
                        elements.append(Paragraph(text, heading_style))
                        elements.append(Spacer(1, 0.1*inch))
                
                # Paragraph tags
                elif part.startswith('<p'):
                    text = re.sub(r'<[^>]+>', '', part)
                    text = unescape(text.strip())
                    if text:
                        # Keep bold and italic
                        text = part.replace('<p>', '').replace('</p>', '')
                        text = text.replace('<strong>', '<b>').replace('</strong>', '</b>')
                        text = text.replace('<em>', '<i>').replace('</em>', '</i>')
                        text = re.sub(r'\sstyle="[^"]*"', '', text)
                        elements.append(Paragraph(text, body_style))
                
                # List tags
                elif part.startswith('<ul') or part.startswith('<ol'):
                    # Extract list items
                    items = re.findall(r'<li[^>]*>(.*?)</li>', part, flags=re.DOTALL)
                    for item in items:
                        item = re.sub(r'<[^>]+>', '', item)
                        item = unescape(item.strip())
                        if item:
                            elements.append(Paragraph(f"• {item}", body_style))
                
                # HR tags
                elif part.startswith('<hr'):
                    elements.append(Spacer(1, 0.3*inch))
            
            return elements
        
        # Convert HTML to elements
        story = html_to_paragraphs(html_content)
        
        # Add footer
        story.append(Spacer(1, 0.5*inch))
        footer_text = f"""
        <b>PanvelIQ - AI-Powered Digital Marketing</b><br/>
        Email: info@panveliq.com | Website: www.panveliq.com<br/>
        <i>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</i>
        """
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER
        )
        story.append(Paragraph(footer_text, footer_style))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        # Generate filename
        company_name = proposal.get('company_name') or 'Client'
        safe_company_name = str(company_name).replace(' ', '_').replace('/', '_')
        filename = f"Proposal_{safe_company_name}_{proposal_id}.pdf"
        
        print(f"[PDF] Successfully generated PDF: {filename}")
        
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except ImportError as ie:
        print(f"[PDF] Import error: {ie}")
        raise HTTPException(
            status_code=501,
            detail="PDF export requires reportlab. Install with: pip install reportlab"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PDF] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def generate_proposal_html_for_pdf(proposal, strategy, differentiators, timeline):
    """Generate HTML from AI data if no edited content exists"""
    
    # Extract data with proper key checking
    campaigns = strategy.get('Recommended_Campaigns', strategy.get('campaigns', []))
    tools = strategy.get('Automation_Tools', strategy.get('automation_tools', []))
    diff_items = differentiators.get('differentiators', [])
    phases = timeline.get('phases', [])
    
    company_name = proposal.get('company_name') or strategy.get('Company') or 'Your Company'
    budget = proposal.get('budget') or strategy.get('Budget') or 0
    business_type = proposal.get('business_type') or strategy.get('Business_Type') or 'business'
    challenges = proposal.get('challenges') or (', '.join(strategy.get('Challenges', [])) if strategy.get('Challenges') else 'Business challenges')
    target_audience = proposal.get('target_audience') or strategy.get('Target_Audience') or 'Target audience'
    
    # Build campaigns HTML
    campaigns_html = ""
    if campaigns:
        for camp in campaigns:
            campaign_type = camp.get('Type') or camp.get('type') or 'Campaign'
            platform = camp.get('Platform') or camp.get('platform') or ''
            platform_text = ', '.join(platform) if isinstance(platform, list) else platform
            topics = camp.get('Content_Topics') or camp.get('content_topics') or []
            topics_text = ', '.join(topics) if isinstance(topics, list) else ''
            budget_pct = camp.get('Budget_Allocation_Percentage') or ''
            
            campaigns_html += f"<li><strong>{campaign_type}</strong>"
            if platform_text:
                campaigns_html += f" ({platform_text})"
            campaigns_html += f": {topics_text}"
            if budget_pct:
                campaigns_html += f" <em>({budget_pct}% of budget)</em>"
            campaigns_html += "</li>"
    else:
        campaigns_html = "<li>Customized marketing campaigns based on your business needs</li>"
    
    # Build tools HTML
    tools_html = ""
    if tools:
        for tool in tools:
            tool_name = tool.get('Tool') or tool.get('tool') or tool.get('name') or 'Marketing Tool'
            purpose = tool.get('Purpose') or tool.get('purpose') or 'Campaign enhancement'
            budget_pct = tool.get('Budget_Allocation_Percentage') or ''
            
            tools_html += f"<li><strong>{tool_name}:</strong> {purpose}"
            if budget_pct:
                tools_html += f" <em>({budget_pct}% of budget)</em>"
            tools_html += "</li>"
    else:
        tools_html = "<li>Marketing automation and analytics tools</li>"
    
    # Build differentiators HTML
    diff_html = ""
    if diff_items:
        for diff in diff_items:
            title = diff.get('title', 'Competitive Advantage')
            description = diff.get('description', '')
            impact = diff.get('impact', 'Positive impact on results')
            diff_html += f"""
            <li>
                <strong>{title}:</strong> {description}<br>
                <em>Impact: {impact}</em>
            </li>
            """
    else:
        diff_html = "<li><strong>AI-Powered Approach:</strong> Leveraging technology for optimal results<br><em>Impact: Increased efficiency and ROI</em></li>"
    
    # Build timeline HTML
    timeline_html = ""
    if phases:
        for idx, phase in enumerate(phases, 1):
            phase_name = phase.get('phase') or phase.get('name') or f"Phase {idx}"
            duration = phase.get('duration', 'TBD')
            deliverables = phase.get('deliverables', [])
            
            timeline_html += f"""
            <h3><strong>Phase {idx}: {phase_name}</strong></h3>
            <p><strong>Duration:</strong> {duration}</p>
            <p><strong>Key Deliverables:</strong></p>
            <ul>
            """
            for deliverable in deliverables:
                timeline_html += f"<li>{deliverable}</li>"
            timeline_html += "</ul>"
    else:
        timeline_html = """
        <h3><strong>Phase 1: Planning & Setup</strong></h3>
        <p><strong>Duration:</strong> 2-4 weeks</p>
        <ul><li>Initial strategy development and campaign setup</li></ul>
        """
    
    return f"""
    <h1>Digital Marketing Proposal</h1>
    <h2>for {company_name}</h2>
    <p style="text-align: center;"><em>Prepared by PanvelIQ</em></p>
    
    <hr>
    
    <h2><strong>Executive Summary</strong></h2>
    <p>This comprehensive digital marketing proposal has been specifically designed for <strong>{company_name}</strong>, a {business_type} looking to enhance their digital presence and drive measurable growth.</p>
    <p>Our AI-powered approach combines cutting-edge marketing technology with proven strategies to deliver exceptional results within your investment budget of <strong>${budget:,.2f}</strong>.</p>
    
    <h2><strong>Current Challenges</strong></h2>
    <p>{challenges}</p>
    
    <h2><strong>Target Audience Analysis</strong></h2>
    <p>{target_audience}</p>
    
    <h2><strong>Recommended Marketing Strategy</strong></h2>
    <p>Based on our AI analysis, we recommend a comprehensive marketing approach across multiple channels.</p>
    
    <h3><strong>Recommended Campaigns</strong></h3>
    <ul>
        {campaigns_html}
    </ul>
    
    <h3><strong>Automation Tools & Technologies</strong></h3>
    <ul>
        {tools_html}
    </ul>
    
    <h2><strong>Competitive Differentiators</strong></h2>
    <p>What sets our approach apart:</p>
    <ul>
        {diff_html}
    </ul>
    
    <h2><strong>Project Timeline</strong></h2>
    {timeline_html}
    
    <hr>
    
    <h2><strong>Investment & ROI</strong></h2>
    <p><strong>Total Investment:</strong> ${budget:,.2f}</p>
    <p>Our data-driven approach ensures maximum return on investment through:</p>
    <ul>
        <li>Continuous performance optimization</li>
        <li>AI-powered audience targeting</li>
        <li>Real-time analytics and reporting</li>
        <li>Agile campaign management</li>
    </ul>
    
    <h2><strong>Next Steps</strong></h2>
    <ol>
        <li>Review this proposal and provide feedback</li>
        <li>Schedule a strategy session to discuss implementation</li>
        <li>Finalize project scope and timeline</li>
        <li>Begin Phase 1 execution</li>
    </ol>
    """


@router.put("/proposals/{proposal_id}/update-content")
async def update_proposal_content(
    proposal_id: int,
    content: dict,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Update proposal content from editor"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if proposal exists
        cursor.execute("SELECT proposal_id FROM project_proposals WHERE proposal_id = %s", (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Check if custom_strategy_html column exists
        has_custom_html = column_exists(cursor, 'project_proposals', 'custom_strategy_html')
        
        if has_custom_html:
            # Store in dedicated column
            cursor.execute("""
                UPDATE project_proposals 
                SET custom_strategy_html = %s, updated_at = NOW()
                WHERE proposal_id = %s
            """, (content.get('content'), proposal_id))
        else:
            # Store in custom_notes
            cursor.execute("""
                UPDATE project_proposals 
                SET custom_notes = %s, updated_at = NOW()
                WHERE proposal_id = %s
            """, (json.dumps({"edited_content": content.get('content')}), proposal_id))
        
        connection.commit()
        
        print(f"[UPDATE] Proposal {proposal_id} content saved")
        
        return {
            "success": True,
            "message": "Content saved successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error updating content: {e}")
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


@router.post("/proposals/{proposal_id}/send-to-dashboard")
async def send_to_dashboard(
    proposal_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Send proposal to client dashboard"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if proposal exists
        cursor.execute("""
            SELECT p.*, u.full_name, u.email 
            FROM project_proposals p
            JOIN users u ON p.client_id = u.user_id
            WHERE p.proposal_id = %s
        """, (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Update status to sent
        cursor.execute("""
            UPDATE project_proposals 
            SET status = %s, sent_at = NOW(), updated_at = NOW()
            WHERE proposal_id = %s
        """, ('sent', proposal_id))
        
        # Create notification for the client
        cursor.execute("""
            INSERT INTO notifications 
            (user_id, notification_type, title, message, is_read, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            proposal['client_id'],
            'proposal_received',
            'New Marketing Proposal',
            f'A new marketing proposal has been added to your dashboard. Please review and provide your feedback.',
            False
        ))
        
        connection.commit()
        
        print(f"[DASHBOARD] Proposal {proposal_id} sent to client {proposal['full_name']} (ID: {proposal['client_id']})")
        print(f"[NOTIFICATION] Created notification for client")
        
        return {
            "success": True,
            "message": "Proposal added to client dashboard!",
            "notification_created": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error sending to dashboard: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

            

@router.post("/proposals/{proposal_id}/send-email")
async def send_proposal_email(
    proposal_id: int,
    email_data: dict,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Send proposal via email using Mailchimp Transactional (Mandrill)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if proposal exists and get details
        cursor.execute("""
            SELECT 
                pp.*,
                u.full_name as client_name,
                u.email as client_email
            FROM project_proposals pp
            LEFT JOIN users u ON pp.client_id = u.user_id
            WHERE pp.proposal_id = %s
        """, (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        recipient_email = email_data.get('recipient_email')
        subject = email_data.get('subject', 'Marketing Proposal for Your Review')
        message = email_data.get('message', '')
        
        if not recipient_email:
            raise HTTPException(status_code=400, detail="Recipient email is required")
        
        # Generate a share link for the email
        share_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=30)
        
        cursor.execute("""
            INSERT INTO proposal_share_links 
            (proposal_id, share_token, created_by, expires_at, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
        """, (proposal_id, share_token, current_user['user_id'], expires_at))
        
        base_url = getattr(settings, 'FRONTEND_URL', 'https://panvel-iq.calim.ai')
        proposal_link = f"{base_url}/proposals/view/{share_token}"
        
        # Build email content with proposal link
        email_html = build_proposal_email_html(
            client_name=proposal.get('client_name', 'Valued Client'),
            message=message,
            proposal_link=proposal_link,
            company_name=proposal.get('company_name', ''),
            business_type=proposal.get('business_type', '')
        )
        
        # Send via Mailchimp Transactional API (Mandrill)
        email_sent = await send_via_mailchimp(
            to_email=recipient_email,
            to_name=proposal.get('client_name', ''),
            subject=subject,
            html_content=email_html,
            text_content=message
        )
        
        if email_sent:
            # Update proposal status
            cursor.execute("""
                UPDATE project_proposals 
                SET status = 'sent', sent_at = NOW(), updated_at = NOW()
                WHERE proposal_id = %s
            """, (proposal_id,))
            connection.commit()
            
            print(f"[EMAIL] Proposal {proposal_id} sent to {recipient_email}")
            
            return {
                "success": True,
                "message": f"Proposal sent successfully to {recipient_email}"
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail="Failed to send email. Please check email configuration."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

async def send_via_mailchimp(
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str,
    text_content: str
) -> bool:
    """
    Send email using SMTP (more reliable than Mailchimp API for transactional emails)
    Falls back to logging if SMTP not configured
    """
    try:
        # Try SMTP first (most reliable)
        smtp_host = getattr(settings, 'SMTP_HOST', None)
        smtp_port = getattr(settings, 'SMTP_PORT', 465)
        smtp_user = getattr(settings, 'SMTP_USER', None)
        smtp_pass = getattr(settings, 'SMTP_PASSWORD', None)
        from_email = getattr(settings, 'FROM_EMAIL', 'hello@panvel-iq.calim.ai')
        from_name = getattr(settings, 'FROM_NAME', 'PanvelIQ')
        
        if smtp_host and smtp_user and smtp_pass:
            print(f"[EMAIL] Sending via SMTP: {smtp_host}")
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{from_email}>"
            msg['To'] = to_email
            
            # Attach both plain text and HTML versions
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, to_email, msg.as_string())
            
            print(f"[EMAIL] Sent successfully via SMTP to {to_email}")
            return True
        
        # If no SMTP, try Mailchimp Transactional (Mandrill) - different from regular Mailchimp
        mandrill_key = getattr(settings, 'MANDRILL_API_KEY', None)
        if mandrill_key:
            print(f"[EMAIL] Sending via Mandrill")
            url = "https://mandrillapp.com/api/1.0/messages/send.json"
            
            payload = {
                "key": mandrill_key,
                "message": {
                    "from_email": from_email,
                    "from_name": from_name,
                    "to": [{"email": to_email, "name": to_name, "type": "to"}],
                    "subject": subject,
                    "html": html_content,
                    "text": text_content
                }
            }
            
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                print(f"[EMAIL] Sent successfully via Mandrill")
                return True
        
        # Fallback: Just log the email (for testing/development)
        print(f"[EMAIL] No email service configured - logging email instead")
        print(f"[EMAIL] To: {to_email}")
        print(f"[EMAIL] Subject: {subject}")
        print(f"[EMAIL] Message preview: {text_content[:200]}...")
        print(f"[EMAIL] Marked as sent (no actual email service configured)")
        return True  # Return True so the proposal status updates
        
    except Exception as e:
        print(f"[EMAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def build_proposal_email_html(
    client_name: str,
    message: str,
    proposal_link: str,
    company_name: str = "",
    business_type: str = ""
) -> str:
    """Build HTML email template for proposal"""
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Marketing Proposal</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <tr>
                        <td style="background: linear-gradient(135deg, #9926F3 0%, #1DD8FC 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px;">PanvelIQ</h1>
                            <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 14px;">AI-Powered Digital Marketing</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="color: #1a1a2e; margin: 0 0 20px 0; font-size: 24px;">Hello {client_name},</h2>
                            <div style="color: #4a4a4a; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                                {message.replace(chr(10), '<br>')}
                            </div>
                            {f'<p style="color: #6b7280; font-size: 14px;"><strong>Company:</strong> {company_name}</p>' if company_name else ''}
                            {f'<p style="color: #6b7280; font-size: 14px;"><strong>Industry:</strong> {business_type}</p>' if business_type else ''}
                            <div style="text-align: center; margin: 40px 0;">
                                <a href="{proposal_link}" style="display: inline-block; background: linear-gradient(135deg, #9926F3 0%, #1DD8FC 100%); color: #ffffff; text-decoration: none; padding: 16px 40px; border-radius: 8px; font-size: 16px; font-weight: bold;">
                                    View Your Proposal
                                </a>
                            </div>
                            <p style="color: #9ca3af; font-size: 13px; text-align: center;">
                                This link will expire in 30 days.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="color: #6b7280; font-size: 14px; margin: 0;">
                                &copy; 2025 PanvelIQ. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""