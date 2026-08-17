"""Shared low-level image helpers used by both tools."""

from PIL import Image


def cover_crop(img, target_w, target_h):
    """Resize `img` to completely fill target_w x target_h, cropping the
    overflow from the center. Guarantees no gaps/borders, regardless of
    the source aspect ratio. Upscales (via LANCZOS) if the source is
    smaller than the target."""
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


def required_upscale_factor(img, target_w, target_h):
    """How much the image must be scaled up (via cover-crop) to fill the
    target box. <= 1.0 means no upscaling is needed (the source is already
    big enough); > 1.0 means it's being stretched beyond its native
    resolution by that factor."""
    src_w, src_h = img.size
    scale_w = target_w / src_w
    scale_h = target_h / src_h
    return max(scale_w, scale_h)


def contain_fit(img, target_w, target_h, bg_color=(255, 255, 255)):
    """Resize `img` to fit entirely within target_w x target_h WITHOUT
    cropping any part of it — the whole design stays in view. Preserves
    aspect ratio and pads any leftover space (when the source proportions
    don't exactly match the target) with bg_color so the result is exactly
    target_w x target_h. Upscales (via LANCZOS) if the source is smaller
    than the target."""
    src_w, src_h = img.size
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))

    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg_color)
    left = (target_w - new_w) // 2
    top = (target_h - new_h) // 2
    canvas.paste(resized, (left, top))
    return canvas


def required_contain_scale_factor(img, target_w, target_h):
    """How much the image must be scaled up to fit inside the target box
    via contain-fit — i.e. the limiting dimension's scale factor (the
    smaller of the two). <= 1.0 means no upscaling is needed."""
    src_w, src_h = img.size
    scale_w = target_w / src_w
    scale_h = target_h / src_h
    return min(scale_w, scale_h)


def stretch_fit(img, target_w, target_h):
    """Resizes `img` to exactly target_w x target_h by scaling width and
    height independently — completely fills the page with ZERO cropping
    and ZERO padding/border. The tradeoff: if the source proportions don't
    already match the target, the image is stretched slightly out of its
    original aspect ratio to make it fit exactly."""
    return img.resize((target_w, target_h), Image.LANCZOS)
