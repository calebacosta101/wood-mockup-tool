"""
Poster Tools
------------
A simple password-protected webpage with four tools:
  1. Wood Mockup — paste posters onto the wood background for listing photos.
  2. Resize for Print — resize posters to 11x17 or 13x19 for actual printing,
     upscaling (with light sharpening) if the source isn't high-res enough.
  3. Framed Mockup — warp posters into the framed wall photo for listing photos.
  4. Poster Catalog — permanent, searchable storage of every poster design,
     behind its own separate password.
"""

import io
import zipfile

import img2pdf
import streamlit as st
from PIL import Image

from mockup_core import load_background, make_mockup, CANVAS_SIZE
from resize_core import resize_for_print, fit_cover_for_print, PAGE_SIZES, UPSCALE_WARN_THRESHOLD, PRINT_DPI
from framed_core import load_room_background, make_framed_mockup
import catalog_core
import memory_guard
import shopify_publish
import theme

st.set_page_config(page_title="Poster Tools", page_icon="🪵", layout="centered")
theme.inject()

BACKGROUND_PATH = "wood_background.jpg"
ROOM_BACKGROUND_PATH = "room_background.png"


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


def build_pdf(files, dpi=PRINT_DPI):
    """Combines a list of (name, jpeg_bytes) into a single multi-page PDF,
    one page per image, at the given resolution — ready for batch printing.

    Uses img2pdf, which embeds the already-JPEG-encoded bytes directly into
    the PDF without decoding them back to raw pixels. Decoding every page's
    full print-resolution pixels at once (the previous Pillow-based
    approach) held 2-3GB+ in memory on large batches, which is what was
    crashing the app on Streamlit Cloud's memory limit.
    """
    layout_fun = img2pdf.get_fixed_dpi_layout_fun((dpi, dpi))
    pdf_bytes = img2pdf.convert([data for _, data in files], layout_fun=layout_fun)
    return io.BytesIO(pdf_bytes)


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
            stopped_early = False
            for i, uf in enumerate(uploaded_files):
                if memory_guard.over_limit():
                    stopped_early = True
                    break
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

            if stopped_early:
                st.error(
                    f"Stopped after {len(results)} of {len(uploaded_files)} images — "
                    "this batch was approaching the app's memory limit. Download what's "
                    "finished below, then run the rest as a separate batch."
                )
            else:
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
        "Upload your poster images below. Each one gets resized to "
        "completely fill the page at print resolution — no cropping, and "
        "no white border either. If a source image's proportions don't "
        "already match the page size exactly, it's stretched slightly to "
        "fit edge-to-edge rather than cropped or padded. If a source "
        "image is too low-res for a crisp print at that size, it's "
        "automatically upscaled and lightly sharpened — and flagged "
        "below so you know which ones to double check."
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

    if not uploaded_files and "resize_results" not in st.session_state:
        st.info("Upload one or more images to get started.")
        return

    if uploaded_files:
        st.write(f"{len(uploaded_files)} image(s) ready.")

        if len(uploaded_files) > 60:
            st.info(
                f"{len(uploaded_files)} images is a big batch. If this app runs low on "
                "memory partway through, it'll stop and let you download what's finished "
                "so far rather than losing the whole batch — but splitting into a few "
                "smaller batches avoids that entirely."
            )

        if st.button("Resize images", type="primary", key="resize_generate"):
            progress = st.progress(0.0, text="Starting...")

            results = []
            warnings = []
            stopped_early = False
            for i, uf in enumerate(uploaded_files):
                if memory_guard.over_limit():
                    stopped_early = True
                    break
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

            st.session_state["resize_results"] = results
            st.session_state["resize_warnings"] = warnings
            st.session_state["resize_size_key"] = size_key
            st.session_state["resize_stopped_early"] = stopped_early
            st.session_state["resize_total_uploaded"] = len(uploaded_files)
            # a fresh run invalidates any previously prepared downloads
            st.session_state.pop("resize_zip_bytes", None)
            st.session_state.pop("resize_pdf_bytes", None)

    if "resize_results" in st.session_state:
        results = st.session_state["resize_results"]
        warnings = st.session_state["resize_warnings"]
        used_size_key = st.session_state["resize_size_key"]
        total_uploaded = st.session_state["resize_total_uploaded"]

        if st.session_state["resize_stopped_early"]:
            st.error(
                f"Stopped after {len(results)} of {total_uploaded} images — this batch "
                "was approaching the app's memory limit. Download what's finished below, "
                "then run the rest as a separate batch."
            )
        else:
            st.success(f"Done! {len(results)} image(s) resized to {used_size_key}in.")

        if warnings:
            lines = "\n".join(
                f"- **{name}** — upscaled {factor:.1f}x, may look soft when printed"
                for name, factor in warnings
            )
            st.warning(
                "These source images were smaller than the print size and "
                "had to be stretched up:\n\n" + lines
            )

        # ZIP and PDF are built lazily, one at a time, on request — building
        # both eagerly (the old behavior) meant holding three full copies of
        # the batch in memory at once (resized images + zip + pdf), which is
        # exactly what large batches don't have room for.
        dl_col1, dl_col2 = st.columns(2)

        with dl_col1:
            if "resize_zip_bytes" in st.session_state:
                st.download_button(
                    "⬇️ Download all as ZIP",
                    data=st.session_state["resize_zip_bytes"],
                    file_name=f"resized_{used_size_key}.zip",
                    mime="application/zip",
                    type="primary",
                    key="resize_download",
                    width="stretch",
                )
            elif st.button("📦 Prepare ZIP", key="resize_prep_zip", width="stretch"):
                # Keeping both a prepared ZIP and a prepared PDF cached at
                # once roughly doubles this step's memory cost for no
                # benefit on a big batch, so preparing one evicts the other.
                st.session_state.pop("resize_pdf_bytes", None)
                st.session_state["resize_zip_bytes"] = build_zip(results).getvalue()
                st.rerun()

        with dl_col2:
            if "resize_pdf_bytes" in st.session_state:
                st.download_button(
                    "⬇️ Download all as PDF",
                    data=st.session_state["resize_pdf_bytes"],
                    file_name=f"resized_{used_size_key}_print_batch.pdf",
                    mime="application/pdf",
                    key="resize_download_pdf",
                    width="stretch",
                )
            elif st.button("📄 Prepare PDF", key="resize_prep_pdf", width="stretch"):
                st.session_state.pop("resize_zip_bytes", None)
                st.session_state["resize_pdf_bytes"] = build_pdf(results).getvalue()
                st.rerun()

        if len(results) > 35:
            st.caption(
                "Large batch — preparing ZIP or PDF replaces whichever one was "
                "previously ready, to keep memory usage safe. Download one before "
                "preparing the other if you need both."
            )

        st.write("Preview:")
        cols = st.columns(3)
        for idx, (name, data) in enumerate(results[:9]):
            cols[idx % 3].image(data, caption=name, width="stretch")
        if len(results) > 9:
            st.caption(f"...and {len(results) - 9} more in the zip.")


