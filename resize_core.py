"""
Core logic for the "Resize for Print" tool: fills an 11x17 or 13x19 inch
page borderlessly, and gently sharpens images that had to be upscaled
to reach print resolution.
"""

from PIL import Image, ImageFilter

from imaging import cover_crop, required_upscale_factor

PRINT_DPI = 300

PAGE_SIZES = {
    "11x17": (11, 17),
    "13x19": (13, 19),
}

# Above this upscale factor, the image is being stretched noticeably
# beyond its native resolution — we apply a mild unsharp mask to help
# counter the softness that introduces, and the app flags it visibly.
UPSCALE_WARN_THRESHOLD = 1.15


def target_pixels(size_key, dpi=PRINT_DPI):
    w_in, h_in = PAGE_SIZES[size_key]
    return round(w_in * dpi), round(h_in * dpi)


def resize_for_print(poster_path_or_image, size_key, dpi=PRINT_DPI):
    """
    Returns (result_image, upscale_factor).
    upscale_factor > 1 means the source was smaller than the print target
    and had to be stretched up by that much to fill the page.
    """
    if isinstance(poster_path_or_image, Image.Image):
        img = poster_path_or_image.convert("RGB")
    else:
        img = Image.open(poster_path_or_image).convert("RGB")

    target_w, target_h = target_pixels(size_key, dpi)
    factor = required_upscale_factor(img, target_w, target_h)

    result = cover_crop(img, target_w, target_h)

    if factor > UPSCALE_WARN_THRESHOLD:
        # Counteract the softness introduced by upscaling. Strength scales
        # gently with how much upscaling happened, capped so it doesn't
        # turn into obvious oversharpening halos on extreme cases.
        percent = min(60 + factor * 25, 180)
        result = result.filter(
            ImageFilter.UnsharpMask(radius=2.2, percent=int(percent), threshold=2)
        )

    return result, factor


def save_jpeg(img, out_path, quality=95):
    img.save(out_path, "JPEG", quality=quality, optimize=True)
