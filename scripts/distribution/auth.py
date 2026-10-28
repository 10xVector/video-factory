#!/usr/bin/env python3
"""
Multi-Brand Credential & API Key Manager (`distribution/auth.py`)
-----------------------------------------------------------------
Manages Gemini API keys and multi-platform social publishing tokens across any number of apps/brands.
Default config path: ~/.config/video-factory/credentials.json
(Automatically falls back to ~/.config/glow/social_tokens.json and environment variables).
"""

import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
import json
from typing import Dict, Any, Optional

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/video-factory/credentials.json")
LEGACY_CONFIG_PATH = os.path.expanduser("~/.config/glow/social_tokens.json")

TEMPLATE_CONFIG: Dict[str, Any] = {
    "gemini_api_key": "",
    "studio_name": "MyStudio",
    "staging": {
        "s3_bucket": "",
        "s3_prefix": "reels",
        "s3_endpoint_url": "",
        "cdn_base_url": "",
    },
    "studio_apps": {
        "youtube_client_id": "",
        "youtube_client_secret": "",
        "meta_app_id": "",
        "meta_app_secret": "",
        "tiktok_client_key": "",
        "tiktok_client_secret": "",
    },
    "brands": {
        "default": {
            "s3_prefix": "reels/default",
            "youtube": {"refresh_token": ""},
            "meta": {
                "page_access_token": "",
                "ig_user_id": "",
                "page_id": "",
                "graph_version": "v21.0",
            },
            "tiktok": {
                "access_token": "",
                "refresh_token": "",
                "privacy_level": "PUBLIC_TO_EVERYONE",
            },
        }
    },
}


def resolve_gemini_api_key(explicit_key: Optional[str] = None, config_path: str = DEFAULT_CONFIG_PATH) -> str:
    """
    Resolves `GEMINI_API_KEY` from:
      1. Explicit CLI flag (`--gemini-key`)
      2. Environment variable (`GEMINI_API_KEY` or `GOOGLE_API_KEY`)
      3. Local `.env` file in current working directory
      4. `~/.config/video-factory/credentials.json`
    """
    if explicit_key:
        return explicit_key.strip()

    env_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if env_key:
        return env_key.strip()

    # Check local .env or web/.env
    for env_candidate in [".env", ".env.local", "web/.env", "mobile/.env", os.path.expanduser("~/.hermes/.env")]:
        if os.path.exists(env_candidate):
            try:
                with open(env_candidate, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip("'\"")
                            if val:
                                return val
            except Exception:
                pass

    raw = load_raw_studio_config(config_path)
    if raw.get("gemini_api_key"):
        return str(raw["gemini_api_key"]).strip()

    return ""


def load_raw_studio_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    cfg = json.loads(json.dumps(TEMPLATE_CONFIG))
    actual_path = config_path if os.path.exists(config_path) else (LEGACY_CONFIG_PATH if os.path.exists(LEGACY_CONFIG_PATH) else config_path)
    if os.path.exists(actual_path):
        try:
            with open(actual_path, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            for k, v in file_cfg.items():
                if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception:
            pass
    return cfg


def load_social_config(config_path: str = DEFAULT_CONFIG_PATH, brand: str = "default") -> Dict[str, Any]:
    raw = load_raw_studio_config(config_path)
    brand_key = (brand or "default").strip().lower()
    if brand_key not in raw.get("brands", {}):
        raw.setdefault("brands", {})[brand_key] = json.loads(json.dumps(TEMPLATE_CONFIG["brands"]["default"]))
        raw["brands"][brand_key]["s3_prefix"] = f"reels/{brand_key}"

    b_cfg = raw["brands"][brand_key]
    studio_apps = raw.get("studio_apps", {})
    staging = dict(raw.get("staging", {}))
    if b_cfg.get("s3_prefix"):
        staging["s3_prefix"] = b_cfg["s3_prefix"]

    return {
        "brand": brand_key,
        "gemini_api_key": resolve_gemini_api_key(config_path=config_path),
        "staging": {
            "s3_bucket": os.getenv("VIDEO_FACTORY_S3_BUCKET", os.getenv("GLOW_S3_BUCKET", staging.get("s3_bucket", ""))),
            "s3_prefix": staging.get("s3_prefix", f"reels/{brand_key}"),
            "s3_endpoint_url": os.getenv("VIDEO_FACTORY_S3_ENDPOINT_URL", staging.get("s3_endpoint_url", "")),
            "cdn_base_url": os.getenv("VIDEO_FACTORY_CDN_BASE_URL", staging.get("cdn_base_url", "")),
        },
        "youtube": {
            "client_id": os.getenv("YOUTUBE_CLIENT_ID", studio_apps.get("youtube_client_id", "")),
            "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET", studio_apps.get("youtube_client_secret", "")),
            "refresh_token": os.getenv("YOUTUBE_REFRESH_TOKEN", b_cfg.get("youtube", {}).get("refresh_token", "")),
        },
        "meta": {
            "page_access_token": os.getenv("META_PAGE_ACCESS_TOKEN", b_cfg.get("meta", {}).get("page_access_token", "")),
            "ig_user_id": os.getenv("META_IG_USER_ID", b_cfg.get("meta", {}).get("ig_user_id", "")),
            "page_id": os.getenv("META_PAGE_ID", b_cfg.get("meta", {}).get("page_id", "")),
            "graph_version": b_cfg.get("meta", {}).get("graph_version", "v21.0"),
        },
        "tiktok": {
            "client_key": os.getenv("TIKTOK_CLIENT_KEY", studio_apps.get("tiktok_client_key", "")),
            "client_secret": os.getenv("TIKTOK_CLIENT_SECRET", studio_apps.get("tiktok_client_secret", "")),
            "access_token": os.getenv("TIKTOK_ACCESS_TOKEN", b_cfg.get("tiktok", {}).get("access_token", "")),
            "refresh_token": os.getenv("TIKTOK_REFRESH_TOKEN", b_cfg.get("tiktok", {}).get("refresh_token", "")),
            "privacy_level": b_cfg.get("tiktok", {}).get("privacy_level", "PUBLIC_TO_EVERYONE"),
        },
    }


def init_social_config(config_path: str = DEFAULT_CONFIG_PATH, gemini_key: str = "") -> str:
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    raw = load_raw_studio_config(config_path)
    if gemini_key:
        raw["gemini_api_key"] = gemini_key.strip()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)
    os.chmod(config_path, 0o600)
    return config_path


