"""
Poster Tools
------------
A simple password-protected webpage with two tools:
  1. Wood Mockup — paste posters onto the wood background for listing photos.
  2. Resize for Print — resize posters to 11x17 or 13x19 for actual printing,
     upscaling (with light sharpening) if the source isn't high-res enough.
"""

import io
import zipfile

import streamlit as st
from PIL import Image

from mockup_core import load_background, make_mockup, CANVAS_SIZE
from resize_core import resize_for_print, PAGE_SIZES, UPSCALE_WARN_THRESHOLD

st.set_page_config(page_title="Poster Tools", page_icon="🪵", layout="centered")

BACKGROUND_PATH = "wood_background.jpg"


# ---------------------------------------------------------------------------
# Password gate
# ---------------------------------------------------------------------------
def check_password():
    """Simple shared-password gate using Streamlit secrets."""
    def password_entered():
        if st.session_state.get("password") == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["password_ok"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_ok"] = False

    if st.session_state.get("password_ok"):
        return True

    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if st.session_state.get("password_ok") is False:
        st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()


# ---------------------------------------------------------------------------
# Shared helper: build a zip from a list of (name, bytes)
# ---------------------------------------------------------------------------
def build_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files:
            zf.writestr(name, data)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Tab 1: Wood Mockup
# ---------------------------------------------------------------------------
def wood_mockup_tab():
    st.write(
        "Upload your poster images below (as many as you like). Each one will be "
        "resized to fit an 11x17 poster shape and pasted onto the wood background. "
        "When it's done, download the zip file with all the finished images."
    )

    uploaded_files = st.file_uploader(
        "Poster images",
        type=["png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp"],
        accept_multiple_files=True,
        key="mockup_uploader",
    )

    quality = st.slider(
        "JPEG quality (higher = bigger file, better quality)",
        min_value=70, max_value=100, value=92,
        key="mockup_quality",
    )

    if uploaded_files:
        st.write(f"{len(uploaded_files)} image(s) ready.")

        if st.button("Generate mockups", type="primary", key="mockup_generate"):
            progress = st.progress(0.0, text="Starting...")
            background = load_background(BACKGROUND_PATH, CANVAS_SIZE)

            results = []
            for i, uf in enumerate(uploaded_files):
                try:
                    poster = Image.open(uf)
                    mockup = make_mockup(poster, background, CANVAS_SIZE)

                    out_buf = io.BytesIO()
                    mockup.save(out_buf, "JPEG", quality=quality, optimize=True)
                    out_buf.seek(0)

                    base_name = uf.name.rsplit(".", 1)[0]
                    out_name = f"{base_name}_mockup.jpg"
                    results.append((out_name, out_buf.getvalue()))
                except Exception as e:
                    st.warning(f"Skipped {uf.name}: {e}")

                progress.progress(
                    (i + 1) / len(uploaded_files),
                    text=f"Processed {i + 1} of {len(uploaded_files)}",
                )

            st.success(f"Done! {len(results)} mockup(s) generated.")

            zip_buffer = build_zip(results)
            st.download_button(
                "⬇️ Download all as ZIP",
                data=zip_buffer,
                file_name="wood_mockups.zip",
                mime="application/zip",
                type="primary",
                key="mockup_download",
            )

            st.write("Preview:")
            cols = st.columns(3)
            for idx, (name, data) in enumerate(results[:9]):
                cols[idx % 3].image(data, caption=name, width="stretch")
            if len(results) > 9:
                st.caption(f"...and {len(results) - 9} more in the zip.")
    else:
        st.info("Upload one or more images to get started.")


# ---------------------------------------------------------------------------
# Tab 2: Resize for Print
# ---------------------------------------------------------------------------
def resize_tab():
    st.write(
        "Upload your poster images below. Each one gets resized to fill the "
        "page edge-to-edge (no white borders) at print resolution. If a "
        "source image is too low-res for a crisp print at that size, it's "
        "automatically upscaled and lightly sharpened — and flagged below "
        "so you know which ones to double check."
    )

    size_key = st.radio(
        "Print size",
        options=list(PAGE_SIZES.keys()),
        horizontal=True,
        key="resize_size",
    )

    uploaded_files = st.file_uploader(
        "Poster images",
        type=["png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp"],
        accept_multiple_files=True,
        key="resize_uploader",
    )

    quality = st.slider(
        "JPEG quality (higher = bigger file, better quality)",
        min_value=80, max_value=100, value=95,
        key="resize_quality",
    )

    if uploaded_files:
        st.write(f"{len(uploaded_files)} image(s) ready.")

        if st.button("Resize images", type="primary", key="resize_generate"):
            progress = st.progress(0.0, text="Starting...")

            results = []
            warnings = []
            for i, uf in enumerate(uploaded_files):
                try:
                    poster = Image.open(uf)
                    resized, factor = resize_for_print(poster, size_key)

                    out_buf = io.BytesIO()
                    resized.save(out_buf, "JPEG", quality=quality, optimize=True)
                    out_buf.seek(0)

                    base_name = uf.name.rsplit(".", 1)[0]
                    out_name = f"{base_name}_{size_key}.jpg"
                    results.append((out_name, out_buf.getvalue()))

                    if factor > UPSCALE_WARN_THRESHOLD:
                        warnings.append((uf.name, factor))
                except Exception as e:
                    st.warning(f"Skipped {uf.name}: {e}")

                progress.progress(
                    (i + 1) / len(uploaded_files),
                    text=f"Processed {i + 1} of {len(uploaded_files)}",
                )

            st.success(f"Done! {len(results)} image(s) resized to {size_key}in.")

            if warnings:
                lines = "\n".join(
                    f"- **{name}** — upscaled {factor:.1f}x, may look soft when printed"
                    for name, factor in warnings
                )
                st.warning(
                    "These source images were smaller than the print size and "
                    "had to be stretched up:\n\n" + lines
                )

            zip_buffer = build_zip(results)
            st.download_button(
                "⬇️ Download all as ZIP",
                data=zip_buffer,
                file_name=f"resized_{size_key}.zip",
                mime="application/zip",
                type="primary",
                key="resize_download",
            )

            st.write("Preview:")
            cols = st.columns(3)
            for idx, (name, data) in enumerate(results[:9]):
                cols[idx % 3].image(data, caption=name, width="stretch")
            if len(results) > 9:
                st.caption(f"...and {len(results) - 9} more in the zip.")
    else:
        st.info("Upload one or more images to get started.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.title("Poster Tools")

tab1, tab2 = st.tabs(["🪵 Wood Mockup", "📐 Resize for Print"])

with tab1:
    wood_mockup_tab()

with tab2:
    resize_tab()
