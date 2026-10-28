#!/usr/bin/env python3
"""
Before / After Image Pair Generator (Gemini Nano Banana 2.1 + Single-Piece Pixel Lock)
======================================================================================
Generates certified pixel-locked Before & After transformation pairs using the
Gemini Interactions API (`gemini-nano-banana-2.1` or `gemini-3-pro-image`) and
composites the edited zone onto the original Before canvas so the face, background,
and unchanged garment zone have 0.0 pixel drift during the video wipe slider.

Usage:
  # Generate a Before + After pair from scratch (1-piece lower-body swap)
  python3 scripts/generate_pair.py \
    --before-prompt "Full-body street style photo of a 30-year-old man on a Soho sidewalk wearing a fitted olive field jacket over a white tee, paired with baggy puddling light-wash jeans and chunky running sneakers. Natural daylight, 2:3 vertical portrait." \
    --after-edit-prompt "Swap ONLY the baggy light-wash jeans and running sneakers for tailored charcoal wool trousers with a clean ankle break and minimalist white leather low-top sneakers. Keep the face, olive jacket, pose, and street background identical." \
    --swap-zone lower \
    --output-before assets/ep_before.jpg \
    --output-after assets/ep_after.jpg

  # Or start from an existing Before photo and generate the pixel-locked After photo
  python3 scripts/generate_pair.py \
    --input-before assets/my_before.jpg \
    --after-edit-prompt "Swap ONLY the boxy oversized hoodie for a structured navy chore coat over a crisp white crew neck tee." \
    --swap-zone upper \
    --output-after assets/my_after.jpg
"""

import argparse
import base64
import io
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from distribution.auth import load_credentials


DEFAULT_IMAGE_MODEL = "gemini-nano-banana-2.1"
API_REVISION = "2026-05-20"


def _resolve_gemini_key(explicit_key: Optional[str] = None) -> str:
    if explicit_key:
        return explicit_key
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key
    creds = load_credentials()
    cred_key = creds.get("gemini", {}).get("api_key", "")
    if cred_key and not cred_key.startswith("YOUR_"):
        return cred_key
    raise RuntimeError(
        "Missing Gemini API Key. Pass --gemini-key, set GEMINI_API_KEY, "
        "or add gemini.api_key in ~/.config/video-factory/credentials.json"
    )


def _generate_image_interaction(
    api_key: str,
    prompt: str,
    model: str = DEFAULT_IMAGE_MODEL,
    aspect_ratio: str = "2:3",
    reference_image_bytes: Optional[bytes] = None,
    reference_mime_type: str = "image/jpeg",
    previous_interaction_id: Optional[str] = None,
) -> Tuple[bytes, Optional[str]]:
    """
    Calls the Gemini Interactions API (`gemini-nano-banana-2.1` or `gemini-3-pro-image`)
    using the `google-genai` SDK when installed, with a direct REST fallback.
    Returns `(image_bytes, interaction_id)`.
    """
    response_format = {
        "type": "image",
        "mime_type": "image/jpeg",
        "aspect_ratio": aspect_ratio,
    }

    # Try official google-genai SDK first (Interactions API)
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key)
        if hasattr(client, "interactions"):
            if reference_image_bytes is not None:
                interaction_input = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "data": base64.b64encode(reference_image_bytes).decode("utf-8"),
                        "mime_type": reference_mime_type,
                    },
                ]
            else:
                interaction_input = prompt

            kwargs = {
                "model": model,
                "input": interaction_input,
                "response_format": response_format,
            }
            if previous_interaction_id:
                kwargs["previous_interaction_id"] = previous_interaction_id

            interaction = client.interactions.create(**kwargs)
            if getattr(interaction, "output_image", None) and getattr(interaction.output_image, "data", None):
                img_bytes = base64.b64decode(interaction.output_image.data)
                return img_bytes, getattr(interaction, "id", None)
    except ImportError:
        pass

    # Direct REST call to https://generativelanguage.googleapis.com/v1beta/interactions
    import requests

    url = "https://generativelanguage.googleapis.com/v1beta/interactions"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
        "Api-Revision": API_REVISION,
    }

    if reference_image_bytes is not None:
        input_payload = [
            {"type": "text", "text": prompt},
            {
                "type": "image",
                "mime_type": reference_mime_type,
                "data": base64.b64encode(reference_image_bytes).decode("utf-8"),
            },
        ]
    else:
        input_payload = [{"type": "text", "text": prompt}]

    body: Dict = {
        "model": model,
        "input": input_payload,
        "response_format": response_format,
    }
    if previous_interaction_id:
        body["previous_interaction_id"] = previous_interaction_id

    resp = requests.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    interaction_id = data.get("id") or data.get("interaction", {}).get("id")
    output_image = data.get("output_image") or data.get("interaction", {}).get("output_image")
    if output_image and output_image.get("data"):
        return base64.b64decode(output_image["data"]), interaction_id

    # Fallback: scan steps/outputs for an image block
    for item in data.get("outputs", data.get("steps", [])):
        if item.get("type") == "image" and item.get("data"):
            return base64.b64decode(item["data"]), interaction_id

    raise RuntimeError(f"Gemini Interactions API did not return an output_image block: {json.dumps(data)[:400]}")


