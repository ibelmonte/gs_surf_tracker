
# Surf Tracker – Full-Stack Application Specification

## 1. Overview

This is a full-stack web application that allows surfers to upload videos and receive automated surf performance analysis. The system consists of:

- **Web Application**: User registration, authentication, profile management, and video upload
- **API Backend**: FastAPI-based REST API with background job processing
- **Tracker Service**: Computer vision pipeline for surf movement detection and analysis
- **Database**: PostgreSQL for storing users, sessions, and analysis results

---

## 2. High-Level Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Next.js   │────────▶│   FastAPI   │────────▶│   Tracker   │
│   Website   │         │     API     │         │   Service   │
│  (shadcn)   │◀────────│  + Celery   │◀────────│  (YOLOv8)   │
└─────────────┘         └─────────────┘         └─────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │ PostgreSQL  │
                        │  Database   │
                        └─────────────┘
```

---

## 3. Project Structure

```
surf_stracker/
├── docker-compose.yml              # Orchestrates all services
├── context/
│   └── requirements.md             # This file
├── tracker/                        # Tracker service (isolated)
│   ├── tracker.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── botsort.yaml
├── api/                            # FastAPI backend
│   ├── main.py                     # FastAPI app entry point
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── config.py                   # Configuration (DB, Redis, etc.)
│   ├── database.py                 # SQLAlchemy setup
│   ├── models/                     # SQLAlchemy models
│   │   ├── user.py
│   │   ├── session.py
│   │   └── profile.py
│   ├── schemas/                    # Pydantic schemas
│   │   ├── user.py
│   │   ├── session.py
│   │   └── profile.py
│   ├── routers/                    # API route handlers
│   │   ├── auth.py                 # Registration, login, email confirmation
│   │   ├── profile.py              # Profile management
│   │   ├── sessions.py             # Video upload & session management
│   │   └── admin.py                # Admin endpoints (optional)
│   ├── services/                   # Business logic
│   │   ├── auth_service.py
│   │   ├── email_service.py
│   │   ├── storage_service.py      # File upload/storage logic
│   │   └── tracker_service.py      # Tracker integration
│   ├── tasks/                      # Celery tasks
│   │   ├── celery_app.py           # Celery configuration
│   │   └── video_processing.py     # Background video processing task
│   └── utils/
│       ├── security.py             # Password hashing, JWT tokens
│       └── dependencies.py         # FastAPI dependencies
├── website/                        # Next.js frontend
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── Dockerfile
│   ├── public/                     # Static assets
│   ├── src/
│   │   ├── app/                    # Next.js 14 app directory
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx            # Landing page
│   │   │   ├── register/
│   │   │   │   └── page.tsx
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx        # User dashboard with sessions
│   │   │   ├── profile/
│   │   │   │   └── page.tsx        # Profile management
│   │   │   └── session/
│   │   │       └── [id]/
│   │   │           └── page.tsx    # View session results
│   │   ├── components/             # shadcn components + custom
│   │   │   ├── ui/                 # shadcn primitives
│   │   │   ├── auth/
│   │   │   ├── video-upload.tsx
│   │   │   ├── session-list.tsx
│   │   │   └── profile-form.tsx
│   │   ├── lib/
│   │   │   ├── api-client.ts       # API client (axios/fetch)
│   │   │   └── utils.ts
│   │   └── hooks/                  # Custom React hooks
│   │       ├── useAuth.ts
│   │       └── useSessions.ts
│   └── ...
└── data/                           # Shared data volume
    ├── queue/                      # Uploaded videos waiting processing
    │   └── {user_id}/
    │       └── {file}.mp4
    └── output/                     # Processed results
        └── {user_id}/
            └── {session_id}/
                ├── output.mp4                      # Annotated video
                └── elements/
                    └── {track_id}/
                        ├── pictures/
                        │   └── {frame}.png
                        └── maneuvers.json          # Changed from turns.json
```

---

## 4. Database Schema

### 4.1 Users Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_email_confirmed BOOLEAN DEFAULT FALSE,
    email_confirmation_token VARCHAR(255),
    email_confirmation_sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Profiles Table

```sql
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(255),
    alias VARCHAR(100),
    profile_picture_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.3 Surfing Sessions Table

