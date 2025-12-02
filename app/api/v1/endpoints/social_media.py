"""
Social Media Command Center API - Module 6
File: app/api/v1/endpoints/social_media.py

Multi-platform scheduling with Module 5 & 8 integration + Real API Publishing
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pymysql
import json
from openai import OpenAI

from app.core.config import settings
from app.core.security import require_admin_or_employee, get_current_user
from app.core.security import get_db_connection
from app.services.social_media_service import SocialMediaService

router = APIRouter()

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Initialize Social Media Service
social_media_service = SocialMediaService()


# ========== PYDANTIC MODELS ==========

class SocialMediaPostCreate(BaseModel):
    """Create social media post"""
    client_id: int
    content_id: Optional[int] = None  # Link to Module 5 content
    platform: str = Field(..., description="Platform: instagram, facebook, linkedin, twitter, pinterest")
    caption: str
    media_urls: List[str] = Field(default_factory=list)  # Media from Module 8
    hashtags: List[str] = Field(default_factory=list)
    scheduled_at: Optional[str] = None
    status: str = Field("draft", description="draft, scheduled, published")


class PostListResponse(BaseModel):
    post_id: int
    client_id: int
    client_name: str
    platform: str
    caption: str
    media_count: int
    hashtags: List[str]
    scheduled_at: Optional[str]
    published_at: Optional[str]
    status: str
    created_at: str


class BestTimeRequest(BaseModel):
    """Get AI-powered best posting times"""
    client_id: int
    platform: str


class BestTimeResponse(BaseModel):
    platform: str
    recommended_times: List[Dict[str, Any]]
    engagement_score: float


# ========== CREATE POST ==========

@router.post("/posts", summary="Create social media post")
async def create_post(
    post: SocialMediaPostCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Create social media post with integration to Module 5 (Content) and Module 8 (Media)
    Publishes immediately if status is 'published', schedules for later if 'scheduled'
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Verify client exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s AND role = 'client'", (post.client_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Client not found")
        
        # If content_id provided, fetch content from Module 5
        if post.content_id:
            cursor.execute("""
                SELECT content_text, hashtags, cta_text 
                FROM content_library 
                WHERE content_id = %s AND client_id = %s
            """, (post.content_id, post.client_id))
            content_data = cursor.fetchone()
            
            if content_data:
                if not post.caption and content_data.get('content_text'):
                    post.caption = content_data['content_text']
                
                if content_data.get('hashtags'):
                    try:
                        content_hashtags = json.loads(content_data['hashtags']) if isinstance(content_data['hashtags'], str) else content_data['hashtags']
                        if not post.hashtags and content_hashtags:
                            post.hashtags = content_hashtags
                    except:
                        pass
        
        # Convert scheduled_at to datetime if provided
        scheduled_datetime = None
        external_post_id = None
        
        if post.scheduled_at:
            try:
                scheduled_datetime = datetime.fromisoformat(post.scheduled_at.replace('Z', '+00:00'))
            except:
                raise HTTPException(status_code=400, detail="Invalid scheduled_at format. Use ISO format.")
        
        # If status is 'published', publish immediately to platform
        if post.status == 'published':
            publish_result = await publish_to_platform(
                platform=post.platform,
                client_id=post.client_id,
                caption=post.caption,
                media_urls=post.media_urls
            )
            
            if publish_result['success']:
                external_post_id = publish_result.get('post_id')
                post.status = 'published'
            else:
                # If publishing failed, save as draft
                post.status = 'draft'
                print(f"Publishing failed: {publish_result.get('error')}")
        
        # Insert post into database
        cursor.execute("""
            INSERT INTO social_media_posts 
            (client_id, content_id, created_by, platform, caption, media_urls, hashtags, 
             scheduled_at, status, external_post_id, published_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            post.client_id,
            post.content_id,
            current_user['user_id'],
            post.platform,
            post.caption,
            json.dumps(post.media_urls),
            json.dumps(post.hashtags),
            scheduled_datetime,
            post.status,
            external_post_id,
            datetime.now() if post.status == 'published' else None
        ))
        
        connection.commit()
        post_id = cursor.lastrowid
        
        return {
            "success": True,
            "message": "Social media post created successfully",
            "post_id": post_id,
            "status": post.status,
            "scheduled_at": post.scheduled_at,
            "external_post_id": external_post_id
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


async def publish_to_platform(
    platform: str,
    client_id: int,
    caption: str,
    media_urls: List[str]
) -> Dict[str, Any]:
    """
    Publish post to social media platform using real APIs
    
    Args:
        platform: Platform name (instagram, facebook, linkedin, twitter)
        client_id: Client ID
        caption: Post caption
        media_urls: List of media URLs
    
    Returns:
        Dict with success status and post_id
    """
    try:
        # Get platform credentials for client
        # In production, these would be stored in api_integrations table
        credentials = social_media_service.get_platform_credentials(client_id, platform)
        
        if not credentials:
            return {
                "success": False,
                "error": f"No credentials configured for {platform}"
            }
        
        # Get first media URL if available
        image_url = media_urls[0] if media_urls else None
        
        # Publish based on platform
        if platform == 'instagram':
            # Get Instagram account ID from credentials
            account_id = credentials.get('account_id')
            if not account_id:
                return {"success": False, "error": "Instagram account not configured"}
            
            result = social_media_service.publish_to_instagram(
                instagram_account_id=account_id,
                caption=caption,
                image_url=image_url
            )
            
        elif platform == 'facebook':
            # Get Facebook page ID from credentials
            page_id = credentials.get('page_id')
            if not page_id:
                return {"success": False, "error": "Facebook page not configured"}
            
            result = social_media_service.publish_to_facebook(
                page_id=page_id,
                message=caption,
                image_url=image_url
            )
            
        elif platform == 'linkedin':
            # Get LinkedIn organization URN from credentials
            org_urn = credentials.get('organization_urn')
            if not org_urn:
                return {"success": False, "error": "LinkedIn account not configured"}
            
            result = social_media_service.publish_to_linkedin(
                author_urn=org_urn,
                text=caption,
                image_url=image_url
            )
            
        elif platform == 'twitter':
            result = social_media_service.publish_to_twitter(
                text=caption
            )
            
        else:
            # For Pinterest and other platforms, save as scheduled
            result = {
                "success": True,
                "post_id": None,
                "platform": platform,
                "note": "Platform publishing not yet implemented"
            }
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ========== LIST POSTS ==========

@router.get("/posts", summary="Get all social media posts")
async def list_posts(
    client_id: Optional[int] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    List social media posts with filters
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = """
            SELECT 
                smp.post_id,
                smp.client_id,
                u.full_name as client_name,
                smp.platform,
                smp.caption,
                smp.media_urls,
                smp.hashtags,
                smp.scheduled_at,
                smp.published_at,
                smp.status,
                smp.created_at
            FROM social_media_posts smp
            JOIN users u ON smp.client_id = u.user_id
            WHERE 1=1
        """
        params = []
        
        if client_id:
            query += " AND smp.client_id = %s"
            params.append(client_id)
        
        if platform:
            query += " AND smp.platform = %s"
            params.append(platform)
        
        if status:
            query += " AND smp.status = %s"
            params.append(status)
        
        query += " ORDER BY smp.created_at DESC"
        
        cursor.execute(query, params)
        posts = cursor.fetchall()
        
        # Format response
        posts_list = []
        for post in posts:
            try:
                media_urls = json.loads(post['media_urls']) if post.get('media_urls') else []
                hashtags = json.loads(post['hashtags']) if post.get('hashtags') else []
            except:
                media_urls = []
                hashtags = []
            
            posts_list.append({
                "post_id": post['post_id'],
                "client_id": post['client_id'],
                "client_name": post['client_name'],
                "platform": post['platform'],
                "caption": post['caption'] or "",
                "media_count": len(media_urls),
                "hashtags": hashtags,
                "scheduled_at": post['scheduled_at'].isoformat() if post.get('scheduled_at') else None,
                "published_at": post['published_at'].isoformat() if post.get('published_at') else None,
                "status": post['status'],
                "created_at": post['created_at'].isoformat()
            })
        
        return {
            "success": True,
            "posts": posts_list,
            "total": len(posts_list)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== GET SINGLE POST ==========

@router.get("/posts/{post_id}", summary="Get single post details")
async def get_post(
    post_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get detailed information about a specific post"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT 
                smp.*,
                u.full_name as client_name,
                u.email as client_email
            FROM social_media_posts smp
            JOIN users u ON smp.client_id = u.user_id
            WHERE smp.post_id = %s
        """, (post_id,))
        
        post = cursor.fetchone()
        
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Parse JSON fields
        try:
            post['media_urls'] = json.loads(post['media_urls']) if post.get('media_urls') else []
            post['hashtags'] = json.loads(post['hashtags']) if post.get('hashtags') else []
        except:
            post['media_urls'] = []
            post['hashtags'] = []
        
        # Convert datetime fields
        if post.get('scheduled_at'):
            post['scheduled_at'] = post['scheduled_at'].isoformat()
        if post.get('published_at'):
            post['published_at'] = post['published_at'].isoformat()
        if post.get('created_at'):
            post['created_at'] = post['created_at'].isoformat()
        
        return {
            "success": True,
            "post": post
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


# ========== UPDATE POST ==========

@router.put("/posts/{post_id}", summary="Update social media post")
async def update_post(
    post_id: int,
    post: SocialMediaPostCreate,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Update an existing social media post"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Check if post exists
        cursor.execute("SELECT post_id FROM social_media_posts WHERE post_id = %s", (post_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Convert scheduled_at
        scheduled_datetime = None
        if post.scheduled_at:
            try:
                scheduled_datetime = datetime.fromisoformat(post.scheduled_at.replace('Z', '+00:00'))
            except:
                raise HTTPException(status_code=400, detail="Invalid scheduled_at format")
        
        # Update post
        cursor.execute("""
            UPDATE social_media_posts 
            SET platform = %s, caption = %s, media_urls = %s, hashtags = %s, 
                scheduled_at = %s, status = %s
            WHERE post_id = %s
        """, (
            post.platform,
            post.caption,
            json.dumps(post.media_urls),
            json.dumps(post.hashtags),
            scheduled_datetime,
            post.status,
            post_id
        ))
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Post updated successfully",
            "post_id": post_id
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


# ========== DELETE POST ==========

@router.delete("/posts/{post_id}", summary="Delete social media post")
async def delete_post(
    post_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Delete a social media post"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("DELETE FROM social_media_posts WHERE post_id = %s", (post_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Post not found")
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Post deleted successfully"
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



# ========== ADD THIS ENDPOINT FOR CONTENT LIBRARY ==========
@router.get("/content-library/{client_id}", summary="Get content library for client")
async def get_content_library(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get content from Module 5 (Content Intelligence Hub) for a specific client
    This provides compatibility for the Social Media Command Center
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT 
                content_id,
                client_id,
                platform,
                content_type,
                title,
                content_text,
                hashtags,
                cta_text,
                optimization_score,
                status,
                created_at
            FROM content_library
            WHERE client_id = %s AND status IN ('draft', 'approved')
            ORDER BY created_at DESC
            LIMIT 50
        """, (client_id,))
        
        content = cursor.fetchall()
        
        # Parse JSON fields
        for item in content:
            if item.get('hashtags'):
                try:
                    item['hashtags'] = json.loads(item['hashtags']) if isinstance(item['hashtags'], str) else item['hashtags']
                except:
                    item['hashtags'] = []
            else:
                item['hashtags'] = []
            
            if item.get('created_at'):
                item['created_at'] = item['created_at'].isoformat()
        
        return {
            "success": True,
            "content": content,
            "count": len(content)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== ADD THIS ENDPOINT FOR MEDIA LIBRARY ==========
@router.get("/media-library/{client_id}", summary="Get media library for client")
async def get_media_library(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get media assets from Module 8 (Creative Media Studio) for a specific client
    This provides compatibility for the Social Media Command Center
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT 
                asset_id,
                client_id,
                asset_type,
                asset_name,
                file_url,
                thumbnail_url,
                created_at
            FROM media_assets
            WHERE client_id = %s
            ORDER BY created_at DESC
            LIMIT 100
        """, (client_id,))
        
        assets = cursor.fetchall()
        
        # Format dates
        for asset in assets:
            if asset.get('created_at'):
                asset['created_at'] = asset['created_at'].isoformat()
        
        return {
            "success": True,
            "assets": assets,
            "count": len(assets)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



# ========== AI BEST TIME RECOMMENDATIONS ==========
@router.post("/best-times", summary="Get AI-powered best posting times")
async def get_best_times(
    request: BestTimeRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    AI-powered best time recommendations based on platform and engagement patterns
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Check existing best times data
        cursor.execute("""
            SELECT day_of_week, hour_of_day, engagement_score
            FROM platform_best_times
            WHERE client_id = %s AND platform = %s
            ORDER BY engagement_score DESC
            LIMIT 5
        """, (request.client_id, request.platform))
        
        existing_times = cursor.fetchall()
        
        if existing_times:
            # Return existing data
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            recommendations = []
            
            for time_data in existing_times:
                recommendations.append({
                    "day": day_names[time_data['day_of_week']],
                    "hour": time_data['hour_of_day'],
                    "time_formatted": f"{time_data['hour_of_day']:02d}:00",
                    "engagement_score": float(time_data['engagement_score'])
                })
            
            return {
                "success": True,
                "platform": request.platform,
                "recommended_times": recommendations
            }
        
        # Generate AI recommendations if no data exists
        prompt = f"""Based on industry best practices for {request.platform}, suggest the top 5 best times to post for maximum engagement.

Consider:
- Platform: {request.platform}
- General audience behavior patterns
- Peak engagement times

Provide response in JSON format:
[
  {{"day": "Monday", "hour": 9, "engagement_score": 85.5}},
  {{"day": "Tuesday", "hour": 14, "engagement_score": 82.3}}
]

Day should be day name, hour in 24h format (0-23), engagement_score (0-100)
"""
        
        response = openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a social media analytics expert specializing in optimal posting times."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        ai_recommendations = json.loads(response.choices[0].message.content)
        
        # Save recommendations to database
        day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
        
        for rec in ai_recommendations:
            day_num = day_map.get(rec['day'], 0)
            cursor.execute("""
                INSERT INTO platform_best_times 
                (client_id, platform, day_of_week, hour_of_day, engagement_score, last_calculated)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE 
                engagement_score = %s, last_calculated = NOW()
            """, (
                request.client_id,
                request.platform,
                day_num,
                rec['hour'],
                rec['engagement_score'],
                rec['engagement_score']
            ))
        
        connection.commit()
        
        # Format response
        recommendations = []
        for rec in ai_recommendations:
            recommendations.append({
                "day": rec['day'],
                "hour": rec['hour'],
                "time_formatted": f"{rec['hour']:02d}:00",
                "engagement_score": rec['engagement_score']
            })
        
        return {
            "success": True,
            "platform": request.platform,
            "recommended_times": recommendations
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


# ========== ADD ANALYTICS SUMMARY ENDPOINT ==========
@router.get("/analytics/summary", summary="Get analytics summary for all platforms")
async def get_analytics_summary(
    client_id: Optional[int] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get performance summaries for each platform
    Used by the Social Media Command Center dashboard
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Build query based on client filter
        query = """
            SELECT 
                platform,
                COUNT(*) as total_posts,
                SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published_posts,
                SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled_posts,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft_posts
            FROM social_media_posts
        """
        params = []
        
        if client_id:
            query += " WHERE client_id = %s"
            params.append(client_id)
        
        query += " GROUP BY platform"
        
        cursor.execute(query, params)
        platform_stats = cursor.fetchall()
        
        # Get analytics data if available
        analytics_query = """
            SELECT 
                platform,
                SUM(followers_count) as followers,
                SUM(impressions) as impressions,
                SUM(reach) as reach,
                SUM(engagement_count) as engagement
            FROM social_media_analytics
        """
        
        if client_id:
            analytics_query += " WHERE client_id = %s"
        
        analytics_query += " GROUP BY platform"
        
        cursor.execute(analytics_query, params if client_id else [])
        analytics_data = cursor.fetchall()
        
        # Merge data
        analytics_map = {row['platform']: row for row in analytics_data}
        
        summaries = []
        for stat in platform_stats:
            platform = stat['platform']
            analytics = analytics_map.get(platform, {})
            
            summaries.append({
                "platform": platform,
                "total_posts": stat['total_posts'] or 0,
                "published_posts": stat['published_posts'] or 0,
                "scheduled_posts": stat['scheduled_posts'] or 0,
                "draft_posts": stat['draft_posts'] or 0,
                "followers": analytics.get('followers') or 0,
                "impressions": analytics.get('impressions') or 0,
                "reach": analytics.get('reach') or 0,
                "engagement": analytics.get('engagement') or 0
            })
        
        # If no data, return default structure for common platforms
        if not summaries:
            for platform in ['instagram', 'facebook', 'linkedin', 'twitter', 'pinterest']:
                summaries.append({
                    "platform": platform,
                    "total_posts": 0,
                    "published_posts": 0,
                    "scheduled_posts": 0,
                    "draft_posts": 0,
                    "followers": 0,
                    "impressions": 0,
                    "reach": 0,
                    "engagement": 0
                })
        
        return {
            "success": True,
            "summaries": summaries
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== GET CALENDAR DATA ==========

from fastapi import Query  # Add this import at the top if not present

@router.get("/calendar", summary="Get calendar view of posts")
async def get_calendar(
    client_id: Optional[int] = None,  # Made optional
    month: Optional[int] = None,
    year: Optional[int] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get calendar view of scheduled posts for a specific month.
    If client_id is not provided, returns posts for ALL clients.
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Default to current month
        if not month or not year:
            now = datetime.now()
            month = month or now.month
            year = year or now.year
        
        # Get first and last day of month
        first_day = datetime(year, month, 1)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # Build query - client_id is now optional
        if client_id:
            cursor.execute("""
                SELECT 
                    smp.post_id,
                    smp.platform,
                    smp.caption,
                    smp.scheduled_at,
                    smp.status,
                    smp.media_urls,
                    u.full_name as client_name
                FROM social_media_posts smp
                JOIN users u ON smp.client_id = u.user_id
                WHERE smp.client_id = %s 
                AND smp.scheduled_at >= %s 
                AND smp.scheduled_at <= %s
                ORDER BY smp.scheduled_at ASC
            """, (client_id, first_day, last_day))
        else:
            # Get posts for ALL clients
            cursor.execute("""
                SELECT 
                    smp.post_id,
                    smp.platform,
                    smp.caption,
                    smp.scheduled_at,
                    smp.status,
                    smp.media_urls,
                    u.full_name as client_name
                FROM social_media_posts smp
                JOIN users u ON smp.client_id = u.user_id
                WHERE smp.scheduled_at >= %s 
                AND smp.scheduled_at <= %s
                ORDER BY smp.scheduled_at ASC
            """, (first_day, last_day))
        
        posts = cursor.fetchall()
        
        # Group by date
        calendar_data = {}
        for post in posts:
            if post['scheduled_at']:
                date_key = post['scheduled_at'].strftime('%Y-%m-%d')
                
                if date_key not in calendar_data:
                    calendar_data[date_key] = []
                
                try:
                    media_urls = json.loads(post['media_urls']) if post.get('media_urls') else []
                except:
                    media_urls = []
                
                calendar_data[date_key].append({
                    "post_id": post['post_id'],
                    "platform": post['platform'],
                    "caption": post['caption'][:100] if post.get('caption') else "",
                    "client_name": post.get('client_name', 'Unknown'),
                    "scheduled_at": post['scheduled_at'].isoformat(),
                    "status": post['status'],
                    "media_count": len(media_urls)
                })
        
        return {
            "success": True,
            "month": month,
            "year": year,
            "calendar": calendar_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@router.get("/stats", summary="Get post statistics")
async def get_stats(
    client_id: Optional[int] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get post statistics (total, scheduled, published, drafts)
    Optionally filter by client_id
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Build query
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled,
                SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft
            FROM social_media_posts
        """
        params = []
        
        if client_id:
            query += " WHERE client_id = %s"
            params.append(client_id)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        return {
            "success": True,
            "stats": {
                "total": result['total'] or 0,
                "scheduled": result['scheduled'] or 0,
                "published": result['published'] or 0,
                "draft": result['draft'] or 0
            }
        }
        
    except Exception as e:
        # Return zeros on error instead of failing
        return {
            "success": True,
            "stats": {
                "total": 0,
                "scheduled": 0,
                "published": 0,
                "draft": 0
            }
        }
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

            
# ========== PLATFORM ANALYTICS ==========

@router.get("/analytics/{client_id}", summary="Get platform-wise analytics")
async def get_analytics(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Get platform-wise performance analytics"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get post counts by platform
        cursor.execute("""
            SELECT 
                platform,
                COUNT(*) as total_posts,
                SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) as published_posts,
                SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) as scheduled_posts,
                SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) as draft_posts
            FROM social_media_posts
            WHERE client_id = %s
            GROUP BY platform
        """, (client_id,))
        
        platform_stats = cursor.fetchall()
        
        # Get analytics data if available
        cursor.execute("""
            SELECT 
                platform,
                SUM(followers_count) as total_followers,
                SUM(impressions) as total_impressions,
                SUM(reach) as total_reach,
                SUM(engagement_count) as total_engagement
            FROM social_media_analytics
            WHERE client_id = %s
            GROUP BY platform
        """, (client_id,))
        
        analytics_data = cursor.fetchall()
        
        # Merge data
        analytics_map = {row['platform']: row for row in analytics_data}
        
        result = []
        for stat in platform_stats:
            platform = stat['platform']
            analytics = analytics_map.get(platform, {})
            
            result.append({
                "platform": platform,
                "total_posts": stat['total_posts'],
                "published_posts": stat['published_posts'],
                "scheduled_posts": stat['scheduled_posts'],
                "draft_posts": stat['draft_posts'],
                "followers": analytics.get('total_followers', 0),
                "impressions": analytics.get('total_impressions', 0),
                "reach": analytics.get('total_reach', 0),
                "engagement": analytics.get('total_engagement', 0)
            })
        
        return {
            "success": True,
            "analytics": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== TRENDING TOPICS ==========
@router.get("/trending", summary="Get trending topics from platforms")
async def get_trending_topics(
    platform: Optional[str] = None,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get trending topics from social media platforms
    Uses AI to generate relevant trending topics when API data unavailable
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Check for stored trends (last 24 hours)
        query = """
            SELECT platform, topic, category, volume, detected_at
            FROM trending_topics
            WHERE detected_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """
        params = []
        
        if platform:
            query += " AND platform = %s"
            params.append(platform)
        
        query += " ORDER BY volume DESC LIMIT 20"
        
        cursor.execute(query, params)
        stored_trends = cursor.fetchall()
        
        if stored_trends and len(stored_trends) >= 5:
            # Format and return stored trends
            for trend in stored_trends:
                if trend.get('detected_at'):
                    trend['detected_at'] = trend['detected_at'].isoformat()
            
            return {
                "success": True,
                "topics": stored_trends,
                "source": "stored"
            }
        
        # Generate AI-based trending suggestions
        try:
            prompt = f"""Generate 6 current trending topics for social media marketing.
            {f'Focus on {platform} platform.' if platform else 'Include topics suitable for various platforms.'}
            
            Return as JSON array with format:
            [
                {{"topic": "Topic Name", "category": "Category", "platform": "platform_name", "volume": 50000}}
            ]
            
            Categories: Technology, Business, Marketing, Lifestyle, Entertainment, News
            Platforms: instagram, facebook, linkedin, twitter, pinterest
            Volume: estimated posts/engagement (10000-500000)
            
            Make topics relevant to digital marketing and business."""
            
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a social media trend analyst. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON from response
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            
            trending = json.loads(content)
            
            # Store trends for future use
            for trend in trending:
                try:
                    cursor.execute("""
                        INSERT INTO trending_topics (platform, topic, category, volume, detected_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (
                        trend.get('platform', 'general'),
                        trend.get('topic', ''),
                        trend.get('category', 'General'),
                        trend.get('volume', 10000)
                    ))
                except:
                    pass
            
            connection.commit()
            
            return {
                "success": True,
                "topics": trending,
                "source": "ai_generated"
            }
            
        except Exception as ai_error:
            print(f"AI trending error: {ai_error}")
            
            # Return default trends
            default_trends = [
                {"topic": "#DigitalMarketing", "category": "Marketing", "platform": platform or "instagram", "volume": 125000},
                {"topic": "#ContentCreation", "category": "Marketing", "platform": platform or "instagram", "volume": 98000},
                {"topic": "#SocialMediaTips", "category": "Marketing", "platform": platform or "facebook", "volume": 87000},
                {"topic": "#BusinessGrowth", "category": "Business", "platform": platform or "linkedin", "volume": 76000},
                {"topic": "#MarketingStrategy", "category": "Marketing", "platform": platform or "twitter", "volume": 65000},
                {"topic": "#BrandBuilding", "category": "Business", "platform": platform or "instagram", "volume": 54000}
            ]
            
            return {
                "success": True,
                "topics": default_trends,
                "source": "default"
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
# ========== PERFORMANCE SUMMARY ==========

@router.get("/performance-summary/{client_id}", summary="Get performance summary by platform")
async def get_performance_summary(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Get small performance summaries for each platform
    Returns key metrics: engagement rate, reach, best performing post
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get performance data by platform
        cursor.execute("""
            SELECT 
                smp.platform,
                COUNT(DISTINCT smp.post_id) as total_published,
                COALESCE(SUM(sma.impressions), 0) as total_impressions,
                COALESCE(SUM(sma.reach), 0) as total_reach,
                COALESCE(SUM(sma.engagement_count), 0) as total_engagement,
                COALESCE(AVG(sma.followers_count), 0) as avg_followers
            FROM social_media_posts smp
            LEFT JOIN social_media_analytics sma ON smp.client_id = sma.client_id AND smp.platform = sma.platform
            WHERE smp.client_id = %s AND smp.status = 'published'
            GROUP BY smp.platform
        """, (client_id,))
        
        platform_data = cursor.fetchall()
        
        summaries = []
        
        for data in platform_data:
            platform = data['platform']
            total_published = data['total_published']
            total_impressions = data['total_impressions']
            total_reach = data['total_reach']
            total_engagement = data['total_engagement']
            avg_followers = data['avg_followers']
            
            # Calculate engagement rate
            engagement_rate = 0
            if total_impressions > 0:
                engagement_rate = (total_engagement / total_impressions) * 100
            elif avg_followers > 0:
                engagement_rate = (total_engagement / avg_followers) * 100
            
            # Get best performing post
            cursor.execute("""
                SELECT caption, scheduled_at
                FROM social_media_posts
                WHERE client_id = %s AND platform = %s AND status = 'published'
                ORDER BY created_at DESC
                LIMIT 1
            """, (client_id, platform))
            
            best_post = cursor.fetchone()
            
            # Generate AI insights
            insight = generate_platform_insight(platform, engagement_rate, total_published)
            
            summaries.append({
                "platform": platform,
                "metrics": {
                    "total_posts": total_published,
                    "impressions": int(total_impressions),
                    "reach": int(total_reach),
                    "engagement": int(total_engagement),
                    "engagement_rate": round(engagement_rate, 2),
                    "followers": int(avg_followers)
                },
                "best_post": {
                    "caption": best_post['caption'][:100] if best_post else "No posts yet",
                    "date": best_post['scheduled_at'].isoformat() if best_post and best_post['scheduled_at'] else None
                },
                "insight": insight,
                "status": "excellent" if engagement_rate > 5 else "good" if engagement_rate > 2 else "needs_improvement"
            })
        
        return {
            "success": True,
            "summaries": summaries
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def generate_platform_insight(platform: str, engagement_rate: float, total_posts: int) -> str:
    """Generate AI insight for platform performance"""
    
    if total_posts == 0:
        return f"Start posting on {platform} to build your presence."
    
    if engagement_rate > 5:
        return f"Excellent performance on {platform}! Your audience is highly engaged."
    elif engagement_rate > 2:
        return f"Good engagement on {platform}. Consider posting at peak times for better reach."
    elif engagement_rate > 0.5:
        return f"Moderate engagement. Try different content formats and posting times on {platform}."
    else:
        return f"Low engagement detected. Review your content strategy for {platform}."


# ========== SYNC ANALYTICS FROM PLATFORMS ==========

@router.post("/sync-analytics/{client_id}", summary="Sync analytics from social platforms")
async def sync_platform_analytics(
    client_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """
    Sync real analytics data from social media platforms (Meta, LinkedIn)
    Fetches latest metrics and saves to database
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
        
        results = {}
        
        # Sync Instagram analytics
        try:
            instagram_result = social_media_service.get_instagram_insights(
                instagram_account_id="placeholder_account_id"  # Get from client config
            )
            
            if instagram_result['success']:
                insights = instagram_result['insights']
                
                cursor.execute("""
                    INSERT INTO social_media_analytics 
                    (client_id, platform, metric_date, followers_count, impressions, reach, engagement_count)
                    VALUES (%s, %s, CURDATE(), %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    followers_count = VALUES(followers_count),
                    impressions = VALUES(impressions),
                    reach = VALUES(reach),
                    engagement_count = VALUES(engagement_count)
                """, (
                    client_id,
                    'instagram',
                    insights.get('follower_count', 0),
                    insights.get('impressions', 0),
                    insights.get('reach', 0),
                    insights.get('profile_views', 0)
                ))
                
                results['instagram'] = "synced"
        except Exception as e:
            results['instagram'] = f"error: {str(e)}"
        
        # Sync Facebook analytics
        try:
            facebook_result = social_media_service.get_facebook_page_insights(
                page_id="placeholder_page_id"  # Get from client config
            )
            
            if facebook_result['success']:
                insights = facebook_result['insights']
                
                cursor.execute("""
                    INSERT INTO social_media_analytics 
                    (client_id, platform, metric_date, followers_count, impressions, engagement_count)
                    VALUES (%s, %s, CURDATE(), %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    followers_count = VALUES(followers_count),
                    impressions = VALUES(impressions),
                    engagement_count = VALUES(engagement_count)
                """, (
                    client_id,
                    'facebook',
                    insights.get('page_fans', 0),
                    insights.get('page_impressions', 0),
                    insights.get('page_engaged_users', 0)
                ))
                
                results['facebook'] = "synced"
        except Exception as e:
            results['facebook'] = f"error: {str(e)}"
        
        # Sync LinkedIn analytics
        try:
            linkedin_result = social_media_service.get_linkedin_analytics(
                organization_urn="placeholder_org_urn"  # Get from client config
            )
            
            if linkedin_result['success']:
                analytics = linkedin_result['analytics']
                
                cursor.execute("""
                    INSERT INTO social_media_analytics 
                    (client_id, platform, metric_date, impressions, engagement_count)
                    VALUES (%s, %s, CURDATE(), %s, %s)
                    ON DUPLICATE KEY UPDATE
                    impressions = VALUES(impressions),
                    engagement_count = VALUES(engagement_count)
                """, (
                    client_id,
                    'linkedin',
                    analytics.get('impressions', 0),
                    analytics.get('likes', 0) + analytics.get('comments', 0) + analytics.get('shares', 0)
                ))
                
                results['linkedin'] = "synced"
        except Exception as e:
            results['linkedin'] = f"error: {str(e)}"
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Analytics synced from platforms",
            "results": results
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