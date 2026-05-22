# Findoor — Government Housing Portal

A Flutter mobile application for Egypt's government housing services, featuring an AI-powered Egyptian National ID (NID) scanner that auto-fills registration forms using OCR.

---

## Project Structure

```
FinalGRAD-mobile/
├── lib/                        # Flutter source code
│   ├── core/                   # Theme, app entry
│   └── features/
│       ├── auth/               # Login, Register, Forgot Password
│       ├── home/               # Home, Profile, Documents Vault
│       │   └── nid_scan_screen.dart   # NID OCR scanner screen
│       └── splash/
├── android/                    # Android config & permissions
├── OCR 2/
│   └── OCR/
│       ├── egyptian_id_ocr.py  # Core OCR pipeline (PaddleOCR)
│       ├── flask_api.py        # REST API wrapping the OCR
│       ├── enhance.py          # Image preprocessing
│       └── app.py              # Gradio UI (for standalone testing)
└── arabic LLM FINAL/           # AI chatbot backend
```

---

## Prerequisites

| Tool | Version |
|---|---|
| Flutter | 3.x stable |
| Dart | 3.x |
| Python | 3.9 – 3.11 |
| pip | latest |
| Android Studio / emulator | Any recent version |

---

## Step 1 — Run the OCR API Server

The Flutter app sends card images to a local Flask server for OCR processing.
**Start this before launching the app.**

### Install Python dependencies

```bash
cd "OCR 2/OCR"
pip install flask flask-cors paddlepaddle paddleocr opencv-python-headless numpy python-dotenv
```

> If you have a GPU, install `paddlepaddle-gpu` instead of `paddlepaddle`.

### (Optional) Enable the Groq Vision fallback

Create a file named `.env` inside `OCR 2/OCR/`:

```
GROQ_API_KEY=your_groq_api_key_here
```

This enables a Groq Vision LLM fallback for images where PaddleOCR fails to extract all fields.

### Start the server

```bash
cd "OCR 2/OCR"
python flask_api.py
```

Expected output:

```
INFO  Starting NID OCR API on 0.0.0.0:5001
 * Running on http://127.0.0.1:5001
 * Running on http://192.168.x.x:5001
```

### Verify it is running

```bash
curl http://localhost:5001/health
```

Expected response:

```json
{ "status": "ok", "service": "nid-ocr" }
```

---

## Step 2 — Configure the API URL in Flutter

Open `lib/features/home/nid_scan_screen.dart` and find this near the top:

```dart
String get _apiBase =>
    kIsWeb ? 'http://localhost:5001' : 'http://10.0.2.2:5001';
```

| Target | URL |
|---|---|
| Chrome (web) | `http://localhost:5001` — already set |
| Android emulator | `http://10.0.2.2:5001` — already set |
| Physical Android device | Change to your machine's LAN IP e.g. `http://192.168.1.x:5001` |

To find your machine's LAN IP on Windows:

```cmd
ipconfig
```

Look for **IPv4 Address** under your active network adapter.

---

## Step 3 — Run the Flutter App

### Install Flutter dependencies

```bash
flutter pub get
```

### Android emulator

```bash
flutter run
```

### Chrome (web)

```bash
flutter run -d chrome --web-port 8080
```

### Physical Android device

1. Enable **Developer Options** and **USB Debugging** on your phone
2. Connect via USB
3. Run:

```bash
flutter devices        # confirm your device appears
flutter run
```

---

## Step 4 — Using the NID Scanner

### From the Registration screen

1. Open the app and tap **Create Account**
2. Tap **"Scan NID to auto-fill Name & ID"** below the National ID field
3. Choose **Capture with Camera** or **Upload from Gallery**
4. If using camera: align your NID card inside the blue frame and tap the capture button
5. Review extracted fields, correct any mistakes, then tap **Confirm**
6. Full Name and National ID are automatically filled in the form

### From the Documents Vault

1. Navigate to **Documents Vault** from the home screen
2. Expand **National ID (Front)**
3. Tap **Scan / Upload**
4. Choose **Scan with NID Scanner** or **Upload from Gallery**

---

## OCR API Reference

**Base URL:** `http://localhost:5001`

### `GET /health`

```json
{ "status": "ok", "service": "nid-ocr" }
```

### `POST /ocr/extract`

Extracts all fields from an Egyptian National ID image.

**Request:** `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `image` | file | JPG, PNG, WEBP, or BMP photo of the NID |

**Success response:**

```json
{
  "success": true,
  "extracted_count": 5,
  "total_fields": 6,
  "data": {
    "الاسم بالكامل":      "اشرف عبدالعزيز محمد حسنين",
    "الرقم القومي":       "26608310100397",
    "تاريخ الميلاد":     "1966/08/31",
    "العنوان بالكامل":    "17 ش منصور عطفة رامز لاظوغلى",
    "المنطقة والمحافظة": "السيدة زينب القاهرة",
    "رقم البطاقة":       "KP1547505"
  }
}
```

**Error response:**

```json
{
  "success": false,
  "error": "OCR processing error: ..."
}
```

---

## Tips for Best OCR Results

- Place the card on a **flat, dark surface**
- Use **good lighting** — avoid glare and shadows
- Hold the phone **directly above** the card, parallel to it
- Make sure the **entire card fits inside the frame** before shooting
- If fewer than 4 fields are detected, retake in better lighting

---

## Known Limitations

| Issue | Details |
|---|---|
| Digit confusion | OCR occasionally confuses `٠↔٦`, `١↔٧` on security-pattern backgrounds |
| Old card layouts (pre-2008) | Zone coordinates are tuned for modern cards only |
| Physical device URL | Must be updated manually to your machine's LAN IP (see Step 2) |
| Camera on web | Works via browser camera API; overlay animations are smoother on native mobile |

---

## App Design

| Role | Value |
|---|---|
| Primary color | `#1E88E5` |
| Dark variant | `#1565C0` |
| Background | `#F8FAFC` |
| Font | Google Fonts — Poppins |
