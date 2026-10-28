import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
"""
Meta Graph API v21.0 Headless Publisher
Supports:
  1. Instagram Reels (`POST /{ig_user_id}/media` -> poll status -> `POST /{ig_user_id}/media_publish`)
  2. Facebook Page Reels (`POST /{page_id}/video_reels` -> two-step / URL upload + publish)
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def _graph_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    raw_body: Optional[bytes] = None,
) -> Dict[str, Any]:
    url = f"{GRAPH_API_BASE}/{endpoint.lstrip('/')}"
    req_headers = headers.copy() if headers else {}

    if method.upper() == "GET":
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        data = None
    else:
        if raw_body is not None:
            data = raw_body
        elif params:
            data = urllib.parse.urlencode(params).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            data = None

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Meta Graph API HTTP {e.code} on {endpoint}: {err_body}") from e


def publish_instagram_reel(
    video_url: str,
    caption: str,
    meta_cfg: Dict[str, Any],
    share_to_feed: bool = True,
    poll_interval: int = 5,
    max_polls: int = 36,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Publishes an Instagram Reel via a publicly staged CDN URL (S3 / R2).
    """
    ig_user_id = meta_cfg.get("ig_user_id") or meta_cfg.get("instagram_business_account_id", "")
    access_token = meta_cfg.get("page_access_token", "")

    if dry_run:
        print(f"   [DRY-RUN] 📸 Instagram Reels: container on IG account '{ig_user_id or '<unset>'}' -> {video_url}")
        return {
            "platform": "instagram",
            "status": "dry_run",
            "container_id": "dry_run_ig_container_123",
            "media_id": "dry_run_ig_media_456",
        }

    if not ig_user_id or not access_token:
        raise RuntimeError(
            "Missing Meta credentials (`ig_user_id` or `page_access_token`)."
        )

    print(f"  [Instagram] 1/3 Creating Reels media container for account {ig_user_id}...")
    container_res = _graph_request(
        "POST",
        f"{ig_user_id}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
            "access_token": access_token,
        },
    )
    creation_id = container_res.get("id")
    if not creation_id:
        raise RuntimeError(f"Failed to create IG Reels container: {container_res}")

    print(f"  [Instagram] 2/3 Waiting for Meta container {creation_id} to transcode...")
    status_code = "IN_PROGRESS"
    for attempt in range(1, max_polls + 1):
        time.sleep(poll_interval)
        status_res = _graph_request(
            "GET",
            creation_id,
            params={
                "fields": "status_code,status",
                "access_token": access_token,
            },
        )
        status_code = status_res.get("status_code", "UNKNOWN")
        print(f"    -> Poll {attempt}/{max_polls}: status_code={status_code}")
        if status_code == "FINISHED":
            break
        if status_code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"IG Reels container failed transcoding: {status_res}")

    if status_code != "FINISHED":
        raise RuntimeError(f"IG Reels container timed out in status: {status_code}")

    print(f"  [Instagram] 3/3 Publishing container {creation_id}...")
    pub_res = _graph_request(
        "POST",
        f"{ig_user_id}/media_publish",
        params={
            "creation_id": creation_id,
            "access_token": access_token,
        },
    )
    media_id = pub_res.get("id", "")
    print(f"  [Instagram] Published! Media ID: {media_id}")
    return {
        "platform": "instagram",
        "status": "published",
        "container_id": creation_id,
        "media_id": media_id,
    }


def publish_facebook_reel(
    video_path: Path,
    video_url: Optional[str],
    description: str,
    meta_cfg: Dict[str, Any],
    scheduled_publish_time: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Publishes a Facebook Page Reel using the Meta Graph Video Reels API:
      Step 1: Initialize upload session (`upload_phase=start`)
      Step 2: Upload binary (or pass `file_url` header to `rupload.facebook.com`)
      Step 3: Finish & publish (`upload_phase=finish`, `video_state=PUBLISHED`)
    """
    page_id = meta_cfg.get("page_id") or meta_cfg.get("facebook_page_id", "")
    access_token = meta_cfg.get("page_access_token", "")

    if dry_run:
        print(f"   [DRY-RUN] 📘 Facebook Reels: Page '{page_id or '<unset>'}' -> {video_path.name}")
        return {
            "platform": "facebook",
            "status": "dry_run",
            "video_id": "dry_run_fb_reel_789",
        }

    if not page_id or not access_token:
        raise RuntimeError("Missing Meta credentials (`facebook_page_id` or `page_access_token`).")

    print(f"  [Facebook] 1/3 Initializing Reels upload session on Page {page_id}...")
    init_res = _graph_request(
        "POST",
        f"{page_id}/video_reels",
        params={
            "upload_phase": "start",
            "access_token": access_token,
        },
    )
    video_id = init_res.get("video_id")
    upload_url = init_res.get("upload_url") or f"https://rupload.facebook.com/video-upload/v21.0/{video_id}"
    if not video_id:
        raise RuntimeError(f"Failed to start FB Reel session: {init_res}")

    print(f"  [Facebook] 2/3 Uploading binary for video_id={video_id}...")
    if video_url and not video_url.startswith("https://dry-run"):
        # Hosted file pull via rupload
        headers = {
            "Authorization": f"OAuth {access_token}",
            "file_url": video_url,
        }
        req = urllib.request.Request(upload_url, data=b"", headers=headers, method="POST")
    else:
        file_bytes = video_path.read_bytes()
        headers = {
            "Authorization": f"OAuth {access_token}",
            "offset": "0",
            "file_size": str(len(file_bytes)),
            "Content-Type": "application/octet-stream",
        }
        req = urllib.request.Request(upload_url, data=file_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            upload_res = json.loads(resp.read().decode("utf-8"))
            if not upload_res.get("success", True):
                raise RuntimeError(f"FB Reel binary upload failed: {upload_res}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"FB rupload HTTP {e.code}: {err_body}") from e

    print(f"  [Facebook] 3/3 Finishing & publishing FB Reel {video_id}...")
    finish_params: Dict[str, Any] = {
        "access_token": access_token,
        "video_id": video_id,
        "upload_phase": "finish",
        "description": description,
    }
    if scheduled_publish_time:
        finish_params["video_state"] = "SCHEDULED"
        finish_params["scheduled_publish_time"] = str(scheduled_publish_time)
    else:
        finish_params["video_state"] = "PUBLISHED"

    finish_res = _graph_request("POST", f"{page_id}/video_reels", params=finish_params)
    print(f"  [Facebook] Published! Video ID: {video_id}")
    return {
        "platform": "facebook",
        "status": "scheduled" if scheduled_publish_time else "published",
        "video_id": video_id,
        "response": finish_res,
    }