def apply_pixel_lock_composite(
    before_img: Image.Image,
    raw_after_img: Image.Image,
    swap_zone: str = "lower",
) -> Image.Image:
    """
    Composites ONLY the target `swap_zone` from `raw_after_img` onto `before_img`
    using a feathered alpha mask. This guarantees 0.0 pixel drift on the head/face,
    outer street/room background, and the unchanged garment zone.

    Supported `swap_zone` values:
      - "upper"  : Unlocks upper torso/jacket/shirt (y: 20%..56%, x: 10%..90%).
                   Locks face/head (y: 0..18%), lower body (y: 60%..100%), and outer edges.
      - "lower"  : Unlocks pants/trousers/shoes (y: 47%..97%, x: 12%..88%).
                   Locks face/head + upper shirt/jacket (y: 0..44%) and outer edges.
      - "center" : Unlocks central subject zone (y: 20%..90%, x: 12%..88%) while
                   locking the top header/head band and outer background frame.
      - "none"   : Returns `raw_after_img` resized to `before_img.size` without masking.
    """
    before_rgb = before_img.convert("RGB")
    w, h = before_rgb.size
    after_rgb = raw_after_img.convert("RGB").resize((w, h), Image.Resampling.LANCZOS)

    zone = swap_zone.lower().strip()
    if zone == "none":
        return after_rgb

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    if zone == "upper":
        # Upper torso / jacket / top zone (keeps head y<18% and lower body y>58% locked)
        x0, x1 = int(w * 0.10), int(w * 0.90)
        y0, y1 = int(h * 0.20), int(h * 0.56)
    elif zone == "lower":
        # Lower body / pants / footwear zone (keeps head + upper torso y<45% locked)
        x0, x1 = int(w * 0.12), int(w * 0.88)
        y0, y1 = int(h * 0.47), int(h * 0.97)
    elif zone == "center":
        x0, x1 = int(w * 0.12), int(w * 0.88)
        y0, y1 = int(h * 0.20), int(h * 0.90)
    else:
        raise ValueError(f"Unknown swap_zone '{swap_zone}'. Choose from: upper, lower, center, none.")

    corner_r = max(12, int(min(w, h) * 0.04))
    draw.rounded_rectangle([x0, y0, x1, y1], radius=corner_r, fill=255)

    feather_radius = max(8, int(h * 0.022))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))

    # Hard-zero the audit zones so head_diff == 0.0 and bg_diff == 0.0 are mathematically guaranteed
    mask_np = np.array(mask, dtype=np.uint8)
    mask_np[: int(h * 0.18), :] = 0  # Top 18% (Head / Face zone)
    mask_np[:, : int(w * 0.08)] = 0  # Left 8% background margin
    mask_np[:, int(w * 0.92) :] = 0  # Right 8% background margin
    if zone == "upper":
        mask_np[int(h * 0.58) :, :] = 0  # Lock lower body completely
    elif zone == "lower":
        mask_np[: int(h * 0.45), :] = 0  # Lock upper body completely

    locked_mask = Image.fromarray(mask_np, mode="L")
    return Image.composite(after_rgb, before_rgb, locked_mask)


