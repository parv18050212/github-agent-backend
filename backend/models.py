"""
Pydantic Models for Database Tables
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class ProjectBase(BaseModel):
    """Base project model"""
    repo_url: str
    team_name: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Model for creating a new project"""
    pass


class Project(ProjectBase):
    """Full project model with all fields"""
    id: UUID
    created_at: datetime
    analyzed_at: Optional[datetime] = None
    status: str = "pending"  # pending, analyzing, completed, failed
    
    # Scores (0-100)
    total_score: Optional[float] = None
    originality_score: Optional[float] = None
    quality_score: Optional[float] = None
    security_score: Optional[float] = None
    effort_score: Optional[float] = None
    implementation_score: Optional[float] = None
    engineering_score: Optional[float] = None
    organization_score: Optional[float] = None
    documentation_score: Optional[float] = None
    
    # Metadata
    total_commits: Optional[int] = None
    verdict: Optional[str] = None  # Production Ready, Prototype, Broken
    ai_pros: Optional[str] = None
    ai_cons: Optional[str] = None
    report_json: Optional[Dict[str, Any]] = None
    viz_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class AnalysisJobBase(BaseModel):
    """Base analysis job model"""
    project_id: UUID
    status: str = "queued"  # queued, running, completed, failed
    progress: int = 0
    current_stage: Optional[str] = None


class AnalysisJobCreate(AnalysisJobBase):
    """Model for creating a new analysis job"""
    pass


class AnalysisJob(AnalysisJobBase):
    """Full analysis job model"""
    id: UUID
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TechStack(BaseModel):
    """Tech stack model"""
    id: UUID
    project_id: UUID
    technology: str
    category: Optional[str] = None  # language, framework, database, tool
    
    class Config:
        from_attributes = True


class Issue(BaseModel):
    """Issue/warning model"""
    id: UUID
    project_id: UUID
    type: str  # security, quality, plagiarism
    severity: str  # high, medium, low
    file_path: Optional[str] = None
    description: str
    ai_probability: Optional[float] = None
    plagiarism_score: Optional[float] = None
    
    class Config:
        from_attributes = True


class TeamMember(BaseModel):
    """Team member model"""
    id: UUID
    project_id: UUID
    name: str
    commits: int
    contribution_pct: Optional[float] = None
    
    class Config:
        from_attributes = True


class ProjectWithDetails(Project):
    """Project with related data"""
    tech_stack: List[TechStack] = []
    issues: List[Issue] = []
    team_members: List[TeamMember] = []
    job: Optional[AnalysisJob] = None
