# Egyptian National ID OCR

Extracts 6 fields from Egyptian national ID card photos using PaddleOCR (Arabic deep-learning model) with a multi-pass pipeline and a Groq Vision LLM fallback for hard cases.

---

## Extracted Fields

| Arabic key | Field | Example |
|---|---|---|
| الاسم بالكامل | Full name |   |
| الرقم القومي | National ID (14 digits) |  |
| تاريخ الميلاد | Date of birth |  |
| العنوان بالكامل | Street address |  |
| المنطقة والمحافظة | District & governorate | |
| رقم البطاقة | Card serial number |  |

---

## Setup

```bash
pip install paddlepaddle paddleocr opencv-python python-dotenv groq

# Copy the env template and add your free Groq API key
cp .env.example .env
# Edit .env → GROQ_API_KEY=gsk_...
```

Arabic OCR models (~50 MB) download automatically on first run and cache to `~/.paddlex/`.  
No GPU required — runs on CPU.

### Groq API key (free)
Sign up at **console.groq.com** → create an API key → paste it in `.env`.  
The key is only used as a fallback when PaddleOCR fails. Without it the system still works, just with lower accuracy on difficult images.

---

## Usage

```bash
# Single image
python egyptian_id_ocr.py tests/id_photo.jpg

# As a Python module
from egyptian_id_ocr import extract_id_fields
result = extract_id_fields("id_photo.jpg", verbose=False)
```

```python
# Output

```

---

## How It Works

### 1 — Preprocessing

Every input image goes through:

| Step | What it does |
|---|---|
| `detect_image_type()` | Decides if the image is a raw phone photo or an already-enhanced scan |
| `_auto_gamma()` | Fixes exposure for very dark or washed-out photos |
| `_deblur()` | Unsharp mask for motion-blurred shots (Laplacian variance < 25) |
| `_deskew()` | Corrects small camera tilt via HoughLinesP |
| `_try_rotations()` | Tests all four 90° orientations, picks the one matching the card aspect ratio |
| `_perspective_warp()` | Detects card corners and warps the card to a fixed 1200 × 757 px canvas |
| `_shadow_remove()` | "Magic color" filter: dilates the L channel to estimate the background, divides it out, then CLAHE — produces white background with vivid text regardless of lighting |
| `_sharpen()` | Unsharp mask for final crispness |

### 2 — OCR Passes

The pipeline runs OCR passes only as needed. Best case = 1 call, worst case = 5.

```
P1  Always         — full 1200×757 card, shadow-removed
P2a If NID missing — NID strip split into right+left halves at 3× upscale
P2b If still missing — full NID zone, adaptive binary threshold
P2c If still missing — NID halves with HSV saturation mask (black ink isolation)
P2d If still missing — wider bottom zone at 3× (last resort)
P3  If name missing AND P1 had fewer than 4 name-zone word tokens
```

**Why split the NID zone in P2a?**  
PaddleOCR crashes on images wider than ~2400 px. The full NID strip on a 1200 px card is ~1140 px wide, so the maximum safe upscale is 2×. Splitting into two ~660 px half-zones allows genuine 3× upscaling, which significantly improves digit recognition.

**Why the HSV saturation mask (P2c)?**  
Egyptian ID cards have a colorful geometric security background. Black ink has near-zero saturation (S < 100) and low brightness (V < 130). Masking everything else to white isolates the printed text from the pattern without relying on global thresholds that the pattern defeats.

### 3 — Field Extraction

OCR tokens are classified by:
- **y position** — name is in 15–52% of card height, NID/date/serial in the bottom 40%
- **content** — digit strings → NID candidates; address keywords → address; district keywords → district; pure Arabic in name zone → name
- **NID structural validation** — must be 14 digits, start with 2 or 3, contain a valid date (YYMMDD) and a valid governorate code (01–27 or 88)

If OCR produces a 13- or 15-digit NID, `_nid_length_fix()` tries all single-digit insertions/deletions to recover a valid 14-digit number.

NID date and governorate are derived automatically from a valid NID when OCR does not separately find them.

### 4 — Groq Vision Fallback

If PaddleOCR cannot produce a structurally valid NID or a plausible name after all passes, the bottom half of the card is sent to **LLaMA 3.2-11B Vision** via Groq's free API. The model reads with full visual context and Arabic number awareness. The response is validated against the NID structure before being accepted.

---

## Current Accuracy (test suite — 11 images, 2 skipped)

**3 / 9 passing — 33%**

| Image | Name | NID | Address | District | Card | Status |
|---|---|---|---|---|---|---|
| 150055.png | ✓ | ✗ wrong digits | ✓ | ✓ | ✓ | **FAIL** |
| 161241.png | ✓ | ✗ wrong digits | ✓ | ✓ | ✓ | **FAIL** |
| 161807.png | ✓ | ✗ missing | ✗ | ✓ | — | **FAIL** |
| 162529.png | ✓ | ✓~ (13/14) | ✓ | ✓ | ✓ | **PASS** |
| 162642.png | ✓ | ✓~ (13/14) | ✓ | ✓ | ✓ | **PASS** |
| 162855.png | ✓ | ✗ wrong digits | ✗ | ✓ | — | **FAIL** |
| WhatsApp AM.jpeg | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| WhatsApp AM 57.jpeg | ✓~ | ✗ wrong | — | — | ✗ | **FAIL** |
| Test_image.jpeg (old card, rotated) | ✓ | ✗ wrong | — | — | ✓ | **FAIL** |

