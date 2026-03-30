#!/usr/bin/env python3
"""
RotMG item detector service.

Primary entry point: detect_item_from_image_path()

Designed to be called by a Discord bot or other automation that supplies one
screenshot at a time and expects back the matched item name (or None).  All
batch/folder-scanning behavior has been removed; debug output is opt-in.
"""

import csv
import glob
import os
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pytesseract
from PIL import Image
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Algorithm tuning constants
# (These control detection quality and can be tweaked without touching logic.)
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.7      # Minimum template-match confidence to accept an anchor
OCR_CONFIDENCE_THRESHOLD = 10   # Minimum per-token Tesseract confidence to keep
OCR_UPSCALE_FACTOR = 4          # Nearest-neighbor upscale multiplier before OCR
OCR_PADDING_SIZE = 20           # White pixels added around the cropped region
FUZZY_MATCH_THRESHOLD = 50      # Minimum suffix-match score to accept a result (0-100)
FUZZY_MATCH_TOP_N = 3           # How many top candidates to evaluate

# Description region geometry (relative to the first anchor position)
DESC_REGION_OFFSET_Y = -37      # Y offset when no second anchor is found (fallback)
DESC_REGION_WIDTH = 600         # Fallback width when no second anchor is found
DESC_REGION_HEIGHT = 35         # Fallback height when no second anchor is found
DESC_LINE_GAP = 2               # Pixel gap between consecutive description line crops

# Supported image formats for template loading
SUPPORTED_FORMATS = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.PNG", "*.JPG", "*.JPEG", "*.WEBP"]

# OCR preprocessing variant names, tried in this order (first is preferred)
OCR_VARIANTS = ["padded_grayscale", "grayscale"]

# Scales tried during multi-scale anchor template matching.
# Each value is a multiplier applied to the template's native pixel dimensions.
TEMPLATE_SCALES = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
TEMPLATE_MIN_DIMENSION = 5   # px — skip any scaled template smaller than this

# Debug visualization colors (BGR format for OpenCV)
_MATCH_COLOR = (0, 255, 0)         # Green  — valid anchor
_WEAK_MATCH_COLOR = (0, 165, 255)  # Orange — below-threshold anchor
_DESC_REGION_COLOR = (255, 0, 255) # Magenta — description crop box
_RECT_THICKNESS = 2


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def scale_value(base: int, scale: float) -> int:
    """Scale a pixel dimension or signed offset by *scale*, returning an int.

    Preserves the sign of *base* so negative offsets stay negative.
    """
    return int(base * scale)


# ---------------------------------------------------------------------------
# Resource loaders
# ---------------------------------------------------------------------------

def load_template_images(template_dir: str) -> Dict[str, np.ndarray]:
    """Load all anchor template images from a directory, converted to grayscale."""
    templates: Dict[str, np.ndarray] = {}
    if not os.path.exists(template_dir):
        return templates
    for fmt in SUPPORTED_FORMATS:
        for path in glob.glob(os.path.join(template_dir, fmt)):
            img = cv2.imread(path, cv2.IMREAD_COLOR)
            if img is not None:
                templates[os.path.basename(path)] = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return templates


def load_item_descriptions(csv_path: str) -> List[Dict[str, str]]:
    """Load item names and full descriptions from the CSV file."""
    if not os.path.exists(csv_path):
        return []
    try:
        items = []
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row.get("Item Name", "").strip()
                desc = row.get("Description", "").strip()
                if name and desc:
                    items.append({"name": name, "description": desc})
        return items
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Template matching — locate the "Feed Power:" anchor in the image
# ---------------------------------------------------------------------------

