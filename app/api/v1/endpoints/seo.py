"""
Smart SEO Toolkit - Backend API (UPDATED WITH REAL APIs)
File: app/api/v1/endpoints/seo.py

UPDATES:
1. Real Google PageSpeed Insights API integration
2. Real Moz API integration for keyword tracking
3. Improved error handling and fallbacks
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from jose import JWTError, jwt
import pymysql
import json
from openai import OpenAI
import requests
import traceback
import hmac
import hashlib
import base64

from app.core.config import settings
from app.services.moz_api_service import MozAPIService

from app.services.seo_service import SEOService

router = APIRouter()


seo_service = SEOService()

# Initialize OpenAI client (v1.0+)
try:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    print(f"Warning: OpenAI client initialization failed: {e}")
    client = None

# Initialize Moz API Service
try:
    moz_service = MozAPIService()
except Exception as e:
    print(f"Warning: Moz API service initialization failed: {e}")
    moz_service = None

# OAuth2 scheme - MUST be defined BEFORE get_current_user
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/{settings.API_VERSION}/auth/login")


# ========== DATABASE & AUTH FUNCTIONS ==========

def get_db_connection():
    """Get MySQL database connection"""
    try:
        connection = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {str(e)}"
        )


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    connection = None
    cursor = None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if email is None or user_id is None:
            raise credentials_exception
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(
            "SELECT user_id, email, full_name, role, status FROM users WHERE user_id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        
        if user is None:
            raise credentials_exception
        
        if user['status'] == 'suspended':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended"
            )
        
        return user
    
    except JWTError:
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== PYDANTIC MODELS ==========

class SEOProjectCreate(BaseModel):
    website_url: HttpUrl
    target_keywords: List[str]

class SEOProjectUpdate(BaseModel):
    website_url: Optional[HttpUrl] = None
    target_keywords: Optional[List[str]] = None
    status: Optional[str] = None

class ContentOptimizationRequest(BaseModel):
    content: str
    target_keyword: str
    content_type: str = "blog"

class BacklinkOutreachRequest(BaseModel):
    seo_project_id: int
    target_url: str
    anchor_text: str

class KeywordTrackingRequest(BaseModel):
    seo_project_id: int
    keyword: str

class VoiceSearchRequest(BaseModel):
    content: str


# ========== SEO PROJECTS ==========

@router.post("/projects/create")
async def create_seo_project(
    project: SEOProjectCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new SEO project"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get domain authority from Moz (if available)
        domain_authority = 0
        if moz_service:
            try:
                domain_metrics = moz_service.get_domain_metrics(str(project.website_url))
                domain_authority = domain_metrics.get('domain_authority', 0)
            except:
                pass
        
        # For clients, use their own ID
        client_id = current_user['user_id']
        
        query = """
            INSERT INTO seo_projects 
            (client_id, website_url, target_keywords, current_domain_authority, status)
            VALUES (%s, %s, %s, %s, 'active')
        """
        
        cursor.execute(query, (
            client_id,
            str(project.website_url),
            json.dumps(project.target_keywords),
            domain_authority
        ))
        connection.commit()
        
        project_id = cursor.lastrowid
        
        return {
            "success": True,
            "message": "SEO project created successfully",
            "seo_project_id": project_id,
            "domain_authority": domain_authority
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create SEO project: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/projects/list")
async def list_seo_projects(current_user: dict = Depends(get_current_user)):
    """Get all SEO projects for current user"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Filter by client_id
        client_id = current_user['user_id']
        
        query = """
            SELECT seo_project_id, client_id, website_url, target_keywords,
                   current_domain_authority, status, created_at
            FROM seo_projects
            WHERE client_id = %s
            ORDER BY created_at DESC
        """
        
        cursor.execute(query, (client_id,))
        projects = cursor.fetchall()
        
        # Parse JSON fields and convert datetime
        for project in projects:
            if project['target_keywords']:
                project['target_keywords'] = json.loads(project['target_keywords'])
            if project['created_at']:
                project['created_at'] = project['created_at'].isoformat()
        
        return {
            "success": True,
            "projects": projects,
            "total": len(projects)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch SEO projects: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/projects/{project_id}")
async def get_seo_project(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get specific SEO project details"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT * FROM seo_projects
            WHERE seo_project_id = %s AND client_id = %s
        """
        
        cursor.execute(query, (project_id, current_user['user_id']))
        project = cursor.fetchone()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SEO project not found"
            )
        
        # Parse JSON and convert datetime
        if project['target_keywords']:
            project['target_keywords'] = json.loads(project['target_keywords'])
        if project['created_at']:
            project['created_at'] = project['created_at'].isoformat()
        
        return {
            "success": True,
            "project": project
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch SEO project: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== AI CONTENT OPTIMIZATION ==========

@router.post("/optimize-content")
async def optimize_content(
    request: ContentOptimizationRequest,
    current_user: dict = Depends(get_current_user)
):
    """AI-based content optimization with scoring"""
    try:
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI service is not configured"
            )
        
        # Analyze content using OpenAI
        prompt = f"""
You are an expert SEO content analyzer. Analyze the following content for SEO optimization.

Target Keyword: {request.target_keyword}
Content Type: {request.content_type}

Content:
{request.content}

Provide a comprehensive SEO analysis in JSON format with:
1. overall_score (0-100)
2. keyword_density (percentage)
3. readability_score (0-100)
4. semantic_relevance (0-100)
5. voice_search_optimized (true/false)
6. recommendations (array of specific improvements)
7. strengths (array of positive points)
8. meta_suggestions (object with title and description keys)

Return only valid JSON, no explanations.
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an SEO expert providing detailed content analysis. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        # Get response content
        response_content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if response_content.startswith('```'):
            response_content = response_content.split('```')[1]
            if response_content.startswith('json'):
                response_content = response_content[4:]
            response_content = response_content.strip()
        
        analysis = json.loads(response_content)
        
        return {
            "success": True,
            "optimization": analysis,
            "target_keyword": request.target_keyword,
            "content_length": len(request.content.split())
        }
    
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse AI response"
        )
    except Exception as e:
        print(f"Content optimization error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content optimization failed: {str(e)}"
        )


# ========== ON-PAGE AUDIT WITH REAL PAGESPEED API ==========

@router.post("/audit/run/{project_id}")
async def run_onpage_audit(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Run comprehensive on-page SEO audit with REAL PageSpeed API"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get project details
        cursor.execute(
            "SELECT website_url FROM seo_projects WHERE seo_project_id = %s AND client_id = %s",
            (project_id, current_user['user_id'])
        )
        project = cursor.fetchone()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SEO project not found"
            )
        
        website_url = project['website_url']
        
        # REAL PageSpeed Insights API Call
        pagespeed_score = await check_pagespeed_real(website_url)
        
        # AI-powered audit using OpenAI
        audit_data = await generate_ai_audit(website_url, pagespeed_score)
        
        # Save audit to database
        query = """
            INSERT INTO seo_audits 
            (seo_project_id, audit_date, overall_score, issues_found, recommendations, page_speed_score)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            project_id,
            date.today(),
            audit_data.get('overall_score', 70),
            json.dumps(audit_data.get('technical_issues', [])),
            json.dumps(audit_data.get('recommendations', [])),
            pagespeed_score
        ))
        connection.commit()
        
        audit_id = cursor.lastrowid
        
        return {
            "success": True,
            "audit_id": audit_id,
            "audit_data": audit_data,
            "page_speed_score": pagespeed_score
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Audit error details: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audit failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


async def check_pagespeed_real(url: str) -> float:
    """REAL Google PageSpeed Insights API Implementation"""
    
    # Check if API key is configured
    api_key = settings.GOOGLE_API_KEY
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google PageSpeed API key is required. Please configure GOOGLE_API_KEY in environment variables."
        )
    
    try:
        # Google PageSpeed Insights API v5
        api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        
        params = {
            'url': url,
            'key': api_key,
            'category': ['performance', 'accessibility', 'best-practices', 'seo'],
            'strategy': 'mobile'
        }
        
        print(f"Calling PageSpeed API for {url}...")
        response = requests.get(api_url, params=params, timeout=45)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract performance score
            lighthouse_result = data.get('lighthouseResult', {})
            categories = lighthouse_result.get('categories', {})
            performance = categories.get('performance', {})
            score = performance.get('score', 0)
            
            # Convert to 0-100 scale
            pagespeed_score = round(score * 100, 1)
            
            print(f"✅ PageSpeed Score for {url}: {pagespeed_score}/100")
            return pagespeed_score
        elif response.status_code == 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid URL or PageSpeed API request: {response.text}"
            )
        elif response.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="PageSpeed API rate limit exceeded. Please try again later."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"PageSpeed API error: {response.status_code} - {response.text[:200]}"
            )
    
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="PageSpeed API request timed out. The website may be slow or unavailable."
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"⚠️ PageSpeed check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PageSpeed check failed: {str(e)}"
        )



async def generate_ai_audit(website_url: str, pagespeed_score: float) -> Dict[str, Any]:
    """Generate AI-powered audit analysis - REQUIRES OpenAI API"""
    
    # Check if OpenAI is configured
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API is required for SEO audit. Please configure OPENAI_API_KEY in environment variables."
        )
    
    try:
        audit_prompt = f"""
Perform a comprehensive on-page SEO audit for website: {website_url}
Current PageSpeed Score: {pagespeed_score}/100

Provide detailed analysis in JSON format with AT LEAST 8-10 technical issues:
{{
  "overall_score": 75,
  "technical_issues": [
    {{"severity": "critical", "description": "Specific critical issue"}},
    {{"severity": "critical", "description": "Another critical issue"}},
    {{"severity": "warning", "description": "Warning level issue"}},
    {{"severity": "warning", "description": "Another warning"}},
    {{"severity": "warning", "description": "Additional warning"}},
    {{"severity": "info", "description": "Informational issue"}},
    {{"severity": "info", "description": "Another info item"}},
    {{"severity": "info", "description": "Additional info"}},
    {{"severity": "info", "description": "More information"}},
    {{"severity": "info", "description": "Final info point"}}
  ],
  "recommendations": [
    "Recommendation 1", 
    "Recommendation 2", 
    "Recommendation 3",
    "Recommendation 4",
    "Recommendation 5",
    "Recommendation 6"
  ],
  "mobile_friendliness": 85,
  "schema_markup": "present"
}}

IMPORTANT RULES:
1. Include AT LEAST 8-10 technical issues covering: meta tags, headings, images, links, performance, mobile, security, accessibility
2. Use severity levels: "critical" (major SEO impact), "warning" (moderate impact), "info" (minor/best practice)
3. Be specific and actionable in descriptions
4. Base overall_score on the PageSpeed score ({pagespeed_score}) adjusted for other factors
5. Provide at least 6 actionable recommendations
6. Return ONLY valid JSON with no markdown formatting

Return ONLY valid JSON.
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert technical SEO auditor. Return only valid JSON with comprehensive technical issues list. No markdown, no explanations."},
                {"role": "user", "content": audit_prompt}
            ],
            temperature=0.7,
            max_tokens=2500
        )
        
        # Get response content
        response_content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if response_content.startswith('```'):
            response_content = response_content.split('```')[1]
            if response_content.startswith('json'):
                response_content = response_content[4:]
            response_content = response_content.strip()
        
        # Parse JSON response
        audit_data = json.loads(response_content)
        
        # Validate required fields
        required_fields = ['overall_score', 'technical_issues', 'recommendations', 'mobile_friendliness', 'schema_markup']
        for field in required_fields:
            if field not in audit_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate we have enough technical issues
        if len(audit_data.get('technical_issues', [])) < 5:
            raise ValueError(f"Insufficient technical issues returned: {len(audit_data.get('technical_issues', []))}. Expected at least 5.")
        
        # Validate we have recommendations
        if len(audit_data.get('recommendations', [])) < 3:
            raise ValueError(f"Insufficient recommendations returned: {len(audit_data.get('recommendations', []))}. Expected at least 3.")
        
        print(f"✅ Successfully generated audit with {len(audit_data['technical_issues'])} issues and {len(audit_data['recommendations'])} recommendations")
        
        return audit_data
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {str(e)}")
        print(f"Response content: {response_content}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse AI response as JSON: {str(e)}"
        )
    except ValueError as e:
        print(f"❌ Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI response validation failed: {str(e)}"
        )
    except Exception as e:
        print(f"❌ Audit generation error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audit generation failed: {str(e)}"
        )



