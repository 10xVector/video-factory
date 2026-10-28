#!/usr/bin/env python3
"""
Headless Multi-Platform Video Distributor (`distribute.py`)
-----------------------------------------------------------
Publishes rendered 9:16 vertical MP4s directly from the terminal to:
  - YouTube Shorts (YouTube Data API v3 Resumable Binary Upload)
  - Instagram Reels (Meta Graph API v21.0 Container + Publish)
  - Facebook Reels (Meta Graph Video Reels API v21.0)
  - TikTok (TikTok Content Posting API v2 Direct Post / Inbox Draft)
"""

import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
import argparse
import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from distribution.auth import (
    DEFAULT_CONFIG_PATH,
    init_social_config,
    load_social_config,
    print_auth_status,
)
from distribution.meta import publish_facebook_reel, publish_instagram_reel
from distribution.tiktok import publish_tiktok_video
from distribution.uploader_s3 import stage_video_to_cdn
from distribution.youtube import publish_youtube_short

LEDGER_PATH = Path.home() / ".config" / "video-factory" / "published_ledger.jsonl"


def infer_metadata_for_video(
    video_path: Path,
    brand: str = "app",
    custom_title: Optional[str] = None,
    custom_caption: Optional[str] = None,
    custom_tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    clean_name = video_path.stem.replace("_", " ").title()
    brand_title = brand.replace("_", " ").title()
    default_tags = [brand.lower().replace(" ", ""), "app", "shorts", "reels"]

    return {
        "title": custom_title or f"{clean_name} — {brand_title} #Shorts",
        "caption": custom_caption or f"{clean_name} ✨\n\nTry {brand_title} free (link in bio).",
        "tags": custom_tags if custom_tags is not None else default_tags,
    }


def append_to_ledger(entry: Dict[str, Any]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def distribute_video(
    video_path: Path,
    platforms: List[str],
    brand: str = "default",
    title: Optional[str] = None,
    caption: Optional[str] = None,
    tags: Optional[List[str]] = None,
    publish_at_iso: Optional[str] = None,
    tiktok_draft: bool = False,
    config_path: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cfg = load_social_config(str(config_path) if config_path else DEFAULT_CONFIG_PATH, brand=brand)
    meta = infer_metadata_for_video(video_path, brand, title, caption, tags)
    norm_platforms = [p.strip().lower() for p in platforms if p.strip()]

    print("\n" + "=" * 72)
    print(f"📡 VIDEO FACTORY DISTRIBUTOR [{brand.upper()}] {'[DRY-RUN]' if dry_run else '[LIVE]'}")
    print(f"   Video File : {video_path} ({video_path.stat().st_size / (1024*1024):.2f} MB)")
    print(f"   Platforms  : {', '.join(norm_platforms)}")
    print(f"   Title      : {meta['title']}")
    if publish_at_iso:
        print(f"   Scheduled  : {publish_at_iso}")
    print("=" * 72)

    needs_cdn = any(p in ("instagram", "facebook", "tiktok") for p in norm_platforms)
    staged_url: Optional[str] = None
    if needs_cdn:
        s3_cfg = cfg.get("staging", {})
        has_s3_bucket = bool(s3_cfg.get("s3_bucket"))
        if dry_run or has_s3_bucket:
            staged_url = stage_video_to_cdn(str(video_path), s3_cfg, dry_run=dry_run)
        elif "instagram" in norm_platforms:
            raise RuntimeError(
                "Instagram Graph API requires a public CDN URL (`staging.s3_bucket` and "
                "`staging.cdn_base_url` in ~/.config/video-factory/credentials.json)."
            )

    scheduled_unix: Optional[int] = None
    if publish_at_iso:
        dt = datetime.datetime.fromisoformat(publish_at_iso.replace("Z", "+00:00"))
        scheduled_unix = int(dt.timestamp())

    results: Dict[str, Any] = {}

    for platform in norm_platforms:
        print(f"\n🚀 Dispatching to [{platform.upper()}]...")
        try:
            if platform == "youtube":
                res = publish_youtube_short(
                    video_path=str(video_path),
                    title=meta["title"],
                    description=meta["caption"],
                    yt_cfg=cfg.get("youtube", {}),
                    tags=meta["tags"],
                    schedule_iso=publish_at_iso,
                    dry_run=dry_run,
                )
            elif platform == "instagram":
                assert staged_url is not None
                res = publish_instagram_reel(
                    video_url=staged_url,
                    caption=meta["caption"],
                    meta_cfg=cfg.get("meta", {}),
                    dry_run=dry_run,
                )
            elif platform == "facebook":
                res = publish_facebook_reel(
                    video_path=video_path,
                    video_url=staged_url,
                    description=meta["caption"],
                    meta_cfg=cfg.get("meta", {}),
                    scheduled_publish_time=scheduled_unix,
                    dry_run=dry_run,
                )
            elif platform == "tiktok":
                res = publish_tiktok_video(
                    video_path=video_path,
                    video_url=staged_url,
                    caption=meta["caption"],
                    tiktok_cfg=cfg.get("tiktok", {}),
                    draft=tiktok_draft,
                    dry_run=dry_run,
                )
            else:
                raise ValueError(f"Unsupported platform '{platform}'.")
            results[platform] = res
        except Exception as exc:
            print(f"  ❌ [{platform.upper()}] Error: {exc}")
            results[platform] = {"platform": platform, "status": "error", "error": str(exc)}

    ledger_record = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "brand": brand,
        "video": str(video_path),
        "title": meta["title"],
        "scheduled_for": publish_at_iso,
        "dry_run": dry_run,
        "results": results,
    }
    append_to_ledger(ledger_record)

    print("\n" + "=" * 72)
    print(f"✅ DISTRIBUTION SUMMARY ({brand.upper()} — {video_path.name}):")
    for plat, info in results.items():
        status_str = info.get("status", "unknown")
        ident = (
            info.get("url")
            or info.get("media_id")
            or info.get("video_id")
            or info.get("publish_id")
            or info.get("error", "")
        )
        print(f"   • {plat.ljust(10)} : {status_str.upper()}  {ident}")
    print(f"   📒 Ledger     : {LEDGER_PATH}")
    print("=" * 72 + "\n")

    return ledger_record


def main() -> None:
    parser = argparse.ArgumentParser(description="Video Factory Multi-Platform Social Distributor")
    parser.add_argument("--brand", type=str, default="default", help="Brand profile key (e.g. 'moment', 'glow')")
    parser.add_argument("--init-config", action="store_true", help="Create/upgrade ~/.config/video-factory/credentials.json")
    parser.add_argument("--gemini-key", type=str, default="", help="Save Gemini API key into credentials.json")
    parser.add_argument("--check-auth", action="store_true", help="Verify configured API tokens for --brand")
    parser.add_argument("--config", type=str, help=f"Custom path to credentials.json (default: {DEFAULT_CONFIG_PATH})")
    parser.add_argument("--video", type=str, help="Path to a single vertical MP4 file to publish")
    parser.add_argument("--platforms", type=str, default="youtube,instagram,facebook,tiktok")
    parser.add_argument("--title", type=str, help="Custom video title")
    parser.add_argument("--caption", type=str, help="Custom caption / description")
    parser.add_argument("--schedule", type=str, help="ISO-8601 UTC publish timestamp")
    parser.add_argument("--tiktok-draft", action="store_true", help="Send TikTok post to Creator Inbox as draft")
    parser.add_argument("--dry-run", action="store_true", help="Simulate API payloads without making live calls")

    args = parser.parse_args()
    cfg_path = Path(args.config) if args.config else None

    if args.init_config or args.gemini_key:
        created = init_social_config(str(cfg_path) if cfg_path else DEFAULT_CONFIG_PATH, gemini_key=args.gemini_key)
        print(f"✨ Saved Video Factory credentials config at: {created}")
        if not args.video and not args.check_auth:
            return

    if args.check_auth:
        print_auth_status(str(cfg_path) if cfg_path else DEFAULT_CONFIG_PATH, brand=args.brand)
        return

    if args.video:
        platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]
        distribute_video(
            video_path=Path(args.video).resolve(),
            platforms=platforms,
            brand=args.brand,
            title=args.title,
            caption=args.caption,
            publish_at_iso=args.schedule,
            tiktok_draft=args.tiktok_draft,
            config_path=cfg_path,
            dry_run=args.dry_run,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