def print_auth_status(config_path: str = DEFAULT_CONFIG_PATH, brand: str = "default") -> None:
    cfg = load_social_config(config_path, brand=brand)
    print(f"\n🔐 [VIDEO FACTORY CREDENTIALS STATUS — BRAND: {brand.upper()}]")
    print(f"   Config File      : {config_path} ({'FOUND' if os.path.exists(config_path) else 'NOT CREATED YET'})")
    print(f"   🤖 Gemini API Key : {'✅ READY' if cfg['gemini_api_key'] else '⚠️  MISSING (pass --gemini-key or set GEMINI_API_KEY)'}")

    s3_ok = bool(cfg["staging"].get("s3_bucket"))
    yt_ok = all(cfg["youtube"].get(k) for k in ("client_id", "client_secret", "refresh_token"))
    ig_ok = all(cfg["meta"].get(k) for k in ("page_access_token", "ig_user_id"))
    fb_ok = all(cfg["meta"].get(k) for k in ("page_access_token", "page_id"))
    tt_ok = bool(cfg["tiktok"].get("access_token") or cfg["tiktok"].get("refresh_token"))

    print(f"   ☁️  S3/R2 Staging  : {'✅ READY' if s3_ok else '⚠️  OPTIONAL (needed for IG/TikTok URL pull)'}")
    print(f"   ▶️  YouTube Shorts : {'✅ READY' if yt_ok else '⚠️  NEEDS OAUTH TOKEN'}")
    print(f"   📸 Instagram Reels: {'✅ READY' if ig_ok else '⚠️  NEEDS META PAGE TOKEN & IG_USER_ID'}")
    print(f"   📘 Facebook Reels : {'✅ READY' if fb_ok else '⚠️  NEEDS META PAGE TOKEN & PAGE_ID'}")
    print(f"   🎵 TikTok         : {'✅ READY' if tt_ok else '⚠️  NEEDS TIKTOK ACCESS/REFRESH TOKEN'}\n")
