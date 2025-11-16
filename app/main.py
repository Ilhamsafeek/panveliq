"""
UPDATED VERSION OF: app/main.py
ADD THE ONBOARDING ROUTES TO YOUR EXISTING main.py

PanvelIQ - AI-powered Digital Marketing Intelligence Platform
Main FastAPI Application Entry Point
"""

from fastapi import FastAPI, Request, HTTPException, status, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
from jose import JWTError, jwt

from app.core.config import settings
from app.api.v1.router import api_router

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered Digital Marketing Intelligence Platform",
    version="1.0.0",
    docs_url=f"/api/{settings.API_VERSION}/docs",
    redoc_url=f"/api/{settings.API_VERSION}/redoc",
    openapi_url=f"/api/{settings.API_VERSION}/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include API routes
app.include_router(api_router, prefix=f"/api/{settings.API_VERSION}")


# ========== ROOT & LANDING PAGE ==========

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Landing page / Homepage"""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": settings.APP_NAME}
    )


# ========== AUTHENTICATION PAGES ==========

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "hide_navbar": True,
            "hide_footer": True
        }
    )


@app.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    return templates.TemplateResponse(
        "auth/register.html",
        {
            "request": request,
            "hide_navbar": True,
            "hide_footer": True
        }
    )


@app.get("/auth/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Forgot password page"""
    return templates.TemplateResponse(
        "auth/forgot-password.html",
        {
            "request": request,
            "hide_navbar": True,
            "hide_footer": True
        }
    )


# ========== ONBOARDING PAGES (NEW) ==========

@app.get("/onboarding/select-package", response_class=HTMLResponse)
async def select_package_page(request: Request):
    """
    Package selection page - Entry Point 1
    User lands here after successful registration
    """
    return templates.TemplateResponse(
        "onboarding/select-package.html",
        {
            "request": request,
            "hide_navbar": True,
            "hide_footer": True
        }
    )


@app.get("/onboarding/verification", response_class=HTMLResponse)
async def verification_page(request: Request):
    """
    Verification page - Entry Point 2
    User lands here after selecting a package
    """
    return templates.TemplateResponse(
        "onboarding/verification.html",
        {
            "request": request,
            "hide_navbar": True,
            "hide_footer": True
        }
    )


# ========== DASHBOARD PAGES ==========

@app.get("/dashboard/client", response_class=HTMLResponse)
async def client_dashboard(request: Request):
    """Client dashboard"""
    return templates.TemplateResponse(
        "dashboard/client.html",
        {"request": request, "show_sidebar": True}
    )


@app.get("/dashboard/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard"""
    return templates.TemplateResponse(
        "dashboard/admin.html",
        {"request": request, "show_sidebar": True}
    )


@app.get("/dashboard/employee", response_class=HTMLResponse)
async def employee_dashboard(request: Request):
    """Employee dashboard"""
    return templates.TemplateResponse(
        "dashboard/employee.html",
        {"request": request, "show_sidebar": True}
    )


# ========== ADMIN PAGES (NEW) ==========

@app.get("/admin/onboarding-verifications", response_class=HTMLResponse)
async def onboarding_verifications_page(request: Request):
    """
    Admin verification panel - Entry Point 3
    Admin uses this to review and approve onboarding requests
    """
    return templates.TemplateResponse(
        "admin/onboarding-verifications.html",
        {
            "request": request,
            "show_sidebar": True
        }
    )


# ========== MODULE PAGES ==========

@app.get("/modules/project-planner", response_class=HTMLResponse)
async def project_planner_page(request: Request):
    """
    Project Planner module page
    """
    # Get token from cookie if available
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        # Check for token in Authorization header (for testing)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    # Try to decode token and get user role
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Verify role is admin or employee
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee role required."
            )
        
        return templates.TemplateResponse(
            "modules/project-planner.html",
            {
                "request": request,
                "show_sidebar": True,
                "user_role": role
            }
        )
    
    except JWTError:
        # Invalid token, serve page and let JS handle it
        return templates.TemplateResponse(
            "modules/project-planner.html",
            {
                "request": request,
                "show_sidebar": True,
                "user_role": None
            }
        )
    except Exception as e:
        # Serve page and let JS handle auth
        return templates.TemplateResponse(
            "modules/project-planner.html",
            {
                "request": request,
                "show_sidebar": True,
                "user_role": None
            }
        )



@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request):
    """
    Clients management page
    Accessible by admin and employees
    """
    # Get token from cookie if available
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        # Check for token in Authorization header (for testing)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    # Try to decode token and get user role
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Verify role is admin or employee
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee role required."
            )
        
        # Render the page
        return templates.TemplateResponse(
            "clients/index.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        # Invalid token - redirect to login
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing clients page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )


@app.get("/clients/{client_id}", response_class=HTMLResponse)
async def client_detail_page(request: Request, client_id: int):
    """
    Individual client detail page
    Accessible by admin and assigned employees
    """
    # Get token from cookie if available
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        # Check for token in Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    # Try to decode token and get user role
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Verify role is admin or employee
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee role required."
            )
        
        # Render the page (we'll create this template next)
        return templates.TemplateResponse(
            "clients/detail.html",
            {
                "request": request,
                "show_sidebar": True,
                "client_id": client_id
            }
        )
        
    except JWTError:
        # Invalid token - redirect to login
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing client detail page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )



# ========== MODULE PAGES ==========

@app.get("/modules/communication", response_class=HTMLResponse)
async def communication_page(request: Request):
    """
    Communication Hub module page
    """
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee role required."
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials."
        )
    
    return templates.TemplateResponse(
        "modules/communication.html",
        {
            "request": request,
            "show_sidebar": True,
            
        }
    )


