"""
LLM-based Egyptian NID field extractor — production build
==========================================================
Two-pass strategy per request:

  Pass 1 — full card → all 6 fields  (Gemini 2.5 Flash / Groq)
  Pass 2 — NID strip zoom → 14-digit NID only  (if Pass 1 missed it)

Providers  (priority order, set in .env):
  GOOGLE_API_KEY  →  Gemini 2.5 Flash  (best Arabic vision, free tier)
                     https://aistudio.google.com/apikey
  GROQ_API_KEY    →  Llama-4-Scout     (fast fallback, free tier)
                     https://console.groq.com
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_FIELD_KEYS = [
    "الاسم بالكامل",
    "الرقم القومي",
    "تاريخ الميلاد",
    "العنوان بالكامل",
    "المنطقة والمحافظة",
    "رقم البطاقة",
]

_AR2LA = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_LA2AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_ALEF  = re.compile(r"[أإآٱ]")

# Egyptian governorate codes (digits 7-8 of the NID)
_GOV_CODES = {
    "01","02","03","04","11","12","13","14","15","16","17","18","19",
    "21","22","23","24","25","26","27","28","29","31","32","33","34","35","88",
}

# Header noise words that should never appear in the name
_NAME_NOISE = {
    "جمهورية", "مصر", "العربية", "بطاقة", "تحقيق",
    "الشخصية", "بطاقه", "التحقيق",
}

# ── Prompts ───────────────────────────────────────────────────────────────────

_FULL_CARD_PROMPT = """\
You are an expert OCR system for Egyptian National ID cards (بطاقة تحقيق الشخصية).

Examine the ENTIRE card image carefully and extract the 6 fields below.
Return ONLY a valid JSON object — no markdown, no explanation, no code fences.
Use null for any field that is truly unreadable.

━━━ FIELD GUIDE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. "الاسم بالكامل"  — Full name
   ⚠ CRITICAL WORD ORDER — read carefully:
     • The name is split across TWO lines on the card:
         TOP line (upper)    → given / first name ONLY   e.g. "باسل"
         BOTTOM line (lower) → all remaining names        e.g. "اشرف عبدالعزيز محمد حسنين"
     • Output the TOP line word(s) FIRST, then the BOTTOM line words, separated by a single space.
     • ✅ CORRECT: "باسل اشرف عبدالعزيز محمد حسنين"  (first name "باسل" is FIRST)
     • ❌ WRONG:   "اشرف عبدالعزيز محمد حسنين باسل"  (first name at the END is wrong)
   • Ignore the card header lines: "جمهورية مصر العربية" and "بطاقة تحقيق الشخصية"

2. "الرقم القومي"  — 14-digit National ID number
   • Printed in large digits across the bottom strip, full width of the card
   • EXACTLY 14 digits; starts with 2 (born 1900s) or 3 (born 2000s)
   • Structure: [C][YY][MM][DD][GG][SSSS][X]
       C  = century (2 or 3)
       YY = year last 2 digits
       MM = birth month (01-12)
       DD = birth day   (01-31)
       GG = governorate code (01-35 or 88)
       SSSS = 4-digit serial
       X  = check digit
   • ‼ Use Arabic-Indic digits ONLY: ٠١٢٣٤٥٦٧٨٩

3. "تاريخ الميلاد"  — Date of birth
   • Format: YYYY/MM/DD  using Arabic-Indic digits
   • Example: ٢٠٠١/١٠/٢١

4. "العنوان بالكامل"  — Street address
   • Arabic text; usually contains شارع / ش / عطفة / ميدان / طريق
   • Do NOT include district or governorate name here

5. "المنطقة والمحافظة"  — District and governorate
   • Example: السيدة زينب القاهرة
   • Do NOT repeat this in the address field

6. "رقم البطاقة"  — Card serial number
   • Alphanumeric code, bottom-right corner of the card
   • Example: 1M4729408  (starts with digit 1, NOT letter I)

━━━ EXAMPLE OUTPUT (14-digit NID, first name باسل first) ━━━━━━━━━━━━━━━━━━━
{
  "الاسم بالكامل": "باسل اشرف عبدالعزيز محمد حسنين",
  "الرقم القومي": "٣٠١١٠٢١٠١٠٤٧٢٩",
  "تاريخ الميلاد": "٢٠٠١/١٠/٢١",
  "العنوان بالكامل": "٧ ش منصور عطفة رامز لاظوغلى",
  "المنطقة والمحافظة": "السيدة زينب القاهرة",
  "رقم البطاقة": "1M4729408"
}
"""

_NID_ONLY_PROMPT = """\
This is a zoomed image of the bottom strip of an Egyptian National ID card.
Locate the 14-digit national ID number.
Reply with EXACTLY 14 Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩) and nothing else.
No spaces, no punctuation, no explanation — just 14 digits.
"""


# ── Image utilities ───────────────────────────────────────────────────────────

def _to_jpeg(img: np.ndarray, quality: int = 90) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("cv2.imencode failed")
    return buf.tobytes()


def _prep_full_card(image_path: str) -> bytes:
    """
    Load → mild enhancement → resize to ≤1280 wide → JPEG bytes.
    Keeps the image readable while staying within LLM token budgets.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    # Mild shadow removal (LAB L-channel normalization)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    img = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    h, w = img.shape[:2]
    if w > 1280:
        s = 1280 / w
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)

    return _to_jpeg(img)


def _prep_nid_strip(image_path: str) -> bytes:
    """
    Crop the bottom 38% of the card (where the NID lives), scale 3×,
    apply binarisation to maximise digit contrast → JPEG bytes.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    h, w = img.shape[:2]
    strip = img[int(h * 0.60):, :]        # bottom 40%

    # Scale up for clarity
    scale = min(3, max(1, 900 // max(strip.shape[:2])))
    if scale > 1:
        strip = cv2.resize(strip, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_LANCZOS4)

    # Adaptive binarization — removes security-pattern background
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    k    = min(max(21, gray.shape[0] // 8), 51)
    k    = k if k % 2 == 1 else k + 1
    bg   = cv2.dilate(gray, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    norm = cv2.divide(gray, bg, scale=255)
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
    norm = clahe.apply(norm)
    _, binary = cv2.threshold(norm, 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    strip = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    return _to_jpeg(strip, quality=95)


# ── JSON / text parsing ───────────────────────────────────────────────────────

def _extract_first_json_object(text: str) -> str | None:
    """
    Walk *text* and return the substring of the first balanced {…} block.
    Properly handles nested objects, string values (incl. escaped quotes).
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_json(raw: str) -> dict | None:
    """
    Robust JSON extraction that survives:
    - Markdown code fences (```json … ```)
    - Thinking-model preamble text containing stray { } characters
    - Leading / trailing prose
    - Unicode escape sequences

    Strategy: strip fences, then iterate through every balanced {…} block
    in document order and return the first one that parses as a non-empty dict.
    """
    if not raw:
        return None

    # Strip all code-fence markers (opening ``` or ```json and closing ```)
    cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()

    # Try each balanced { } block in order — thinking content typically
    # uses unquoted keys so it won't parse as JSON; the actual JSON will.
    search_from = 0
    while True:
        brace_pos = cleaned.find("{", search_from)
        if brace_pos == -1:
            break
        candidate = _extract_first_json_object(cleaned[brace_pos:])
        if candidate:
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict) and len(obj) >= 1:
                    return obj
            except json.JSONDecodeError:
                pass
            search_from = brace_pos + 1
        else:
            break

    logger.debug("_parse_json: no parseable JSON object found")
    return None


def _parse_nid_digits(raw: str) -> str | None:
    """Extract exactly 14 Arabic-Indic or Western digits from a raw LLM reply."""
    # Convert Western → Arabic-Indic
    raw = raw.translate(_LA2AR)
    # Keep only Arabic-Indic digits
    digits = re.sub(r"[^٠-٩]", "", raw)
    return digits if len(digits) == 14 else None


