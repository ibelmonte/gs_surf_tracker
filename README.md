# Surf Tracker - Full-Stack Surf Performance Analysis

AI-powered surf video analysis platform that detects surfers, tracks their movements, and identifies maneuvers automatically.

## Overview

Surf Tracker is a complete web application that allows surfers to upload videos and receive detailed performance analysis using computer vision and deep learning.

### Features

- User registration and authentication with email confirmation
- Video upload and management
- Automated surf maneuver detection (turns, snaps, cutbacks, etc.)
- Pose estimation for detailed body mechanics analysis
- Multi-surfer tracking with stable IDs
- Per-surfer results with annotated videos and frame captures
- RESTful API with Swagger documentation
- Modern React-based web interface

## Architecture

The application consists of five main services:

1. **Database (PostgreSQL)**: Stores users, sessions, and results
2. **Redis**: Message broker for Celery background tasks
3. **API (FastAPI)**: RESTful API backend
4. **Celery Worker**: Background video processing
5. **Website (Next.js)**: User interface
6. **Tracker**: Computer vision pipeline (YOLOv8 + BoTSORT + MediaPipe)

## Project Structure

```
surf_stracker/
├── docker-compose.yml          # Orchestrates all services
├── .env.example                # Environment variables template
├── api/                        # FastAPI backend
│   ├── main.py                 # API entry point
│   ├── config.py               # Configuration
│   ├── database.py             # Database setup
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── routers/                # API endpoints
│   ├── services/               # Business logic
│   ├── tasks/                  # Celery tasks
│   └── utils/                  # Utilities
├── tracker/                    # Video processing service
│   ├── tracker.py              # Main tracker script
│   ├── botsort.yaml            # Tracker config
│   └── Dockerfile
├── website/                    # Next.js frontend
│   ├── src/
│   │   ├── app/                # Next.js pages
│   │   ├── components/         # React components
│   │   ├── lib/                # Utilities
│   │   └── hooks/              # Custom hooks
│   └── package.json
├── data/                       # Persistent data (not in git)
│   ├── queue/                  # Uploaded videos
│   └── output/                 # Processed results
└── context/
    └── requirements.md         # Full specification
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Git

### 1. Clone the repository

```bash
git clone <repository-url>
cd surf_stracker
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required configuration:
- `DB_PASSWORD`: PostgreSQL password
- `JWT_SECRET_KEY`: Secret for JWT tokens (generate with `openssl rand -hex 32`)
- `SMTP_*`: Email server configuration for user registration

### 3. Start all services

```bash
docker compose up --build
```

This will start:
- PostgreSQL (port 5432)
- Redis (port 6379)
- API (port 8000)
- Website (port 3000)
- Celery worker (background)

### 4. Access the application

- **Website**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health

## Development

### Working on the API

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload
```

### Working on the Website

```bash
cd website
npm install
npm run dev
```

### Running the Tracker Standalone

```bash
cd tracker
docker build -t tracker .
docker run --rm \
  -v $(pwd)/data:/app/data \
  -e VIDEO_SOURCE=/app/data/input.mp4 \
  tracker
```

## Development Phases

This project is being built in phases:

- [x] **Phase 1**: Project restructuring (CURRENT)
- [ ] **Phase 2**: API backend implementation
- [ ] **Phase 3**: Tracker integration with API
- [ ] **Phase 4**: Frontend implementation
- [ ] **Phase 5**: Polish and testing

See `context/requirements.md` for detailed specifications.

## Technology Stack

### Backend
- FastAPI (async Python web framework)
- PostgreSQL (database)
- SQLAlchemy 2.0 (ORM)
- Celery + Redis (background tasks)
- JWT authentication

### Frontend
- Next.js 14 (React framework)
- shadcn/ui (UI components)
- Tailwind CSS (styling)
- React Hook Form + Zod (forms)

### Tracker
- YOLOv8n (person detection)
- BoTSORT (multi-object tracking)
- MediaPipe Pose (pose estimation)
- OpenCV (video processing)

## API Endpoints (Planned)

- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login
- `GET /api/profile/me` - Get user profile
- `POST /api/sessions/upload` - Upload video
- `GET /api/sessions/` - List user sessions
- `GET /api/sessions/{id}` - Get session results

Full API documentation will be available at `/docs` when implemented.

## Contributing

This project is in active development. See the current phase status and TODOs in the codebase.

## License

[Add license information]

## Contact

[Add contact information]