def _find_distinct_matches(
    result: np.ndarray,
    template_size: Tuple[int, int],
    template_name: str,
    max_matches: int = 3,
    min_distance: int = 50,
) -> List[Dict]:
    """Return up to max_matches spatially distinct matches for one template."""
    matches = []
    result_copy = result.copy()
    for _ in range(max_matches):
        _, max_val, _, max_loc = cv2.minMaxLoc(result_copy)
        if max_val < 0.1:
            break
        br = (max_loc[0] + template_size[0], max_loc[1] + template_size[1])
        matches.append({
            "template": template_name,
            "confidence": max_val,
            "top_left": max_loc,
            "bottom_right": br,
            "size": template_size,
        })
        # Suppress the neighbourhood so the next iteration finds a different spot
        y1 = max(0, max_loc[1] - min_distance)
        y2 = min(result_copy.shape[0], max_loc[1] + template_size[1] + min_distance)
        x1 = max(0, max_loc[0] - min_distance)
        x2 = min(result_copy.shape[1], max_loc[0] + template_size[0] + min_distance)
        result_copy[y1:y2, x1:x2] = 0
    return matches


def match_template_multiscale(
    screenshot_gray: np.ndarray,
    template: np.ndarray,
    scales: Optional[List[float]] = None,
    debug: bool = False,
) -> Tuple[float, Tuple[int, int], float, Tuple[int, int]]:
    """Match *template* against *screenshot_gray* at each scale in *scales*.

    For each scale the template is resized (preserving aspect ratio) and
    matched with TM_CCOEFF_NORMED.  The scale that produces the highest
    confidence is returned.

    Returns:
        (best_confidence, best_top_left, best_scale, (template_w, template_h))
    """
    if scales is None:
        scales = TEMPLATE_SCALES

    th, tw = template.shape[:2]
    img_h, img_w = screenshot_gray.shape[:2]

    best_conf: float = 0.0
    best_loc: Tuple[int, int] = (0, 0)
    best_scale: float = 1.0
    best_size: Tuple[int, int] = (tw, th)

    for scale in scales:
        new_w = max(1, int(tw * scale))
        new_h = max(1, int(th * scale))

        if new_w < TEMPLATE_MIN_DIMENSION or new_h < TEMPLATE_MIN_DIMENSION:
            if debug:
                print(f"      [multiscale] scale={scale:.2f}: template too small "
                      f"({new_w}x{new_h}), skipping")
            continue
        if new_w >= img_w or new_h >= img_h:
            if debug:
                print(f"      [multiscale] scale={scale:.2f}: template ({new_w}x{new_h}) "
                      f">= image ({img_w}x{img_h}), skipping")
            continue

        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        scaled_tpl = cv2.resize(template, (new_w, new_h), interpolation=interp)
        try:
            res = cv2.matchTemplate(screenshot_gray, scaled_tpl, cv2.TM_CCOEFF_NORMED)
        except cv2.error as exc:
            if debug:
                print(f"      [multiscale] scale={scale:.2f}: matchTemplate error — {exc}")
            continue

        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if debug:
            print(f"      [multiscale] scale={scale:.2f}: conf={max_val:.4f} at {max_loc}")

        if max_val > best_conf:
            best_conf = max_val
            best_loc = max_loc
            best_scale = scale
            best_size = (new_w, new_h)

    return best_conf, best_loc, best_scale, best_size


