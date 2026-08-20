"""
Publishes a listing directly to Shopify using a long-lived offline access
token obtained once via shopify_oauth_setup.py and stored in this app's
Streamlit secrets — no OAuth flow runs inside the deployed app itself.
"""

import base64

import requests

API_VERSION = "2024-10"


class ShopifyPublishError(Exception):
    pass


def create_product(shop_domain, access_token, *, title, description, price, tags, images, status="draft"):
    """
    images: list of (filename, bytes) tuples — becomes the product's photos.
    tags: comma-separated string.
    status: "draft" (default — review in Shopify before it goes live) or "active".
    Returns (product_dict, admin_url).
    """
    payload = {
        "product": {
            "title": title,
            "body_html": description or "",
            "tags": tags or "",
            "status": status,
            "variants": [{"price": str(price)}],
            "images": [
                {"attachment": base64.b64encode(data).decode("ascii"), "filename": name}
                for name, data in images
            ],
        }
    }

    resp = requests.post(
        f"https://{shop_domain}/admin/api/{API_VERSION}/products.json",
        headers={
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    if not resp.ok:
        raise ShopifyPublishError(f"Shopify rejected the product ({resp.status_code}): {resp.text[:400]}")

    product = resp.json()["product"]
    admin_url = f"https://{shop_domain}/admin/products/{product['id']}"
    return product, admin_url