@app.get("/modules/content", response_class=HTMLResponse)
async def content_page(request: Request):
    """Content Intelligence Hub module page"""
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee role required."
            )
        
        return templates.TemplateResponse(
            "modules/content.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing content page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )


@app.get("/modules/media-studio", response_class=HTMLResponse)
async def media_studio_page(request: Request):
    """
    Creative Media Studio module page
    """
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Only admin and employee can access
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee role required."
            )
        
        return templates.TemplateResponse(
            "modules/media-studio.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing media studio page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )


@app.get("/modules/social-media", response_class=HTMLResponse)
async def social_media_page(request: Request):
    """
    Social Media Command Center module page
    """
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Only admin and employee can access
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee role required."
            )
        
        return templates.TemplateResponse(
            "modules/social-media.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing social media page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )


# ADD THIS ROUTE TO app/main.py
# Place it in the # ========== MODULE PAGES ========== section
# Right after your social_media_page route

@app.get("/modules/seo", response_class=HTMLResponse)
async def seo_page(request: Request):
    """
    Smart SEO Toolkit module page
    """
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Only admin and employee can access
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee role required."
            )
        
        return templates.TemplateResponse(
            "modules/seo.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing SEO module page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )


@app.get("/modules/ads", response_class=HTMLResponse)
async def ad_strategy_page(request: Request):
    """Ad Strategy Engine module page"""
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee role required."
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials."
        )
    
    return templates.TemplateResponse(
        "modules/ad-strategy.html",
        {
            "request": request,
            "show_sidebar": True,
        }
    )


@app.get("/modules/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """
    Unified Analytics Dashboard module page
    No backend authentication check - frontend will handle it via localStorage token
    """
    return templates.TemplateResponse(
        "modules/analytics.html",
        {
            "request": request,
            "show_sidebar": True
        }
    )


@app.get("/admin/chatbot", response_class=HTMLResponse)
async def chatbot_admin_page(request: Request):
    """
    Chatbot management admin page
    Only accessible by admin users
    """
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Only admin can access
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required."
            )
        
        return templates.TemplateResponse(
            "admin/chatbot-admin.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing chatbot admin page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )

# Add this route in the # ========== ADMIN PAGES ========== section of app/main.py
# Place it near other admin routes like /admin/packages, /admin/tasks, etc.

@app.get("/admin/users", response_class=HTMLResponse)
async def user_management_page(request: Request):
    """
    Chatbot management admin page
    Only accessible by admin users
    """
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Only admin can access
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required."
            )
        
        return templates.TemplateResponse(
            "admin/user-management.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        # Invalid token - redirect to login
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing user management page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )


# ========== TASK MANAGEMENT PAGES ==========

@app.get("/admin/tasks", response_class=HTMLResponse)
async def admin_tasks_page(request: Request):
    """
    Chatbot management admin page
    Only accessible by admin users
    """
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Only admin can access
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required."
            )
        
        return templates.TemplateResponse(
            "admin/tasks.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing admin tasks page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )


@app.get("/tasks", response_class=HTMLResponse)
async def employee_tasks_page(request: Request):
    """
    Chatbot management admin page
    Only accessible by admin users
    """
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Only admin can access
        if role and role not in ["admin", "employee"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required."
            )
        
        return templates.TemplateResponse(
            "tasks/index.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing tasks page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )


@app.get("/employee/tasks", response_class=HTMLResponse)
async def employee_tasks_alt_route(request: Request):
    """
    Alternative route for employee tasks (redirects to /tasks)
    """
    return RedirectResponse(url="/tasks")


@app.get("/admin/finance", response_class=HTMLResponse)
async def financial_pl_page(request: Request):
    """
    Chatbot management admin page
    Only accessible by admin users
    """
    access_token: Optional[str] = request.cookies.get("access_token")
    role = None
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    try:
        if access_token:
            payload = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            role = payload.get("role")
        
        # Only admin can access
        if role and role not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required."
            )
        
        return templates.TemplateResponse(
            "admin/finance.html",
            {
                "request": request,
                "show_sidebar": True
            }
        )
        
    except JWTError:
        # Invalid token - redirect to login
        return RedirectResponse(url="/auth/login")
    except Exception as e:
        print(f"Error accessing user management page: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load page"
        )


# ========== HEALTH CHECK ==========

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "features": {
            "authentication": "enabled",
            "database": "mysql",
            "onboarding": "enabled"  # NEW
        }
    }


# ========== STARTUP & SHUTDOWN EVENTS ==========

@app.on_event("startup")
async def startup_event():
    """Actions to perform on application startup"""
    print(f"🚀 {settings.APP_NAME} is starting...")
    print(f"📍 Environment: {settings.ENVIRONMENT}")
    print(f"🔧 Debug mode: {settings.DEBUG}")
    print(f"📊 API Documentation: http://{settings.HOST}:{settings.PORT}/api/{settings.API_VERSION}/docs")
    print(f"🔐 Login page: http://{settings.HOST}:{settings.PORT}/auth/login")
    print(f"📝 Register page: http://{settings.HOST}:{settings.PORT}/auth/register")
    print(f"📦 Package selection: http://{settings.HOST}:{settings.PORT}/onboarding/select-package")  # NEW
    print(f"✅ Verification: http://{settings.HOST}:{settings.PORT}/onboarding/verification")  # NEW
    print(f"👨‍💼 Admin verifications: http://{settings.HOST}:{settings.PORT}/admin/onboarding-verifications")  # NEW


@app.on_event("shutdown")
async def shutdown_event():
    """Actions to perform on application shutdown"""
    print(f"🛑 {settings.APP_NAME} is shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )