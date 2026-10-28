#!/usr/bin/env python3
"""
Universal Marketing Video Factory (`video_factory.py`)
------------------------------------------------------
Autonomous end-to-end short-form video generation pipeline for TikTok, Instagram Reels, & YouTube Shorts.
Works with ANY app repository (React Native, Expo, Next.js, iOS, Web) by inspecting the repo's
look & feel (colors, app name, screenshots, value proposition) or reading a custom BrandConfig.

Usage Examples:
  # 1. Inspect a repository and auto-generate its BrandConfig:
  python3 video_factory.py --inspect-repo /path/to/app --save-brand brand.json

  # 2. Render from a campaign template JSON:
  python3 video_factory.py --template examples/moment_friday_hangout.json

  # 3. Brainstorm & render a new campaign from a target persona + app repo via Gemini:
  python3 video_factory.py \
      --repo /path/to/app \
      --persona "25yo remote worker new to NYC who hates awkward networking events" \
      --gemini-key "$GEMINI_API_KEY"
"""

import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspect_repo import inspect_repository, hex_to_rgb
from factory.config import (
    BrandThemeConfig,
    CampaignConfig,
    HookConfig,
    RevealConfig,
    BreakdownConfig,
    BreakdownBullet,
    OutroConfig,
    ProofConfig,
    TakeawayConfig,
)
from factory.audio import build_audio_track, build_native_audio_track
from factory.renderer import VideoRenderer
from factory.script_manager import ScriptReviewManager
from distribution.auth import resolve_gemini_api_key, init_social_config, print_auth_status


