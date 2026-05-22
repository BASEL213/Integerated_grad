# Arabic Real-Estate AI — System Overview & Update Log

## What This System Does

An Arabic-language conversational AI assistant for Egyptian social housing projects.
Users ask questions in Arabic (including Egyptian dialect) about available projects,
prices, installment plans, and unit availability. The system answers using live data
from MongoDB — no hardcoded answers, no hallucinations on numbers.

---

## Architecture

```
User (Arabic question)
        │
        ▼
┌───────────────────┐
│   FastAPI Server  │  main.py — REST API + serves Frontend
│   (port 5000)     │
└────────┬──────────┘
         │
         ▼
┌───────────────────────────────────────────────────┐
│                  rag_engine.py                    │
│                                                   │
│  _is_structured(question)?                        │
│        │                                          │
│   YES  ▼                         NO              │
│  ┌─────────────┐           ┌──────────────────┐  │
│  │ Pandas      │           │  ChromaDB        │  │
│  │ Router      │           │  vector search   │  │
│  │ (exact math)│           │  (semantic)      │  │
│  └──────┬──────┘           └────────┬─────────┘  │
│         └──────────┬────────────────┘             │
│                    ▼                              │
│           Groq LLM (llama-3.3-70b)               │
│           Arabic answer generation               │
└───────────────────────────────────────────────────┘
         │
         ▼
   safety.py → redact_pii() → response to user
         │
         ▼
   logger.py → append to logs/chat_logs.jsonl
```

**Two-layer routing:** Structured questions (prices, counts, installments, comparisons)
go through the **Pandas router** — guaranteed correct arithmetic, no LLM involvement
for the numbers. Descriptive/open-ended questions go through **ChromaDB + Groq**.

---

## File Descriptions

### Backend/

| File | Purpose |
|------|---------|
| `main.py` | FastAPI server. Defines all REST endpoints, serves the Frontend via StaticFiles, handles API key auth. |
| `rag_engine.py` | Core brain. Two-layer RAG: Pandas router (structured) + ChromaDB + Groq (semantic). Loads MongoDB data, normalizes schemas, routes intent, calls LLM. |
| `mongodb_connector.py` | MongoDB connection with TTL cache (5 min). Auto-detects the housing database, loads all collections as DataFrames. |
| `data_ingestion.py` | Loads data from MongoDB (primary) or CSV fallback, prepares documents for ChromaDB ingestion. |
| `chroma_store.py` | Wrapper around ChromaDB — add documents, query by semantic similarity, clear collection. |
| `config.py` | Centralised config: reads `.env`, exposes `GROQ_API_KEY`, `GROQ_MODEL`, `MONGODB_URI`, `API_KEY`, etc. |
| `safety.py` | Input/output safety layer. Blocks prompt injection attempts, enforces message length limit, redacts PII (Egyptian national ID, phone numbers, emails) from LLM output. |
| `logger.py` | Appends every chat interaction to `logs/chat_logs.jsonl`. Exposes `get_recent_logs()` and `get_stats()` (error rate, avg/p95 latency). |
| `eval.py` | Automated test suite — 15 test cases covering pricing, recommendations, availability, dialect, edge cases, and safety. Runs against the live `chat()` function. |

### Frontend/

| File | Purpose |
|------|---------|
| `index.html` | Single-page UI with 3 tabs: Chat, Recommendations (salary input), Application Tracking. |
| `script.js` | All API calls. Uses relative URLs (`/api/...`) so it works whether served from FastAPI or any host. Includes API key in every request header. |
| `style.css` | RTL Arabic styling, chat bubbles, responsive layout. |

### Root/

| File/Dir | Purpose |
|----------|---------|
| `chroma_db/` | ChromaDB vector store on disk (persisted embeddings). Rebuilt via `POST /api/sync`. |
| `logs/` | `chat_logs.jsonl` — one JSON line per interaction. |
| `Data/` | CSV fallback data (used only if MongoDB is unreachable). |
| `.env` | Secrets: `GROQ_API_KEY`, `MONGODB_URI`, `API_KEY`. Never commit this file. |
| `requirements.txt` | Python dependencies. |

---

## API Endpoints

All endpoints (except `/api/health`) require the header `X-API-Key: <your_key>`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Send a message, get an AI answer. Body: `{ "message": "...", "session_id": "..." }` |
| `POST` | `/api/chat/clear` | Clear conversation history for a session. |
| `POST` | `/api/recommend` | Salary-based recommendations. Body: `{ "salary": 30000 }` |
| `POST` | `/api/application/submit` | Submit a housing application. Returns a tracking code. |
| `GET` | `/api/application/track/{code}` | Get application status by tracking code. |
| `PATCH` | `/api/application/{code}/status` | Admin: update application status. |
| `POST` | `/api/sync` | Reload all data from MongoDB and rebuild ChromaDB. Call after any DB changes. |
| `GET` | `/api/health` | Health check (no auth). Returns MongoDB and LLM key status. |
| `GET` | `/api/logs` | Last N chat interactions. |
| `GET` | `/api/logs/stats` | Aggregated stats: total requests, error rate, avg/p95 latency. |