def _find_second_anchor(
    screenshot_gray: np.ndarray,
    templates: Dict[str, np.ndarray],
    first_anchor: Dict,
    detected_scale: float = 1.0,
    debug: bool = False,
) -> Tuple[Optional[Tuple[int, int]], Optional[int]]:
    """
    Search for a horizontally-flipped anchor template to the right of the
    first anchor on the same Y coordinate.  Returns (position, distance) or
    (None, None) if not found.

    *detected_scale* should match the scale at which the first anchor was
    found so the flipped template is resized consistently.
    """
    first_y = first_anchor["top_left"][1]
    first_x = first_anchor["top_left"][0]

    # Y-tolerance grows with UI scale to stay robust at larger resolutions.
    y_tol = max(5, scale_value(5, detected_scale))

    if debug:
        print(f"    [debug] Searching for second anchor on y={first_y} "
              f"(scale={detected_scale:.2f}, y_tol={y_tol}px)...")

    candidates = []
    for template_name, template in templates.items():
        flipped = cv2.flip(template, 1)
        # Resize the flipped template to match the detected scale of the first anchor.
        if detected_scale != 1.0:
            sc_w = max(1, int(flipped.shape[1] * detected_scale))
            sc_h = max(1, int(flipped.shape[0] * detected_scale))
            if sc_w < screenshot_gray.shape[1] and sc_h < screenshot_gray.shape[0]:
                interp = cv2.INTER_AREA if detected_scale < 1.0 else cv2.INTER_LINEAR
                flipped = cv2.resize(flipped, (sc_w, sc_h), interpolation=interp)
        try:
            res = cv2.matchTemplate(screenshot_gray, flipped, cv2.TM_CCOEFF_NORMED)
        except cv2.error:
            continue
        size = flipped.shape[::-1]
        for m in _find_distinct_matches(res, size, f"{template_name}_flipped",
                                        max_matches=10, min_distance=30):
            if (abs(m["top_left"][1] - first_y) <= y_tol
                    and m["top_left"][0] > first_x
                    and m["confidence"] >= CONFIDENCE_THRESHOLD * 0.8):
                candidates.append(m)

    if candidates:
        best = max(candidates, key=lambda x: x["confidence"])
        pos = best["top_left"]
        dist = pos[0] - first_x
        if debug:
            print(f"    [debug] Second anchor: {best['template']} at {pos} "
                  f"(conf={best['confidence']:.4f}, dist={dist}px)")
        return pos, dist

    if debug:
        print(f"    [debug] No second anchor found on y={first_y}")
    return None, None


def locate_anchor(
    screenshot_gray: np.ndarray,
    templates: Dict[str, np.ndarray],
    debug: bool = False,
) -> Tuple[str, float, Tuple[int, int], Tuple[int, int],
           Optional[Tuple[int, int]], Optional[int], float]:
    """
    Locate the 'Feed Power:' anchor in a grayscale image using multi-scale
    template matching.

    Each template is tried at every scale in TEMPLATE_SCALES; the scale that
    produces the highest TM_CCOEFF_NORMED score is retained.

    Returns:
        (template_name, confidence, top_left, bottom_right,
         second_anchor_pos, anchor_distance, detected_scale)

    Returns empty/zero values (with detected_scale=1.0) if no match exceeds
    CONFIDENCE_THRESHOLD.
    """
    all_matches: List[Dict] = []

    if debug:
        print(f"    [debug] Scales to try: {TEMPLATE_SCALES}")

    for template_name, template in templates.items():
        if debug:
            print(f"    [debug] {template_name}: running multi-scale match...")
        conf, loc, best_scale, size = match_template_multiscale(
            screenshot_gray, template, TEMPLATE_SCALES, debug=debug
        )
        if debug:
            print(f"    [debug] {template_name}: best conf={conf:.4f} "
                  f"at {loc}, scale={best_scale:.2f}, size={size}")
        if conf <= 0.1:
            continue

        # Re-run matching at the winning scale so _find_distinct_matches can
        # surface all spatially distinct occurrences (e.g. two stacked tooltips
        # at the same X column).  This preserves the "pick topmost" clustering.
        interp = cv2.INTER_AREA if best_scale < 1.0 else cv2.INTER_LINEAR
        scaled_tpl = cv2.resize(
            template,
            (size[0], size[1]),
            interpolation=interp,
        )
        try:
            res = cv2.matchTemplate(screenshot_gray, scaled_tpl, cv2.TM_CCOEFF_NORMED)
        except cv2.error:
            res = None

        if res is not None:
            for m in _find_distinct_matches(res, size, template_name, max_matches=3):
                m["scale"] = best_scale
                all_matches.append(m)
        else:
            # Fallback: keep at least the single best match we already found.
            br = (loc[0] + size[0], loc[1] + size[1])
            all_matches.append({
                "template": template_name,
                "confidence": conf,
                "top_left": loc,
                "bottom_right": br,
                "size": size,
                "scale": best_scale,
            })

    valid = [m for m in all_matches if m["confidence"] >= CONFIDENCE_THRESHOLD]
    if not valid:
        return "", 0.0, (0, 0), (0, 0), None, None, 1.0

    # Among valid matches, cluster by x-position and pick the topmost from
    # the column that contains the best-confidence match.
    best = max(valid, key=lambda x: x["confidence"])
    x_tol = int(screenshot_gray.shape[1] * 0.05)
    similar_x = [m for m in valid if abs(m["top_left"][0] - best["top_left"][0]) <= x_tol]
    anchor = min(similar_x, key=lambda x: x["top_left"][1])
    detected_scale = anchor["scale"]

    if debug:
        print(f"    [debug] First anchor: {anchor['template']} at {anchor['top_left']} "
              f"(conf={anchor['confidence']:.4f}, detected_scale={detected_scale:.2f})")

    second_pos, dist = _find_second_anchor(
        screenshot_gray, templates, anchor,
        detected_scale=detected_scale, debug=debug
    )
    return (anchor["template"], anchor["confidence"],
            anchor["top_left"], anchor["bottom_right"],
            second_pos, dist, detected_scale)