# ---------------------------------------------------------------------------
# Tab 3: Framed Mockup
# ---------------------------------------------------------------------------
def framed_mockup_tab():
    st.write(
        "Upload your poster images below. Each one is fit to the chosen print "
        "size (upscaled and lightly sharpened if needed, same as the Resize "
        "tool) and warped into the frame on the wall photo — including its "
        "slight camera-angle tilt, so it sits naturally instead of looking "
        "pasted flat on top."
    )

    size_key = st.radio(
        "Poster size",
        options=list(PAGE_SIZES.keys()),
        horizontal=True,
        key="framed_size",
    )

    uploaded_files = st.file_uploader(
        "Poster images",
        type=["png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp"],
        accept_multiple_files=True,
        key="framed_uploader",
    )

    quality = st.slider(
        "JPEG quality (higher = bigger file, better quality)",
        min_value=70, max_value=100, value=92,
        key="framed_quality",
    )

    if uploaded_files:
        st.write(f"{len(uploaded_files)} image(s) ready.")

        if st.button("Generate framed mockups", type="primary", key="framed_generate"):
            progress = st.progress(0.0, text="Starting...")
            background = load_room_background(ROOM_BACKGROUND_PATH)

            results = []
            warnings = []
            stopped_early = False
            for i, uf in enumerate(uploaded_files):
                if memory_guard.over_limit():
                    stopped_early = True
                    break
                try:
                    poster = Image.open(uf)
                    # bring it to true print dimensions first (filling the
                    # rectangle completely, with upscale + sharpen if
                    # needed), then warp that into the frame
                    fitted, factor = fit_cover_for_print(poster, size_key)
                    framed = make_framed_mockup(fitted, background)

                    out_buf = io.BytesIO()
                    framed.save(out_buf, "JPEG", quality=quality, optimize=True)
                    out_buf.seek(0)

                    base_name = uf.name.rsplit(".", 1)[0]
                    out_name = f"{base_name}_framed.jpg"
                    results.append((out_name, out_buf.getvalue()))

                    if factor > UPSCALE_WARN_THRESHOLD:
                        warnings.append((uf.name, factor))
                except Exception as e:
                    st.warning(f"Skipped {uf.name}: {e}")

                progress.progress(
                    (i + 1) / len(uploaded_files),
                    text=f"Processed {i + 1} of {len(uploaded_files)}",
                )

            if stopped_early:
                st.error(
                    f"Stopped after {len(results)} of {len(uploaded_files)} images — "
                    "this batch was approaching the app's memory limit. Download what's "
                    "finished below, then run the rest as a separate batch."
                )
            else:
                st.success(f"Done! {len(results)} framed mockup(s) generated.")

            if warnings:
                lines = "\n".join(
                    f"- **{name}** — upscaled {factor:.1f}x, may look soft up close"
                    for name, factor in warnings
                )
                st.warning(
                    "These source images were smaller than the chosen print size "
                    "and had to be stretched up:\n\n" + lines
                )

            zip_buffer = build_zip(results)
            st.download_button(
                "⬇️ Download all as ZIP",
                data=zip_buffer,
                file_name="framed_mockups.zip",
                mime="application/zip",
                type="primary",
                key="framed_download",
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
# Tab 4: Poster Catalog
# ---------------------------------------------------------------------------
def catalog_password_gate():
    """Separate shared-password gate for the catalog, independent of the
    main app password. Uses its own session_state key so unlocking the
    catalog doesn't unlock/affect the rest of the app or vice versa."""
    def entered():
        if st.session_state.get("catalog_password") == st.secrets.get("CATALOG_PASSWORD", ""):
            st.session_state["catalog_password_ok"] = True
            del st.session_state["catalog_password"]
        else:
            st.session_state["catalog_password_ok"] = False

    if st.session_state.get("catalog_password_ok"):
        return True

    st.text_input(
        "Catalog password", type="password", on_change=entered, key="catalog_password"
    )
    if st.session_state.get("catalog_password_ok") is False:
        st.error("Incorrect password.")
    return False


def _catalog_config():
    repo = st.secrets.get("GITHUB_REPO", "")
    token = st.secrets.get("GITHUB_TOKEN", "")
    branch = st.secrets.get("GITHUB_BRANCH", "main")
    return repo, token, branch


def _load_catalog_entries(repo, token, branch, force=False):
    if force or "catalog_entries" not in st.session_state:
        try:
            entries, sha = catalog_core.get_index(repo, token, branch)
            st.session_state["catalog_entries"] = entries
            st.session_state["catalog_sha"] = sha
        except catalog_core.CatalogError as e:
            st.error(str(e))
            st.session_state["catalog_entries"] = st.session_state.get("catalog_entries", [])
    return st.session_state.get("catalog_entries", [])


def _get_image_bytes(repo, token, branch, path):
    """Fetches + caches image bytes per path in session_state so switching
    tabs / searching doesn't re-hit the GitHub API for every thumbnail on
    every rerun."""
    cache = st.session_state.setdefault("catalog_image_cache", {})
    if path not in cache:
        try:
            cache[path] = catalog_core.fetch_image_bytes(repo, token, path, branch)
        except catalog_core.CatalogError:
            cache[path] = None
    return cache[path]


def catalog_tab():
    if not catalog_password_gate():
        return

    repo, token, branch = _catalog_config()
    if not repo or not token:
        st.warning(
            "The catalog isn't fully set up yet — it needs `GITHUB_REPO` and "
            "`GITHUB_TOKEN` added under the app's Settings → Secrets."
        )
        return

    st.write(
        "Every poster added here is stored permanently and can be searched by "
        "name or keyword. Add new designs below, or search and download "
        "existing ones."
    )

    col_search, col_refresh = st.columns([4, 1])
    with col_search:
        query = st.text_input("Search by name or keyword", key="catalog_search")
    with col_refresh:
        st.write("")
        st.write("")
        if st.button("🔄 Refresh", key="catalog_refresh", width="stretch"):
            _load_catalog_entries(repo, token, branch, force=True)
            st.rerun()

    entries = _load_catalog_entries(repo, token, branch)
    results = catalog_core.search(entries, query)

    st.caption(f"{len(results)} of {len(entries)} poster(s) shown.")

    if results:
        cols = st.columns(3)
        ordered = sorted(results, key=lambda e: e.get("added", ""), reverse=True)
        for idx, entry in enumerate(ordered):
            col = cols[idx % 3]
            with col:
                img_bytes = _get_image_bytes(repo, token, branch, entry["path"])
                if img_bytes:
                    st.image(img_bytes, width="stretch")
                else:
                    st.caption("(image unavailable)")

                edit_key = f"catalog_editing_{entry['id']}"
                confirm_key = f"catalog_confirm_delete_{entry['id']}"
                is_editing = st.session_state.get(edit_key, False)

                if is_editing:
                    edited_name = st.text_input(
                        "Name", value=entry["name"], key=f"catalog_edit_name_{entry['id']}"
                    )
                    edited_keywords = st.text_input(
                        "Keywords", value=entry.get("keywords", ""),
                        key=f"catalog_edit_kw_{entry['id']}",
                    )
                    ecol1, ecol2 = st.columns(2)
                    if ecol1.button("Save", key=f"catalog_edit_save_{entry['id']}", type="primary", width="stretch"):
                        if not edited_name.strip():
                            st.error("Name can't be empty.")
                        else:
                            try:
                                catalog_core.update_poster(
                                    repo, token, entry["id"],
                                    edited_name.strip(), edited_keywords.strip(), branch,
                                )
                                _load_catalog_entries(repo, token, branch, force=True)
                                st.session_state[edit_key] = False
                                st.success("Updated.")
                                st.rerun()
                            except catalog_core.CatalogError as e:
                                st.error(str(e))
                    if ecol2.button("Cancel", key=f"catalog_edit_cancel_{entry['id']}", width="stretch"):
                        st.session_state[edit_key] = False
                        st.rerun()
                else:
                    st.markdown(f"**{entry['name']}**")
                    if entry.get("keywords"):
                        st.caption(entry["keywords"])
                    st.caption(f"Added {entry.get('added', '?')}")

                    if img_bytes:
                        st.download_button(
                            "⬇️ Download",
                            data=img_bytes,
                            file_name=entry["path"].rsplit("/", 1)[-1],
                            key=f"catalog_dl_{entry['id']}",
                            width="stretch",
                        )

                    if st.session_state.get(confirm_key):
                        st.warning("Delete this poster permanently?")
                        dcol1, dcol2 = st.columns(2)
                        if dcol1.button("Yes, delete", key=f"catalog_delete_yes_{entry['id']}", width="stretch"):
                            try:
                                catalog_core.delete_poster(repo, token, entry, branch)
                                st.session_state.get("catalog_image_cache", {}).pop(entry["path"], None)
                                _load_catalog_entries(repo, token, branch, force=True)
                                st.session_state[confirm_key] = False
                                st.success(f"Deleted '{entry['name']}'.")
                                st.rerun()
                            except catalog_core.CatalogError as e:
                                st.error(str(e))
                        if dcol2.button("Cancel", key=f"catalog_delete_cancel_{entry['id']}", width="stretch"):
                            st.session_state[confirm_key] = False
                            st.rerun()
                    else:
                        bcol1, bcol2 = st.columns(2)
                        if bcol1.button("✏️ Edit", key=f"catalog_edit_{entry['id']}", width="stretch"):
                            st.session_state[edit_key] = True
                            st.rerun()
                        if bcol2.button("🗑️ Delete", key=f"catalog_delete_{entry['id']}", width="stretch"):
                            st.session_state[confirm_key] = True
                            st.rerun()

                st.write("---")
    else:
        st.info("No posters match that search." if entries else "No posters in the catalog yet — add one below.")

    st.divider()
    st.subheader("Add posters")
    st.caption(
        "Select one image to name it yourself, or select several at once "
        "to bulk-upload — bulk uploads are named from their filenames "
        "automatically, and you can rename any of them afterward with the "
        "✏️ Edit button on its card."
    )

    with st.form("catalog_add_form", clear_on_submit=True):
        new_files = st.file_uploader(
            "Poster image(s)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="catalog_new_files",
        )
        new_name = st.text_input(
            "Name (only used when uploading a single image)", key="catalog_new_name"
        )
        new_keywords = st.text_input(
            "Keywords (comma-separated, optional — applied to all images uploaded here)",
            key="catalog_new_keywords",
        )
        submitted = st.form_submit_button("Add to catalog", type="primary")

        if submitted:
            if not new_files:
                st.error("Please choose at least one image.")
            else:
                keywords = new_keywords.strip()
                if len(new_files) == 1:
                    f = new_files[0]
                    name = new_name.strip() or catalog_core.guess_name_from_filename(f.name)
                    items = [{
                        "name": name, "keywords": keywords,
                        "image_bytes": f.getvalue(), "orig_filename": f.name,
                    }]
                else:
                    items = [
                        {
                            "name": catalog_core.guess_name_from_filename(f.name),
                            "keywords": keywords,
                            "image_bytes": f.getvalue(),
                            "orig_filename": f.name,
                        }
                        for f in new_files
                    ]
                try:
                    added = catalog_core.add_posters_bulk(repo, token, items, branch)
                    _load_catalog_entries(repo, token, branch, force=True)
                    if len(added) == 1:
                        st.success(f"Added '{added[0]['name']}' to the catalog.")
                    else:
                        st.success(f"Added {len(added)} posters to the catalog.")
                    st.rerun()
                except catalog_core.CatalogError as e:
                    st.error(str(e))


# ---------------------------------------------------------------------------
# Tab 5: Shopify Listings
# ---------------------------------------------------------------------------
def _shopify_config():
    shop_domain = st.secrets.get("SHOPIFY_SHOP_DOMAIN", "")
    access_token = st.secrets.get("SHOPIFY_ACCESS_TOKEN", "")
    return shop_domain, access_token


def shopify_tab():
    shop_domain, access_token = _shopify_config()
    if not shop_domain or not access_token:
        st.warning(
            "Shopify isn't connected yet — this needs `SHOPIFY_SHOP_DOMAIN` and "
            "`SHOPIFY_ACCESS_TOKEN` added under the app's Settings → Secrets. "
            "Run `shopify_oauth_setup.py` locally once to get those values."
        )
        return

    st.write(
        "Upload the image(s) for a listing, fill in the details, and push it "
        "straight to Shopify as a new product."
    )

    uploaded_files = st.file_uploader(
        "Listing images (first one becomes the main product photo)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="shopify_uploader",
    )

    if uploaded_files:
        cols = st.columns(min(len(uploaded_files), 4))
        for idx, f in enumerate(uploaded_files):
            cols[idx % len(cols)].image(f.getvalue(), width="stretch")

    title = st.text_input("Title", key="shopify_title")
    description = st.text_area("Description", key="shopify_description", height=120)

    price_col, tags_col = st.columns([1, 2])
    price = price_col.number_input("Price ($)", min_value=0.0, step=1.0, format="%.2f", key="shopify_price")
    tags = tags_col.text_input("Tags (comma-separated)", key="shopify_tags")

    status = st.radio(
        "Status",
        options=["draft", "active"],
        format_func=lambda s: "Draft (review in Shopify before publishing)" if s == "draft" else "Active (goes live immediately)",
        key="shopify_status",
    )

    if st.button("🛒 Push to Shopify", type="primary", key="shopify_publish_button"):
        if not uploaded_files:
            st.error("Add at least one image.")
        elif not title.strip():
            st.error("Title is required.")
        elif price <= 0:
            st.error("Price must be greater than $0.")
        else:
            images = [(f.name, f.getvalue()) for f in uploaded_files]
            try:
                with st.spinner("Publishing to Shopify..."):
                    product, admin_url = shopify_publish.create_product(
                        shop_domain,
                        access_token,
                        title=title.strip(),
                        description=description.strip(),
                        price=price,
                        tags=tags.strip(),
                        images=images,
                        status=status,
                    )
                st.success(f"Published '{product['title']}' as {status}.")
                st.markdown(f"[View in Shopify admin]({admin_url})")
            except shopify_publish.ShopifyPublishError as e:
                st.error(str(e))
    else:
        if not uploaded_files:
            st.info("Upload one or more images to get started.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
theme.eyebrow("POSTER TOOLS · UTILITIES")
st.title("Print & mockup toolkit")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🪵 Wood Mockup", "📐 Resize for Print", "🖼️ Framed Mockup", "🗂️ Poster Catalog", "🛒 Shopify Listings"]
)

with tab1:
    wood_mockup_tab()

with tab2:
    resize_tab()

with tab3:
    framed_mockup_tab()

with tab4:
    catalog_tab()

with tab5:
    shopify_tab()
