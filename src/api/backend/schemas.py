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
    
    class Config:
        # Allow response to use camelCase for frontend
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "project_id": "987fcdeb-51a2-43f1-b9e5-ac4c5d6e7890",
                "status": "running",
                "progress": 45,
                "current_stage": "security_scan",
                "error_message": None,
                "started_at": "2024-01-09T10:30:00",
                "completed_at": None
            }
        }


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


class SecurityIssue(BaseModel):
    """Security issue with enhanced details"""
    type: str
    severity: str
    file: str
    line: Optional[int] = None
    description: str


class AIAnalysis(BaseModel):
    """AI analysis results"""
    aiGeneratedPercentage: float
    aiVerdict: Optional[str] = None
    strengths: List[str] = []
    improvements: List[str] = []
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
    architecture_score: Optional[float] = None
    llm_score: Optional[float] = None  # Maps to originality


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


class ProjectDetailResponse(BaseModel):
    """Enhanced project detail response matching frontend"""
    # Identity
    id: UUID
    teamName: Optional[str] = None
    repoUrl: str
    submittedAt: datetime
    status: str
    
    # Tech Stack
    techStack: List[str] = []  # Technology names as strings
    languages: List[LanguageBreakdown] = []
    architecturePattern: str = "Monolithic"
    frameworks: List[str] = []
    
    # Flat Scores (not nested)
    totalScore: float = 0
    qualityScore: float = 0
    securityScore: float = 0
    originalityScore: float = 0
    architectureScore: float = 0
    documentationScore: float = 0
    
    # Commit Forensics
    totalCommits: int = 0
    contributors: List[ContributorDetail] = []
    commitPatterns: List[CommitPattern] = []
    burstCommitWarning: bool = False
    lastMinuteCommits: int = 0
    
    # Security
    securityIssues: List[SecurityIssue] = []
    secretsDetected: int = 0
    
    # AI Analysis
    aiGeneratedPercentage: float = 0
    aiVerdict: Optional[str] = None
    strengths: List[str] = []
    improvements: List[str] = []
    
    # Project Stats
    totalFiles: int = 0
    totalLinesOfCode: int = 0
    testCoverage: float = 0


class ProjectListItemResponse(BaseModel):
    """Project list item response matching frontend"""
    id: UUID
    teamName: Optional[str] = None
    repoUrl: str
    status: str
    totalScore: float = 0
    qualityScore: float = 0
    securityScore: float = 0
    originalityScore: float = 0
    architectureScore: float = 0
    documentationScore: float = 0
    techStack: List[str] = []  # Top technologies as strings
    securityIssues: int = 0  # Count
    submittedAt: datetime


class StatsResponse(BaseModel):
    """Dashboard statistics response"""
    totalProjects: int
    completedProjects: int
    pendingProjects: int
    averageScore: float  # Note: 'average' not 'avg'
    totalSecurityIssues: int


class BatchUploadItemRequest(BaseModel):
    """Single item in batch upload CSV"""
    teamName: str
    repoUrl: str
    description: Optional[str] = None


# ================ Auth & Collaboration ================


class AuthUserResponse(BaseModel):
    """Authenticated user context"""
    user_id: UUID
    email: Optional[str] = None
    role: str
    full_name: Optional[str] = None


class CreateTeamRequest(BaseModel):
    """Create a new team"""
    name: str
    mentor_id: Optional[UUID] = None
    description: Optional[str] = None
    is_active: bool = True


class TeamMemberRequest(BaseModel):
    """Add a member to a team"""
    user_id: UUID
    role: str = Field("member", pattern="^(leader|member)$")


class ProjectCommentRequest(BaseModel):
    """Create a comment for a project"""
    project_id: UUID
    comment: str
    is_private: bool = False


class ProjectCommentResponse(BaseModel):
    """Returned project comment"""
    id: UUID
    project_id: UUID
    user_id: UUID
    comment: str
    is_private: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# ==================== NEW SCHEMAS FOR BATCH SYSTEM ====================

# ---------- Authentication Schemas ----------

