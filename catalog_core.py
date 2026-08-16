"""
Core logic for the Poster Catalog: stores poster images + searchable
metadata (name, keywords) permanently in the same GitHub repo the app
lives in, using GitHub's REST API directly (no extra service needed).

Storage layout in the repo:
  catalog/images/<slug>.<ext>   - the actual poster files
  catalog/index.json            - [{id, name, keywords, path, added}, ...]
"""

import base64
import re
import uuid
from datetime import datetime, timezone

import requests

API_ROOT = "https://api.github.com"
INDEX_PATH = "catalog/index.json"
IMAGES_DIR = "catalog/images"


class CatalogError(Exception):
    pass


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo_url(repo, path):
    return f"{API_ROOT}/repos/{repo}/contents/{path}"


def _slugify(name):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "poster"


def get_index(repo, token, branch="main"):
    """Returns (entries_list, sha_or_None). sha is None if index.json doesn't exist yet."""
    resp = requests.get(
        _repo_url(repo, INDEX_PATH), headers=_headers(token),
        params={"ref": branch}, timeout=20,
    )
    if resp.status_code == 404:
        return [], None
    if not resp.ok:
        raise CatalogError(f"Couldn't load catalog index ({resp.status_code}): {resp.text[:200]}")
    data = resp.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    import json
    entries = json.loads(content) if content.strip() else []
    return entries, data["sha"]


def _save_index(repo, token, entries, sha, branch="main", message="Update catalog index"):
    import json
    body = {
        "message": message,
        "content": base64.b64encode(json.dumps(entries, indent=2).encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha
    resp = requests.put(_repo_url(repo, INDEX_PATH), headers=_headers(token), json=body, timeout=30)
    if not resp.ok:
        raise CatalogError(f"Couldn't save catalog index ({resp.status_code}): {resp.text[:300]}")
    return resp.json()["content"]["sha"]


def guess_name_from_filename(filename):
    """Turns 'sunset_beach-v2.png' into 'Sunset Beach V2' as a friendly
    default name for bulk uploads — the user can always rename it after."""
    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    base = re.sub(r"[_\-]+", " ", base).strip()
    base = re.sub(r"\s+", " ", base)
    return base.title() if base else "Untitled Poster"


def add_posters_bulk(repo, token, items, branch="main"):
    """Uploads multiple images and appends all of them to the index in a
    single index save (one commit for the index, regardless of how many
    images), rather than re-reading/re-saving the index once per image.

    `items` is a list of dicts: {name, keywords, image_bytes, orig_filename}.
    Returns the list of new entries, in the same order as `items`.
    """
    new_entries = []
    for item in items:
        orig_filename = item["orig_filename"]
        name = item["name"]
        ext = orig_filename.rsplit(".", 1)[-1].lower() if "." in orig_filename else "jpg"
        poster_id = uuid.uuid4().hex[:10]
        slug = _slugify(name)
        image_path = f"{IMAGES_DIR}/{slug}-{poster_id}.{ext}"

        put_body = {
            "message": f"Add poster: {name}",
            "content": base64.b64encode(item["image_bytes"]).decode("ascii"),
            "branch": branch,
        }
        resp = requests.put(_repo_url(repo, image_path), headers=_headers(token), json=put_body, timeout=60)
        if not resp.ok:
            raise CatalogError(
                f"Couldn't upload '{orig_filename}' ({resp.status_code}): {resp.text[:300]}"
            )

        new_entries.append({
            "id": poster_id,
            "name": name,
            "keywords": item.get("keywords", ""),
            "path": image_path,
            "added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })

    entries, sha = get_index(repo, token, branch)
    entries.extend(new_entries)
    message = (
        f"Add poster to index: {new_entries[0]['name']}"
        if len(new_entries) == 1
        else f"Add {len(new_entries)} posters to index"
    )
    _save_index(repo, token, entries, sha, branch, message=message)
    return new_entries


def add_poster(repo, token, name, keywords, image_bytes, orig_filename, branch="main"):
    """Convenience wrapper around add_posters_bulk for a single poster.
    Returns the new entry."""
    items = [{
        "name": name,
        "keywords": keywords,
        "image_bytes": image_bytes,
        "orig_filename": orig_filename,
    }]
    return add_posters_bulk(repo, token, items, branch)[0]


def update_poster(repo, token, entry_id, new_name, new_keywords, branch="main"):
    """Renames a poster and/or updates its keywords. Only the index
    metadata changes — the underlying image file and its path are left
    exactly where they are. Returns the updated entry."""
    entries, sha = get_index(repo, token, branch)
    updated = None
    for e in entries:
        if e["id"] == entry_id:
            e["name"] = new_name
            e["keywords"] = new_keywords
            updated = e
            break
    if updated is None:
        raise CatalogError(
            "That poster couldn't be found — it may have already been deleted. Try refreshing."
        )
    _save_index(repo, token, entries, sha, branch, message=f"Rename poster: {new_name}")
    return updated


def delete_poster(repo, token, entry, branch="main"):
    """Removes the image file and its index entry."""
    resp = requests.get(
        _repo_url(repo, entry["path"]), headers=_headers(token),
        params={"ref": branch}, timeout=20,
    )
    if resp.ok:
        file_sha = resp.json()["sha"]
        del_body = {"message": f"Remove poster: {entry['name']}", "sha": file_sha, "branch": branch}
        requests.delete(_repo_url(repo, entry["path"]), headers=_headers(token), json=del_body, timeout=30)

    entries, sha = get_index(repo, token, branch)
    entries = [e for e in entries if e["id"] != entry["id"]]
    _save_index(repo, token, entries, sha, branch, message=f"Remove from index: {entry['name']}")


def image_raw_url(repo, path, branch="main"):
    """Direct raw.githubusercontent.com URL — works for both public and
    private repos as long as it's fetched with the token, but for display
    inside the app we fetch bytes via the API instead (see fetch_image_bytes)."""
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"


def fetch_image_bytes(repo, token, path, branch="main"):
    resp = requests.get(
        _repo_url(repo, path), headers=_headers(token),
        params={"ref": branch}, timeout=30,
    )
    if not resp.ok:
        raise CatalogError(f"Couldn't load image ({resp.status_code})")
    return base64.b64decode(resp.json()["content"])


def search(entries, query):
    if not query or not query.strip():
        return entries
    q = query.strip().lower()
    out = []
    for e in entries:
        haystack = (e.get("name", "") + " " + e.get("keywords", "")).lower()
        if q in haystack:
            out.append(e)
    return out
