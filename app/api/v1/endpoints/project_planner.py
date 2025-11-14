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
    """Export proposal as professional interactive PDF"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get proposal
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
        
        # Generate professional PDF
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, mm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
            from reportlab.lib import colors
            
            # Parse JSON data
            strategy_data = json.loads(proposal['ai_generated_strategy']) if proposal['ai_generated_strategy'] else {}
            diff_data = json.loads(proposal['competitive_differentiators']) if proposal['competitive_differentiators'] else {}
            timeline_data = json.loads(proposal['suggested_timeline']) if proposal['suggested_timeline'] else {}
            
            # Create PDF in memory
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=50, bottomMargin=40, leftMargin=40, rightMargin=40)
            
            # Custom styles
            styles = getSampleStyleSheet()
            
            cover_title = ParagraphStyle(
                'CoverTitle', parent=styles['Heading1'], fontSize=36,
                textColor=colors.HexColor('#9926F3'), spaceAfter=10,
                alignment=TA_CENTER, fontName='Helvetica-Bold', leading=42
            )
            
            cover_subtitle = ParagraphStyle(
                'CoverSubtitle', parent=styles['Normal'], fontSize=18,
                textColor=colors.HexColor('#1DD8FC'), spaceAfter=30,
                alignment=TA_CENTER, fontName='Helvetica', leading=22
            )
            
            section_heading = ParagraphStyle(
                'SectionHeading', parent=styles['Heading1'], fontSize=20,
                textColor=colors.HexColor('#9926F3'), spaceAfter=15, spaceBefore=20,
                fontName='Helvetica-Bold', borderWidth=2, borderColor=colors.HexColor('#1DD8FC'),
                borderPadding=10, backColor=colors.HexColor('#F8F9FA'), leading=24
            )
            
            sub_heading = ParagraphStyle(
                'SubHeading', parent=styles['Heading2'], fontSize=16,
                textColor=colors.HexColor('#1DD8FC'), spaceAfter=10, spaceBefore=15,
                fontName='Helvetica-Bold', leading=20
            )
            
            body_pro = ParagraphStyle(
                'BodyPro', parent=styles['Normal'], fontSize=11,
                textColor=colors.HexColor('#333333'), spaceAfter=10,
                alignment=TA_JUSTIFY, fontName='Helvetica', leading=16
            )
            
            bullet_point = ParagraphStyle(
                'BulletPoint', parent=styles['Normal'], fontSize=11,
                textColor=colors.HexColor('#555555'), spaceAfter=8,
                leftIndent=20, bulletIndent=10, fontName='Helvetica', leading=15
            )
            
            # Build story
            story = []
            
            # === COVER PAGE ===
            story.append(Spacer(1, 1.5*inch))
            story.append(Paragraph("DIGITAL MARKETING", cover_title))
            story.append(Paragraph("PROPOSAL", cover_title))
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph(f"Prepared for {proposal['client_name']}", cover_subtitle))
            story.append(Spacer(1, 0.5*inch))
            
            # Client Info Table
            client_info = [
                ['Company:', proposal.get('company_name', 'N/A')],
                ['Business Type:', proposal['business_type']],
                ['Investment Budget:', f"${proposal['budget']:,.2f}"],
                ['Prepared On:', datetime.now().strftime('%B %d, %Y')],
            ]
            
            client_table = Table(client_info, colWidths=[2*inch, 4*inch])
            client_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#9926F3')),
                ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#F8F9FA')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
                ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('PADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DDDDDD')),
            ]))
            story.append(client_table)
            story.append(PageBreak())
            
            # === EXECUTIVE SUMMARY ===
            story.append(Paragraph("EXECUTIVE SUMMARY", section_heading))
            story.append(Spacer(1, 0.2*inch))
            
            summary_text = f"""
            This comprehensive digital marketing proposal has been specifically designed for 
            <b>{proposal.get('company_name', 'your organization')}</b>, a {proposal['business_type']} 
            looking to enhance their digital presence and drive measurable growth.
            <br/><br/>
            Our AI-powered approach combines cutting-edge marketing technology with proven strategies 
            to deliver exceptional results within your investment budget of <b>${proposal['budget']:,.2f}</b>.
            <br/><br/>
            <b>Key Challenges We'll Address:</b><br/>
            {proposal.get('challenges', 'Market penetration and brand awareness')}
            <br/><br/>
            <b>Target Audience Focus:</b><br/>
            {proposal.get('target_audience', 'Defined target market segments')}
            """
            story.append(Paragraph(summary_text, body_pro))
            story.append(PageBreak())
            
            # === STRATEGY SECTION ===
            story.append(Paragraph("STRATEGIC MARKETING APPROACH", section_heading))
            story.append(Spacer(1, 0.2*inch))
            
            if strategy_data and strategy_data.get('campaigns'):
                story.append(Paragraph("Recommended Campaign Mix", sub_heading))
                
                campaign_data = []
                for campaign_type, details in strategy_data.get('campaigns', {}).items():
                    if isinstance(details, dict):
                        platforms = ', '.join(details.get('platforms', [])) if details.get('platforms') else 'Multiple Platforms'
                        campaign_name = campaign_type.replace('_', ' ').title()
                        campaign_data.append([campaign_name, platforms])
                
                if campaign_data:
                    campaign_table = Table(campaign_data, colWidths=[2.5*inch, 4*inch])
                    campaign_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9926F3')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('PADDING', (0, 0), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DDDDDD')),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
                    ]))
                    story.append(campaign_table)
                    story.append(Spacer(1, 0.2*inch))
            
            # Automation Tools
            if strategy_data and strategy_data.get('automation_tools'):
                story.append(Paragraph("Marketing Automation & Tools", sub_heading))
                for tool in strategy_data.get('automation_tools', [])[:8]:
                    story.append(Paragraph(f"• {tool}", bullet_point))
            
            story.append(PageBreak())
            
            # === DIFFERENTIATORS ===
            story.append(Paragraph("WHY CHOOSE US", section_heading))
            story.append(Spacer(1, 0.2*inch))
            
            if diff_data and diff_data.get('differentiators'):
                for idx, diff in enumerate(diff_data.get('differentiators', [])[:5], 1):
                    story.append(Paragraph(f"<b>{idx}. {diff.get('title', 'Key Advantage')}</b>", sub_heading))
                    story.append(Paragraph(diff.get('description', ''), body_pro))
                    
                    impact_table = Table(
                        [['Expected Impact:', diff.get('impact', 'Significant positive results')]],
                        colWidths=[1.5*inch, 4.5*inch]
                    )
                    impact_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#1DD8FC')),
                        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#E8F8FD')),
                        ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
                        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('PADDING', (0, 0), (-1, -1), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1DD8FC')),
                    ]))
                    story.append(impact_table)
                    story.append(Spacer(1, 0.15*inch))
            
            story.append(PageBreak())
            
            # === TIMELINE ===
            story.append(Paragraph("PROJECT TIMELINE & MILESTONES", section_heading))
            story.append(Spacer(1, 0.2*inch))
            
            if timeline_data and timeline_data.get('phases'):
                for phase in timeline_data.get('phases', []):
                    phase_header = Table(
                        [[phase.get('phase', 'Phase'), phase.get('duration', 'Duration TBD')]],
                        colWidths=[4*inch, 2*inch]
                    )
                    phase_header.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#9926F3')),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 12),
                        ('PADDING', (0, 0), (-1, -1), 10),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ]))
                    story.append(phase_header)
                    
                    if phase.get('milestones'):
                        for milestone in phase.get('milestones', []):
                            story.append(Paragraph(f"✓ {milestone}", bullet_point))
                    
                    story.append(Spacer(1, 0.15*inch))
            
            story.append(PageBreak())
            
            # === INVESTMENT ===
            story.append(Paragraph("INVESTMENT BREAKDOWN", section_heading))
            story.append(Spacer(1, 0.2*inch))
            
            budget = float(proposal['budget'])  # Convert Decimal to float
            investment_data = [
                ['Investment Category', 'Allocation', 'Amount'],
                ['Strategy & Planning', '15%', f"${budget * 0.15:,.2f}"],
                ['Creative Development', '20%', f"${budget * 0.20:,.2f}"],
                ['Media & Advertising', '45%', f"${budget * 0.45:,.2f}"],
                ['Analytics & Optimization', '10%', f"${budget * 0.10:,.2f}"],
                ['Management & Support', '10%', f"${budget * 0.10:,.2f}"],
                ['', '<b>TOTAL INVESTMENT</b>', f"<b>${budget:,.2f}</b>"],
            ]
            
            investment_table = Table(investment_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
            investment_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9926F3')),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1DD8FC')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('PADDING', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DDDDDD')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8F9FA')]),
            ]))
            story.append(investment_table)
            
            # === NEXT STEPS ===
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("NEXT STEPS", section_heading))
            story.append(Spacer(1, 0.2*inch))
            
            next_steps = [
                "Review this comprehensive proposal and share any questions or feedback",
                "Schedule a discovery call to discuss your specific goals and requirements",
                "Finalize the strategy and customize the approach based on your input",
                "Sign the agreement and begin onboarding process",
                "Launch your digital marketing campaigns within 2 weeks",
            ]
            
            for idx, step in enumerate(next_steps, 1):
                story.append(Paragraph(f"<b>Step {idx}:</b> {step}", bullet_point))
            
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("CONTACT INFORMATION", sub_heading))
            
            contact_info = """
            <b>PanvelIQ Digital Marketing</b><br/>
            Email: hello@panveliq.com | Phone: +1 (555) 123-4567<br/>
            Website: www.panveliq.com<br/><br/>
            We look forward to partnering with you on this exciting journey!
            """
            story.append(Paragraph(contact_info, body_pro))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            
            # Safe filename generation
            company_name = proposal.get('company_name') or 'Client'
            safe_company_name = str(company_name).replace(' ', '_').replace('/', '_')
            filename = f"Proposal_{safe_company_name}_{proposal_id}.pdf"
            
            return StreamingResponse(
                buffer,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
        
        except ImportError as ie:
            print(f"Import error: {ie}")
            raise HTTPException(
                status_code=501,
                detail="PDF export requires reportlab. Install: pip install reportlab"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error exporting PDF: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



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