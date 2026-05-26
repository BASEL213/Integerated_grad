"""
Flask REST API — Egyptian NID OCR
==================================
Run:  python flask_api.py

Endpoints
---------
  POST /ocr/extract   multipart/form-data, field "image"
  GET  /health        liveness probe
  GET  /status        shows which extraction method is active
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid

# ── Paddle inference flags (must be set before any paddle import) ──────────────
os.environ.setdefault("FLAGS_use_mkldnn",     "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("PADDLE_DISABLE_MKLDNN","1")

# ── Load .env before any import that reads env vars ───────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, request, jsonify

try:
    from flask_cors import CORS as _CORS
    _has_cors = True
except ImportError:
    _has_cors = False

from llm_extractor import llm_extract, has_llm_key, _validate_nid, _AR2LA, _LA2AR

class _RidFilter(logging.Filter):
    """Inject a default request_id into records that don't supply one."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  [%(request_id)s]  %(message)s",
)
for _h in logging.root.handlers:
    _h.addFilter(_RidFilter())

logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
if _has_cors:
    _CORS(app, resources={r"/*": {"origins": "*"}})

# ── Extraction strategy ───────────────────────────────────────────────────────

_USE_LLM        = has_llm_key()
_MAX_UPLOAD_MB  = 15
_MAX_UPLOAD_B   = _MAX_UPLOAD_MB * 1024 * 1024
_ALLOWED_EXT    = {"jpg", "jpeg", "png", "webp", "bmp"}

if _USE_LLM:
    _provider = "Gemini" if os.environ.get("GOOGLE_API_KEY") else "Groq"
    logger.info("LLM extraction ENABLED — primary provider: %s", _provider)
    logger.info("PaddleOCR will be used as fallback if LLM returns nothing.")
else:
    logger.info("No LLM API key found — using PaddleOCR only.")
    logger.info("Set GOOGLE_API_KEY or GROQ_API_KEY in .env to enable fast LLM mode.")

# ── Warm-up PaddleOCR (only when it will be the primary path) ─────────────────