# ---------------------------------------------------------------------------
# Description region geometry
# ---------------------------------------------------------------------------

def calculate_desc_region(
    first_anchor_pos: Tuple[int, int],
    second_anchor_pos: Optional[Tuple[int, int]] = None,
    template_width: int = 71,
    scale: float = 1.0,
    debug: bool = False,
) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """
    Compute the bounding box for the last line of the item description,
    which sits just above the 'Feed Power:' anchor row in the tooltip.

    *scale* is the detected template scale from ``locate_anchor``.  It is
    used to proportionally adjust the fallback geometry constants so the
    crop region stays correct across screenshots with different UI scales.
    The dynamic path (when *second_anchor_pos* is known) derives its width
    directly from image coordinates, so *scale* is only needed there for the
    template_width correction.
    """
    x = first_anchor_pos[0]

    if second_anchor_pos is not None:
        # The second anchor was found at the same scale as the first, so
        # its x-position already encodes the real rendered width.  We only
        # need to scale template_width to compute the right edge correctly.
        scaled_tpl_w = scale_value(template_width, scale)
        full_width = (second_anchor_pos[0] + scaled_tpl_w) - first_anchor_pos[0]
        width = int(full_width * 0.98)          # 98% avoids stray UI pixels at the edge
        height = max(20, int(width * 0.05))     # height scales with tooltip width
        y_offset = -max(15, int(width * 0.05))  # offset upward to sit above the anchor
        y = first_anchor_pos[1] + y_offset
        if debug:
            print(f"    [debug] Desc region: {width}px × {height}px "
                  f"(dynamic, y_offset={y_offset}, scale={scale:.2f})")
    else:
        # Fallback: scale the hard-coded defaults proportionally.
        width = max(1, scale_value(DESC_REGION_WIDTH, scale))
        height = max(1, scale_value(DESC_REGION_HEIGHT, scale))
        y_offset = scale_value(DESC_REGION_OFFSET_Y, scale)
        y = first_anchor_pos[1] + y_offset
        if debug:
            print(f"    [debug] Desc region: {width}px × {height}px "
                  f"(fallback scaled, scale={scale:.2f}, y_offset={y_offset})")

    return (x, y), (x + width, y + height)


# ---------------------------------------------------------------------------
# OCR pipeline
# ---------------------------------------------------------------------------

