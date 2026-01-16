# RenfeServer

Backend server project.

## Tech Stack

### Backend
- **Python 3.13+** with **FastAPI**
- **PostgreSQL** database
- **Redis** for cache and background jobs
- DDD + Hexagonal Architecture + CQRS

### Frontend
- **React 19** + **TypeScript**
- **Vite** build tool
- **Tailwind CSS** + **shadcn/ui**
- React Router v6

## Server Access

- **Server:** juanmacias.com
- **Username:** root
- **Domain:** redcercanias.com

## Development

### Prerequisites

- Python 3.13+
- Node.js 20+
- PostgreSQL
- Redis

### Getting Started

```bash
# Backend
cd /Users/juanmacias/Projects/renfeserver
PYTHONPATH=. uv run uvicorn app:app --reload --port 8000

# Frontend
cd /Users/juanmacias/Projects/renfeserver/web/app
npm run dev

# Database
PGPASSWORD=postgres psql -h localhost -p 5443 -U postgres -d renfeserver_dev
```

## License

Proprietary - All rights reserved.