if not _USE_LLM:
    try:
        from egyptian_id_ocr import get_ocr_engine
        logger.info("Pre-loading PaddleOCR model …")
        get_ocr_engine()
        logger.info("PaddleOCR model ready.")
    except Exception as _e:
        logger.warning("OCR pre-load failed (will retry on first request): %s", _e)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _allowed_ext(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXT


def _paddle_nid_fillin(tmp_path: str, result: dict, rid: str) -> str:
    """
    Run a targeted PaddleOCR zone scan on just the NID strip when the LLM
    extracted all other fields but missed the 14-digit national ID.

    Returns the method suffix: "+paddle_nid" if NID was found, "" otherwise.
    Modifies *result* in-place.
    """
    log = logging.LoggerAdapter(logger, {"request_id": rid})
    log.info("LLM missed NID — running targeted NID zone OCR …")
    try:
        import cv2
        from egyptian_id_ocr import (
            preprocess_photo, preprocess_enhanced,
            detect_image_type, _zone_ocr, _deduplicate_ocr,
            extract_fields, _nid_length_fix, _derive_from_nid,
        )

        img      = cv2.imread(tmp_path)
        img_type = detect_image_type(img)
        proc     = (preprocess_enhanced(img)
                    if img_type == "enhanced"
                    else preprocess_photo(img))
        ph       = proc.shape[0]

        # Three complementary passes over the NID strip
        tokens  = _zone_ocr(proc, "nid_r", scale=3, binary=False)
        tokens += _zone_ocr(proc, "nid_l", scale=3, binary=False)
        tokens += _zone_ocr(proc, "nid_r", scale=3, saturation_mask=True)
        tokens += _zone_ocr(proc, "nid_l", scale=3, saturation_mask=True)
        tokens  = _deduplicate_ocr(tokens)

        nid_fields = extract_fields(tokens, card_h=ph)
        nid_raw    = nid_fields.get("الرقم القومي") or ""
        nid_digits = re.sub(r"\D", "", nid_raw.translate(_AR2LA))

        # Try length correction (13/15 → 14 digit fixes)
        if not _validate_nid(nid_digits):
            fixed = _nid_length_fix(nid_digits)
            if fixed:
                nid_digits = fixed

        if _validate_nid(nid_digits):
            result["الرقم القومي"] = nid_digits.translate(_LA2AR)
            log.info("NID zone fill-in succeeded: %s", nid_digits)

            # Derive date-of-birth if also missing
            if not result.get("تاريخ الميلاد"):
                derived = _derive_from_nid(nid_digits)
                result["تاريخ الميلاد"] = derived["date"]
                log.info("Date derived from NID: %s", derived["date"])

            return "+paddle_nid"
        else:
            log.info("NID zone OCR also failed — NID remains null")
            return ""

    except Exception as exc:
        log.warning("NID zone fill-in error: %s", exc)
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    """Liveness probe — always fast."""
    return jsonify({"status": "ok", "service": "nid-ocr"})


@app.route("/status", methods=["GET"])
def status():
    """Shows which extraction path is active and expected latency."""
    llm_provider = None
    if os.environ.get("GOOGLE_API_KEY"):
        llm_provider = "gemini-2.5-flash"
    elif os.environ.get("GROQ_API_KEY"):
        llm_provider = "meta-llama/llama-4-scout-17b-16e-instruct"

    return jsonify({
        "llm_enabled":      _USE_LLM,
        "llm_provider":     llm_provider,
        "paddle_ready":     not _USE_LLM,
        "expected_latency": "3-15 s" if _USE_LLM else "~220 s",
        "max_upload_mb":    _MAX_UPLOAD_MB,
    })


@app.route("/ocr/extract", methods=["POST"])
def extract():
    """
    Main OCR endpoint.

    Accepts: multipart/form-data with field "image"
    Returns: JSON with "success", "data", "extracted_count", "total_fields", "method"
    """
    rid = str(uuid.uuid4())[:8]
    log = logging.LoggerAdapter(logger, {"request_id": rid})

    # ── Input validation ──────────────────────────────────────────────────────
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error":   'No image provided. Send as multipart/form-data with key "image".',
        }), 400

    file = request.files["image"]

    if not file.filename:
        return jsonify({"success": False, "error": "Empty filename."}), 400

    if not _allowed_ext(file.filename):
        return jsonify({
            "success": False,
            "error":   f"Unsupported format. Allowed: {', '.join(sorted(_ALLOWED_EXT))}",
        }), 400

    suffix   = "." + file.filename.rsplit(".", 1)[-1].lower()
    tmp_path = None

    try:
        # Save to temp file so both PaddleOCR (path-based) and LLM can use it
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        # ── File-size guard (checked after save for simplicity) ───────────────
        size_b  = os.path.getsize(tmp_path)
        size_kb = size_b // 1024
        if size_b > _MAX_UPLOAD_B:
            return jsonify({
                "success": False,
                "error":   f"File too large ({size_kb} KB). Maximum: {_MAX_UPLOAD_MB} MB.",
            }), 413

        log.info("OCR request — %d KB  ext=%s", size_kb, suffix)

        result      = None
        method_used = "paddle"

        # ── 1. LLM path (fast, ~3-15 s) ──────────────────────────────────────
        if _USE_LLM:
            result = llm_extract(tmp_path)

            if result and any(v for v in result.values()):
                method_used = (
                    "gemini" if os.environ.get("GOOGLE_API_KEY") else "groq"
                )
                log.info("LLM extraction succeeded (%s)", method_used)

                # If NID is still missing, run a fast targeted zone scan
                nid_ar  = result.get("الرقم القومي") or ""
                nid_la  = re.sub(r"\D", "", nid_ar.translate(_AR2LA))
                if not _validate_nid(nid_la):
                    method_used += _paddle_nid_fillin(tmp_path, result, rid)
            else:
                log.info("LLM returned no usable data — falling back to PaddleOCR …")
                result = None

        # ── 2. PaddleOCR fallback (offline, ~220 s) ───────────────────────────
        if result is None:
            from egyptian_id_ocr import extract_id_fields
            result      = extract_id_fields(tmp_path, verbose=False, save_debug=False)
            method_used = "paddle"

        # ── Summarise ─────────────────────────────────────────────────────────
        extracted = sum(1 for v in result.values() if v)
        log.info("Done — extracted %d/6 fields  method=%s", extracted, method_used)

        return jsonify({
            "success":         True,
            "data":            result,
            "extracted_count": extracted,
            "total_fields":    6,
            "method":          method_used,
            "request_id":      rid,
        })

    except Exception as exc:
        log.error("OCR failed: %s", exc, exc_info=True)
        return jsonify({
            "success":    False,
            "error":      f"OCR processing error: {exc}",
            "request_id": rid,
        }), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    logger.info("Starting NID OCR API on 0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