def audit_pair_metrics(before_path: Path, after_path: Path) -> Dict[str, float]:
    """
    Computes the same zone-by-zone pixel-diff metrics checked by
    `ScriptReviewManager.audit_stage_progression()`.
    """
    b_img = Image.open(before_path).convert("RGB")
    a_img = Image.open(after_path).convert("RGB").resize(b_img.size, Image.Resampling.LANCZOS)

    b_arr = np.array(b_img, dtype=np.float32)
    a_arr = np.array(a_img, dtype=np.float32)
    h, w, _ = b_arr.shape

    head_diff = float(np.mean(np.abs(b_arr[: int(h * 0.18), int(w * 0.25) : int(w * 0.75)] - a_arr[: int(h * 0.18), int(w * 0.25) : int(w * 0.75)])))
    left_bg = float(np.mean(np.abs(b_arr[:, : int(w * 0.08)] - a_arr[:, : int(w * 0.08)])))
    right_bg = float(np.mean(np.abs(b_arr[:, int(w * 0.92) :] - a_arr[:, int(w * 0.92) :])))
    bg_diff = (left_bg + right_bg) / 2.0
    upper_diff = float(np.mean(np.abs(b_arr[int(h * 0.22) : int(h * 0.52), int(w * 0.25) : int(w * 0.75)] - a_arr[int(h * 0.22) : int(h * 0.52), int(w * 0.25) : int(w * 0.75)])))
    lower_diff = float(np.mean(np.abs(b_arr[int(h * 0.55) : int(h * 0.90), int(w * 0.25) : int(w * 0.75)] - a_arr[int(h * 0.55) : int(h * 0.90), int(w * 0.25) : int(w * 0.75)])))

    return {
        "head_diff": round(head_diff, 2),
        "bg_diff": round(bg_diff, 2),
        "upper_diff": round(upper_diff, 2),
        "lower_diff": round(lower_diff, 2),
    }


