"""
Creative Media Studio API - Module 8
File: app/api/v1/endpoints/media_studio.py

AI-powered media generation: DALL-E, Synthesia, Canva
"""

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import pymysql
import json
import requests
import base64
from openai import OpenAI

from app.core.config import settings
from app.core.security import require_admin_or_employee, get_current_user
from app.core.security import get_db_connection

router = APIRouter()

# Initialize OpenAI client (for DALL-E)
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ========== PYDANTIC MODELS ==========

class ImageGenerateRequest(BaseModel):
    """Request model for DALL-E image generation"""
    prompt: str = Field(..., description="Image description prompt")
    client_id: int
    size: str = Field("1024x1024", description="Image size: 256x256, 512x512, 1024x1024, 1024x1792, 1792x1024")
    quality: str = Field("standard", description="Quality: standard or hd")
    style: str = Field("vivid", description="Style: vivid or natural")
    n: int = Field(1, description="Number of images (1-4)")


class VideoGenerateRequest(BaseModel):
    """Request model for Synthesia video generation"""
    script: str = Field(..., description="Video script/narration")
    client_id: int
    avatar_id: Optional[str] = Field(None, description="Synthesia avatar ID")
    voice_id: Optional[str] = Field(None, description="Voice ID")
    background: Optional[str] = Field("white", description="Background color or image")
    title: Optional[str] = Field(None, description="Video title")


class CanvaDesignRequest(BaseModel):
    """Request model for Canva design"""
    design_type: str = Field(..., description="Design type: social_post, story, presentation, etc.")
    client_id: int
    title: str
    content_elements: Optional[Dict[str, Any]] = Field({}, description="Design content elements")


class AssetUpdateRequest(BaseModel):
    """Request model for updating asset"""
    asset_name: Optional[str] = None
    status: Optional[str] = None


# ========== DALL-E IMAGE GENERATION ==========

async def generate_dalle_image(prompt: str, size: str, quality: str, style: str, n: int) -> Dict[str, Any]:
    """Generate images using DALL-E"""
    
    try:
        print(f"[DALL-E] Generating {n} image(s) with prompt: {prompt[:50]}...")
        
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            n=1  # DALL-E 3 only supports n=1
        )
        
        images = []
        for image_data in response.data:
            images.append({
                "url": image_data.url,
                "revised_prompt": getattr(image_data, 'revised_prompt', prompt)
            })
        
        print(f"[DALL-E] Successfully generated {len(images)} image(s)")
        return {
            "success": True,
            "images": images,
            "model": "dall-e-3"
        }
        
    except Exception as e:
        print(f"[DALL-E] Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DALL-E generation failed: {str(e)}"
        )


# ========== SYNTHESIA VIDEO GENERATION ==========

async def generate_synthesia_video(
    script: str,
    avatar_id: Optional[str] = None,
    voice_id: Optional[str] = None,
    background: str = "white",
    title: Optional[str] = None
) -> Dict[str, Any]:
    """Generate video using Synthesia API"""
    
    try:
        print(f"[SYNTHESIA] Generating video with script: {script[:50]}...")
        
        # Synthesia API endpoint
        api_url = "https://api.synthesia.io/v2/videos"
        
        # Use default avatar if not specified
        avatar = avatar_id or settings.SYNTHESIA_AVATAR_ID or "anna_costume1_cameraA"
        
        # Prepare request payload - Updated format for Synthesia API v2
        payload = {
            "test": True,  # Set to True for testing (doesn't use credits)
            "visibility": "private",
            "title": title or "AI Generated Video",
            "description": "Generated via PanvelIQ",
            "input": [
                {
                    "scriptText": script,
                    "avatar": avatar,
                    "background": background
                }
            ]
        }
        
        # Synthesia API uses x-api-key header, not Authorization
        headers = {
            "x-api-key": settings.SYNTHESIA_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        print(f"[SYNTHESIA] Sending request to: {api_url}")
        print(f"[SYNTHESIA] Avatar: {avatar}")
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        
        # Log response for debugging
        print(f"[SYNTHESIA] Status Code: {response.status_code}")
        print(f"[SYNTHESIA] Response: {response.text[:200]}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            video_id = result.get("id")
            print(f"[SYNTHESIA] Video creation initiated. ID: {video_id}")
            return {
                "success": True,
                "video_id": video_id,
                "status": "processing",
                "message": "Video generation started. It may take a few minutes."
            }
        else:
            # Try to get detailed error message
            try:
                error_data = response.json()
                error_msg = error_data.get("message") or error_data.get("error") or str(error_data)
            except:
                error_msg = response.text or "Unknown error"
            
            print(f"[SYNTHESIA] Error Response: {error_msg}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Synthesia API error: {error_msg}"
            )
            
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Synthesia API timeout"
        )
    except Exception as e:
        print(f"[SYNTHESIA] Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Synthesia generation failed: {str(e)}"
        )


async def check_synthesia_video_status(video_id: str) -> Dict[str, Any]:
    """Check Synthesia video generation status"""
    
    try:
        api_url = f"https://api.synthesia.io/v2/videos/{video_id}"
        
        headers = {
            "x-api-key": settings.SYNTHESIA_API_KEY
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "status": result.get("status"),
                "download_url": result.get("download"),
                "duration": result.get("duration"),
                "visibility": result.get("visibility")
            }
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail="Failed to fetch video status"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status check failed: {str(e)}"
        )


