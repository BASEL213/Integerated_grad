# Real-Estate AI — REST API Reference
### For the SW Backend & Frontend Teams

**Base URL (local dev):** `http://localhost:5000`  
**Content-Type:** `application/json` (unless noted otherwise)

---

## Authentication

Set `API_KEY` in `.env`. Every request must include:

```
X-API-Key: <your-key>
```

If `API_KEY` is empty the header is **not required** (dev mode).  
`GET /api/health` and `GET /api/status` are **always public** (no key needed).

---

## Response envelope

All endpoints return:

```json
{ "success": true,  ...fields }   // 2xx
{ "success": false, "error": "..." }  // 4xx / 5xx
```

---

## Endpoints

### GET `/api/health`
System health — use this to check if the AI service is up before making calls.

**Response**
```json
{
  "success": true,
  "status": "running",
  "auth_enabled": true,
  "llm_model": "llama-3.3-70b-versatile (Groq)",
  "llm_key_set": true,
  "ocr_providers": ["ngrok (colab)", "openrouter"],
  "ngrok_url": "https://staring-reliant-revocable.ngrok-free.dev",
  "csv_files": ["L_Obour.csv", "North_coast.csv", "new_cairo.csv"],
  "db_chunks": 312,
  "db_sources": ["L_Obour.csv", "North_coast.csv", "new_cairo.csv"]
}
```

---

### POST `/api/chat`
Main Arabic chatbot — answers questions about projects, prices, requirements, etc.

**Request**
```json
{
  "message": "ما هي المشاريع المتاحة؟",
  "session_id": "user-abc-123"
}
```
- `session_id` (optional): any string that identifies the user's session.  
  Pass the same ID across turns to keep conversation history.  
  If omitted defaults to `"default"` (shared across all callers — not recommended for production).

**Response**
```json
{
  "success": true,
  "answer": "المشاريع المتاحة في قاعدة البيانات:\n  • العلمين...",
  "sources": ["قاعدة البيانات المباشرة (CSV)"],
  "session_id": "user-abc-123"
}
```

**Example questions the chatbot handles:**
- `ما هي المشاريع المتاحة؟`
- `ما الأوراق المطلوبة للتقديم؟`
- `ما سعر وحدة في العبور؟`
- `ما القسط على 7 سنوات في نزهة الأندلس؟`
- `أريد التقديم على وحدة في العلمين`
- `رشح لي مشروع مناسب لدخل 15,000 جنيه`

---

### POST `/api/chat/clear`
Clears conversation history for a session.

**Request**
```json
{ "session_id": "user-abc-123" }
```

**Response**
```json
{ "success": true, "message": "Chat history cleared", "session_id": "user-abc-123" }
```

---

### POST `/api/recommend`
Returns salary-based project recommendations.

**Request**
```json
{
  "salary": 15000,
  "session_id": "user-abc-123"
}
```
- `salary`: net monthly income in EGP (integer or string with commas).

**Response**
```json
{
  "success": true,
  "answer": "بناءً على دخل شهري قدره 15,000 جنيه، إليك أفضل الترشيحات...",
  "sources": ["قاعدة البيانات المباشرة (CSV)"],
  "session_id": "user-abc-123",
  "salary_input": 15000
}
```

---

### POST `/api/ocr`
Extracts structured data from an Arabic document image.  
**Content-Type:** `multipart/form-data`

**Form fields**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | image file | Yes | JPG / PNG / WEBP — ID card or salary statement |
| `provider` | string | No | `auto` (default) \| `ngrok` \| `openrouter` \| `hf` |

**Response**
```json
{
  "success": true,
  "message": "OCR extraction complete",
  "provider": "ngrok (colab)",
  "filename": "id_card.jpg",
  "data": {
    "full_name": "أحمد محمد علي حسن",
    "id_number": "30101011234567",
    "job": "مهندس",
    "monthly_income": 12000,
    "_provider": "ngrok"
  }
}
```
- Any field can be `null` if the value was not readable in the image.
- `id_number` is validated to be exactly 14 digits (null otherwise).
- `monthly_income` is always an integer (EGP) or null.

