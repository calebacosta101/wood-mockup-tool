"""
Run this once, locally, to complete Shopify's OAuth handshake for the
custom app and get a long-lived offline access token. Shopify offline
tokens don't expire, so this script only ever needs to run once per
store connection — after it prints the token, paste it into this app's
Streamlit secrets and you're done with this file.

Before running:
  1. Fill in CLIENT_ID, CLIENT_SECRET, and SHOP_DOMAIN below.
  2. In Shopify's Dev Dashboard, on this app's version config, make sure
     http://localhost:8787/callback is listed under Redirect URLs, and
     the Scopes field includes write_products (and read_products if you
     want it too).

Run with:  python shopify_oauth_setup.py
"""

import hashlib
import hmac as hmac_lib
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs

import requests

CLIENT_ID = "PASTE_CLIENT_ID_HERE"
CLIENT_SECRET = "PASTE_CLIENT_SECRET_HERE"
SHOP_DOMAIN = "your-store.myshopify.com"
SCOPES = "read_products,write_products"
REDIRECT_URI = "http://localhost:8787/callback"

_expected_state = secrets.token_hex(16)
_result = {}


def _verify_hmac(params):
    received = params.get("hmac", [None])[0]
    if not received:
        return False
    filtered = {k: v for k, v in params.items() if k not in ("hmac", "signature")}
    message = "&".join(f"{k}={v[0]}" for k, v in sorted(filtered.items()))
    digest = hmac_lib.new(CLIENT_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac_lib.compare_digest(digest, received)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)

        if params.get("state", [None])[0] != _expected_state:
            self._respond(400, "State mismatch — try running the script again.")
            return
        if not _verify_hmac(params):
            self._respond(400, "HMAC verification failed — request may not be from Shopify.")
            return

        code = params.get("code", [None])[0]
        resp = requests.post(
            f"https://{SHOP_DOMAIN}/admin/oauth/access_token",
            json={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": code},
            timeout=30,
        )
        if not resp.ok:
            self._respond(502, f"Token exchange failed: {resp.text[:300]}")
            return

        _result["access_token"] = resp.json()["access_token"]
        self._respond(200, "Done — check your terminal for the access token, then close this tab.")

    def _respond(self, status, message):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"<h2>{message}</h2>".encode())

    def log_message(self, format, *args):
        pass  # keep the terminal output clean


def main():
    if "PASTE_" in CLIENT_ID or "PASTE_" in CLIENT_SECRET:
        print("Fill in CLIENT_ID and CLIENT_SECRET at the top of this file first.")
        return

    auth_url = f"https://{SHOP_DOMAIN}/admin/oauth/authorize?" + urlencode({
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": _expected_state,
    })

    print("Opening your browser for Shopify authorization...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8787), Handler)
    print("Waiting for Shopify to redirect back to http://localhost:8787/callback ...")
    server.handle_request()  # blocks until the single callback request arrives
    server.server_close()

    if "access_token" not in _result:
        print("Something went wrong — no access token received. Check the messages above.")
        return

    print("\nSuccess! Add these to the app's Streamlit secrets:\n")
    print(f'SHOPIFY_SHOP_DOMAIN = "{SHOP_DOMAIN}"')
    print(f'SHOPIFY_ACCESS_TOKEN = "{_result["access_token"]}"')


if __name__ == "__main__":
    main()
