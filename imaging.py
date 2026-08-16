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
