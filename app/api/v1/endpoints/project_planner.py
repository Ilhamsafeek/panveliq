"""
AI Project Planner - Complete API Implementation (No Migration Required)
File: app/api/v1/endpoints/project_planner.py
"""

from fastapi import APIRouter, HTTPException, status, Depends, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import pymysql
import json
import secrets
from io import BytesIO

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
    """Generate shareable link for proposal"""
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
        
        # Generate unique token
        share_token = secrets.token_urlsafe(32)
        
        # Try to use share_links table if it exists
        try:
            cursor.execute("""
                INSERT INTO proposal_share_links (proposal_id, share_token, created_by, expires_at)
                VALUES (%s, %s, %s, DATE_ADD(NOW(), INTERVAL 30 DAY))
            """, (proposal_id, share_token, current_user['user_id']))
            connection.commit()
        except:
            # Table doesn't exist, just generate URL
            pass
        
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8000')
        share_link = f"{base_url}/proposals/view/{proposal_id}?token={share_token}"
        
        print(f"[LINK] Generated share link for proposal {proposal_id}")
        
        return {
            "success": True,
            "share_link": share_link,
            "expires_in": "30 days"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating link: {e}")
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
        cursor.execute("SELECT * FROM project_proposals WHERE proposal_id = %s", (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        # Update status to sent
        cursor.execute("""
            UPDATE project_proposals 
            SET status = %s, sent_at = NOW(), updated_at = NOW()
            WHERE proposal_id = %s
        """, ('sent', proposal_id))
        
        connection.commit()
        
        print(f"[DASHBOARD] Proposal {proposal_id} sent to client dashboard")
        
        return {
            "success": True,
            "message": "Proposal successfully added to client dashboard"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error sending to dashboard: {e}")
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
    """Send proposal via email"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if proposal exists
        cursor.execute("SELECT * FROM project_proposals WHERE proposal_id = %s", (proposal_id,))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        
        recipient_email = email_data.get('recipient_email')
        subject = email_data.get('subject', 'Marketing Proposal for Your Review')
        message = email_data.get('message', '')
        
        if not recipient_email:
            raise HTTPException(status_code=400, detail="Recipient email is required")
        
        # Here you would integrate with your email service (SendGrid, AWS SES, etc.)
        # For now, we'll just log it and update the status
        
        print(f"[EMAIL] Sending proposal {proposal_id} to {recipient_email}")
        print(f"  Subject: {subject}")
        print(f"  Message: {message[:100]}...")
        
        # Update proposal status
        cursor.execute("""
            UPDATE project_proposals 
            SET status = %s, sent_at = NOW(), updated_at = NOW()
            WHERE proposal_id = %s
        """, ('sent', proposal_id))
        
        connection.commit()
        
        # TODO: Implement actual email sending here
        # Example with a generic email service:
        # send_email(
        #     to=recipient_email,
        #     subject=subject,
        #     body=message,
        #     attachments=[generate_pdf(proposal_id)]
        # )
        
        return {
            "success": True,
            "message": f"Proposal sent successfully to {recipient_email}"
        }
    
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