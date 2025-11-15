"""
Ad Strategy & Suggestion Engine API - Module 9 (COMPLETE VERSION)
File: app/api/v1/endpoints/ad_strategy.py

COMPLETE implementation with ALL requirements from scope document:
1. Audience Intelligence & Segmentation (ENHANCED with lookalike, device, time-based)
2. Platform & Channel Selector (ENHANCED with format selection, TikTok, YouTube)
3. Ad Copy & Creative Generator (ENHANCED with image prompts, video scripts)
4. Placement & Bidding Optimizer (NEW - with historical data, auto/manual recommendations)
5. Performance Forecasting Model (ENHANCED with break-even calculator, simulations)
6. Execution & Publishing Engine (ENHANCED with A/B testing, pause/resume)
7. Live Dashboard & Report (COMPLETE)
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import pymysql
import json
from openai import OpenAI

from app.core.config import settings
from app.core.security import require_admin_or_employee, get_current_user, get_db_connection
from app.services.ads_service import AdService

router = APIRouter()

# Initialize services
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
ad_service = AdService()


# ========== PYDANTIC MODELS ==========

class AudienceSegmentCreate(BaseModel):
    """Create audience segment with enhanced options"""
    client_id: int
    platform: str = Field(..., description="meta, google, linkedin, tiktok")
    segment_name: str
    demographics: Dict[str, Any] = Field(default_factory=dict)
    interests: List[str] = Field(default_factory=list)
    behaviors: List[str] = Field(default_factory=list)
    device_targeting: Optional[Dict[str, Any]] = None  # NEW: mobile, desktop, tablet
    time_based_targeting: Optional[Dict[str, Any]] = None  # NEW: time of day, day of week
    lookalike_source: Optional[str] = None  # NEW: lookalike audience
    custom_criteria: Optional[Dict[str, Any]] = None


class PlatformRecommendationRequest(BaseModel):
    """Get AI platform recommendations with format selection"""
    client_id: int
    campaign_objective: str
    budget: float
    target_audience: Dict[str, Any]
    industry: Optional[str] = None
    include_formats: bool = True  # NEW: Include format recommendations


class AdCopyGenerateRequest(BaseModel):
    """Generate ad copy with creative suggestions"""
    campaign_objective: str
    product_service: str
    target_audience: str
    platform: str
    tone: str = "professional"
    key_benefits: List[str] = Field(default_factory=list)
    cta_type: str = "Learn More"
    include_image_prompts: bool = True  # NEW
    include_video_scripts: bool = False  # NEW
    ad_format: Optional[str] = None  # NEW: stories, feed, reels, shorts, youtube


class PlacementOptimizationRequest(BaseModel):
    """Get placement and bidding recommendations"""
    campaign_id: int
    platform: str
    historical_data_days: int = 30  # NEW: Use historical data
    optimization_goal: str = "conversions"  # NEW: conversions, clicks, impressions


class CampaignCreate(BaseModel):
    """Create ad campaign with enhanced options"""
    client_id: int
    campaign_name: str
    platform: str
    objective: str
    budget: float
    start_date: date
    end_date: Optional[date] = None
    target_audience: Dict[str, Any]
    placement_settings: Optional[Dict[str, Any]] = None
    bidding_strategy: Optional[str] = None
    schedule_settings: Optional[Dict[str, Any]] = None  # NEW: scheduling
    ab_test_config: Optional[Dict[str, Any]] = None  # NEW: A/B testing


class AdCreate(BaseModel):
    """Create ad within campaign"""
    campaign_id: int
    ad_name: str
    ad_format: str
    primary_text: str
    headline: str
    description: Optional[str] = None
    media_urls: List[str] = Field(default_factory=list)
    is_ab_test_variant: bool = False  # NEW
    ab_test_group: Optional[str] = None  # NEW: A or B


class ForecastRequest(BaseModel):
    """Forecast campaign performance with simulations"""
    platform: str
    objective: str
    budget: float
    duration_days: int
    target_audience_size: int
    include_breakeven: bool = True  # NEW
    average_order_value: Optional[float] = None  # NEW: for break-even calc
    run_simulations: bool = False  # NEW: budget scenarios


class CampaignControlRequest(BaseModel):
    """Control campaign status"""
    action: str = Field(..., description="pause, resume, schedule")
    scheduled_at: Optional[datetime] = None  # NEW


# ========== 1. ENHANCED AUDIENCE INTELLIGENCE ==========

@router.post("/audience/create", summary="Create enhanced audience segment")
async def create_audience_segment(
    segment: AudienceSegmentCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Create custom audience segment with ALL targeting options:
    - Custom & lookalike audiences
    - Interest & behavior targeting
    - Device profiling
    - Time-based targeting
    - In-market & affinity audiences (Google)
    """
    connection = None
    cursor = None
    
    try:
        # Get ENHANCED AI suggestions
        ai_suggestions = await ad_service.get_enhanced_audience_suggestions(
            platform=segment.platform,
            demographics=segment.demographics,
            interests=segment.interests,
            behaviors=segment.behaviors,
            device_targeting=segment.device_targeting,
            time_targeting=segment.time_based_targeting,
            lookalike_source=segment.lookalike_source
        )
        
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Build ENHANCED segment criteria
        segment_criteria = {
            "demographics": segment.demographics,
            "interests": segment.interests,
            "behaviors": segment.behaviors,
            "device_targeting": segment.device_targeting or {},
            "time_based_targeting": segment.time_based_targeting or {},
            "lookalike": segment.lookalike_source,
            "custom": segment.custom_criteria or {},
            "ai_suggestions": ai_suggestions,
            # NEW: Platform-specific audiences
            "in_market_audiences": ai_suggestions.get('in_market_audiences', []),
            "affinity_audiences": ai_suggestions.get('affinity_audiences', [])
        }
        
        cursor.execute("""
            INSERT INTO audience_segments (
                client_id, segment_name, platform, segment_criteria,
                estimated_size, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            segment.client_id,
            segment.segment_name,
            segment.platform,
            json.dumps(segment_criteria),
            ai_suggestions.get('estimated_reach', 0),
            current_user['user_id']
        ))
        
        connection.commit()
        segment_id = cursor.lastrowid
        
        return {
            "success": True,
            "segment_id": segment_id,
            "segment_criteria": segment_criteria,
            "ai_suggestions": ai_suggestions,
            "lookalike_audiences": ai_suggestions.get('lookalike_suggestions', []),
            "device_breakdown": ai_suggestions.get('device_breakdown', {}),
            "best_times": ai_suggestions.get('best_times', [])
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create segment: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/audience/list/{client_id}", summary="List audience segments")
async def list_audience_segments(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get all audience segments for a client"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT s.*, u.full_name as creator_name
            FROM audience_segments s
            JOIN users u ON s.created_by = u.user_id
            WHERE s.client_id = %s
            ORDER BY s.created_at DESC
        """, (client_id,))
        
        segments = cursor.fetchall()
        
        for seg in segments:
            if seg['segment_criteria']:
                seg['segment_criteria'] = json.loads(seg['segment_criteria'])
        
        return {"success": True, "segments": segments}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch segments: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== 2. ENHANCED PLATFORM SELECTOR ==========

