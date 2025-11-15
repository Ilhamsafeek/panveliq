"""
Smart SEO Toolkit - Backend API
File: app/api/v1/endpoints/seo.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime, date
from jose import JWTError, jwt
import pymysql
import json
from openai import OpenAI
import requests
import traceback

from app.core.config import settings

router = APIRouter()

# Initialize OpenAI client (v1.0+)
try:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    print(f"Warning: OpenAI client initialization failed: {e}")
    client = None

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
        
        # For clients, use their own ID; for admin/employee, require client_id
        client_id = current_user['user_id']
        
        query = """
            INSERT INTO seo_projects 
            (client_id, website_url, target_keywords, status)
            VALUES (%s, %s, %s, 'active')
        """
        
        cursor.execute(query, (
            client_id,
            str(project.website_url),
            json.dumps(project.target_keywords)
        ))
        connection.commit()
        
        project_id = cursor.lastrowid
        
        return {
            "success": True,
            "message": "SEO project created successfully",
            "seo_project_id": project_id
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
8. meta_suggestions (title and description)

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


# ========== ON-PAGE AUDIT ==========

@router.post("/audit/run/{project_id}")
async def run_onpage_audit(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Run comprehensive on-page SEO audit"""
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
        
        # Run PageSpeed Insights audit (with error handling)
        try:
            pagespeed_score = await check_pagespeed(website_url)
        except Exception as e:
            print(f"PageSpeed check failed: {str(e)}")
            pagespeed_score = 0.0
        
        # AI-powered audit using OpenAI (with better error handling)
        try:
            if not client:
                raise Exception("OpenAI client not configured")
            
            audit_prompt = f"""
Perform a comprehensive on-page SEO audit for website: {website_url}

Provide detailed analysis in JSON format:
{{
  "overall_score": 75,
  "technical_issues": [
    {{"severity": "critical", "description": "Issue description"}},
    {{"severity": "warning", "description": "Issue description"}},
    {{"severity": "info", "description": "Issue description"}}
  ],
  "recommendations": ["Recommendation 1", "Recommendation 2", "Recommendation 3"],
  "meta_tags_analysis": "Analysis of title and description tags",
  "heading_structure": "H1-H6 structure analysis",
  "image_optimization": "Alt tags and file size analysis",
  "internal_linking": "Link structure quality",
  "mobile_friendliness": 85,
  "schema_markup": "present",
  "page_speed_insights": {pagespeed_score}
}}

Return ONLY valid JSON with no markdown formatting or explanations.
"""
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert technical SEO auditor. Return only valid JSON."},
                    {"role": "user", "content": audit_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Get response content
            response_content = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_content.startswith('```'):
                response_content = response_content.split('```')[1]
                if response_content.startswith('json'):
                    response_content = response_content[4:]
                response_content = response_content.strip()
            
            audit_data = json.loads(response_content)
            
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            # Return fallback audit data if OpenAI fails
            audit_data = {
                "overall_score": 70,
                "technical_issues": [
                    {"severity": "info", "description": "Audit completed with limited data due to API unavailability"}
                ],
                "recommendations": [
                    "Configure OpenAI API key to get detailed recommendations",
                    "Check meta tags and ensure they are optimized",
                    "Optimize images with proper alt text"
                ],
                "meta_tags_analysis": "Limited analysis available",
                "heading_structure": "Please configure API for detailed analysis",
                "image_optimization": "Please configure API for detailed analysis",
                "internal_linking": "Please configure API for detailed analysis",
                "mobile_friendliness": 75,
                "schema_markup": "unknown",
                "page_speed_insights": pagespeed_score
            }
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            print(f"Response content: {response_content}")
            # Return fallback data
            audit_data = {
                "overall_score": 70,
                "technical_issues": [
                    {"severity": "warning", "description": "Unable to parse detailed audit results"}
                ],
                "recommendations": [
                    "Review website structure manually",
                    "Check for broken links",
                    "Optimize page load speed"
                ],
                "meta_tags_analysis": "Analysis unavailable",
                "heading_structure": "Analysis unavailable",
                "image_optimization": "Analysis unavailable",
                "internal_linking": "Analysis unavailable",
                "mobile_friendliness": 75,
                "schema_markup": "unknown",
                "page_speed_insights": pagespeed_score
            }
        
        # Save audit results
        query = """
            INSERT INTO seo_audits 
            (seo_project_id, audit_date, overall_score, issues_found, 
             recommendations, page_speed_score)
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
        import traceback
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


async def check_pagespeed(url: str) -> float:
    """Check PageSpeed Insights score"""
    try:
        api_key = getattr(settings, 'GOOGLE_API_KEY', '')
        if not api_key:
            return 0.0
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}"
        
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            score = data.get('lighthouseResult', {}).get('categories', {}).get('performance', {}).get('score', 0)
            return round(score * 100, 2)
        return 0.0
    except:
        return 0.0


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

Return JSON with: {{"subject": "...", "body": "..."}}
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert SEO outreach specialist. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=800
        )
        
        # Get response content
        response_content = response.choices[0].message.content.strip()
        
        # Remove markdown if present
        if response_content.startswith('```'):
            response_content = response_content.split('```')[1]
            if response_content.startswith('json'):
                response_content = response_content[4:]
            response_content = response_content.strip()
        
        email_draft = json.loads(response_content)
        
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
    
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate email draft"
        )
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


# ========== KEYWORD TRACKING (SERP) ==========

@router.post("/keywords/track")
async def track_keyword(
    request: KeywordTrackingRequest,
    current_user: dict = Depends(get_current_user)
):
    """Track keyword position in SERP"""
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
        
        # Simulate SERP position check (In production, use real SERP API)
        current_position = await check_serp_position(project['website_url'], request.keyword)
        search_volume = await get_search_volume(request.keyword)
        
        # Save tracking data
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


async def check_serp_position(website_url: str, keyword: str) -> int:
    """Check current SERP position (simulated)"""
    # In production, integrate with Google Search Console API or Moz API
    # For now, return simulated position
    import random
    return random.randint(1, 100)


async def get_search_volume(keyword: str) -> int:
    """Get keyword search volume (simulated)"""
    # In production, integrate with Google Keyword Planner API or Moz API
    # For now, return simulated volume
    import random
    return random.randint(100, 10000)


@router.get("/keywords/history/{project_id}")
async def get_keyword_history(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get keyword tracking history"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT kt.* FROM keyword_tracking kt
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


# ========== VOICE & SEMANTIC SEARCH ==========

@router.post("/optimize-voice-search")
async def optimize_for_voice_search(
    content: str,
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
{content}

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


# ========== AUDIT HISTORY ==========

@router.get("/audits/list/{project_id}")
async def list_audits(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get all audits for a project"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT a.* FROM seo_audits a
            JOIN seo_projects p ON a.seo_project_id = p.seo_project_id
            WHERE a.seo_project_id = %s AND p.client_id = %s
            ORDER BY a.audit_date DESC
        """
        
        cursor.execute(query, (project_id, current_user['user_id']))
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
            "audits": audits,
            "total": len(audits)
        }
    
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