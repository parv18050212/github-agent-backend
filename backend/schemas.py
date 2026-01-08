"""
API Request and Response Schemas
"""
from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ==================== Request Schemas ====================

class AnalyzeRepoRequest(BaseModel):
    """Request to analyze a repository"""
    repo_url: str = Field(..., description="GitHub repository URL")
    team_name: Optional[str] = Field(None, description="Team or project name")
    
    @validator('repo_url')
    def validate_repo_url(cls, v):
        """Validate that URL is a proper GitHub URL"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('repo_url must start with http:// or https://')
        if 'github.com' not in v.lower():
            raise ValueError('Only GitHub repositories are supported')
        return v


class BatchUploadRequest(BaseModel):
    """Request to analyze multiple repositories"""
    repos: List[AnalyzeRepoRequest] = Field(..., min_items=1, max_items=50)


class ProjectFilterParams(BaseModel):
    """Query parameters for filtering projects"""
    status: Optional[str] = None
    min_score: Optional[float] = Field(None, ge=0, le=100)
    max_score: Optional[float] = Field(None, ge=0, le=100)
    team_name: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class LeaderboardParams(BaseModel):
    """Query parameters for leaderboard"""
    sort_by: str = Field("total_score", description="Field to sort by")
    order: str = Field("desc", description="asc or desc")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    status: Optional[str] = Field("completed", description="Filter by status")


# ==================== Response Schemas ====================

class AnalyzeRepoResponse(BaseModel):
    """Response from analyze-repo endpoint"""
    job_id: UUID
    project_id: UUID
    status: str
    message: str = "Analysis queued successfully"


class BatchUploadResponse(BaseModel):
    """Response from batch-upload endpoint"""
    jobs: List[AnalyzeRepoResponse]
    total: int
    message: str


class AnalysisStatusResponse(BaseModel):
    """Response for analysis status"""
    job_id: UUID
    project_id: UUID
    status: str  # queued, running, completed, failed
    progress: int  # 0-100
    current_stage: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class LanguageBreakdown(BaseModel):
    """Language usage breakdown"""
    name: str
    percentage: float


class ContributorDetail(BaseModel):
    """Detailed contributor information"""
    name: str
    commits: int
    additions: int = 0
    deletions: int = 0
    percentage: float


class CommitPattern(BaseModel):
    """Commit pattern over time"""
    date: str
    commits: int
    additions: int = 0
    deletions: int = 0


class ScoreBreakdown(BaseModel):
    """Score breakdown"""
    total_score: Optional[float] = None
    originality_score: Optional[float] = None
    quality_score: Optional[float] = None
    security_score: Optional[float] = None
    effort_score: Optional[float] = None
    implementation_score: Optional[float] = None
    engineering_score: Optional[float] = None
    organization_score: Optional[float] = None
    documentation_score: Optional[float] = None
    architecture_score: Optional[float] = None  # Alias for engineering


class TechStackItem(BaseModel):
    """Tech stack item"""
    technology: str
    category: Optional[str] = None


class IssueItem(BaseModel):
    """Issue item"""
    type: str
    severity: str
    file_path: Optional[str] = None
    description: str
    ai_probability: Optional[float] = None
    plagiarism_score: Optional[float] = None


class TeamMemberItem(BaseModel):
    """Team member item"""
    name: str
    commits: int
    contribution_pct: Optional[float] = None


class AnalysisResultResponse(BaseModel):
    """Full analysis result"""
    project_id: UUID
    repo_url: str
    team_name: Optional[str] = None
    status: str
    analyzed_at: Optional[datetime] = None
    
    # Scores
    scores: ScoreBreakdown
    
    # Details
    total_commits: Optional[int] = None
    verdict: Optional[str] = None
    ai_pros: Optional[str] = None
    ai_cons: Optional[str] = None
    
    # Related data
    tech_stack: List[TechStackItem] = []
    issues: List[IssueItem] = []
    team_members: List[TeamMemberItem] = []
    
    # Visualization
    viz_url: Optional[str] = None
    
    # Full report
    report_json: Optional[Dict[str, Any]] = None


class ProjectListItem(BaseModel):
    """Project list item (summary)"""
    id: UUID
    repo_url: str
    team_name: Optional[str] = None
    status: str
    total_score: Optional[float] = None
    verdict: Optional[str] = None
    created_at: datetime
    analyzed_at: Optional[datetime] = None


class ProjectListResponse(BaseModel):
    """Response for project list"""
    projects: List[ProjectListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class LeaderboardItem(BaseModel):
    """Leaderboard item"""
    rank: int
    id: UUID
    repo_url: str
    team_name: Optional[str] = None
    total_score: float
    originality_score: Optional[float] = None
    quality_score: Optional[float] = None
    security_score: Optional[float] = None
    implementation_score: Optional[float] = None
    verdict: Optional[str] = None
    analyzed_at: Optional[datetime] = None


class LeaderboardResponse(BaseModel):
    """Response for leaderboard"""
    leaderboard: List[LeaderboardItem]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
