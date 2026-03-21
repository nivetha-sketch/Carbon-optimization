# Full-Stack Carbon Optimizer App

## Architecture

- `backend/app/main.py`: FastAPI backend for pipeline execution and analytics APIs.
- `frontend/`: React + Vite frontend with colorful charts and user-friendly filters.

## Backend setup

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

## Frontend setup

```bash
cd frontend
npm install
# Optional: change backend URL for frontend
# copy .env.example .env.local and update VITE_API_BASE_URL
npm run dev
```

Frontend runs at `http://localhost:5173` and calls backend from `VITE_API_BASE_URL` (default: `http://127.0.0.1:8000`).

## API endpoints

- `GET /health`
- `POST /pipeline/run/all`
- `POST /pipeline/run/{train|generate|predict|decide|schedule|evaluate}`
- `GET /dashboard/meta`
- `POST /dashboard/analytics`
- `GET /model/config` (shows active training dataset and available steps)

### Filter payload

```json
{
  "decisions": [],
  "regions": [],
  "priorities": [],
  "logic": "and",
  "limit": 300
}
```
