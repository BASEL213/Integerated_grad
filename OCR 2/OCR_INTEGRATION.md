# Egyptian NID OCR — Integration Notes

## What Was Built

### 1. Flask REST API (`OCR 2/OCR/flask_api.py`)
A thin production-ready REST wrapper around the existing `extract_id_fields()` pipeline.

| Detail | Value |
|---|---|
| Default port | `5001` |
| Bind address | `0.0.0.0` (reachable from phone on same network) |
| Health check | `GET /health` |
| OCR endpoint | `POST /ocr/extract` |
| Input | `multipart/form-data`, field name: `image` |
| Accepted formats | `jpg`, `jpeg`, `png`, `webp`, `bmp` |
| Response (success) | `{ success: true, data: { Arabic fields }, extracted_count, total_fields }` |
| Response (error) | `{ success: false, error: "..." }` |

**To start the server:**
```bash
cd "OCR 2/OCR"
python flask_api.py
```

**Optional dependency** — install `flask-cors` for cross-origin support:
```bash
pip install flask flask-cors
```

---

### 2. NID Scanner Screen (`lib/features/home/nid_scan_screen.dart`)
A full-featured Flutter screen with two acquisition modes and a guided review flow.

#### Screen states
```
options → camera (or gallery) → processing → results → [confirm / retry]
                                           ↘ failed  → [retry / skip]
```

#### Camera mode features
- Full-screen live camera preview via the `camera` Flutter package
- **NID guide frame** — dark overlay with a transparent cutout sized to the ISO 7810 ID-1 card ratio (85.6 × 54 mm → 1.586:1). This forces the user to frame the card correctly before shooting.
- **Animated corner brackets** — pulse from white to primary blue (#1E88E5) on a 1.4 s loop, giving a "live scanning" feel.
- **Scan line animation** — a gradient blue line sweeps top-to-bottom inside the frame every 2 s.
- **Tip cycling** — 5 contextual tips ("Hold steady", "Avoid shadows", etc.) fade-slide every 2 s below the frame.
- Quick access to gallery upload from inside the camera view.

#### Gallery mode
Uses `image_picker` (already a project dependency) — no extra permission needed.

#### Results page
- Shows all 6 extracted fields in editable `TextFormField` widgets.
- Fields not detected are highlighted in orange with a "Not detected" badge.
- Quality badge shows `X/6 fields detected` with a percentage.
- User can correct any field before confirming.
- Returns a `Map<String, String>` to the caller on confirm.

#### Error page
- Explains what went wrong (permission denied, server unreachable, zero fields extracted).
- "Tips for a better scan" panel with actionable advice.
- Two exits: **Try Again** (back to options) or **Skip & Fill Manually** (pop without data).

---

### 3. Registration Screen (`lib/features/auth/register_screen.dart`)
Added a **"Scan NID to auto-fill Name & ID"** button between the National ID field and the Phone Number field.

- Tapping it navigates to `NIDScanScreen`.
- On return, populates **Full Name** and **National ID** controllers automatically.
- Button turns green with a checkmark after a successful scan; tapping again allows re-scanning.

---

### 4. Documents Vault Screen (`lib/features/home/documents_vault_screen.dart`)
NID documents (`National ID (Front)`, `National ID (Back)`) now show a **"Scan / Upload"** button instead of the plain "Upload Now".

Tapping it opens a bottom sheet with:
- **Scan with NID Scanner** — navigates to `NIDScanScreen` (front side only; back side has no extractable text so OCR is skipped).
- **Upload from Gallery** — existing flow unchanged.

---

### 5. `pubspec.yaml` — new dependency
```yaml
camera: ^0.11.0+2
```
Run `flutter pub get` after pulling this change.

---

### 6. `android/app/src/main/AndroidManifest.xml` — new permissions
```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-feature android:name="android.hardware.camera" android:required="false" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"
    android:maxSdkVersion="32" />
<uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
```

---

## API Server IP — Developer Note
Inside `nid_scan_screen.dart`, the API base URL is:
```dart
const String _apiBase = 'http://10.0.2.2:5001';
```
`10.0.2.2` is Android emulator's alias for the host machine's `localhost`.  
**For a real physical device**, change this to your machine's LAN IP, e.g.:
```dart
const String _apiBase = 'http://192.168.1.x:5001';
```

---

## Known Challenges & Limitations

### OCR Accuracy (existing, not introduced by this integration)

| Challenge | Root Cause | Severity |
|---|---|---|
| NID digit confusion (`٠↔٦`, `١↔٧`, `٣↔٢`) | Arabic digit OCR on security-pattern backgrounds is noisy | High |
| Missing NID on some images | Low contrast between digits and card background; multi-pass helps but doesn't always recover | Medium |
| Structurally valid but wrong NID | PaddleOCR picks a plausible 14-digit string that passes checksum/format rules but has wrong digits | High |
| Older card layouts (pre-2008) | Zone coordinates are hardcoded for modern card; old cards have different field positions | Medium |
| Non-deterministic results | PaddleOCR sampling varies between runs on the same image | Low |

**Recommended fix (long term):** Fine-tune `arabic_PP-OCRv5_mobile_rec` on ~100 labelled Egyptian ID digit crops, or integrate a dedicated digit-recognition step for the NID zone.

### Integration Challenges

| Challenge | How It Was Handled |
|---|---|
| No real-time card detection in the viewfinder | Guide overlay + cycling tips teach the user to frame correctly before shooting. Quality is assessed after capture by checking how many fields were extracted. |
| `camera` package requires runtime permission | `CameraException` with code `CameraAccessDenied` is caught and surfaced as a clear error message with "Try Again". |
| Large image uploads over slow LAN | Dio timeout set to 60 s receive / 30 s send. Gallery picker compresses to `imageQuality: 90`. |
| Arabic field keys in the API response | Dart code reads Arabic Unicode keys directly from the JSON dict (`data['الرقم القومي']`) — no translation layer needed. |
| API unreachable (server not started) | `DioExceptionType.connectionTimeout` and `unknown` are caught; error page shown with "Cannot reach OCR server" message. |
| OCR returns 0 fields (bad photo) | Redirects to the error page instead of showing empty results; instructs the user to retake with better lighting/framing. |
| `TextDirection` of extracted Arabic text | All result `TextFormField` widgets use `textDirection: TextDirection.rtl` so Arabic text renders correctly in the review form. |

### Future Improvements

- **On-device card detection** — A MobileNet-based card corner detector running on each camera frame could drive real-time "Move left", "Too far", "Good — hold still" guidance (requires TFLite integration).
- **Liveness / glare detection** — Reject images with specular highlights before sending to the API, saving round-trip time.
- **Groq Vision fallback** — Set the `GROQ_API_KEY` environment variable on the server to enable the LLM fallback pass for hard images.
- **Offline mode** — Cache the last successful extraction so users can review without re-scanning on poor connectivity.
- **NID back side** — The back of modern Egyptian IDs contains the mother's name and blood type; extending zone maps to cover these would increase the data captured per scan.