```sql
CREATE TABLE surfing_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    video_filename VARCHAR(255) NOT NULL,
    video_path VARCHAR(500) NOT NULL,
    status VARCHAR(50) NOT NULL,  -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    output_path VARCHAR(500),
    results_json JSONB,  -- Store tracker results
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    started_processing_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_sessions_user_id ON surfing_sessions(user_id);
CREATE INDEX idx_sessions_status ON surfing_sessions(status);
```

---

## 5. API Endpoints

### 5.1 Authentication (`/api/auth/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Register new user, send confirmation email |
| POST | `/login` | Login with email/password, returns JWT token |
| POST | `/confirm-email` | Confirm email with token |
| POST | `/resend-confirmation` | Resend confirmation email |
| POST | `/forgot-password` | Request password reset |
| POST | `/reset-password` | Reset password with token |
| POST | `/logout` | Logout (optional, client-side token removal) |

### 5.2 Profile (`/api/profile/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/me` | Get current user profile |
| PUT | `/me` | Update profile (name, alias) |
| POST | `/me/picture` | Upload profile picture |
| DELETE | `/me/picture` | Delete profile picture |

### 5.3 Sessions (`/api/sessions/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all user sessions |
| GET | `/{session_id}` | Get session details + results |
| POST | `/upload` | Upload video, create session, trigger processing |
| DELETE | `/{session_id}` | Delete session and associated files |

### 5.4 Admin (`/api/admin/`) - Optional

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sessions` | List all sessions (all users) |
| GET | `/users` | List all users |
| POST | `/sessions/{id}/retry` | Retry failed session |

---

## 6. Video Processing Workflow

### 6.1 Upload Flow

1. **User uploads video** via website (`/api/sessions/upload`)
2. **API receives video**:
   - Validates file (format, size)
   - Generates unique `session_id`
   - Stores video in `/data/queue/{user_id}/{filename}.mp4`
   - Creates `surfing_sessions` record with status=`pending`
   - Returns session details to user
3. **API triggers Celery task** `process_video.delay(session_id)`
4. **User redirected** to dashboard showing pending session

### 6.2 Background Processing (Celery Task)

```python
@celery_app.task
def process_video(session_id: str):
    """
    Background task to process video using tracker.

    Steps:
    1. Update session status to 'processing'
    2. Run tracker via subprocess or Docker API
    3. Monitor tracker progress
    4. On completion:
       - Update session status to 'completed'
       - Store output_path
       - Parse results JSON and store in results_json field
    5. On error:
       - Update status to 'failed'
       - Store error_message
    """
```

**Tracker Invocation**:
```bash
docker run --rm \
  -v /data/queue/{user_id}:/app/data \
  -v /data/output/{user_id}/{session_id}:/app/data/output \
  -e VIDEO_SOURCE=/app/data/{filename}.mp4 \
  tracker:latest
```

### 6.3 Status Updates

The session status field tracks the processing state:

- `pending`: Video uploaded, waiting for processing
- `processing`: Tracker is currently analyzing video
- `completed`: Analysis complete, results available
- `failed`: Processing failed, error_message contains details

The API should provide a polling endpoint or WebSocket for real-time status updates.

---

## 7. Tracker Service (Existing System)

The tracker service remains largely unchanged but is containerized and callable by the API.

### 7.1 Inputs

- **Video file**: `/app/data/{filename}.mp4` (mounted from queue)
- **Environment variables**:
  - `VIDEO_SOURCE`: Path to input video
  - `ROTATION`: Optional rotation override

### 7.2 Outputs (to `/data/output/{user_id}/{session_id}/`)

```
output/
├── output.mp4                          # Annotated video with bounding boxes
└── elements/
    └── {track_id}/                     # Per-surfer data
        ├── pictures/
        │   ├── {frame}.png             # Frame captures at maneuver moments
        │   └── ...
        └── maneuvers.json              # Maneuver events (renamed from turns.json)
