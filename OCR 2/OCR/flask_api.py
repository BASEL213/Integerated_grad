"""
Flask REST API — Egyptian NID OCR
Run: python flask_api.py
Endpoint: POST /ocr/extract  (multipart/form-data, field name: "image")
Health:   GET  /health
"""

import os
import sys
import tempfile
import logging

# Disable MKL-DNN to avoid paddle inference issues
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["PADDLE_DISABLE_MKLDNN"] = "1"

from flask import Flask, request, jsonify

try:
    from flask_cors import CORS
    _has_cors = True
except ImportError:
    _has_cors = False

from egyptian_id_ocr import extract_id_fields

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
if _has_cors:
    CORS(app)

_ALLOWED = {"jpg", "jpeg", "png", "webp", "bmp"}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED


# ── Health check ────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "nid-ocr"})


# ── Main OCR endpoint ────────────────────────────────────────────────────────

@app.route("/ocr/extract", methods=["POST"])
def extract():
    # Validate input
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error": 'No image provided. Send as multipart/form-data with key "image".',
        }), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify({"success": False, "error": "Empty filename."}), 400
    if not _allowed(file.filename):
        return jsonify({
            "success": False,
            "error": f"Unsupported format. Allowed: {', '.join(sorted(_ALLOWED))}",
        }), 400

    suffix = "." + file.filename.rsplit(".", 1)[-1].lower()
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        size_kb = os.path.getsize(tmp_path) // 1024
        logger.info("OCR request — %d KB, suffix=%s", size_kb, suffix)

        result: dict = extract_id_fields(tmp_path, verbose=False, save_debug=False)

        extracted = sum(1 for v in result.values() if v)
        logger.info("Extracted %d/6 fields", extracted)

        return jsonify({
            "success": True,
            "data": result,
            "extracted_count": extracted,
            "total_fields": 6,
        })

    except Exception as exc:
        logger.error("OCR failed: %s", exc, exc_info=True)
        return jsonify({
            "success": False,
            "error": f"OCR processing error: {exc}",
        }), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    logger.info("Starting NID OCR API on 0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=False)
