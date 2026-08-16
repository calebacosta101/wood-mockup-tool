"""
Core logic for the "Framed Mockup" tool: warps a poster into the blank
frame on the room-scene background photo. The frame corners were measured
directly from the reference photo (there's a slight camera-perspective
tilt to it, so this uses a real 4-point warp rather than a flat paste).
"""

import cv2
import numpy as np
from PIL import Image

from imaging import cover_crop

# --- Frame interior corners, measured from the reference room photo ---
# stored as fractions of the background image size so they scale to any
# resolution of that same photo.
FRAME_CORNERS_FRAC = {
    "tl": (0.58794, 0.15625),
    "tr": (0.73256, 0.15039),
    "br": (0.73328, 0.55339),
    "bl": (0.58757, 0.55273),
}


def load_room_background(bg_path):
    return Image.open(bg_path).convert("RGB")


def _corners_px(bg_size):
    w, h = bg_size
    return {k: (fx * w, fy * h) for k, (fx, fy) in FRAME_CORNERS_FRAC.items()}


def make_framed_mockup(poster_path_or_image, background):
    """
    poster_path_or_image: file path or PIL Image of the raw poster artwork
    background: pre-loaded PIL Image of the room scene
    Returns a PIL Image (RGB) of the finished composite.
    """
    if isinstance(poster_path_or_image, Image.Image):
        poster = poster_path_or_image.convert("RGB")
    else:
        poster = Image.open(poster_path_or_image).convert("RGB")

    bg_w, bg_h = background.size
    c = _corners_px((bg_w, bg_h))
    tl, tr, br, bl = c["tl"], c["tr"], c["br"], c["bl"]

    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    src_w = round((dist(tl, tr) + dist(bl, br)) / 2)
    src_h = round((dist(tl, bl) + dist(tr, br)) / 2)
    src_w, src_h = max(src_w, 2), max(src_h, 2)

    # fill that rectangle with the poster (no gaps, cropped to fit)
    poster_fit = cover_crop(poster, src_w, src_h)
    poster_np = np.array(poster_fit)  # RGB

    src_pts = np.float32([[0, 0], [src_w, 0], [src_w, src_h], [0, src_h]])
    dst_pts = np.float32([tl, tr, br, bl])
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

    warped = cv2.warpPerspective(
        poster_np, matrix, (bg_w, bg_h),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_TRANSPARENT,
    )

    # build a matching mask (white quad) so we only composite inside the frame
    mask_src = np.full((src_h, src_w), 255, dtype=np.uint8)
    mask_warped = cv2.warpPerspective(mask_src, matrix, (bg_w, bg_h))
    # feather the mask edge by 1-2px for a clean blend against the frame
    mask_warped = cv2.GaussianBlur(mask_warped, (3, 3), 0)
    mask_norm = (mask_warped.astype(np.float32) / 255.0)[..., None]

    bg_np = np.array(background).astype(np.float32)
    warped_f = warped.astype(np.float32)
    composite = bg_np * (1 - mask_norm) + warped_f * mask_norm
    composite = np.clip(composite, 0, 255).astype(np.uint8)

    return Image.fromarray(composite, "RGB")


def save_jpeg(img, out_path, quality=92):
    img.save(out_path, "JPEG", quality=quality, optimize=True)
