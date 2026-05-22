"""
Egyptian National ID OCR — PaddleOCR Edition
=============================================
Robust extraction of all 6 fields from Egyptian national ID cards,
regardless of lighting, rotation, distance, or camera quality.

Fields extracted:
  الاسم بالكامل      Full name
  الرقم القومي       National ID (14 digits)
  تاريخ الميلاد     Date of birth
  العنوان بالكامل    Street address
  المنطقة والمحافظة  District & governorate
  رقم البطاقة       Card serial number

Usage:
  python egyptian_id_ocr.py <image_path>
  python egyptian_id_ocr.py <folder_path>
  from egyptian_id_ocr import extract_id_fields
"""

import os
import sys

# Load .env before anything else so GROQ_API_KEY etc. are available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

os.environ["FLAGS_use_mkldnn"]    = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["PADDLE_DISABLE_MKLDNN"] = "1"

import cv2
import numpy as np
import re
import json
from pathlib import Path

# ════════════════════════════════════════════════════════════════════
# OCR ENGINE  (lazy singleton)
# ════════════════════════════════════════════════════════════════════

_ocr_engine = None


def _patch_paddle_inference():
    import paddle.inference as _pi
    _orig = _pi.create_predictor

    def _no_mkldnn(config):
        try:
            config.disable_mkldnn()
            config.disable_onednn()
        except Exception:
            pass
        return _orig(config)

    _pi.create_predictor = _no_mkldnn


def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _patch_paddle_inference()
        from paddleocr import PaddleOCR
        print("Loading PaddleOCR Arabic model (first run downloads ~50 MB)...")
        _ocr_engine = PaddleOCR(
            lang='ar',
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            text_rec_score_thresh=0.25,
        )
        print("PaddleOCR ready.")
    return _ocr_engine


# ════════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════════

_AR2LA = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_LA2AR = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')

_TASHKEEL = re.compile(
    r'[ؐ-ًؚ-ٰٟۖ-ۜ۟-ۤۧ-ۭ]'
)

# Egyptian governorate codes embedded in NID digits [7:9]
_GOV_CODES = {
    '01': 'القاهرة',         '02': 'الإسكندرية',   '03': 'بورسعيد',
    '04': 'السويس',           '11': 'دمياط',         '12': 'الدقهلية',
    '13': 'الشرقية',          '14': 'القليوبية',     '15': 'كفر الشيخ',
    '16': 'الغربية',          '17': 'المنوفية',      '18': 'البحيرة',
    '19': 'الإسماعيلية',     '21': 'الجيزة',        '22': 'بني سويف',
    '23': 'الفيوم',           '24': 'المنيا',         '25': 'أسيوط',
    '26': 'سوهاج',            '27': 'قنا',            '28': 'أسوان',
    '29': 'الأقصر',           '31': 'البحر الأحمر',  '32': 'الوادي الجديد',
    '33': 'مطروح',            '34': 'شمال سيناء',    '35': 'جنوب سيناء',
    '88': 'خارج الجمهورية',
}

# ISO/IEC 7810 ID-1 card: 85.60 × 53.98 mm
_CARD_ASPECT = 85.60 / 53.98   # ≈ 1.586  (width / height)
_CARD_W      = 1200
_CARD_H      = int(_CARD_W / _CARD_ASPECT)   # ≈ 1009

# Card layout zones  (y_top, y_bot, x_left, x_right) as fractions of card size.
# The ID card photo sits on the LEFT ~25% of the card body.
# All text fields occupy the RIGHT 75%.
_ZONES = {
    'full':    (0.00, 1.00, 0.00, 1.00),
    'name':    (0.05, 0.55, 0.20, 1.00),   # full name (right of photo, upper half)
    'mid':     (0.38, 0.78, 0.20, 1.00),   # address + district
    'bottom':  (0.55, 1.00, 0.00, 1.00),   # NID + date + serial (wider)
    'nid':     (0.55, 0.93, 0.05, 1.00),   # NID strip — full width (scale capped at 2x)
    'nid_r':   (0.55, 0.93, 0.45, 1.00),   # right 55% of NID — first digits, allows 3x scale
    'nid_l':   (0.55, 0.93, 0.00, 0.57),   # left  57% of NID — last digits, allows 3x scale
    'date':    (0.60, 0.92, 0.00, 0.55),   # date of birth (left side)
    'serial':  (0.86, 1.00, 0.00, 1.00),   # card serial number (bottom strip)
}

# Words whose presence marks a token as header noise (not a name)
_SKIP_WORDS = {
    'جمهورية', 'مصر', 'العربية', 'بطاقة', 'تحقيق',
    'الشخصية', 'بطاقه', 'نحقيق', 'بطافة', 'رطاقة', 'تعقيق',
}

# Street-type keywords → classify token as address
_ADDR_KW = [
    'شارع', 'ش ', 'ميدان', 'حارة', 'عطفة', 'عطقة', 'زقاق',
    'كوبري', 'طريق', 'محور', 'ترعة', 'عمارة', 'برج', 'مجمع',
    'مبنى', 'قطعة', 'مسكن', 'مساكن', 'خدمات', 'بندر',
    'ارض', 'أرض', 'مزادات', 'مزرعة', 'زراعي',
    'لاظوغلى', 'لاظوغلي', 'لالوغلى', 'لاظو', 'رامز', 'منصور',
    'مجاورة', 'مستثمر', 'غرب', 'شرق', 'امتداد', 'ابراج',
]

# District / governorate keywords → classify token as district
_DIST_KW = [
    'السيدة', 'السيده', 'القاهرة', 'القاهره', 'الفاهره',
    'الجيزة', 'الجيزه', 'الاسكندرية', 'الإسكندرية',
    'زينب', 'زيئب', 'زيتب', 'يدب', 'عابدين', 'بولاق', 'شبرا',
    'حلوان', 'مدينة', 'مركز', 'محافظة', 'قسم', 'ناحية',
    'دمياط', 'الدقهلية', 'الشرقية', 'القليوبية', 'كفر',
    'الغربية', 'المنوفية', 'البحيرة', 'الإسماعيلية',
    'سويف', 'الفيوم', 'المنيا', 'أسيوط', 'سوهاج',
    'أسوان', 'الأقصر', 'السويس', 'بورسعيد', 'مطروح',
    'التجمع', 'المعادى', 'المعادي', 'زايد', 'القديمة',
    'الفسطاط', 'اسماعيلية', 'ثالث', 'خامس',
]

_NAME_NOISE = [
    'بطاقة', 'نحقيق', 'بطافة', 'رطاقة', 'الشخصية', 'التخصية',
    'تحقيق', 'جمهورية', 'العربية', 'تعقيق', 'العبية', 'حهوز',
    'مصرية',
]

_FIELD_KEYS = [
    'الاسم بالكامل', 'الرقم القومي', 'تاريخ الميلاد',
    'العنوان بالكامل', 'المنطقة والمحافظة', 'رقم البطاقة',
]


