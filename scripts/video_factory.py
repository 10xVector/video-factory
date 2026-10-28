#!/usr/bin/env python3
"""
Universal Marketing Video Factory (`video_factory.py`)
------------------------------------------------------
Autonomous end-to-end short-form video generation pipeline for TikTok, Instagram Reels, & YouTube Shorts.
Works with ANY app repository (React Native, Expo, Next.js, iOS, Web) by inspecting the repo's
look & feel (colors, app name, screenshots, value proposition) or reading a custom BrandConfig.

Supports 3 built-in video formats + batch series generation (`--count 10`):
  1. `before_after_slider`  : Full-screen Before -> After wipe slider + 2-point breakdown + CTA
  2. `side_by_side_proof`   : Split-screen comparison + visual callout + takeaway punchline
  3. `screen_walkthrough`   : 3-step app screen tour + feature sheet + CTA

Usage Examples:
  # 1. Inspect a repository and auto-generate its BrandConfig:
  python3 scripts/video_factory.py --inspect-repo /path/to/app --save-brand brand.json

  # 2. Render from a campaign template JSON:
  python3 scripts/video_factory.py --template examples/glow_before_after.json

  # 3. Brainstorm & render a 10-video series following an example format via Gemini:
  python3 scripts/video_factory.py \
      --repo /path/to/app \
      --example-template examples/glow_before_after.json \
      --persona "12-axis style methodology — 1-piece outfit upgrades for everyday men and women" \
      --count 10 \
      --generate-images
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


DEFAULT_TEXT_MODEL = "gemini-3.8-flash"
API_REVISION = "2026-05-20"


def _call_gemini_json(prompt: str, api_key: str, model: str = DEFAULT_TEXT_MODEL) -> Any:
    """
    Calls Gemini (`gemini-3.8-flash`) via the official `google-genai` Interactions API
    when installed, with a direct REST fallback. Parses and returns JSON output.
    """
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key)
        if hasattr(client, "interactions"):
            interaction = client.interactions.create(
                model=model,
                input=prompt,
                response_format={"type": "json"},
            )
            raw = getattr(interaction, "output_text", None) or ""
            if raw:
                return json.loads(raw)
    except Exception:
        pass

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
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
    return json.loads(raw_text)


def plan_campaign_from_persona(
    persona: str,
    brand_info: Dict[str, Any],
    api_key: Optional[str] = None,
    format_override: Optional[str] = None,
    example_template: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Uses Gemini (`gemini-3.8-flash`) to brainstorm a single high-retention short-form video campaign.
    """
    episodes = plan_series_from_persona(
        persona=persona,
        brand_info=brand_info,
        count=1,
        api_key=api_key,
        format_override=format_override,
        example_template=example_template,
    )
    return episodes[0]


def plan_series_from_persona(
    persona: str,
    brand_info: Dict[str, Any],
    count: int = 1,
    api_key: Optional[str] = None,
    format_override: Optional[str] = None,
    example_template: Optional[Dict[str, Any]] = None,
    previous_episodes: Optional[List[Dict[str, Any]]] = None,
    start_episode_index: int = 1,
) -> List[Dict[str, Any]]:
    """
    Uses Gemini (`gemini-3.8-flash`) to brainstorm `count` distinct episodes (e.g. 1 or 10 videos)
    following an optional `example_template` structure and adhering to 5th-grade plain-English clarity.
    When `previous_episodes` is provided (e.g. `--daily` mode), avoids repeating any past hooks or swaps.
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
    v_format = (
        format_override
        or (example_template.get("format") if example_template else None)
        or brand_info.get("default_format", "screen_walkthrough")
    )

    example_block = ""
    if example_template:
        example_block = (
            "\nFollow the exact pacing, badge style, and narrative rhythm of this reference template:\n"
            f"{json.dumps(example_template, indent=2)}\n"
        )

    history_block = ""
    if previous_episodes:
        past_summary = [
            f"- {ep.get('name')}: {' / '.join(ep.get('hook_badge', []))} -> {' / '.join(ep.get('reveal_badge', []))}"
            for ep in previous_episodes[-30:]
        ]
        history_block = (
            f"\nPreviously Generated Episodes (DO NOT repeat these mistakes, garments, or hooks; "
            f"start numbering at ep{start_episode_index:02d}_...):\n"
            + "\n".join(past_summary)
            + "\n"
        )

    print(
        f"🤖 Brainstorming {count} '{v_format}' episode(s) (starting at #{start_episode_index}) for {app_name} "
        f"targeting: \"{persona}\" via {DEFAULT_TEXT_MODEL}..."
    )

    prompt = f"""You are a world-class short-form video creative director for "{app_name}" ({tagline}).
