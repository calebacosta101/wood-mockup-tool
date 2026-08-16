"""
Core image logic for the wood-background poster mockup tool.
Shared by the Streamlit app and can be run standalone for testing.
"""

from PIL import Image, ImageFilter, ImageDraw
import io

# --- Frame placement, measured from the sample mockup you provided ---
# (as fractions of the canvas, so it scales to any output resolution)
FRAME_LEFT = 0.20625
FRAME_RIGHT = 0.79219
FRAME_TOP = 0.08438
FRAME_BOTTOM = 0.91563

# Output canvas size (square, matches your sample mockup's proportions).
# 2000px is a solid resolution for Etsy/marketplace listing photos.
CANVAS_SIZE = 2000

SHADOW_BLUR = 26
SHADOW_OFFSET = (10, 22)   # (x, y) — shadow drifts slightly down-right
SHADOW_OPACITY = 90        # 0-255


def cover_crop(img, target_w, target_h):
    """Resize `img` to completely fill target_w x target_h, cropping the overflow
    from the center. Guarantees no gaps/borders, regardless of aspect ratio."""
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        new_h = target_h
        new_w = max(target_w, round(src_ratio * new_h))
    else:
        new_w = target_w
        new_h = max(target_h, round(new_w / src_ratio))

    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def load_background(bg_path, canvas_size=CANVAS_SIZE):
    bg = Image.open(bg_path).convert("RGB")
    return cover_crop(bg, canvas_size, canvas_size)


def make_mockup(poster_path_or_image, background, canvas_size=CANVAS_SIZE):
    """
    poster_path_or_image: file path or PIL Image of the raw poster artwork
    background: a pre-loaded PIL Image (canvas_size x canvas_size), from load_background()
    Returns a PIL Image (RGB) of the finished mockup.
    """
    if isinstance(poster_path_or_image, Image.Image):
        poster = poster_path_or_image.convert("RGB")
    else:
        poster = Image.open(poster_path_or_image).convert("RGB")

    left = round(FRAME_LEFT * canvas_size)
    right = round(FRAME_RIGHT * canvas_size)
    top = round(FRAME_TOP * canvas_size)
    bottom = round(FRAME_BOTTOM * canvas_size)
    frame_w, frame_h = right - left, bottom - top

    poster_fit = cover_crop(poster, frame_w, frame_h)

    canvas = background.copy()

    # --- soft drop shadow ---
    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    sx, sy = SHADOW_OFFSET
    shadow_draw.rectangle(
        [left + sx, top + sy, right + sx, bottom + sy],
        fill=(0, 0, 0, SHADOW_OPACITY),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow_layer)

    # --- paste the poster on top ---
    canvas.paste(poster_fit, (left, top))

    return canvas.convert("RGB")


def save_jpeg(img, out_path, quality=92):
    img.save(out_path, "JPEG", quality=quality, optimize=True)
