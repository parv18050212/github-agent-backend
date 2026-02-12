"""
Main FastAPI Application
Repository Analysis Backend API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from prometheus_fastapi_instrumentator import Instrumentator

# Load environment variables
load_dotenv()

# Import routers
from src.api.backend.routers import (
    analysis, 
    frontend_api, 
    auth,
    auth_new,
    batches,
    teams,
    mentors,
    assignments,
    dashboards,
    analytics,
    reports,
    admin_users,
    mentor_dashboard,
    alerts,
    debug  # Debug/diagnostic endpoints
)

# Create FastAPI app
app = FastAPI(
    title="Repository Analysis API",
    description="Backend API for analyzing GitHub repositories with AI-powered scoring",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    excluded_handlers=["/metrics"],
).instrument(app).expose(app)


# CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
if cors_origins == ["*"]:
    cors_origins = [
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081"
    ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router)
app.include_router(frontend_api.router)  # Frontend-compatible endpoints

# New authentication with Google OAuth (register before legacy auth)
app.include_router(auth_new.router)

# Legacy auth + project comments only
app.include_router(auth.router)

# New batch management system routers
app.include_router(batches.router)  # Batch management (CRUD)
app.include_router(teams.router)  # Team management - all /api/teams endpoints (Phase 2)
app.include_router(mentors.router)  # Mentor management (Phase 3)
app.include_router(assignments.router)  # Mentor-Team assignments (Phase 3)
app.include_router(dashboards.router)  # Admin & Mentor dashboards (Phase 4)
app.include_router(analytics.router)  # Team Analytics (Phase 5)
app.include_router(reports.router)  # Reports & Analytics (Phase 5)
app.include_router(admin_users.router)  # Admin User Management (Admin Portal)
app.include_router(mentor_dashboard.router)  # Mentor Dashboard (Mentor-only endpoints)
app.include_router(alerts.router)  # Alerts & Notifications
app.include_router(debug.router)  # Debug & Diagnostics (Admin-only)

# Real-time Celery sync and historical data tracking
from src.api.backend.routers import analysis_status, analysis_history
app.include_router(analysis_status.router)  # Real-time job status with WebSocket
app.include_router(analysis_history.router)  # Historical snapshots for 7-day tracking


@app.get("/")
async def root():
    """Root endpoint - API info"""
    return {
        "name": "Repository Analysis API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            # Analysis
            "analyze": "POST /api/analyze-repo",
            "status": "GET /api/analysis-status/{job_id}",
            "result": "GET /api/analysis-result/{job_id}",
            "batch_upload": "POST /api/batch-upload",
            
            # Teams (Unified with analysis data)
            "team_list": "GET /api/teams",
            "team_detail": "GET /api/teams/{id}",
            "team_analyze": "POST /api/teams/{id}/analyze",
            
            # Leaderboard (Frontend-compatible)
            "leaderboard": "GET /api/leaderboard?tech=&sort=&search=",
            "leaderboard_chart": "GET /api/leaderboard/chart",
            
            # Stats
            "stats": "GET /api/stats",
            "tech_stacks": "GET /api/tech-stacks"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Supabase connection
        from src.api.backend.database import get_supabase_client
        supabase = get_supabase_client()
        
        # Simple query to test connection
        result = supabase.table("teams").select("id").limit(1).execute()
        
        return {
            "status": "healthy",
            "database": "connected",
            "supabase": "ok"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "error",
                "error": str(e)
            }
        )




@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("\n" + "="*60)
    print("🚀 Repository Analysis API Starting...")
    print("="*60)
    print(f"📊 Docs available at: http://localhost:8000/docs")
    print(f"🔍 Health check: http://localhost:8000/health")
    print("="*60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    print("\n" + "="*60)
    print("👋 Repository Analysis API Shutting Down...")
    print("="*60 + "\n")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 3000))
    
    uvicorn.run(
        "main:app",
        port=port,
        reload=True,
        log_level="info"
    )
