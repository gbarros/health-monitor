from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SRC = ROOT / "web" / "src"
WEB_PUBLIC = ROOT / "web" / "public"


def read_web_file(relative: str) -> str:
    return (WEB_SRC / relative).read_text(encoding="utf-8")


def read_public_file(relative: str) -> str:
    return (WEB_PUBLIC / relative).read_text(encoding="utf-8")