---

## Known Limitations

### 1. NID digit misreads — the main failure mode

The four failing NID cases (150055, 161241, 162855, WhatsApp AM 57) share a pattern: the OCR extracts a **structurally valid** 14-digit NID (valid century digit, valid date, valid governorate code) but the digits themselves are wrong. This means:

- The NID zone is found correctly — it is not a localization problem
- Structural validation cannot reject or correct the result because it accidentally passes
- The root cause is the Arabic OCR model confusing visually similar digits:  
  `٠` ↔ `٦`, `١` ↔ `٧`, `٣` ↔ `٢`, etc., especially against the security background pattern

### 2. NID completely missing — 161807

All five OCR passes (including the HSV saturation mask) produce no digit tokens in the NID zone for this image. The security background on this particular card variant completely overwhelms the digit contrast. The Groq fallback would help here but requires the API key to be set.

### 3. Old card layout — Test_image.jpeg

The pre-2008 Egyptian ID card design has a different field layout. The NID appears at a different position and the card has a portrait aspect ratio when rotated. The current hardcoded zone fractions (`_ZONES`) are tuned for the post-2008 landscape card only. The old card reads a partial digit string from the card serial position and reports it as the NID.

### 4. Heavily degraded / glare-covered images — WhatsApp AM 57

This image appears to have glare or severe image quality issues that cause the perspective correction to misalign the zones. The name and NID both land at unexpected positions relative to the hardcoded zone fractions.

### 5. Address extraction is brittle

Address tokens are identified by a keyword list (`_ADDR_KW`). Any address without a recognized street-type keyword (شارع, ميدان, عطفة, etc.) falls through to the name zone and may be misclassified. The current approach also produces occasional double-counting of address components.

---

## What Needs to Be Improved

### High priority — accuracy

| Problem | Recommended fix |
|---|---|
| NID digit misreads on patterned backgrounds | Fine-tune `arabic_PP-OCRv5_mobile_rec` on ~100 Egyptian ID card digit-strip crops with labeled ground truth. This directly attacks the root cause. |
| NID missing on some cards (161807) | The Groq Vision fallback handles this automatically once `GROQ_API_KEY` is set in `.env`. |
| Old card layout (pre-2008) | Add a second `_ZONES_OLD` mapping and a card-generation detector (heuristic: check if the card header text is positioned differently, or use the card serial format as a signal). |

### Medium priority — robustness

| Problem | Recommended fix |
|---|---|
| Hardcoded zone fractions break for unusual crops/zooms | Train a lightweight YOLO-nano model on 20–30 labeled cards to detect field bounding boxes dynamically instead of using fixed fractions. This also handles old/new card variants automatically. |
| Address keyword list misses uncommon street types | Expand `_ADDR_KW` from a static list to a broader set, or use a district/address classifier trained on Egyptian address text. |
| OCR non-determinism (results vary between runs) | Run PaddleOCR multiple times on the NID zone and take a majority vote across runs. 3 runs typically converge. |

### Low priority — quality of life

| Problem | Recommended fix |
|---|---|
| No image quality pre-flight | Add blur detection (Laplacian variance), glare detection (large near-white regions), and tilt detection before running OCR. Reject or warn on images that will certainly fail. |
| `تاريخ الميلاد` derived, not directly read | Most cards print the date clearly. Add a dedicated date-zone OCR pass to read it directly instead of always deriving from NID. |
| Speed: up to 5 OCR passes on hard images | Most of the time is spent in PaddleOCR's model inference. Switch to `PP-OCRv5_server` for NID zones only (higher accuracy, same speed on small crops) while keeping `mobile` for full-image P1. |

---

## Files

```
OCR/
├── egyptian_id_ocr.py   Main pipeline — preprocessing, OCR passes, field extraction, Groq fallback
├── test_ocr.py          Test runner — 11 ground-truth images, fuzzy field matching
├── enhance.py           Standalone preprocessing utilities (used during development)
├── app.py               CLI / API entry point
├── camscanner.ipynb     Notebook exploring the shadow-removal preprocessing
├── .env                 Your API keys (not committed)
├── .env.example         Key template (safe to commit)
├── .gitignore
├── tests/               Test images
└── venv/                Python virtual environment
```

---

## Photo Tips for Best Results

- **Hold the camera directly above the card** — even a 20° angle distorts glyph shapes
- **Even, diffuse lighting** — avoid direct flash (creates glare on the holographic strip) and avoid shadows across the text zones
- **Card fills 70–80% of the frame** — too far = low resolution, too close = edge clipping
- **Keep the card flat** — on a table, not held in hand
- **Avoid the NID strip glare** — the bottom strip has a reflective laminate; tilt the light source slightly