```

### 7.3 Maneuver JSON Format

Each tracked surfer gets a `maneuvers.json` file:

```json
{
    "id": 2,
    "total_maneuvers": 5,
    "events": [
        {
            "frame": 136,
            "timestamp": 46.999876260757446,
            "maneuver_type": "bottom_turn",
            "turn_metrics": {
                "angle_degrees": 57.89,
                "direction": "right",
                "angular_speed_deg_s": 45.2
            },
            "pose_features": {
                "body_lean": 28.5,
                "knee_bend": 135.2,
                "arm_extension": 0.65,
                "center_mass_y": 0.52,
                "shoulder_rotation": -15.3,
                "hip_shoulder_alignment": 8.2
            },
            "trajectory_features": {
                "turn_radius": 165.3,
                "speed": 32.5,
                "vertical_displacement": 15.2,
                "path_smoothness": 0.15
            }
        }
    ]
}
```

### 7.4 Tracker Configuration

The tracker uses YOLOv8n + BoTSORT for detection and tracking:

- **Detection**: YOLOv8n for person detection
- **Tracking**: BoTSORT with ReID for stable IDs across occlusions
- **Pose Estimation**: MediaPipe Pose for body pose features
- **Maneuver Classification**: Rule-based classifier using pose + trajectory features

Key parameters:
- Confidence threshold: 0.4
- Trajectory buffer: 70 frames
- Turn detection: 45° minimum angle, 25°/s minimum speed
- Activity filtering: 100px movement, 10 active frames required

---

## 8. Technology Stack

### 8.1 Backend (API)

- **Framework**: FastAPI (async, OpenAPI/Swagger docs)
- **Database**: PostgreSQL 15+
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Task Queue**: Celery with Redis broker
- **Authentication**: JWT tokens (PyJWT)
- **Email**: SMTP (Python's smtplib or service like SendGrid)
- **File Storage**: Local filesystem (mounted volumes)
- **Validation**: Pydantic v2

### 8.2 Frontend (Website)

- **Framework**: Next.js 14+ (App Router)
- **UI Library**: shadcn/ui (Radix UI + Tailwind CSS)
- **State Management**: React Context or Zustand
- **Forms**: React Hook Form + Zod validation
- **API Client**: Axios or native fetch
- **Styling**: Tailwind CSS

### 8.3 Tracker

- **Language**: Python 3.10
- **Computer Vision**: OpenCV, Ultralytics YOLOv8
- **Tracking**: BoTSORT (built into Ultralytics)
- **Pose**: MediaPipe
- **Deep Learning**: PyTorch

### 8.4 Infrastructure

- **Containerization**: Docker + Docker Compose
- **Reverse Proxy**: Nginx (optional, for production)
- **Storage**: Shared Docker volumes for data persistence

---

## 9. Docker Services

The `docker-compose.yml` orchestrates all services:

```yaml
services:
  # PostgreSQL database
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: surf_tracker
      POSTGRES_USER: surf_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Redis for Celery broker
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # FastAPI backend
  api:
    build: ./api
    environment:
      DATABASE_URL: postgresql://surf_user:${DB_PASSWORD}@db:5432/surf_tracker
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      SMTP_HOST: ${SMTP_HOST}
      SMTP_PORT: ${SMTP_PORT}
      SMTP_USER: ${SMTP_USER}
      SMTP_PASSWORD: ${SMTP_PASSWORD}
    volumes:
      - ./data:/data
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis

  # Celery worker for background tasks
  celery_worker:
    build: ./api
    command: celery -A tasks.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://surf_user:${DB_PASSWORD}@db:5432/surf_tracker
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./data:/data
      - /var/run/docker.sock:/var/run/docker.sock  # To run tracker containers
    depends_on:
      - db
      - redis

  # Tracker service (pre-built image)
  tracker:
    build: ./tracker
    # This service doesn't run continuously - called by Celery worker

  # Next.js website
  website:
    build: ./website
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  postgres_data:
```

---

## 10. User Flows

### 10.1 Registration & Email Confirmation

1. User visits `/register`
2. Fills out email + password form
3. API creates user with `is_email_confirmed=false`
4. API generates confirmation token, stores in DB
5. API sends email with confirmation link: `https://app.com/confirm?token=xyz`
6. User clicks link
7. Frontend calls `/api/auth/confirm-email` with token
8. API validates token, sets `is_email_confirmed=true`
9. User redirected to login or dashboard