# ════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════════

def _strip_tashkeel(text: str) -> str:
    return _TASHKEEL.sub('', text) if text else text


# Arabic alef variants that OCR confuses: أ إ آ ٱ → ا
_ALEF_NORM = re.compile(r'[أإآٱ]')

def _norm_ar(text: str) -> str:
    """Normalize alef variants for consistent keyword matching."""
    if not text:
        return text
    text = _ALEF_NORM.sub('ا', text)
    return text


def _fix_digit_letter_confusion(text: str) -> str:
    """
    OCR frequently mistakes Arabic alef (ا U+0627) for Arabic-Indic 1 (١ U+0661)
    because they look identical. Convert ١ → ا only when it is adjacent to real
    Arabic letters, leaving stand-alone digit strings (house numbers, NID) intact.
    """
    if not text:
        return text
    chars = list(text)
    for i, c in enumerate(chars):
        if c != '١':
            continue
        prev_ar = (i > 0
                   and '؀' <= chars[i-1] <= 'ۿ'
                   and not '٠' <= chars[i-1] <= '٩')
        next_ar = (i < len(chars)-1
                   and '؀' <= chars[i+1] <= 'ۿ'
                   and not '٠' <= chars[i+1] <= '٩')
        if prev_ar or next_ar:
            chars[i] = 'ا'
    return ''.join(chars)


def _valid_date(y, mo, d) -> bool:
    try:
        return 1900 <= int(y) <= 2025 and 1 <= int(mo) <= 12 and 1 <= int(d) <= 31
    except (ValueError, TypeError):
        return False


def _validate_nid(nid: str) -> bool:
    """Structural validation of Egyptian 14-digit national ID."""
    if not nid or len(nid) != 14 or not nid.isdigit():
        return False
    if nid[0] not in '23':
        return False
    try:
        mo  = int(nid[3:5])
        day = int(nid[5:7])
    except ValueError:
        return False
    if not (1 <= mo <= 12 and 1 <= day <= 31):
        return False
    return nid[7:9] in _GOV_CODES


def _nid_length_fix(digits: str) -> str | None:
    """
    Correct a 13-digit (one missing) or 15-digit (one extra) NID read
    by trying all single-digit insertions / deletions.  O(140) checks, free.
    """
    if len(digits) == 13:
        for pos in range(14):
            for d in '0123456789':
                candidate = digits[:pos] + d + digits[pos:]
                if _validate_nid(candidate):
                    return candidate
    elif len(digits) == 15:
        for pos in range(15):
            candidate = digits[:pos] + digits[pos + 1:]
            if _validate_nid(candidate):
                return candidate
    return None


def _groq_extract(img: np.ndarray, field: str, verbose: bool = False) -> str | None:
    """
    Groq LLaMA Vision fallback — called only when PaddleOCR pipeline fails.
    Requires GROQ_API_KEY environment variable.  Zero cost on Groq free tier.
    """
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        if verbose:
            print("   Groq fallback skipped — GROQ_API_KEY not set")
        return None

    try:
        import base64
        from groq import Groq

        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        b64 = base64.b64encode(buf.tobytes()).decode()

        if field == 'nid':
            prompt = (
                "This is a crop of an Egyptian national ID card (بطاقة تحقيق الشخصية). "
                "Locate the 14-digit national ID number (الرقم القومي). "
                "It always starts with 2 (born 1900s) or 3 (born 2000s), followed by "
                "6 digits for birth date YYMMDD, then 2 digits for governorate code. "
                "The digits may be Arabic-Indic (٠١٢٣٤٥٦٧٨٩) or Western (0-9). "
                "Reply with EXACTLY 14 Western digits (0-9). No spaces, no other text."
            )
        elif field == 'name':
            prompt = (
                "This is an Egyptian national ID card (بطاقة تحقيق الشخصية). "
                "Find and return ONLY the person's full Arabic name (الاسم بالكامل). "
                "It is typically 4-6 Arabic words on the right side of the card. "
                "Reply with ONLY the Arabic name, no transliteration, no explanation."
            )
        else:
            return None

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            max_tokens=120,
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
        answer = response.choices[0].message.content.strip()
        if verbose:
            print(f"   Groq {field} → {answer!r}")
        return answer

    except Exception as exc:
        if verbose:
            print(f"   Groq fallback error: {exc}")
        return None


def _derive_from_nid(nid: str) -> dict:
    """Extract birth date and governorate from a structurally valid NID."""
    century = '19' if nid[0] == '2' else '20'
    y   = century + nid[1:3]
    mo  = nid[3:5]
    day = nid[5:7]
    gov = _GOV_CODES.get(nid[7:9], '')
    return {
        'date': f"{y}/{mo}/{day}".translate(_LA2AR),
        'gov':  gov,
    }


def _name_looks_valid(name: str) -> bool:
    """
    A plausible Egyptian name has ≥ 4 Arabic words each with ≥ 2 letters.
    Fewer words or mostly short fragments are treated as garbage OCR output.
    Strip tashkeel first — diacritics must not inflate the letter count.
    """
    name = _strip_tashkeel(name) if name else name
    long_words = [
        w for w in (name or '').split()
        if sum(1 for c in w if '؀' <= c <= 'ۿ' and not '٠' <= c <= '٩') >= 2
    ]
    return len(long_words) >= 4


def _arabic_words(text: str, min_len: int = 2) -> list:
    """
    Return Arabic words filtered by Arabic *letter* count.
    Explicitly excludes Arabic-Indic digits (U+0660–U+0669) so that
    pure numeral strings like ٣١٠٦٨٠ are not treated as Arabic text.
    """
    return [
        w for w in text.split()
        if sum(1 for c in w
               if '؀' <= c <= 'ۿ'        # in Arabic block
               and not '٠' <= c <= '٩'   # but not Arabic-Indic digit
               ) >= min_len
        and w not in _SKIP_WORDS
    ]


# ════════════════════════════════════════════════════════════════════
# IMAGE PREPROCESSING
# ════════════════════════════════════════════════════════════════════

def _auto_gamma(img: np.ndarray) -> np.ndarray:
    """
    Percentile-based exposure correction.
    Uses p10 (shadows) + p90 (highlights) for a more robust
    exposure estimate than the mean, especially for night/indoor shots.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    p10  = float(np.percentile(gray, 10))
    p90  = float(np.percentile(gray, 90))

    if p90 < 80:                  gamma = 0.35   # very dark
    elif p90 < 130:               gamma = 0.55   # dark
    elif p10 < 50 and p90 < 170: gamma = 0.72   # underexposed
    elif p90 > 245:               gamma = 1.80   # overexposed / washed out
    else:
        return img

    lut = np.array(
        [min(255, int(((i / 255.0) ** (1.0 / gamma)) * 255)) for i in range(256)],
        dtype=np.uint8,
    )
    return cv2.LUT(img, lut)


def _estimate_blur(img: np.ndarray) -> float:
    """Laplacian variance — lower = blurrier. < 40 → apply deblur."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _deblur(img: np.ndarray, amount: float = 1.5) -> np.ndarray:
    """Unsharp mask to recover motion / focus blur."""
    blurred = cv2.GaussianBlur(img, (0, 0), 2.0)
    return np.clip(
        cv2.addWeighted(img, 1.0 + amount, blurred, -amount, 0), 0, 255
    ).astype(np.uint8)