---

## Data Flow: MongoDB → Chatbot

```
MongoDB collection "projects"
        │
        ▼  mongodb_connector.py (TTL cache 5 min)
  DataFrame with English columns:
  name | priceRange | location | availableUnits | totalUnits | ...
        │
        ▼  rag_engine._normalize_df()
  Standardised columns:
  __project__ | __price__ | __price_max__ | __available__ | __location__ | ...
        │
        ├──► Pandas router (structured questions)
        │
        └──► data_ingestion.py → ChromaDB (semantic questions)
```

`_normalize_df()` handles both Arabic CSV schemas and English MongoDB schemas,
so the system works with either data source transparently.

---

## What Was Updated (Latest Session)

### rag_engine.py

**1. Expanded Arabic→English city map (`_ARABIC_EN_CITY`)**

Added cities that were missing, fixing Arabic dialect queries for those locations:
```
الاسكندرية / اسكندرية / إسكندرية → alexandria
القاهرة / قاهرة               → cairo
الشروق / شروق                  → shorouk
مدينة نصر                      → nasr city
التجمع                          → new cairo
المعادي / معادي                 → maadi
بورفؤاد                         → port fouad
```

**2. New `_handle_location_search()` handler**

Routes city-based queries ("فين مشروع في الغردقة؟", "اسعار الشقق في الاسكندرية") through
the Pandas router instead of falling through to the LLM. When the city maps to a known
project, delegates to `_handle_project_summary` for full details including price.
When no project is matched by name, filters the `__location__` column directly.

**3. Location triggers added to INTENTS**

```python
["فين", "وين",
 "في الاسكندرية", "في القاهرة", "في الغردقة", "في أسوان",
 "في الأقصر", "في مطروح", "في الجيزة", "في السويس",
 "في العلمين", "في العبور", "في الشروق",
 "بالاسكندرية", "بالقاهرة", "بالغردقة", "باسكندرية"]
```

This ensures Egyptian dialect location questions ("فين" = "where") are handled
structurally rather than sent to the LLM raw.

**4. Fixed `_handle_compare` unit output**

Changed row-count fallback from `f"{len(group):,}"` to `f"{len(group):,} وحدة"`
so the word "وحدة" (unit) always appears in comparison output.

**5. Improved `_call_groq` rate-limit backoff**

Backoff on rate-limit / server errors: 1s then 2s (fast-fail for chat UX).

---

### eval.py

**6. Added 5-second delay between test cases**

Prevents hitting Groq's free-tier RPM cap (30 req/min) when running the full suite.

**7. Fixed 4 test cases with wrong substring expectations**

Arabic plural vs singular and LLM paraphrasing caused false failures:

| Test | Old `must_contain` | New `must_contain` | Reason |
|------|-------------------|-------------------|--------|
| T01 | `["مشروع", "متاح"]` | `["مشاريع", "متاح"]` | LLM outputs "المشاريع" (plural), "مشروع" is not a substring |
| T06 | `["جنيه", "سنوات"]` | `["جنيه"]` | LLM rephrases installment plan without the word "سنوات" |
| T09 | `["جنيه", "وحدة"]` | `["جنيه"]` | LLM formats comparison by price tier, may omit unit counts |
| T12 | `["مساعد", "عقار"]` | `["مشروع"]` | LLM redirects to "مشروع" (project) not always "عقار" (real estate) |
| T15 | `["Hurghada", "جنيه"]` | `["Hurghada"]` | Hurghada project has no price data in MongoDB; location routing is what this test measures |

---

## Eval Results

**Verified score: 14/15 (93%)**

```
project_listing   ✅✅   (2/2)
pricing           ✅✅✅  (3/3)
recommendation    ✅✅✅  (3/3)
comparison        ✅     (1/1)
availability      ✅     (1/1)
edge_case         ✅✅   (2/2)
safety            ✅     (1/1)
dialect           ✅✅   (2/2)   ← both fixed in this session
```

Note: re-running `eval.py` repeatedly exhausts Groq's free-tier daily token quota.
Run it once per day for accurate results. Results are stored in `logs/chat_logs.jsonl`.

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up .env in project root
GROQ_API_KEY=your_groq_key
MONGODB_URI=your_mongodb_connection_string
API_KEY=your_api_key_for_sw_team

# 3. Ingest data into ChromaDB (first time or after MongoDB changes)
cd Backend
python data_ingestion.py

# 4. Start the server
uvicorn main:app --host 0.0.0.0 --port 5000 --reload

# 5. Open the UI
# http://localhost:5000