def plan_campaign_from_persona(
    persona: str,
    brand_info: Dict[str, Any],
    api_key: Optional[str] = None,
    format_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Uses Gemini to brainstorm a high-retention short-form video campaign tailored to ANY app
    and target persona, adhering strictly to the 5th-grade plain-English clarity standard.
    """
    resolved_key = resolve_gemini_api_key(api_key)
    if not resolved_key:
        raise ValueError(
            "GEMINI_API_KEY is required to brainstorm campaigns from a persona. "
            "Pass `--gemini-key YOUR_KEY`, set `GEMINI_API_KEY` in `.env`, or run `--init-credentials`."
        )

    app_name = brand_info.get("app_name", "Our App")
    tagline = brand_info.get("tagline", "")
    desc = brand_info.get("description", "")
    v_format = format_override or brand_info.get("default_format", "screen_walkthrough")

    print(f"🤖 Brainstorming viral '{v_format}' campaign for {app_name} targeting persona: \"{persona}\" via Gemini...")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={resolved_key}"

    prompt = f"""You are a world-class short-form video creative director for "{app_name}" ({tagline}).
App Description: {desc}
Target Video Format: {v_format}
Target Persona / Angle: "{persona}"

Strict Creative Standards:
1. Plain 5th-Grade English ("Caveman clarity"): Use short, punchy, everyday words. Zero corporate buzzwords.
2. Total spoken word count across all 4 scenes MUST be under 60 words (15-22 seconds total).
3. 4-Scene Narrative:
   - Scene 1 (Hook): Relatable POV dilemma or visual hook for this persona (1 short sentence).
   - Scene 2 (Reveal / Step 1->2): How {app_name} solves it immediately on screen (1-2 short sentences).
   - Scene 3 (Breakdown Sheet): 2 concrete reasons why it works in real life (1-2 short sentences).
   - Scene 4 (Outro CTA): Low-friction call to action (1 short sentence).

Output ONLY a raw JSON object matching this exact schema:
{{
  "name": "snake_case_campaign_name",
  "gender": "neutral",
  "hook_badge": ["Line 1 (max 28 chars)", "Line 2 (max 28 chars)"],
  "hook_vo": "Spoken hook sentence.",
  "step1_title": "Step 1 · Short Label",
  "step2_title": "Step 2 · Short Label",
  "step3_title": "Step 3 · Short Label",
  "reveal_badge": ["Line 1 (max 28 chars)", "Line 2 (max 28 chars)"],
  "reveal_vo": "Spoken reveal explanation.",
  "breakdown_badge": ["Line 1 (max 28 chars)", "Line 2 (max 28 chars)"],
  "breakdown_vo": "Spoken breakdown summary.",
  "sheet_title": "why {app_name.lower()} works",
  "bullet1_title": "2-3 Word Feature Title",
  "bullet1_desc": "Short 6-8 word plain English explanation.",
  "bullet2_title": "2-3 Word Feature Title",
  "bullet2_desc": "Short 6-8 word plain English explanation.",
  "button_text": "Try {app_name} Free",
  "outro_vo": "Spoken outro call to action."
}}
"""
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    })

    cmd = [
        "curl", "-s", "-L", "-X", "POST",
        url,
        "-H", "Content-Type: application/json",
        "-d", payload,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    resp_data = json.loads(res.stdout)
    if "candidates" not in resp_data:
        raise RuntimeError(f"Gemini API error: {resp_data}")
    raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
    plan = json.loads(raw_text)
    print(f"✨ Campaign Strategy Generated: {plan['name']}")
    return plan


def run_pipeline(
    config: CampaignConfig,
    work_dir: str = "/tmp/video_factory_work",
    output_dir: str = "./marketing_output",
) -> str:
    """Executes the full video creation pipeline: TTS -> Audio Mix -> Frame Render -> Mux -> Visual Audit."""
    campaign_work_dir = os.path.join(work_dir, config.name)
    os.makedirs(campaign_work_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, config.output_filename)
    video_format = getattr(config, "format", "screen_walkthrough")

    print("\n" + "=" * 68)
    print(f"🚀 VIDEO FACTORY [{config.brand.app_name.upper()}]: Generating '{config.name}' ({video_format.upper()})")
    if config.screenshots:
        print(f"   Screenshots  : {len(config.screenshots)} screens loaded")
    else:
        print(f"   Before Image : {config.before_image}")
        print(f"   After Image  : {config.after_image}")
    print(f"   Brand Accent : RGB {config.brand.primary_accent_rgb}")
    print(f"   Voice        : {config.voice}")
    print(f"   Target Output: {output_path}")
    print("=" * 68 + "\n")

    pitch_val = getattr(config, "pitch_shift", 0.0)

    if video_format in ("native_loop", "side_by_side_proof"):
        vo_texts = [
            config.hook.voiceover_text,
            config.proof.voiceover_text or config.reveal.voiceover_text,
            config.takeaway.voiceover_text or config.outro.voiceover_text,
        ]
        audio_meta = build_native_audio_track(vo_texts, config.voice or "en_us_001", campaign_work_dir, pitch_shift=pitch_val)
    else:
        vo_texts = [
            config.hook.voiceover_text,
            config.reveal.voiceover_text or config.proof.voiceover_text,
            config.breakdown.voiceover_text,
            config.outro.voiceover_text or config.takeaway.voiceover_text,
        ]
        audio_meta = build_audio_track(vo_texts, config.voice or "en_us_001", campaign_work_dir, pitch_shift=pitch_val)

    temp_mp4 = os.path.join(campaign_work_dir, f"{config.name}_raw_video.mp4")
    renderer = VideoRenderer(config, audio_meta)
    renderer.render_video(temp_mp4)

    print("📦 Muxing final video with master audio...")
    mux_cmd = [
        "ffmpeg", "-y",
        "-i", temp_mp4,
        "-i", audio_meta["master_audio_path"],
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]
    subprocess.run(mux_cmd, capture_output=True, check=True)

    audit_dir = os.path.join(campaign_work_dir, "visual_audit")
    ScriptReviewManager.audit_rendered_video(output_path, extract_dir=audit_dir)

    print("\n" + "=" * 68)
    print(f"🎉 SUCCESS! Final marketing video created and visually certified:")
    print(f"   {output_path}")
    subprocess.run(["ls", "-lh", output_path])
    print("=" * 68 + "\n")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Universal Marketing Video Factory (Skill CLI)")
    parser.add_argument("--repo", type=str, help="Path to target app repository to auto-discover brand look, colors, and screenshots")
    parser.add_argument("--inspect-repo", type=str, help="Inspect the specified repo path, print discovered BrandConfig, and exit")
    parser.add_argument("--brand-config", type=str, help="Path to a saved BrandConfig JSON file")
    parser.add_argument("--save-brand", type=str, help="Save discovered BrandConfig JSON to this path")
    parser.add_argument("--template", type=str, help="Path to a campaign template JSON file")
    parser.add_argument("--persona", type=str, help="Target persona / angle to auto-plan campaign via Gemini")
    parser.add_argument("--gemini-key", type=str, help="Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--init-credentials", action="store_true", help="Initialize ~/.config/video-factory/credentials.json")
    parser.add_argument("--check-auth", action="store_true", help="Check configured Gemini and social publishing credentials")
    parser.add_argument(
        "--format",
        type=str,
        choices=["screen_walkthrough", "before_after_slider", "side_by_side_proof", "app_template", "native_loop"],
        help="Video layout format",
    )
    parser.add_argument("--voice", type=str, default="en_us_001", help="TTS voice ID or preset (e.g. en_us_001, tiktok-jessie, tiktok-male, tiktok-uk)")
    parser.add_argument("--accent-color", type=str, help="Override brand primary accent hex color (e.g. '#FF4E50')")
    parser.add_argument("--app-name", type=str, help="Override brand app name (e.g. 'Moment')")
    parser.add_argument("--screens", nargs="+", help="Explicit list of 2-3 app screenshot paths for screen_walkthrough mode")
    parser.add_argument("--before", type=str, help="Path to before image (for before_after_slider / side_by_side_proof)")
    parser.add_argument("--after", type=str, help="Path to after image (for before_after_slider / side_by_side_proof)")
    parser.add_argument("--output-dir", type=str, default="./marketing_output", help="Directory for rendered MP4 output")
    parser.add_argument("--output", type=str, help="Custom output MP4 filename")
    parser.add_argument("--save-template", type=str, help="Save generated campaign template JSON to this path")
    parser.add_argument("--force", action="store_true", help="Bypass Script Review Manager editorial gate")
    parser.add_argument("--publish", action="store_true", help="Publish rendered video via headless distributor")
    parser.add_argument("--dry-run-publish", action="store_true", help="Run social distribution in dry-run simulation mode")
    parser.add_argument("--platforms", type=str, default="youtube,instagram,facebook,tiktok", help="Comma-separated platforms for --publish")

    args = parser.parse_args()
    target_platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    if args.init_credentials:
        path = init_social_config(gemini_key=args.gemini_key or "")
        print(f"✨ Initialized Video Factory credentials file at: {path}")
        return

    if args.check_auth:
        print_auth_status(brand=args.app_name or "default")
        return

    if args.inspect_repo:
        info = inspect_repository(args.inspect_repo)
        if args.save_brand:
            Path(args.save_brand).write_text(json.dumps(info, indent=2), encoding="utf-8")
            print(f"💾 Saved BrandConfig to: {args.save_brand}")
        print(json.dumps(info, indent=2))
        return

    # Load or discover BrandConfig if --repo or --brand-config is supplied
    brand_info: Dict[str, Any] = {}
    if args.brand_config and os.path.exists(args.brand_config):
        brand_info = json.loads(Path(args.brand_config).read_text(encoding="utf-8"))
    elif args.repo:
        brand_info = inspect_repository(args.repo)
        if args.save_brand:
            Path(args.save_brand).write_text(json.dumps(brand_info, indent=2), encoding="utf-8")

    # Apply CLI overrides to brand_info
    if args.app_name:
        brand_info["app_name"] = args.app_name
    if args.accent_color:
        brand_info.setdefault("theme", {})["primary_accent_rgb"] = hex_to_rgb(args.accent_color)

    # Mode 1: Render from a Campaign Template JSON
    if args.template:
        print(f"📂 Loading campaign template from: {args.template}")
        with open(args.template, "r", encoding="utf-8") as f:
            raw_tmpl = json.load(f)

        # Resolve relative screenshot/image paths relative to template parent or repo
        tmpl_dir = Path(args.template).resolve().parent
        repo_base = Path(args.repo).resolve() if args.repo else Path.cwd()

        def _resolve_asset(p_str: str) -> str:
            if not p_str or os.path.isabs(p_str) and os.path.exists(p_str):
                return p_str
            for base in [Path.cwd(), repo_base, tmpl_dir, tmpl_dir.parent.parent]:
                cand = (base / p_str).resolve()
                if cand.exists():
                    return str(cand)
            return p_str

        if "screenshots" in raw_tmpl:
            raw_tmpl["screenshots"] = [_resolve_asset(s) for s in raw_tmpl["screenshots"]]
        if raw_tmpl.get("before_image"):
            raw_tmpl["before_image"] = _resolve_asset(raw_tmpl["before_image"])
        if raw_tmpl.get("after_image"):
            raw_tmpl["after_image"] = _resolve_asset(raw_tmpl["after_image"])

        if args.screens:
            raw_tmpl["screenshots"] = [str(Path(s).resolve()) for s in args.screens]
        if args.before:
            raw_tmpl["before_image"] = str(Path(args.before).resolve())
        if args.after:
            raw_tmpl["after_image"] = str(Path(args.after).resolve())

        mgr = ScriptReviewManager(raw_tmpl)
        if not mgr.print_editorial_report() and not args.force:
            print("🛑 Video generation aborted by Script Review Manager. Fix editorial flags or pass --force.")
            sys.exit(1)

        config = CampaignConfig.from_json(args.template, brand_override=brand_info)
        config.screenshots = raw_tmpl.get("screenshots", config.screenshots)
        config.before_image = raw_tmpl.get("before_image", config.before_image)
        config.after_image = raw_tmpl.get("after_image", config.after_image)

        if args.format:
            config.format = args.format
        if args.voice:
            config.voice = args.voice
        if args.accent_color:
            config.brand.primary_accent_rgb = hex_to_rgb(args.accent_color)
        if args.app_name:
            config.brand.app_name = args.app_name
        if args.output:
            config.output_filename = args.output

        out_path = run_pipeline(config, output_dir=args.output_dir)
        if args.publish or args.dry_run_publish:
            from distribute import distribute_video
            distribute_video(
                Path(out_path),
                platforms=target_platforms,
                brand=config.brand.app_name.lower(),
                dry_run=args.dry_run_publish,
            )
        return

    # Mode 2: Brainstorm & Render from Persona + Repo/BrandConfig via Gemini
    if args.persona:
        if not brand_info:
            brand_info = inspect_repository(".")
        plan = plan_campaign_from_persona(
            persona=args.persona,
            brand_info=brand_info,
            api_key=args.gemini_key,
            format_override=args.format,
        )

        discovered = brand_info.get("discovered_assets", {})
        screens = args.screens or discovered.get("screenshots", [])[:3]
        pairs = discovered.get("before_after_pairs", [])
        before_img = args.before or (pairs[0][0] if pairs else (screens[0] if screens else ""))
        after_img = args.after or (pairs[0][1] if pairs else (screens[1] if len(screens) > 1 else before_img))

        chosen_format = args.format or brand_info.get("default_format", "screen_walkthrough")
        theme_dict = brand_info.get("theme", {})
        app_name = brand_info.get("app_name", "App")
        tagline = brand_info.get("tagline", "")

        brand_cfg = BrandThemeConfig(
            app_name=app_name,
            tagline=tagline,
            header_badge_text=theme_dict.get("header_badge_text", "Live on iOS"),
            primary_accent_rgb=theme_dict.get("primary_accent_rgb", [255, 78, 80]),
            surface_bg_rgb=theme_dict.get("surface_bg_rgb", [18, 18, 22]),
        )

        out_name = args.output or f"{app_name.lower()}_{plan['name']}.mp4"

        config = CampaignConfig(
            name=plan["name"],
            output_filename=out_name,
            format=chosen_format,
            voice=args.voice or "en_us_001",
            fps=30,
            screenshots=screens,
            before_image=before_img,
            after_image=after_img,
            step1_title=plan.get("step1_title", "Step 1 · Discover"),
            step2_title=plan.get("step2_title", "Step 2 · Match"),
            step3_title=plan.get("step3_title", "Step 3 · Meet IRL"),
            brand=brand_cfg,
            hook=HookConfig(
                badge_lines=plan["hook_badge"],
                voiceover_text=plan["hook_vo"],
            ),
            reveal=RevealConfig(
                badge_lines=plan["reveal_badge"],
                voiceover_text=plan["reveal_vo"],
            ),
            breakdown=BreakdownConfig(
                badge_lines=plan["breakdown_badge"],
                voiceover_text=plan["breakdown_vo"],
                sheet_title=plan.get("sheet_title", f"why {app_name.lower()} works"),
                bullets=[
                    BreakdownBullet(title=plan["bullet1_title"], description=plan["bullet1_desc"]),
                    BreakdownBullet(title=plan["bullet2_title"], description=plan["bullet2_desc"]),
                ],
                button_text=plan.get("button_text", f"Try {app_name} Free"),
            ),
            outro=OutroConfig(
                app_title=f"{app_name} — {tagline}" if tagline else app_name,
                subtitle=brand_info.get("description", "")[:65],
                cta_button_text=f"Try {app_name} Free",
                bottom_pill_lines=["Free on the App Store", "Link in bio"],
                voiceover_text=plan["outro_vo"],
            ),
        )

        if args.save_template:
            config.to_json(args.save_template)
            print(f"💾 Saved generated campaign template to: {args.save_template}")

        out_path = run_pipeline(config, output_dir=args.output_dir)
        if args.publish or args.dry_run_publish:
            from distribute import distribute_video
            distribute_video(
                Path(out_path),
                platforms=target_platforms,
                brand=app_name.lower(),
                dry_run=args.dry_run_publish,
            )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