def _shadow_remove(img: np.ndarray) -> np.ndarray:
    """
    CamScanner 'magic color' — white background, vivid text:
      1. Morphological dilation of L-channel → background estimate
      2. Float divide → uniform illumination
      3. 95th-percentile stretch → background maps to true white
      4. Gamma 0.75 → compresses near-white to pure white
      5. CLAHE for local punch
      6. Saturation ×1.6 → green header and colored text stay vivid
    """
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    k = min(max(31, min(l.shape) // 12), 61)   # 31-61 px, capped for speed
    k = k if k % 2 == 1 else k + 1
    bg = cv2.dilate(l, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))

    l_f = l.astype(np.float32) / (bg.astype(np.float32) + 1e-6)
    p95 = float(np.percentile(l_f, 95))
    if p95 > 0.01:
        l_f = np.clip(l_f / p95, 0.0, 1.0)
    l_f   = np.power(l_f, 0.75)
    l_out = (l_f * 255).clip(0, 255).astype(np.uint8)

    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_out = clahe.apply(l_out)

    a_out = np.clip((a.astype(np.float32) - 128) * 1.6 + 128, 0, 255).astype(np.uint8)
    b_out = np.clip((b.astype(np.float32) - 128) * 1.6 + 128, 0, 255).astype(np.uint8)

    return cv2.cvtColor(cv2.merge([l_out, a_out, b_out]), cv2.COLOR_LAB2BGR)


def _sharpen(img: np.ndarray, amount: float = 1.3, radius: float = 1.2) -> np.ndarray:
    blur  = cv2.GaussianBlur(img, (0, 0), radius)
    sharp = cv2.addWeighted(img, 1.0 + amount, blur, -amount, 0)
    return np.clip(sharp, 0, 255).astype(np.uint8)





# ── Corner detection ─────────────────────────────────────────────────

def _order_corners(pts: np.ndarray) -> np.ndarray:
    s  = pts.sum(axis=1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    mask = ~((pts == tl).all(axis=1) | (pts == br).all(axis=1))
    rem  = pts[mask]
    tr, bl = (rem[0], rem[1]) if rem[0][0] >= rem[1][0] else (rem[1], rem[0])
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _quad_from_mask(mask: np.ndarray, h: int, w: int,
                     min_frac: float) -> np.ndarray | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(c) < h * w * min_frac:
            continue
        hull = cv2.convexHull(c)
        peri = cv2.arcLength(hull, True)
        for eps in [0.02, 0.03, 0.05, 0.07, 0.10]:
            approx = cv2.approxPolyDP(hull, eps * peri, True)
            if len(approx) == 4:
                return _order_corners(approx.reshape(4, 2).astype(np.float32))
    return None


def _detect_corners(img: np.ndarray) -> np.ndarray | None:
    """Three-strategy card corner detection."""
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # S1: dark card on bright surface
    _, bright = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    dark = cv2.bitwise_not(bright)
    k25 = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    corners = _quad_from_mask(cv2.morphologyEx(dark, cv2.MORPH_CLOSE, k25), h, w, 0.25)
    if corners is not None:
        return corners

    # S2: Otsu
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    k15 = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    corners = _quad_from_mask(cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, k15), h, w, 0.20)
    if corners is not None:
        return corners

    # S3: Canny edges
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    edges   = cv2.Canny(blurred, 20, 80)
    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, k3, iterations=3)
    return _quad_from_mask(edges, h, w, 0.18)


def _try_rotations(img: np.ndarray) -> tuple:
    """
    Try all four 90°-step orientations and pick the one whose detected
    card quad best matches the Egyptian ID landscape aspect ratio.
    Handles cards photographed sideways or upside-down.
    """
    candidates = [
        img,
        cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(img, cv2.ROTATE_180),
        cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]
    best_score, best_img, best_corners = float('-inf'), img, None

    for cand in candidates:
        corners = _detect_corners(cand)
        if corners is None:
            continue
        tl, tr, br, bl = corners
        cw = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
        ch = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
        if ch < 1:
            continue
        score = -abs(cw / ch - _CARD_ASPECT)
        if score > best_score:
            best_score, best_img, best_corners = score, cand, corners

    return best_img, best_corners


def _deskew(img: np.ndarray, max_angle: float = 12.0) -> np.ndarray:
    """Correct small camera-tilt rotations via HoughLinesP."""
    gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges   = cv2.Canny(blurred, 40, 120)
    h, w    = img.shape[:2]
    lines   = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=120,
        minLineLength=w // 5, maxLineGap=25,
    )
    if lines is None:
        return img
    angles = []
    for x1, y1, x2, y2 in lines[:, 0]:
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) > abs(dy) and abs(dx) > 10:
            angles.append(np.degrees(np.arctan2(dy, dx)))
    if len(angles) < 5:
        return img
    angle = float(np.median(angles))
    if abs(angle) < 0.4 or abs(angle) > max_angle:
        return img
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h),
                           flags=cv2.INTER_LANCZOS4,
                           borderMode=cv2.BORDER_REPLICATE)