### 10.2 Profile Setup

1. User logs in (receives JWT token)
2. Visits `/profile`
3. Fills out full name, alias, uploads picture
4. API updates `profiles` table
5. Profile picture stored in `/data/profile_pictures/{user_id}/`

### 10.3 Video Upload & Processing

1. User visits `/dashboard`
2. Clicks "Upload Video"
3. Selects video file (MP4, MOV, etc.)
4. Frontend uploads to `/api/sessions/upload`
5. API:
   - Validates file
   - Saves to `/data/queue/{user_id}/{filename}.mp4`
   - Creates session record (status=`pending`)
   - Triggers Celery task
6. Frontend shows session in list with "Pending" status
7. Background: Celery task runs tracker
8. Frontend polls `/api/sessions/{id}` for status updates
9. When complete, user sees "View Results" button
10. User clicks, navigates to `/session/{id}`
11. Frontend fetches session details, displays:
    - Annotated video player
    - List of detected surfers
    - Per-surfer maneuver timeline
    - Statistics (total maneuvers, types, etc.)

### 10.4 Viewing Results

The session results page displays:
- **Video Player**: Annotated output video with bounding boxes
- **Surfer List**: All detected surfers with track IDs
- **Maneuver Timeline**: Timeline of detected maneuvers per surfer
- **Detailed Metrics**: For each maneuver:
  - Frame snapshot
  - Maneuver type (bottom turn, snap, cutback, etc.)
  - Turn angle, direction, speed
  - Pose metrics (lean, knee bend, arm position)
  - Trajectory metrics (radius, speed, vertical displacement)
- **Download**: Option to download annotated video and JSON data

---

## 11. Security Considerations

- **Password Security**: Use bcrypt or argon2 for hashing
- **JWT Tokens**: Short expiration (15min access, 7d refresh)
- **Email Confirmation**: Required before allowing uploads
- **File Upload**: Validate file types, limit size (e.g., 500MB max)
- **Rate Limiting**: Limit uploads per user per day
- **CORS**: Configure properly for frontend-backend communication
- **SQL Injection**: Use ORM parameterized queries
- **XSS**: Sanitize user inputs in frontend
- **CSRF**: Use CSRF tokens for state-changing requests

---

## 12. Development Phases

### Phase 1: Project Restructuring
- Move tracker files to `tracker/` folder
- Create `api/` and `website/` folder structure
- Set up docker-compose with all services
- Configure shared data volumes

### Phase 2: API Backend
- Set up FastAPI project structure
- Implement database models and migrations
- Build authentication endpoints (register, login, confirm email)
- Build profile management endpoints
- Implement file upload endpoint
- Set up Celery for background tasks

### Phase 3: Tracker Integration
- Modify tracker to accept dynamic input/output paths
- Create Celery task to invoke tracker
- Implement session status tracking
- Parse tracker output and store in database

### Phase 4: Frontend
- Set up Next.js project with shadcn/ui
- Implement authentication pages (register, login)
- Build dashboard with session list
- Create video upload component
- Build session results viewer
- Implement profile management

### Phase 5: Polish & Testing
- Add real-time status updates (polling or WebSocket)
- Implement error handling and retry logic
- Add user feedback (notifications, loading states)
- Performance testing with large videos
- Security audit
- Documentation

---

## 13. Future Enhancements

- **Social Features**: Share sessions, follow other surfers, leaderboards
- **Advanced Analytics**: Compare sessions, track improvement over time
- **Mobile App**: React Native app for on-the-go uploads
- **Live Streaming**: Process live surf competitions
- **AI Improvements**: Train custom models on surf footage, better maneuver classification
- **Wave Detection**: Identify wave characteristics (size, shape, speed)
- **Multiple Camera Angles**: Support for multi-angle footage
- **Collaborative Features**: Coaches can review and comment on sessions
- **Payment Integration**: Premium features, pay-per-processing model
- **Export Options**: Export to social media, create highlight reels

---

This document serves as the complete specification for the Surf Tracker full-stack application, intended for consumption by AI coding agents, development teams, and project stakeholders.
