import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
"""
TikTok Content Posting API v2 Headless Publisher
Supports:
  - OAuth2 refresh token exchange (`https://open.tiktokapis.com/v2/oauth/token/`)
  - Direct Post (`/v2/post/publish/video/init/`) via `PULL_FROM_URL` or `FILE_UPLOAD`
  - Inbox Draft upload (`/v2/post/publish/inbox/video/init/`) when `draft=True`
  - Publish status polling (`/v2/post/publish/status/fetch/`)
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


def refresh_tiktok_access_token(tiktok_cfg: Dict[str, Any]) -> str:
    """
    Exchanges a TikTok refresh_token for a fresh access_token if client_key,
    client_secret, and refresh_token are configured; otherwise falls back to
    the static access_token in tiktok_cfg.
    """
    client_key = tiktok_cfg.get("client_key", "")
    client_secret = tiktok_cfg.get("client_secret", "")
    refresh_token = tiktok_cfg.get("refresh_token", "")
    static_token = tiktok_cfg.get("access_token", "")

    if not (client_key and client_secret and refresh_token):
        if static_token:
            return static_token
        raise RuntimeError("Missing TikTok credentials in config (`access_token` or `refresh_token`).")

    payload = urllib.parse.urlencode(
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{TIKTOK_API_BASE}/oauth/token/",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "access_token" not in data:
                raise RuntimeError(f"TikTok token refresh error: {data}")
            return data["access_token"]
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"TikTok OAuth HTTP {e.code}: {err_body}") from e


def publish_tiktok_video(
    video_path: Path,
    video_url: Optional[str],
    caption: str,
    tiktok_cfg: Dict[str, Any],
    draft: bool = False,
    poll_interval: int = 5,
    max_polls: int = 24,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Publishes (or sends to Inbox Drafts) a vertical MP4 to TikTok via Content Posting API v2.
    Prefers `PULL_FROM_URL` if a verified domain URL is available, otherwise uses `FILE_UPLOAD`.
    """
    privacy_level = tiktok_cfg.get("privacy_level", "PUBLIC_TO_EVERYONE")
    mode_label = "INBOX_DRAFT" if draft else f"DIRECT_POST ({privacy_level})"

    if dry_run:
        source_type = "PULL_FROM_URL" if video_url else "FILE_UPLOAD"
        print(f"  [TikTok DRY-RUN] Would publish via {mode_label} using source={source_type}")
        print(f"    -> file: {video_path.name} ({video_path.stat().st_size / (1024*1024):.2f} MB)")
        if video_url:
            print(f"    -> video_url: {video_url}")
        print(f"    -> title/caption: {caption[:80]}{'...' if len(caption) > 80 else ''}")
        return {
            "platform": "tiktok",
            "status": "dry_run",
            "mode": mode_label,
            "publish_id": "dry_run_tt_pub_999",
        }

    access_token = refresh_tiktok_access_token(tiktok_cfg)
    endpoint = (
        f"{TIKTOK_API_BASE}/post/publish/inbox/video/init/"
        if draft
        else f"{TIKTOK_API_BASE}/post/publish/video/init/"
    )

    file_size = video_path.stat().st_size
    use_pull = bool(video_url and not video_url.startswith("https://dry-run"))

    if use_pull:
        source_info = {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        }
    else:
        source_info = {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        }

    body: Dict[str, Any] = {"source_info": source_info}
    if not draft:
        body["post_info"] = {
            "title": caption[:2200],
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
        }

    print(f"  [TikTok] 1/3 Initializing {mode_label} ({source_info['source']})...")
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            init_res = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"TikTok init HTTP {e.code}: {err_body}") from e

    err_code = init_res.get("error", {}).get("code", "ok")
    if err_code != "ok":
        raise RuntimeError(f"TikTok init returned error: {init_res}")

    data_block = init_res.get("data", {})
    publish_id = data_block.get("publish_id", "")
    upload_url = data_block.get("upload_url", "")

    if not use_pull and upload_url:
        print(f"  [TikTok] 2/3 Uploading {file_size / (1024*1024):.2f} MB binary to TikTok ingest...")
        video_bytes = video_path.read_bytes()
        put_req = urllib.request.Request(
            upload_url,
            data=video_bytes,
            headers={
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                "Content-Length": str(file_size),
                "Content-Type": "video/mp4",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(put_req, timeout=300) as put_resp:
                if put_resp.status not in (200, 201, 206):
                    raise RuntimeError(f"Unexpected TikTok PUT status {put_resp.status}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"TikTok binary PUT HTTP {e.code}: {err_body}") from e
    else:
        print(f"  [TikTok] 2/3 TikTok pulling video directly from {video_url}...")

    print(f"  [TikTok] 3/3 Polling publish status for publish_id={publish_id}...")
    final_status = "PROCESSING_UPLOAD"
    for attempt in range(1, max_polls + 1):
        time.sleep(poll_interval)
        status_req = urllib.request.Request(
            f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
            data=json.dumps({"publish_id": publish_id}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(status_req, timeout=30) as s_resp:
                s_data = json.loads(s_resp.read().decode("utf-8"))
                final_status = s_data.get("data", {}).get("status", "UNKNOWN")
                print(f"    -> Poll {attempt}/{max_polls}: status={final_status}")
                if final_status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
                    break
                if final_status == "FAILED":
                    fail_reason = s_data.get("data", {}).get("fail_reason", "unknown")
                    raise RuntimeError(f"TikTok publish failed: {fail_reason} ({s_data})")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"TikTok status poll HTTP {e.code}: {err_body}") from e

    print(f"  [TikTok] Completed with status={final_status} (publish_id={publish_id})")
    return {
        "platform": "tiktok",
        "status": final_status,
        "publish_id": publish_id,
    }
