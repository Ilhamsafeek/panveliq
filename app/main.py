"""
REPLACE CONTENT IN: app/main.py (existing file)

PanvelIQ - AI-powered Digital Marketing Intelligence Platform
Main FastAPI Application Entry Point
"""

from fastapi import FastAPI, Request, HTTPException, status, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from typing import Optional


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


@app.get("/modules/project-planner", response_class=HTMLResponse)
async def project_planner_page(request: Request, access_token: Optional[str] = Cookie(None)):
    """
    AI Project Planner page
    
    **Access**: Admin and Employee only
    """
    # Check if user is authenticated
    if not access_token:
        # Redirect to login if no token
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    
    try:
        # Verify token and get user
        from jose import jwt, JWTError
        from app.core.config import settings
        
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        role = payload.get("role")
        
        # Check if user is admin or employee
        if role not in ['admin', 'employee']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Admin or Employee role required."
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
        # Invalid token, redirect to login
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
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
            "database": "mysql"
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