def _preprocess_grayscale(image: np.ndarray) -> np.ndarray:
    """Grayscale + nearest-neighbor upscale."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    h, w = gray.shape
    return cv2.resize(gray, (w * OCR_UPSCALE_FACTOR, h * OCR_UPSCALE_FACTOR),
                      interpolation=cv2.INTER_NEAREST)


def _preprocess_padded_grayscale(image: np.ndarray) -> np.ndarray:
    """Grayscale + upscale + white padding border."""
    processed = _preprocess_grayscale(image)
    return cv2.copyMakeBorder(
        processed,
        OCR_PADDING_SIZE, OCR_PADDING_SIZE,
        OCR_PADDING_SIZE, OCR_PADDING_SIZE,
        cv2.BORDER_CONSTANT, value=255,
    )


_PREPROCESSING_FNS = {
    "grayscale": _preprocess_grayscale,
    "padded_grayscale": _preprocess_padded_grayscale,
}


def build_ocr_text_from_tokens(ocr_data: Dict) -> Dict:
    """Filter Tesseract token output by confidence and assemble the description line."""
    if not ocr_data or "text" not in ocr_data:
        return {"raw_tokens": [], "filtered_tokens": [],
                "desc_last_line": "", "average_confidence": 0}

    raw_tokens, filtered_tokens, confidences = [], [], []
    for i in range(len(ocr_data["text"])):
        text = ocr_data["text"][i].strip()
        conf = int(ocr_data["conf"][i]) if ocr_data["conf"][i] != "-1" else 0
        if text:
            raw_tokens.append({"text": text, "confidence": conf})
            if conf >= OCR_CONFIDENCE_THRESHOLD:
                filtered_tokens.append({"text": text, "confidence": conf})
                confidences.append(conf)

    return {
        "raw_tokens": raw_tokens,
        "filtered_tokens": filtered_tokens,
        "desc_last_line": " ".join(t["text"] for t in filtered_tokens),
        "average_confidence": sum(confidences) / len(confidences) if confidences else 0,
    }


def _run_ocr_on_variant(image: np.ndarray, variant_name: str) -> Dict:
    """Invoke Tesseract on one pre-processed image."""
    try:
        data = pytesseract.image_to_data(
            Image.fromarray(image),
            config=r"--oem 3 --psm 7",
            output_type=pytesseract.Output.DICT,
        )
        return {"success": True, "data": data, "variant_name": variant_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "variant_name": variant_name, "error": str(e)}


def ocr_desc_region(cropped: np.ndarray, debug: bool = False) -> Dict:
    """
    Run OCR over multiple preprocessing variants and return the best result.

    Tries each variant in OCR_VARIANTS order and scores them by token count
    and average confidence.  Returns the highest-scoring variant's output.

    Return dict keys:
        success, desc_last_line, average_confidence,
        raw_tokens, filtered_tokens, best_variant, all_variants
    """
    variants: Dict[str, np.ndarray] = {}
    for name in OCR_VARIANTS:
        fn = _PREPROCESSING_FNS.get(name)
        if fn:
            try:
                variants[name] = fn(cropped)
            except Exception:
                pass

    best_result = None
    best_score = 0
    all_results = []

    for variant_name in OCR_VARIANTS:
        if variant_name not in variants:
            continue
        variant_image = variants[variant_name]
        ocr_result = _run_ocr_on_variant(variant_image, variant_name)

        if ocr_result["success"]:
            tokens = build_ocr_text_from_tokens(ocr_result["data"])
            score = len(tokens["filtered_tokens"]) * 10 + tokens["average_confidence"]
            entry = {
                "variant_name": variant_name, "success": True, "score": score,
                "variant_image": variant_image,
                **tokens,
            }
            all_results.append(entry)
            if score > best_score:
                best_score = score
                best_result = entry.copy()
            if debug:
                print(f"    [debug] OCR variant '{variant_name}': "
                      f"'{tokens['desc_last_line']}' (score={score:.1f})")
        else:
            all_results.append({
                "variant_name": variant_name, "success": False, "score": 0,
                "error": ocr_result["error"], "variant_image": variant_image,
            })

    if best_result:
        return {
            "success": True,
            "desc_last_line": best_result["desc_last_line"],
            "average_confidence": best_result["average_confidence"],
            "raw_tokens": best_result["raw_tokens"],
            "filtered_tokens": best_result["filtered_tokens"],
            "best_variant": best_result["variant_name"],
            "all_variants": all_results,
        }
    return {
        "success": False, "desc_last_line": "", "average_confidence": 0,
        "raw_tokens": [], "filtered_tokens": [],
        "best_variant": None, "all_variants": all_results,
    }


# ---------------------------------------------------------------------------
# Fuzzy matching against description suffixes
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Lowercase, strip non-alphanumeric characters, collapse whitespace."""
    if not text:
        return ""
    normalized = "".join(c if c.isalnum() or c.isspace() else "" for c in text.lower())
    return " ".join(normalized.split())


