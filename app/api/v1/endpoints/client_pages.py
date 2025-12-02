"""
Client Pages API - Complete Implementation
File: app/api/v1/endpoints/client_pages.py
Handles client dashboard endpoints: package, reports, messages, campaigns
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
                cs.status as subscription_status,
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
            AND cs.status = 'active'
            ORDER BY cs.start_date DESC
            LIMIT 1
        """
        
        cursor.execute(query, (current_user['user_id'],))
        subscription = cursor.fetchone()
        
        if not subscription:
            print(f"No active subscription found for user {current_user['user_id']}")
            return {
                "status": "success",
                "has_package": False,
                "package": None,
                "message": "No active package found"
            }
        
        # Parse features JSON
        if subscription.get('features'):
            if isinstance(subscription['features'], str):
                subscription['features'] = json.loads(subscription['features'])
        
        # Calculate days remaining
        days_remaining = 0
        if subscription.get('end_date'):
            end_date = subscription['end_date']
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            today = datetime.now().date()
            days_remaining = (end_date - today).days
        
        # Format dates for JSON response
        if subscription.get('start_date'):
            subscription['start_date'] = subscription['start_date'].isoformat() if hasattr(subscription['start_date'], 'isoformat') else str(subscription['start_date'])
        if subscription.get('end_date'):
            subscription['end_date'] = subscription['end_date'].isoformat() if hasattr(subscription['end_date'], 'isoformat') else str(subscription['end_date'])
        
        subscription['days_remaining'] = days_remaining
        subscription['status'] = subscription['subscription_status']
        
        print(f"Package found for user {current_user['user_id']}: {subscription['package_name']}")
        
        return {
            "status": "success",
            "has_package": True,
            "package": subscription
        }
    
    except Exception as e:
        print(f"Error fetching package: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch package: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

            
@router.get("/my-proposals", summary="Get current user's proposals")
async def get_my_proposals(current_user: dict = Depends(get_current_user)):
    """Get all proposals sent to the current user"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get all proposals for this client
        query = """
            SELECT 
                p.proposal_id,
                p.company_name,
                p.business_type,
                p.budget,
                p.challenges,
                p.target_audience,
                p.existing_presence,
                p.ai_generated_strategy,
                p.competitive_differentiators,
                p.suggested_timeline,
                p.status,
                p.sent_at,
                p.created_at,
                p.updated_at,
                u.full_name as created_by_name,
                u.email as created_by_email
            FROM project_proposals p
            LEFT JOIN users u ON p.created_by = u.user_id
            WHERE p.client_id = %s
            AND p.status IN ('sent', 'accepted', 'rejected')
            ORDER BY p.created_at DESC
        """
        
        cursor.execute(query, (current_user['user_id'],))
        proposals = cursor.fetchall()
        
        # Format dates and parse JSON
        for proposal in proposals:
            if proposal.get('sent_at'):
                proposal['sent_at'] = proposal['sent_at'].isoformat()
            if proposal.get('created_at'):
                proposal['created_at'] = proposal['created_at'].isoformat()
            if proposal.get('updated_at'):
                proposal['updated_at'] = proposal['updated_at'].isoformat()
            
            # Parse JSON fields
            if proposal.get('existing_presence') and isinstance(proposal['existing_presence'], str):
                proposal['existing_presence'] = json.loads(proposal['existing_presence'])
            if proposal.get('ai_generated_strategy') and isinstance(proposal['ai_generated_strategy'], str):
                proposal['ai_generated_strategy'] = json.loads(proposal['ai_generated_strategy'])
            if proposal.get('competitive_differentiators') and isinstance(proposal['competitive_differentiators'], str):
                proposal['competitive_differentiators'] = json.loads(proposal['competitive_differentiators'])
            if proposal.get('suggested_timeline') and isinstance(proposal['suggested_timeline'], str):
                proposal['suggested_timeline'] = json.loads(proposal['suggested_timeline'])
        
        return {
            "status": "success",
            "proposals": proposals,
            "total": len(proposals)
        }
    
    except Exception as e:
        print(f"Error fetching proposals: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch proposals: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/my-proposals/{proposal_id}", summary="Get single proposal details")
async def get_proposal_details(
    proposal_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed view of a specific proposal"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                p.*,
                u.full_name as created_by_name,
                u.email as created_by_email
            FROM project_proposals p
            LEFT JOIN users u ON p.created_by = u.user_id
            WHERE p.proposal_id = %s AND p.client_id = %s
        """
        
        cursor.execute(query, (proposal_id, current_user['user_id']))
        proposal = cursor.fetchone()
        
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )
        
        # Format dates and parse JSON
        if proposal.get('sent_at'):
            proposal['sent_at'] = proposal['sent_at'].isoformat()
        if proposal.get('created_at'):
            proposal['created_at'] = proposal['created_at'].isoformat()
        if proposal.get('updated_at'):
            proposal['updated_at'] = proposal['updated_at'].isoformat()
        
        # Parse JSON fields
        if proposal.get('existing_presence') and isinstance(proposal['existing_presence'], str):
            proposal['existing_presence'] = json.loads(proposal['existing_presence'])
        if proposal.get('ai_generated_strategy') and isinstance(proposal['ai_generated_strategy'], str):
            proposal['ai_generated_strategy'] = json.loads(proposal['ai_generated_strategy'])
        if proposal.get('competitive_differentiators') and isinstance(proposal['competitive_differentiators'], str):
            proposal['competitive_differentiators'] = json.loads(proposal['competitive_differentiators'])
        if proposal.get('suggested_timeline') and isinstance(proposal['suggested_timeline'], str):
            proposal['suggested_timeline'] = json.loads(proposal['suggested_timeline'])
        
        return {
            "status": "success",
            "proposal": proposal
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching proposal details: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch proposal: {str(e)}"
        )
    
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/my-proposals/{proposal_id}/respond", summary="Respond to proposal")
async def respond_to_proposal(
    proposal_id: int,
    response_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Client can accept or reject a proposal"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        action = response_data.get('action')  # 'accept' or 'reject'
        comments = response_data.get('comments', '')
        
        if action not in ['accept', 'reject']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be 'accept' or 'reject'"
            )
        
        new_status = 'accepted' if action == 'accept' else 'rejected'
        
        # Update proposal status
        cursor.execute("""
            UPDATE project_proposals 
            SET status = %s, updated_at = NOW()
            WHERE proposal_id = %s AND client_id = %s
        """, (new_status, proposal_id, current_user['user_id']))
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found"
            )
        
        # Create notification for the employee who created it
        cursor.execute("""
            SELECT created_by FROM project_proposals WHERE proposal_id = %s
        """, (proposal_id,))
        creator = cursor.fetchone()
        
        if creator:
            cursor.execute("""
                INSERT INTO notifications 
                (user_id, notification_type, title, message, is_read, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (
                creator['created_by'],
                f'proposal_{new_status}',
                f'Proposal {new_status.capitalize()}',
                f'Your proposal has been {new_status} by the client. {comments}',
                False
            ))
        
        connection.commit()
        
        return {
            "status": "success",
            "message": f"Proposal {new_status} successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error responding to proposal: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to respond to proposal: {str(e)}"
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


# ========== MESSAGES ENDPOINTS (CORRECTED) ==========

@router.get("/messages", summary="Get client messages")
async def get_client_messages(current_user: dict = Depends(get_current_user)):
    """Get all messages for current client (sent and received)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get messages where client is sender OR receiver
        query = """
            SELECT 
                m.message_id,
                m.subject,
                m.message_body as message,
                m.is_read,
                m.created_at,
                CASE 
                    WHEN m.sender_id = %s THEN 'sent'
                    ELSE 'received'
                END as message_direction,
                CASE 
                    WHEN m.sender_id = %s THEN receiver.full_name
                    ELSE sender.full_name
                END as other_party_name,
                sender.user_id as sender_id,
                sender.full_name as sender_name
            FROM messages m
            JOIN users sender ON m.sender_id = sender.user_id
            JOIN users receiver ON m.receiver_id = receiver.user_id
            WHERE m.sender_id = %s OR m.receiver_id = %s
            ORDER BY m.created_at DESC
            LIMIT 50
        """
        
        cursor.execute(query, (
            current_user['user_id'], 
            current_user['user_id'],
            current_user['user_id'],
            current_user['user_id']
        ))
        messages = cursor.fetchall()
        
        return {
            "status": "success",
            "messages": messages,
            "total": len(messages),
            "unread_count": sum(1 for m in messages if not m['is_read'] and m['message_direction'] == 'received')
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
        
        # Insert into messages table (not notifications)
        query = """
            INSERT INTO messages 
            (sender_id, receiver_id, subject, message_body, is_read, created_at)
            VALUES (%s, %s, %s, %s, FALSE, NOW())
        """
        
        cursor.execute(query, (
            current_user['user_id'],  # sender is current user (client)
            message.recipient_id,      # receiver is selected team member
            message.subject,
            message.message_body
        ))
        
        message_id = cursor.lastrowid
        connection.commit()
        
        print(f"✅ Message sent: ID={message_id}, From={current_user['user_id']}, To={message.recipient_id}")
        
        return {
            "status": "success",
            "message": "Message sent successfully",
            "message_id": message_id
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
            UPDATE messages 
            SET is_read = TRUE 
            WHERE message_id = %s AND receiver_id = %s
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


@router.get("/team-members", summary="Get team members for messaging")
async def get_team_members(current_user: dict = Depends(get_current_user)):
    """Get all team members (assigned employees + admins) that client can message"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        team_members = []
        
        # Get all admins
        cursor.execute("""
            SELECT 
                user_id,
                full_name,
                email,
                role
            FROM users
            WHERE role = 'admin' AND status = 'active'
            ORDER BY full_name
        """)
        
        admins = cursor.fetchall()
        team_members.extend(admins)
        
        # Get assigned employees for this client
        cursor.execute("""
            SELECT 
                u.user_id,
                u.full_name,
                u.email,
                u.role
            FROM employee_assignments ea
            JOIN users u ON ea.employee_id = u.user_id
            WHERE ea.client_id = %s AND u.status = 'active'
            ORDER BY u.full_name
        """, (current_user['user_id'],))
        
        employees = cursor.fetchall()
        team_members.extend(employees)
        
        return {
            "status": "success",
            "team_members": team_members
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch team members: {str(e)}"
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
            spend = float(campaign['total_spend'])
            
            # Calculate CTR
            campaign['ctr'] = round((clicks / impressions * 100), 2) if impressions > 0 else 0
            
            # Calculate CPC
            campaign['cpc'] = round((spend / clicks), 2) if clicks > 0 else 0
        
        return {
            "status": "success",
            "campaigns": campaigns,
            "total": len(campaigns)
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