**Error (all providers failed)**
```json
{ "success": false, "error": "OCR failed: All OCR providers failed. Details: ..." }
```
HTTP 502.

---

### POST `/api/application/submit`
Submits a housing application and returns a tracking code.

**Request**
```json
{
  "full_name": "أحمد محمد علي حسن",
  "id_number": "30101011234567",
  "job": "مهندس",
  "monthly_income": 12000,
  "selected_project": "العبور",
  "installment_plan": "7 سنوات",
  "phone": "01012345678"
}
```
Required: `full_name`, `id_number`.  
All other fields are optional but recommended.

**Response** — HTTP 201
```json
{
  "success": true,
  "message": "Application submitted successfully",
  "tracking_code": "A3F9E1B2",
  "status": "pending_review",
  "status_label": "تحت المراجعة"
}
```

---

### GET `/api/application/track/<code>`
Retrieves a full application by tracking code.

```
GET /api/application/track/A3F9E1B2
```

**Response**
```json
{
  "success": true,
  "application": {
    "tracking_code": "A3F9E1B2",
    "full_name": "أحمد محمد علي حسن",
    "id_number": "30101011234567",
    "selected_project": "العبور",
    "status": "pending_review",
    "status_label": "تحت المراجعة",
    "submission_date": "2026-04-25 14:30:00"
  }
}
```

---

### PATCH `/api/application/<code>/status`
**Admin / SW backend only** — updates application status after review.

**Request**
```json
{
  "status": "approved",
  "notes": "تم التحقق من المستندات"
}
```

Valid `status` values:

| Value | Arabic label |
|-------|-------------|
| `pending_review` | تحت المراجعة |
| `awaiting_docs` | بانتظار المستندات |
| `approved` | تمت الموافقة |
| `rejected` | مرفوض |
| `cancelled` | ملغي |

**Response**
```json
{
  "success": true,
  "message": "Status updated",
  "tracking_code": "A3F9E1B2",
  "status": "approved",
  "status_label": "تمت الموافقة"
}
```

---

## Typical Integration Flow

```
1. App starts → GET /api/health   (confirm AI service is up)

2. User opens chat →
   POST /api/chat  { message, session_id }
   ↳ show answer, keep session_id for next messages

3. User asks for recommendation →
   POST /api/recommend  { salary, session_id }
   ↳ show recommended projects

4. User wants to apply →
   a. POST /api/ocr  (multipart, file = ID card image)
      ↳ get { full_name, id_number, job, monthly_income }
   b. Show extracted data to user for confirmation/editing
   c. POST /api/application/submit  { all fields }
      ↳ get tracking_code
   d. Show tracking_code to user

5. User tracks their application →
   GET /api/application/track/<code>

6. Admin updates status →
   PATCH /api/application/<code>/status  { status, notes }
```

---

## Running locally

```bash
cd "b:/arabic LLM/Backend"
pip install -r ../requirements.txt
python app.py
# Server starts at http://0.0.0.0:5000
```

Before the first run (or after adding new CSV data):
```bash
# POST http://localhost:5000/api/ingest/reset
curl -X POST http://localhost:5000/api/ingest/reset -H "X-API-Key: <key>"
```

---

## Notes for deployment

- The Flask server runs on port **5000**. Put it behind nginx/caddy in production.
- Set `ALLOWED_ORIGINS` in `.env` to your frontend's actual domain.
- Set a strong random `API_KEY` — share it only with the backend team.
- The OCR ngrok URL (`NGROK_OCR_URL`) must be updated each time the Colab session restarts.  
  Consider exposing it via your own endpoint so the frontend doesn't hardcode it.
- Application data is stored as JSON files in `Data/applications/`.  
  Migrate to a real database (PostgreSQL / SQLite) before going to production.
