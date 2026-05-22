import os
import sys

os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["PADDLE_DISABLE_MKLDNN"] = "1"

import cv2
import gradio as gr

from egyptian_id_ocr import extract_id_fields

# ── Field definitions (Arabic key → display label) ──────────────────
FIELDS = [
    ("الاسم بالكامل",      "Full Name  /  الاسم بالكامل"),
    ("الرقم القومي",       "National ID  /  الرقم القومي"),
    ("تاريخ الميلاد",     "Date of Birth  /  تاريخ الميلاد"),
    ("العنوان بالكامل",    "Address  /  العنوان بالكامل"),
    ("المنطقة والمحافظة", "District & Governorate  /  المنطقة والمحافظة"),
    ("رقم البطاقة",       "Card Number  /  رقم البطاقة"),
]

CSS = """
.result-box textarea { font-size: 1.1rem; direction: rtl; text-align: right; }
.id-number textarea  { font-family: monospace; font-size: 1.2rem; letter-spacing: 2px; }
h1 { text-align: center; }
"""


def run_ocr(image_path: str):
    """Called by Gradio with the uploaded file path."""
    if image_path is None:
        return [None] + [""] * len(FIELDS) + ["Please upload an image."]

    try:
        result = extract_id_fields(image_path, verbose=False, save_debug=True)
    except Exception as e:
        return [None] + [""] * len(FIELDS) + [f"Error: {e}"]

    # Load the processed/debug image if it was saved
    base = os.path.splitext(image_path)[0]
    debug_path = base + "_processed.jpg"
    processed_img = None
    if os.path.exists(debug_path):
        bgr = cv2.imread(debug_path)
        processed_img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    field_values = [result.get(ar_key, "") for ar_key, _ in FIELDS]

    found = sum(1 for v in field_values if v)
    status = f"✅ Extracted {found}/{len(FIELDS)} fields successfully."

    return [processed_img] + field_values + [status]


def build_ui():
    with gr.Blocks(css=CSS, title="Egyptian ID OCR") as demo:
        gr.Markdown("# Egyptian National ID — OCR Reader")

        with gr.Row():
            # ── Left column: upload + processed preview ──────────────
            with gr.Column(scale=1):
                image_input = gr.Image(
                    label="Upload ID Card Image",
                    type="filepath",
                    sources=["upload", "clipboard"],
                )
                run_btn = gr.Button("Extract Fields", variant="primary")
                processed_out = gr.Image(label="Preprocessed Image", interactive=False)

            # ── Right column: extracted fields ───────────────────────
            with gr.Column(scale=1):
                field_outputs = []
                for i, (ar_key, label) in enumerate(FIELDS):
                    extra_cls = "id-number result-box" if "رقم" in ar_key else "result-box"
                    tb = gr.Textbox(
                        label=label,
                        interactive=False,
                        elem_classes=extra_cls,
                    )
                    field_outputs.append(tb)

                status_box = gr.Textbox(label="Status", interactive=False, lines=1)

        all_outputs = [processed_out] + field_outputs + [status_box]

        run_btn.click(fn=run_ocr, inputs=image_input, outputs=all_outputs)
        # Also trigger on image upload/change
        image_input.change(fn=run_ocr, inputs=image_input, outputs=all_outputs)

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(inbrowser=True)
