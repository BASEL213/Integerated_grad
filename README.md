# Findoor — Government Housing Portal

A Flutter mobile application for Egypt's government housing services, featuring an AI-powered Egyptian National ID (NID) scanner that auto-fills registration forms using OCR and a built-in Arabic AI chatbot.

---

## Project Structure

```
FinalGRAD-mobile/
├── lib/                              # Flutter source code
│   ├── core/                         # Theme, app entry point
│   └── features/
│       ├── auth/                     # Login, Register, Forgot Password
│       ├── home/                     # Home, Profile, Documents Vault
│       │   └── nid_scan_screen.dart  # NID OCR scanner screen
│       └── splash/
├── android/                          # Android configuration
├── ios/                              # iOS configuration
├── OCR 2/
│   └── OCR/
│       ├── flask_api.py              # REST API (Flask)
│       ├── llm_extractor.py          # Two-pass LLM extraction engine
│       ├── egyptian_id_ocr.py        # PaddleOCR offline fallback
│       ├── enhance.py                # Image preprocessing utilities
│       ├── TECHNICAL.md              # Deep-dive: how the OCR works
│       └── tests/                    # Sample NID images for testing
└── arabic LLM FINAL/                 # Arabic AI chatbot backend
```

> **OCR technical documentation:** [`OCR 2/OCR/TECHNICAL.md`](OCR%202/OCR/TECHNICAL.md)
> Covers the two-pass LLM architecture, all challenges faced, how they were solved, and future improvement plans.

---

## Prerequisites

| Tool | Version |
|---|---|
| Flutter | 3.x stable |
| Dart | 3.x |
| Python | 3.9 – 3.13 |
| pip | latest |
| Android Studio / emulator | Any recent version |

---

## Step 1 — Run the OCR API Server

The Flutter app sends card images to a local Flask server for processing.
**Start this before launching the app.**

### Install dependencies

```bash
cd "OCR 2/OCR"
pip install flask flask-cors paddlepaddle paddleocr opencv-python-headless numpy \
            python-dotenv google-genai groq
```

### Configure API keys (recommended for fast mode)

Create `OCR 2/OCR/.env` — **never commit this file**:

```
# Gemini key (best Arabic OCR, free at aistudio.google.com/apikey)
GOOGLE_API_KEY=your_google_api_key_here

# Groq key (fast fallback, free at console.groq.com)
GROQ_API_KEY=your_groq_api_key_here
```

Without keys the server uses PaddleOCR (~220 s per request, fully offline).

### Start

```bash
cd "OCR 2/OCR"
python flask_api.py
```

Expected output:

```
INFO  LLM extraction ENABLED -- primary provider: Gemini
INFO  Starting NID OCR API on 0.0.0.0:5001
 * Running on http://127.0.0.1:5001
 * Running on http://192.168.x.x:5001
```

### Verify

```bash
curl http://localhost:5001/health
# {"status": "ok", "service": "nid-ocr"}
```

---

## Step 2 — Configure the API URL in Flutter

Open [`lib/features/home/nid_scan_screen.dart`](lib/features/home/nid_scan_screen.dart) and find:

```dart
String get _apiBase =>
    kIsWeb ? 'http://localhost:5001' : 'http://10.0.2.2:5001';
```

| Target | URL |
|---|---|
| Chrome (web) | `http://localhost:5001` — already set |
| Android emulator | `http://10.0.2.2:5001` — already set |
| Physical Android device | Change to your machine's LAN IP e.g. `http://192.168.1.x:5001` |

To find your LAN IP on Windows: run `ipconfig` and look for **IPv4 Address**.

---

## Step 3 — Run the Flutter App

```bash
flutter pub get
flutter run            # Android emulator
flutter run -d chrome  # Chrome
```

---

## Step 4 — Using the NID Scanner

1. Open the app and tap **Create Account**
2. Tap **"Scan NID to auto-fill"**
3. Choose a clear photo of your NID card from the gallery
4. Review the extracted fields; correct any mistakes
5. Tap **Confirm** — Full Name, National ID, and other fields are auto-filled

### Tips for best results

- Place the card on a flat, dark surface
- Use good even lighting — avoid glare and shadows
- Hold the camera directly above the card, parallel to it
- Make sure the entire card is visible in the frame

---

## OCR Performance

| Mode | Speed | Internet Required |
|---|---|---|
| LLM (Gemini 2.5 Flash) | **~5–15 s** | Yes (free API key) |
| LLM (Groq fallback) | ~10–20 s | Yes (free API key) |
| PaddleOCR (offline) | ~220 s on CPU | No |

The server automatically selects the best available provider.

---

## OCR API Reference

**Base URL:** `http://localhost:5001`

### POST /ocr/extract

**Request:** `multipart/form-data`, field `image` (JPG, PNG, WEBP, or BMP; max 15 MB)

**Success response:**

```json
{
  "success": true,
  "extracted_count": 6,
  "total_fields": 6,
  "method": "gemini",
  "request_id": "fdc504bd",
  "data": {
  }
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
  "expected_latency": "3-15 s",
  "max_upload_mb": 15
}
```

---

## Design Reference

| Token | Value |
|---|---|
| Primary color | `#1E88E5` |
| Dark variant | `#1565C0` |
| Background | `#F8FAFC` |
| Font | Google Fonts — Poppins |