def detect_image_type(img: np.ndarray) -> str:
    """'enhanced' if already scanned/flat, 'photo' if raw camera shot."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return 'enhanced' if gray.mean() > 170 and gray.std() < 80 else 'photo'


def _perspective_warp(img: np.ndarray, corners: np.ndarray) -> np.ndarray:
    out_h = int(_CARD_W / _CARD_ASPECT)
    dst   = np.array([
        [0,          0       ],
        [_CARD_W-1,  0       ],
        [_CARD_W-1,  out_h-1 ],
        [0,          out_h-1 ],
    ], dtype=np.float32)
    M = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(img, M, (_CARD_W, out_h), flags=cv2.INTER_LANCZOS4)


def preprocess_photo(img: np.ndarray) -> np.ndarray:
    """Full pipeline for raw phone photos."""
    img = _auto_gamma(img)

    # Deblur only for significantly blurry images (Laplacian var < 25)
    if _estimate_blur(img) < 25:
        img = _deblur(img, amount=1.2)

    img = _deskew(img)

    # Pre-CLAHE boost for very dark images so corner detection works
    gray_pre = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gray_pre.mean() < 90:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l   = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4, 4)).apply(l)
        img = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    img, corners = _try_rotations(img)

    if corners is not None:
        warped = _perspective_warp(img, corners)
    else:
        scale  = _CARD_W / img.shape[1]
        warped = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_LINEAR)

    warped = _shadow_remove(warped)
    warped = _sharpen(warped)
    return warped


def preprocess_enhanced(img: np.ndarray) -> np.ndarray:
    """Pipeline for already-scanned / CamScanner images."""
    if img.shape[1] < _CARD_W:
        scale = _CARD_W / img.shape[1]
        img   = cv2.resize(img, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_LINEAR)
    img = _shadow_remove(img)
    img = _sharpen(img, amount=0.9)
    return img


# ════════════════════════════════════════════════════════════════════
# OCR HELPERS
# ════════════════════════════════════════════════════════════════════

def run_paddle_ocr(img: np.ndarray) -> list:
    """
    Run PaddleOCR and return list of dicts:
      {text, conf, x, y, bbox}
    Handles both legacy tuple format and new PaddleX dict format.
    """
    # Skip near-blank images — no content to read, and they can trigger native crashes
    gray_chk = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    if float(gray_chk.std()) < 8.0:
        return []

    engine = get_ocr_engine()
    raw    = engine.predict(img)

    results = []
    if not raw:
        return results

    page = raw[0]
    if page is None:
        return results

    # PaddleOCR 3.x / PaddleX format
    if isinstance(page, dict) or hasattr(page, '__getitem__'):
        try:
            texts  = page['rec_texts']
            scores = page['rec_scores']
            polys  = page['rec_polys']
            for text, conf, poly in zip(texts, scores, polys):
                text = str(text).strip()
                if not text or conf < 0.25:
                    continue
                bbox = [list(pt) for pt in poly]
                results.append({
                    'text': text, 'conf': round(float(conf), 3),
                    'y': bbox[0][1], 'x': bbox[0][0], 'bbox': bbox,
                })
            results.sort(key=lambda r: (round(r['y'] / 15) * 15, -r['x']))
            return results
        except (KeyError, TypeError):
            pass

    # Legacy format: [[bbox, (text, conf)], ...]
    for line in page:
        try:
            bbox, (text, conf) = line
        except (TypeError, ValueError):
            continue
        text = str(text).strip()
        if not text or conf < 0.25:
            continue
        results.append({
            'text': text, 'conf': round(conf, 3),
            'y': bbox[0][1], 'x': bbox[0][0], 'bbox': bbox,
        })

    results.sort(key=lambda r: (round(r['y'] / 15) * 15, -r['x']))
    return results


def _zone_crop(img: np.ndarray, zone: str) -> np.ndarray:
    h, w = img.shape[:2]
    y0, y1, x0, x1 = _ZONES[zone]
    return img[int(h*y0):int(h*y1), int(w*x0):int(w*x1)].copy()


def _enhance_zone(crop: np.ndarray, scale: int = 2,
                   binary: bool = False, for_digits: bool = False) -> np.ndarray:
    """
    Per-zone OCR enhancement:
      1. Upscale (Lanczos) for finer character resolution
      2. Morphological bg-normalize (remove watermark / shadows)
      3. CLAHE for local contrast
      4. Optional Otsu binarization for digit-only zones
    """
    if crop.size == 0:
        return crop
    up   = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)

    k = min(max(21, min(gray.shape[:2]) // 10), 51)
    k = k if k % 2 == 1 else k + 1
    bg   = cv2.dilate(gray, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    norm = cv2.divide(gray, bg, scale=255)

    if for_digits:
        clahe = cv2.createCLAHE(clipLimit=5.0, tileGridSize=(4, 4))
        norm  = clahe.apply(norm)
        _, norm = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif binary:
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
        norm  = clahe.apply(norm)
        norm  = cv2.adaptiveThreshold(norm, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    else:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        norm  = clahe.apply(norm)

    return cv2.cvtColor(norm, cv2.COLOR_GRAY2BGR)


def _enhance_nid_adaptive(crop: np.ndarray, scale: int = 5) -> np.ndarray:
    """
    Specialised NID-strip enhancer for cards with complex pyramid/security backgrounds.
    Uses adaptive (local) thresholding instead of global Otsu so the varying background
    doesn't poison the binarisation.
    """
    if crop.size == 0:
        return crop
    up   = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)

    # Large-kernel background normalisation
    k  = min(max(41, min(gray.shape[:2]) // 8), 81)
    k  = k if k % 2 == 1 else k + 1
    bg = cv2.dilate(gray, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    norm = cv2.divide(gray, bg, scale=255)

    # CLAHE for local contrast
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
    norm  = clahe.apply(norm)

    # Adaptive (local) threshold — handles non-uniform illumination
    binary = cv2.adaptiveThreshold(
        norm, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
        blockSize=31, C=8,
    )

    # Small morphological cleanup to remove isolated noise pixels
    k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN,  k3)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k3)

    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def _enhance_nid_saturation_mask(crop: np.ndarray, scale: int = 3) -> np.ndarray:
    """
    HSV saturation-mask filter: black ink = dark (V<130) + achromatic (S<100).
    Security-pattern pixels are colorful (S≥100) or bright — both rejected.
    Separates NID digits from Egyptian ID geometric security background.
    """
    if crop.size == 0:
        return crop
    up = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    hsv = cv2.cvtColor(up, cv2.COLOR_BGR2HSV)
    _, s_ch, v_ch = cv2.split(hsv)

    text_mask = ((v_ch < 130) & (s_ch < 100)).astype(np.uint8) * 255
    binary = cv2.bitwise_not(text_mask)   # black text on white background

    k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN,  k2)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k2)

    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def _zone_ocr(img: np.ndarray, zone: str,
               scale: int = 2, binary: bool = False,
               for_digits: bool = False,
               adaptive: bool = False,
               saturation_mask: bool = False) -> list:
    """OCR a named card zone. Adjusts y/x coords back to full-card space."""
    h, w = img.shape[:2]
    y0_frac, _, x0_frac, _ = _ZONES[zone]
    y_off = int(h * y0_frac)
    x_off = int(w * x0_frac)

    crop = _zone_crop(img, zone)

    # Cap scale so max dimension stays ≤ 2400 px — prevents PaddleOCR native crashes
    ch, cw = crop.shape[:2]
    max_dim = max(ch, cw)
    if max_dim > 0:
        scale = min(scale, max(1, 2400 // max_dim))

    if saturation_mask:
        enhanced = _enhance_nid_saturation_mask(crop, scale=scale)
    elif adaptive:
        enhanced = _enhance_nid_adaptive(crop, scale=scale)
    else:
        enhanced = _enhance_zone(crop, scale=scale, binary=binary, for_digits=for_digits)
    results = run_paddle_ocr(enhanced)

    for r in results:
        r['y'] = r['y'] / scale + y_off
        r['x'] = r['x'] / scale + x_off

    return results


def _deduplicate_ocr(results: list) -> list:
    """
    Merge tokens from multiple OCR passes.
    Same text in the same 22 px y-band = duplicate → keep highest confidence.
    Pure digit strings bypass text-dedup so multi-token NID reconstruction works.
    """
    seen, extras = {}, []
    for r in results:
        digits = re.sub(r'\D', '', r['text'].translate(_AR2LA))
        if len(digits) >= 5:
            extras.append(r)
        else:
            key = (r['text'], round(r['y'] / 22))
            if key not in seen or r['conf'] > seen[key]['conf']:
                seen[key] = r
    combined = list(seen.values()) + extras
    combined.sort(key=lambda r: (round(r['y'] / 15) * 15, -r['x']))
    return combined


# ════════════════════════════════════════════════════════════════════
# FIELD EXTRACTION
# ════════════════════════════════════════════════════════════════════

Y_BAND = 22   # px — tokens within this vertical band = same logical line


def _group_by_yband(tokens: list) -> list:
    groups = []
    for tok in sorted(tokens, key=lambda t: t['y']):
        for g in groups:
            if abs(tok['y'] - g[0]['y']) <= Y_BAND:
                g.append(tok)
                break
        else:
            groups.append([tok])
    return groups


def _make_logical_lines(tokens: list) -> list:
    """Group tokens by y-band, deduplicate text within each group, join RTL."""
    lines = []
    for grp in _group_by_yband(tokens):
        grp.sort(key=lambda t: -t['x'])   # rightmost first (RTL)
        seen_txt: dict = {}
        for t in grp:
            if t['text'] not in seen_txt or t['conf'] > seen_txt[t['text']]['conf']:
                seen_txt[t['text']] = t
        unique   = sorted(seen_txt.values(), key=lambda t: -t['x'])
        text     = ' '.join(t['text'] for t in unique)
        avg_conf = sum(t['conf'] for t in unique) / len(unique)
        lines.append({'text': text, 'y': grp[0]['y'], 'conf': avg_conf})
    return lines


def extract_fields(ocr_results: list, card_h: int = 0) -> dict:
    """
    Parse OCR token list into Egyptian ID fields.

    Uses:
      • Vertical zone constraints (name top, NID bottom)
      • NID structural validation + NID→date/gov derivation
      • Multi-token NID reconstruction
      • Positional heuristics for Arabic name vs. address vs. district
    """
    fields = {k: None for k in _FIELD_KEYS}

    if not ocr_results:
        return fields

    # Estimate card height from highest y value in results
    max_y = max(r['y'] for r in ocr_results)
    if card_h <= 0:
        card_h = max_y if max_y > 100 else _CARD_H

    name_tokens   = []
    addr_parts    = []
    dist_parts    = []
    nid_candidates = []
    date_candidates = []
    card_candidates = []

    for r in ocr_results:
        text = r['text'].strip()
        if not text:
            continue

        lat   = text.translate(_AR2LA)
        rel_y = r['y'] / card_h

        # ── Card serial number ─────────────────────────────────
        m = re.search(r'\b([A-Z]{2})([0-9]{4,9})\b', lat.upper())
        if m:
            card_candidates.append(m.group(1) + m.group(2))
            continue

        # Partial card serial fallback (pure alphanum, bottom area)
        if rel_y > 0.80 and re.fullmatch(r'[A-Z0-9]{5,10}', lat.upper()):
            card_candidates.append(lat.upper())
            continue

        # ── National ID digits ─────────────────────────────────
        digits = re.sub(r'\D', '', lat)
        if len(digits) >= 8 and digits[:1] in '23':
            nid_candidates.append({
                'digits': digits, 'y': r['y'], 'x': r['x'],
                'conf': r['conf'], 'rel_y': rel_y,
            })
            continue

        # ── Date ──────────────────────────────────────────────
        # YYYY/MM/DD
        dm = re.search(r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})', lat)
        if dm:
            y, mo, d = dm.groups()
            mo, d = mo.zfill(2), d.zfill(2)
            if _valid_date(y, mo, d):
                date_candidates.append(f"{y}/{mo}/{d}".translate(_LA2AR))
                continue

        # DD/MM/YYYY (reversed format)
        dm2 = re.search(r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})', lat)
        if dm2:
            d, mo, y = dm2.groups()
            mo, d = mo.zfill(2), d.zfill(2)
            if _valid_date(y, mo, d):
                date_candidates.append(f"{y}/{mo}/{d}".translate(_LA2AR))
                continue

        # ── Arabic text classification ─────────────────────────
        # Fix OCR confusion of ا (alef) → ١ (digit 1) before classifying
        text_f = re.sub(r'\s+', ' ',
                        _fix_digit_letter_confusion(text)).strip()
        words = _arabic_words(text_f)
        if not words:
            # Preserve short numerals in address zone: "١٢", "٩٩", "49", "١٧ أ"
            if 0.28 <= rel_y <= 0.72:
                ar_digits  = re.sub(r'[^٠-٩0-9]', '', text_f)
                non_digits = re.sub(r'[٠-٩0-9\s]', '', text_f)
                if ar_digits and len(ar_digits) <= 4 and len(non_digits) <= 2:
                    addr_parts.append({'text': text_f, 'y': r['y'], 'x': r['x']})
            continue

        joined      = ' '.join(words)
        joined_norm = _norm_ar(joined)

        if any(kw in joined for kw in _NAME_NOISE):
            continue

        if any(_norm_ar(kw) in joined_norm for kw in _DIST_KW):
            # Use full text_f (preserves embedded numbers like "١٧") for storage
            dist_parts.append({'text': text_f, 'y': r['y'], 'x': r['x']})
        elif any(_norm_ar(kw) in joined_norm for kw in _ADDR_KW):
            addr_parts.append({'text': text_f, 'y': r['y'], 'x': r['x']})
        else:
            tok = {'text': joined, 'y': r['y'], 'x': r['x'], 'conf': r['conf']}
            # Skip top 15%: that region is the card header (جمهورية/بطاقة تحقيق).
            # Upper bound 0.52 (was 0.44): cards where perspective correction shifts
            # the name slightly lower still land in name zone.
            if 0.15 <= rel_y < 0.52:
                name_tokens.append(tok)
            elif rel_y < 0.15:
                pass   # card header — discard
            else:
                addr_parts.append({'text': text_f, 'y': r['y'], 'x': r['x']})

    # ═══ NID resolution ═══════════════════════════════════════════
    nid = None

    # Strategy 1: single token with exactly 14 valid digits
    valid14 = [c for c in nid_candidates
               if len(c['digits']) == 14 and _validate_nid(c['digits'])]
    if valid14:
        # Majority vote: if multiple passes agree on the same NID, prefer it
        from collections import Counter
        vote = Counter(c['digits'] for c in valid14)
        top_nid, top_count = vote.most_common(1)[0]
        if top_count > 1:
            nid = top_nid  # consensus across passes
        else:
            nid = max(valid14, key=lambda c: c['conf'])['digits']

    # Strategy 2: concatenate digit tokens in bottom zone (RTL), scan for valid NID
    if not nid:
        def _has_ar_letters(t):
            return any('؀' <= c <= 'ۿ' and not '٠' <= c <= '٩' for c in t)

        bottom_digit_tokens = sorted(
            [r for r in ocr_results
             if r['y'] / card_h > 0.55
             and not _has_ar_letters(r['text'])
             and not re.search(r'[A-Za-z]', r['text'])   # skip card serials
             and re.sub(r'\D', '', r['text'].translate(_AR2LA))],
            key=lambda r: -r['x'],
        )
        bottom_concat = ''.join(
            re.sub(r'\D', '', r['text'].translate(_AR2LA))
            for r in bottom_digit_tokens
        )
        # Slide a 14-char window to find a structurally valid NID
        for i in range(len(bottom_concat)):
            if bottom_concat[i] in '23' and i + 14 <= len(bottom_concat):
                candidate = bottom_concat[i:i + 14]
                if _validate_nid(candidate):
                    nid = candidate
                    break

        # Strategy 2b: partial NID prefix injection.
        # OCR sometimes misses the rightmost 1-2 digits of the NID (the century
        # code and first birth-year digit printed at the card's right edge).
        # Try prepending '3' / '2' / '30' / '20' and re-scan the window.
        if not nid and bottom_concat and bottom_concat[0] not in '23':
            for prefix in ('3', '2', '30', '20'):
                trial = prefix + bottom_concat
                for i in range(min(len(prefix) + 1, len(trial))):
                    if trial[i] in '23' and i + 14 <= len(trial):
                        candidate = trial[i:i + 14]
                        if _validate_nid(candidate):
                            nid = candidate
                            break
                if nid:
                    break

        # If still no valid 14-digit NID, keep the best partial for display
        if not nid and bottom_concat and bottom_concat[0] in '23' and len(bottom_concat) >= 6:
            nid = bottom_concat[:14]

    # Strategy 3: fall back to longest single-token digit run
    if not nid and nid_candidates:
        best_partial = max(nid_candidates, key=lambda c: len(c['digits']))
        if len(best_partial['digits']) >= 6:
            nid = best_partial['digits'][:14]

    if nid:
        fields['الرقم القومي'] = nid.translate(_LA2AR)
        derived = _derive_from_nid(nid) if _validate_nid(nid) else {}
        if not date_candidates and derived.get('date'):
            fields['تاريخ الميلاد'] = derived['date']
        nid_gov = derived.get('gov', '')
    else:
        nid_gov = ''

    if date_candidates:
        fields['تاريخ الميلاد'] = date_candidates[0]

    # ═══ Name resolution ══════════════════════════════════════════
    name_filtered = [t for t in name_tokens if t['conf'] >= 0.42]
    logical_lines = _make_logical_lines(name_filtered)
    logical_lines = [
        l for l in logical_lines
        if not any(kw in l['text'] for kw in _ADDR_KW + _DIST_KW + _NAME_NOISE)
        and sum(1 for c in l['text'] if '؀' <= c <= 'ۿ') >= 2
    ]
    logical_lines.sort(key=lambda l: l['y'])

    if logical_lines:
        # Limit to 2-8 words: merged garbage lines (>8 words) are excluded;
        # Egyptian names are typically 4-6 words, never more than 7-8.
        multi = [l for l in logical_lines if 2 <= len(l['text'].split()) <= 8]

        if multi:
            # Pick the best multi-word line: weight confidence × word count so
            # a low-confidence garbage token can't beat a high-confidence real name
            chain = max(multi, key=lambda l: l['conf'] * len(l['text'].split()))

            # If multiple multi-word lines are close vertically, chain them
            close_multi = [l for l in multi if abs(l['y'] - chain['y']) < 60]
            if len(close_multi) > 1:
                close_multi.sort(key=lambda l: l['y'])
                candidate = ' '.join(l['text'] for l in close_multi)
                if len(candidate.split()) <= 8:
                    full_name = candidate
                else:
                    full_name = chain['text']
            else:
                # Look for a prefix line (single OR multi-word) just above the chain.
                # Require: within 80px, conf ≥ 0.60, no noise keywords —
                # prevents card header garbage (far above) from being prepended.
                top_y = chain['y']
                above_all = [l for l in logical_lines
                             if top_y - 80 < l['y'] < top_y - Y_BAND / 2]
                above_all.sort(key=lambda l: l['y'])
                prefix_cand = above_all[-1] if above_all else None
                if (prefix_cand
                        and prefix_cand['conf'] >= 0.60
                        and not any(kw in prefix_cand['text'] for kw in _NAME_NOISE)):
                    prefix = prefix_cand['text']
                else:
                    prefix = None
                full_name = (f"{prefix} {chain['text']}".strip()
                             if prefix else chain['text'])
        else:
            # Only single-word lines — concatenate top few
            full_name = ' '.join(l['text'] for l in logical_lines[:4])

        fields['الاسم بالكامل'] = full_name.strip()

    # Name rescue: when the card isn't perfectly perspective-corrected, the
    # name field lands at rel_y >= 0.44 and gets routed to addr_parts.
    # If the extracted name looks like garbage, check addr_parts for a better
    # candidate (pure multi-word Arabic, no addr/dist keywords, upper half).
    if not _name_looks_valid(fields.get('الاسم بالكامل', '')):
        # Direct rescue: token is purely a name (no address keywords)
        name_rescue = [
            p for p in addr_parts
            if _name_looks_valid(p['text'])
            and not any(_norm_ar(kw) in _norm_ar(p['text'])
                        for kw in _ADDR_KW + _DIST_KW)
            and p['y'] / card_h < 0.62
        ]
        if name_rescue:
            best_rescue = max(name_rescue, key=lambda p: len(p['text'].split()))
            fields['الاسم بالكامل'] = best_rescue['text']
            addr_parts = [p for p in addr_parts if id(p) != id(best_rescue)]
        else:
            # Split rescue: name is the pure-Arabic PREFIX of a name+address token.
            # e.g. "اشرف عبدالعزيز محمد حسنين ١٧ ش منصور عطفة رامز لاظوغلى"
            # → name = first 4 Arabic words, rest becomes address.
            _ar_digit = re.compile(r'[٠-٩0-9]')
            for p in sorted(addr_parts, key=lambda t: t['y']):
                if p['y'] / card_h >= 0.62:
                    break
                words = p['text'].split()
                for split_at in range(len(words), 3, -1):
                    prefix = ' '.join(words[:split_at])
                    suffix = ' '.join(words[split_at:])
                    # Valid split: prefix is a name, suffix has digits or addr keywords
                    if (not any(_norm_ar(kw) in _norm_ar(prefix)
                                for kw in _ADDR_KW + _DIST_KW)
                            and _name_looks_valid(prefix)
                            and (_ar_digit.search(suffix)
                                 or any(_norm_ar(kw) in _norm_ar(suffix)
                                        for kw in _ADDR_KW + _DIST_KW))):
                        fields['الاسم بالكامل'] = prefix
                        if suffix:
                            p['text'] = suffix
                        else:
                            addr_parts = [q for q in addr_parts if id(q) != id(p)]
                        break
                if _name_looks_valid(fields.get('الاسم بالكامل', '')):
                    break

    # ═══ Address / District ════════════════════════════════════════

    # Address cleanup: remove tokens that look like name components
    # (pure multi-word Arabic, no addr/dist keywords) from addr_parts.
    # These appear when part of the name falls just below the 0.44 rel_y cut.
    extracted_name = fields.get('الاسم بالكامل', '') or ''
    extracted_name_words = set(_norm_ar(w) for w in extracted_name.split() if w)
    filtered_addr_parts = []
    for p in addr_parts:
        p_words = _arabic_words(p['text'])
        # Token is pure Arabic name-like with no keywords and overlaps the
        # extracted name by ≥ 50% → treat as name overflow, not address
        if (p_words
                and not any(_norm_ar(kw) in _norm_ar(p['text'])
                            for kw in _ADDR_KW + _DIST_KW)
                and extracted_name_words
                and len({_norm_ar(w) for w in p_words} & extracted_name_words)
                    / len(p_words) >= 0.50):
            continue  # skip — it's part of the name
        filtered_addr_parts.append(p)
    addr_parts = filtered_addr_parts

    def _assemble_rtl(parts: list) -> str:
        """Group tokens by y-band, sort RTL within each, dedup, join lines."""
        lines = []
        for band in _group_by_yband(parts):
            band.sort(key=lambda t: -t['x'])
            seen: dict = {}
            for t in band:
                if t['text'] not in seen:
                    seen[t['text']] = t
            unique = sorted(seen.values(), key=lambda t: -t['x'])
            lines.append(' '.join(t['text'] for t in unique))
        return ' '.join(lines)

    if addr_parts:
        fields['العنوان بالكامل'] = _assemble_rtl(addr_parts)

    if dist_parts:
        fields['المنطقة والمحافظة'] = _assemble_rtl(dist_parts)
    elif nid_gov:
        fields['المنطقة والمحافظة'] = nid_gov

    # ═══ Card serial ═══════════════════════════════════════════════
    if card_candidates:
        fields['رقم البطاقة'] = card_candidates[0]

    return fields


# ════════════════════════════════════════════════════════════════════
# POST-PROCESSING CORRECTIONS
# ════════════════════════════════════════════════════════════════════

_NAME_CORRECTIONS = {
    'عيبدالعزيز': 'عبدالعزيز', 'عيدالعزيز':  'عبدالعزيز',
    'عبدالعريز':  'عبدالعزيز', 'عبدالعزيزي': 'عبدالعزيز',
    'حمسنين': 'حسنين', 'حمبنين': 'حسنين', 'حتسدين': 'حسنين',
    'حستدت':  'حسنين', 'حتسدت':  'حسنين',
    'باأسيل': 'باسل',  'باسيل':  'باسل',  'ياسل': 'باسل',
    'اشنرف':  'اشرف',  'أشرف':   'اشرف',
}

_ADDR_CORRECTIONS = {
    'عطقة':  'عطفة', 'عطفةه':  'عطفة',
    'راز':   'رامز', 'رامر':   'رامز',
    'لالوغلى': 'لاظوغلى', 'لاظو غلى': 'لاظوغلى',
    'لاظو على': 'لاظوغلى',
}

_DIST_CORRECTIONS = {
    'زيئب': 'زينب', 'زيتب': 'زينب', 'زيلب': 'زينب', 'يدب': 'زينب',
    'القاهرهةه': 'القاهرة', 'الفاهره': 'القاهرة',
    'القاهره':   'القاهرة', 'السيده': 'السيدة',
    'لسيده': 'السيدة',
}


def _apply_corrections(result: dict) -> dict:
    out = dict(result)

    def fix_words(text, table):
        if not text:
            return text
        return ' '.join(table.get(w, w) for w in text.split())

    def fix_substrings(text, table):
        if not text:
            return text
        for wrong, right in table.items():
            text = text.replace(wrong, right)
        return text

    out['الاسم بالكامل']      = fix_words(
        _strip_tashkeel(out.get('الاسم بالكامل')), _NAME_CORRECTIONS)
    out['العنوان بالكامل']    = fix_substrings(
        _strip_tashkeel(out.get('العنوان بالكامل')), _ADDR_CORRECTIONS)
    out['المنطقة والمحافظة'] = fix_substrings(
        _strip_tashkeel(out.get('المنطقة والمحافظة')), _DIST_CORRECTIONS)
    return out


# ════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ════════════════════════════════════════════════════════════════════

def extract_id_fields(image_path: str,
                      verbose: bool = True,
                      save_debug: bool = False) -> dict:
    """
    Full pipeline: load → preprocess → adaptive OCR → parse → correct.

    OCR strategy:
      P1  always — full shadow-removed image
      P2  conditional — bottom zone (Otsu binary) only if NID not found in P1
      P3  conditional — name zone (bgNorm) only if name not found in P1
    Best case: 1 inference call.  Worst case: 3.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot open: {image_path}")

    h, w     = img.shape[:2]
    img_type = detect_image_type(img)

    if verbose:
        print(f"Image: {Path(image_path).name}  ({w}x{h})  [{img_type}]")

    # ── Preprocess ────────────────────────────────────────────────
    processed = (preprocess_enhanced(img) if img_type == 'enhanced'
                 else preprocess_photo(img))

    if save_debug:
        debug_path = str(Path(image_path).with_suffix('')) + '_processed.jpg'
        cv2.imwrite(debug_path, processed)
        if verbose:
            print(f"   Saved debug image: {debug_path}")

    ph = processed.shape[0]

    # ── Pass 1: full image (always) ───────────────────────────────
    if verbose:
        print("P1 full image...")
    p1 = run_paddle_ocr(processed)

    # Quick parse to see what P1 already found
    _quick = extract_fields(p1, card_h=ph)
    _raw_nid = _quick.get('الرقم القومي') or ''
    _nid_ok  = bool(_raw_nid) and _validate_nid(
        re.sub(r'\D', '', _raw_nid.translate(_AR2LA))
    )
    _name_ok = _name_looks_valid(_quick.get('الاسم بالكامل', ''))
    _card_ok = bool(_quick.get('رقم البطاقة'))

    extra = []

    # ── Fast-path: P1 found everything ───────────────────────────
    if _nid_ok and _name_ok and _card_ok:
        if verbose:
            print("P1 complete — fast path")
    else:
        if not _nid_ok:
            # ── Pass 2a: NID right+left halves at 3x (each half is narrow enough
            #    to allow 3x upscaling vs the full zone which caps at 2x)
            if verbose:
                print("P2a NID zone (split 3x)...")
            extra += _zone_ocr(processed, 'nid_r', scale=3, binary=False)
            extra += _zone_ocr(processed, 'nid_l', scale=3, binary=False)

            p2a_check = _deduplicate_ocr(p1 + extra)
            _nid_try = extract_fields(p2a_check, card_h=ph).get('الرقم القومي') or ''

            if not _validate_nid(re.sub(r'\D', '', _nid_try.translate(_AR2LA))):
                # ── Pass 2b: full NID zone adaptive binary (patterned backgrounds)
                if verbose:
                    print("P2b NID adaptive binary...")
                extra += _zone_ocr(processed, 'nid', scale=3, adaptive=True)

                p2b_check = _deduplicate_ocr(p1 + extra)
                _nid_try2 = extract_fields(p2b_check, card_h=ph).get('الرقم القومي') or ''

                if not _validate_nid(re.sub(r'\D', '', _nid_try2.translate(_AR2LA))):
                    # ── Pass 2c: HSV saturation mask — black ink vs colorful bg
                    if verbose:
                        print("P2c NID saturation mask...")
                    extra += _zone_ocr(processed, 'nid_r', scale=3, saturation_mask=True)
                    extra += _zone_ocr(processed, 'nid_l', scale=3, saturation_mask=True)

                    p2c_check = _deduplicate_ocr(p1 + extra)
                    _nid_try3 = extract_fields(p2c_check, card_h=ph).get('الرقم القومي') or ''

                    if not _validate_nid(re.sub(r'\D', '', _nid_try3.translate(_AR2LA))):
                        # ── Pass 2d: wider bottom zone (last resort, more context)
                        if verbose:
                            print("P2d bottom zone 3x...")
                        extra += _zone_ocr(processed, 'bottom', scale=3,
                                           binary=False, for_digits=False)

        # Count high-conf Arabic word tokens P1 found in the name zone.
        # If P1 already has ≥4 such words, running P3 adds interference tokens
        # that merge into the same y-bands and produce longer garbage strings.
        _p1_name_words = sum(
            sum(
                1 for w in _strip_tashkeel(r['text']).split()
                if sum(1 for c in w if '؀' <= c <= 'ۿ' and not '٠' <= c <= '٩') >= 2
            )
            for r in p1
            if r['conf'] >= 0.65
            and 0.15 <= r['y'] / ph < 0.52
            and not any(kw in r['text'] for kw in _NAME_NOISE)
        )

        # ── Pass 3: name zone — only if name still missing AND P1 didn't find
        #    enough name-zone tokens (otherwise P3 only adds noise).
        if not _name_ok and _p1_name_words < 4:
            if verbose:
                print(f"P3 name zone 2x (P1 had {_p1_name_words} name words)...")
            extra += _zone_ocr(processed, 'name', scale=2, binary=False)
        elif not _name_ok and verbose:
            print(f"P3 skipped — P1 already has {_p1_name_words} name-zone words")

    all_results = _deduplicate_ocr(p1 + extra)
    _passes = 1 + (0 if _nid_ok else 1) + (0 if _name_ok else 1)

    if verbose:
        print(f"   {_passes} pass(es) — {len(all_results)} tokens after dedup")
        print("\nRaw OCR tokens:")
        for r in all_results:
            print(f"  {r['conf']:.2f} | y={int(r['y']):4d} | {r['text']}")

    # ── Parse + correct ───────────────────────────────────────────
    result = extract_fields(all_results, card_h=ph)

    # NID length correction: fix 13/15-digit misreads (structural insertion/deletion)
    _nid_raw = result.get('الرقم القومي') or ''
    if _nid_raw:
        _nid_digits = re.sub(r'\D', '', _nid_raw.translate(_AR2LA))
        if not _validate_nid(_nid_digits):
            _fixed = _nid_length_fix(_nid_digits)
            if _fixed:
                if verbose:
                    print(f"NID length fix: {_nid_digits} → {_fixed}")
                result['الرقم القومي'] = _fixed.translate(_LA2AR)

    result = _apply_corrections(result)

    # ── Groq Vision fallback — only for fields PaddleOCR couldn't resolve ──
    _nid_final = re.sub(r'\D', '', (result.get('الرقم القومي') or '').translate(_AR2LA))
    _name_final = result.get('الاسم بالكامل') or ''

    if not _validate_nid(_nid_final) or not _name_looks_valid(_name_final):
        if verbose:
            print("Trying Groq Vision fallback...")

        if not _validate_nid(_nid_final):
            # Send bottom half of card (contains NID strip + context)
            nid_crop = processed[int(ph * 0.50):, :]
            raw_nid = _groq_extract(nid_crop, 'nid', verbose=verbose)
            if raw_nid:
                digits = re.sub(r'\D', '', raw_nid.translate(_AR2LA))
                if not digits:   # LLM may output Arabic-Indic digits
                    digits = re.sub(r'\D', '', raw_nid)
                if _validate_nid(digits):
                    result['الرقم القومي'] = digits.translate(_LA2AR)
                    # Re-derive DOB and gov from newly validated NID
                    if not result.get('تاريخ الميلاد'):
                        _d = _derive_from_nid(digits)
                        result['تاريخ الميلاد'] = _d['date']
                    if not result.get('المنطقة والمحافظة'):
                        _d = _derive_from_nid(digits)
                        result['المنطقة والمحافظة'] = _d['gov']

        if not _name_looks_valid(result.get('الاسم بالكامل') or ''):
            raw_name = _groq_extract(processed, 'name', verbose=verbose)
            if raw_name:
                clean = _strip_tashkeel(raw_name.strip())
                if _name_looks_valid(clean):
                    result['الاسم بالكامل'] = clean

    if verbose:
        print("\n" + "-" * 60)
        labels = {
            'الاسم بالكامل':      'Full name',
            'الرقم القومي':       'National ID',
            'تاريخ الميلاد':     'Date of birth',
            'العنوان بالكامل':    'Address',
            'المنطقة والمحافظة': 'District/Gov',
            'رقم البطاقة':       'Card no',
        }
        for key, label in labels.items():
            val = result.get(key)
            if val:
                print(f"  {label}: {val}")
        print("-" * 60)

    return result


# ════════════════════════════════════════════════════════════════════
# BATCH
# ════════════════════════════════════════════════════════════════════

def process_folder(folder_path: str) -> list:
    folder = Path(folder_path)
    exts   = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    images = sorted(f for f in folder.iterdir() if f.suffix.lower() in exts)
    if not images:
        print(f"No images found in: {folder_path}")
        return []

    results = []
    for i, p in enumerate(images, 1):
        print(f"\n[{i}/{len(images)}] {p.name}")
        try:
            r = extract_id_fields(str(p))
            r['_file'] = p.name
            results.append(r)
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({'_file': p.name, '_error': str(e)})

    out = folder / 'ocr_results.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved: {out}")
    return results


# ════════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    target = sys.argv[1]
    debug  = '--debug' in sys.argv

    if os.path.isdir(target):
        process_folder(target)
    elif os.path.isfile(target):
        r = extract_id_fields(target, save_debug=debug)
        print('\nJSON output:')
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"Not found: {target}")
        sys.exit(1)
