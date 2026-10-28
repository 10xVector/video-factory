#!/usr/bin/env python3
"""
Headless YouTube Shorts Publisher (YouTube Data API v3)
-------------------------------------------------------
Zero-dependency resumable upload client using Google OAuth2 refresh token.
Automatically formats titles/descriptions with #Shorts and supports scheduled publishing.
"""

import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List


def refresh_youtube_access_token(yt_cfg: Dict[str, Any]) -> str:
    """Exchanges OAuth2 refresh_token for a fresh access_token."""
    client_id = yt_cfg.get("client_id", "")
    client_secret = yt_cfg.get("client_secret", "")
    refresh_token = yt_cfg.get("refresh_token", "")
    if not (client_id and client_secret and refresh_token):
        raise ValueError("Missing YouTube OAuth credentials in ~/.config/video-factory/credentials.json")

    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
        return payload["access_token"]


def publish_youtube_short(
    video_path: str,
    title: str,
    description: str,
    yt_cfg: Dict[str, Any],
    tags: Optional[List[str]] = None,
    schedule_iso: Optional[str] = None,
    privacy: str = "public",
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Uploads a 9:16 vertical MP4 as a YouTube Short via the resumable upload protocol.
    """
    short_title = title if "#shorts" in title.lower() else f"{title[:88]} #Shorts"
    tag_list = tags or ["Shorts", "app", "viral"]
    hashtag_str = " ".join(f"#{t.lstrip('#')}" for t in tag_list[:5])
    short_desc = f"{description}\n\n#Shorts {hashtag_str}".strip()

    status_block: Dict[str, Any] = {
        "selfDeclaredMadeForKids": False
    }
    if schedule_iso:
        status_block["privacyStatus"] = "private"
        status_block["publishAt"] = schedule_iso
    else:
        status_block["privacyStatus"] = privacy

    metadata = {
        "snippet": {
            "title": short_title,
            "description": short_desc,
            "tags": tag_list,
            "categoryId": "26"  # Howto & Style
        },
        "status": status_block
    }

    if dry_run:
        print(f"   [DRY-RUN] ▶️  YouTube Shorts: '{short_title}' (privacy={status_block['privacyStatus']})")
        if schedule_iso:
            print(f"   [DRY-RUN] ⏰ Scheduled for: {schedule_iso}")
        return {"platform": "youtube", "status": "dry_run", "title": short_title}

    access_token = refresh_youtube_access_token(yt_cfg)
    file_size = os.path.getsize(video_path)
    meta_bytes = json.dumps(metadata).encode("utf-8")

    # Step 1: Initiate resumable upload session
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    init_req = urllib.request.Request(
        init_url,
        data=meta_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(file_size),
            "X-Upload-Content-Type": "video/mp4"
        },
        method="POST"
    )
    with urllib.request.urlopen(init_req, timeout=30) as init_resp:
        upload_url = init_resp.headers.get("Location")

    if not upload_url:
        raise RuntimeError("YouTube API did not return a resumable upload Location header.")

    # Step 2: Stream binary video bytes
    print(f"▶️  Uploading binary to YouTube Shorts ({file_size / 1_048_576:.1f} MB)...")
    with open(video_path, "rb") as vf:
        video_bytes = vf.read()

    put_req = urllib.request.Request(
        upload_url,
        data=video_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Length": str(file_size),
            "Content-Type": "video/mp4"
        },
        method="PUT"
    )
    with urllib.request.urlopen(put_req, timeout=300) as put_resp:
        result = json.loads(put_resp.read().decode("utf-8"))

    video_id = result.get("id", "")
    short_url = f"https://youtube.com/shorts/{video_id}"
    print(f"✅ YouTube Short Published: {short_url}")
    return {"platform": "youtube", "id": video_id, "url": short_url}