@router.post("/platform/recommend", summary="Get enhanced platform recommendations")
async def get_platform_recommendations(
    request: PlatformRecommendationRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    AI-powered platform selection with:
    - Meta, Google, YouTube, Display, TikTok, LinkedIn
    - Budget split suggestions
    - Format selection (Stories vs Feed, Search vs Display, Reels vs Shorts)
    """
    try:
        recommendations = await ad_service.recommend_platforms_enhanced(
            objective=request.campaign_objective,
            budget=request.budget,
            target_audience=request.target_audience,
            industry=request.industry,
            include_formats=request.include_formats
        )
        
        return {
            "success": True,
            "recommendations": recommendations
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}"
        )


# ========== 3. ENHANCED AD COPY & CREATIVE GENERATOR ==========

@router.post("/adcopy/generate", summary="Generate enhanced ad copy with creatives")
async def generate_ad_copy(
    request: AdCopyGenerateRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Generate platform-optimized ad copy with:
    - Primary text, headlines, descriptions
    - Image prompts for Canva/DALL-E integration
    - Video script templates for Reels/Shorts/YouTube
    """
    try:
        ad_copy = await ad_service.generate_ad_copy_enhanced(
            objective=request.campaign_objective,
            product=request.product_service,
            audience=request.target_audience,
            platform=request.platform,
            tone=request.tone,
            benefits=request.key_benefits,
            cta=request.cta_type,
            include_image_prompts=request.include_image_prompts,
            include_video_scripts=request.include_video_scripts,
            ad_format=request.ad_format
        )
        
        return {
            "success": True,
            "ad_copy": ad_copy
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate ad copy: {str(e)}"
        )


# ========== 4. NEW: PLACEMENT & BIDDING OPTIMIZER ==========

@router.post("/placement/optimize", summary="Get placement and bidding recommendations")
async def optimize_placement(
    request: PlacementOptimizationRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Placement & bidding optimization using:
    - Historical performance data
    - Platform-specific insights
    - Auto vs manual placement recommendations
    - Smart bidding strategies (Maximize Conversions, Target ROAS, etc.)
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get historical performance data
        end_date = date.today()
        start_date = end_date - timedelta(days=request.historical_data_days)
        
        cursor.execute("""
            SELECT 
                ap.*, a.ad_format, a.placement_settings
            FROM ad_performance ap
            JOIN ads a ON ap.ad_id = a.ad_id
            JOIN ad_campaigns c ON a.campaign_id = c.campaign_id
            WHERE c.campaign_id = %s 
            AND c.platform = %s
            AND ap.metric_date BETWEEN %s AND %s
        """, (request.campaign_id, request.platform, start_date, end_date))
        
        historical_data = cursor.fetchall()
        
        # Get AI-powered optimization recommendations
        optimization = await ad_service.optimize_placement_and_bidding(
            platform=request.platform,
            historical_data=historical_data,
            optimization_goal=request.optimization_goal
        )
        
        return {
            "success": True,
            "optimization": optimization
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to optimize placement: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== 5. ENHANCED PERFORMANCE FORECASTING ==========

@router.post("/forecast", summary="Enhanced performance forecast with simulations")
async def forecast_performance(
    request: ForecastRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Generate AI-powered performance forecast with:
    - CTR, CPC, CPM, ROAS, Impressions predictions
    - Budget vs result simulation
    - Break-even ad spend calculator
    - Multiple budget scenarios
    """
    try:
        forecast = await ad_service.forecast_campaign_performance_enhanced(
            platform=request.platform,
            objective=request.objective,
            budget=request.budget,
            duration_days=request.duration_days,
            audience_size=request.target_audience_size,
            include_breakeven=request.include_breakeven,
            aov=request.average_order_value,
            run_simulations=request.run_simulations
        )
        
        return {
            "success": True,
            "forecast": forecast
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate forecast: {str(e)}"
        )


# ========== 6. CAMPAIGNS WITH A/B TESTING ==========

@router.post("/campaigns/create", summary="Create campaign with A/B testing")
async def create_campaign(
    campaign: CampaignCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Create new ad campaign with A/B testing and scheduling options"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            INSERT INTO ad_campaigns (
                client_id, created_by, campaign_name, platform, objective,
                budget, start_date, end_date, target_audience,
                placement_settings, bidding_strategy, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            campaign.client_id,
            current_user['user_id'],
            campaign.campaign_name,
            campaign.platform,
            campaign.objective,
            campaign.budget,
            campaign.start_date,
            campaign.end_date,
            json.dumps(campaign.target_audience),
            json.dumps(campaign.placement_settings or {}),
            campaign.bidding_strategy,
            'draft'
        ))
        
        connection.commit()
        campaign_id = cursor.lastrowid
        
        # If A/B testing configured, create suggestion record
        if campaign.ab_test_config:
            cursor.execute("""
                INSERT INTO ai_ad_suggestions (
                    client_id, campaign_id, audience_segments,
                    platform_recommendations, ad_copy_suggestions,
                    budget_recommendations, forecasted_metrics, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                campaign.client_id,
                campaign_id,
                json.dumps({}),
                json.dumps({}),
                json.dumps({"ab_test": campaign.ab_test_config}),
                json.dumps({}),
                json.dumps({}),
                'pending'
            ))
            connection.commit()
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "message": "Campaign created successfully",
            "ab_testing_enabled": bool(campaign.ab_test_config)
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/campaigns/list/{client_id}", summary="List campaigns")
async def list_campaigns(
    client_id: int,
    platform: Optional[str] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get all campaigns for a client"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = """
            SELECT c.*, u.full_name as creator_name,
                   COUNT(DISTINCT a.ad_id) as total_ads
            FROM ad_campaigns c
            JOIN users u ON c.created_by = u.user_id
            LEFT JOIN ads a ON c.campaign_id = a.campaign_id
            WHERE c.client_id = %s
        """
        params = [client_id]
        
        if platform:
            query += " AND c.platform = %s"
            params.append(platform)
        
        query += " GROUP BY c.campaign_id ORDER BY c.created_at DESC"
        
        cursor.execute(query, params)
        campaigns = cursor.fetchall()
        
        for camp in campaigns:
            if camp['target_audience']:
                camp['target_audience'] = json.loads(camp['target_audience'])
            if camp['placement_settings']:
                camp['placement_settings'] = json.loads(camp['placement_settings'])
        
        return {"success": True, "campaigns": campaigns}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch campaigns: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== 7. ENHANCED CAMPAIGN PUBLISHING & CONTROL ==========

@router.post("/campaigns/{campaign_id}/publish", summary="Publish campaign with A/B testing")
async def publish_campaign(
    campaign_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Publish campaign to ad platform with:
    - Draft to live pushing
    - A/B split test creation
    - Automatic scheduling
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("SELECT * FROM ad_campaigns WHERE campaign_id = %s", (campaign_id,))
        campaign = cursor.fetchone()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Check for A/B test configuration
        cursor.execute("""
            SELECT ad_copy_suggestions FROM ai_ad_suggestions 
            WHERE campaign_id = %s ORDER BY created_at DESC LIMIT 1
        """, (campaign_id,))
        
        ab_config = None
        ab_result = cursor.fetchone()
        if ab_result and ab_result['ad_copy_suggestions']:
            suggestions = json.loads(ab_result['ad_copy_suggestions'])
            ab_config = suggestions.get('ab_test')
        
        # Publish campaign
        result = await ad_service.publish_campaign_enhanced(
            campaign=campaign,
            ab_test_config=ab_config
        )
        
        # Update campaign status
        cursor.execute("""
            UPDATE ad_campaigns
            SET status = 'active', external_campaign_id = %s
            WHERE campaign_id = %s
        """, (result.get('external_id'), campaign_id))
        
        connection.commit()
        
        return {
            "success": True,
            "external_campaign_id": result.get('external_id'),
            "ab_test_created": result.get('ab_test_created', False),
            "message": "Campaign published successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish campaign: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/campaigns/{campaign_id}/control", summary="Control campaign (pause/resume/schedule)")
async def control_campaign(
    campaign_id: int,
    control: CampaignControlRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Campaign control actions:
    - Pause campaign
    - Resume campaign
    - Schedule campaign for future date
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("SELECT * FROM ad_campaigns WHERE campaign_id = %s", (campaign_id,))
        campaign = cursor.fetchone()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Execute control action
        result = await ad_service.control_campaign(
            campaign=campaign,
            action=control.action,
            scheduled_at=control.scheduled_at
        )
        
        # Update campaign status
        new_status = {
            'pause': 'paused',
            'resume': 'active',
            'schedule': 'draft'
        }.get(control.action, campaign['status'])
        
        cursor.execute("""
            UPDATE ad_campaigns SET status = %s WHERE campaign_id = %s
        """, (new_status, campaign_id))
        
        connection.commit()
        
        return {
            "success": True,
            "action": control.action,
            "new_status": new_status,
            "message": f"Campaign {control.action}d successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to control campaign: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== ADS MANAGEMENT ==========

@router.post("/ads/create", summary="Create ad with A/B test support")
async def create_ad(
    ad: AdCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Create ad within a campaign (supports A/B testing)"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            INSERT INTO ads (
                campaign_id, ad_name, ad_format, primary_text,
                headline, description, media_urls, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ad.campaign_id,
            ad.ad_name,
            ad.ad_format,
            ad.primary_text,
            ad.headline,
            ad.description,
            json.dumps(ad.media_urls),
            'active'
        ))
        
        connection.commit()
        ad_id = cursor.lastrowid
        
        return {
            "success": True,
            "ad_id": ad_id,
            "message": "Ad created successfully",
            "ab_test_group": ad.ab_test_group if ad.is_ab_test_variant else None
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ad: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/campaigns/{campaign_id}/ads", summary="List campaign ads")
async def list_campaign_ads(
    campaign_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get all ads for a campaign"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT a.*,
                   COALESCE(SUM(ap.impressions), 0) as total_impressions,
                   COALESCE(SUM(ap.clicks), 0) as total_clicks,
                   COALESCE(AVG(ap.ctr), 0) as avg_ctr,
                   COALESCE(AVG(ap.cpc), 0) as avg_cpc
            FROM ads a
            LEFT JOIN ad_performance ap ON a.ad_id = ap.ad_id
            WHERE a.campaign_id = %s
            GROUP BY a.ad_id
            ORDER BY a.created_at DESC
        """, (campaign_id,))
        
        ads = cursor.fetchall()
        
        for ad in ads:
            if ad['media_urls']:
                ad['media_urls'] = json.loads(ad['media_urls'])
        
        return {"success": True, "ads": ads}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch ads: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== PERFORMANCE TRACKING ==========

@router.get("/performance/{campaign_id}", summary="Get campaign performance")
async def get_campaign_performance(
    campaign_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get campaign performance metrics"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = """
            SELECT 
                ap.metric_date,
                SUM(ap.impressions) as impressions,
                SUM(ap.clicks) as clicks,
                AVG(ap.ctr) as ctr,
                AVG(ap.cpc) as cpc,
                SUM(ap.spend) as spend,
                SUM(ap.conversions) as conversions,
                AVG(ap.roas) as roas
            FROM ads a
            JOIN ad_performance ap ON a.ad_id = ap.ad_id
            WHERE a.campaign_id = %s
        """
        params = [campaign_id]
        
        if start_date:
            query += " AND ap.metric_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND ap.metric_date <= %s"
            params.append(end_date)
        
        query += " GROUP BY ap.metric_date ORDER BY ap.metric_date DESC"
        
        cursor.execute(query, params)
        metrics = cursor.fetchall()
        
        # Calculate totals
        cursor.execute("""
            SELECT 
                SUM(ap.impressions) as total_impressions,
                SUM(ap.clicks) as total_clicks,
                AVG(ap.ctr) as avg_ctr,
                AVG(ap.cpc) as avg_cpc,
                SUM(ap.spend) as total_spend,
                SUM(ap.conversions) as total_conversions,
                AVG(ap.roas) as avg_roas
            FROM ads a
            JOIN ad_performance ap ON a.ad_id = ap.ad_id
            WHERE a.campaign_id = %s
        """ + (" AND ap.metric_date >= %s" if start_date else "") + 
              (" AND ap.metric_date <= %s" if end_date else ""),
        params)
        
        totals = cursor.fetchone()
        
        return {
            "success": True,
            "daily_metrics": metrics,
            "totals": totals
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch performance: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/dashboard/{client_id}", summary="Get ads dashboard data")
async def get_ads_dashboard(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get comprehensive dashboard data"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Campaign stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_campaigns,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_campaigns,
                COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_campaigns,
                SUM(budget) as total_budget
            FROM ad_campaigns
            WHERE client_id = %s
        """, (client_id,))
        campaign_stats = cursor.fetchone()
        
        # Performance by platform
        cursor.execute("""
            SELECT 
                c.platform,
                COUNT(DISTINCT c.campaign_id) as campaigns,
                COUNT(DISTINCT a.ad_id) as ads,
                COALESCE(SUM(ap.impressions), 0) as impressions,
                COALESCE(SUM(ap.clicks), 0) as clicks,
                COALESCE(SUM(ap.spend), 0) as spend,
                COALESCE(SUM(ap.conversions), 0) as conversions
            FROM ad_campaigns c
            LEFT JOIN ads a ON c.campaign_id = a.campaign_id
            LEFT JOIN ad_performance ap ON a.ad_id = ap.ad_id
            WHERE c.client_id = %s
            GROUP BY c.platform
        """, (client_id,))
        platform_performance = cursor.fetchall()
        
        # Recent campaigns
        cursor.execute("""
            SELECT c.*, u.full_name as creator_name
            FROM ad_campaigns c
            JOIN users u ON c.created_by = u.user_id
            WHERE c.client_id = %s
            ORDER BY c.created_at DESC
            LIMIT 5
        """, (client_id,))
        recent_campaigns = cursor.fetchall()
        
        return {
            "success": True,
            "campaign_stats": campaign_stats,
            "platform_performance": platform_performance,
            "recent_campaigns": recent_campaigns
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard data: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()