#!/usr/bin/env python3
"""Extract embedded image assets from a private ChatGPT HTML export.

Outputs are intentionally meant for ignored private paths. The manifest avoids
raw diary text by keeping only short redacted context around each image.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path


DATA_IMAGE_RE = re.compile(
    r"data:image/(?P<kind>png|jpe?g|webp);base64,(?P<body>[A-Za-z0-9+/=\s]+)",
    re.IGNORECASE,
)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


@dataclass(frozen=True)
class ImageAsset:
    id: str
    image_type: str
    filename: str
    byte_size: int
    sha256: str
    width_px: int | None
    height_px: int | None
    html_image_index: int
    html_offset: int
    nearby_text_redacted: str
    review_classification: str = "unreviewed"


def extract_assets(raw_html: str, *, output_dir: Path) -> list[ImageAsset]:
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    assets: list[ImageAsset] = []
    for index, match in enumerate(DATA_IMAGE_RE.finditer(raw_html), start=1):
        image_type = match.group("kind").lower().replace("jpg", "jpeg")
        compact_body = re.sub(r"\s+", "", match.group("body"))
        try:
            content = base64.b64decode(compact_body, validate=False)
        except ValueError:
            continue
        digest = hashlib.sha256(content).hexdigest()
        ext = "jpg" if image_type == "jpeg" else image_type
        filename = f"chatgpt_image_{index:03d}_{digest[:12]}.{ext}"
        path = image_dir / filename
        if not path.exists():
            path.write_bytes(content)
        width, height = image_dimensions(content, image_type=image_type)
        assets.append(
            ImageAsset(
                id=f"chatgpt_image_{index:03d}",
                image_type=image_type,
                filename=str(path.relative_to(output_dir)),
                byte_size=len(content),
                sha256=digest,
                width_px=width,
                height_px=height,
                html_image_index=index,
                html_offset=match.start(),
                nearby_text_redacted=redact_text(nearby_text(raw_html, match.start())),
            )
        )
    return assets


def image_dimensions(content: bytes, *, image_type: str) -> tuple[int | None, int | None]:
    if image_type == "png":
        return png_dimensions(content)
    if image_type == "jpeg":
        return jpeg_dimensions(content)
    return (None, None)


def png_dimensions(content: bytes) -> tuple[int | None, int | None]:
    if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n":
        return (None, None)
    return (
        int.from_bytes(content[16:20], "big"),
        int.from_bytes(content[20:24], "big"),
    )


def jpeg_dimensions(content: bytes) -> tuple[int | None, int | None]:
    if len(content) < 4 or content[:2] != b"\xff\xd8":
        return (None, None)
    offset = 2
    while offset + 9 < len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue
        marker = content[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(content):
            break
        segment_length = int.from_bytes(content[offset : offset + 2], "big")
        if segment_length < 2:
            break
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            if offset + 7 <= len(content):
                height = int.from_bytes(content[offset + 3 : offset + 5], "big")
                width = int.from_bytes(content[offset + 5 : offset + 7], "big")
                return (width, height)
            break
        offset += segment_length
    return (None, None)


def nearby_text(raw_html: str, offset: int, *, radius: int = 2200) -> str:
    start = max(0, offset - radius)
    end = min(len(raw_html), offset + radius)
    snippet = IMG_TAG_RE.sub(" [image] ", raw_html[start:end])
    snippet = re.sub(r"<script\b.*?</script>", " ", snippet, flags=re.IGNORECASE | re.DOTALL)
    snippet = re.sub(r"<style\b.*?</style>", " ", snippet, flags=re.IGNORECASE | re.DOTALL)
    snippet = re.sub(r"<[^>]+>", " ", snippet)
    return normalize_text(html.unescape(snippet))[:800]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def redact_text(value: str) -> str:
    redacted = re.sub(r"\b\d{8,14}\b", "[barcode]", value)
    redacted = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", redacted)
    return redacted


def manifest_payload(assets: list[ImageAsset], *, source: Path, output_dir: Path) -> dict[str, object]:
    return {
        "format": "health-monitor.chatgpt-image-assets",
        "version": 1,
        "source_name": str(source),
        "output_dir": str(output_dir),
        "review_classifications": [
            "nutrition_label",
            "meal_photo",
            "screenshot_other",
            "irrelevant",
            "unreviewed",
        ],
        "assets": [
            {
                "id": asset.id,
                "image_type": asset.image_type,
                "filename": asset.filename,
                "byte_size": asset.byte_size,
                "sha256": asset.sha256,
                "width_px": asset.width_px,
                "height_px": asset.height_px,
                "html_image_index": asset.html_image_index,
                "html_offset": asset.html_offset,
                "nearby_text_redacted": asset.nearby_text_redacted,
                "review_classification": asset.review_classification,
            }
            for asset in assets
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_file", type=Path)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("private/chatgpt-assets"),
    )
    args = parser.parse_args()

    raw_html = args.html_file.read_text(encoding="utf-8", errors="replace")
    assets = extract_assets(raw_html, output_dir=args.out_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            manifest_payload(assets, source=args.html_file, output_dir=args.out_dir),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Extracted images: {len(assets)}")
    print(f"Wrote manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