def find_best_matches(
    ocr_text: str,
    items: List[Dict[str, str]],
    top_n: int = FUZZY_MATCH_TOP_N,
) -> List[Dict]:
    """
    Score each item by comparing the OCR text against every word-based suffix
    of its full description.

    Because the OCR region captures the LAST VISIBLE LINE of the tooltip
    description, the correct item's suffix at that line boundary should score
    highest.  The best suffix score becomes the item's overall score.

    Returns up to top_n candidates sorted by score descending, each with:
        score, name, description, matched_suffix, normalized_ocr
    """
    if not ocr_text.strip() or not items:
        return []
    normalized_ocr = normalize_text(ocr_text)
    if not normalized_ocr:
        return []

    results = []
    for item in items:
        normalized_desc = normalize_text(item["description"])
        if not normalized_desc:
            continue
        words = normalized_desc.split()
        best_score = 0
        best_suffix = ""
        for i in range(len(words)):
            suffix = " ".join(words[i:])
            score = fuzz.ratio(normalized_ocr, suffix)
            if score > best_score:
                best_score = score
                best_suffix = suffix
        results.append({
            "score": best_score,
            "name": item["name"],
            "description": item["description"],
            "matched_suffix": best_suffix,
            "normalized_ocr": normalized_ocr,
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)[:top_n]


def choose_best_match(
    matches: List[Dict],
    threshold: float = FUZZY_MATCH_THRESHOLD,
) -> Optional[Dict]:
    """Return the top match only if its score meets the threshold, else None."""
    return matches[0] if matches and matches[0]["score"] >= threshold else None


# ---------------------------------------------------------------------------
# Debug helpers  (only called when debug=True)
# ---------------------------------------------------------------------------

def _save_debug_artifacts(
    image: np.ndarray,
    filename: str,
    anchor_top_left: Tuple[int, int],
    anchor_bottom_right: Tuple[int, int],
    second_anchor_pos: Optional[Tuple[int, int]],
    desc_tl: Tuple[int, int],
    desc_br: Tuple[int, int],
    passes_threshold: bool,
    ocr_results: Dict,
    output_dir: str,
    line2_tl: Optional[Tuple[int, int]] = None,
    line2_br: Optional[Tuple[int, int]] = None,
    ocr2_results: Optional[Dict] = None,
) -> None:
    """Save an annotated debug image, the OCR crop, and per-variant preprocessed images."""
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(filename)[0]
    annotated = image.copy()

    # First anchor box
    color = _MATCH_COLOR if passes_threshold else _WEAK_MATCH_COLOR
    cv2.rectangle(annotated, anchor_top_left, anchor_bottom_right, color, _RECT_THICKNESS)

    # Second anchor box + connecting line
    if second_anchor_pos:
        aw = anchor_bottom_right[0] - anchor_top_left[0]
        ah = anchor_bottom_right[1] - anchor_top_left[1]
        cv2.rectangle(annotated, second_anchor_pos,
                      (second_anchor_pos[0] + aw, second_anchor_pos[1] + ah),
                      (255, 255, 0), _RECT_THICKNESS)
        c1 = (anchor_top_left[0] + aw // 2, anchor_top_left[1] + ah // 2)
        c2 = (second_anchor_pos[0] + aw // 2, second_anchor_pos[1] + ah // 2)
        cv2.line(annotated, c1, c2, (0, 255, 255), 2)

    # Description region boxes (line 1, and line 2 above if present)
    cv2.rectangle(annotated, desc_tl, desc_br, _DESC_REGION_COLOR, _RECT_THICKNESS)
    if line2_tl is not None and line2_br is not None:
        cv2.rectangle(annotated, line2_tl, line2_br, _DESC_REGION_COLOR, _RECT_THICKNESS)
    cv2.imwrite(os.path.join(output_dir, f"debug_{filename}"), annotated)

    if ocr_results.get("cropped_region") is not None:
        cv2.imwrite(os.path.join(output_dir, f"crop_{base}.png"),
                    ocr_results["cropped_region"])

    if ocr2_results is not None and ocr2_results.get("cropped_region") is not None:
        cv2.imwrite(os.path.join(output_dir, f"crop_{base}_line2.png"),
                    ocr2_results["cropped_region"])

    for v in ocr_results.get("all_variants", []):
        vi = v.get("variant_image")
        if vi is not None:
            vname = v.get("variant_name", "unknown")
            cv2.imwrite(os.path.join(output_dir, f"variant_{base}_{vname}.png"), vi)


# ---------------------------------------------------------------------------
# PRIMARY SERVICE ENTRY POINT
# ---------------------------------------------------------------------------

def detect_item_from_image_path(
    image_path: str,
    template_dir: str,
    descriptions_csv_path: str,
    tesseract_cmd: Optional[str] = None,
    debug: bool = True,
    debug_output_dir: str = "./debug_output",
) -> Optional[Dict]:
    """
    Detect a RotMG item from a single screenshot file.

    Pipeline:
      1. Load templates + descriptions.
      2. Find the 'Feed Power:' anchor in the image.
      3. Crop the last line of the item description just above the anchor.
      4. OCR the crop using multiple preprocessing variants.
      5. Fuzzy-match the OCR text against description suffixes from the CSV.
      6. Return the best confident match, or None.

    Args:
        image_path:            Path to the screenshot to analyze.
        template_dir:          Directory containing anchor template image(s).
        descriptions_csv_path: Path to rotmg_item_descriptions.csv.
        tesseract_cmd:         Optional path to the Tesseract executable.
        debug:                 When True, print step-by-step logs and save
                               annotated debug images to debug_output_dir.
        debug_output_dir:      Where to write debug images (only used when
                               debug=True).

    Returns:
        On a confident match:
            {
                "item_name":      str,   # Matched item name from the CSV
                "score":          float, # Suffix match score (0-100)
                "matched_text":   str,   # Raw OCR text from the description line
                "matched_suffix": str,   # Description suffix that scored best
            }
        Returns None if the image cannot be read, no anchor is detected,
        OCR yields no usable text, or no candidate meets FUZZY_MATCH_THRESHOLD.
    """
    # --- Configure Tesseract if a path was provided ---
    if tesseract_cmd and os.path.exists(tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    # --- Load templates ---
    templates = load_template_images(template_dir)
    if not templates:
        if debug:
            print(f"[detect] No templates found in '{template_dir}'")
        return None

    # --- Load item descriptions ---
    item_descriptions = load_item_descriptions(descriptions_csv_path)
    if not item_descriptions:
        if debug:
            print(f"[detect] No item descriptions loaded from '{descriptions_csv_path}'")
        return None

    # --- Load image ---
    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        if debug:
            print(f"[detect] Could not read image: {image_path}")
        return None

    if debug:
        print(f"[detect] Processing: {os.path.basename(image_path)} "
              f"({image.shape[1]}x{image.shape[0]})")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # --- Locate anchor ---
    if debug:
        print("[detect] Locating 'Feed Power:' anchor...")
    template_name, confidence, top_left, bottom_right, second_anchor_pos, _, detected_scale = locate_anchor(
        gray, templates, debug=debug
    )

    if confidence < CONFIDENCE_THRESHOLD:
        if debug:
            print(f"[detect] Anchor not found (best conf={confidence:.4f})")
        return None

    if debug:
        print(f"[detect] Anchor '{template_name}' at {top_left} "
              f"(conf={confidence:.4f}, detected_scale={detected_scale:.2f})")

    # --- Calculate description region ---
    desc_tl, desc_br = calculate_desc_region(
        top_left, second_anchor_pos, scale=detected_scale, debug=debug
    )

    # --- Crop the description line, clamping to image bounds ---
    ih, iw = image.shape[:2]
    x1, y1 = max(0, desc_tl[0]), max(0, desc_tl[1])
    x2, y2 = min(iw, desc_br[0]), min(ih, desc_br[1])

    if x2 <= x1 or y2 <= y1:
        if debug:
            print("[detect] Description region crop is invalid (out of image bounds)")
        return None

    cropped = image[y1:y2, x1:x2]

    # --- OCR the description line (line 1 — bottom line) ---
    if debug:
        print("[detect] Running OCR on description region (line 1)...")
    ocr = ocr_desc_region(cropped, debug=debug)
    ocr["cropped_region"] = cropped  # attach so debug artifacts can save it

    if not ocr["success"] or not ocr["desc_last_line"].strip():
        if debug:
            print(f"[detect] OCR produced no usable text (error: {ocr.get('error')})")
            _save_debug_artifacts(image, os.path.basename(image_path),
                                  top_left, bottom_right, second_anchor_pos,
                                  desc_tl, desc_br, True, ocr, debug_output_dir)
        return None

    ocr_text = ocr["desc_last_line"]
    if debug:
        print(f"[detect] OCR line 1 text: '{ocr_text}' "
              f"(avg_conf={ocr['average_confidence']:.1f})")

    # --- OCR the line above the first description region (line 2) ---
    line_h = desc_br[1] - desc_tl[1]
    line2_tl = (desc_tl[0], desc_tl[1] - line_h - DESC_LINE_GAP)
    line2_br = (desc_br[0], desc_tl[1] - DESC_LINE_GAP)

    line2_x1, line2_y1 = max(0, line2_tl[0]), max(0, line2_tl[1])
    line2_x2, line2_y2 = min(iw, line2_br[0]), min(ih, line2_br[1])

    ocr2: Optional[Dict] = None
    ocr2_text = ""
    if line2_x2 > line2_x1 and line2_y2 > line2_y1:
        cropped2 = image[line2_y1:line2_y2, line2_x1:line2_x2]
        if debug:
            print("[detect] Running OCR on description region (line 2 — line above)...")
        ocr2 = ocr_desc_region(cropped2, debug=debug)
        ocr2["cropped_region"] = cropped2
        if ocr2["success"] and ocr2["desc_last_line"].strip():
            ocr2_text = ocr2["desc_last_line"]
            if debug:
                print(f"[detect] OCR line 2 text: '{ocr2_text}' "
                      f"(avg_conf={ocr2['average_confidence']:.1f})")
        elif debug:
            print("[detect] OCR line 2 produced no usable text; using single line only")
    elif debug:
        print("[detect] Line-above region is out of image bounds; using single line only")

    # Stitch in reading order (line above first), skipping empty results
    lines = [t for t in [ocr2_text, ocr_text] if t.strip()]
    stitched_ocr_text = " ".join(lines)
    if debug:
        print(f"[detect] Stitched OCR text: '{stitched_ocr_text}'")

    # --- Fuzzy-match against description suffixes ---
    if debug:
        print("[detect] Fuzzy-matching against description suffixes...")
    candidates = find_best_matches(stitched_ocr_text, item_descriptions)
    best = choose_best_match(candidates, FUZZY_MATCH_THRESHOLD)

    if debug:
        print("[detect] Top candidates:")
        for c in candidates:
            print(f"  score={c['score']:5.1f} | {c['name']}")
        print(f"[detect] Accepted: {best['name'] if best else 'None (below threshold)'}")
        _save_debug_artifacts(image, os.path.basename(image_path),
                              top_left, bottom_right, second_anchor_pos,
                              desc_tl, desc_br, True, ocr, debug_output_dir,
                              line2_tl=line2_tl, line2_br=line2_br, ocr2_results=ocr2)

    if best is None:
        return None

    return {
        "item_name": best["name"],
        "score": best["score"],
        "matched_text": stitched_ocr_text,
        "matched_suffix": best["matched_suffix"],
    }
