"""
Core logic for the "Resize for Print" tool: resizes posters to exactly
fill an 11x17 or 13x19 inch page at print resolution — no cropping, and
no white border/padding either. If the source image's proportions don't
already match the page, it's stretched slightly (width and height scaled
independently) to fit perfectly, rather than cropping or padding. Also
gently sharpens images that had to be upscaled to reach print resolution.
"""

from PIL import Image, ImageFilter

from imaging import cover_crop, stretch_fit, required_upscale_factor

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


def _sharpen_if_upscaled(img, factor):
    if factor > UPSCALE_WARN_THRESHOLD:
        # Counteract the softness introduced by upscaling. Strength scales
        # gently with how much upscaling happened, capped so it doesn't
        # turn into obvious oversharpening halos on extreme cases.
        percent = min(60 + factor * 25, 180)
        return img.filter(
            ImageFilter.UnsharpMask(radius=2.2, percent=int(percent), threshold=2)
        )
    return img


def resize_for_print(poster_path_or_image, size_key, dpi=PRINT_DPI):
    """
    Resizes the poster to exactly fill the page — NO cropping, and NO
    white border either. If the source proportions don't already match
    the page, it's stretched (width/height scaled independently) just
    enough to fit perfectly edge-to-edge.

    Returns (result_image, upscale_factor). upscale_factor > 1 means the
    source was smaller than the print target and had to be scaled up by
    that much (in its more demanding dimension) to fill the page.
    """
    if isinstance(poster_path_or_image, Image.Image):
        img = poster_path_or_image.convert("RGB")
    else:
        img = Image.open(poster_path_or_image).convert("RGB")

    target_w, target_h = target_pixels(size_key, dpi)
    factor = required_upscale_factor(img, target_w, target_h)

    result = stretch_fit(img, target_w, target_h)
    result = _sharpen_if_upscaled(result, factor)

    return result, factor


def fit_cover_for_print(poster_path_or_image, size_key, dpi=PRINT_DPI):
    """
    Fills the page completely edge-to-edge, cropping any overflow instead
    of padding. Used as the pre-fit step for tools like Framed Mockup,
    where the poster needs to fill a rectangle with no visible background
    showing through — cropping there is fine since it's just simulating
    a listing photo, not producing the actual print file.

    Returns (result_image, upscale_factor), same meaning as above.
    """
    if isinstance(poster_path_or_image, Image.Image):
        img = poster_path_or_image.convert("RGB")
    else:
        img = Image.open(poster_path_or_image).convert("RGB")

    target_w, target_h = target_pixels(size_key, dpi)
    factor = required_upscale_factor(img, target_w, target_h)

    result = cover_crop(img, target_w, target_h)
    result = _sharpen_if_upscaled(result, factor)

    return result, factor


def save_jpeg(img, out_path, quality=95):
    img.save(out_path, "JPEG", quality=quality, optimize=True)
