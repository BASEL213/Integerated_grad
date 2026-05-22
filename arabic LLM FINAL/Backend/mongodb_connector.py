"""
mongodb_connector.py — Live MongoDB data layer
================================================
Connects to MongoDB Atlas, loads every collection as a DataFrame,
and caches the result for CACHE_TTL seconds.

Drop a new collection → call invalidate() or POST /api/sync
and the chatbot picks it up automatically.
"""

import time
import pandas as pd
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config import MONGODB_URI, MONGODB_DB

_client: MongoClient | None = None
_cache: dict[str, pd.DataFrame] = {}
_cache_time: float = 0
CACHE_TTL = 300  # seconds — refresh every 5 minutes automatically


# ── Connection ─────────────────────────────────────────────────────────────────

def _get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000, tls=True)
    return _client


def _get_db():
    client = _get_client()
    if MONGODB_DB:
        return client[MONGODB_DB]
    # Auto-detect: pick first non-system database
    system_dbs = {"admin", "local", "config"}
    for db_name in client.list_database_names():
        if db_name not in system_dbs:
            return client[db_name]
    raise RuntimeError("No user database found in MongoDB cluster.")


def ping() -> bool:
    """Returns True if MongoDB is reachable."""
    try:
        _get_client().admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError):
        return False


# ── Cache management ───────────────────────────────────────────────────────────

def invalidate():
    """Force next call to get_all_dataframes() to reload from MongoDB."""
    global _cache, _cache_time
    _cache = {}
    _cache_time = 0


def _is_stale() -> bool:
    return not _cache or (time.time() - _cache_time) > CACHE_TTL


# ── Main loader ────────────────────────────────────────────────────────────────

def get_all_dataframes(force_refresh: bool = False) -> dict[str, pd.DataFrame]:
    """
    Returns {collection_name: DataFrame} for every collection in the database.
    Results are cached for CACHE_TTL seconds.
    Pass force_refresh=True (or call invalidate()) to reload immediately.
    """
    global _cache, _cache_time

    if not force_refresh and not _is_stale():
        return _cache

    db     = _get_db()
    result = {}

    for col_name in db.list_collection_names():
        try:
            docs = list(db[col_name].find({}, {"_id": 0}))
            if not docs:
                continue
            df = pd.DataFrame(docs)
            df.columns = df.columns.str.strip()
            result[col_name] = df
            print(f"[MongoDB] Loaded '{col_name}': {len(df)} rows, {len(df.columns)} cols")
        except Exception as e:
            print(f"[MongoDB] Skipping '{col_name}': {e}")

    _cache      = result
    _cache_time = time.time()
    print(f"[MongoDB] Cache refreshed — {len(result)} collections loaded.")
    return result


def get_collection_names() -> list[str]:
    """Returns list of all collection names in the database."""
    try:
        return _get_db().list_collection_names()
    except Exception as e:
        print(f"[MongoDB] Could not list collections: {e}")
        return []
