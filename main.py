"""
Main FastAPI Application
Repository Analysis Backend API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routers
from src.api.backend.routers import (
    analysis, 
    projects, 
    leaderboard, 
    frontend_api, 
    auth,
    auth_new,
    batches
)

# Create FastAPI app
app = FastAPI(
    title="Repository Analysis API",
    description="Backend API for analyzing GitHub repositories with AI-powered scoring",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router)
# app.include_router(projects.router)  # Disabled - using frontend_api instead
# app.include_router(leaderboard.router)  # Disabled - using frontend_api instead
app.include_router(frontend_api.router)  # Frontend-compatible endpoints
app.include_router(auth.router)  # Auth/roles/teams/comments (legacy)

# New batch management system routers
app.include_router(auth_new.router)  # New authentication with Google OAuth
app.include_router(batches.router)  # Batch management (CRUD)


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
            
            # Projects (Frontend-compatible)
            "project_detail": "GET /api/projects/{id}",
            "project_list": "GET /api/projects?status=&tech=&sort=&search=",
            "delete_project": "DELETE /api/projects/{id}",
            
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
        from backend.database import get_supabase_client
        supabase = get_supabase_client()
        
        # Simple query to test connection
        result = supabase.table("projects").select("id").limit(1).execute()
        
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
    
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        port=port,
        reload=True,
        log_level="info"
    )