@router.get("/audits/list/{project_id}")
async def list_audits(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get audit history for a project"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify project ownership
        cursor.execute(
            "SELECT seo_project_id FROM seo_projects WHERE seo_project_id = %s AND client_id = %s",
            (project_id, current_user['user_id'])
        )
        
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SEO project not found"
            )
        
        # Get audits
        query = """
            SELECT * FROM seo_audits
            WHERE seo_project_id = %s
            ORDER BY audit_date DESC
            LIMIT 10
        """
        
        cursor.execute(query, (project_id,))
        audits = cursor.fetchall()
        
        # Parse JSON fields
        for audit in audits:
            if audit['issues_found']:
                audit['issues_found'] = json.loads(audit['issues_found'])
            if audit['recommendations']:
                audit['recommendations'] = json.loads(audit['recommendations'])
            if audit['audit_date']:
                audit['audit_date'] = audit['audit_date'].isoformat()
            if audit['created_at']:
                audit['created_at'] = audit['created_at'].isoformat()
        
        return {
            "success": True,
            "audits": audits
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch audits: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== KEYWORD TRACKING WITH REAL MOZ API ==========
@router.post("/keywords/track")
async def track_keyword(
    request: KeywordTrackingRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Track keyword position using REAL API integration
    - Uses Google Search Console API (if configured)
    - Falls back to Moz API for keyword metrics
    - Uses GPT-4 for keyword analysis
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify project ownership
        cursor.execute(
            "SELECT website_url FROM seo_projects WHERE seo_project_id = %s AND client_id = %s",
            (request.seo_project_id, current_user['user_id'])
        )
        project = cursor.fetchone()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SEO project not found"
            )
        
        website_url = project['website_url']
        
        # REAL API INTEGRATION: Get actual keyword position and metrics
        keyword_data = await get_real_keyword_data(website_url, request.keyword)
        
        current_position = keyword_data['position']
        search_volume = keyword_data['search_volume']
        
        # Save tracking data to database
        query = """
            INSERT INTO keyword_tracking 
            (seo_project_id, keyword, search_volume, current_position, tracked_date)
            VALUES (%s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            request.seo_project_id,
            request.keyword,
            search_volume,
            current_position,
            date.today()
        ))
        connection.commit()
        
        return {
            "success": True,
            "keyword": request.keyword,
            "current_position": current_position,
            "search_volume": search_volume,
            "difficulty": keyword_data.get('difficulty', 0),
            "tracked_date": date.today().isoformat()
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Keyword tracking failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


async def get_real_keyword_data(website_url: str, keyword: str) -> Dict[str, Any]:
    """
    Get REAL keyword data using Google Search Console and Moz APIs
    
    Returns:
        Dict with position, search_volume, difficulty, etc.
    """
    try:
        # Clean URL (remove http://, https://, www.)
        clean_url = website_url.replace('http://', '').replace('https://', '').replace('www.', '')
        
        # Method 1: Try Google Search Console API (if configured)
        position = await check_serp_position_google(clean_url, keyword)
        
        # Method 2: Get search volume and difficulty from Moz API
        moz_data = await get_moz_keyword_data(keyword)
        
        search_volume = moz_data.get('search_volume', 0)
        difficulty = moz_data.get('difficulty', 0)
        
        # If position is still None, use GPT-4 to estimate based on domain authority
        if position is None or position == 0:
            position = await estimate_keyword_position(clean_url, keyword)
        
        return {
            'position': position,
            'search_volume': search_volume,
            'difficulty': difficulty,
            'source': 'google_search_console' if position else 'estimated'
        }
        
    except Exception as e:
        # Fallback to estimated data if APIs fail
        return {
            'position': await estimate_keyword_position(website_url, keyword),
            'search_volume': 0,
            'difficulty': 0,
            'source': 'estimated',
            'error': str(e)
        }


async def check_serp_position_google(website_url: str, keyword: str) -> Optional[int]:
    """
    Check REAL keyword position using Google Search Console API
    
    Note: Requires OAuth2 authentication setup
    """
    try:
        # Check if Search Console credentials are configured
        if not hasattr(settings, 'SEARCH_CONSOLE_SERVICE_ACCOUNT_EMAIL'):
            return None
        
        # Use Search Console API to get actual keyword position
        search_data = seo_service.get_search_analytics(
            site_url=f"https://{website_url}",
            start_date=(date.today() - timedelta(days=7)).isoformat(),
            end_date=date.today().isoformat(),
            dimensions=['query']
        )
        
        if search_data.get('success') and search_data.get('rows'):
            # Find the specific keyword in results
            for row in search_data['rows']:
                if row['keys'][0].lower() == keyword.lower():
                    return int(row.get('position', 0))
        
        return None
        
    except Exception as e:
        print(f"Google Search Console error: {str(e)}")
        return None

async def get_moz_keyword_data(keyword: str) -> Dict[str, Any]:
    """
    Get keyword metrics from Moz API (search volume, difficulty)
    """
    try:
        # Check if Moz credentials are configured
        if not settings.MOZ_ACCESS_ID or not settings.MOZ_SECRET_KEY:
            print("Moz API not configured, returning zeros")
            return {'search_volume': 0, 'difficulty': 0}
        
        # Moz API uses Keyword Explorer endpoint
        # Documentation: https://moz.com/help/moz-api/mozscape/api-reference/url-metrics
        
        expires = int((datetime.now() + timedelta(minutes=5)).timestamp())
        access_id = settings.MOZ_ACCESS_ID
        secret_key = settings.MOZ_SECRET_KEY
        
        # Generate authentication signature
        string_to_sign = f"{access_id}\n{expires}"
        signature = hmac.new(
            secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
        auth_string = base64.b64encode(signature).decode('utf-8')
        
        # Moz Keyword Research API endpoint
        # Note: This requires a paid Moz Pro subscription with API access
        url = "https://lsapi.seomoz.com/v2/keyword_research"
        
        headers = {
            'Authorization': f'Basic {base64.b64encode(f"{access_id}:{auth_string}".encode()).decode()}'
        }
        
        params = {
            'Expires': expires
        }
        
        # Request body for keyword metrics
        payload = {
            'keyword': keyword,
            'location': 'IN'  # India
        }
        
        response = requests.post(url, headers=headers, params=params, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'search_volume': data.get('monthly_volume', 0),
                'difficulty': data.get('difficulty', 0),
                'opportunity': data.get('opportunity', 0),
                'source': 'moz_api'
            }
        else:
            print(f"Moz API error: {response.status_code} - {response.text}")
            return {'search_volume': 0, 'difficulty': 0}
        
    except Exception as e:
        print(f"Moz API error: {str(e)}")
        return {'search_volume': 0, 'difficulty': 0}


@router.get("/test-moz-credentials")
async def test_moz_credentials():
    """Test if Moz API credentials are valid"""
    try:
        if not settings.MOZ_ACCESS_ID or not settings.MOZ_SECRET_KEY:
            return {
                "success": False,
                "error": "Moz credentials not configured in .env file"
            }
        
        # Test with URL Metrics endpoint (basic endpoint)
        auth_string = base64.b64encode(
            f"{settings.MOZ_ACCESS_ID}:{settings.MOZ_SECRET_KEY}".encode()
        ).decode()
        
        headers = {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/json'
        }
        
        url = "https://lsapi.seomoz.com/v2/url_metrics"
        payload = {"targets": ["moz.com"]}
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "response": response.text[:500],  # First 500 chars
            "credentials_format": {
                "access_id_length": len(settings.MOZ_ACCESS_ID),
                "secret_key_length": len(settings.MOZ_SECRET_KEY)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def estimate_keyword_position(website_url: str, keyword: str) -> int:
    """
    Use GPT-4 to estimate keyword position based on domain authority
    This is a fallback when real APIs are not configured
    """
    try:
        if not client:
            # If no OpenAI client, return a reasonable estimate
            return 51  # Beyond first page
        
        # Get domain authority
        domain_data = seo_service.get_domain_authority(f"https://{website_url}")
        da = domain_data.get('domain_authority', 0) if domain_data.get('success') else 0
        
        prompt = f"""
Based on the following information, estimate the likely Google SERP position:
- Domain Authority: {da}/100
- Keyword: "{keyword}"
- Website: {website_url}

Return ONLY a number between 1-100 representing the estimated position.
Consider:
- DA 60+: positions 1-20
- DA 40-60: positions 20-50
- DA 20-40: positions 50-80
- DA <20: positions 80-100
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an SEO expert. Return only a number."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=10
        )
        
        position_str = response.choices[0].message.content.strip()
        position = int(''.join(filter(str.isdigit, position_str)))
        
        return max(1, min(position, 100))  # Ensure between 1-100
        
    except Exception as e:
        print(f"GPT-4 estimation error: {str(e)}")
        return 51  # Default fallback





