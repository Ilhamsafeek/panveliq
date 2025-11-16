"""
Main API Router
Combines all endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    project_planner,
    onboarding,
    clients,
    admin,
    employees,
#     dashboard,
    tasks,
#     messages,
    communication,
    content,
    social_media,
    seo,
    media_studio,
    ads,
    analytics,
    chatbot,
#     finance,
#     settings as settings_endpoint
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(project_planner.router, prefix="/project-planner", tags=["Project Planner"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
api_router.include_router(clients.router, prefix="/clients", tags=["Clients"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(employees.router, prefix="/employees", tags=["Employees"])

# api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
# api_router.include_router(messages.router, prefix="/messages", tags=["Messages"])
api_router.include_router(communication.router, prefix="/communication", tags=["Communication"])
api_router.include_router(content.router, prefix="/content", tags=["Content"])
api_router.include_router(social_media.router, prefix="/social-media", tags=["Social Media"])
api_router.include_router(seo.router, prefix="/seo", tags=["SEO"])
api_router.include_router(media_studio.router, prefix="/media-studio", tags=["Media Studio"])
api_router.include_router(ads.router, prefix="/ad-strategy", tags=["Ads"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(chatbot.router, prefix="/chatbot", tags=["Chatbot"])
# api_router.include_router(finance.router, prefix="/finance", tags=["Finance"])
# api_router.include_router(settings_endpoint.router, prefix="/settings", tags=["Settings"])


# Test endpoint
@api_router.get("/test")
async def test_endpoint():
    """
    Test endpoint to verify API is working
    """
    return {
        "status": "success",
        "message": "API is working!",
        "version": "v1"
    }