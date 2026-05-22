"""
CamScanner-style document preprocessing for Egyptian ID cards.

Pipeline (in order):
  1. Card boundary detection   — finds the ID card rectangle in the photo
  2. Perspective warp          — flattens tilt/angle to a true rectangle
  3. Illumination normalization — CLAHE on L-channel (LAB) for even brightness
  4. Noise reduction           — bilateral filter (edge-preserving smoothing)
  5. Unsharp masking           — sharpens text edges
  6. Morphological bg removal  — divides out watermark/texture background

The perspective-corrected image is used for address and number extraction.
The raw image is kept for name extraction (hOCR y-grouping is rotation-sensitive).

Usage:
    from enhance import preprocess_id_image
    raw, warped = preprocess_id_image('id_photo.jpg')
    # raw   → use for name extraction
    # warped → use for address / numbers
"""

import cv2
import numpy as np
from pathlib import Path


# ════════════════════════════════════════════════════════════════════
# 1. CARD BOUNDARY DETECTION
# ════════════════════════════════════════════════════════════════════

def detect_card_corners(img: np.ndarray) -> np.ndarray | None:
    """
    Find the four corners of the ID card in the photo.

    Strategy: Egyptian ID cards are darker than most table surfaces.
    We threshold on brightness and find the largest dark blob that
    occupies a sensible fraction of the frame (30-95%).

    Returns:
        4×2 float32 array [TL, TR, BR, BL], or None if not found.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ── Try brightness-based separation ──────────────────────────
    _, bright_mask = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    dark_mask      = cv2.bitwise_not(bright_mask)

    # Close small holes in the card region
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
    dark_closed = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel)

    corners = _largest_quad_from_mask(dark_closed, h, w, min_frac=0.25)
    if corners is not None:
        return corners

    # ── Fall back: Canny edge + contour approach ──────────────────
    blurred = cv2.GaussianBlur(gray, (9, 9), 0)
    edges   = cv2.Canny(blurred, 30, 100)
    kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges   = cv2.dilate(edges, kernel2, iterations=2)

    return _largest_quad_from_mask(edges, h, w, min_frac=0.20)


def _largest_quad_from_mask(mask: np.ndarray, h: int, w: int,
                              min_frac: float = 0.20) -> np.ndarray | None:
    """Extract largest 4-corner polygon from a binary mask."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for c in contours[:5]:
        area = cv2.contourArea(c)
        if area < (h * w * min_frac):
            continue
        hull = cv2.convexHull(c)
        peri = cv2.arcLength(hull, True)
        for eps in [0.03, 0.05, 0.08, 0.10]:
            approx = cv2.approxPolyDP(hull, eps * peri, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2).astype(np.float32)
                return _order_corners(pts)

    return None


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """
    Order corners as [TL, TR, BR, BL].

    Algorithm:
      TL = min(x+y)   — nearest to origin
      BR = max(x+y)   — farthest from origin
      TR = max x of remaining two points
      BL = min x of remaining two points
    """
    s  = pts.sum(axis=1)          # x+y
    tl = pts[np.argmin(s)]        # smallest x+y = TL
    br = pts[np.argmax(s)]        # largest  x+y = BR

    # Remaining two points
    mask     = ~((pts == tl).all(axis=1) | (pts == br).all(axis=1))
    remaining = pts[mask]

    # Larger x = TR, smaller x = BL
    if remaining[0][0] >= remaining[1][0]:
        tr, bl = remaining[0], remaining[1]
    else:
        bl, tr = remaining[0], remaining[1]

    return np.array([tl, tr, br, bl], dtype=np.float32)


# ════════════════════════════════════════════════════════════════════
# 2. PERSPECTIVE WARP
# ════════════════════════════════════════════════════════════════════

# Standard ID-1 card aspect ratio: 85.60 mm × 53.98 mm ≈ 1.586 : 1
_ID_ASPECT = 85.60 / 53.98   # ≈ 1.586


def perspective_warp(img: np.ndarray,
                     corners: np.ndarray,
                     output_width: int = 1400) -> np.ndarray:
    """
    Warp the detected card quad to a flat rectangle.

    Args:
        img          : Original image.
        corners      : 4×2 float32 [TL, TR, BR, BL].
        output_width : Width of rectified output (height auto from aspect).

    Returns:
        Warped image (output_width × output_height).
    """
    out_h = int(output_width / _ID_ASPECT)
    dst   = np.array([
        [0,             0           ],
        [output_width-1, 0          ],
        [output_width-1, out_h - 1  ],
        [0,             out_h - 1   ],
    ], dtype=np.float32)

    M      = cv2.getPerspectiveTransform(corners, dst)
    warped = cv2.warpPerspective(img, M, (output_width, out_h),
                                  flags=cv2.INTER_CUBIC)
    return warped


# ════════════════════════════════════════════════════════════════════
# 3. ILLUMINATION NORMALIZATION
# ════════════════════════════════════════════════════════════════════