App Description: {desc}
Target Video Format: {v_format}
Series Theme / Target Persona: "{persona}"
Number of Distinct Episodes to Generate: {count}
Starting Episode Number: ep{start_episode_index:02d}
{example_block}{history_block}
Strict Creative Standards for EVERY Episode:
1. Plain 5th-Grade English ("Caveman clarity"): Use short, punchy, everyday words. Zero corporate buzzwords.
2. Total spoken word count across all 4 scenes MUST be under 60 words (15-20 seconds total).
3. 4-Scene Narrative:
   - Scene 1 (Hook): Relatable visual mistake, dilemma, or base look score (1 short sentence).
   - Scene 2 (Reveal): The 1-piece swap or instant app solution that fixes it (1-2 short sentences).
   - Scene 3 (Breakdown Sheet): 2 concrete reasons why it works (1 short sentence).
   - Scene 4 (Outro CTA): Low-friction call to action (1 short sentence).
4. If generating Before/After transformations, specify `swap_zone` ("lower" for pants/skirt/shoes swaps, or "upper" for shirt/jacket/layer swaps) plus `before_image_prompt` and `after_edit_prompt` so Nano Banana 2.1 can generate a pixel-locked pair.

Output ONLY a JSON object with key "episodes" containing a list of {count} episode objects matching this exact schema:
{{
  "episodes": [
    {{
      "name": "ep{start_episode_index:02d}_snake_case_name",
      "gender": "female or male or neutral",
      "swap_zone": "lower or upper",
      "before_score": "7.8",
      "after_score": "9.4",
      "hook_badge": ["Line 1 (max 28 chars)", "Line 2 (max 28 chars)"],
      "hook_vo": "Spoken hook sentence.",
      "step1_title": "1 Swap · Short Label",
      "step2_title": "Dim 2 · Short Label",
      "step3_title": "Dim 3 · Short Label",
      "reveal_badge": ["Line 1 (max 28 chars)", "Line 2 (max 28 chars)"],
      "reveal_vo": "Spoken reveal explanation.",
      "breakdown_badge": ["Line 1 (max 28 chars)"],
      "breakdown_vo": "Spoken breakdown summary.",
      "sheet_title": "why {app_name.lower()} works",
      "bullet1_title": "2-4 Word Feature Title",
      "bullet1_desc": "Short 6-9 word plain English explanation.",
      "bullet2_title": "2-4 Word Feature Title",
      "bullet2_desc": "Short 6-9 word plain English explanation.",
      "button_text": "Save Before & After Video",
      "outro_vo": "Spoken outro call to action.",
      "before_image_prompt": "Full-body 2:3 vertical street style portrait prompt for the Before look.",
      "after_edit_prompt": "Instruction to swap ONLY the target garment zone while keeping face, pose, and background identical."
    }}
  ]
}}
"""
    data = _call_gemini_json(prompt, api_key=resolved_key, model=DEFAULT_TEXT_MODEL)
    episodes = data.get("episodes", [data] if isinstance(data, dict) and "name" in data else [])
    if not episodes:
        raise RuntimeError(f"Gemini did not return valid episodes: {data}")
    print(f"✨ Generated {len(episodes)} episode plan(s)!")
    return episodes


def format_series_markdown_table(episodes: List[Dict[str, Any]]) -> str:
    """Formats a batch of planned episodes as a clean Markdown table."""
    lines = [
        "| # | Episode | Hook (Before) | 1-Piece Upgrade (After) | Score | Why It Works (Breakdown) |",
        "|---|---|---|---|---|---|",
    ]
    for idx, ep in enumerate(episodes, 1):
        name = ep.get("name", f"ep{idx:02d}")
        hook = " — ".join(ep.get("hook_badge", []))
        reveal = " — ".join(ep.get("reveal_badge", []))
        b_score = ep.get("before_score", "7.8")
        a_score = ep.get("after_score", "9.4")
        why = f"**{ep.get('bullet1_title', '')}** + **{ep.get('bullet2_title', '')}**"
        lines.append(f"| {idx} | `{name}` | {hook} | {reveal} | {b_score} → **{a_score}** | {why} |")
    return "\n".join(lines)


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
    parser.add_argument("--template", type=str, help="Path to a campaign template JSON file to render directly")
    parser.add_argument("--example-template", type=str, help="Path to an example template JSON whose format/pacing Gemini should clone across --count videos")
    parser.add_argument("--persona", type=str, help="Target persona / series theme to auto-plan campaign(s) via Gemini")
    parser.add_argument("--count", type=int, default=1, help="Number of distinct videos to plan and render in batch (e.g., --count 10)")
    parser.add_argument("--daily", action="store_true", help="Daily autopilot mode: reads daily_history.json in --output-dir, generates the next non-repeating episode (#N), and updates SERIES_TRACKER.md")
    parser.add_argument("--plan-only", action="store_true", help="Generate and print the episode series table + JSON templates without rendering MP4s")
    parser.add_argument("--generate-images", action="store_true", help="Auto-generate pixel-locked Before & After photos via Gemini Nano Banana 2.1 (generate_pair.py)")
    parser.add_argument("--swap-zone", choices=["lower", "upper", "center", "none"], help="Override swap zone for --generate-images")
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

        tmpl_dir = Path(args.template).resolve().parent
        repo_base = Path(args.repo).resolve() if args.repo else Path.cwd()

        def _resolve_asset(p_str: str) -> str:
            if not p_str or os.path.isabs(p_str) and os.path.exists(p_str):
                return p_str
            for base in [Path.cwd(), repo_base, tmpl_dir, tmpl_dir.parent, tmpl_dir.parent.parent]:
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

    # Mode 2: Brainstorm & Render 1 or N Episodes from Persona (+ optional Example Template) via Gemini
    if args.persona:
        if not brand_info:
            brand_info = inspect_repository(".")

        example_tmpl_dict: Optional[Dict[str, Any]] = None
        if args.example_template and os.path.exists(args.example_template):
            example_tmpl_dict = json.loads(Path(args.example_template).read_text(encoding="utf-8"))
            if not args.app_name and "brand" in example_tmpl_dict:
                brand_info.setdefault("app_name", example_tmpl_dict["brand"].get("app_name", "App"))
                brand_info.setdefault("tagline", example_tmpl_dict["brand"].get("tagline", ""))
                brand_info.setdefault("theme", example_tmpl_dict["brand"])

        os.makedirs(args.output_dir, exist_ok=True)
        history_path = Path(args.output_dir) / "daily_history.json"
        past_episodes: List[Dict[str, Any]] = []
        if args.daily and history_path.exists():
            try:
                past_episodes = json.loads(history_path.read_text(encoding="utf-8"))
                print(f"📅 Daily Autopilot: Loaded {len(past_episodes)} previously generated episode(s) from {history_path}")
            except Exception:
                past_episodes = []

        start_ep_idx = len(past_episodes) + 1

        episodes = plan_series_from_persona(
            persona=args.persona,
            brand_info=brand_info,
            count=max(1, args.count),
            api_key=args.gemini_key,
            format_override=args.format,
            example_template=example_tmpl_dict,
            previous_episodes=past_episodes if args.daily else None,
            start_episode_index=start_ep_idx,
        )

        if args.daily:
            from datetime import datetime, timezone
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for ep in episodes:
                ep["generated_date"] = today_str
            past_episodes.extend(episodes)
            history_path.write_text(json.dumps(past_episodes, indent=2), encoding="utf-8")
            tracker_md = format_series_markdown_table(past_episodes)
            tracker_path = Path(args.output_dir) / "SERIES_TRACKER.md"
            tracker_path.write_text(f"# Daily Autopilot Series Tracker ({len(past_episodes)} Total Episodes)\n\n{tracker_md}\n", encoding="utf-8")
            print(f"📅 Updated Daily Autopilot ledger ({history_path}) & tracker ({tracker_path})")

        series_table_md = format_series_markdown_table(episodes)
        print("\n📋 PLANNED EPISODE SERIES TABLE:\n")
        print(series_table_md)
        print()

        table_path = Path(args.output_dir) / "episode_series_plan.md"
        table_path.write_text(f"# Planned Video Series ({len(episodes)} Episodes)\n\n{series_table_md}\n", encoding="utf-8")
        print(f"💾 Saved Markdown episode table to: {table_path}")

        if args.plan_only:
            return

        discovered = brand_info.get("discovered_assets", {})
        screens = args.screens or discovered.get("screenshots", [])[:3]
        pairs = discovered.get("before_after_pairs", [])

        chosen_format = (
            args.format
            or (example_tmpl_dict.get("format") if example_tmpl_dict else None)
            or brand_info.get("default_format", "screen_walkthrough")
        )
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

        rendered_outputs: List[str] = []
        for idx, plan in enumerate(episodes):
            ep_name = plan["name"]
            pair_idx = idx % len(pairs) if pairs else 0
            before_img = args.before or (pairs[pair_idx][0] if pairs else (screens[0] if screens else ""))
            after_img = args.after or (pairs[pair_idx][1] if pairs else (screens[1] if len(screens) > 1 else before_img))

            # Optional AI Before/After pair generation via Gemini Nano Banana 2.1 + Pixel Lock
            if args.generate_images and plan.get("after_edit_prompt"):
                from generate_pair import generate_locked_pair

                assets_dir = Path(args.output_dir) / "assets"
                gen_before = assets_dir / f"{ep_name}_before.jpg"
                gen_after = assets_dir / f"{ep_name}_after.jpg"
                zone = args.swap_zone or plan.get("swap_zone", "lower")
                generate_locked_pair(
                    before_prompt=plan.get("before_image_prompt"),
                    input_before=Path(args.before) if args.before else None,
                    after_edit_prompt=plan["after_edit_prompt"],
                    swap_zone=zone,
                    output_before=gen_before,
                    output_after=gen_after,
                    gemini_key=args.gemini_key,
                )
                before_img = str(gen_before)
                after_img = str(gen_after)

            out_name = (
                args.output
                if (args.output and len(episodes) == 1)
                else f"{app_name.lower()}_{ep_name}.mp4"
            )

            config = CampaignConfig(
                name=ep_name,
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

            tmpl_save_path = (
                args.save_template
                if (args.save_template and len(episodes) == 1)
                else os.path.join(args.output_dir, f"{ep_name}.json")
            )
            config.to_json(tmpl_save_path)
            print(f"💾 Saved campaign template JSON to: {tmpl_save_path}")

            out_path = run_pipeline(config, output_dir=args.output_dir)
            rendered_outputs.append(out_path)
            if args.publish or args.dry_run_publish:
                from distribute import distribute_video
                distribute_video(
                    Path(out_path),
                    platforms=target_platforms,
                    brand=app_name.lower(),
                    dry_run=args.dry_run_publish,
                )

        if len(rendered_outputs) > 1:
            print("\n" + "=" * 68)
            print(f"🏆 BATCH SERIES COMPLETE: Rendered {len(rendered_outputs)} videos:")
            for p in rendered_outputs:
                print(f"   🎬 {p}")
            print("=" * 68 + "\n")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
