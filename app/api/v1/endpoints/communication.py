"""
Communication Hub API - WhatsApp, Email Campaigns & Triggered Flows
COMPLETE FILE WITH REAL API INTEGRATIONS
File: app/api/v1/endpoints/communication.py
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import pymysql
import json

from app.core.config import settings
from app.core.security import require_admin_or_employee, get_db_connection
from app.services.ai_service import AIService
from app.services.whatsapp_service import WhatsAppService
from app.services.email_service import EmailService

router = APIRouter()


# ========== PYDANTIC MODELS ==========

class WhatsAppCampaignCreate(BaseModel):
    """Create WhatsApp campaign"""
    client_id: int
    campaign_name: str
    template_name: Optional[str] = None
    message_content: str
    recipient_list: List[str]  # Phone numbers
    schedule_type: str = "scheduled"  # immediate or scheduled
    scheduled_at: Optional[datetime] = None


class EmailCampaignCreate(BaseModel):
    """Create Email campaign"""
    client_id: int
    campaign_name: str
    subject_line: str
    email_body: str
    recipient_list: List[EmailStr]
    segment_criteria: Optional[Dict[str, Any]] = {}
    schedule_type: str = "scheduled"
    scheduled_at: Optional[datetime] = None
    is_ab_test: bool = False
    ab_test_config: Optional[Dict[str, Any]] = {}


class AIEmailGenerateRequest(BaseModel):
    """Request AI-generated email copy"""
    campaign_goal: str
    target_audience: str
    tone: str = "professional"  # professional, friendly, urgent
    include_cta: bool = True
    industry: Optional[str] = None


class TriggeredFlowCreate(BaseModel):
    """Create triggered automation flow"""
    client_id: int
    flow_name: str
    trigger_type: str  # lead_signup, cart_abandonment, email_open, etc.
    trigger_conditions: Dict[str, Any]
    flow_actions: List[Dict[str, Any]]
    channel: str  # whatsapp, email, sms
    is_active: bool = True


class AudienceSegmentCreate(BaseModel):
    """Create audience segment"""
    client_id: int
    segment_name: str
    description: Optional[str] = None
    platform: str  # whatsapp, email, both
    segment_criteria: Dict[str, Any]
    estimated_size: Optional[int] = 0
    contacts_data: Optional[List[Dict[str, Any]]] = []  # ADD THIS


# ========== WHATSAPP CAMPAIGNS ==========

@router.post("/whatsapp/campaigns/create")
async def create_whatsapp_campaign(
    campaign: WhatsAppCampaignCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Create a new WhatsApp campaign with REAL API integration"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert campaign
        query = """
            INSERT INTO whatsapp_campaigns 
            (client_id, created_by, campaign_name, template_name, message_content, 
             schedule_type, scheduled_at, status, total_recipients, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(query, (
            campaign.client_id,
            current_user['user_id'],
            campaign.campaign_name,
            campaign.template_name,
            campaign.message_content,
            campaign.schedule_type,
            campaign.scheduled_at,
            'draft' if campaign.schedule_type == 'scheduled' else 'sending',
            len(campaign.recipient_list)
        ))
        
        connection.commit()
        campaign_id = cursor.lastrowid
        
        # ===== REAL WHATSAPP API INTEGRATION =====
        if campaign.schedule_type == 'immediate':
            try:
                whatsapp = WhatsAppService()
                
                # Validate phone numbers
                valid_recipients = [
                    phone for phone in campaign.recipient_list 
                    if whatsapp.validate_phone_number(phone)
                ]
                
                if not valid_recipients:
                    raise HTTPException(
                        status_code=400,
                        detail="No valid phone numbers provided"
                    )
                
                # Send bulk messages
                result = await whatsapp.send_bulk_messages(
                    recipients=valid_recipients,
                    message=campaign.message_content,
                    template_name=campaign.template_name
                )
                
                # Update campaign with results
                cursor.execute("""
                    UPDATE whatsapp_campaigns 
                    SET delivered_count = %s, 
                        status = %s,
                        total_recipients = %s
                    WHERE campaign_id = %s
                """, (
                    result['successful'],
                    'sent',
                    len(valid_recipients),
                    campaign_id
                ))
                connection.commit()
                
                return {
                    "success": True,
                    "message": "WhatsApp campaign sent successfully",
                    "campaign_id": campaign_id,
                    "status": "sent",
                    "total_sent": result['successful'],
                    "failed": result['failed'],
                    "details": result['details']
                }
                
            except Exception as api_error:
                # Update status to failed
                cursor.execute("""
                    UPDATE whatsapp_campaigns 
                    SET status = 'failed'
                    WHERE campaign_id = %s
                """, (campaign_id,))
                connection.commit()
                
                raise HTTPException(
                    status_code=500,
                    detail=f"WhatsApp API Error: {str(api_error)}"
                )
        
        # Scheduled campaign
        return {
            "success": True,
            "message": "WhatsApp campaign scheduled successfully",
            "campaign_id": campaign_id,
            "status": "scheduled",
            "scheduled_at": campaign.scheduled_at.isoformat() if campaign.scheduled_at else None
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


@router.get("/whatsapp/campaigns/list")
async def list_whatsapp_campaigns(
    client_id: Optional[int] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get all WhatsApp campaigns"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                wc.campaign_id, wc.campaign_name, wc.template_name, 
                wc.schedule_type, wc.scheduled_at, wc.status,
                wc.total_recipients, wc.delivered_count, wc.created_at,
                u.full_name as client_name,
                creator.full_name as created_by_name
            FROM whatsapp_campaigns wc
            JOIN users u ON wc.client_id = u.user_id
            JOIN users creator ON wc.created_by = creator.user_id
        """
        
        if client_id:
            query += " WHERE wc.client_id = %s"
            cursor.execute(query + " ORDER BY wc.created_at DESC", (client_id,))
        else:
            cursor.execute(query + " ORDER BY wc.created_at DESC")
        
        campaigns = cursor.fetchall()
        
        # Convert datetime to ISO format
        for campaign in campaigns:
            if campaign.get('scheduled_at'):
                campaign['scheduled_at'] = campaign['scheduled_at'].isoformat()
            if campaign.get('created_at'):
                campaign['created_at'] = campaign['created_at'].isoformat()
        
        return {
            "success": True,
            "campaigns": campaigns,
            "total": len(campaigns)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/whatsapp/campaigns/{campaign_id}")
async def get_whatsapp_campaign(
    campaign_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get specific WhatsApp campaign details"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT wc.*, u.full_name as client_name, u.email as client_email
            FROM whatsapp_campaigns wc
            JOIN users u ON wc.client_id = u.user_id
            WHERE wc.campaign_id = %s
        """
        
        cursor.execute(query, (campaign_id,))
        campaign = cursor.fetchone()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Convert datetime
        if campaign.get('scheduled_at'):
            campaign['scheduled_at'] = campaign['scheduled_at'].isoformat()
        if campaign.get('created_at'):
            campaign['created_at'] = campaign['created_at'].isoformat()
        
        return {
            "success": True,
            "campaign": campaign
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== EMAIL CAMPAIGNS ==========

@router.post("/email/campaigns/create")
async def create_email_campaign(
    campaign: EmailCampaignCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Create a new Email campaign with REAL Mailchimp API integration"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert campaign
        query = """
            INSERT INTO email_campaigns 
            (client_id, created_by, campaign_name, subject_line, email_body,
             segment_criteria, schedule_type, scheduled_at, status, 
             total_recipients, is_ab_test, ab_test_config, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(query, (
            campaign.client_id,
            current_user['user_id'],
            campaign.campaign_name,
            campaign.subject_line,
            campaign.email_body,
            json.dumps(campaign.segment_criteria),
            campaign.schedule_type,
            campaign.scheduled_at,
            'draft' if campaign.schedule_type == 'scheduled' else 'sending',
            len(campaign.recipient_list),
            campaign.is_ab_test,
            json.dumps(campaign.ab_test_config) if campaign.ab_test_config else None
        ))
        
        connection.commit()
        campaign_id = cursor.lastrowid
        
        # ===== REAL MAILCHIMP API INTEGRATION =====
        if campaign.schedule_type == 'immediate':
            try:
                email_service = EmailService(provider="mailchimp")
                
                # Send bulk emails
                result = await email_service.send_bulk_emails(
                    recipients=campaign.recipient_list,
                    subject=campaign.subject_line,
                    html_content=campaign.email_body,
                    from_email="noreply@panveliq.com",
                    from_name="PanvelIQ"
                )
                
                # Update campaign with results
                cursor.execute("""
                    UPDATE email_campaigns 
                    SET total_recipients = %s,
                        status = %s
                    WHERE email_campaign_id = %s
                """, (
                    result['successful'],
                    'sent',
                    campaign_id
                ))
                connection.commit()
                
                return {
                    "success": True,
                    "message": "Email campaign sent successfully",
                    "campaign_id": campaign_id,
                    "status": "sent",
                    "total_sent": result['successful'],
                    "failed": result['failed'],
                    "details": result['details']
                }
                
            except Exception as api_error:
                # Update status to failed
                cursor.execute("""
                    UPDATE email_campaigns 
                    SET status = 'failed'
                    WHERE email_campaign_id = %s
                """, (campaign_id,))
                connection.commit()
                
                raise HTTPException(
                    status_code=500,
                    detail=f"Mailchimp API Error: {str(api_error)}"
                )
        
        # Scheduled campaign
        return {
            "success": True,
            "message": "Email campaign scheduled successfully",
            "campaign_id": campaign_id,
            "status": "scheduled",
            "scheduled_at": campaign.scheduled_at.isoformat() if campaign.scheduled_at else None
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


@router.post("/email/generate-copy")
async def generate_email_copy(
    request: AIEmailGenerateRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Generate AI-powered email copy"""
    try:
        ai_service = AIService()
        
        prompt = f"""
        Generate professional email marketing copy with the following parameters:
        
        Campaign Goal: {request.campaign_goal}
        Target Audience: {request.target_audience}
        Tone: {request.tone}
        Industry: {request.industry or 'General'}
        Include CTA: {'Yes' if request.include_cta else 'No'}
        
        Please provide:
        1. Subject line (compelling and under 60 characters)
        2. Preview text (50 characters)
        3. Email body (HTML formatted, engaging, with clear structure)
        4. CTA button text (if applicable)
        
        Return as JSON with keys: subject_line, preview_text, email_body, cta_text
        """
        
        response = await ai_service.generate_strategy(prompt)
        
        return {
            "success": True,
            "email_copy": response
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email/campaigns/list")
async def list_email_campaigns(
    client_id: Optional[int] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get all Email campaigns"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                ec.email_campaign_id, ec.campaign_name, ec.subject_line,
                ec.schedule_type, ec.scheduled_at, ec.status,
                ec.total_recipients, ec.opened_count, ec.clicked_count,
                ec.is_ab_test, ec.created_at,
                u.full_name as client_name,
                creator.full_name as created_by_name
            FROM email_campaigns ec
            JOIN users u ON ec.client_id = u.user_id
            JOIN users creator ON ec.created_by = creator.user_id
        """
        
        if client_id:
            query += " WHERE ec.client_id = %s"
            cursor.execute(query + " ORDER BY ec.created_at DESC", (client_id,))
        else:
            cursor.execute(query + " ORDER BY ec.created_at DESC")
        
        campaigns = cursor.fetchall()
        
        # Convert datetime and calculate metrics
        for campaign in campaigns:
            if campaign.get('scheduled_at'):
                campaign['scheduled_at'] = campaign['scheduled_at'].isoformat()
            if campaign.get('created_at'):
                campaign['created_at'] = campaign['created_at'].isoformat()
            
            # Calculate open rate and click rate
            if campaign['total_recipients'] > 0:
                campaign['open_rate'] = round((campaign['opened_count'] / campaign['total_recipients']) * 100, 2)
                campaign['click_rate'] = round((campaign['clicked_count'] / campaign['total_recipients']) * 100, 2)
            else:
                campaign['open_rate'] = 0
                campaign['click_rate'] = 0
        
        return {
            "success": True,
            "campaigns": campaigns,
            "total": len(campaigns)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/email/campaigns/{campaign_id}")
async def get_email_campaign(
    campaign_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get specific Email campaign details"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT ec.*, u.full_name as client_name, u.email as client_email
            FROM email_campaigns ec
            JOIN users u ON ec.client_id = u.user_id
            WHERE ec.email_campaign_id = %s
        """
        
        cursor.execute(query, (campaign_id,))
        campaign = cursor.fetchone()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Parse JSON fields
        if campaign.get('segment_criteria'):
            campaign['segment_criteria'] = json.loads(campaign['segment_criteria']) if isinstance(campaign['segment_criteria'], str) else campaign['segment_criteria']
        
        if campaign.get('ab_test_config'):
            campaign['ab_test_config'] = json.loads(campaign['ab_test_config']) if isinstance(campaign['ab_test_config'], str) else campaign['ab_test_config']
        
        # Convert datetime
        if campaign.get('scheduled_at'):
            campaign['scheduled_at'] = campaign['scheduled_at'].isoformat()
        if campaign.get('created_at'):
            campaign['created_at'] = campaign['created_at'].isoformat()
        
        # Calculate metrics
        if campaign['total_recipients'] > 0:
            campaign['open_rate'] = round((campaign['opened_count'] / campaign['total_recipients']) * 100, 2)
            campaign['click_rate'] = round((campaign['clicked_count'] / campaign['total_recipients']) * 100, 2)
        else:
            campaign['open_rate'] = 0
            campaign['click_rate'] = 0
        
        return {
            "success": True,
            "campaign": campaign
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== TRIGGERED AUTOMATION FLOWS ==========

@router.post("/flows/create")
async def create_triggered_flow(
    flow: TriggeredFlowCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Create a new triggered automation flow"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            INSERT INTO triggered_flows
            (client_id, created_by, flow_name, trigger_type, trigger_conditions,
             flow_actions, channel, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(query, (
            flow.client_id,
            current_user['user_id'],
            flow.flow_name,
            flow.trigger_type,
            json.dumps(flow.trigger_conditions),
            json.dumps(flow.flow_actions),
            flow.channel,
            flow.is_active
        ))
        
        connection.commit()
        flow_id = cursor.lastrowid
        
        return {
            "success": True,
            "message": "Automation flow created successfully",
            "flow_id": flow_id
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/flows/list")
async def list_triggered_flows(
    client_id: Optional[int] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get all triggered automation flows"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                tf.flow_id, tf.flow_name, tf.trigger_type, tf.channel,
                tf.is_active, tf.created_at, tf.updated_at,
                u.full_name as client_name,
                creator.full_name as created_by_name,
                COUNT(DISTINCT fe.execution_id) as total_executions
            FROM triggered_flows tf
            JOIN users u ON tf.client_id = u.user_id
            JOIN users creator ON tf.created_by = creator.user_id
            LEFT JOIN flow_executions fe ON tf.flow_id = fe.flow_id
        """
        
        if client_id:
            query += " WHERE tf.client_id = %s"
            query += " GROUP BY tf.flow_id ORDER BY tf.created_at DESC"
            cursor.execute(query, (client_id,))
        else:
            query += " GROUP BY tf.flow_id ORDER BY tf.created_at DESC"
            cursor.execute(query)
        
        flows = cursor.fetchall()
        
        # Convert datetime
        for flow in flows:
            if flow.get('created_at'):
                flow['created_at'] = flow['created_at'].isoformat()
            if flow.get('updated_at'):
                flow['updated_at'] = flow['updated_at'].isoformat()
        
        return {
            "success": True,
            "flows": flows,
            "total": len(flows)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/flows/{flow_id}")
async def get_triggered_flow(
    flow_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get specific triggered flow details"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT tf.*, u.full_name as client_name
            FROM triggered_flows tf
            JOIN users u ON tf.client_id = u.user_id
            WHERE tf.flow_id = %s
        """
        
        cursor.execute(query, (flow_id,))
        flow = cursor.fetchone()
        
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        # Parse JSON fields
        if flow.get('trigger_conditions'):
            flow['trigger_conditions'] = json.loads(flow['trigger_conditions']) if isinstance(flow['trigger_conditions'], str) else flow['trigger_conditions']
        
        if flow.get('flow_actions'):
            flow['flow_actions'] = json.loads(flow['flow_actions']) if isinstance(flow['flow_actions'], str) else flow['flow_actions']
        
        # Convert datetime
        if flow.get('created_at'):
            flow['created_at'] = flow['created_at'].isoformat()
        if flow.get('updated_at'):
            flow['updated_at'] = flow['updated_at'].isoformat()
        
        # Get execution history
        cursor.execute("""
            SELECT execution_id, triggered_at, status, error_message
            FROM flow_executions
            WHERE flow_id = %s
            ORDER BY triggered_at DESC
            LIMIT 10
        """, (flow_id,))
        
        executions = cursor.fetchall()
        for execution in executions:
            if execution.get('triggered_at'):
                execution['triggered_at'] = execution['triggered_at'].isoformat()
        
        flow['recent_executions'] = executions
        
        return {
            "success": True,
            "flow": flow
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/flows/{flow_id}/toggle")
async def toggle_flow_status(
    flow_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Toggle automation flow active/inactive status"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get current status
        cursor.execute("SELECT is_active FROM triggered_flows WHERE flow_id = %s", (flow_id,))
        flow = cursor.fetchone()
        
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        # Toggle status
        new_status = not flow['is_active']
        cursor.execute("""
            UPDATE triggered_flows 
            SET is_active = %s, updated_at = NOW()
            WHERE flow_id = %s
        """, (new_status, flow_id))
        
        connection.commit()
        
        return {
            "success": True,
            "message": f"Flow {'activated' if new_status else 'deactivated'} successfully",
            "is_active": new_status
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


# ========== AUDIENCE SEGMENTATION ==========
@router.post("/segments/create")
async def create_audience_segment(
    segment: AudienceSegmentCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Create a new audience segment with contacts"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert segment
        query = """
            INSERT INTO audience_segments
            (client_id, segment_name, description, platform, segment_criteria, estimated_size, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(query, (
            segment.client_id,
            segment.segment_name,
            segment.description,
            segment.platform,
            json.dumps(segment.segment_criteria),
            segment.estimated_size,
            current_user['user_id']
        ))
        
        segment_id = cursor.lastrowid
        
        # Insert contacts if provided
        if segment.contacts_data and len(segment.contacts_data) > 0:
            contact_query = """
                INSERT INTO segment_contacts
                (segment_id, name, email, phone, company, additional_data, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """
            
            for contact in segment.contacts_data:
                cursor.execute(contact_query, (
                    segment_id,
                    contact.get('name', ''),
                    contact.get('email', ''),
                    contact.get('phone', ''),
                    contact.get('company', ''),
                    json.dumps({k: v for k, v in contact.items() if k not in ['name', 'email', 'phone', 'company']})
                ))
        
        connection.commit()
        
        print(f"✅ Created segment {segment_id} with {segment.estimated_size} contacts")
        
        return {
            "success": True,
            "message": f"Segment created with {segment.estimated_size} contacts",
            "segment_id": segment_id,
            "estimated_size": segment.estimated_size
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error creating segment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@router.get("/segments/list")
async def list_audience_segments(
    client_id: Optional[int] = None,
    platform: Optional[str] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get all audience segments"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                s.segment_id, s.segment_name, s.description, s.platform,
                s.estimated_size, s.created_at,
                u.full_name as client_name,
                creator.full_name as created_by_name
            FROM audience_segments s
            JOIN users u ON s.client_id = u.user_id
            JOIN users creator ON s.created_by = creator.user_id
            WHERE 1=1
        """
        
        params = []
        if client_id:
            query += " AND s.client_id = %s"
            params.append(client_id)
        
        if platform:
            query += " AND s.platform = %s"
            params.append(platform)
        
        query += " ORDER BY s.created_at DESC"
        cursor.execute(query, params if params else None)
        
        segments = cursor.fetchall()
        
        # Convert datetime
        for segment in segments:
            if segment.get('created_at'):
                segment['created_at'] = segment['created_at'].isoformat()
        
        return {
            "success": True,
            "segments": segments,
            "total": len(segments)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== ANALYTICS & METRICS ==========

@router.get("/analytics/overview")
async def get_communication_analytics(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get communication hub analytics overview"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # WhatsApp Stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_campaigns,
                SUM(total_recipients) as total_sent,
                SUM(delivered_count) as total_delivered,
                COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent_count,
                COUNT(CASE WHEN status = 'scheduled' THEN 1 END) as scheduled_count
            FROM whatsapp_campaigns
            WHERE client_id = %s
        """, (client_id,))
        whatsapp_stats = cursor.fetchone()
        
        # Email Stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_campaigns,
                SUM(total_recipients) as total_sent,
                SUM(opened_count) as total_opened,
                SUM(clicked_count) as total_clicked,
                COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent_count,
                COUNT(CASE WHEN status = 'scheduled' THEN 1 END) as scheduled_count
            FROM email_campaigns
            WHERE client_id = %s
        """, (client_id,))
        email_stats = cursor.fetchone()
        
        # Calculate rates
        email_open_rate = 0
        email_click_rate = 0
        if email_stats['total_sent'] and email_stats['total_sent'] > 0:
            email_open_rate = round((email_stats['total_opened'] / email_stats['total_sent']) * 100, 2)
            email_click_rate = round((email_stats['total_clicked'] / email_stats['total_sent']) * 100, 2)
        
        whatsapp_delivery_rate = 0
        if whatsapp_stats['total_sent'] and whatsapp_stats['total_sent'] > 0:
            whatsapp_delivery_rate = round((whatsapp_stats['total_delivered'] / whatsapp_stats['total_sent']) * 100, 2)
        
        # Triggered Flows Stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_flows,
                COUNT(CASE WHEN is_active = TRUE THEN 1 END) as active_flows
            FROM triggered_flows
            WHERE client_id = %s
        """, (client_id,))
        flows_stats = cursor.fetchone()
        
        return {
            "success": True,
            "analytics": {
                "whatsapp": {
                    "total_campaigns": whatsapp_stats['total_campaigns'] or 0,
                    "total_sent": whatsapp_stats['total_sent'] or 0,
                    "total_delivered": whatsapp_stats['total_delivered'] or 0,
                    "delivery_rate": whatsapp_delivery_rate,
                    "sent_count": whatsapp_stats['sent_count'] or 0,
                    "scheduled_count": whatsapp_stats['scheduled_count'] or 0
                },
                "email": {
                    "total_campaigns": email_stats['total_campaigns'] or 0,
                    "total_sent": email_stats['total_sent'] or 0,
                    "total_opened": email_stats['total_opened'] or 0,
                    "total_clicked": email_stats['total_clicked'] or 0,
                    "open_rate": email_open_rate,
                    "click_rate": email_click_rate,
                    "sent_count": email_stats['sent_count'] or 0,
                    "scheduled_count": email_stats['scheduled_count'] or 0
                },
                "flows": {
                    "total_flows": flows_stats['total_flows'] or 0,
                    "active_flows": flows_stats['active_flows'] or 0
                }
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()




@router.get("/segments/{segment_id}")
async def get_segment_details(
    segment_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get specific segment details"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                s.segment_id, s.segment_name, s.description, s.platform,
                s.estimated_size, s.segment_criteria, s.created_at,
                u.full_name as client_name,
                creator.full_name as created_by_name
            FROM audience_segments s
            JOIN users u ON s.client_id = u.user_id
            JOIN users creator ON s.created_by = creator.user_id
            WHERE s.segment_id = %s
        """
        
        cursor.execute(query, (segment_id,))
        segment = cursor.fetchone()
        
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        # Convert datetime
        if segment.get('created_at'):
            segment['created_at'] = segment['created_at'].isoformat()
        
        # Parse segment_criteria if it's a string
        if segment.get('segment_criteria') and isinstance(segment['segment_criteria'], str):
            try:
                segment['segment_criteria'] = json.loads(segment['segment_criteria'])
            except:
                pass
        
        return {
            "success": True,
            "segment": segment
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.delete("/segments/{segment_id}")
async def delete_segment(
    segment_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Delete an audience segment"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if segment exists
        cursor.execute("""
            SELECT segment_id, segment_name 
            FROM audience_segments 
            WHERE segment_id = %s
        """, (segment_id,))
        
        segment = cursor.fetchone()
        
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        # Delete the segment
        cursor.execute("""
            DELETE FROM audience_segments 
            WHERE segment_id = %s
        """, (segment_id,))
        
        connection.commit()
        
        return {
            "success": True,
            "message": f"Segment '{segment['segment_name']}' deleted successfully"
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



@router.get("/segments/{segment_id}/recipients")
async def get_segment_recipients(
    segment_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get recipients from a segment"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get segment details
        cursor.execute("""
            SELECT segment_id, segment_name, platform, estimated_size
            FROM audience_segments
            WHERE segment_id = %s
        """, (segment_id,))
        
        segment = cursor.fetchone()
        
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        # Get contacts from segment_contacts table
        cursor.execute("""
            SELECT contact_id, name, email, phone, company
            FROM segment_contacts
            WHERE segment_id = %s
        """, (segment_id,))
        
        contacts = cursor.fetchall()
        
        # Build recipient list based on platform
        platform = segment.get('platform', 'email').lower()
        recipients = []
        
        for contact in contacts:
            if platform == 'email' or platform == 'both':
                if contact.get('email'):
                    recipients.append(contact['email'])
            elif platform == 'whatsapp':
                if contact.get('phone'):
                    recipients.append(contact['phone'])
            
            # If both platforms, include both email and phone
            if platform == 'both':
                if contact.get('phone'):
                    recipients.append(contact['phone'])
        
        estimated_size = segment.get('estimated_size', len(contacts))
        
        return {
            "success": True,
            "segment_id": segment_id,
            "segment_name": segment['segment_name'],
            "platform": platform,
            "estimated_size": estimated_size,
            "recipients": recipients,
            "total_recipients": len(recipients),
            "contacts": contacts  # Full contact details
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching segment recipients: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()