# ── Field validation & normalisation ─────────────────────────────────────────

def _validate_nid(nid_western: str) -> bool:
    """Structural validation: length, century digit, date part, governorate."""
    if not nid_western or len(nid_western) != 14 or not nid_western.isdigit():
        return False
    if nid_western[0] not in "23":
        return False
    try:
        mo  = int(nid_western[3:5])
        day = int(nid_western[5:7])
    except ValueError:
        return False
    if not (1 <= mo <= 12 and 1 <= day <= 31):
        return False
    return nid_western[7:9] in _GOV_CODES


def _normalise_name(val: str) -> str | None:
    """Clean an Arabic name: remove noise words, normalize alef, tidy spaces."""
    if not val:
        return None
    val = _ALEF.sub("ا", val.strip())
    words = [w for w in val.split() if w not in _NAME_NOISE]
    # Must have ≥ 2 Arabic words
    arabic_words = [w for w in words
                    if sum(1 for c in w if "؀" <= c <= "ۿ") >= 2]
    if len(arabic_words) < 2:
        return None
    return " ".join(words)


def _normalise_nid(val: str) -> str | None:
    """Validate and return a 14-digit Arabic-Indic NID, or None."""
    if not val:
        return None
    # Convert any Western digits to Arabic-Indic, strip non-digits
    ar = val.translate(_LA2AR)
    digits_ar = re.sub(r"[^٠-٩]", "", ar)
    if len(digits_ar) != 14:
        return None
    digits_la = digits_ar.translate(_AR2LA)
    return digits_ar if _validate_nid(digits_la) else None


def _normalise_date(val: str) -> str | None:
    """Parse a date string and return YYYY/MM/DD in Arabic-Indic, or None."""
    if not val:
        return None
    # Normalize to Western digits and separators
    s = re.sub(r"[-.]", "/", val.translate(_AR2LA))
    # Try YYYY/MM/DD
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})$", s.strip())
    if m:
        y, mo, d = m.groups()
        mo, d = mo.zfill(2), d.zfill(2)
        if 1900 <= int(y) <= 2030 and 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"{y}/{mo}/{d}".translate(_LA2AR)
    # Try DD/MM/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", s.strip())
    if m:
        d, mo, y = m.groups()
        mo, d = mo.zfill(2), d.zfill(2)
        if 1900 <= int(y) <= 2030 and 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
            return f"{y}/{mo}/{d}".translate(_LA2AR)
    return None


def _normalise_serial(val: str) -> str | None:
    """Fix common I/O confusion in card serials (e.g. IM → 1M, O → 0)."""
    if not val:
        return None
    val = val.strip()
    # Serial starts with a digit, not a letter — fix leading I or l
    if val and val[0].upper() in ("I", "L"):
        val = "1" + val[1:]
    # Fix embedded O (oh) → 0 (zero) in the digit portion  (first char already handled)
    result = val[0] + val[1:].replace("O", "0").replace("o", "0")
    return result if re.fullmatch(r"[A-Z0-9]{5,12}", result.upper()) else val


def _normalise_address(addr: str | None, district: str | None) -> str | None:
    """
    Strip district/governorate text that bleeds into the address field.
    If the address ends with the district string, remove that suffix.
    """
    if not addr:
        return None
    addr = addr.strip().strip("-").strip()
    if district:
        dist_clean = _ALEF.sub("ا", district.strip())
        # Try to remove trailing occurrence of district (partial or full match)
        for chunk in [dist_clean] + dist_clean.split():
            if len(chunk) < 3:
                continue
            idx = addr.rfind(chunk)
            if idx != -1:
                candidate = addr[:idx].strip().strip("-").strip()
                if candidate:
                    addr = candidate
                    break
    return addr or None


