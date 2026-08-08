"""main.py — FlowLens API (FastAPI + PostgreSQL).

Single-service backend covering auth, file upload, bottleneck analysis,
and PDF report generation. Designed to deploy as-is on Render (or any
container host) with a Supabase/Render Postgres database.

Run locally:
    pip install -r requirements.txt
    uvicorn main:app --reload

Required env vars: DATABASE_URL, JWT_SECRET, CLIENT_URL (CORS origin)
"""

import os
import json
import uuid
import requests
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from db import get_cursor, init_db
from auth import hash_password, verify_password, create_token, get_current_user, require_admin, public_user
from analysis import run_analysis
from parsing import parse_csv_bytes, parse_excel_bytes, parse_google_sheet_csv_url
from pdf_report import generate_report_pdf

app = FastAPI(title="FlowLens API")

CLIENT_URL = os.environ.get("CLIENT_URL", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CLIENT_URL.split(",")] if CLIENT_URL != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FlowLens API"}


# ---------------------------------------------------------------- auth ----

class RegisterBody(BaseModel):
    name: str
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class SettingsBody(BaseModel):
    z_threshold: float | None = None


@app.post("/api/auth/register")
def register(body: RegisterBody):
    if not body.name or not body.email or not body.password:
        raise HTTPException(400, "Name, email, and password are all required.")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")

    email = body.email.lower().strip()
    with get_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            raise HTTPException(409, "An account with this email already exists.")
        cur.execute("SELECT COUNT(*) AS c FROM users")
        total_users = cur.fetchone()["c"]

    role = "admin" if total_users == 0 else "user"
    user_id = str(uuid.uuid4())
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO users (id, name, email, password_hash, role) VALUES (%s, %s, %s, %s, %s)",
            (user_id, body.name.strip(), email, hash_password(body.password), role),
        )
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()

    return {"token": create_token(user_id), "user": public_user(user)}


@app.post("/api/auth/login")
def login(body: LoginBody):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (body.email.lower().strip(),))
        user = cur.fetchone()

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")

    return {"token": create_token(user["id"]), "user": public_user(user)}


@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    return {"user": public_user(user)}


@app.patch("/api/auth/settings")
def update_settings(body: SettingsBody, user=Depends(get_current_user)):
    if body.z_threshold is not None:
        with get_cursor(commit=True) as cur:
            cur.execute("UPDATE users SET z_threshold = %s WHERE id = %s", (body.z_threshold, user["id"]))
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user["id"],))
        updated = cur.fetchone()
    return {"user": public_user(updated)}


# ------------------------------------------------------------- datasets ----

