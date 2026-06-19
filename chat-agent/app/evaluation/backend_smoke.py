from __future__ import annotations

import argparse
import json
from typing import Any

from app.clients import BackendClient, BackendClientError, create_backend_client
from app.services.env_service import load_local_env


def run_backend_smoke(client: BackendClient | None = None, query: str = "shirt", limit: int = 1) -> dict[str, Any]:
    backend = client or create_backend_client()
    result: dict[str, Any] = {
        "catalogSearch": {"ok": False, "count": 0},
        "catalogDetail": {"ok": False, "skipped": True},
        "recommendSimilar": {"ok": False, "skipped": True},
    }

    products = backend.catalog_search(query=query, limit=limit)
    result["catalogSearch"] = {"ok": True, "count": len(products)}
    if not products:
        return result

    first = products[0]
    slug = first.get("slug")
    detail = backend.catalog_detail(slug=slug) if slug else None
    if isinstance(detail, dict):
        result["catalogDetail"] = {
            "ok": True,
            "skipped": False,
            "slug": detail.get("slug") or slug,
            "hasImage": bool(detail.get("imageUrl")),
            "colors": len(detail.get("colors") or []),
            "sizes": len(detail.get("sizes") or []),
            "stock": int(detail.get("stock", 0) or 0),
        }
    else:
        result["catalogDetail"] = {"ok": False, "skipped": False, "slug": slug}

    variant_id = (detail or first).get("variantId") if isinstance(detail or first, dict) else None
    recommendations = backend.recommend_similar(variant_id=variant_id, limit=limit) if variant_id else []
    result["recommendSimilar"] = {
        "ok": True,
        "skipped": False,
        "variantId": variant_id,
        "count": len(recommendations),
    }
    return result


def main() -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description="Smoke test chat-agent Spring backend mode.")
    parser.add_argument("--query", default="shirt")
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()

    try:
        result = run_backend_smoke(query=args.query, limit=args.limit)
    except BackendClientError as exc:
        result = {"ok": False, "status": exc.status, "error": str(exc)}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["catalogSearch"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
