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


class TriggeredFlowUpdate(BaseModel):
    """Update triggered automation flow"""
    client_id: Optional[int] = None
    flow_name: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_conditions: Optional[Dict[str, Any]] = None
    flow_actions: Optional[List[Dict[str, Any]]] = None
    channel: Optional[str] = None
    is_active: Optional[bool] = None
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
        
        # Determine correct status based on schedule_type
        if campaign.schedule_type == 'scheduled':
            campaign_status = 'scheduled'
        else:  # immediate
            campaign_status = 'draft'  # Will be updated to 'sent' after API call
        
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
            campaign_status,
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
                # Update status to draft on failure (since 'failed' is not in ENUM)
                cursor.execute("""
                    UPDATE whatsapp_campaigns 
                    SET status = 'draft'
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

@router.put("/whatsapp/campaigns/{campaign_id}")
async def update_whatsapp_campaign(
    campaign_id: int,
    campaign: WhatsAppCampaignCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Update existing WhatsApp campaign"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if campaign exists
        cursor.execute("SELECT campaign_id FROM whatsapp_campaigns WHERE campaign_id = %s", (campaign_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Update campaign
        update_query = """
            UPDATE whatsapp_campaigns
            SET campaign_name = %s,
                template_name = %s,
                message_content = %s,
                recipient_list = %s,
                schedule_type = %s,
                scheduled_at = %s,
                updated_at = NOW()
            WHERE campaign_id = %s
        """
        
        cursor.execute(update_query, (
            campaign.campaign_name,
            campaign.template_name,
            campaign.message_content,
            json.dumps(campaign.recipient_list),
            campaign.schedule_type,
            campaign.scheduled_at,
            campaign_id
        ))
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Campaign updated successfully",
            "campaign_id": campaign_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error updating campaign: {str(e)}")
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
    """Get WhatsApp campaign details"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                wc.*,
                u.full_name as client_name
            FROM whatsapp_campaigns wc
            LEFT JOIN users u ON wc.client_id = u.user_id
            WHERE wc.campaign_id = %s
        """
        cursor.execute(query, (campaign_id,))
        campaign = cursor.fetchone()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Parse recipient_list if it's JSON string
        if campaign.get('recipient_list') and isinstance(campaign['recipient_list'], str):
            campaign['recipient_list'] = json.loads(campaign['recipient_list'])
        
        # Convert datetime
        if campaign.get('created_at'):
            campaign['created_at'] = campaign['created_at'].isoformat()
        if campaign.get('scheduled_at'):
            campaign['scheduled_at'] = campaign['scheduled_at'].isoformat()
        
        return {
            "success": True,
            "campaign": campaign
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching campaign: {str(e)}")
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
            'draft' if campaign.schedule_type == 'scheduled' else 'sent',
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
async def get_flow(flow_id: int, current_user: dict = Depends(require_admin_or_employee)):
    """Get single automation flow details"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT 
                tf.*,
                u.full_name as client_name,
                (SELECT COUNT(*) FROM flow_executions WHERE flow_id = tf.flow_id) as total_executions
            FROM triggered_flows tf
            JOIN users u ON tf.client_id = u.user_id
            WHERE tf.flow_id = %s
        """, (flow_id,))
        
        flow = cursor.fetchone()
        
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        # Parse JSON fields
        if flow.get('trigger_conditions') and isinstance(flow['trigger_conditions'], str):
            try:
                flow['trigger_conditions'] = json.loads(flow['trigger_conditions'])
            except:
                flow['trigger_conditions'] = {}
        
        if flow.get('flow_actions') and isinstance(flow['flow_actions'], str):
            try:
                flow['flow_actions'] = json.loads(flow['flow_actions'])
            except:
                flow['flow_actions'] = []
        
        # Convert datetime to string
        if flow.get('created_at'):
            flow['created_at'] = flow['created_at'].isoformat()
        if flow.get('updated_at'):
            flow['updated_at'] = flow['updated_at'].isoformat()
        
        return {"success": True, "flow": flow}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()



@router.put("/flows/{flow_id}")
async def update_flow(
    flow_id: int,
    flow_data: TriggeredFlowUpdate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Update an existing automation flow"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Check if flow exists
        cursor.execute("SELECT flow_id FROM triggered_flows WHERE flow_id = %s", (flow_id,))
        existing = cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        # Build update query dynamically
        update_fields = []
        values = []
        
        if flow_data.client_id is not None:
            update_fields.append("client_id = %s")
            values.append(flow_data.client_id)
        
        if flow_data.flow_name is not None:
            update_fields.append("flow_name = %s")
            values.append(flow_data.flow_name)
        
        if flow_data.trigger_type is not None:
            update_fields.append("trigger_type = %s")
            values.append(flow_data.trigger_type)
        
        if flow_data.trigger_conditions is not None:
            update_fields.append("trigger_conditions = %s")
            values.append(json.dumps(flow_data.trigger_conditions))
        
        if flow_data.flow_actions is not None:
            update_fields.append("flow_actions = %s")
            values.append(json.dumps(flow_data.flow_actions))
        
        if flow_data.channel is not None:
            update_fields.append("channel = %s")
            values.append(flow_data.channel)
        
        if flow_data.is_active is not None:
            update_fields.append("is_active = %s")
            values.append(flow_data.is_active)
        
        if not update_fields:
            return {"success": True, "message": "No fields to update", "flow_id": flow_id}
        
        # Add updated_at
        update_fields.append("updated_at = NOW()")
        
        # Add flow_id for WHERE clause
        values.append(flow_id)
        
        query = f"UPDATE triggered_flows SET {', '.join(update_fields)} WHERE flow_id = %s"
        cursor.execute(query, values)
        conn.commit()
        
        return {
            "success": True,
            "message": "Flow updated successfully",
            "flow_id": flow_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating flow: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.delete("/flows/{flow_id}")
async def delete_flow(flow_id: int, current_user: dict = Depends(require_admin_or_employee)):
    """Delete an automation flow"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if flow exists
        cursor.execute("SELECT flow_id FROM triggered_flows WHERE flow_id = %s", (flow_id,))
        existing = cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Flow not found")
        
        # Delete flow executions first (foreign key)
        cursor.execute("DELETE FROM flow_executions WHERE flow_id = %s", (flow_id,))
        
        # Delete flow
        cursor.execute("DELETE FROM triggered_flows WHERE flow_id = %s", (flow_id,))
        conn.commit()
        
        return {
            "success": True,
            "message": "Flow deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting flow: {e}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

            

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
        
        # Insert segment with contacts_data
        query = """
            INSERT INTO audience_segments
            (client_id, segment_name, description, platform, segment_criteria, estimated_size, contacts_data, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (
            segment.client_id,
            segment.segment_name,
            segment.description,
            segment.platform,
            json.dumps(segment.segment_criteria),
            segment.estimated_size,
            json.dumps(segment.contacts_data) if segment.contacts_data else None,  # ✅ Save contacts_data as JSON
            current_user['user_id']
        ))
        
        segment_id = cursor.lastrowid
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
async def get_segment(
    segment_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get segment details including contacts"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                s.segment_id,
                s.segment_name,
                s.description,
                s.platform,
                s.segment_criteria,
                s.estimated_size,
                s.contacts_data,
                s.created_at,
                s.client_id,
                u.full_name as client_name
            FROM audience_segments s
            LEFT JOIN users u ON s.client_id = u.user_id
            WHERE s.segment_id = %s
        """
        cursor.execute(query, (segment_id,))
        segment = cursor.fetchone()  # ✅ Already a dictionary!
        
        print(f"📦 Raw segment: {segment}")
        
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        # ✅ Parse JSON fields (segment is already a dict)
        try:
            if segment.get('segment_criteria') and isinstance(segment['segment_criteria'], str):
                segment['segment_criteria'] = json.loads(segment['segment_criteria'])
            elif not segment.get('segment_criteria'):
                segment['segment_criteria'] = {}
        except Exception as e:
            print(f"⚠️ Error parsing segment_criteria: {e}")
            segment['segment_criteria'] = {}
        
        try:
            if segment.get('contacts_data'):
                if isinstance(segment['contacts_data'], str):
                    print(f"📞 Parsing contacts_data: {segment['contacts_data']}")
                    segment['contacts_data'] = json.loads(segment['contacts_data'])
                    print(f"✅ Parsed to: {segment['contacts_data']}")
            else:
                segment['contacts_data'] = []
        except Exception as e:
            print(f"❌ Error parsing contacts_data: {e}")
            segment['contacts_data'] = []
        
        # Convert datetime to string for JSON serialization
        if segment.get('created_at'):
            segment['created_at'] = segment['created_at'].isoformat()
        
        print(f"✅ Returning segment with {len(segment.get('contacts_data', []))} contacts")
        
        return {
            "success": True,
            "segment": segment
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Full error: {error_detail}")
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


@router.post("/whatsapp/test-send")
async def test_whatsapp_send(
    current_user: dict = Depends(require_admin_or_employee)
):
    """Test WhatsApp API connection"""
    import requests
    
    WHATSAPP_API_URL = "https://graph.facebook.com/v17.0/894443070408271/messages"
    WHATSAPP_ACCESS_TOKEN = "EAA6Dz8Sr46MBP9NPIyHKvyJktmDC2kbUBbSFNIjtv2d4ZBXJFcEzx9c06VeQUGFQiwTZBoJlo0L8UThX1wYiCXJxiJXtfuTVj496A9XZCL1cvGoSTjVqBXSR2Lm8MykKE9XZCMJrmn6g51TZAR6Y9ZA6nGTisczzjttNgETiB0SVpNiS6K1fVUL0J6UyctgNbPKHqFptz3gOhqg0UJF66EsMZAaEKi3FMWfaxqSQHPohje2SXkZD"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": "94777140803",
        "type": "text",
        "text": {
            "body": "Test message from PanvelIQ"
        }
    }
    
    try:
        print(f"📞 Sending request to: {WHATSAPP_API_URL}")
        print(f"📞 Payload: {payload}")
        print(f"🔑 Token (first 30 chars): {WHATSAPP_ACCESS_TOKEN[:30]}...")
        
        response = requests.post(WHATSAPP_API_URL, headers=headers, json=payload)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📄 Full Response: {response.text}")
        
        response_data = {}
        try:
            response_data = response.json()
        except:
            response_data = {"raw_text": response.text}
        
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response": response_data,
            "error_details": response_data.get("error", {}) if isinstance(response_data, dict) else None
        }
    except Exception as e:
        import traceback
        print(f"❌ Exception: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e)
        }