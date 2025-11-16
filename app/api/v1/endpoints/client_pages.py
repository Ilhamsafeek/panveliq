"""
Client Pages API
File: app/api/v1/endpoints/client_pages.py
CREATE THIS NEW FILE
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import pymysql
import json

from app.core.config import settings
from app.core.security import get_current_user
from app.core.security import get_db_connection

router = APIRouter()


# ========== PYDANTIC MODELS ==========

class MessageCreate(BaseModel):
    recipient_id: int
    subject: str
    message_body: str


# ========== MY PACKAGE ENDPOINTS ==========

@router.get("/my-package", summary="Get current user's package")
async def get_my_package(current_user: dict = Depends(get_current_user)):
    """Get current user's subscription package details"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get client's active subscription
        query = """
            SELECT 
                cs.subscription_id,
                cs.start_date,
                cs.end_date,
                cs.status,
                p.package_id,
                p.package_name,
                p.package_tier,
                p.description,
                p.price,
                p.billing_cycle,
                p.features
            FROM client_subscriptions cs
            INNER JOIN packages p ON cs.package_id = p.package_id
            WHERE cs.client_id = %s
            ORDER BY cs.start_date DESC
            LIMIT 1
        """
        
        cursor.execute(query, (current_user['user_id'],))
        subscription = cursor.fetchone()
        
        if not subscription:
            return {
                "status": "success",
                "has_package": False,
                "message": "No active package found"
            }
        
        # Parse features JSON
        if subscription['features'] and isinstance(subscription['features'], str):
            subscription['features'] = json.loads(subscription['features'])
        
        # Calculate days remaining
        if subscription['end_date']:
            days_remaining = (subscription['end_date'] - datetime.now().date()).days
            subscription['days_remaining'] = max(0, days_remaining)
        
        return {
            "status": "success",
            "has_package": True,
            "package": subscription
        }
    
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


# ========== REPORTS ENDPOINTS ==========