# ========== CANVA DESIGN CREATION ==========

async def create_canva_design(
    design_type: str,
    title: str,
    content_elements: Dict[str, Any]
) -> Dict[str, Any]:
    """Create design using Canva API"""
    
    try:
        print(f"[CANVA] Creating {design_type} design: {title}")
        
        # Canva API endpoint
        api_url = "https://api.canva.com/rest/v1/designs"
        
        # Map design types to Canva design types
        design_type_mapping = {
            "social_post": "InstagramPost",
            "story": "InstagramStory",
            "presentation": "Presentation",
            "logo": "Logo",
            "flyer": "Flyer",
            "poster": "Poster",
            "banner": "Banner",
            "facebook_post": "FacebookPost",
            "twitter_post": "TwitterPost",
            "linkedin_post": "LinkedInPost"
        }
        
        canva_design_type = design_type_mapping.get(design_type, "InstagramPost")
        
        # Prepare request payload
        payload = {
            "design_type": canva_design_type,
            "title": title
        }
        
        headers = {
            "Authorization": f"Bearer {settings.CANVA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        
        if response.status_code in [200, 201]:
            result = response.json()
            design_id = result.get("design", {}).get("id")
            edit_url = result.get("design", {}).get("urls", {}).get("edit_url")
            
            print(f"[CANVA] Design created. ID: {design_id}")
            return {
                "success": True,
                "design_id": design_id,
                "edit_url": edit_url,
                "message": "Design created successfully. Use edit_url to customize."
            }
        else:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            print(f"[CANVA] Error: {error_msg}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Canva API error: {error_msg}"
            )
            
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Canva API timeout"
        )
    except Exception as e:
        print(f"[CANVA] Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Canva design creation failed: {str(e)}"
        )


# ========== API ENDPOINTS ==========

