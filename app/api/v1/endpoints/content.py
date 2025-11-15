"""
Content Intelligence Hub API - Module 5
File: app/api/v1/endpoints/content.py

AI-powered content creation and optimization
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import pymysql
import json
from openai import OpenAI

from app.core.config import settings
from app.core.security import require_admin_or_employee, get_current_user
from app.core.security import get_db_connection

router = APIRouter()

# Initialize OpenAI client (v1.0.0+)
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ========== PYDANTIC MODELS ==========

class ContentGenerateRequest(BaseModel):
    """Request model for AI content generation"""
    platform: str = Field(..., description="Social media platform")
    content_type: str = Field(..., description="Type of content")
    topic: str = Field(..., description="Content topic/brief")
    tone: Optional[str] = Field("professional", description="Content tone")
    target_audience: Optional[str] = Field(None, description="Target audience")
    keywords: Optional[List[str]] = Field([], description="Keywords to include")
    client_id: Optional[int] = Field(None, description="Client ID")


class ContentSaveRequest(BaseModel):
    """Request model for saving content"""
    client_id: int
    platform: str
    content_type: str
    title: Optional[str] = None
    content_text: str
    hashtags: Optional[List[str]] = []
    cta_text: Optional[str] = None
    optimization_score: Optional[float] = None
    status: str = "draft"


class ContentUpdateRequest(BaseModel):
    """Request model for updating content"""
    title: Optional[str] = None
    content_text: Optional[str] = None
    hashtags: Optional[List[str]] = None
    cta_text: Optional[str] = None
    optimization_score: Optional[float] = None
    status: Optional[str] = None


# ========== HELPER FUNCTIONS ==========

def get_platform_guidelines(platform: str) -> Dict[str, Any]:
    """Get platform-specific content guidelines"""
    guidelines = {
        "instagram": {
            "max_chars": 2200,
            "optimal_chars": 150,
            "hashtag_limit": 30,
            "optimal_hashtags": "8-15",
            "best_practices": [
                "Use emojis to increase engagement",
                "Ask questions to encourage comments",
                "Include call-to-action in first line",
                "Use line breaks for readability"
            ]
        },
        "facebook": {
            "max_chars": 63206,
            "optimal_chars": 250,
            "hashtag_limit": 10,
            "optimal_hashtags": "1-3",
            "best_practices": [
                "Keep posts concise and scannable",
                "Use native video when possible",
                "Tag relevant pages and people",
                "Post when audience is most active"
            ]
        },
        "linkedin": {
            "max_chars": 3000,
            "optimal_chars": 150,
            "hashtag_limit": 30,
            "optimal_hashtags": "3-5",
            "best_practices": [
                "Lead with value or insight",
                "Use professional tone",
                "Include industry-specific hashtags",
                "Tag relevant professionals"
            ]
        },
        "twitter": {
            "max_chars": 280,
            "optimal_chars": 240,
            "hashtag_limit": 10,
            "optimal_hashtags": "1-2",
            "best_practices": [
                "Be concise and impactful",
                "Use trending hashtags strategically",
                "Include media for higher engagement",
                "Engage with replies quickly"
            ]
        },
        "pinterest": {
            "max_chars": 500,
            "optimal_chars": 200,
            "hashtag_limit": 20,
            "optimal_hashtags": "5-10",
            "best_practices": [
                "Use keyword-rich descriptions",
                "Include compelling calls-to-action",
                "Add relevant hashtags",
                "Describe image content clearly"
            ]
        }
    }
    
    return guidelines.get(platform.lower(), {
        "max_chars": 2000,
        "optimal_chars": 200,
        "hashtag_limit": 10,
        "optimal_hashtags": "3-5",
        "best_practices": []
    })


def generate_ai_content(
    platform: str,
    content_type: str,
    topic: str,
    tone: str,
    target_audience: Optional[str] = None,
    keywords: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Generate content using OpenAI"""
    
    guidelines = get_platform_guidelines(platform)
    
    # Build the prompt
    prompt = f"""Create engaging {platform} content for the following:

Topic: {topic}
Content Type: {content_type}
Tone: {tone}
Platform: {platform}
Target Audience: {target_audience or 'General audience'}
"""

    if keywords:
        prompt += f"\nKeywords to include: {', '.join(keywords)}"
    
    prompt += f"""

Platform Guidelines:
- Optimal length: {guidelines['optimal_chars']} characters
- Maximum length: {guidelines['max_chars']} characters
- Optimal hashtags: {guidelines['optimal_hashtags']}

Requirements:
1. Create {content_type} content optimized for {platform}
2. Use {tone} tone
3. Include engaging hook in the first line
4. Make it actionable and valuable
5. Keep within optimal character limit
6. DO NOT include hashtags in the main content

Provide the response in this JSON format:
{{
    "content": "The main content text without hashtags",
    "headline": "Attention-grabbing headline (if applicable)",
    "cta": "Clear call-to-action"
}}
"""

    try:
        response = openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert social media content creator specializing in platform-specific optimization."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        content_data = json.loads(response.choices[0].message.content)
        
        # Generate hashtags separately
        hashtag_prompt = f"""Generate {guidelines['optimal_hashtags']} relevant hashtags for {platform} content about: {topic}

Requirements:
- Mix of popular and niche hashtags
- Relevant to {platform} audience
- Include trending hashtags when applicable
- Format: Return only a JSON array of hashtag strings (without # symbol)

Example: ["socialmedia", "marketing", "digitalstrategy"]
"""
        
        hashtag_response = openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a hashtag optimization expert."},
                {"role": "user", "content": hashtag_prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        hashtags = json.loads(hashtag_response.choices[0].message.content)
        
        # Calculate optimization score
        content_length = len(content_data.get('content', ''))
        optimal_length = guidelines['optimal_chars']
        
        # Score based on length optimization (60% weight)
        length_score = min(100, (content_length / optimal_length) * 100) if content_length <= guidelines['max_chars'] else 50
        
        # Score based on hashtags (20% weight)
        hashtag_count = len(hashtags)
        optimal_hashtag_range = guidelines['optimal_hashtags'].split('-')
        optimal_min = int(optimal_hashtag_range[0])
        optimal_max = int(optimal_hashtag_range[-1]) if '-' in guidelines['optimal_hashtags'] else optimal_min
        
        if optimal_min <= hashtag_count <= optimal_max:
            hashtag_score = 100
        else:
            hashtag_score = 70
        
        # Overall score
        optimization_score = (length_score * 0.6) + (hashtag_score * 0.2) + 20
        
        return {
            "content": content_data.get('content', ''),
            "headline": content_data.get('headline', ''),
            "cta": content_data.get('cta', ''),
            "hashtags": hashtags,
            "optimization_score": round(optimization_score, 2),
            "guidelines": guidelines,
            "character_count": content_length
        }
        
    except Exception as e:
        print(f"Error generating content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate content: {str(e)}"
        )


# ========== API ENDPOINTS ==========

@router.post("/generate")
async def generate_content(
    request: ContentGenerateRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Generate AI-powered content for social media"""
    
    try:
        result = generate_ai_content(
            platform=request.platform,
            content_type=request.content_type,
            topic=request.topic,
            tone=request.tone,
            target_audience=request.target_audience,
            keywords=request.keywords
        )
        
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in generate_content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/save")
async def save_content(
    request: ContentSaveRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Save content to library"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert content
        cursor.execute("""
            INSERT INTO content_library (
                client_id, created_by, platform, content_type,
                title, content_text, hashtags, cta_text,
                ai_generated, optimization_score, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.client_id,
            current_user['user_id'],
            request.platform,
            request.content_type,
            request.title,
            request.content_text,
            json.dumps(request.hashtags),
            request.cta_text,
            True,
            request.optimization_score,
            request.status
        ))
        
        connection.commit()
        content_id = cursor.lastrowid
        
        return {
            "success": True,
            "message": "Content saved successfully",
            "content_id": content_id
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error saving content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save content: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/list")
async def list_content(
    client_id: Optional[int] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get list of content from library"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Build query
        query = """
            SELECT 
                cl.*,
                u.full_name as creator_name,
                c.full_name as client_name
            FROM content_library cl
            LEFT JOIN users u ON cl.created_by = u.user_id
            LEFT JOIN users c ON cl.client_id = c.user_id
            WHERE 1=1
        """
        params = []
        
        # Role-based filtering
        if current_user['role'] == 'client':
            query += " AND cl.client_id = %s"
            params.append(current_user['user_id'])
        elif client_id:
            query += " AND cl.client_id = %s"
            params.append(client_id)
        
        if platform:
            query += " AND cl.platform = %s"
            params.append(platform)
        
        if status:
            query += " AND cl.status = %s"
            params.append(status)
        
        query += " ORDER BY cl.created_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, tuple(params))
        content_list = cursor.fetchall()
        
        # Parse JSON fields
        for content in content_list:
            if content.get('hashtags'):
                content['hashtags'] = json.loads(content['hashtags'])
        
        return {
            "success": True,
            "data": content_list
        }
        
    except Exception as e:
        print(f"Error fetching content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch content: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/{content_id}")
async def get_content(
    content_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get specific content by ID"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                cl.*,
                u.full_name as creator_name,
                c.full_name as client_name
            FROM content_library cl
            LEFT JOIN users u ON cl.created_by = u.user_id
            LEFT JOIN users c ON cl.client_id = c.user_id
            WHERE cl.content_id = %s
        """, (content_id,))
        
        content = cursor.fetchone()
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found"
            )
        
        # Parse JSON fields
        if content.get('hashtags'):
            content['hashtags'] = json.loads(content['hashtags'])
        
        return {
            "success": True,
            "data": content
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch content: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.put("/{content_id}")
async def update_content(
    content_id: int,
    request: ContentUpdateRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Update existing content"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Build update query
        update_fields = []
        params = []
        
        if request.title is not None:
            update_fields.append("title = %s")
            params.append(request.title)
        
        if request.content_text is not None:
            update_fields.append("content_text = %s")
            params.append(request.content_text)
        
        if request.hashtags is not None:
            update_fields.append("hashtags = %s")
            params.append(json.dumps(request.hashtags))
        
        if request.cta_text is not None:
            update_fields.append("cta_text = %s")
            params.append(request.cta_text)
        
        if request.optimization_score is not None:
            update_fields.append("optimization_score = %s")
            params.append(request.optimization_score)
        
        if request.status is not None:
            update_fields.append("status = %s")
            params.append(request.status)
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        params.append(content_id)
        
        query = f"""
            UPDATE content_library 
            SET {', '.join(update_fields)}
            WHERE content_id = %s
        """
        
        cursor.execute(query, tuple(params))
        connection.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found"
            )
        
        return {
            "success": True,
            "message": "Content updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error updating content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update content: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.delete("/{content_id}")
async def delete_content(
    content_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Delete content from library"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            DELETE FROM content_library 
            WHERE content_id = %s
        """, (content_id,))
        
        connection.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found"
            )
        
        return {
            "success": True,
            "message": "Content deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error deleting content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete content: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/platforms/guidelines")
async def get_all_platform_guidelines():
    """Get content guidelines for all platforms"""
    
    platforms = ["instagram", "facebook", "linkedin", "twitter", "pinterest"]
    
    return {
        "success": True,
        "data": {platform: get_platform_guidelines(platform) for platform in platforms}
    }