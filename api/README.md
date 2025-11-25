# Surf Tracker API

FastAPI backend for the Surf Tracker application.

## Quick Start

### Using Docker Compose (Recommended)

```bash
# From project root
docker compose up api
```

Access the API at:
- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Local Development

```bash
cd api

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://surf_user:changeme@localhost:5432/surf_tracker"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="your-secret-key-here"

# Run the server
uvicorn main:app --reload
```

## API Endpoints

### Authentication (`/api/auth/`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/register` | Register new user | No |
| POST | `/login` | Login with email/password | No |
| POST | `/confirm-email` | Confirm email with token | No |
| POST | `/resend-confirmation` | Resend confirmation email | No |
| POST | `/forgot-password` | Request password reset | No |
| POST | `/reset-password` | Reset password with token | No |

### Profile (`/api/profile/`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/me` | Get current user profile | Yes |
| PUT | `/me` | Update profile | Yes |
| POST | `/me/picture` | Upload profile picture | Yes |
| DELETE | `/me/picture` | Delete profile picture | Yes |

### Sessions (`/api/sessions/`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/upload` | Upload video for analysis | Yes (confirmed) |
| GET | `/` | List all user sessions | Yes (confirmed) |
| GET | `/{session_id}` | Get session details | Yes (confirmed) |
| DELETE | `/{session_id}` | Delete session | Yes (confirmed) |

## Testing with Swagger

1. Start the API: `docker compose up api` (or run locally)
2. Open browser to http://localhost:8000/docs
3. Test the authentication flow:

### Register a New User

```json
POST /api/auth/register
{
  "email": "test@example.com",
  "password": "TestPass123"
}
```

### Login

```json
POST /api/auth/login
{
  "email": "test@example.com",
  "password": "TestPass123"
}
```

Response will include `access_token`. Copy this token.

### Authorize in Swagger

1. Click the "Authorize" button at the top right
2. Enter: `Bearer <your_access_token>`
3. Click "Authorize"

Now you can test authenticated endpoints!

### Update Profile

```json
PUT /api/profile/me
{
  "full_name": "Test User",
  "alias": "Surfer123"
}
```

### Upload Video

1. Click "Try it out" on `/api/sessions/upload`
2. Click "Choose File" and select a video
3. Execute

The video will be queued for processing by the Celery worker.

## Testing with cURL

### Register

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "TestPass123"}'
```

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "TestPass123"}'
```

### Get Profile (with auth)

```bash
TOKEN="your_access_token_here"

curl -X GET http://localhost:8000/api/profile/me \
  -H "Authorization: Bearer $TOKEN"
```

### Upload Video (with auth)

```bash
curl -X POST http://localhost:8000/api/sessions/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/video.mp4"
```

## Database Migrations

### Create a migration

```bash
cd api
alembic revision --autogenerate -m "description of changes"
```

### Apply migrations

```bash
alembic upgrade head
```

### Rollback one migration

```bash
alembic downgrade -1
```

## Celery Worker

The Celery worker processes video uploads in the background.

### Start worker (with Docker Compose)

```bash
docker compose up celery_worker
```

### Start worker (local)

```bash
cd api
celery -A tasks.celery_app worker --loglevel=info
```

### Monitor tasks

```bash
# View Celery logs
docker compose logs -f celery_worker
```

## Project Structure

```
api/
├── main.py                 # FastAPI app entry point
├── config.py               # Configuration settings
├── database.py             # Database setup
├── models/                 # SQLAlchemy models
│   ├── user.py
│   ├── profile.py
│   └── session.py
├── schemas/                # Pydantic schemas
│   ├── user.py
│   ├── profile.py
│   └── session.py
├── routers/                # API endpoints
│   ├── auth.py
│   ├── profile.py
│   └── sessions.py
├── services/               # Business logic
│   ├── auth_service.py
│   └── email_service.py
├── tasks/                  # Celery tasks
│   ├── celery_app.py
│   └── video_processing.py
├── utils/                  # Utilities
│   ├── security.py
│   └── dependencies.py
└── alembic/                # Database migrations
```

## Environment Variables

See `.env.example` in the project root for all available configuration options.

Required variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `JWT_SECRET_KEY`: Secret key for JWT tokens
- `SMTP_*`: Email server configuration

## Troubleshooting

### Database connection errors

Make sure PostgreSQL is running:
```bash
docker compose up db
```

### Email not sending

Check SMTP configuration in `.env`. For development, you can use a service like [Mailtrap](https://mailtrap.io/) or [Mailhog](https://github.com/mailhog/MailHog).

### Celery worker not processing videos

1. Make sure Redis is running: `docker compose up redis`
2. Check Celery logs: `docker compose logs celery_worker`
3. Ensure tracker Docker image is built: `docker compose build tracker`

### Video processing fails

Check that:
1. Video file format is supported (MP4, MOV, AVI, MKV)
2. Tracker Docker image exists
3. Data directories have correct permissions