class LoginRequest(BaseModel):
    """Login request with Google ID token"""
    id_token: str = Field(..., description="Google OAuth ID token")


class LoginResponse(BaseModel):
    """Login response"""
    access_token: str
    refresh_token: str
    user: "UserProfileResponse"
    expires_in: int


class UserProfileResponse(BaseModel):
    """User profile response"""
    id: UUID
    email: str
    role: str  # admin, mentor
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime


class UserUpdateRequest(BaseModel):
    """Update user profile"""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


# ---------- Batch Management Schemas ----------

class BatchCreateRequest(BaseModel):
    """Create new batch"""
    name: str = Field(..., description="Batch name (e.g., '4th Sem 2024')")
    semester: str = Field(..., description="Semester (e.g., '4th Sem')")
    year: int = Field(..., ge=2020, le=2100, description="Year")
    start_date: datetime
    end_date: datetime
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class BatchUpdateRequest(BaseModel):
    """Update batch"""
    name: Optional[str] = None
    semester: Optional[str] = None
    year: Optional[int] = Field(None, ge=2020, le=2100)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = Field(None, pattern="^(active|archived|upcoming)$")


class BatchResponse(BaseModel):
    """Batch response"""
    id: UUID
    name: str
    semester: str
    year: int
    start_date: datetime
    end_date: datetime
    status: str
    team_count: int
    student_count: int
    created_at: datetime
    updated_at: datetime


class BatchStatsResponse(BaseModel):
    """Batch with statistics"""
    id: UUID
    name: str
    semester: str
    year: int
    start_date: datetime
    end_date: datetime
    status: str
    team_count: int
    student_count: int
    avg_score: Optional[float] = None
    completed_projects: int = 0
    pending_projects: int = 0
    at_risk_teams: int = 0
    created_at: datetime
    updated_at: datetime


class BatchListResponse(BaseModel):
    """List of batches"""
    batches: List[BatchResponse]
    total: int


# ---------- Team Management Schemas ----------

class TeamCreateRequest(BaseModel):
    """Create new team"""
    batch_id: UUID
    team_name: str = Field(..., min_length=1, max_length=255)
    project_id: Optional[UUID] = None
    mentor_id: Optional[UUID] = None


class TeamUpdateRequest(BaseModel):
    """Update team"""
    team_name: Optional[str] = Field(None, min_length=1, max_length=255)
    project_id: Optional[UUID] = None
    mentor_id: Optional[UUID] = None
    health_status: Optional[str] = Field(None, pattern="^(on_track|at_risk|critical)$")
    risk_flags: Optional[List[str]] = None


class TeamResponse(BaseModel):
    """Team response"""
    id: UUID
    batch_id: UUID
    team_name: str
    project_id: Optional[UUID] = None
    mentor_id: Optional[UUID] = None
    student_count: int
    health_status: str
    risk_flags: List[str]
    last_activity: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TeamWithDetailsResponse(BaseModel):
    """Team with students and project"""
    id: UUID
    batch_id: UUID
    team_name: str
    project_id: Optional[UUID] = None
    mentor_id: Optional[UUID] = None
    student_count: int
    health_status: str
    risk_flags: List[str]
    last_activity: Optional[datetime] = None
    students: List["StudentResponse"] = []
    project: Optional["ProjectListItemResponse"] = None
    mentor: Optional[UserProfileResponse] = None
    created_at: datetime
    updated_at: datetime


class TeamListResponse(BaseModel):
    """List of teams"""
    teams: List[TeamResponse]
    total: int


# ---------- Student Schemas ----------

class StudentCreateRequest(BaseModel):
    """Create new student"""
    team_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    github_username: Optional[str] = None


