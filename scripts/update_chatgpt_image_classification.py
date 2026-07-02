#!/usr/bin/env python3
"""Update review classifications in a private ChatGPT image manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED_CLASSIFICATIONS = {
    "nutrition_label",
    "meal_photo",
    "screenshot_other",
    "irrelevant",
    "unreviewed",
}


def update_manifest(
    manifest: dict[str, object],
    *,
    asset_ids: set[str],
    classification: str,
) -> int:
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise ValueError(f"unsupported classification: {classification}")
    assets = manifest.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("manifest assets must be a list")
    changed = 0
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("id")) in asset_ids:
            asset["review_classification"] = classification
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("private/chatgpt-assets/manifest.json"),
    )
    parser.add_argument("--classification", required=True, choices=sorted(ALLOWED_CLASSIFICATIONS))
    parser.add_argument("asset_ids", nargs="+")
    args = parser.parse_args()

    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    changed = update_manifest(
        payload,
        asset_ids=set(args.asset_ids),
        classification=args.classification,
    )
    args.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Updated assets: {changed}")
    print(f"Manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
