"""
Unified Analytics Dashboard - Backend API
File: app/api/v1/endpoints/analytics.py
Module 10: Central hub for all analytics – paid, organic, web, and conversion
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import pymysql
import json
from openai import OpenAI

from app.core.config import settings
from app.core.security import require_admin_or_employee, get_current_user, get_db_connection

router = APIRouter()

# Initialize OpenAI for AI insights
try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    print(f"Warning: OpenAI client initialization failed: {e}")
    openai_client = None


# ========== PYDANTIC MODELS ==========

class AnalyticsOverviewResponse(BaseModel):
    success: bool
    client_id: int
    date_range: Dict[str, str]
    overview_metrics: Dict[str, Any]
    daily_metrics: List[Dict[str, Any]]
    ai_insights: Optional[List[Dict[str, str]]] = None


class ConversionFunnelCreate(BaseModel):
    client_id: int
    funnel_name: str
    funnel_stages: List[Dict[str, Any]]


class PerformanceAlertCreate(BaseModel):
    client_id: int
    alert_type: str
    title: str
    description: str


# ========== ANALYTICS OVERVIEW ENDPOINTS ==========

@router.get("/overview/{client_id}", summary="Get comprehensive analytics overview")
async def get_analytics_overview(
    client_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get comprehensive analytics overview for a client
    Aggregates data from ads, SEO, social media, and communication modules
    """
    connection = None
    cursor = None
    
    try:
        # Default to last 30 days if not specified
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Verify client exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (client_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get analytics overview data
        cursor.execute("""
            SELECT 
                metric_date,
                total_ad_spend,
                total_impressions,
                total_clicks,
                total_conversions,
                total_roas,
                website_visits,
                organic_traffic,
                social_engagement
            FROM analytics_overview
            WHERE client_id = %s 
            AND metric_date BETWEEN %s AND %s
            ORDER BY metric_date ASC
        """, (client_id, start_date, end_date))
        
        daily_metrics = cursor.fetchall()
        
        # Convert datetime objects to strings
        for metric in daily_metrics:
            if metric.get('metric_date'):
                metric['metric_date'] = metric['metric_date'].isoformat()
        
        # Calculate aggregate metrics
        cursor.execute("""
            SELECT 
                SUM(total_ad_spend) as total_spend,
                SUM(total_impressions) as total_impressions,
                SUM(total_clicks) as total_clicks,
                SUM(total_conversions) as total_conversions,
                AVG(total_roas) as avg_roas,
                SUM(website_visits) as total_website_visits,
                SUM(organic_traffic) as total_organic_traffic,
                SUM(social_engagement) as total_social_engagement
            FROM analytics_overview
            WHERE client_id = %s 
            AND metric_date BETWEEN %s AND %s
        """, (client_id, start_date, end_date))
        
        aggregates = cursor.fetchone()
        
        # Calculate CTR and conversion rate
        ctr = (float(aggregates['total_clicks']) / float(aggregates['total_impressions']) * 100) if aggregates['total_impressions'] else 0
        conversion_rate = (float(aggregates['total_conversions']) / float(aggregates['total_clicks']) * 100) if aggregates['total_clicks'] else 0
        
        overview_metrics = {
            "total_ad_spend": float(aggregates['total_spend'] or 0),
            "total_impressions": int(aggregates['total_impressions'] or 0),
            "total_clicks": int(aggregates['total_clicks'] or 0),
            "total_conversions": int(aggregates['total_conversions'] or 0),
            "avg_roas": float(aggregates['avg_roas'] or 0),
            "ctr": round(ctr, 2),
            "conversion_rate": round(conversion_rate, 2),
            "total_website_visits": int(aggregates['total_website_visits'] or 0),
            "total_organic_traffic": int(aggregates['total_organic_traffic'] or 0),
            "total_social_engagement": int(aggregates['total_social_engagement'] or 0)
        }
        
        # Generate AI insights if OpenAI is available
        ai_insights = None
        if openai_client and overview_metrics['total_impressions'] > 0:
            ai_insights = await generate_ai_insights(overview_metrics, daily_metrics)
        
        return {
            "success": True,
            "client_id": client_id,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "overview_metrics": overview_metrics,
            "daily_metrics": daily_metrics,
            "ai_insights": ai_insights
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching analytics overview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analytics: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/sync/{client_id}", summary="Sync analytics data from all modules")
async def sync_analytics_data(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Sync and aggregate analytics data from all modules:
    - Ad campaigns (Module 9)
    - SEO data (Module 7)
    - Social media (Module 6)
    - Communication campaigns (Module 4)
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Verify client exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (client_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Client not found")
        
        today = date.today()
        
        # Aggregate ad campaign data
        cursor.execute("""
            SELECT 
                COALESCE(SUM(c.budget), 0) as total_ad_spend,
                COALESCE(SUM(ap.impressions), 0) as total_impressions,
                COALESCE(SUM(ap.clicks), 0) as total_clicks,
                COALESCE(SUM(ap.conversions), 0) as total_conversions,
                COALESCE(AVG(ap.roas), 0) as avg_roas
            FROM ad_campaigns c
            LEFT JOIN ad_performance ap ON c.campaign_id = ap.campaign_id
            WHERE c.client_id = %s 
            AND (ap.metric_date = %s OR ap.metric_date IS NULL)
        """, (client_id, today))
        
        ad_data = cursor.fetchone()
        
        # Aggregate social media data
        cursor.execute("""
            SELECT 
                COALESCE(SUM(engagement_count), 0) as social_engagement
            FROM social_media_analytics
            WHERE client_id = %s 
            AND metric_date = %s
        """, (client_id, today))
        
        social_data = cursor.fetchone()
        
        # Aggregate SEO data (website visits and organic traffic)
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN metric_name = 'organic_traffic' THEN metric_value ELSE 0 END), 0) as organic_traffic,
                COALESCE(SUM(CASE WHEN metric_name = 'total_visits' THEN metric_value ELSE 0 END), 0) as website_visits
            FROM seo_analytics
            WHERE client_id = %s 
            AND metric_date = %s
        """, (client_id, today))
        
        seo_data = cursor.fetchone()
        
        # Insert or update analytics overview
        cursor.execute("""
            INSERT INTO analytics_overview (
                client_id,
                metric_date,
                total_ad_spend,
                total_impressions,
                total_clicks,
                total_conversions,
                total_roas,
                website_visits,
                organic_traffic,
                social_engagement
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                total_ad_spend = VALUES(total_ad_spend),
                total_impressions = VALUES(total_impressions),
                total_clicks = VALUES(total_clicks),
                total_conversions = VALUES(total_conversions),
                total_roas = VALUES(total_roas),
                website_visits = VALUES(website_visits),
                organic_traffic = VALUES(organic_traffic),
                social_engagement = VALUES(social_engagement)
        """, (
            client_id,
            today,
            ad_data['total_ad_spend'],
            ad_data['total_impressions'],
            ad_data['total_clicks'],
            ad_data['total_conversions'],
            ad_data['avg_roas'],
            seo_data['website_visits'],
            seo_data['organic_traffic'],
            social_data['social_engagement']
        ))
        
        connection.commit()
        
        # Check for performance alerts
        await check_and_create_alerts(cursor, connection, client_id, {
            "ad_spend": float(ad_data['total_ad_spend'] or 0),
            "impressions": int(ad_data['total_impressions'] or 0),
            "roas": float(ad_data['avg_roas'] or 0),
            "engagement": int(social_data['social_engagement'] or 0)
        })
        
        return {
            "success": True,
            "message": "Analytics data synced successfully",
            "synced_date": today.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error syncing analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync analytics: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== CONVERSION FUNNEL ENDPOINTS ==========

@router.post("/funnels", summary="Create conversion funnel")
async def create_conversion_funnel(
    funnel: ConversionFunnelCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Create a conversion funnel for tracking drop-offs"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            INSERT INTO conversion_funnels (client_id, funnel_name, funnel_stages)
            VALUES (%s, %s, %s)
        """, (funnel.client_id, funnel.funnel_name, json.dumps(funnel.funnel_stages)))
        
        connection.commit()
        funnel_id = cursor.lastrowid
        
        return {
            "success": True,
            "funnel_id": funnel_id,
            "message": "Conversion funnel created successfully"
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create funnel: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/funnels/{client_id}", summary="Get conversion funnels")
async def get_conversion_funnels(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get all conversion funnels for a client"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT * FROM conversion_funnels
            WHERE client_id = %s
            ORDER BY created_at DESC
        """, (client_id,))
        
        funnels = cursor.fetchall()
        
        # Parse JSON data
        for funnel in funnels:
            if funnel.get('funnel_stages'):
                funnel['funnel_stages'] = json.loads(funnel['funnel_stages']) if isinstance(funnel['funnel_stages'], str) else funnel['funnel_stages']
            if funnel.get('drop_off_analysis'):
                funnel['drop_off_analysis'] = json.loads(funnel['drop_off_analysis']) if isinstance(funnel['drop_off_analysis'], str) else funnel['drop_off_analysis']
            if funnel.get('created_at'):
                funnel['created_at'] = funnel['created_at'].isoformat()
        
        return {
            "success": True,
            "funnels": funnels
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch funnels: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== PERFORMANCE ALERTS ENDPOINTS ==========

@router.get("/alerts/{client_id}", summary="Get performance alerts")
async def get_performance_alerts(
    client_id: int,
    unread_only: bool = False,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get performance alerts for a client"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = "SELECT * FROM performance_alerts WHERE client_id = %s"
        params = [client_id]
        
        if unread_only:
            query += " AND is_read = FALSE"
        
        query += " ORDER BY created_at DESC LIMIT 50"
        
        cursor.execute(query, params)
        alerts = cursor.fetchall()
        
        # Convert datetime
        for alert in alerts:
            if alert.get('created_at'):
                alert['created_at'] = alert['created_at'].isoformat()
        
        return {
            "success": True,
            "alerts": alerts,
            "total_alerts": len(alerts),
            "unread_count": sum(1 for a in alerts if not a['is_read'])
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch alerts: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/alerts/{alert_id}/mark-read", summary="Mark alert as read")
async def mark_alert_read(
    alert_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Mark a performance alert as read"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            UPDATE performance_alerts 
            SET is_read = TRUE 
            WHERE alert_id = %s
        """, (alert_id,))
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Alert marked as read"
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update alert: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== EXPORT ENDPOINTS ==========

@router.get("/export/{client_id}", summary="Export analytics report")
async def export_analytics_report(
    client_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    format: str = "json",  # json, csv, pdf
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Export analytics report in various formats
    Formats: json, csv (future: pdf with charts)
    """
    connection = None
    cursor = None
    
    try:
        # Default to last 30 days
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get comprehensive analytics data
        cursor.execute("""
            SELECT * FROM analytics_overview
            WHERE client_id = %s 
            AND metric_date BETWEEN %s AND %s
            ORDER BY metric_date ASC
        """, (client_id, start_date, end_date))
        
        analytics_data = cursor.fetchall()
        
        # Convert datetime to string
        for row in analytics_data:
            if row.get('metric_date'):
                row['metric_date'] = row['metric_date'].isoformat()
            if row.get('created_at'):
                row['created_at'] = row['created_at'].isoformat()
        
        if format == "csv":
            # Future: Convert to CSV format
            return {
                "success": True,
                "message": "CSV export coming soon",
                "data": analytics_data
            }
        else:  # json
            return {
                "success": True,
                "export_format": "json",
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "data": analytics_data
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export report: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== HELPER FUNCTIONS ==========

async def generate_ai_insights(overview_metrics: Dict, daily_metrics: List[Dict]) -> List[Dict[str, str]]:
    """Generate AI-powered insights from analytics data"""
    try:
        # Prepare data summary for AI
        data_summary = f"""
        Analytics Overview:
        - Total Ad Spend: ${overview_metrics['total_ad_spend']:.2f}
        - Total Impressions: {overview_metrics['total_impressions']:,}
        - Total Clicks: {overview_metrics['total_clicks']:,}
        - CTR: {overview_metrics['ctr']:.2f}%
        - Conversions: {overview_metrics['total_conversions']}
        - Conversion Rate: {overview_metrics['conversion_rate']:.2f}%
        - ROAS: {overview_metrics['avg_roas']:.2f}
        - Website Visits: {overview_metrics['total_website_visits']:,}
        - Organic Traffic: {overview_metrics['total_organic_traffic']:,}
        - Social Engagement: {overview_metrics['total_social_engagement']:,}
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a digital marketing analytics expert. Analyze the data and provide 3-4 actionable insights in a concise, professional manner. Each insight should be specific and data-driven."
                },
                {
                    "role": "user",
                    "content": f"Analyze this marketing performance data and provide actionable insights:\n\n{data_summary}"
                }
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        insights_text = response.choices[0].message.content.strip()
        
        # Parse insights into structured format
        insights = []
        for line in insights_text.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                # Remove numbering/bullets
                clean_line = line.lstrip('0123456789.-•) ').strip()
                if clean_line:
                    insights.append({
                        "type": "recommendation",
                        "message": clean_line
                    })
        
        return insights[:4]  # Return max 4 insights
        
    except Exception as e:
        print(f"Error generating AI insights: {str(e)}")
        return [{
            "type": "info",
            "message": "AI insights temporarily unavailable. Check back later for personalized recommendations."
        }]


async def check_and_create_alerts(cursor, connection, client_id: int, metrics: Dict):
    """Check performance metrics and create alerts for underperformance"""
    try:
        alerts_to_create = []
        
        # Alert: Low ROAS
        if metrics['roas'] > 0 and metrics['roas'] < 2.0:
            alerts_to_create.append({
                "alert_type": "low_roas",
                "title": "Low ROAS Detected",
                "description": f"Your Return on Ad Spend is {metrics['roas']:.2f}, which is below the recommended threshold of 2.0. Consider optimizing your ad targeting or creative."
            })
        
        # Alert: Low impressions with spend
        if metrics['ad_spend'] > 100 and metrics['impressions'] < 1000:
            alerts_to_create.append({
                "alert_type": "low_impressions",
                "title": "Low Impressions",
                "description": f"You've spent ${metrics['ad_spend']:.2f} but only received {metrics['impressions']} impressions. Your ads may not be reaching the right audience."
            })
        
        # Alert: Low social engagement
        if metrics['engagement'] < 50:
            alerts_to_create.append({
                "alert_type": "low_engagement",
                "title": "Low Social Media Engagement",
                "description": f"Social engagement is at {metrics['engagement']}. Consider posting more interactive content or adjusting your posting schedule."
            })
        
        # Insert alerts
        for alert in alerts_to_create:
            # Check if similar alert exists in last 7 days
            cursor.execute("""
                SELECT alert_id FROM performance_alerts
                WHERE client_id = %s 
                AND alert_type = %s
                AND created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
            """, (client_id, alert['alert_type']))
            
            if not cursor.fetchone():  # Only create if no recent alert of same type
                cursor.execute("""
                    INSERT INTO performance_alerts (client_id, alert_type, title, description)
                    VALUES (%s, %s, %s, %s)
                """, (client_id, alert['alert_type'], alert['title'], alert['description']))
        
        connection.commit()
        
    except Exception as e:
        print(f"Error creating alerts: {str(e)}")

    # ========== WEEKLY ANALYTICS AGGREGATION ==========

@router.get("/overview/weekly/{client_id}", summary="Get weekly analytics aggregation")
async def get_weekly_analytics(
    client_id: int,
    weeks: int = 4,  # Last 4 weeks by default
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get weekly aggregated analytics data
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Verify client exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (client_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get weekly data
        cursor.execute("""
            SELECT * FROM analytics_weekly
            WHERE client_id = %s
            ORDER BY week_start_date DESC
            LIMIT %s
        """, (client_id, weeks))
        
        weekly_data = cursor.fetchall()
        
        # Convert dates
        for week in weekly_data:
            if week.get('week_start_date'):
                week['week_start_date'] = week['week_start_date'].isoformat()
            if week.get('week_end_date'):
                week['week_end_date'] = week['week_end_date'].isoformat()
            if week.get('created_at'):
                week['created_at'] = week['created_at'].isoformat()
        
        return {
            "success": True,
            "client_id": client_id,
            "weeks_returned": len(weekly_data),
            "weekly_data": weekly_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch weekly analytics: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== CAMPAIGN-LEVEL ANALYTICS ==========

@router.get("/campaigns/{client_id}", summary="Get campaign-level analytics")
async def get_campaign_analytics(
    client_id: int,
    campaign_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get detailed campaign-level analytics
    Filter by campaign type: ads, email, social, seo
    """
    connection = None
    cursor = None
    
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = """
            SELECT * FROM analytics_campaign
            WHERE client_id = %s 
            AND metric_date BETWEEN %s AND %s
        """
        params = [client_id, start_date, end_date]
        
        if campaign_type:
            query += " AND campaign_type = %s"
            params.append(campaign_type)
        
        query += " ORDER BY metric_date DESC, campaign_type"
        
        cursor.execute(query, params)
        campaigns = cursor.fetchall()
        
        # Convert dates
        for campaign in campaigns:
            if campaign.get('metric_date'):
                campaign['metric_date'] = campaign['metric_date'].isoformat()
            if campaign.get('created_at'):
                campaign['created_at'] = campaign['created_at'].isoformat()
        
        return {
            "success": True,
            "client_id": client_id,
            "campaign_type_filter": campaign_type,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "campaigns": campaigns,
            "total_campaigns": len(campaigns)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch campaign analytics: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== KEYWORD MOVEMENT TRACKING ==========

@router.get("/seo/keyword-movement/{client_id}", summary="Get keyword ranking movement")
async def get_keyword_movement(
    client_id: int,
    days: int = 30,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Track keyword ranking changes over time
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT 
                keyword,
                previous_position,
                current_position,
                position_change,
                change_percentage,
                search_volume,
                tracked_date
            FROM keyword_movement
            WHERE client_id = %s
            AND tracked_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY tracked_date DESC, ABS(position_change) DESC
        """, (client_id, days))
        
        movements = cursor.fetchall()
        
        # Convert dates and categorize movements
        for movement in movements:
            if movement.get('tracked_date'):
                movement['tracked_date'] = movement['tracked_date'].isoformat()
            
            # Add trend indicator
            if movement['position_change'] < 0:
                movement['trend'] = 'up'  # Lower position number = higher ranking
                movement['trend_label'] = f"↑ {abs(movement['position_change'])} positions"
            elif movement['position_change'] > 0:
                movement['trend'] = 'down'
                movement['trend_label'] = f"↓ {movement['position_change']} positions"
            else:
                movement['trend'] = 'stable'
                movement['trend_label'] = "No change"
        
        return {
            "success": True,
            "client_id": client_id,
            "tracking_period_days": days,
            "keyword_movements": movements,
            "total_keywords": len(movements)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch keyword movements: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== HEATMAP DATA ==========

@router.get("/heatmap/{client_id}", summary="Get heatmap interaction data")
async def get_heatmap_data(
    client_id: int,
    page_url: Optional[str] = None,
    days: int = 7,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get heatmap data for user interactions (clicks, scrolls, hovers)
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = """
            SELECT 
                page_url,
                element_selector,
                click_x,
                click_y,
                interaction_type,
                COUNT(*) as interaction_count,
                tracked_date
            FROM heatmap_data
            WHERE client_id = %s
            AND tracked_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        """
        params = [client_id, days]
        
        if page_url:
            query += " AND page_url = %s"
            params.append(page_url)
        
        query += " GROUP BY page_url, element_selector, click_x, click_y, interaction_type, tracked_date"
        query += " ORDER BY interaction_count DESC"
        
        cursor.execute(query, params)
        heatmap_points = cursor.fetchall()
        
        # Convert dates
        for point in heatmap_points:
            if point.get('tracked_date'):
                point['tracked_date'] = point['tracked_date'].isoformat()
        
        return {
            "success": True,
            "client_id": client_id,
            "page_filter": page_url,
            "tracking_period_days": days,
            "heatmap_data": heatmap_points,
            "total_interactions": sum(p['interaction_count'] for p in heatmap_points)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch heatmap data: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== ANOMALY DETECTION ==========

@router.get("/anomalies/{client_id}", summary="Get performance anomalies")
async def get_performance_anomalies(
    client_id: int,
    severity: Optional[str] = None,
    unresolved_only: bool = True,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get detected performance anomalies
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = "SELECT * FROM performance_anomalies WHERE client_id = %s"
        params = [client_id]
        
        if unresolved_only:
            query += " AND is_resolved = FALSE"
        
        if severity:
            query += " AND severity = %s"
            params.append(severity)
        
        query += " ORDER BY severity DESC, detected_date DESC"
        
        cursor.execute(query, params)
        anomalies = cursor.fetchall()
        
        # Convert dates
        for anomaly in anomalies:
            if anomaly.get('detected_date'):
                anomaly['detected_date'] = anomaly['detected_date'].isoformat()
            if anomaly.get('created_at'):
                anomaly['created_at'] = anomaly['created_at'].isoformat()
        
        return {
            "success": True,
            "client_id": client_id,
            "severity_filter": severity,
            "showing_unresolved_only": unresolved_only,
            "anomalies": anomalies,
            "total_anomalies": len(anomalies)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch anomalies: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/detect-anomalies/{client_id}", summary="Run anomaly detection")
async def detect_anomalies(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Detect anomalies in performance metrics using statistical analysis
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get last 30 days of data for baseline
        cursor.execute("""
            SELECT 
                metric_date,
                total_impressions,
                total_clicks,
                total_conversions,
                total_ad_spend,
                website_visits
            FROM analytics_overview
            WHERE client_id = %s
            AND metric_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            ORDER BY metric_date ASC
        """, (client_id,))
        
        historical_data = cursor.fetchall()
        
        if len(historical_data) < 7:
            return {
                "success": False,
                "message": "Not enough historical data for anomaly detection (minimum 7 days required)"
            }
        
        # Calculate statistical baselines and detect anomalies
        anomalies_detected = []
        metrics_to_check = ['total_impressions', 'total_clicks', 'total_conversions', 'total_ad_spend', 'website_visits']
        
        for metric in metrics_to_check:
            values = [float(d[metric] or 0) for d in historical_data]
            
            # Calculate mean and standard deviation
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_dev = variance ** 0.5
            
            # Check today's value
            today_value = values[-1] if values else 0
            
            # Detect if value is outside 2 standard deviations (95% confidence)
            if abs(today_value - mean) > 2 * std_dev and std_dev > 0:
                deviation_pct = ((today_value - mean) / mean * 100) if mean > 0 else 0
                
                # Determine severity
                if abs(deviation_pct) > 50:
                    severity = 'critical'
                elif abs(deviation_pct) > 30:
                    severity = 'high'
                elif abs(deviation_pct) > 15:
                    severity = 'medium'
                else:
                    severity = 'low'
                
                # Insert anomaly
                cursor.execute("""
                    INSERT INTO performance_anomalies 
                    (client_id, metric_name, expected_value, actual_value, deviation_percentage, severity, detected_date)
                    VALUES (%s, %s, %s, %s, %s, %s, CURDATE())
                """, (client_id, metric, mean, today_value, abs(deviation_pct), severity))
                
                anomalies_detected.append({
                    "metric": metric,
                    "expected": round(mean, 2),
                    "actual": round(today_value, 2),
                    "deviation": round(deviation_pct, 2),
                    "severity": severity
                })
        
        connection.commit()
        
        return {
            "success": True,
            "anomalies_detected": len(anomalies_detected),
            "anomalies": anomalies_detected,
            "message": f"Detected {len(anomalies_detected)} anomalies"
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== GOOGLE ANALYTICS 4 INTEGRATION ==========

@router.get("/ga4/{client_id}", summary="Get Google Analytics 4 data")
async def get_ga4_data(
    client_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get Google Analytics 4 data including bounce rate
    """
    connection = None
    cursor = None
    
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT * FROM ga4_data
            WHERE client_id = %s
            AND metric_date BETWEEN %s AND %s
            ORDER BY metric_date DESC
        """, (client_id, start_date, end_date))
        
        ga4_data = cursor.fetchall()
        
        # Convert dates
        for row in ga4_data:
            if row.get('metric_date'):
                row['metric_date'] = row['metric_date'].isoformat()
            if row.get('created_at'):
                row['created_at'] = row['created_at'].isoformat()
        
        # Calculate aggregates
        if ga4_data:
            total_page_views = sum(d['page_views'] or 0 for d in ga4_data)
            avg_bounce_rate = sum(d['bounce_rate'] or 0 for d in ga4_data) / len(ga4_data)
            total_conversions = sum(d['conversion_events'] or 0 for d in ga4_data)
        else:
            total_page_views = 0
            avg_bounce_rate = 0
            total_conversions = 0
        
        return {
            "success": True,
            "client_id": client_id,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "ga4_metrics": ga4_data,
            "summary": {
                "total_page_views": total_page_views,
                "avg_bounce_rate": round(avg_bounce_rate, 2),
                "total_conversions": total_conversions
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch GA4 data: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()