class StudentUpdateRequest(BaseModel):
    """Update student"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    github_username: Optional[str] = None


class StudentResponse(BaseModel):
    """Student response"""
    id: UUID
    team_id: UUID
    name: str
    email: Optional[str] = None
    github_username: Optional[str] = None
    contribution_score: float
    commit_count: int
    lines_added: int
    lines_deleted: int
    last_commit_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class StudentListResponse(BaseModel):
    """List of students"""
    students: List[StudentResponse]
    total: int


# ---------- Mentor Assignment Schemas ----------

class MentorAssignmentCreateRequest(BaseModel):
    """Assign mentor to team"""
    mentor_id: UUID
    team_id: UUID
    batch_id: UUID


class MentorAssignmentResponse(BaseModel):
    """Mentor assignment response"""
    id: UUID
    mentor_id: UUID
    team_id: UUID
    batch_id: UUID
    assigned_at: datetime
    assigned_by: Optional[UUID] = None


class MentorAssignmentListResponse(BaseModel):
    """List of mentor assignments"""
    assignments: List[MentorAssignmentResponse]
    total: int


# ---------- Admin Dashboard Schemas ----------

class AdminDashboardStatsResponse(BaseModel):
    """Admin dashboard statistics"""
    total_teams: int
    total_students: int
    total_projects: int
    avg_score: Optional[float] = None
    completed_projects: int
    pending_projects: int
    at_risk_teams: int
    critical_teams: int


class AdminTeamListItem(BaseModel):
    """Team item for admin dashboard"""
    id: UUID
    team_name: str
    project_id: Optional[UUID] = None
    student_count: int
    health_status: str
    risk_flags: List[str]
    total_score: Optional[float] = None
    mentor_name: Optional[str] = None


class AdminBatchOverviewResponse(BaseModel):
    """Batch overview for admin"""
    batch: BatchStatsResponse
    teams: List[AdminTeamListItem]
    recent_activity: List["ActivityLogResponse"] = []


# ---------- Mentor Dashboard Schemas ----------

class MentorDashboardStatsResponse(BaseModel):
    """Mentor dashboard statistics"""
    assigned_teams: int
    total_students: int
    avg_team_score: Optional[float] = None
    at_risk_teams: int
    pending_reviews: int


class MentorTeamListItem(BaseModel):
    """Team item for mentor dashboard"""
    id: UUID
    team_name: str
    batch_name: str
    student_count: int
    health_status: str
    total_score: Optional[float] = None
    last_activity: Optional[datetime] = None


class MentorDashboardResponse(BaseModel):
    """Mentor dashboard data"""
    stats: MentorDashboardStatsResponse
    teams: List[MentorTeamListItem]


# ---------- Analytics Schemas ----------

class HealthStatusDistribution(BaseModel):
    """Health status distribution"""
    on_track: int
    at_risk: int
    critical: int


class RiskFlagAnalysis(BaseModel):
    """Risk flag analysis"""
    flag: str
    count: int
    percentage: float


class BatchAnalyticsResponse(BaseModel):
    """Batch analytics"""
    batch_id: UUID
    batch_name: str
    health_distribution: HealthStatusDistribution
    risk_flags: List[RiskFlagAnalysis]
    avg_score: Optional[float] = None
    score_distribution: Dict[str, int]  # score ranges
    top_teams: List[AdminTeamListItem]
    bottom_teams: List[AdminTeamListItem]


class TeamAnalyticsResponse(BaseModel):
    """Team analytics"""
    team_id: UUID
    team_name: str
    health_status: str
    risk_flags: List[str]
    student_contributions: List["StudentContribution"]
    commit_timeline: List["CommitDataPoint"]
    score_breakdown: ScoreBreakdown


class StudentContribution(BaseModel):
    """Student contribution data"""
    student_id: UUID
    name: str
    commit_count: int
    lines_added: int
    lines_deleted: int
    contribution_percentage: float


class CommitDataPoint(BaseModel):
    """Commit data point for timeline"""
    date: str
    commits: int
    contributors: int


class ActivityLogResponse(BaseModel):
    """Activity log entry"""
    id: UUID
    batch_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    action: str
    description: str
    timestamp: datetime


# ---------- Report Generation Schemas ----------

class GenerateReportRequest(BaseModel):
    """Generate report request"""
    batch_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    format: str = Field("pdf", pattern="^(pdf|csv|json)$")
    include_details: bool = True


class ReportResponse(BaseModel):
    """Report response"""
    report_id: UUID
    format: str
    download_url: str
    generated_at: datetime
    expires_at: Optional[datetime] = None
