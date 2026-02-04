# HackEval Backend

AI-powered GitHub repository analysis system for hackathon evaluation.

## 🚀 Quick Start

```bash
# Development
python main.py

# With Celery worker
python -m celery -A celery_app worker --loglevel=info

# Run tests
pytest tests/
```

## 📁 Project Structure

```
proj-github agent/
├── main.py                 # FastAPI application entry point
├── celery_app.py          # Celery configuration
├── celery_worker.py       # Background analysis workers
├── Dockerfile             # Docker container definition
│
├── src/                   # Source code
│   ├── api/              # API layer
│   │   └── backend/      # Backend API implementation
│   │       ├── routers/  # FastAPI route handlers
│   │       ├── crud.py   # Database operations
│   │       ├── schemas.py # Pydantic models
│   │       └── utils/    # Utilities (cache, health)
│   │
│   ├── core/             # Core business logic
│   │   ├── agent.py      # Main analysis orchestrator
│   │   └── analyzer_service.py # Analysis service
│   │
│   ├── detectors/        # Analysis detectors
│   │   ├── quality_metrics.py
│   │   ├── security_scanner.py
│   │   ├── ai_detector.py
│   │   └── plagiarism_detector.py
│   │
│   └── orchestrator/     # Analysis pipeline
│       └── runner.py
│
├── tests/                # Test suite
│   ├── integration/      # Integration tests
│   └── unit/            # Unit tests (if any)
│
├── scripts/             # Utility scripts
│   ├── admin/          # Admin maintenance scripts
│   ├── debug/          # Debugging scripts & outputs
│   ├── dev/            # Development scripts (Docker, start scripts)
│   └── archive/        # Archived migration scripts
│
├── migrations/          # Database migrations
│   └── sql/            # SQL migration files
│
├── tools/              # Development tools
│   ├── get_token_helper.py  # OAuth token helper
│   └── certificates/        # SSL certificates
│
├── docs/               # Documentation
│   ├── README.md       # This file
│   ├── CELERY_BEAT_README.md
│   ├── DOCKER_README.md
│   └── archive/        # Archived docs
│
├── logs/               # Application logs
├── reports/            # Generated reports
└── repo_cache/         # Cached analyzed repositories

```

## 🔧 Configuration

Required environment variables in `.env`:

```env
# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_SERVICE_KEY=your_service_key

# AI
GEMINI_API_KEY=your_gemini_key

# GitHub
GH_API_KEY=your_github_token

# Redis/Celery
REDIS_URL=redis://localhost:6379/0

# Server
PORT=8000
CORS_ORIGINS=http://localhost:8080
```

## 📚 Key Components

### API Routers
- `analysis.py` - Repository analysis endpoints
- `frontend_api.py` - Frontend-compatible project/leaderboard APIs
- `auth_new.py` - Google OAuth authentication
- `batches.py` - Batch management
- `teams.py` - Team management
- `analytics.py` - Team analytics
- `dashboards.py` - Admin/mentor dashboards
- `analysis_status.py` - Real-time job status (WebSocket)
- `analysis_history.py` - Historical snapshots

### Analysis Pipeline
1. **Clone** - Repository cloning
2. **Detect** - Tech stack detection
3. **Analyze** - Code quality, security, architecture
4. **Score** - Multi-dimensional scoring
5. **Report** - Generate comprehensive report

### Background Jobs (Celery)
- Repository analysis (async)
- Batch processing
- Automatic weekly re-analysis
- Health status updates

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/integration/test_phase1.py

# With coverage
pytest --cov=src tests/
```

## 🐳 Docker

```bash
# Build
docker build -t hackeval-backend .

# Run
docker-compose up
```

See `docs/DOCKER_README.md` for details.

## 📊 Database Schema

Uses PostgreSQL via Supabase:
- `projects` - Analyzed projects
- `teams` - Team information
- `batches` - Hackathon batches
- `analysis_jobs` - Analysis job tracking
- `analysis_snapshots` - Historical snapshots
- `users` - User authentication
- `mentor_assignments` - Mentor-team mappings

## 🔒 Authentication

Role-based access control:
- **Admin** - Full system access
- **Mentor** - Team management, grading
- **Participant** - View own team data

## 📖 Documentation

- **API Docs** - http://localhost:8000/docs (auto-generated)
- **Architecture** - See root `CODEBASE_DOCUMENTATION.md`
- **Integration Guide** - See root `INTEGRATION_GUIDE.md`
- **Performance** - See root `PERFORMANCE_GUIDE.md`

## 🛠️ Development Scripts

```bash
# Admin scripts
scripts/admin/set_admin_role.py          # Set user roles
scripts/admin/cleanup_projects.py        # Clean duplicate projects
scripts/admin/backfill_languages.py      # Update tech stack data

# Debug scripts
scripts/debug/debug_analytics.py         # Debug analytics issues
scripts/debug/diagnose_batch_failure.py  # Diagnose batch failures

# Dev scripts
scripts/dev/docker-start.sh              # Start Docker containers
scripts/dev/start_worker.ps1             # Start Celery worker
```

## 📈 Performance

- **Caching**: Redis (5-min TTL for analytics)
- **Database**: 18 performance indexes
- **Analysis**: Parallel LLM calls (3x faster)
- **WebSocket**: Real-time job status updates

## 🤝 Contributing

1. Follow existing code structure
2. Add tests for new features
3. Update documentation
4. Run `pytest` before committing

## 📄 License

Proprietary - HackEval Team 2026

## 🆘 Support

- Issues: Check `docs/archive/troubleshooting/`
- API Reference: http://localhost:8000/docs
- Logs: `logs/` directory
