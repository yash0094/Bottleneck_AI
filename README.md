# FlowLens AI — simplified stack

Finds your process's weakest link: upload operations data (CSV/Excel or a
public Google Sheet), FlowLens statistically detects the bottleneck stage
and stuck items, and gives you a plain-English report + downloadable PDF.

This is a **rewrite for easy deployment**, replacing the original
Node/Express + React/Vite/Docker stack with:

- **Backend:** Python (FastAPI) + PostgreSQL. One `main.py`, no Docker
  required — deploys on Render as a plain "Web Service" with a build/start
  command, or runs anywhere `pip install -r requirements.txt` works.
- **Frontend:** plain HTML/CSS/JavaScript, zero build step. Deploys on
  Render as a "Static Site" (or any static host — Netlify, Vercel, GitHub
  Pages, Supabase Storage, etc).
- **Database:** PostgreSQL — point `DATABASE_URL` at a free Supabase
  project or a Render Postgres instance.

```
flowlens/
├── backend/          FastAPI app (deploy as a Render "Web Service")
│   ├── main.py        all API routes
│   ├── db.py           Postgres connection + schema
│   ├── auth.py          JWT + password hashing
│   ├── analysis.py       bottleneck detection engine
│   ├── parsing.py         CSV/Excel/Google-Sheet parsing
│   ├── pdf_report.py       PDF report generator
│   ├── requirements.txt
│   ├── runtime.txt
│   ├── Procfile
│   └── .env.example
├── frontend/          static HTML/CSS/JS (deploy as a Render "Static Site")
│   ├── index.html      login / sign up
│   ├── dashboard.html    dataset list
│   ├── upload.html        CSV/Excel upload + Sheets import
│   ├── report.html         bottleneck report + PDF download
│   ├── css/style.css
│   └── js/                config.js, api.js, auth.js, dashboard.js, upload.js, report.js
└── samples/sample_process_data.csv
```

## What changed vs. the previous evaluation feedback

The screenshots you shared flagged: no automated testing, no CI/CD, no
`.gitignore`, missing docs, and heavy DevOps surface area (Docker + Node +
Express + Vite + nginx). This rewrite directly addresses the deployment
pain points:

- Removed Express, Node build tooling, Vite, Tailwind build, nginx config,
  and Docker — nothing to compile, so Render's default Python/static
  buildpacks just work.
- Swapped SQLite (`better-sqlite3`, file-based, doesn't survive Render's
  ephemeral filesystem) for Postgres, which is what makes Supabase/Render
  Postgres deployment possible in the first place.
- Google Sheets import no longer requires a Google OAuth app/consent
  screen (a common source of deployment friction) — it fetches the sheet's
  public CSV export instead. Trade-off: the sheet must be shared as
  "Anyone with the link can view". If you need private-sheet OAuth import
  back, that's a clean addition to `parsing.py` / `main.py` later.
- Added a real `.gitignore`, a `.env.example`, and inline docstrings on
  every module (the specific gaps called out in the "Areas for
  improvement" panel in your screenshots).
- Kept the same bottleneck math (z-score vs. stage mean, IQR outlier rule,
  cause classification) so results match the original engine.

I didn't add a test suite or CI pipeline in this pass, since you asked to
keep this round focused and deployable — say the word and I'll add
`pytest` + a GitHub Actions workflow next.

## 1. Database — Supabase (free tier works)

1. Create a project at supabase.com.
2. Project Settings → Database → Connection string → **URI**. Copy it —
   this is your `DATABASE_URL`. (Use the "Transaction" pooler connection
   string if you're on a serverless-style host.)
3. Nothing else to do — `main.py` creates all tables automatically on
   first startup.

(A Render Postgres instance works identically — just use its connection
string instead.)

## 2. Backend — Render Web Service

1. Push this repo to GitHub.
2. Render → New → Web Service → connect the repo, root directory
   `backend`.
3. Build command: `pip install -r requirements.txt`
   Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   (Render also auto-detects the included `Procfile`.)
4. Environment variables:
   - `DATABASE_URL` — from step 1
   - `JWT_SECRET` — any long random string
   - `CLIENT_URL` — your frontend's Render static site URL (set this
     after step 3 below; comma-separate multiple origins if needed)
5. Deploy. Check `https://<your-backend>.onrender.com/api/health`.

## 3. Frontend — Render Static Site

1. Edit `frontend/js/config.js` and set `API_BASE_URL` to your backend
   URL from step 2.
2. Render → New → Static Site → connect the repo, root directory
   `frontend`, no build command, publish directory `.`.
3. Deploy. Visit the static site URL, sign up (the first account becomes
   admin automatically), and upload `samples/sample_process_data.csv` to
   try it end to end.

Go back and set the backend's `CLIENT_URL` to this static site's URL so
CORS allows it, then redeploy the backend.

## Running locally

```bash
# backend
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL + JWT_SECRET
export $(cat .env | xargs)
uvicorn main:app --reload

# frontend — any static file server works, e.g.
cd frontend
python3 -m http.server 5500
# then open http://localhost:5500 (config.js already points at localhost:8000)
```

## API summary

| Method & path | Purpose |
|---|---|
| `POST /api/auth/register` / `/login` | account creation / sign-in |
| `GET /api/auth/me` | current user |
| `PATCH /api/auth/settings` | update bottleneck sensitivity |
| `POST /api/upload` | upload CSV/Excel (multipart) |
| `POST /api/sheets/import` | import a public Google Sheet |
| `GET /api/datasets` / `DELETE /api/datasets/{id}` | list / delete datasets |
| `POST /api/analysis/{id}/run` | run bottleneck analysis |
| `GET /api/analysis/{id}/latest` | fetch last analysis |
| `GET /api/report/{id}/pdf` | download the PDF report |

This backend was integration-tested end-to-end (register → upload →
analyze → PDF download) against a live Postgres instance before delivery.