def normalize_illumination(img: np.ndarray,
                            clip_limit: float = 2.5,
                            tile_grid: tuple = (8, 8)) -> np.ndarray:
    """
    CLAHE on the L-channel (LAB) — equalizes brightness unevenly lit photos
    without blowing out colour or creating halo artefacts.
    """
    lab  = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    l     = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


# ════════════════════════════════════════════════════════════════════
# 4. NOISE REDUCTION (bilateral)
# ════════════════════════════════════════════════════════════════════

def denoise(img: np.ndarray,
            d: int = 7,
            sigma_color: float = 35,
            sigma_space: float = 35) -> np.ndarray:
    """
    Bilateral filter — smooths noise while preserving text edges.

    Tuned conservatively (d=7, sigma=35) to avoid blurring fine strokes
    or amplifying the watermark texture when sharpening follows.
    """
    return cv2.bilateralFilter(img, d, sigma_color, sigma_space)


# ════════════════════════════════════════════════════════════════════
# 5. UNSHARP MASK (sharpening)
# ════════════════════════════════════════════════════════════════════

def sharpen(img: np.ndarray,
            amount: float = 1.4,
            radius: float = 1.5) -> np.ndarray:
    """
    Unsharp mask — classic photographic sharpening.

    Formula: sharpened = original × (1 + amount) - gaussian × amount

    WARNING: Sharpening amplifies ALL high-frequency content, including
    the watermark texture. Use only on images where watermark has already
    been suppressed (e.g., after bg_normalize) or avoided.

    For the Egyptian ID pipeline, sharpening is applied to the
    perspective-corrected image BEFORE bg_normalize to improve contrast
    for text detection — the bg_normalize then suppresses the amplified
    watermark that sharpening reveals.
    """
    blurred   = cv2.GaussianBlur(img, (0, 0), radius)
    sharpened = cv2.addWeighted(img, 1.0 + amount, blurred, -amount, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


# ════════════════════════════════════════════════════════════════════
# 6. MORPHOLOGICAL BACKGROUND REMOVAL
# ════════════════════════════════════════════════════════════════════

def bg_normalize(gray: np.ndarray, ksize: int = 21) -> np.ndarray:
    """
    Morphological illumination normalization.

    Estimates the background as the dilated (bright) version of the image.
    Dividing by this estimate removes slow-varying background —
    effectively suppressing the pyramid/sphinx watermark on Egyptian IDs.

    This is the core step that makes text readable through the watermark.
    """
    bg = cv2.morphologyEx(
        gray, cv2.MORPH_DILATE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))
    )
    return cv2.divide(gray, bg, scale=255)


# ════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def preprocess_id_image(image_path: str,
                         save_warped: bool = False,
                         output_width: int = 1400) -> tuple:
    """
    Full CamScanner-style preprocessing for an Egyptian ID card photo.

    Steps:
        1. Load image
        2. Detect card corners
        3. Perspective warp to flat rectangle
        4. Illumination normalization (CLAHE)
        5. Bilateral denoising
        6. Sharpen (conservative)

    Returns:
        (raw_img, warped_img)

        raw_img   — original image, deskewed if needed. Use for NAME extraction
                    (hOCR y-position grouping is sensitive to rotation).
        warped_img — perspective-corrected, enhanced. Use for ADDRESS and NUMBERS.

    If card corners cannot be detected, warped_img == raw_img (graceful fallback).
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot open: {image_path}")

    raw = img.copy()

    # ── Detect card in photo ───────────────────────────────────────
    corners = detect_card_corners(img)

    if corners is None:
        # No card boundary found — fall back to original
        return raw, raw

    # ── Perspective warp ───────────────────────────────────────────
    warped = perspective_warp(img, corners, output_width=output_width)

    # NOTE: Bilateral denoising and sharpening are intentionally skipped here.
    # Both consistently break Tesseract PSM-4's Arabic column segmentation on
    # Egyptian IDs — they alter local contrast in ways that confuse the layout
    # analyser. Enhancement is applied per-field in the OCR pipeline via
    # bg_normalize, which handles the watermark suppression without side effects.

    # ── Save debug output ──────────────────────────────────────────
    if save_warped:
        out_path = str(Path(image_path).with_suffix('')) + '_warped.jpg'
        cv2.imwrite(out_path, warped)

    return raw, warped


def enhance_for_ocr(img: np.ndarray, scale: int = 3,
                    bg_ksize: int = 21) -> np.ndarray:
    """
    Per-field OCR enhancement: scale up → bg_normalize → return grayscale.
    Used internally by the main OCR pipeline for each extracted region.

    Args:
        img      : Region-of-interest crop (BGR).
        scale    : Upscale factor (3× default for address, 6× for name).
        bg_ksize : Morphological kernel size for background estimation.

    Returns:
        Normalized grayscale ready for Tesseract.
    """
    s    = cv2.resize(img, None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(s, cv2.COLOR_BGR2GRAY)
    return bg_normalize(gray, ksize=bg_ksize)
