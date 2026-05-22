"""
logger.py — Production request/response logging
Every AI interaction is appended to logs/chat_logs.jsonl
"""
import os
import json
from datetime import datetime

_BASE     = os.path.dirname(__file__)
LOG_DIR   = os.path.join(_BASE, "..", "logs")
LOG_FILE  = os.path.join(LOG_DIR, "chat_logs.jsonl")


def log_interaction(session_id: str, message: str, answer: str,
                    sources: list, latency_ms: float, error: str | None = None):
    os.makedirs(LOG_DIR, exist_ok=True)
    entry = {
        "ts":         datetime.utcnow().isoformat(),
        "session_id": session_id,
        "message":    message,
        "answer":     answer[:500],   # truncate for storage
        "sources":    sources,
        "latency_ms": round(latency_ms),
        "error":      error,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_recent_logs(n: int = 50) -> list:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    entries = [json.loads(l) for l in lines]
    return entries[-n:] if n else entries


def get_stats() -> dict:
    logs = get_recent_logs(n=0)
    if not logs:
        return {"total_requests": 0}
    errors    = [l for l in logs if l.get("error")]
    latencies = [l["latency_ms"] for l in logs if l.get("latency_ms")]
    sorted_lat = sorted(latencies)
    return {
        "total_requests": len(logs),
        "error_count":    len(errors),
        "error_rate_pct": round(len(errors) / len(logs) * 100, 1),
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "p95_latency_ms": round(sorted_lat[int(len(sorted_lat) * 0.95)]) if sorted_lat else 0,
        "unique_sessions": len({l["session_id"] for l in logs}),
    }