def _post_process(result: dict) -> dict:
    """
    Apply all field-level normalisation and cross-field consistency rules.
    Modifies a copy; never returns None values that were previously valid.
    """
    out = dict(result)

    # Name
    out["الاسم بالكامل"] = _normalise_name(out.get("الاسم بالكامل") or "")

    # NID
    out["الرقم القومي"] = _normalise_nid(out.get("الرقم القومي") or "")

    # Date — derive from NID if LLM got the NID but not the date
    raw_date = _normalise_date(out.get("تاريخ الميلاد") or "")
    if not raw_date:
        nid_ar = out.get("الرقم القومي") or ""
        nid_la = nid_ar.translate(_AR2LA)
        if _validate_nid(nid_la):
            century = "19" if nid_la[0] == "2" else "20"
            y   = century + nid_la[1:3]
            mo  = nid_la[3:5]
            day = nid_la[5:7]
            raw_date = _normalise_date(f"{y}/{mo}/{day}")
    out["تاريخ الميلاد"] = raw_date

    # Address — strip any district bleed
    out["العنوان بالكامل"] = _normalise_address(
        out.get("العنوان بالكامل"),
        out.get("المنطقة والمحافظة"),
    )

    # District — basic cleanup
    dist = (out.get("المنطقة والمحافظة") or "").strip().strip("-").strip()
    out["المنطقة والمحافظة"] = dist or None

    # Card serial
    out["رقم البطاقة"] = _normalise_serial(out.get("رقم البطاقة") or "")

    return out


# ══════════════════════════════════════════════════════════════════════════════
# Provider: Google Gemini
# ══════════════════════════════════════════════════════════════════════════════