def generate_locked_pair(
    after_edit_prompt: str,
    output_before: Path,
    output_after: Path,
    before_prompt: Optional[str] = None,
    input_before: Optional[Path] = None,
    swap_zone: str = "lower",
    aspect_ratio: str = "2:3",
    model: str = DEFAULT_IMAGE_MODEL,
    gemini_key: Optional[str] = None,
) -> Dict[str, float]:
    """
    Generates or loads the `Before` image, generates the edited `After` image via
    `gemini-nano-banana-2.1`, composites the target zone for a 0.0-drift pixel lock,
    saves both files, and returns the pixel-diff audit metrics.
    """
    api_key = _resolve_gemini_key(gemini_key)
    output_before.parent.mkdir(parents=True, exist_ok=True)
    output_after.parent.mkdir(parents=True, exist_ok=True)

    interaction_id: Optional[str] = None

    if input_before and input_before.exists():
        print(f"📸 Loading existing Before image: {input_before}")
        before_img = Image.open(input_before).convert("RGB")
        if input_before.resolve() != output_before.resolve():
            before_img.save(output_before, quality=95)
        with open(output_before, "rb") as f:
            before_bytes = f.read()
    else:
        if not before_prompt:
            raise ValueError("Provide either --before-prompt (to generate Before) or --input-before (existing image).")
        print(f"🎨 Generating Before image with {model} ({aspect_ratio})...")
        before_bytes, interaction_id = _generate_image_interaction(
            api_key=api_key,
            prompt=before_prompt,
            model=model,
            aspect_ratio=aspect_ratio,
        )
        before_img = Image.open(io.BytesIO(before_bytes)).convert("RGB")
        before_img.save(output_before, quality=95)
        print(f"   ✓ Saved Before image -> {output_before} ({before_img.size[0]}x{before_img.size[1]})")

    zone_instruction = {
        "upper": "Modify ONLY the upper-body top/jacket/shirt. Keep the person's face, hair, lower-body pants/shoes, pose, lighting, and background 100% identical.",
        "lower": "Modify ONLY the lower-body pants/trousers and footwear. Keep the person's face, hair, upper-body shirt/jacket, pose, lighting, and background 100% identical.",
        "center": "Modify ONLY the central target subject described. Keep the top framing and outer background 100% identical.",
        "none": "Keep the person's identity, pose, camera angle, and background consistent.",
    }.get(swap_zone.lower(), "")

    full_after_prompt = f"{after_edit_prompt.strip()} {zone_instruction}".strip()

    print(f"✨ Generating After edit with {model} (swap_zone={swap_zone})...")
    raw_after_bytes, _ = _generate_image_interaction(
        api_key=api_key,
        prompt=full_after_prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        reference_image_bytes=None if interaction_id else before_bytes,
        reference_mime_type="image/jpeg",
        previous_interaction_id=interaction_id,
    )
    raw_after_img = Image.open(io.BytesIO(raw_after_bytes)).convert("RGB")

    locked_after_img = apply_pixel_lock_composite(
        before_img=before_img,
        raw_after_img=raw_after_img,
        swap_zone=swap_zone,
    )
    locked_after_img.save(output_after, quality=95)
    print(f"   ✓ Saved Pixel-Locked After image -> {output_after}")

    metrics = audit_pair_metrics(output_before, output_after)
    print(
        f"🔒 Pixel-Lock Audit: head_diff={metrics['head_diff']} (<=6.0) | "
        f"bg_diff={metrics['bg_diff']} (<=6.0) | "
        f"upper_diff={metrics['upper_diff']} | lower_diff={metrics['lower_diff']}"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate pixel-locked Before/After transformation image pairs using Gemini Nano Banana 2.1"
    )
    parser.add_argument("--before-prompt", help="Prompt to generate the Before image from scratch")
    parser.add_argument("--input-before", help="Path to an existing Before image (skips Before generation)")
    parser.add_argument("--after-edit-prompt", required=True, help="Instruction describing the 1-piece upgrade for the After image")
    parser.add_argument(
        "--swap-zone",
        choices=["upper", "lower", "center", "none"],
        default="lower",
        help="Body/canvas zone to unlock for the After edit while pixel-locking the rest (default: lower)",
    )
    parser.add_argument("--aspect-ratio", default="2:3", help="Image aspect ratio, e.g. 2:3 or 9:16 (default: 2:3)")
    parser.add_argument(
        "--model",
        default=DEFAULT_IMAGE_MODEL,
        help=f"Gemini image generation model (default: {DEFAULT_IMAGE_MODEL}, or gemini-3-pro-image)",
    )
    parser.add_argument("--output-before", default="before.jpg", help="Output path for the Before image")
    parser.add_argument("--output-after", default="after.jpg", help="Output path for the After image")
    parser.add_argument("--gemini-key", help="Gemini API Key override")

    args = parser.parse_args()

    generate_locked_pair(
        after_edit_prompt=args.after_edit_prompt,
        output_before=Path(args.output_before).resolve(),
        output_after=Path(args.output_after).resolve(),
        before_prompt=args.before_prompt,
        input_before=Path(args.input_before).resolve() if args.input_before else None,
        swap_zone=args.swap_zone,
        aspect_ratio=args.aspect_ratio,
        model=args.model,
        gemini_key=args.gemini_key,
    )


if __name__ == "__main__":
    main()
