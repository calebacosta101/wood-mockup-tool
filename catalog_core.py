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


def add_poster(repo, token, name, keywords, image_bytes, orig_filename, branch="main"):
    """Uploads the image and appends a new entry to the index. Returns the new entry."""
    ext = orig_filename.rsplit(".", 1)[-1].lower() if "." in orig_filename else "jpg"
    poster_id = uuid.uuid4().hex[:10]
    slug = _slugify(name)
    image_path = f"{IMAGES_DIR}/{slug}-{poster_id}.{ext}"

    put_body = {
        "message": f"Add poster: {name}",
        "content": base64.b64encode(image_bytes).decode("ascii"),
        "branch": branch,
    }
    resp = requests.put(_repo_url(repo, image_path), headers=_headers(token), json=put_body, timeout=60)
    if not resp.ok:
        raise CatalogError(f"Couldn't upload image ({resp.status_code}): {resp.text[:300]}")

    entries, sha = get_index(repo, token, branch)
    entry = {
        "id": poster_id,
        "name": name,
        "keywords": keywords,
        "path": image_path,
        "added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    entries.append(entry)
    _save_index(repo, token, entries, sha, branch, message=f"Add poster to index: {name}")
    return entry


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