_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def _gemini_call(jpeg_bytes: bytes, prompt: str, max_tokens: int = 1500) -> str | None:
    """
    Single Gemini call. Tries each model in _GEMINI_MODELS.
    Rate-limit (429) → cascade to next model.
    Returns raw text or None.

    Note: Gemini 2.5 Flash is a thinking model; it may use several hundred
    tokens for internal reasoning before emitting the JSON.  Use max_tokens ≥
    1500 for the full-card prompt to avoid truncating the JSON response.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
    except Exception as exc:
        logger.warning("Gemini client init failed: %s", exc)
        return None

    for model in _GEMINI_MODELS:
        for attempt in range(2):   # 1 retry per model on rate-limit
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0,
                        max_output_tokens=max_tokens,
                    ),
                )
                return resp.text
            except Exception as exc:
                err = str(exc)
                is_quota  = "429" in err or "RESOURCE_EXHAUSTED" in err
                is_unavail = "503" in err or "UNAVAILABLE" in err
                if (is_quota or is_unavail) and attempt == 0:
                    wait = 38 if is_quota else 5
                    logger.info("Gemini %s %s — waiting %ds …",
                                model, "rate-limited" if is_quota else "unavailable", wait)
                    time.sleep(wait)
                    continue
                if is_quota or is_unavail:
                    logger.warning("Gemini %s still unavailable — trying next model", model)
                    break   # cascade to next model
                logger.warning("Gemini %s error: %s", model, exc)
                break       # non-quota error — try next model

    return None


# ══════════════════════════════════════════════════════════════════════════════
# Provider: Groq
# ══════════════════════════════════════════════════════════════════════════════

_GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def _groq_call(jpeg_bytes: bytes, prompt: str, max_tokens: int = 600) -> str | None:
    """Single Groq vision call. Returns raw text or None."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        from groq import Groq
        b64    = base64.b64encode(jpeg_bytes).decode()
        client = Groq(api_key=api_key)
        resp   = client.chat.completions.create(
            model=_GROQ_MODEL,
            max_tokens=max_tokens,
            temperature=0,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Groq call failed: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Extraction passes
# ══════════════════════════════════════════════════════════════════════════════

def _pass1_all_fields(image_path: str) -> dict | None:
    """
    Pass 1 — send the full card image with the 6-field prompt.
    Returns post-processed dict or None if both providers fail.
    """
    try:
        full_jpeg = _prep_full_card(image_path)
    except Exception as exc:
        logger.error("Pass1: image load error: %s", exc)
        return None

    raw = None

    if os.environ.get("GOOGLE_API_KEY"):
        raw = _gemini_call(full_jpeg, _FULL_CARD_PROMPT, max_tokens=1500)
        if raw:
            logger.debug("Pass1 Gemini raw: %.300s", raw)

    if not raw and os.environ.get("GROQ_API_KEY"):
        raw = _groq_call(full_jpeg, _FULL_CARD_PROMPT, max_tokens=1500)
        if raw:
            logger.debug("Pass1 Groq raw: %.300s", raw)

    if not raw:
        return None

    parsed = _parse_json(raw)
    if not parsed:
        # Log enough to diagnose any future parsing regression
        preview = (raw or "").strip()[:600].replace("\n", " ")
        logger.warning("Pass1: JSON parse failed — raw[0:600]: %s", preview)
        return None

    result = _post_process({k: parsed.get(k) for k in _FIELD_KEYS})
    extracted = sum(1 for v in result.values() if v)
    logger.info("Pass1 extracted %d/6 fields", extracted)
    return result if extracted > 0 else None


def _pass2_nid_only(image_path: str) -> str | None:
    """
    Pass 2 — crop and zoom the NID strip, ask for just the 14-digit number.
    Returns a validated 14-digit Arabic-Indic string or None.
    """
    try:
        strip_jpeg = _prep_nid_strip(image_path)
    except Exception as exc:
        logger.error("Pass2: strip crop error: %s", exc)
        return None

    raw = None

    # 50 tokens: enough for 14 Arabic-Indic digits even on thinking models
    if os.environ.get("GOOGLE_API_KEY"):
        raw = _gemini_call(strip_jpeg, _NID_ONLY_PROMPT, max_tokens=50)
        if raw:
            logger.debug("Pass2 Gemini NID raw: %s", raw.strip())

    if not raw and os.environ.get("GROQ_API_KEY"):
        raw = _groq_call(strip_jpeg, _NID_ONLY_PROMPT, max_tokens=50)
        if raw:
            logger.debug("Pass2 Groq NID raw: %s", raw.strip())

    if not raw:
        return None

    digits_ar = _parse_nid_digits(raw)
    if digits_ar and _validate_nid(digits_ar.translate(_AR2LA)):
        logger.info("Pass2 NID extracted: %s", digits_ar)
        return digits_ar

    logger.warning("Pass2 NID invalid or wrong length: %r", raw.strip()[:30])
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def llm_extract(image_path: str) -> dict | None:
    """
    Full two-pass extraction pipeline.

    Returns a dict with _FIELD_KEYS on success, None if no provider is configured
    or the image cannot be read (caller should fall back to PaddleOCR).

    Fields that could not be extracted are set to None (never missing keys).
    """
    if not has_llm_key():
        return None

    # ── Pass 1: full card ─────────────────────────────────────────────────────
    result = _pass1_all_fields(image_path)
    if result is None:
        logger.warning("llm_extract: Pass1 returned nothing")
        return None

    # ── Pass 2: NID strip zoom (only when Pass 1 missed the NID) ─────────────
    if not result.get("الرقم القومي"):
        logger.info("NID missing after Pass1 — running Pass2 (NID strip zoom) …")
        nid_ar = _pass2_nid_only(image_path)
        if nid_ar:
            result["الرقم القومي"] = nid_ar
            # Derive date from the newly found NID if also missing
            if not result.get("تاريخ الميلاد"):
                nid_la = nid_ar.translate(_AR2LA)
                century = "19" if nid_la[0] == "2" else "20"
                y  = century + nid_la[1:3]
                mo = nid_la[3:5]
                d  = nid_la[5:7]
                result["تاريخ الميلاد"] = _normalise_date(f"{y}/{mo}/{d}")
                logger.info("Date derived from Pass2 NID")

    extracted = sum(1 for v in result.values() if v)
    logger.info("llm_extract final: %d/6 fields", extracted)
    return result


def has_llm_key() -> bool:
    """True if at least one LLM API key is set in the environment."""
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GROQ_API_KEY"))