async def analyze_keyword_with_ai(keyword: str) -> Dict[str, Any]:
    """Use OpenAI to intelligently estimate keyword metrics"""
    
    if not client:
        # Simple estimation based on keyword characteristics
        word_count = len(keyword.split())
        keyword_length = len(keyword)
        
        # Estimate search volume (shorter, fewer words = higher volume typically)
        base_volume = 10000
        if word_count == 1:
            search_volume = base_volume
        elif word_count == 2:
            search_volume = base_volume // 2
        elif word_count == 3:
            search_volume = base_volume // 4
        else:
            search_volume = base_volume // 8
        
        # Estimate difficulty (shorter = harder)
        difficulty = min(100, max(10, 100 - (word_count * 15)))
        
        # Estimate position (inversely related to difficulty)
        estimated_position = min(100, max(1, difficulty))
        
        return {
            'search_volume': search_volume,
            'difficulty': difficulty,
            'estimated_position': estimated_position
        }
    
    try:
        # Use AI to provide intelligent estimates
        prompt = f"""
Analyze the keyword: "{keyword}"

Provide SEO metrics estimation in JSON format:
{{
  "search_volume": 5000,
  "difficulty": 65,
  "estimated_position": 45,
  "keyword_type": "commercial/informational/navigational/transactional",
  "competition": "low/medium/high"
}}

Guidelines:
- search_volume: Estimated monthly searches (100-100000)
- difficulty: How hard to rank (0-100, higher = harder)
- estimated_position: Likely starting position for new content (1-100)
- Short generic keywords = high volume, high difficulty
- Long-tail specific keywords = lower volume, lower difficulty
- Brand keywords = very high volume
- Question keywords = medium volume, medium difficulty

Return ONLY valid JSON.
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an SEO keyword analyst. Return only valid JSON with no markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        response_content = response.choices[0].message.content.strip()
        
        # Remove markdown if present
        if response_content.startswith('```'):
            response_content = response_content.split('```')[1]
            if response_content.startswith('json'):
                response_content = response_content[4:]
            response_content = response_content.strip()
        
        analysis = json.loads(response_content)
        
        # Validate and ensure we have required fields
        return {
            'search_volume': analysis.get('search_volume', 1000),
            'difficulty': analysis.get('difficulty', 50),
            'estimated_position': analysis.get('estimated_position', 50),
            'keyword_type': analysis.get('keyword_type', 'informational'),
            'competition': analysis.get('competition', 'medium')
        }
        
    except Exception as e:
        print(f"AI keyword analysis failed: {str(e)}")
        # Fallback to simple estimation
        word_count = len(keyword.split())
        return {
            'search_volume': max(100, 10000 // (word_count * 2)),
            'difficulty': min(100, 30 + (word_count * 10)),
            'estimated_position': 50
        }
        
@router.get("/keywords/history/{project_id}")
async def get_keyword_history(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get keyword tracking history with real data"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT kt.*
            FROM keyword_tracking kt
            JOIN seo_projects p ON kt.seo_project_id = p.seo_project_id
            WHERE kt.seo_project_id = %s AND p.client_id = %s
            ORDER BY kt.tracked_date DESC, kt.keyword ASC
        """
        
        cursor.execute(query, (project_id, current_user['user_id']))
        keywords = cursor.fetchall()
        
        # Convert dates
        for kw in keywords:
            if kw['tracked_date']:
                kw['tracked_date'] = kw['tracked_date'].isoformat()
            if kw['created_at']:
                kw['created_at'] = kw['created_at'].isoformat()
        
        return {
            "success": True,
            "keywords": keywords,
            "total": len(keywords)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch keyword history: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

            

# ========== BACKLINK MANAGEMENT ==========

@router.post("/backlinks/suggest")
async def suggest_backlinks(
    request: BacklinkOutreachRequest,
    current_user: dict = Depends(get_current_user)
):
    """AI-powered backlink suggestions with email outreach draft"""
    connection = None
    cursor = None
    
    try:
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI service is not configured"
            )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Verify project ownership
        cursor.execute(
            "SELECT website_url FROM seo_projects WHERE seo_project_id = %s AND client_id = %s",
            (request.seo_project_id, current_user['user_id'])
        )
        project = cursor.fetchone()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SEO project not found"
            )
        
        # Generate outreach email using AI
        prompt = f"""
Create a professional backlink outreach email for:

Our Website: {project['website_url']}
Target Website: {request.target_url}
Anchor Text: {request.anchor_text}

Generate a personalized, professional outreach email that:
1. Introduces our brand professionally
2. Explains why a backlink would be mutually beneficial
3. Suggests specific content/page for the link
4. Is concise and respectful
5. Includes a clear call-to-action

Return ONLY valid JSON with this exact structure:
{{"subject": "Your email subject here", "body": "Your email body here"}}

No markdown, no explanations, just the JSON.
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert SEO outreach specialist. Return ONLY valid JSON with subject and body keys. No markdown formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=800
        )
        
        # Get response content
        response_content = response.choices[0].message.content.strip()
        
        # Remove markdown if present
        if response_content.startswith('```'):
            lines = response_content.split('\n')
            response_content = '\n'.join(lines[1:-1])  # Remove first and last line
            response_content = response_content.strip()
        
        # Try to parse JSON
        try:
            email_draft = json.loads(response_content)
            
            # Ensure required keys exist
            if 'subject' not in email_draft or 'body' not in email_draft:
                # Fallback to creating structure
                email_draft = {
                    "subject": "Partnership Opportunity - Quality Backlink Exchange",
                    "body": response_content if isinstance(response_content, str) else "Regarding a potential collaboration opportunity..."
                }
        except json.JSONDecodeError as e:
            print(f"JSON decode failed: {str(e)}")
            # Create fallback email
            email_draft = {
                "subject": "Partnership Opportunity - Quality Backlink Exchange",
                "body": f"Hi,\n\nI hope this email finds you well. I'm reaching out from {project['website_url']} regarding a potential collaboration.\n\nWe've been following your work at {request.target_url} and believe there could be mutual value in connecting our audiences.\n\nWould you be interested in discussing how we might work together?\n\nBest regards"
            }
        
        # Save backlink record
        query = """
            INSERT INTO backlinks 
            (seo_project_id, source_url, target_url, anchor_text, outreach_email, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
        """
        
        cursor.execute(query, (
            request.seo_project_id,
            request.target_url,
            project['website_url'],
            request.anchor_text,
            json.dumps(email_draft)
        ))
        connection.commit()
        
        backlink_id = cursor.lastrowid
        
        return {
            "success": True,
            "backlink_id": backlink_id,
            "email_draft": email_draft
        }
    
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Backlink error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backlink suggestion failed: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/backlinks/list/{project_id}")
async def list_backlinks(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all backlinks for a project"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT b.* FROM backlinks b
            JOIN seo_projects p ON b.seo_project_id = p.seo_project_id
            WHERE b.seo_project_id = %s AND p.client_id = %s
            ORDER BY b.created_at DESC
        """
        
        cursor.execute(query, (project_id, current_user['user_id']))
        backlinks = cursor.fetchall()
        
        # Parse JSON fields
        for backlink in backlinks:
            if backlink['outreach_email']:
                backlink['outreach_email'] = json.loads(backlink['outreach_email'])
            if backlink['created_at']:
                backlink['created_at'] = backlink['created_at'].isoformat()
        
        return {
            "success": True,
            "backlinks": backlinks,
            "total": len(backlinks)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch backlinks: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== VOICE & SEMANTIC SEARCH ==========

@router.post("/optimize-voice-search")
async def optimize_for_voice_search(
    request: VoiceSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """Optimize content for voice and semantic search"""
    try:
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI service is not configured"
            )
        
        prompt = f"""
Analyze and optimize the following content for voice search and semantic SEO.

Content:
{request.content}

Provide JSON response with:
1. voice_search_score (0-100)
2. conversational_tone_score (0-100)
3. question_based_optimization (suggested questions to add)
4. featured_snippet_potential (high/medium/low)
5. semantic_improvements (array of suggestions)
6. long_tail_keywords (suggested phrases)
7. local_seo_opportunities (if applicable)
8. structured_data_recommendations (schema types)

Return only valid JSON.
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a voice search and semantic SEO expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        # Get response content
        response_content = response.choices[0].message.content.strip()
        
        # Remove markdown if present
        if response_content.startswith('```'):
            response_content = response_content.split('```')[1]
            if response_content.startswith('json'):
                response_content = response_content[4:]
            response_content = response_content.strip()
        
        optimization = json.loads(response_content)
        
        return {
            "success": True,
            "voice_optimization": optimization
        }
    
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse optimization data"
        )
    except Exception as e:
        print(f"Voice optimization error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice search optimization failed: {str(e)}"
        )