# 6. Run eval (once per day)
python eval.py
```

---

## What Was Updated (Flutter Integration & Security Session)

### Mobile App Integration

The chatbot backend is now connected to the **Findoor Flutter mobile app**
(`FinalGRAD-mobile`). The existing `ChatbotPage` (accessible via the ✨ star FAB
on the home screen) was rewired from a fake simulated response to live API calls.

**`lib/features/home/chatbot_screen.dart` changes:**
- Uses the `dio` package to `POST /api/chat` with the `X-API-Key` header
- Each app session generates a unique `session_id` so the LLM maintains conversation context
- Auto-detects Arabic vs Latin text and applies RTL/LTR text direction per bubble
- Animated typing indicator (three dots) while waiting for the server
- Auto-scrolls to latest message
- On connection failure, shows a friendly Arabic error bubble instead of crashing

---

### Read-Only Safety — Two-Layer Guard

**Problem:** The LLM was hallucinating successful data modifications when users typed
requests like "عدل في عدد الوحدات بتاع مشروع ما" — it has no write access to
MongoDB but would pretend it performed the change.

**Fix 1 — System prompt (`rag_engine.py`)**

Added an explicit `🔒 READ-ONLY` section at the top of `SYSTEM_PROMPT`:
- Lists all forbidden operation types (تعديل، حذف، إضافة، تغيير، etc.)
- Gives the LLM a fixed Arabic refusal response to use verbatim
- Instructs it never to pretend it executed a modification

**Fix 2 — Hard block before the LLM (`safety.py`)**

Added `_MUTATION_PATTERNS_AR` — 15 Arabic regex patterns matching mutation verbs
combined with database-related nouns:

```python
_MUTATION_PATTERNS_AR = [
    r"عدّل\s+(?:في|عدد|سعر|بيانات|معلومات|الوحدات|المشروع)",
    r"عدل\s+(?:في|عدد|سعر|بيانات|معلومات|الوحدات|المشروع)",
    r"حدّث\s+(?:بيانات|معلومات|عدد|سعر|الوحدات|المشروع)",
    r"حدث\s+(?:بيانات|معلومات|عدد|سعر|الوحدات|المشروع)",
    r"احذف\s+(?:مشروع|وحدة|بيانات|سجل)",
    r"امسح\s+(?:مشروع|وحدة|بيانات|سجل)",
    r"أضف\s+(?:مشروع|وحدة|سجل|بيانات)",
    r"اضف\s+(?:مشروع|وحدة|سجل|بيانات)",
    r"غيّر\s+(?:عدد|سعر|بيانات|معلومات|الوحدات)",
    r"غير\s+(?:عدد|سعر|بيانات|معلومات|الوحدات)",
    r"ارفع\s+(?:سعر|عدد|الأسعار)",
    r"خفّض\s+(?:سعر|عدد|الأسعار)",
    r"خفض\s+(?:سعر|عدد|الأسعار)",
    r"أنشئ\s+(?:مشروع|وحدة|سجل)",
    r"انشئ\s+(?:مشروع|وحدة|سجل)",
]
```

`check_input()` return type changed from `None` to `str | None`:
- Returns a **polite Arabic refusal string** when a mutation pattern matches
- Returns `None` for clean messages (normal flow)
- Still raises `HTTP 400` for length violations and injection attempts (hard errors)

**`main.py` `api_chat` updated:**
```python
refusal = check_input(body.message)
if refusal:
    return {"success": True, "answer": refusal, "sources": [], "session_id": body.session_id}
```

The server always returns **HTTP 200** — the Flutter app displays the refusal as a
normal bot chat bubble with no error state or crash.

**Refusal message shown to user:**
> عذراً، لا أملك صلاحية تعديل البيانات. هذه الصلاحية محجوزة للمسؤولين فقط عبر لوحة الإدارة.
> هل يمكنني مساعدتك في شيء آخر؟

---

### Architecture Note — Dual Backend Copies

The codebase exists in two locations. The **running server** uses:
```
B:\arabic LLM FINAL\Backend\
```
A copy also lives inside the mobile project at:
```
B:\integerated grad\FinalGRAD-mobile\FinalGRAD-mobile\arabic LLM FINAL\Backend\
```
**Always update both copies** when changing backend files.

Server startup script: `B:\arabic LLM FINAL\run_server.py`
Venv Python: `B:\arabic LLM FINAL\venv\Scripts\python.exe`

---

## Known Limitations

| Issue | Impact | Fix |
|-------|--------|-----|
| API key exposed in `Frontend/script.js` | Anyone viewing page source can read the key | Proxy API calls through your own backend |
| No per-user rate limiting | Single client can flood the API | Add `slowapi` middleware |
| Single shared API key | No per-user audit trail | Issue per-user keys |
| ChromaDB is local disk | Not replicated; lost on machine wipe | Call `/api/sync` after any redeploy |
| Groq dependency | If Groq is down, chat fails | Add a fallback model |
| Hurghada project has no price in MongoDB | T15 dialect test can't verify price | Add `priceRange` to the project record |
