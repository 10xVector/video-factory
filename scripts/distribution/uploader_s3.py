#!/usr/bin/env python3
"""
Headless S3 / Cloudflare R2 Video Staging Uploader
--------------------------------------------------
Uploads rendered 9:16 MP4 files to an S3 or R2 bucket and returns the public
HTTPS CDN URL required by Meta Graph API and TikTok Content Posting API.
"""

import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
import subprocess
from typing import Dict, Any


def stage_video_to_cdn(video_path: str, staging_cfg: Dict[str, Any], dry_run: bool = False) -> str:
    """
    Uploads `video_path` to S3/R2 and returns the public HTTPS URL.
    Uses `boto3` if installed, falling back seamlessly to `aws s3 cp` CLI.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    bucket = staging_cfg.get("s3_bucket", "glow-social-cdn")
    prefix = staging_cfg.get("s3_prefix", "reels").strip("/")
    endpoint_url = staging_cfg.get("s3_endpoint_url", "")
    cdn_base = staging_cfg.get("cdn_base_url", f"https://{bucket}.s3.amazonaws.com").rstrip("/")

    filename = os.path.basename(video_path)
    s3_key = f"{prefix}/{filename}" if prefix else filename
    public_url = f"{cdn_base}/{s3_key}"

    if dry_run:
        print(f"   [DRY-RUN] ☁️  Would upload '{video_path}' -> s3://{bucket}/{s3_key}")
        print(f"   [DRY-RUN] 🔗 Staged CDN URL: {public_url}")
        return public_url

    print(f"☁️  Uploading '{filename}' to s3://{bucket}/{s3_key}...")

    try:
        import boto3
        s3_kwargs: Dict[str, Any] = {}
        if endpoint_url:
            s3_kwargs["endpoint_url"] = endpoint_url
        s3 = boto3.client("s3", **s3_kwargs)
        s3.upload_file(
            video_path,
            bucket,
            s3_key,
            ExtraArgs={"ContentType": "video/mp4"}
        )
    except ImportError:
        cmd = ["aws", "s3", "cp", video_path, f"s3://{bucket}/{s3_key}", "--content-type", "video/mp4"]
        if endpoint_url:
            cmd.extend(["--endpoint-url", endpoint_url])
        subprocess.run(cmd, check=True)

    print(f"✅ Staged CDN URL: {public_url}")
    return public_url