def _get_owned_dataset(dataset_id: str, user):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM datasets WHERE id = %s", (dataset_id,))
        dataset = cur.fetchone()
    if not dataset:
        raise HTTPException(404, "Dataset not found.")
    if dataset["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(403, "Not authorized to access this dataset.")
    return dataset


@app.get("/api/datasets")
def list_datasets(user=Depends(get_current_user)):
    with get_cursor() as cur:
        if user["role"] == "admin":
            cur.execute(
                """SELECT d.*, u.name AS owner_name, u.email AS owner_email
                   FROM datasets d JOIN users u ON u.id = d.user_id
                   ORDER BY d.created_at DESC"""
            )
        else:
            cur.execute("SELECT * FROM datasets WHERE user_id = %s ORDER BY created_at DESC", (user["id"],))
        datasets = cur.fetchall()
    return {"datasets": datasets}


@app.delete("/api/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, user=Depends(get_current_user)):
    _get_owned_dataset(dataset_id, user)
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM datasets WHERE id = %s", (dataset_id,))
    return {"success": True}


def _store_records(user_id: str, name: str, source: str, records: list) -> dict:
    dataset_id = str(uuid.uuid4())
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO datasets (id, user_id, name, source, row_count) VALUES (%s, %s, %s, %s, %s)",
            (dataset_id, user_id, name, source, len(records)),
        )
        for r in records:
            cur.execute(
                """INSERT INTO records (dataset_id, item_id, stage, entry_time, exit_time, duration_seconds)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (dataset_id, r["item_id"], r["stage"], r["entry_time"], r["exit_time"], r["duration_seconds"]),
            )
    return {"id": dataset_id, "name": name, "row_count": len(records)}


# --------------------------------------------------------------- upload ----

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    name: str = Form(default=""),
    user=Depends(get_current_user),
):
    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(400, "File exceeds the 20MB limit.")

    is_excel = bool(file.filename and file.filename.lower().endswith((".xlsx", ".xls")))
    records, errors = (parse_excel_bytes(raw) if is_excel else parse_csv_bytes(raw))

    if not records:
        raise HTTPException(400, f"Could not parse any valid rows from this file. Details: {errors[:5]}")

    dataset = _store_records(user["id"], name or file.filename or "Untitled dataset", "upload", records)
    return {"dataset": dataset, "warnings": errors[:20], "skippedRows": len(errors)}


class SheetImportBody(BaseModel):
    spreadsheetUrl: str
    name: str | None = None


@app.post("/api/sheets/import")
def import_sheet(body: SheetImportBody, user=Depends(get_current_user)):
    """Simple, no-OAuth import: the target sheet must be shared as
    'Anyone with the link can view'. FlowLens fetches its public CSV export."""
    try:
        csv_url = parse_google_sheet_csv_url(body.spreadsheetUrl)
        resp = requests.get(csv_url, timeout=20)
        resp.raise_for_status()
    except Exception:
        raise HTTPException(
            400,
            "Failed to fetch this sheet. Make sure the URL is correct and the sheet is "
            "shared as 'Anyone with the link can view'.",
        )

    records, errors = parse_csv_bytes(resp.content)
    if not records:
        raise HTTPException(400, f"Could not parse any valid rows from this sheet. Details: {errors[:5]}")

    dataset = _store_records(user["id"], body.name or "Google Sheet import", "sheets", records)
    return {"dataset": dataset, "warnings": errors[:20], "skippedRows": len(errors)}


# -------------------------------------------------------------- analysis ----

class RunAnalysisBody(BaseModel):
    zThreshold: float | None = None


@app.post("/api/analysis/{dataset_id}/run")
def run_dataset_analysis(dataset_id: str, body: RunAnalysisBody, user=Depends(get_current_user)):
    dataset = _get_owned_dataset(dataset_id, user)
    z_threshold = body.zThreshold if body.zThreshold is not None else user["z_threshold"]

    with get_cursor() as cur:
        cur.execute("SELECT * FROM records WHERE dataset_id = %s", (dataset_id,))
        records = cur.fetchall()

    result = run_analysis(records, float(z_threshold))
    if result.get("error"):
        raise HTTPException(400, result["error"])

    analysis_id = str(uuid.uuid4())
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO analyses (id, dataset_id, result_json, z_threshold) VALUES (%s, %s, %s, %s)",
            (analysis_id, dataset_id, json.dumps(result, default=str), z_threshold),
        )

    return {"analysisId": analysis_id, "result": result}


@app.get("/api/analysis/{dataset_id}/latest")
def latest_analysis(dataset_id: str, user=Depends(get_current_user)):
    dataset = _get_owned_dataset(dataset_id, user)
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM analyses WHERE dataset_id = %s ORDER BY created_at DESC LIMIT 1",
            (dataset_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "No analysis has been run for this dataset yet.")
    return {"analysisId": row["id"], "result": row["result_json"], "createdAt": row["created_at"]}


# ---------------------------------------------------------------- report ----

@app.get("/api/report/{dataset_id}/pdf")
def download_report(dataset_id: str, user=Depends(get_current_user)):
    dataset = _get_owned_dataset(dataset_id, user)
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM analyses WHERE dataset_id = %s ORDER BY created_at DESC LIMIT 1",
            (dataset_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Run an analysis first before downloading a report.")

    pdf_bytes = generate_report_pdf(dataset["name"], row["result_json"], user["name"])
    safe_name = "".join(c if c.isalnum() else "_" for c in dataset["name"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="FlowLens_Report_{safe_name}.pdf"'},
    )


# ----------------------------------------------------------------- admin ----

@app.get("/api/auth/users")
def list_users(user=Depends(get_current_user)):
    require_admin(user)
    with get_cursor() as cur:
        cur.execute("SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC")
        return {"users": cur.fetchall()}
