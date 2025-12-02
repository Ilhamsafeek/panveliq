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


"""
FIXED Analytics Sync Endpoint
Replace the /sync/{client_id} endpoint in app/api/v1/endpoints/analytics.py
"""

@router.post("/sync/{client_id}", summary="Sync analytics data from all modules")
async def sync_analytics_data(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Sync and aggregate analytics data from all modules:
    - Ad campaigns (Module 9)
    - Social media (Module 6)
    - Communication campaigns (Module 4)
    Note: This creates/updates records in analytics_overview table
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Verify client exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s AND role = 'client'", (client_id,))
        client = cursor.fetchone()
        
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        today = date.today()
        last_30_days = today - timedelta(days=30)
        
        # Initialize metrics
        total_ad_spend = 0
        total_impressions = 0
        total_clicks = 0
        total_conversions = 0
        avg_roas = 0
        website_visits = 0
        organic_traffic = 0
        social_engagement = 0
        
        # 1. AGGREGATE AD CAMPAIGN DATA (from ad_campaigns table)
        try:
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(budget), 0) as total_budget,
                    COALESCE(COUNT(*), 0) as campaign_count
                FROM ad_campaigns
                WHERE client_id = %s 
                AND status IN ('active', 'completed')
                AND created_at >= %s
            """, (client_id, last_30_days))
            
            ad_data = cursor.fetchone()
            if ad_data:
                total_ad_spend = float(ad_data['total_budget'] or 0)
        except Exception as e:
            print(f"Warning: Could not fetch ad campaign data: {e}")
        
        # 2. AGGREGATE SOCIAL MEDIA ANALYTICS
        try:
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(impressions), 0) as total_impressions,
                    COALESCE(SUM(engagement_count), 0) as total_engagement,
                    COALESCE(SUM(reach), 0) as total_reach
                FROM social_media_analytics
                WHERE client_id = %s 
                AND metric_date >= %s
            """, (client_id, last_30_days))
            
            social_data = cursor.fetchone()
            if social_data:
                total_impressions += int(social_data['total_impressions'] or 0)
                social_engagement = int(social_data['total_engagement'] or 0)
        except Exception as e:
            print(f"Warning: Could not fetch social media data: {e}")
        
        # 3. AGGREGATE COMMUNICATION CAMPAIGN DATA
        try:
            # WhatsApp campaigns
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total_recipients), 0) as total_sent,
                    COALESCE(SUM(delivered_count), 0) as total_delivered
                FROM whatsapp_campaigns
                WHERE client_id = %s 
                AND status = 'sent'
                AND created_at >= %s
            """, (client_id, last_30_days))
            
            whatsapp_data = cursor.fetchone()
            
            # Email campaigns
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total_recipients), 0) as total_sent,
                    COALESCE(SUM(delivered_count), 0) as total_delivered,
                    COALESCE(SUM(opened_count), 0) as total_opened,
                    COALESCE(SUM(clicked_count), 0) as total_clicked
                FROM email_campaigns
                WHERE client_id = %s 
                AND status = 'sent'
                AND created_at >= %s
            """, (client_id, last_30_days))
            
            email_data = cursor.fetchone()
            if email_data:
                total_clicks += int(email_data['total_clicked'] or 0)
                # Count email opens as website visits
                website_visits += int(email_data['total_opened'] or 0)
        except Exception as e:
            print(f"Warning: Could not fetch communication data: {e}")
        
        # 4. CHECK IF WE HAVE SEO DATA (from seo_metrics table if it exists)
        try:
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(organic_traffic), 0) as total_organic
                FROM seo_metrics
                WHERE client_id = %s 
                AND metric_date >= %s
            """, (client_id, last_30_days))
            
            seo_data = cursor.fetchone()
            if seo_data:
                organic_traffic = int(seo_data['total_organic'] or 0)
        except Exception as e:
            print(f"Warning: SEO metrics table may not exist yet: {e}")
        
        # 5. CALCULATE DERIVED METRICS
        # ROAS calculation (if we have conversions data)
        if total_conversions > 0 and total_ad_spend > 0:
            # Assuming average order value of $100 for demo
            avg_order_value = 100
            total_revenue = total_conversions * avg_order_value
            avg_roas = total_revenue / total_ad_spend
        
        # 6. INSERT/UPDATE INTO analytics_overview TABLE
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
                social_engagement,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
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
            total_ad_spend,
            total_impressions,
            total_clicks,
            total_conversions,
            avg_roas,
            website_visits,
            organic_traffic,
            social_engagement
        ))
        
        connection.commit()
        
        # 7. RETURN SUMMARY
        return {
            "success": True,
            "message": "Analytics data synced successfully",
            "client_id": client_id,
            "sync_date": today.isoformat(),
            "metrics_synced": {
                "total_ad_spend": total_ad_spend,
                "total_impressions": total_impressions,
                "total_clicks": total_clicks,
                "total_conversions": total_conversions,
                "avg_roas": round(avg_roas, 2),
                "website_visits": website_visits,
                "organic_traffic": organic_traffic,
                "social_engagement": social_engagement
            },
            "data_sources": {
                "ad_campaigns": "✓" if total_ad_spend > 0 else "○",
                "social_media": "✓" if total_impressions > 0 else "○",
                "communication": "✓" if total_clicks > 0 or website_visits > 0 else "○",
                "seo": "✓" if organic_traffic > 0 else "○"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error syncing analytics: {error_details}")
        
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



@router.post("/sync-all-platforms", summary="Sync analytics from all external APIs")
async def sync_all_platforms(
    request: dict,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Sync REAL analytics data from all integrated platforms:
    - Google Analytics 4 (GA4) - Website metrics
    - Meta Ads API - Facebook/Instagram ad performance
    - Google Ads API - Google ad performance  
    - Moz API - SEO metrics
    """
    connection = None
    cursor = None
    
    try:
        client_id = request.get('client_id')
        start_date = request.get('start_date')
        end_date = request.get('end_date')
        
        if not client_id:
            raise HTTPException(status_code=400, detail="client_id is required")
        
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get client's API credentials from client_profiles
        cursor.execute("""
            SELECT 
                cp.client_id,
                cp.website_url,
                cp.meta_ad_account_id,
                cp.meta_access_token,
                cp.google_ads_customer_id,
                cp.ga4_property_id,
                cp.business_name,
                cp.moz_access_id
            FROM client_profiles cp
            WHERE cp.client_id = %s
        """, (client_id,))
        
        client_data = cursor.fetchone()
        
        sync_results = {
            "ga4": {"success": False, "message": "Not configured"},
            "meta_ads": {"success": False, "message": "Not configured"},
            "google_ads": {"success": False, "message": "Not configured"},
            "moz": {"success": False, "message": "Not configured"}
        }
        
        # ============================================
        # 1. SYNC META ADS DATA (Facebook/Instagram)
        # ============================================
        try:
            from app.services.meta_ads_service import MetaAdsReportingService
            
            meta_service = MetaAdsReportingService()
            
            # Use client's ad account or default from settings
            ad_account_id = None
            if client_data and client_data.get('meta_ad_account_id'):
                ad_account_id = client_data['meta_ad_account_id']
            elif hasattr(settings, 'META_AD_ACCOUNT_ID') and settings.META_AD_ACCOUNT_ID:
                ad_account_id = settings.META_AD_ACCOUNT_ID
            
            if ad_account_id:
                meta_data = meta_service.get_campaign_performance(
                    ad_account_id=ad_account_id,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if meta_data.get('success'):
                    # Store aggregated data in analytics_overview
                    summary = meta_data.get('summary', {})
                    
                    cursor.execute("""
                        INSERT INTO analytics_overview 
                        (client_id, metric_date, total_ad_spend, total_impressions, 
                         total_clicks, total_conversions, total_roas)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        total_ad_spend = VALUES(total_ad_spend),
                        total_impressions = VALUES(total_impressions),
                        total_clicks = VALUES(total_clicks),
                        total_conversions = VALUES(total_conversions),
                        total_roas = VALUES(total_roas)
                    """, (
                        client_id,
                        end_date,
                        summary.get('total_spend', 0),
                        summary.get('total_impressions', 0),
                        summary.get('total_clicks', 0),
                        summary.get('total_conversions', 0),
                        summary.get('roas', 0)
                    ))
                    
                    # Store campaign-level data
                    for campaign in meta_data.get('campaigns', []):
                        cursor.execute("""
                            INSERT INTO analytics_campaign
                            (client_id, campaign_id, campaign_name, campaign_type, 
                             metric_date, impressions, clicks, ctr, conversions, 
                             spend, roas, platform)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            impressions = VALUES(impressions),
                            clicks = VALUES(clicks),
                            ctr = VALUES(ctr),
                            conversions = VALUES(conversions),
                            spend = VALUES(spend),
                            roas = VALUES(roas)
                        """, (
                            client_id,
                            campaign.get('campaign_id', ''),
                            campaign.get('campaign_name', 'Unknown'),
                            'ads',
                            end_date,
                            int(campaign.get('impressions', 0)),
                            int(campaign.get('clicks', 0)),
                            float(campaign.get('ctr', 0)),
                            int(campaign.get('conversions', 0)),
                            float(campaign.get('spend', 0)),
                            float(campaign.get('roas', 0)),
                            'meta'
                        ))
                    
                    sync_results["meta_ads"] = {
                        "success": True,
                        "message": f"Synced {len(meta_data.get('campaigns', []))} campaigns",
                        "campaigns": len(meta_data.get('campaigns', []))
                    }
                else:
                    sync_results["meta_ads"] = {
                        "success": False,
                        "message": meta_data.get('error', 'Failed to fetch data')
                    }
            else:
                sync_results["meta_ads"] = {
                    "success": False,
                    "message": "No Meta Ad Account ID configured"
                }
                
        except ImportError as e:
            sync_results["meta_ads"] = {"success": False, "message": f"Service not available: {str(e)}"}
        except Exception as e:
            sync_results["meta_ads"] = {"success": False, "message": str(e)}
        
        # ============================================
        # 2. SYNC GOOGLE ADS DATA
        # ============================================
        try:
            from app.services.google_ads_reporting import GoogleAdsReportingService
            
            google_ads_service = GoogleAdsReportingService()
            
            google_data = google_ads_service.get_campaign_performance(
                start_date=start_date,
                end_date=end_date
            )
            
            if google_data.get('success'):
                summary = google_data.get('summary', {})
                
                # Update analytics_overview (add to existing Meta data)
                cursor.execute("""
                    INSERT INTO analytics_overview 
                    (client_id, metric_date, total_ad_spend, total_impressions, 
                     total_clicks, total_conversions)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    total_ad_spend = total_ad_spend + VALUES(total_ad_spend),
                    total_impressions = total_impressions + VALUES(total_impressions),
                    total_clicks = total_clicks + VALUES(total_clicks),
                    total_conversions = total_conversions + VALUES(total_conversions)
                """, (
                    client_id,
                    end_date,
                    summary.get('total_cost', 0),
                    summary.get('total_impressions', 0),
                    summary.get('total_clicks', 0),
                    summary.get('total_conversions', 0)
                ))
                
                # Store Google Ads campaigns
                for campaign in google_data.get('campaigns', []):
                    cursor.execute("""
                        INSERT INTO analytics_campaign
                        (client_id, campaign_id, campaign_name, campaign_type, 
                         metric_date, impressions, clicks, ctr, conversions, 
                         spend, platform)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        impressions = VALUES(impressions),
                        clicks = VALUES(clicks),
                        ctr = VALUES(ctr),
                        conversions = VALUES(conversions),
                        spend = VALUES(spend)
                    """, (
                        client_id,
                        campaign.get('campaign_id', ''),
                        campaign.get('campaign_name', 'Unknown'),
                        'ads',
                        end_date,
                        int(campaign.get('impressions', 0)),
                        int(campaign.get('clicks', 0)),
                        float(campaign.get('ctr', 0)),
                        int(campaign.get('conversions', 0)),
                        float(campaign.get('cost', 0)),
                        'google'
                    ))
                
                sync_results["google_ads"] = {
                    "success": True,
                    "message": f"Synced {len(google_data.get('campaigns', []))} campaigns"
                }
            else:
                sync_results["google_ads"] = {
                    "success": False,
                    "message": google_data.get('error', 'Failed to fetch data')
                }
                
        except ImportError as e:
            sync_results["google_ads"] = {"success": False, "message": f"Service not available: {str(e)}"}
        except Exception as e:
            sync_results["google_ads"] = {"success": False, "message": str(e)}
        
        # ============================================
        # 3. SYNC GOOGLE ANALYTICS 4 DATA
        # ============================================
        try:
            from app.services.google_analytics_service import GoogleAnalyticsService
            
            ga4_service = GoogleAnalyticsService()
            
            # Use client's property ID or default
            property_id = None
            if client_data and client_data.get('ga4_property_id'):
                property_id = client_data['ga4_property_id']
            elif hasattr(settings, 'GA4_PROPERTY_ID') and settings.GA4_PROPERTY_ID:
                property_id = settings.GA4_PROPERTY_ID
            
            if property_id:
                ga4_data = ga4_service.get_website_metrics(
                    start_date=start_date,
                    end_date=end_date
                )
                
                if ga4_data.get('success'):
                    summary = ga4_data.get('summary', {})
                    
                    # Store in ga4_data table
                    cursor.execute("""
                        INSERT INTO ga4_data 
                        (client_id, metric_date, sessions, users, page_views, 
                         bounce_rate, avg_session_duration, conversion_events)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        sessions = VALUES(sessions),
                        users = VALUES(users),
                        page_views = VALUES(page_views),
                        bounce_rate = VALUES(bounce_rate),
                        avg_session_duration = VALUES(avg_session_duration),
                        conversion_events = VALUES(conversion_events)
                    """, (
                        client_id,
                        end_date,
                        summary.get('total_sessions', 0),
                        summary.get('total_users', 0),
                        summary.get('total_pageviews', 0),
                        summary.get('bounce_rate', 0),
                        summary.get('avg_session_duration', 0),
                        summary.get('conversions', 0)
                    ))
                    
                    # Update website_visits in analytics_overview
                    cursor.execute("""
                        INSERT INTO analytics_overview 
                        (client_id, metric_date, website_visits, organic_traffic)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        website_visits = VALUES(website_visits),
                        organic_traffic = VALUES(organic_traffic)
                    """, (
                        client_id,
                        end_date,
                        summary.get('total_sessions', 0),
                        summary.get('organic_sessions', 0)
                    ))
                    
                    sync_results["ga4"] = {
                        "success": True,
                        "message": "Synced GA4 data",
                        "sessions": summary.get('total_sessions', 0)
                    }
                else:
                    sync_results["ga4"] = {
                        "success": False,
                        "message": ga4_data.get('error', 'Failed to fetch data')
                    }
            else:
                sync_results["ga4"] = {
                    "success": False,
                    "message": "No GA4 Property ID configured"
                }
                
        except ImportError as e:
            sync_results["ga4"] = {"success": False, "message": f"Service not available: {str(e)}"}
        except Exception as e:
            sync_results["ga4"] = {"success": False, "message": str(e)}
        
        # ============================================
        # 4. SYNC MOZ SEO DATA
        # ============================================
        try:
            from app.services.moz_api_service import MozAPIService
            
            moz_service = MozAPIService()
            
            website_url = None
            if client_data and client_data.get('website_url'):
                website_url = client_data['website_url']
            
            if website_url:
                moz_data = moz_service.get_url_metrics(website_url)
                
                if moz_data.get('success'):
                    # Update SEO project domain authority
                    cursor.execute("""
                        UPDATE seo_projects 
                        SET current_domain_authority = %s
                        WHERE client_id = %s AND status = 'active'
                    """, (moz_data.get('domain_authority', 0), client_id))
                    
                    sync_results["moz"] = {
                        "success": True,
                        "message": "Synced Moz SEO data",
                        "domain_authority": moz_data.get('domain_authority', 0)
                    }
                else:
                    sync_results["moz"] = {
                        "success": False,
                        "message": moz_data.get('error', 'Failed to fetch data')
                    }
            else:
                sync_results["moz"] = {
                    "success": False,
                    "message": "No website URL configured"
                }
                
        except ImportError as e:
            sync_results["moz"] = {"success": False, "message": f"Service not available: {str(e)}"}
        except Exception as e:
            sync_results["moz"] = {"success": False, "message": str(e)}
        
        # ============================================
        # 5. SYNC SOCIAL MEDIA ENGAGEMENT
        # ============================================
        try:
            cursor.execute("""
                INSERT INTO content_engagement_tracking 
                (client_id, platform, content_format, post_id, caption, 
                 impressions, reach, likes, comments, shares, saves, published_at)
                SELECT 
                    sp.client_id,
                    sp.platform,
                    CASE 
                        WHEN sp.content_type = 'single_image' THEN 'image'
                        WHEN sp.content_type IN ('carousel', 'video', 'reel', 'story') THEN sp.content_type
                        ELSE 'image'
                    END,
                    sp.post_id,
                    LEFT(sp.caption, 500),
                    COALESCE(sma.impressions, 0),
                    COALESCE(sma.reach, 0),
                    COALESCE(FLOOR(sma.engagement_count * 0.7), 0),
                    COALESCE(FLOOR(sma.engagement_count * 0.2), 0),
                    COALESCE(FLOOR(sma.engagement_count * 0.08), 0),
                    COALESCE(FLOOR(sma.engagement_count * 0.02), 0),
                    sp.scheduled_at
                FROM scheduled_posts sp
                LEFT JOIN social_media_analytics sma 
                    ON sp.client_id = sma.client_id 
                    AND sp.platform = sma.platform
                    AND DATE(sp.scheduled_at) = sma.metric_date
                WHERE sp.client_id = %s 
                AND sp.status = 'published'
                ON DUPLICATE KEY UPDATE
                impressions = VALUES(impressions),
                reach = VALUES(reach),
                likes = VALUES(likes),
                comments = VALUES(comments),
                shares = VALUES(shares),
                saves = VALUES(saves)
            """, (client_id,))
            
            # Update social_engagement in analytics_overview
            cursor.execute("""
                UPDATE analytics_overview ao
                SET social_engagement = (
                    SELECT COALESCE(SUM(likes + comments + shares + saves), 0)
                    FROM content_engagement_tracking cet
                    WHERE cet.client_id = ao.client_id
                    AND DATE(cet.published_at) = ao.metric_date
                )
                WHERE ao.client_id = %s
            """, (client_id,))
            
            sync_results["social"] = {"success": True, "message": "Synced social engagement"}
        except Exception as e:
            sync_results["social"] = {"success": False, "message": str(e)}
        
        connection.commit()
        
        # Count successful syncs
        successful_syncs = sum(1 for r in sync_results.values() if r.get('success'))
        
        return {
            "success": True,
            "message": f"Sync completed. {successful_syncs}/{len(sync_results)} platforms synced.",
            "sync_results": sync_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/seo-metrics/{client_id}")
async def get_seo_metrics(
    client_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get current SEO metrics for a client's website"""
    try:
        from app.services.moz_api_service import MozAPIService
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get client website URL
        cursor.execute("""
            SELECT website_url, company_name
            FROM clients 
            WHERE client_id = %s
        """, (client_id,))
        
        client = cursor.fetchone()
        
        if not client or not client.get('website_url'):
            raise HTTPException(
                status_code=404,
                detail="Client website URL not found"
            )
        
        # Initialize Moz service
        moz_service = MozAPIService()
        
        # Get URL metrics
        url_metrics = moz_service.get_url_metrics(client['website_url'])
        
        # Get backlink metrics
        backlink_metrics = moz_service.get_backlink_metrics(client['website_url'])
        
        # Get historical SEO metrics from database
        cursor.execute("""
            SELECT 
                metric_date,
                domain_authority,
                page_authority,
                spam_score,
                backlinks_count,
                referring_domains
            FROM seo_metrics
            WHERE client_id = %s
            ORDER BY metric_date DESC
            LIMIT 30
        """, (client_id,))
        
        historical_metrics = cursor.fetchall()
        
        # Convert datetime to string
        for metric in historical_metrics:
            if metric.get('metric_date'):
                metric['metric_date'] = metric['metric_date'].isoformat()
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "client_name": client['company_name'],
            "website_url": client['website_url'],
            "current_metrics": url_metrics,
            "backlinks": backlink_metrics,
            "historical_data": historical_metrics
        }
        
    except Exception as e:
        logger.error(f"Error fetching SEO metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch SEO metrics: {str(e)}"
        )


@router.post("/competitor-analysis/{client_id}")
async def analyze_competitors(
    client_id: int,
    competitor_urls: List[str],
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Compare client's SEO metrics with competitors
    
    Request body:
    {
        "competitor_urls": ["https://competitor1.com", "https://competitor2.com"]
    }
    """
    try:
        from app.services.moz_api_service import MozAPIService
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get client website URL
        cursor.execute("""
            SELECT website_url, company_name
            FROM clients 
            WHERE client_id = %s
        """, (client_id,))
        
        client = cursor.fetchone()
        
        if not client or not client.get('website_url'):
            raise HTTPException(
                status_code=404,
                detail="Client website URL not found"
            )
        
        # Initialize Moz service
        moz_service = MozAPIService()
        
        # Perform competitor analysis
        analysis = moz_service.get_competitor_analysis(
            domain=client['website_url'],
            competitor_domains=competitor_urls
        )
        
        # Store analysis in database for future reference
        cursor.execute("""
            INSERT INTO competitor_analyses (
                client_id,
                primary_domain,
                competitor_domains,
                analysis_data,
                created_at
            ) VALUES (%s, %s, %s, %s, NOW())
        """, (
            client_id,
            client['website_url'],
            json.dumps(competitor_urls),
            json.dumps(analysis)
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "client_name": client['company_name'],
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Error performing competitor analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze competitors: {str(e)}"
        )


@router.get("/top-pages/{client_id}")
async def get_top_pages(
    client_id: int,
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get top performing pages for client's website"""
    try:
        from app.services.moz_api_service import MozAPIService
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get client website URL
        cursor.execute("""
            SELECT website_url, company_name
            FROM clients 
            WHERE client_id = %s
        """, (client_id,))
        
        client = cursor.fetchone()
        
        if not client or not client.get('website_url'):
            raise HTTPException(
                status_code=404,
                detail="Client website URL not found"
            )
        
        # Initialize Moz service
        moz_service = MozAPIService()
        
        # Get top pages
        top_pages = moz_service.get_top_pages(
            domain=client['website_url'],
            limit=limit
        )
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "client_name": client['company_name'],
            "website_url": client['website_url'],
            "top_pages": top_pages
        }
        
    except Exception as e:
        logger.error(f"Error fetching top pages: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch top pages: {str(e)}"
        )


@router.get("/platform-comparison/{client_id}")
async def get_platform_comparison(
    client_id: int,
    start_date: str,
    end_date: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Compare performance across all advertising platforms
    Meta Ads vs Google Ads
    """
    try:
        from app.services.meta_ads_reporting import MetaAdsReportingService
        from app.services.google_ads_reporting import GoogleAdsReportingService
        
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get client ad account IDs
        cursor.execute("""
            SELECT 
                company_name,
                meta_ad_account_id, 
                google_ads_account_id
            FROM clients 
            WHERE client_id = %s
        """, (client_id,))
        
        client = cursor.fetchone()
        
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        comparison_data = {
            "client_name": client['company_name'],
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            },
            "platforms": []
        }
        
        # Fetch Meta Ads data
        if client.get('meta_ad_account_id'):
            meta_service = MetaAdsReportingService()
            meta_data = meta_service.get_campaign_performance(
                ad_account_id=client['meta_ad_account_id'],
                start_date=start_date,
                end_date=end_date
            )
            
            if meta_data.get('success'):
                comparison_data['platforms'].append({
                    "platform": "Meta Ads",
                    "metrics": meta_data.get('summary', {}),
                    "campaigns_count": len(meta_data.get('campaigns', []))
                })
        
        # Fetch Google Ads data
        if client.get('google_ads_account_id'):
            google_ads_service = GoogleAdsReportingService()
            google_ads_data = google_ads_service.get_campaign_performance(
                start_date=start_date,
                end_date=end_date
            )
            
            if google_ads_data.get('success'):
                comparison_data['platforms'].append({
                    "platform": "Google Ads",
                    "metrics": google_ads_data.get('summary', {}),
                    "campaigns_count": len(google_ads_data.get('campaigns', []))
                })
        
        # Calculate winner for each metric
        if len(comparison_data['platforms']) >= 2:
            comparison_data['winner_analysis'] = {
                "best_roas": self._get_best_platform(comparison_data['platforms'], 'roas'),
                "best_ctr": self._get_best_platform(comparison_data['platforms'], 'average_ctr'),
                "best_conversion_rate": self._get_best_platform(comparison_data['platforms'], 'conversion_rate'),
                "lowest_cost": self._get_best_platform(comparison_data['platforms'], 'total_cost', reverse=True)
            }
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "comparison": comparison_data
        }
        
    except Exception as e:
        logger.error(f"Error comparing platforms: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compare platforms: {str(e)}"
        )


def _get_best_platform(platforms: List[Dict], metric_key: str, reverse: bool = False):
    """Helper function to determine best performing platform for a metric"""
    try:
        platform_metrics = []
        
        for platform in platforms:
            metrics = platform.get('metrics', {})
            value = metrics.get(metric_key, 0)
            
            platform_metrics.append({
                "platform": platform['platform'],
                "value": value
            })
        
        if not platform_metrics:
            return None
        
        # Sort by value
        sorted_platforms = sorted(
            platform_metrics,
            key=lambda x: x['value'],
            reverse=not reverse
        )
        
        return sorted_platforms[0]
        
    except Exception as e:
        logger.error(f"Error determining best platform: {str(e)}")
        return None


@router.get("/performance-alerts/{client_id}")
async def get_performance_alerts(
    client_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get automated performance alerts for underperforming campaigns
    Checks: Low CTR, High CPC, Low ROAS, Declining traffic
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get last 7 days vs previous 7 days
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        two_weeks_ago = today - timedelta(days=14)
        
        # Current week metrics
        cursor.execute("""
            SELECT 
                AVG(total_roas) as avg_roas,
                AVG(total_clicks * 100.0 / NULLIF(total_impressions, 0)) as avg_ctr,
                AVG(total_ad_spend / NULLIF(total_clicks, 0)) as avg_cpc,
                SUM(website_visits) as total_visits
            FROM analytics_overview
            WHERE client_id = %s 
            AND metric_date BETWEEN %s AND %s
        """, (client_id, week_ago, today))
        
        current_week = cursor.fetchone()
        
        # Previous week metrics
        cursor.execute("""
            SELECT 
                AVG(total_roas) as avg_roas,
                AVG(total_clicks * 100.0 / NULLIF(total_impressions, 0)) as avg_ctr,
                AVG(total_ad_spend / NULLIF(total_clicks, 0)) as avg_cpc,
                SUM(website_visits) as total_visits
            FROM analytics_overview
            WHERE client_id = %s 
            AND metric_date BETWEEN %s AND %s
        """, (client_id, two_weeks_ago, week_ago))
        
        previous_week = cursor.fetchone()
        
        alerts = []
        
        # Check for declining ROAS
        if current_week['avg_roas'] and previous_week['avg_roas']:
            roas_change = ((current_week['avg_roas'] - previous_week['avg_roas']) / previous_week['avg_roas']) * 100
            
            if roas_change < -20:
                alerts.append({
                    "type": "warning",
                    "metric": "ROAS",
                    "message": f"ROAS declined by {abs(roas_change):.1f}% in the last week",
                    "current_value": round(float(current_week['avg_roas']), 2),
                    "previous_value": round(float(previous_week['avg_roas']), 2),
                    "recommendation": "Review campaign targeting and ad creative performance"
                })
        
        # Check for low CTR
        if current_week['avg_ctr'] and float(current_week['avg_ctr']) < 1.0:
            alerts.append({
                "type": "alert",
                "metric": "CTR",
                "message": f"Click-through rate is low at {current_week['avg_ctr']:.2f}%",
                "current_value": round(float(current_week['avg_ctr']), 2),
                "recommendation": "Consider refreshing ad copy and creative assets"
            })
        
        # Check for declining traffic
        if current_week['total_visits'] and previous_week['total_visits']:
            traffic_change = ((current_week['total_visits'] - previous_week['total_visits']) / previous_week['total_visits']) * 100
            
            if traffic_change < -15:
                alerts.append({
                    "type": "warning",
                    "metric": "Website Traffic",
                    "message": f"Website traffic declined by {abs(traffic_change):.1f}% in the last week",
                    "current_value": int(current_week['total_visits']),
                    "previous_value": int(previous_week['total_visits']),
                    "recommendation": "Review SEO performance and organic search rankings"
                })
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "alert_count": len(alerts),
            "alerts": alerts,
            "checked_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating performance alerts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate alerts: {str(e)}"
        )


# ========== CONTENT ENGAGEMENT BY FORMAT & PLATFORM ==========
@router.get("/content-engagement/{client_id}", summary="Get content engagement by format and platform")
async def get_content_engagement(
    client_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get content engagement metrics broken down by:
    - Content format (image, video, carousel, text, story, reel)
    - Platform (instagram, facebook, linkedin, twitter)
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
        
        # Get engagement by content format
        cursor.execute("""
            SELECT 
                content_format,
                COUNT(*) as total_posts,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(reach), 0) as total_reach,
                COALESCE(SUM(likes + comments + shares + saves), 0) as total_engagement,
                COALESCE(AVG(CASE WHEN impressions > 0 
                    THEN (likes + comments + shares + saves) * 100.0 / impressions 
                    ELSE 0 END), 0) as avg_engagement_rate
            FROM content_engagement_tracking
            WHERE client_id = %s 
            AND created_at BETWEEN %s AND %s
            GROUP BY content_format
            ORDER BY total_engagement DESC
        """, (client_id, start_date, end_date))
        
        format_engagement = cursor.fetchall()
        
        # Get engagement by platform
        cursor.execute("""
            SELECT 
                platform,
                COUNT(*) as total_posts,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(reach), 0) as total_reach,
                COALESCE(SUM(likes + comments + shares + saves), 0) as total_engagement,
                COALESCE(AVG(CASE WHEN impressions > 0 
                    THEN (likes + comments + shares + saves) * 100.0 / impressions 
                    ELSE 0 END), 0) as avg_engagement_rate
            FROM content_engagement_tracking
            WHERE client_id = %s 
            AND created_at BETWEEN %s AND %s
            GROUP BY platform
            ORDER BY total_engagement DESC
        """, (client_id, start_date, end_date))
        
        platform_engagement = cursor.fetchall()
        
        # Get top performing content
        cursor.execute("""
            SELECT 
                content_id,
                platform,
                content_format,
                caption,
                impressions,
                reach,
                (likes + comments + shares + saves) as engagement,
                CASE WHEN impressions > 0 
                    THEN (likes + comments + shares + saves) * 100.0 / impressions 
                    ELSE 0 END as engagement_rate,
                published_at
            FROM content_engagement_tracking
            WHERE client_id = %s 
            AND created_at BETWEEN %s AND %s
            ORDER BY engagement DESC
            LIMIT 5
        """, (client_id, start_date, end_date))
        
        top_content = cursor.fetchall()
        
        # Convert decimals and dates
        for item in format_engagement:
            item['avg_engagement_rate'] = round(float(item['avg_engagement_rate'] or 0), 2)
            item['total_impressions'] = int(item['total_impressions'] or 0)
            item['total_reach'] = int(item['total_reach'] or 0)
            item['total_engagement'] = int(item['total_engagement'] or 0)
        
        for item in platform_engagement:
            item['avg_engagement_rate'] = round(float(item['avg_engagement_rate'] or 0), 2)
            item['total_impressions'] = int(item['total_impressions'] or 0)
            item['total_reach'] = int(item['total_reach'] or 0)
            item['total_engagement'] = int(item['total_engagement'] or 0)
        
        for item in top_content:
            item['engagement_rate'] = round(float(item['engagement_rate'] or 0), 2)
            item['engagement'] = int(item['engagement'] or 0)
            item['impressions'] = int(item['impressions'] or 0)
            if item.get('published_at'):
                item['published_at'] = item['published_at'].isoformat()
        
        # Determine best performing format and platform
        best_format = format_engagement[0]['content_format'] if format_engagement else None
        best_platform = platform_engagement[0]['platform'] if platform_engagement else None
        
        # Generate recommendation
        recommendation = "Start creating content to see performance insights."
        if format_engagement and platform_engagement:
            recommendation = f"{format_engagement[0]['content_format'].replace('_', ' ').title()} content performs best with {format_engagement[0]['avg_engagement_rate']}% engagement rate. Focus on {platform_engagement[0]['platform'].title()} for highest overall engagement."
        
        return {
            "success": True,
            "client_id": client_id,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "by_format": format_engagement,
            "by_platform": platform_engagement,
            "top_performing_content": top_content,
            "insights": {
                "best_format": best_format,
                "best_platform": best_platform,
                "recommendation": recommendation
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch content engagement: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def generate_content_recommendation(format_data: list, platform_data: list) -> str:
    """Generate AI-like recommendation based on content performance"""
    if not format_data or not platform_data:
        return "Start creating content to see performance insights."
    
    best_format = format_data[0]
    best_platform = platform_data[0]
    
    format_name = best_format['content_format'].replace('_', ' ').title()
    platform_name = best_platform['platform'].title()
    
    return f"{format_name} content performs best with {best_format['avg_engagement_rate']}% engagement rate. Focus on {platform_name} which shows the highest overall engagement."




# ========== SYNC CONTENT ENGAGEMENT DATA ==========
# Add this to the sync_all_platforms endpoint or as a separate endpoint
# in app/api/v1/endpoints/analytics.py

@router.post("/sync-content-engagement/{client_id}", summary="Sync content engagement from posts")
async def sync_content_engagement(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Sync content engagement data from social media posts"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Sync from scheduled_posts to content_engagement_tracking
        cursor.execute("""
            INSERT INTO content_engagement_tracking 
            (client_id, platform, content_format, post_id, caption, 
             impressions, reach, likes, comments, shares, saves, published_at)
            SELECT 
                sp.client_id,
                sp.platform,
                CASE 
                    WHEN sp.content_type = 'single_image' THEN 'image'
                    WHEN sp.content_type IN ('carousel', 'video', 'reel', 'story') THEN sp.content_type
                    ELSE 'image'
                END,
                sp.post_id,
                LEFT(sp.caption, 500),
                COALESCE(sma.impressions, 0),
                COALESCE(sma.reach, 0),
                COALESCE(FLOOR(sma.engagement_count * 0.7), 0),
                COALESCE(FLOOR(sma.engagement_count * 0.2), 0),
                COALESCE(FLOOR(sma.engagement_count * 0.08), 0),
                COALESCE(FLOOR(sma.engagement_count * 0.02), 0),
                sp.scheduled_at
            FROM scheduled_posts sp
            LEFT JOIN social_media_analytics sma 
                ON sp.client_id = sma.client_id 
                AND sp.platform = sma.platform
                AND DATE(sp.scheduled_at) = sma.metric_date
            WHERE sp.client_id = %s 
            AND sp.status = 'published'
            ON DUPLICATE KEY UPDATE
            impressions = VALUES(impressions),
            reach = VALUES(reach),
            likes = VALUES(likes),
            comments = VALUES(comments),
            shares = VALUES(shares),
            saves = VALUES(saves)
        """, (client_id,))
        
        synced_count = cursor.rowcount
        connection.commit()
        
        return {
            "success": True,
            "message": f"Synced {synced_count} content records",
            "synced_count": synced_count
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync content engagement: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# Also update the main sync_all_platforms to include content engagement sync
# Add this call at the end of sync_all_platforms:
#
# # 5. Sync content engagement data
# await sync_content_engagement(client_id, current_user)