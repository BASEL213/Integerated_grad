"""
main.py — Arabic Real-Estate AI  |  FastAPI
============================================
Run:
    uvicorn main:app --host 0.0.0.0 --port 5000 --reload

Interactive docs (for SW team):
    http://localhost:5000/docs
"""

import os
import uuid
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from werkzeug.utils import secure_filename

from config import UPLOADS_DIR, APPLICATIONS_DIR, API_KEY, ALLOWED_ORIGINS
from rag_engine import chat, clear_history, refresh_data
from safety import check_input
from logger import get_recent_logs, get_stats

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Arabic Real-Estate AI API",
    description="LLM chatbot + salary recommendations + application management for Egyptian social housing projects.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ──────────────────────────────────────────────────────────────────────

def require_api_key(x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized — invalid or missing X-API-Key")


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class ChatClearRequest(BaseModel):
    session_id: str = "default"

class RecommendRequest(BaseModel):
    salary: int
    session_id: Optional[str] = None

class ApplicationSubmit(BaseModel):
    full_name: str
    id_number: str
    project: Optional[str] = None
    unit_type: Optional[str] = None
    phone: Optional[str] = None
    monthly_salary: Optional[int] = None

class StatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_STATUSES = {"pending_review", "awaiting_docs", "approved", "rejected", "cancelled"}
STATUS_LABELS  = {
    "pending_review": "تحت المراجعة",
    "awaiting_docs":  "بانتظار المستندات",
    "approved":       "تمت الموافقة",
    "rejected":       "مرفوض",
    "cancelled":      "ملغي",
}


def _load_application(code: str) -> dict | None:
    path = os.path.join(APPLICATIONS_DIR, f"{code.upper()}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_application(code: str, data: dict):
    os.makedirs(APPLICATIONS_DIR, exist_ok=True)
    with open(os.path.join(APPLICATIONS_DIR, f"{code.upper()}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/api/chat", tags=["Chat"], dependencies=[Depends(require_api_key)])
def api_chat(body: ChatRequest):
    """
    Send a message to the Arabic real-estate AI assistant.
    The model remembers conversation history per `session_id`.
    """
    if not body.message.strip():
        raise HTTPException(400, "'message' must not be empty")
    refusal = check_input(body.message)
    if refusal:
        return {"success": True, "answer": refusal, "sources": [], "session_id": body.session_id}
    result = chat(body.message.strip(), body.session_id)
    return {"success": True, **result}


@app.post("/api/chat/clear", tags=["Chat"], dependencies=[Depends(require_api_key)])
def api_chat_clear(body: ChatClearRequest):
    """Clear conversation history for a session."""
    clear_history(body.session_id)
    return {"success": True, "message": "Chat history cleared", "session_id": body.session_id}


# ── Recommendations ───────────────────────────────────────────────────────────

@app.post("/api/recommend", tags=["Recommendations"], dependencies=[Depends(require_api_key)])
def api_recommend(body: RecommendRequest):
    """
    Get affordable housing recommendations based on monthly salary.
    Returns projects + units the user can afford, with correct installment math.
    """
    if body.salary <= 0:
        raise HTTPException(400, "'salary' must be a positive number")
    session_id = body.session_id or f"rec_{uuid.uuid4().hex[:8]}"
    query      = f"أريد ترشيح مشروع مناسب لدخل شهري {body.salary} جنيه"
    result     = chat(query, session_id)
    result["salary_input"] = body.salary
    return {"success": True, **result}


# ── Application ───────────────────────────────────────────────────────────────

@app.post("/api/application/submit", tags=["Applications"], status_code=201,
          dependencies=[Depends(require_api_key)])
def api_submit(body: ApplicationSubmit):
    """Submit a housing application. Returns a tracking code."""
    tracking_code = str(uuid.uuid4())[:8].upper()
    data = body.model_dump()
    data.update({
        "tracking_code":   tracking_code,
        "submission_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status":          "pending_review",
        "status_label":    STATUS_LABELS["pending_review"],
    })
    _save_application(tracking_code, data)
    return {
        "success":       True,
        "tracking_code": tracking_code,
        "status":        "pending_review",
        "status_label":  STATUS_LABELS["pending_review"],
    }


@app.get("/api/application/track/{code}", tags=["Applications"],
         dependencies=[Depends(require_api_key)])
def api_track(code: str):
    """Get application details by tracking code."""
    app_data = _load_application(code)
    if not app_data:
        raise HTTPException(404, f"Tracking code '{code.upper()}' not found")
    return {"success": True, "application": app_data}


@app.patch("/api/application/{code}/status", tags=["Applications"],
           dependencies=[Depends(require_api_key)])
def api_update_status(code: str, body: StatusUpdate):
    """
    Update application status (admin use).
    Valid values: pending_review | awaiting_docs | approved | rejected | cancelled
    """
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Allowed: {sorted(VALID_STATUSES)}")
    app_data = _load_application(code)
    if not app_data:
        raise HTTPException(404, f"Tracking code '{code.upper()}' not found")
    app_data["status"]       = body.status
    app_data["status_label"] = STATUS_LABELS[body.status]
    app_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if body.notes:
        app_data["admin_notes"] = body.notes
    _save_application(code, app_data)
    return {"success": True, "tracking_code": code.upper(),
            "status": body.status, "status_label": STATUS_LABELS[body.status]}


# ── Monitoring ───────────────────────────────────────────────────────────────

@app.get("/api/logs", tags=["Monitoring"], dependencies=[Depends(require_api_key)])
def api_logs(n: int = 50):
    """Return the last N chat interactions (prompts + responses + latency)."""
    return {"success": True, "logs": get_recent_logs(n)}


@app.get("/api/logs/stats", tags=["Monitoring"], dependencies=[Depends(require_api_key)])
def api_log_stats():
    """Aggregated stats: total requests, error rate, avg latency, p95 latency."""
    return {"success": True, "stats": get_stats()}


# ── Sync ─────────────────────────────────────────────────────────────────────

@app.post("/api/sync", tags=["System"], dependencies=[Depends(require_api_key)])
def api_sync():
    """
    Reload all data from MongoDB and rebuild ChromaDB.
    Call this whenever you add, update, or drop a collection in MongoDB.
    """
    try:
        from data_ingestion import prepare_documents
        from chroma_store import add_documents, clear_collection, get_collection_info

        refresh_data()                    # invalidate rag_engine + mongodb cache
        clear_collection()                # wipe ChromaDB
        documents = prepare_documents()   # reload from MongoDB
        if not documents:
            raise HTTPException(500, "No data found in MongoDB after sync")
        add_documents(documents)
        info = get_collection_info()
        return {
            "success":        True,
            "message":        "Sync complete — chatbot now reflects latest MongoDB data",
            "chunks_ingested": len(documents),
            "total_in_db":    info["count"],
            "collections":    info.get("sources", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {str(e)}")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
def api_health():
    """Health check — no auth required. SW team can ping this to verify the server is up."""
    from config import GROQ_API_KEY
    from mongodb_connector import ping, get_collection_names
    mongo_ok      = ping()
    collections   = get_collection_names() if mongo_ok else []
    return {
        "status":        "running",
        "auth_enabled":  bool(API_KEY),
        "llm_model":     "llama-3.3-70b-versatile (Groq)",
        "llm_key_set":   bool(GROQ_API_KEY),
        "mongodb":       "connected" if mongo_ok else "unreachable",
        "collections":   collections,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "Frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(APPLICATIONS_DIR, exist_ok=True)
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
