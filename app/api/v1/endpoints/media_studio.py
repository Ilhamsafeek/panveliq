"""
Creative Media Studio API - Module 8 (UPDATED WITH LOCAL FILE STORAGE)
File: app/api/v1/endpoints/media_studio.py
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import pymysql
import json
import requests
import base64
import os
import uuid
import hashlib
from openai import OpenAI

from app.core.config import settings
from app.core.security import require_admin_or_employee, get_current_user
from app.core.security import get_db_connection

router = APIRouter()

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Media storage directory
MEDIA_STORAGE_DIR = os.path.join(settings.UPLOAD_DIR, "media_assets")

# Ensure directory exists
os.makedirs(MEDIA_STORAGE_DIR, exist_ok=True)


# ========== UTILITY FUNCTIONS ==========

def download_and_save_file(url: str, asset_type: str, file_extension: str = None) -> Dict[str, str]:
    """
    Download file from URL and save to local storage.
    Returns local file path and URL.
    """
    try:
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Determine file extension
        if not file_extension:
            if asset_type == 'image':
                file_extension = 'png'
            elif asset_type == 'video':
                file_extension = 'mp4'
            elif asset_type == 'animation':
                file_extension = 'gif'
            else:
                file_extension = 'bin'
        
        filename = f"{asset_type}_{timestamp}_{unique_id}.{file_extension}"
        
        # Create subdirectory for asset type
        type_dir = os.path.join(MEDIA_STORAGE_DIR, asset_type + "s")
        os.makedirs(type_dir, exist_ok=True)
        
        file_path = os.path.join(type_dir, filename)
        
        # Download the file
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        
        # Save to disk
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Generate relative URL for serving
        relative_path = f"/static/uploads/media_assets/{asset_type}s/{filename}"
        
        print(f"[STORAGE] File saved: {file_path}")
        
        return {
            "file_path": file_path,
            "file_url": relative_path,
            "filename": filename
        }
        
    except Exception as e:
        print(f"[STORAGE] Error saving file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )


def save_base64_file(base64_data: str, asset_type: str, file_extension: str = None) -> Dict[str, str]:
    """
    Save base64 encoded data to local storage.
    Returns local file path and URL.
    """
    try:
        # Remove data URL prefix if present
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        # Decode base64
        file_data = base64.b64decode(base64_data)
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not file_extension:
            file_extension = 'png' if asset_type == 'image' else 'bin'
        
        filename = f"{asset_type}_{timestamp}_{unique_id}.{file_extension}"
        
        # Create subdirectory for asset type
        type_dir = os.path.join(MEDIA_STORAGE_DIR, asset_type + "s")
        os.makedirs(type_dir, exist_ok=True)
        
        file_path = os.path.join(type_dir, filename)
        
        # Save to disk
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # Generate relative URL for serving
        relative_path = f"/static/uploads/media_assets/{asset_type}s/{filename}"
        
        print(f"[STORAGE] Base64 file saved: {file_path}")
        
        return {
            "file_path": file_path,
            "file_url": relative_path,
            "filename": filename
        }
        
    except Exception as e:
        print(f"[STORAGE] Error saving base64 file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )


# ========== PYDANTIC MODELS ==========

class ImageGenerateRequest(BaseModel):
    """Request model for DALL-E image generation"""
    prompt: str = Field(..., description="Image description prompt")
    client_id: int
    size: str = Field("1024x1024", description="Image size: 1024x1024, 1024x1792, 1792x1024")
    quality: str = Field("standard", description="Quality: standard or hd")
    style: str = Field("vivid", description="Style: vivid or natural")
    n: int = Field(1, description="Number of images (1-4)")


class VideoGenerateRequest(BaseModel):
    """Request model for Synthesia video generation"""
    script: str = Field(..., description="Video script/narration")
    client_id: int
    avatar_id: Optional[str] = Field(None, description="Synthesia avatar ID")
    voice_id: Optional[str] = Field(None, description="Voice ID")
    background: Optional[str] = Field("white", description="Background color")
    title: Optional[str] = Field(None, description="Video title")


class AnimationGenerateRequest(BaseModel):
    """Request model for text-to-animation"""
    prompt: str = Field(..., description="Animation description")
    client_id: int
    title: str
    style: str = Field("modern", description="Animation style")
    duration: int = Field(5, description="Duration in seconds")


class ImageToVideoRequest(BaseModel):
    """Request model for image-to-video conversion"""
    client_id: int
    image_data: str = Field(..., description="Base64 encoded image")
    motion_prompt: str = Field(..., description="Motion description")
    duration: int = Field(5, description="Video duration in seconds")


class ImageToAnimationRequest(BaseModel):
    """Request model for image-to-animation conversion"""
    client_id: int
    image_data: str = Field(..., description="Base64 encoded image")
    animation_effect: str = Field(..., description="Animation effect description")
    animation_type: str = Field("loop", description="Animation type")


class CanvaDesignRequest(BaseModel):
    """Request model for Canva design"""
    design_type: str = Field(..., description="Design type: social_post, story, etc.")
    client_id: int
    title: str
    content_elements: Optional[Dict[str, Any]] = Field({}, description="Design content")


# ========== DALL-E IMAGE GENERATION ==========

async def generate_dalle_image(prompt: str, size: str, quality: str, style: str, n: int) -> Dict[str, Any]:
    """Generate images using DALL-E 3"""
    
    try:
        print(f"[DALL-E] Generating image: {prompt[:50]}...")
        
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
            # Download and save the image locally
            saved_file = download_and_save_file(
                url=image_data.url,
                asset_type='image',
                file_extension='png'
            )
            
            images.append({
                "url": saved_file["file_url"],  # Use local URL
                "original_url": image_data.url,  # Keep original for reference
                "file_path": saved_file["file_path"],
                "filename": saved_file["filename"],
                "revised_prompt": getattr(image_data, 'revised_prompt', prompt)
            })
        
        print(f"[DALL-E] Successfully generated and saved {len(images)} image(s)")
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
        print(f"[SYNTHESIA] Generating video: {script[:50]}...")
        
        api_url = "https://api.synthesia.io/v2/videos"
        avatar = avatar_id or settings.SYNTHESIA_AVATAR_ID or "anna_costume1_cameraA"
        
        headers = {
            "Authorization": settings.SYNTHESIA_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "test": True,  # Use test mode
            "title": title or "Generated Video",
            "input": [
                {
                    "scriptText": script,
                    "avatar": avatar,
                    "background": background
                }
            ]
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            result = response.json()
            video_id = result.get("id")
            
            print(f"[SYNTHESIA] Video created with ID: {video_id}")
            
            return {
                "success": True,
                "video_id": video_id,
                "status": "processing",
                "message": "Video is being generated. Check status endpoint for updates."
            }
        else:
            error_msg = response.json().get("message", "Unknown error")
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


# ========== IDEOGRAM ANIMATION GENERATION ==========

async def generate_ideogram_animation(
    prompt: str,
    style: str = "modern",
    aspect_ratio: str = "16:9"
) -> Dict[str, Any]:
    """Generate animation using Ideogram API"""
    
    try:
        print(f"[IDEOGRAM] Generating animation: {prompt[:50]}...")
        
        api_url = "https://api.ideogram.ai/generate"
        
        headers = {
            "Api-Key": settings.IDEOGRAM_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "image_request": {
                "prompt": f"animated {style} style: {prompt}",
                "model": "V_2",
                "aspect_ratio": aspect_ratio,
                "magic_prompt_option": "AUTO"
            }
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("data") and len(result["data"]) > 0:
                image_url = result["data"][0].get("url")
                
                if image_url:
                    # Download and save locally
                    saved_file = download_and_save_file(
                        url=image_url,
                        asset_type='animation',
                        file_extension='png'  # Ideogram returns PNG
                    )
                    
                    return {
                        "success": True,
                        "url": saved_file["file_url"],
                        "original_url": image_url,
                        "file_path": saved_file["file_path"],
                        "filename": saved_file["filename"]
                    }
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No animation generated"
            )
        else:
            error_msg = response.json().get("message", "Unknown error")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Ideogram API error: {error_msg}"
            )
            
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Ideogram API timeout"
        )
    except Exception as e:
        print(f"[IDEOGRAM] Error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ideogram generation failed: {str(e)}"
        )


# ========== CANVA DESIGN CREATION ==========

async def create_canva_design(
    design_type: str,
    title: str,
    content_elements: Optional[Dict] = None
) -> Dict[str, Any]:
    """Create design using Canva API"""
    
    try:
        print(f"[CANVA] Creating design: {title}")
        
        api_url = "https://api.canva.com/rest/v1/designs"
        
        headers = {
            "Authorization": f"Bearer {settings.CANVA_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Map design types to Canva asset types
        design_types_map = {
            "InstagramPost": "DAFVtKJq-Yc",
            "InstagramStory": "DAFVtFZq8Ss",
            "Presentation": "DAFVtOqq6Qo",
            "Logo": "DAFVtL8q5qY",
            "Flyer": "DAFVtMpqSIE",
            "Poster": "DAFVtNxqoI0",
            "Banner": "DAFVtPBqEwY",
            "FacebookPost": "DAFVtRJqiAA",
            "TwitterPost": "DAFVtSlqlZY",
            "LinkedInPost": "DAFVtT1qXsU"
        }
        
        asset_id = design_types_map.get(design_type, "DAFVtKJq-Yc")
        
        payload = {
            "asset_id": asset_id,
            "title": title
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            result = response.json()
            design_id = result.get("design", {}).get("id")
            edit_url = result.get("design", {}).get("urls", {}).get("edit_url")
            
            return {
                "success": True,
                "design_id": design_id,
                "edit_url": edit_url
            }
        else:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
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
    """Generate images using DALL-E and save locally"""
    
    connection = None
    cursor = None
    
    try:
        result = await generate_dalle_image(
            prompt=request.prompt,
            size=request.size,
            quality=request.quality,
            style=request.style,
            n=request.n
        )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        saved_assets = []
        
        for idx, image in enumerate(result["images"]):
            cursor.execute("""
                INSERT INTO media_assets (
                    client_id, created_by, asset_type, asset_name,
                    file_url, file_path, ai_generated, generation_type, prompt_used
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                request.client_id,
                current_user['user_id'],
                'image',
                f"DALL-E Image {idx + 1}",
                image["url"],  # Local URL
                image.get("file_path", ""),  # Local file path
                True,
                "dall-e-3",
                request.prompt
            ))
            
            saved_assets.append({
                "asset_id": cursor.lastrowid,
                "url": image["url"],
                "revised_prompt": image.get("revised_prompt", request.prompt)
            })
        
        connection.commit()
        
        return {
            "success": True,
            "assets": saved_assets,
            "model": "dall-e-3"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
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
        result = await generate_synthesia_video(
            script=request.script,
            avatar_id=request.avatar_id,
            voice_id=request.voice_id,
            background=request.background,
            title=request.title
        )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Save video asset with processing status
        cursor.execute("""
            INSERT INTO media_assets (
                client_id, created_by, asset_type, asset_name,
                file_url, ai_generated, generation_type, prompt_used,
                metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.client_id,
            current_user['user_id'],
            'video',
            request.title or "Synthesia Video",
            "",  # Will be updated when video is ready
            True,
            "synthesia",
            request.script,
            json.dumps({"video_id": result["video_id"], "status": "processing"})
        ))
        
        asset_id = cursor.lastrowid
        connection.commit()
        
        return {
            "success": True,
            "asset_id": asset_id,
            "video_id": result["video_id"],
            "status": "processing",
            "message": "Video is being generated. Check status for updates."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate video: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/video-status/{video_id}")
async def get_video_status(
    video_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Check Synthesia video generation status and download if ready"""
    
    connection = None
    cursor = None
    
    try:
        api_url = f"https://api.synthesia.io/v2/videos/{video_id}"
        
        headers = {
            "Authorization": settings.SYNTHESIA_API_KEY
        }
        
        response = requests.get(api_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            video_status = result.get("status", "unknown")
            
            # If video is complete, download and save locally
            if video_status == "complete":
                download_url = result.get("download")
                
                if download_url:
                    # Download and save the video
                    saved_file = download_and_save_file(
                        url=download_url,
                        asset_type='video',
                        file_extension='mp4'
                    )
                    
                    # Update the database with local file URL
                    connection = get_db_connection()
                    cursor = connection.cursor()
                    
                    cursor.execute("""
                        UPDATE media_assets 
                        SET file_url = %s, file_path = %s, 
                            metadata = JSON_SET(COALESCE(metadata, '{}'), '$.status', 'complete')
                        WHERE metadata->>'$.video_id' = %s
                    """, (saved_file["file_url"], saved_file["file_path"], video_id))
                    
                    connection.commit()
                    
                    return {
                        "success": True,
                        "video_id": video_id,
                        "status": "complete",
                        "url": saved_file["file_url"],
                        "download_url": saved_file["file_url"]
                    }
            
            return {
                "success": True,
                "video_id": video_id,
                "status": video_status
            }
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail="Failed to get video status"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video status: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/generate/animation")
async def generate_animation(
    request: AnimationGenerateRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Generate animation using Ideogram"""
    
    connection = None
    cursor = None
    
    try:
        result = await generate_ideogram_animation(
            prompt=request.prompt,
            style=request.style
        )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO media_assets (
                client_id, created_by, asset_type, asset_name,
                file_url, file_path, ai_generated, generation_type, prompt_used
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.client_id,
            current_user['user_id'],
            'animation',
            request.title,
            result["url"],  # Local URL
            result.get("file_path", ""),
            True,
            "ideogram",
            request.prompt
        ))
        
        asset_id = cursor.lastrowid
        connection.commit()
        
        return {
            "success": True,
            "asset_id": asset_id,
            "url": result["url"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate animation: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/image-to-video")
async def image_to_video(
    request: ImageToVideoRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Convert image to video using GPT-4 + Synthesia"""
    
    connection = None
    cursor = None
    
    try:
        # First save the uploaded image locally
        saved_image = save_base64_file(
            base64_data=request.image_data,
            asset_type='image',
            file_extension='png'
        )
        
        # Generate script using GPT-4
        script_response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative scriptwriter. Generate a short, engaging video narration based on the motion description provided."
                },
                {
                    "role": "user",
                    "content": f"Create a {request.duration} second video script for this motion: {request.motion_prompt}"
                }
            ],
            max_tokens=200
        )
        
        script = script_response.choices[0].message.content
        
        # Generate video with Synthesia
        video_result = await generate_synthesia_video(
            script=script,
            title=f"Image Video - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO media_assets (
                client_id, created_by, asset_type, asset_name,
                file_url, ai_generated, generation_type, prompt_used,
                metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.client_id,
            current_user['user_id'],
            'video',
            f"Image-to-Video",
            "",
            True,
            "synthesia",
            request.motion_prompt,
            json.dumps({
                "video_id": video_result["video_id"],
                "status": "processing",
                "source_image": saved_image["file_url"]
            })
        ))
        
        asset_id = cursor.lastrowid
        connection.commit()
        
        return {
            "success": True,
            "asset_id": asset_id,
            "video_id": video_result["video_id"],
            "status": "processing",
            "script": script
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert image to video: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/image-to-animation")
async def image_to_animation(
    request: ImageToAnimationRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Convert image to animation using Ideogram"""
    
    connection = None
    cursor = None
    
    try:
        # Save the uploaded image locally first
        saved_image = save_base64_file(
            base64_data=request.image_data,
            asset_type='image',
            file_extension='png'
        )
        
        # Generate animation prompt based on the effect
        animation_prompt = f"Animate with {request.animation_effect} effect, {request.animation_type} style animation"
        
        result = await generate_ideogram_animation(
            prompt=animation_prompt,
            style=request.animation_type
        )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO media_assets (
                client_id, created_by, asset_type, asset_name,
                file_url, file_path, ai_generated, generation_type, prompt_used,
                metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.client_id,
            current_user['user_id'],
            'animation',
            f"Image-to-Animation",
            result["url"],
            result.get("file_path", ""),
            True,
            "ideogram",
            request.animation_effect,
            json.dumps({"source_image": saved_image["file_url"]})
        ))
        
        asset_id = cursor.lastrowid
        connection.commit()
        
        return {
            "success": True,
            "asset_id": asset_id,
            "url": result["url"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert image to animation: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/create-design")
async def create_design(
    request: CanvaDesignRequest,
    current_user: dict = Depends(require_admin_or_employee)
):
    """Create design using Canva"""
    
    connection = None
    cursor = None
    
    try:
        result = await create_canva_design(
            design_type=request.design_type,
            title=request.title,
            content_elements=request.content_elements
        )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO media_assets (
                client_id, created_by, asset_type, asset_name,
                file_url, ai_generated, generation_type,
                metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request.client_id,
            current_user['user_id'],
            'presentation',
            request.title,
            result.get("edit_url", ""),
            True,
            "canva",
            json.dumps({"design_id": result["design_id"]})
        ))
        
        asset_id = cursor.lastrowid
        connection.commit()
        
        return {
            "success": True,
            "asset_id": asset_id,
            "design_id": result["design_id"],
            "edit_url": result["edit_url"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create design: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== ASSET MANAGEMENT ENDPOINTS ==========

@router.get("/assets")
async def get_assets(
    client_id: Optional[int] = None,
    asset_type: Optional[str] = None,
    generation_type: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get all media assets with optional filters"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
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
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch asset: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/assets/{asset_id}/download")
async def download_asset(
    asset_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Download asset file"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT asset_id, asset_name, file_url, file_path, asset_type
            FROM media_assets 
            WHERE asset_id = %s
        """, (asset_id,))
        
        asset = cursor.fetchone()
        
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found"
            )
        
        # Check if local file exists
        file_path = asset.get('file_path')
        if file_path and os.path.exists(file_path):
            # Determine media type
            media_types = {
                'image': 'image/png',
                'video': 'video/mp4',
                'animation': 'image/gif',
                'presentation': 'application/pdf'
            }
            media_type = media_types.get(asset['asset_type'], 'application/octet-stream')
            
            return FileResponse(
                path=file_path,
                filename=asset['asset_name'] or f"asset_{asset_id}",
                media_type=media_type
            )
        
        # Fallback: redirect to file_url
        file_url = asset.get('file_url')
        if file_url:
            return {"redirect_url": file_url}
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset file not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download asset: {str(e)}"
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
    """Delete media asset and its file"""
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Get file path before deleting
        cursor.execute("""
            SELECT file_path FROM media_assets WHERE asset_id = %s
        """, (asset_id,))
        
        asset = cursor.fetchone()
        
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found"
            )
        
        # Delete from database
        cursor.execute("""
            DELETE FROM media_assets 
            WHERE asset_id = %s
        """, (asset_id,))
        
        connection.commit()
        
        # Delete file from disk if exists
        file_path = asset.get('file_path')
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"[STORAGE] Deleted file: {file_path}")
            except Exception as e:
                print(f"[STORAGE] Warning: Could not delete file {file_path}: {e}")
        
        return {
            "success": True,
            "message": "Asset deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete asset: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()