@router.get("/reports", summary="Get client reports")
async def get_client_reports(current_user: dict = Depends(get_current_user)):
    """Get all reports for current client"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get campaign data with aggregated performance
        query = """
            SELECT 
                'campaign' as report_type,
                ac.campaign_id as reference_id,
                ac.campaign_name as title,
                ac.created_at as report_date,
                COALESCE(SUM(ap.impressions), 0) as impressions,
                COALESCE(SUM(ap.clicks), 0) as clicks,
                COALESCE(SUM(ap.conversions), 0) as conversions,
                COALESCE(SUM(ap.spend), 0) as spend
            FROM ad_campaigns ac
            LEFT JOIN ads a ON ac.campaign_id = a.campaign_id
            LEFT JOIN ad_performance ap ON a.ad_id = ap.ad_id
            WHERE ac.client_id = %s
            GROUP BY ac.campaign_id, ac.campaign_name, ac.created_at
            ORDER BY ac.created_at DESC
            LIMIT 10
        """
        
        cursor.execute(query, (current_user['user_id'],))
        raw_reports = cursor.fetchall()
        
        # Format reports with metrics object
        reports = []
        for report in raw_reports:
            reports.append({
                'report_type': report['report_type'],
                'reference_id': report['reference_id'],
                'title': report['title'],
                'report_date': report['report_date'],
                'metrics': {
                    'impressions': int(report['impressions']),
                    'clicks': int(report['clicks']),
                    'conversions': int(report['conversions']),
                    'spend': float(report['spend'])
                }
            })
        
        return {
            "status": "success",
            "reports": reports,
            "total": len(reports)
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch reports: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== MESSAGES ENDPOINTS ==========

@router.get("/messages", summary="Get client messages")
async def get_client_messages(current_user: dict = Depends(get_current_user)):
    """Get all messages for current client"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get messages (sent and received)
        query = """
            SELECT 
                n.notification_id as message_id,
                n.notification_type as message_type,
                n.title as subject,
                n.message,
                n.is_read,
                n.created_at,
                u.full_name as sender_name,
                u.user_id as sender_id
            FROM notifications n
            LEFT JOIN users u ON n.user_id = u.user_id
            WHERE n.user_id = %s
            ORDER BY n.created_at DESC
            LIMIT 50
        """
        
        cursor.execute(query, (current_user['user_id'],))
        messages = cursor.fetchall()
        
        return {
            "status": "success",
            "messages": messages,
            "total": len(messages),
            "unread_count": sum(1 for m in messages if not m['is_read'])
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch messages: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/messages/send", summary="Send a message")
async def send_message(
    message: MessageCreate,
    current_user: dict = Depends(get_current_user)
):
    """Send a message to team member"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert notification
        query = """
            INSERT INTO notifications 
            (user_id, notification_type, title, message)
            VALUES (%s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            message.recipient_id,
            'client_message',
            message.subject,
            message.message_body
        ))
        
        connection.commit()
        
        return {
            "status": "success",
            "message": "Message sent successfully"
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/messages/{message_id}/read", summary="Mark message as read")
async def mark_message_read(
    message_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Mark a message as read"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            UPDATE notifications 
            SET is_read = TRUE 
            WHERE notification_id = %s AND user_id = %s
        """
        
        cursor.execute(query, (message_id, current_user['user_id']))
        connection.commit()
        
        return {
            "status": "success",
            "message": "Message marked as read"
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update message: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== CAMPAIGNS ENDPOINTS ==========

@router.get("/campaigns", summary="Get client campaigns")
async def get_client_campaigns(current_user: dict = Depends(get_current_user)):
    """Get all campaigns for current client"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get ad campaigns with aggregated performance
        query = """
            SELECT 
                ac.campaign_id,
                ac.campaign_name,
                ac.platform,
                ac.status,
                ac.start_date,
                ac.end_date,
                ac.budget,
                ac.created_at,
                COALESCE(SUM(ap.impressions), 0) as total_impressions,
                COALESCE(SUM(ap.clicks), 0) as total_clicks,
                COALESCE(SUM(ap.conversions), 0) as total_conversions,
                COALESCE(SUM(ap.spend), 0) as total_spend
            FROM ad_campaigns ac
            LEFT JOIN ads a ON ac.campaign_id = a.campaign_id
            LEFT JOIN ad_performance ap ON a.ad_id = ap.ad_id
            WHERE ac.client_id = %s
            GROUP BY ac.campaign_id
            ORDER BY ac.created_at DESC
        """
        
        cursor.execute(query, (current_user['user_id'],))
        campaigns = cursor.fetchall()
        
        # Calculate metrics for each campaign
        for campaign in campaigns:
            impressions = int(campaign['total_impressions'])
            clicks = int(campaign['total_clicks'])
            conversions = int(campaign['total_conversions'])
            spend = float(campaign['total_spend'])
            
            # Calculate CTR
            if impressions > 0:
                campaign['ctr'] = round((clicks / impressions) * 100, 2)
            else:
                campaign['ctr'] = 0
            
            # Calculate conversion rate
            if clicks > 0:
                campaign['conversion_rate'] = round((conversions / clicks) * 100, 2)
            else:
                campaign['conversion_rate'] = 0
            
            # Calculate cost per conversion
            if spend > 0 and conversions > 0:
                campaign['cost_per_conversion'] = round(spend / conversions, 2)
            else:
                campaign['cost_per_conversion'] = 0
        
        # Get counts by status
        active_count = sum(1 for c in campaigns if c['status'] == 'active')
        paused_count = sum(1 for c in campaigns if c['status'] == 'paused')
        completed_count = sum(1 for c in campaigns if c['status'] == 'completed')
        
        return {
            "status": "success",
            "campaigns": campaigns,
            "total": len(campaigns),
            "counts": {
                "active": active_count,
                "paused": paused_count,
                "completed": completed_count
            }
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch campaigns: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/campaigns/{campaign_id}", summary="Get campaign details")
async def get_campaign_details(
    campaign_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed information for a specific campaign"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                ac.*,
                u.full_name as created_by_name
            FROM ad_campaigns ac
            LEFT JOIN users u ON ac.created_by = u.user_id
            WHERE ac.campaign_id = %s AND ac.client_id = %s
        """
        
        cursor.execute(query, (campaign_id, current_user['user_id']))
        campaign = cursor.fetchone()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Parse JSON fields
        if campaign.get('target_audience') and isinstance(campaign['target_audience'], str):
            campaign['target_audience'] = json.loads(campaign['target_audience'])
        
        if campaign.get('placement_settings') and isinstance(campaign['placement_settings'], str):
            campaign['placement_settings'] = json.loads(campaign['placement_settings'])
        
        return {
            "status": "success",
            "campaign": campaign
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch campaign details: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()