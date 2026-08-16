"""
Wood Mockup Generator
----------------------
A simple password-protected webpage: upload poster images in bulk, each one
gets resized (11x17 proportions) and pasted onto the wood background, and
you download a single zip of finished JPEGs.

Deployment: see README.md in this folder.
"""

import io
import zipfile

import streamlit as st
from PIL import Image

from mockup_core import load_background, make_mockup, CANVAS_SIZE

st.set_page_config(page_title="Wood Mockup Generator", page_icon="🪵", layout="centered")

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
# Main app
# ---------------------------------------------------------------------------
st.title("🪵 Wood Mockup Generator")
st.write(
    "Upload your poster images below (as many as you like). Each one will be "
    "resized to fit an 11x17 poster shape and pasted onto the wood background. "
    "When it's done, download the zip file with all the finished images."
)

uploaded_files = st.file_uploader(
    "Poster images",
    type=["png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp"],
    accept_multiple_files=True,
)

quality = st.slider(
    "JPEG quality (higher = bigger file, better quality)",
    min_value=70, max_value=100, value=92,
)

if uploaded_files:
    st.write(f"{len(uploaded_files)} image(s) ready.")

    if st.button("Generate mockups", type="primary"):
        progress = st.progress(0.0, text="Starting...")
        background = load_background(BACKGROUND_PATH, CANVAS_SIZE)

        zip_buffer = io.BytesIO()
        results = []

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, uf in enumerate(uploaded_files):
                try:
                    poster = Image.open(uf)
                    mockup = make_mockup(poster, background, CANVAS_SIZE)

                    out_buf = io.BytesIO()
                    mockup.save(out_buf, "JPEG", quality=quality, optimize=True)
                    out_buf.seek(0)

                    base_name = uf.name.rsplit(".", 1)[0]
                    out_name = f"{base_name}_mockup.jpg"
                    zf.writestr(out_name, out_buf.getvalue())
                    results.append((out_name, out_buf.getvalue()))
                except Exception as e:
                    st.warning(f"Skipped {uf.name}: {e}")

                progress.progress(
                    (i + 1) / len(uploaded_files),
                    text=f"Processed {i + 1} of {len(uploaded_files)}",
                )

        zip_buffer.seek(0)
        st.success(f"Done! {len(results)} mockup(s) generated.")

        st.download_button(
            "⬇️ Download all as ZIP",
            data=zip_buffer,
            file_name="wood_mockups.zip",
            mime="application/zip",
            type="primary",
        )

        st.write("Preview:")
        cols = st.columns(3)
        for idx, (name, data) in enumerate(results[:9]):
            cols[idx % 3].image(data, caption=name, width="stretch")
        if len(results) > 9:
            st.caption(f"...and {len(results) - 9} more in the zip.")
else:
    st.info("Upload one or more images to get started.")
