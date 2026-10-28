#!/usr/bin/env python3
"""
Repo Brand & Look Inspector (`inspect_repo.py`)
-----------------------------------------------
Automatically scans any target repository (React Native, Expo, Next.js, Swift, Flutter, Web)
to extract:
  1. App Name, Slug, & Value Proposition (from app.json, package.json, README.md, landing page)
  2. Look & Feel / Brand Palette (from tailwind.config.*, globals.css, theme files)
  3. Existing Screenshots & Marketing Assets (from screenshots/, public/marketing/, assets/)
  4. Recommended Layout Mode (`screen_walkthrough`, `before_after_slider`, or `side_by_side_proof`)

Outputs a ready-to-use `BrandConfig` JSON file or prints a structured discovery summary.
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


HEX_RE = re.compile(r"#([0-9a-fA-F]{6})\b")


def hex_to_rgb(hex_str: str) -> List[int]:
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]


def rgb_to_hex(rgb: List[int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(rgb[0], rgb[1], rgb[2])


def find_app_identity(repo_root: Path) -> Dict[str, str]:
    """Discovers app name, slug, tagline, and description from repo metadata."""
    app_name = repo_root.name.replace("-", " ").replace("_", " ").title()
    slug = repo_root.name.lower().replace(" ", "_")
    tagline = ""
    description = ""

    # 1. Check mobile/app.json or app.json (Expo / React Native)
    for rel in ["mobile/app.json", "app.json"]:
        p = repo_root / rel
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                expo = data.get("expo", data)
                if expo.get("name"):
                    raw_name = expo["name"]
                    if " - " in raw_name:
                        parts = raw_name.split(" - ", 1)
                        app_name = parts[0].strip()
                        tagline = parts[1].strip()
                    else:
                        app_name = raw_name.strip()
                if expo.get("slug"):
                    slug = expo["slug"].strip().lower()
                break
            except Exception:
                pass

    # 2. Check package.json if still generic
    for rel in ["package.json", "web/package.json", "mobile/package.json"]:
        p = repo_root / rel
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("description") and not description:
                    description = data["description"].strip()
            except Exception:
                pass

    # 3. Check README.md or CLAUDE.md for product summary
    for doc in ["README.md", "CLAUDE.md", "web/README.md", "marketing/README.md"]:
        p = repo_root / doc
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                for line in lines[:25]:
                    if line.startswith("# "):
                        heading = line.lstrip("# ").strip()
                        if "—" in heading or ":" in heading or "-" in heading:
                            sep = "—" if "—" in heading else (":" if ":" in heading else "-")
                            parts = heading.split(sep, 1)
                            if len(parts[0].strip()) < 25:
                                app_name = parts[0].strip()
                            if not tagline and len(parts) > 1:
                                tagline = parts[1].strip()
                    elif not line.startswith("#") and not line.startswith("```") and len(line) > 30 and not description:
                        description = line[:240]
                if description:
                    break
            except Exception:
                pass

    return {
        "app_name": app_name,
        "slug": slug,
        "tagline": tagline or f"Discover {app_name}",
        "description": description or f"{app_name} mobile and web application.",
    }


def find_brand_colors(repo_root: Path) -> Dict[str, Any]:
    """Scans tailwind configs and CSS files for accent and surface colors."""
    primary_rgb = [255, 78, 80]  # Default vibrant coral/rose (#FF4E50)
    surface_rgb = [18, 18, 22]   # Default dark mode surface (#121216)
    detected_hexes: Dict[str, str] = {}

    candidates = [
        "mobile/tailwind.config.js",
        "mobile/tailwind.config.ts",
        "web/tailwind.config.ts",
        "web/tailwind.config.js",
        "tailwind.config.js",
        "tailwind.config.ts",
        "mobile/global.css",
        "web/src/app/globals.css",
        "src/app/globals.css",
    ]

    for rel in candidates:
        p = repo_root / rel
        if not p.exists():
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            # Look for named accent or primary colors
            for m in re.finditer(r"['\"]?([a-zA-Z0-9_-]+)['\"]?\s*:\s*['\"]#(0-9a-fA-F]{6})['\"]", content):
                key, hex_val = m.group(1).lower(), m.group(2)
                detected_hexes[key] = f"#{hex_val}"
            # Also broader regex
            for m in re.finditer(r"([a-zA-Z0-9_-]+)\s*[:=]\s*['\"]?(#[0-9a-fA-F]{6})['\"]?", content):
                key, hex_val = m.group(1).lower(), m.group(2)
                detected_hexes[key] = hex_val
        except Exception:
            pass

    # Pick best accent color (non-grayscale)
    for key, hx in detected_hexes.items():
        rgb = hex_to_rgb(hx)
        # Check if colorful (max - min channel > 40)
        if max(rgb) - min(rgb) > 40 and any(k in key for k in ["accent", "primary", "brand", "sunset", "rose", "pink"]):
            primary_rgb = rgb
            break

    # Pick surface color
    for key, hx in detected_hexes.items():
        rgb = hex_to_rgb(hx)
        if max(rgb) < 45 and any(k in key for k in ["surface", "bg", "background", "base", "dark"]):
            surface_rgb = rgb
            break

    return {
        "primary_accent_rgb": primary_rgb,
        "primary_accent_hex": rgb_to_hex(primary_rgb),
        "surface_bg_rgb": surface_rgb,
        "surface_bg_hex": rgb_to_hex(surface_rgb),
        "discovered_tokens": detected_hexes,
    }


def find_screenshots_and_assets(repo_root: Path) -> Dict[str, Any]:
    """Discovers app screenshots, marketing screens, and before/after pairs in the repo."""
    search_dirs = [
        "web/public/marketing",
        "public/marketing",
        "screenshots",
        "marketing/assets",
        "assets/screenshots",
        "mobile/assets",
        "assets",
    ]
    screens: List[str] = []
    before_after_pairs: List[Tuple[str, str]] = []
    app_icon: Optional[str] = None

    seen = set()
    all_images: List[Path] = []

    for d_rel in search_dirs:
        d_path = repo_root / d_rel
        if not d_path.exists() or not d_path.is_dir():
            continue
        for root, _, files in os.walk(d_path):
            for f in sorted(files):
                ext = os.path.splitext(f)[1].lower()
                if ext not in (".png", ".jpg", ".jpeg", ".webp"):
                    continue
                full_p = Path(root) / f
                if str(full_p) in seen:
                    continue
                seen.add(str(full_p))
                low_f = f.lower()
                if "icon" in low_f and not app_icon and ext == ".png":
                    app_icon = str(full_p)
                    continue
                if any(skip in low_f for skip in ["favicon", "splash", "adaptive-icon", "og.png", "badge"]):
                    continue
                all_images.append(full_p)

    # Identify before/after pairs vs app screens
    by_stem = {p.stem.lower(): p for p in all_images}
    for stem, p in by_stem.items():
        if stem.endswith("_before"):
            prefix = stem[:-7]
            after_key = f"{prefix}_after"
            if after_key in by_stem:
                before_after_pairs.append((str(p), str(by_stem[after_key])))

    # Identify UI screenshots (prioritize screen-* or portrait screenshots)
    for p in all_images:
        name_l = p.name.lower()
        if name_l.startswith("screen") or "screenshot" in str(p).lower():
            screens.append(str(p))

    if not screens:
        screens = [str(p) for p in all_images[:8]]

    # Recommend format based on discovered assets
    recommended_format = "before_after_slider" if before_after_pairs and not any("screen-" in s for s in screens) else "screen_walkthrough"

    return {
        "app_icon": app_icon or "",
        "screenshots": screens[:12],
        "before_after_pairs": before_after_pairs[:6],
        "recommended_format": recommended_format,
    }


def inspect_repository(repo_path: str) -> Dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    if not repo_root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_root}")

    identity = find_app_identity(repo_root)
    colors = find_brand_colors(repo_root)
    assets = find_screenshots_and_assets(repo_root)

    brand_config = {
        "brand_id": identity["slug"],
        "app_name": identity["app_name"],
        "tagline": identity["tagline"],
        "description": identity["description"],
        "repo_path": str(repo_root),
        "default_format": assets["recommended_format"],
        "default_voice": "en_us_001",
        "theme": {
            "primary_accent_rgb": colors["primary_accent_rgb"],
            "primary_accent_hex": colors["primary_accent_hex"],
            "surface_bg_rgb": colors["surface_bg_rgb"],
            "surface_bg_hex": colors["surface_bg_hex"],
            "header_badge_text": "Live on iOS",
            "status_bar_time": "9:41",
        },
        "outro": {
            "app_title": f"{identity['app_name']} — {identity['tagline']}" if identity["tagline"] else identity["app_name"],
            "subtitle": identity["description"][:70],
            "cta_button_text": f"Try {identity['app_name']} Free",
            "bottom_pill_lines": ["Free on the App Store", "Link in bio"],
        },
        "discovered_assets": assets,
    }
    return brand_config


def main():
    parser = argparse.ArgumentParser(description="Inspect an app repository to extract BrandConfig for Video Factory")
    parser.add_argument("repo_path", nargs="?", default=".", help="Path to the target app repository (default: current directory)")
    parser.add_argument("--save", type=str, help="Save extracted BrandConfig JSON to this path")
    parser.add_argument("--json", action="store_true", help="Print raw JSON output only")
    args = parser.parse_args()

    result = inspect_repository(args.repo_path)

    if args.save:
        save_p = Path(args.save).expanduser().resolve()
        save_p.parent.mkdir(parents=True, exist_ok=True)
        save_p.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if not args.json:
            print(f"💾 Saved discovered BrandConfig to: {save_p}")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n" + "=" * 68)
        print(f"🔍 VIDEO FACTORY REPO DISCOVERY: {result['app_name']} ({result['brand_id']})")
        print("=" * 68)
        print(f"   📁 Repo Path          : {result['repo_path']}")
        print(f"   🏷️  Tagline            : {result['tagline']}")
        print(f"   📝 Description        : {result['description'][:90]}...")
        print(f"   🎨 Primary Accent     : {result['theme']['primary_accent_hex']} (RGB {result['theme']['primary_accent_rgb']})")
        print(f"   🌑 Surface Background : {result['theme']['surface_bg_hex']} (RGB {result['theme']['surface_bg_rgb']})")
        print(f"   🎬 Recommended Format : {result['default_format']}")
        print(f"   📸 App Screenshots    : {len(result['discovered_assets']['screenshots'])} found")
        for s in result["discovered_assets"]["screenshots"][:6]:
            print(f"      • {s}")
        if result["discovered_assets"]["before_after_pairs"]:
            print(f"   🔄 Before/After Pairs : {len(result['discovered_assets']['before_after_pairs'])} found")
        print("=" * 68 + "\n")


if __name__ == "__main__":
    main()
