# Egyptian NID OCR — Technical Deep Dive

A production-grade pipeline for extracting all six fields from an Egyptian National ID card photograph in 3–15 seconds using a two-pass LLM strategy with a full PaddleOCR fallback.

---

## Table of Contents

1. [What Gets Extracted](#what-gets-extracted)
2. [Architecture Overview](#architecture-overview)
3. [How the Two-Pass LLM Strategy Works](#how-the-two-pass-llm-strategy-works)
4. [How the PaddleOCR Fallback Works](#how-the-paddleocr-fallback-works)
5. [Image Preprocessing](#image-preprocessing)
6. [Provider Cascade and Rate Limit Handling](#provider-cascade-and-rate-limit-handling)
7. [Field Validation and Post-processing](#field-validation-and-post-processing)
8. [Challenges and How We Solved Them](#challenges-and-how-we-solved-them)
9. [Limitations](#limitations)
10. [Future Plans](#future-plans)
11. [Running the Server](#running-the-server)
12. [API Reference](#api-reference)

---

## What Gets Extracted

| Arabic Field Key | English | Example |
|---|---|---|
| `الاسم بالكامل` | Full name | باسل اشرف عبدالعزيز محمد حسنين |
| `الرقم القومي` | 14-digit NID number | ٣٠١١٠٢١٠١٠٤٧٢٩ |
| `تاريخ الميلاد` | Date of birth | ٢٠٠١/١٠/٢١ |
| `العنوان بالكامل` | Street address | ٧ ش منصور عطفة رامز لاظوغلى |
| `المنطقة والمحافظة` | District and governorate | السيدة زينب القاهرة |
| `رقم البطاقة` | Card serial number | 1M4729408 |

All numeric values are returned in **Arabic-Indic digits** (٠١٢٣٤٥٦٧٨٩) to match what is printed on the card.

---

## Architecture Overview

```
Mobile App (Flutter)
      |
      |  POST /ocr/extract   (multipart image)
      v
+------------------------------------------+
|       Flask API  (flask_api.py)          |
|                                          |
|  +------------------------------------+  |
|  |  LLM Extractor (llm_extractor.py) |  |  ~3-15 s
|  |                                    |  |
|  |  Pass 1: full card -> 6 fields     |  |
|  |  Pass 2: NID strip zoom            |  |
|  |                                    |  |
|  |  Provider cascade:                 |  |
|  |    Gemini 2.5 Flash                |  |
|  |    -> Gemini 2.0 Flash             |  |
|  |    -> Gemini 2.0 Flash-Lite        |  |
|  |    -> Groq (Llama-4 Scout)         |  |
|  +------------------------------------+  |
|                 |                        |
|           If LLM fails                   |
|                 v                        |
|  +------------------------------------+  |
|  |  PaddleOCR Pipeline               |  |  ~220 s on CPU
|  |  (egyptian_id_ocr.py)             |  |
|  |  Zone OCR -> field extraction     |  |
|  +------------------------------------+  |
+------------------------------------------+
```

---

## How the Two-Pass LLM Strategy Works

### Pass 1 — Full Card (all 6 fields)

1. **Load image** and apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to reduce uneven lighting and shadows.
2. **Resize** to at most 1280 px wide to save API tokens while keeping all text readable.
3. **Encode as JPEG bytes** and send to the LLM with a detailed structured prompt.
4. The prompt:
   - Describes the physical layout of a modern Egyptian NID card
   - Explicitly explains the **two-line name layout**: top line = first/given name, bottom line = remaining names
   - Gives the exact 14-digit NID structure: `[C][YY][MM][DD][GG][SSSS][X]`
   - Provides a correct JSON example using 14-digit Arabic-Indic NID
   - Shows a checkmark example (correct name order) and a cross example (wrong order)
5. **Robust JSON extraction** using `_parse_json()`:
   - Strips all markdown code fences (` ```json ` and ` ``` `)
   - Uses a **balanced-brace walker** (`_extract_first_json_object`) instead of a naive `rfind("}")` — this correctly handles thinking-model preamble that may contain stray `{…}` characters
   - Tries every `{…}` block in document order; returns the first one that parses as a valid non-empty JSON dict

### Pass 2 — NID Strip Zoom (NID only, when Pass 1 misses NID)

1. **Crop** the bottom 38% of the card image (where the 14-digit number lives).
2. **Scale 3×** using Lanczos4 interpolation for sub-pixel sharpness.
3. Apply **morphological background removal + CLAHE + Otsu binarization** to produce high-contrast black digits on white.
4. Ask the LLM for **exactly 14 Arabic-Indic digits and nothing else** (50-token response limit).
5. **Structural validation** before accepting: correct length, starts with `2` or `3`, valid month/day, governorate code in the known set of 35 valid Egyptian governorate codes.

---

## How the PaddleOCR Fallback Works

When all LLM providers fail or return empty data, the full offline pipeline runs using PaddleOCR's Arabic model:

1. **Image type detection** — distinguishes handheld photographs from flatbed scans or screen captures and applies the appropriate preprocessing path.
2. **Preprocessing** — shadow removal, deskew, denoising tailored to the image type.
3. **Zone OCR** — the card is divided into named spatial zones:
   - `name_r`, `name_l` — right/left halves of the name area
   - `nid_r`, `nid_l` — right/left halves of the NID strip
   - `dob`, `address`, `district`, `serial` etc.
4. **Multi-pass scanning** — each zone is scanned multiple times with different scales and binarization settings; results are deduplicated.
5. **Field extraction** — regex and heuristic rules map Arabic OCR tokens to the six structured fields.
6. **NID length correction** — fixes the most common misread patterns: 13-digit reads (one digit swallowed by the security pattern) and 15-digit reads (a digit doubled).

The same NID zone-scan is also used as a **targeted fill-in** when the LLM extracts all other fields successfully but misses just the NID, saving ~200 s compared to running the full PaddleOCR pipeline.

---

## Image Preprocessing

```
Input photo
    |
    +-- CLAHE (clipLimit=2.0, 8x8 tiles)
    |     Removes uneven lighting caused by phone shadow or table reflection
    |
    +-- Resize to <= 1280 px wide
    |     Controls LLM token cost without losing legibility
    |
    +-- JPEG encode at quality 90 -> bytes sent to LLM API

         (NID strip only — Pass 2 and paddle fill-in)
    |
    +-- Crop bottom 38% of card
    +-- Scale 3x (Lanczos4)
    +-- Dilate + divide (morphological background removal)
    +-- CLAHE (clipLimit=4.0, 4x4 tiles)
    +-- Otsu binarization -> high-contrast black/white digit image
```

---

## Provider Cascade and Rate Limit Handling

```
Request arrives
    |
    v
Gemini 2.5 Flash  --[429 or 503]--> wait 38s/5s --> retry once
    | (still limited or unavailable)
    v
Gemini 2.0 Flash  --[429 or 503]--> wait + retry
    |
    v
Gemini 2.0 Flash-Lite  --[429 or 503]--> wait + retry
    |
    v
Groq Llama-4-Scout-17B  --[error]--> log and skip
    |
    v  (all providers failed)
PaddleOCR offline pipeline (no API key needed)
```

Approximate free-tier quotas:

| Model | Requests/min | Requests/day |
|---|---|---|
| Gemini 2.5 Flash | 10 | 500 |
| Gemini 2.0 Flash | 15 | 1,500 |
| Gemini 2.0 Flash-Lite | 30 | 1,500 |
| Groq Llama-4-Scout | 30 | 14,400 |

---

## Field Validation and Post-processing

Every extracted value passes through a normalisation pipeline before being returned:

| Field | What the normaliser does |
|---|---|
| **Name** | Removes card header noise words (`جمهورية`, `بطاقة تحقيق`…); normalises all alef variants (أ إ آ ا → ا); requires at least 2 Arabic words |
| **NID** | Must be exactly 14 digits, start with `2` or `3`, have valid month (01–12) and day (01–31), and have a governorate code matching one of the 35 known Egyptian codes — otherwise set to `null` |
| **Date of birth** | Accepts `YYYY/MM/DD` or `DD/MM/YYYY` input; normalises to `YYYY/MM/DD` in Arabic-Indic digits; derives from NID automatically if date field is missing but NID is valid |
| **Address** | Strips trailing district/governorate text that bleeds in from the next field |
| **District** | Basic whitespace and dash cleanup |
| **Card serial** | Converts leading `I` or `L` to `1` (one); converts embedded `O` to `0` (zero) |

---

## Challenges and How We Solved Them

### Challenge 1 — PaddleOCR took ~220 seconds on CPU

**Problem:** The PaddleOCR Arabic model is large. It loads lazily, so the very first request took 3–4 minutes — far beyond the mobile app's timeout.

**Solution:** Switched to a **LLM-first architecture**. Google Gemini 2.5 Flash reads and interprets the card as a vision task in 3–10 seconds. PaddleOCR became an offline fallback that activates only when no API key is configured or all providers fail.

---

### Challenge 2 — First-request connection timeout

**Problem:** Even after adding the LLM path, the Flutter app timed out with a 10-second connect timeout before the server had finished warming up.

**Solution:**
- Added model pre-warm at server startup (PaddleOCR-only mode)
- Increased Flutter `connectTimeout` to 20 s and `receiveTimeout` to 5 min
- Changed Flask to `threaded=True` so health-check requests are never blocked by a long OCR job running on another thread

---

### Challenge 3 — Egyptian NID two-line name layout

**Problem:** The full name on an Egyptian NID is printed across two separate physical lines: the first name alone on the top line, and all remaining names on the bottom line. LLMs consistently returned only one line or reversed the order.

**Solution:** The prompt now explicitly describes the layout, shows a correct example with the first name first, and shows a wrong example with the first name last. This alone resolved the ordering issue for Gemini models.

---

### Challenge 4 — Thinking-model JSON parse failure

**Problem:** Gemini 2.5 Flash is a thinking model. Before producing the final answer it internally reasons step by step. This reasoning text often contained `{…}` objects written in Arabic prose (e.g. discussing JSON structure). Our original parser used `rfind("}")` to find the JSON end-boundary, which latched onto the last `}` in the thinking preamble rather than the actual JSON output.

**Solution:** Replaced `rfind("}")` with `_extract_first_json_object()`, a **balanced-brace walker** that:
- Iterates through the text character by character, tracking `{` / `}` depth and skipping content inside quoted strings
- Returns the first fully balanced `{…}` block
- Calls `json.loads()` on it; if it fails (thinking content uses unquoted Arabic keys), advances past that block and tries the next one
- Returns the first block that parses as a valid JSON dict

---

### Challenge 5 — LLM hallucinating wrong-length NIDs

**Problem:** Groq's Llama model returned 17-digit NIDs for some images — essentially a confabulation of the correct digits with a few extras.

**Solution:** Strict structural validation in `_normalise_nid()`:
- Exactly 14 digits
- First digit must be `2` or `3`
- Positions 3–4 (birth month) must be 01–12
- Positions 5–6 (birth day) must be 01–31
- Positions 7–8 (governorate) must match one of the 35 valid Egyptian governorate codes

Any NID failing these checks is discarded and Pass 2 / PaddleOCR fill-in is attempted.

---

### Challenge 6 — Address and district field bleed

**Problem:** Vision LLMs sometimes appended the district text at the end of the address field because the two fields are physically adjacent on the card.

**Solution:** `_normalise_address()` checks whether the address string ends with any word or phrase from the district field and strips that suffix, so the two fields stay separated.

---

### Challenge 7 — Card serial character confusion

**Problem:** Both LLMs and PaddleOCR regularly confused `I` (capital i) for `1` (one) and `O` (capital oh) for `0` (zero) in the alphanumeric card serial number.

**Solution:** `_normalise_serial()` applies deterministic corrections:
- Leading `I` or `L` → `1`
- Embedded `O` → `0` in the digit portion

---

### Challenge 8 — Missing date of birth

**Problem:** LLMs sometimes extracted the NID correctly but returned `null` for the date of birth because the printed date was partially obscured or the model missed it.

**Solution:** The 14-digit Egyptian NID directly encodes the birth date at positions 1–6: `[C][YY][MM][DD]`. When the date field is null but the NID is valid, the pipeline derives and formats the date automatically with no additional API call.

---

### Challenge 9 — Gemini free-tier rate limits

**Problem:** The free Gemini API has per-minute and per-day quotas. Heavy test sessions exhausted all three model quotas simultaneously.

**Solution:** Three-level defence:
1. On 429 or 503: wait (38 s for quota, 5 s for overload), retry once, then cascade to the cheaper model
2. After all three Gemini models fail: cascade to Groq (much higher free-tier quota: ~14,400 req/day)
3. If Groq also fails: run PaddleOCR offline (no internet required, works indefinitely)

---

## Limitations

| Limitation | Details |
|---|---|
| **Free API daily quotas** | Free Gemini tier: ~500–1,500 requests/day. Production deployments should use a paid key or a self-hosted open-source model. |
| **Pre-2008 card layouts** | The zone coordinates and field positions differ on older Egyptian NIDs (before the current biometric card format). The pipeline is tuned for modern cards only. |
| **Very poor image quality** | Images with severe glare, extreme motion blur, or less than ~30% of the card visible may produce partial results or fail entirely. |
| **Groq Arabic accuracy** | Groq's Llama model is noticeably weaker on Arabic than Gemini; name word order errors and NID misreads are more common when falling back to Groq. |
| **No GPU acceleration (PaddleOCR)** | The offline fallback runs on CPU in the current setup (~220 s). With a GPU, PaddleOCR drops to ~5 s. |
| **Physical device LAN IP** | The Flutter API URL (`10.0.2.2` for emulator) must be changed to the server's LAN IP for real-device testing. |

---

## Future Plans

### Short-term

- [ ] **Fine-tune a small vision model on Egyptian NID images** — a LoRA adapter on a compact model would eliminate API dependency entirely and reduce latency below 1 s.
- [ ] **GPU-accelerated PaddleOCR** — switching to `paddlepaddle-gpu` reduces the offline fallback from ~220 s to ~5 s.
- [ ] **Confidence scoring** — expose per-field confidence in the API response so the Flutter UI can highlight fields needing manual correction more precisely.
- [ ] **Card front/back detection** — automatically reject back-of-card photos before sending to OCR, saving a round-trip.

### Medium-term

- [ ] **On-device ML (TFLite / ONNX)** — deploy a quantised model directly inside the Flutter app, eliminating the separate Python server entirely.
- [ ] **NID checksum validation** — the 14th digit is a check digit. Implementing the checksum algorithm allows detecting OCR errors that produce structurally plausible but mathematically wrong NIDs.
- [ ] **Multi-card type support** — extend to Egyptian driving licences, passports, and vehicle registration cards using the same LLM-vision approach with card-type-specific prompts.
- [ ] **Passport MRZ parsing** — the machine-readable zone at the bottom of a passport can be decoded deterministically without any LLM.

### Long-term

- [ ] **Liveness detection** — verify that a physical card is present (not a photo of a photo or a digital mockup) to prevent identity fraud at registration.
- [ ] **Arabic handwriting recognition** — a small number of older cards have handwritten field values; a separate handwriting model can handle these cases.
- [ ] **Federated model improvement** — collect anonymised failure cases (with explicit user consent) to continuously retrain the local model without ever sending raw ID images to a third-party server.

---

## Running the Server

### Prerequisites

```bash
cd "OCR 2/OCR"
pip install flask flask-cors paddlepaddle paddleocr opencv-python-headless numpy \
            python-dotenv google-genai groq
```

### Configure API keys (optional but highly recommended)

Create a file named `.env` inside `OCR 2/OCR/` — **do not commit this file**:

```
# Gemini (recommended — best Arabic vision, free at aistudio.google.com/apikey)
GOOGLE_API_KEY=your_google_api_key_here

# Groq (fast fallback — generous free tier at console.groq.com)
GROQ_API_KEY=your_groq_api_key_here
```

Without any key the server falls back to PaddleOCR (offline, ~220 s per request, no internet required).

### Start

```bash
python flask_api.py
```

Expected startup output:

```
INFO  [-]  LLM extraction ENABLED -- primary provider: Gemini
INFO  [-]  Starting NID OCR API on 0.0.0.0:5001
 * Running on http://127.0.0.1:5001
 * Running on http://192.168.x.x:5001
```

### Verify

```bash
curl http://localhost:5001/health
# {"status": "ok", "service": "nid-ocr"}

curl http://localhost:5001/status
# {"llm_enabled": true, "llm_provider": "gemini-2.5-flash", ...}
```

---

## API Reference

### POST /ocr/extract

**Request:** `multipart/form-data`, field `image` (JPG, PNG, WEBP, or BMP; max 15 MB)

**Success response (200):**

```json
{
  "success": true,
  "data": {
    "الاسم بالكامل":      "باسل اشرف عبدالعزيز محمد حسنين",
    "الرقم القومي":       "٣٠١١٠٢١٠١٠٤٧٢٩",
    "تاريخ الميلاد":     "٢٠٠١/١٠/٢١",
    "العنوان بالكامل":    "٧ ش منصور عطفة رامز لاظوغلى",
    "المنطقة والمحافظة": "السيدة زينب القاهرة",
    "رقم البطاقة":       "1M4729408"
  },
  "extracted_count": 6,
  "total_fields": 6,
  "method": "gemini",
  "request_id": "fdc504bd"
}
```

`method` values: `gemini`, `groq`, `gemini+paddle_nid`, `groq+paddle_nid`, `paddle`

Unreadable fields are returned as `null` (never omitted).

**Error response (400 / 413 / 500):**

```json
{
  "success": false,
  "error": "human-readable error message",
  "request_id": "fdc504bd"
}
```

### GET /health

```json
{"status": "ok", "service": "nid-ocr"}
```

### GET /status

```json
{
  "llm_enabled": true,
  "llm_provider": "gemini-2.5-flash",
  "paddle_ready": false,
  "expected_latency": "3-15 s",
  "max_upload_mb": 15
}
```