@router.post("/generate/image")
async def generate_image(
    request: ImageGenerateRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Generate images using DALL-E"""
    
    connection = None
    cursor = None
    
    try:
        # Generate image
        result = await generate_dalle_image(
            prompt=request.prompt,
            size=request.size,
            quality=request.quality,
            style=request.style,
            n=request.n
        )
        
        # Save to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        saved_assets = []
        
        for idx, image in enumerate(result["images"]):
            cursor.execute("""
                INSERT INTO media_assets (
                    client_id, created_by, asset_type, asset_name,
                    file_url, ai_generated, generation_type, prompt_used
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                request.client_id,
                current_user['user_id'],
                'image',
                f"DALL-E Image {idx + 1}",
                image["url"],
                True,
                "dall-e-3",
                request.prompt
            ))
            
            saved_assets.append({
                "asset_id": cursor.lastrowid,
                "url": image["url"],
                "revised_prompt": image.get("revised_prompt")
            })
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Images generated successfully",
            "assets": saved_assets
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error generating image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate image: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/generate/video")
async def generate_video(
    request: VideoGenerateRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Generate video using Synthesia"""
    
    connection = None
    cursor = None
    
    try:
        # Generate video
        result = await generate_synthesia_video(
            script=request.script,
            avatar_id=request.avatar_id,
            voice_id=request.voice_id,
            background=request.background,
            title=request.title
        )
        
        # Save to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO media_assets (
                client_id, created_by, asset_type, asset_name,
                file_url, ai_generated, generation_type, prompt_used
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.client_id,
            current_user['user_id'],
            'video',
            request.title or "Synthesia Video",
            result.get("video_id", ""),  # Store video_id temporarily
            True,
            "synthesia",
            request.script
        ))
        
        asset_id = cursor.lastrowid
        connection.commit()
        
        return {
            "success": True,
            "message": "Video generation started",
            "asset_id": asset_id,
            "video_id": result.get("video_id"),
            "status": result.get("status")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error generating video: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate video: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/video/status/{video_id}")
async def get_video_status(
    video_id: str,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Check Synthesia video generation status"""
    
    try:
        result = await check_synthesia_video_status(video_id)
        
        # Update database if video is complete
        if result.get("status") == "complete" and result.get("download_url"):
            connection = get_db_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                UPDATE media_assets 
                SET file_url = %s
                WHERE file_url = %s AND generation_type = 'synthesia'
            """, (result.get("download_url"), video_id))
            
            connection.commit()
            cursor.close()
            connection.close()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status check failed: {str(e)}"
        )


@router.post("/generate/design")
async def generate_design(
    request: CanvaDesignRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Create design using Canva"""
    
    connection = None
    cursor = None
    
    try:
        # Create design
        result = await create_canva_design(
            design_type=request.design_type,
            title=request.title,
            content_elements=request.content_elements
        )
        
        # Save to database
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO media_assets (
                client_id, created_by, asset_type, asset_name,
                file_url, ai_generated, generation_type, prompt_used
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.client_id,
            current_user['user_id'],
            'presentation',  # Can be modified based on design_type
            request.title,
            result.get("edit_url", ""),
            True,
            "canva",
            json.dumps(request.content_elements)
        ))
        
        asset_id = cursor.lastrowid
        connection.commit()
        
        return {
            "success": True,
            "message": "Design created successfully",
            "asset_id": asset_id,
            "design_id": result.get("design_id"),
            "edit_url": result.get("edit_url")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error creating design: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create design: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/assets")
async def list_assets(
    client_id: Optional[int] = None,
    asset_type: Optional[str] = None,
    generation_type: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get list of media assets"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                ma.*,
                u.full_name as creator_name,
                c.full_name as client_name
            FROM media_assets ma
            LEFT JOIN users u ON ma.created_by = u.user_id
            LEFT JOIN users c ON ma.client_id = c.user_id
            WHERE 1=1
        """
        params = []
        
        # Role-based filtering
        if current_user['role'] == 'client':
            query += " AND ma.client_id = %s"
            params.append(current_user['user_id'])
        elif client_id:
            query += " AND ma.client_id = %s"
            params.append(client_id)
        
        if asset_type:
            query += " AND ma.asset_type = %s"
            params.append(asset_type)
        
        if generation_type:
            query += " AND ma.generation_type = %s"
            params.append(generation_type)
        
        query += " ORDER BY ma.created_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, tuple(params))
        assets = cursor.fetchall()
        
        return {
            "success": True,
            "data": assets
        }
        
    except Exception as e:
        print(f"Error fetching assets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch assets: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/assets/{asset_id}")
async def get_asset(
    asset_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get specific asset by ID"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                ma.*,
                u.full_name as creator_name,
                c.full_name as client_name
            FROM media_assets ma
            LEFT JOIN users u ON ma.created_by = u.user_id
            LEFT JOIN users c ON ma.client_id = c.user_id
            WHERE ma.asset_id = %s
        """, (asset_id,))
        
        asset = cursor.fetchone()
        
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found"
            )
        
        return {
            "success": True,
            "data": asset
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching asset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch asset: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: int,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Delete media asset"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            DELETE FROM media_assets 
            WHERE asset_id = %s
        """, (asset_id,))
        
        connection.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found"
            )
        
        return {
            "success": True,
            "message": "Asset deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error deleting asset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete asset: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()