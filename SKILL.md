---
name: video-factory
description: >-
  Generate high-retention 9:16 short-form marketing videos (TikTok, Instagram Reels, YouTube Shorts)
  for any mobile or web app repository. Automatically inspects the target repo to extract the app's
  look and feel (brand colors, app name, tagline, value proposition, and screenshots), configures
  voiceover TTS and Gemini campaign planning, renders 1080x1920 vertical MP4s with visual QA, and
  optionally distributes to YouTube Shorts, Instagram Reels, Facebook Reels, and TikTok. Use when
  the user wants to create marketing videos, TikTok/Reels/Shorts campaigns, app promo videos, or
  before/after ads for any app or repository.
---

# Universal Marketing Video Factory (`video-factory`)

This skill turns any mobile or web application repository into an autonomous short-form video production and social distribution studio. It works seamlessly across **Claude Code**, **Antigravity**, **Cursor**, and **Codex**.

## Installation (For Claude Code, Antigravity, Cursor, & Codex)

```bash
# Clone & install into ~/.claude/skills/video-factory and ~/.agents/skills/video-factory:
git clone https://github.com/10xVector/video-factory.git
cd video-factory && ./install.sh
```

> **Note on Script Paths**: In the commands below, `<SKILL_DIR>` refers to wherever this skill is installed (e.g., `~/.claude/skills/video-factory`, `~/.agents/skills/video-factory`, or `.claude/skills/video-factory`).

## Prerequisites

- **System**: `python3` (with `Pillow`), `ffmpeg` / `ffprobe`, `curl`
- **Optional API Keys** (stored in `~/.config/video-factory/credentials.json` or `.env`):
  - `GEMINI_API_KEY`: Required only when auto-brainstorming new scripts/campaigns from a persona (`--persona`).
  - Social Publishing Tokens (YouTube OAuth, Meta Graph API, TikTok API, S3/R2 staging bucket): Required only when publishing live (`--publish`).

---

## Agent Workflow: How to Run the Video Factory

Whenever the user asks to create a marketing video or campaign for an app, follow these 4 steps:

### Step 1: Discover the Target App's Look & Feel (`inspect_repo.py`)

Run `inspect_repo.py` against the target repository path (defaults to current repo `.` or any repo path the user specifies, such as `~/code/Moment`, `~/code/glow`, etc.):

```bash
python3 .agents/skills/video-factory/scripts/inspect_repo.py /path/to/repo --save /tmp/brand_config.json
```
*(If running from global skills directory `~/.claude/skills/video-factory`, adjust the script path to `~/.claude/skills/video-factory/scripts/inspect_repo.py`.)*

This automatically extracts:
- **App Identity**: `app_name`, `tagline`, and `description` from `app.json`, `package.json`, and `README.md`.
- **Brand Palette**: Primary accent color (`primary_accent_hex` / RGB) and dark surface background color from `tailwind.config.*` or `globals.css`.
- **App Screenshots & Assets**: Discovers portrait UI screenshots (`web/public/marketing/`, `screenshots/`) and before/after pairs (`*_before.jpg` / `*_after.jpg`).
- **Recommended Visual Layout**:
  - `screen_walkthrough` — Best for apps with UI screens (e.g., Moment, SaaS, social, productivity). Cycles through 3 app screenshots inside a glass bezel iOS frame, then reveals a customized feature breakdown card and CTA outro.
  - `before_after_slider` — Best for visual transformation apps (e.g., Glow, photo editing, fitness, interior design). Smoothly wipes a `< >` comparison slider across Before & After images, then shows a scoring/coaching breakdown sheet.
  - `side_by_side_proof` — Split-screen Before vs. After visual proof loop.

---

### Step 2: Confirm Preferences & Missing Credentials with the User

Present the auto-discovered **App Name**, **Primary Accent Color**, **Screenshots Found**, and **Recommended Format** to the user, and confirm (or ask if not yet specified):

1. **Target Repo & Screenshots**: Confirm which 2–3 screenshots (or before/after images) to feature.
2. **Look & Feel Overrides**: Ask if they want to keep the auto-detected brand accent color (e.g., `#FF4E50`) and header badge text (e.g., `"Live Nearby"`), or customize them.
3. **Voice Selection (`--voice`)**:
   - `en_us_001` (`tiktok-jessie` — Canonical OG TikTok Female voice, highest trust & retention, **default**)
   - `en_us_006` (`tiktok-male` — TikTok Male voice)
   - `en_male_narration` (`tiktok-narrator` — Storyteller narrator)
   - `en_uk_001` (`tiktok-uk` — British voice)
   - `en_au_001` (`tiktok-au` — Australian voice)
4. **Credentials Check** (only if needed):
   - If generating a campaign dynamically via `--persona`, check if `GEMINI_API_KEY` is set (`python3 .../video_factory.py --check-auth`). If missing, ask the user for their Gemini API key and save it with:
     ```bash
     python3 .agents/skills/video-factory/scripts/video_factory.py --init-credentials --gemini-key "USER_KEY"
     ```
   - Alternatively, **you (the agent)** can author the campaign JSON template directly using the schema in `examples/moment_friday_hangout.json` — which requires **zero Gemini API key**!

---

### Step 3: Author or Plan the Campaign & Render the Video

You can generate the video in two ways:

#### Option A: Agent-Authored Campaign Template (Zero API Key Needed — Recommended)
Copy and customize one of the bundled templates:
- App Screen Walkthrough: [examples/moment_friday_hangout.json](examples/moment_friday_hangout.json)
- Before/After Slider: [examples/glow_before_after.json](examples/glow_before_after.json)

Ensure the voiceover copy obeys the **Executive Editorial QA Gates** enforced by `script_manager.py`:
- **Plain 5th-Grade English**: Flesch-Kincaid grade level <= 6.5. Short, everyday words; zero academic or corporate buzzwords.
- **High-Retention Pacing**: Total spoken word count <= 75 words across all 4 scenes (renders to an optimal 15–24 second video).
- **100% PG Brand Safety**: No violent or morbid metaphors.

Then run the renderer:
```bash
python3 .agents/skills/video-factory/scripts/video_factory.py \
  --template /path/to/campaign.json \
  --voice en_us_001 \
  --output-dir ./marketing_output
```

#### Option B: Auto-Brainstorm 1 or 10+ Videos from a Persona / Example Format via Gemini (`--persona` + `--count 10`)
If the user provided a `GEMINI_API_KEY` and wants Gemini (`gemini-3.8-flash`) to plan a single video or a **10-video batch series** following an example template format (and optionally generate pixel-locked Before/After photos via `gemini-nano-banana-2.1` + `scripts/generate_pair.py`):
```bash
# Generate a 10-episode series following an example video format:
python3 .agents/skills/video-factory/scripts/video_factory.py \
  --repo /path/to/repo \
  --example-template .agents/skills/video-factory/examples/glow_before_after.json \
  --persona "12-axis fashion methodology — 1-piece outfit upgrades for everyday men and women" \
  --count 10 \
  --generate-images \
  --voice en_us_001 \
  --output-dir ./marketing_output

# Or generate a single pixel-locked Before/After photo pair directly:
python3 .agents/skills/video-factory/scripts/generate_pair.py \
  --before-prompt "Full-body 2:3 street style photo of a 30yo man wearing an olive jacket and wrinkled beige chinos." \
  --after-edit-prompt "Swap ONLY the wrinkled beige chinos for dark brown pleated wool trousers and loafers." \
  --swap-zone lower \
  --output-before ./marketing_output/assets/before.jpg \
  --output-after ./marketing_output/assets/after.jpg
```

---

### Step 4: Post-Render Visual Audit & Optional Multi-Platform Distribution

1. Every run automatically extracts milestone frames (`s1_hook`, `s2_transition`, `s3_breakdown_sheet`, `s4_outro_cta`) via `ffmpeg` and verifies frame integrity.
2. Inspect the extracted milestone frames in `/tmp/video_factory_work/<campaign_name>/visual_audit/` to visually confirm typography, contrast, and screenshot framing.
3. If the user wants to publish or dry-run social distribution to **YouTube Shorts, Instagram Reels, Facebook Reels, and TikTok**:
   ```bash
   # Check configured social tokens for a brand profile:
   python3 .agents/skills/video-factory/scripts/distribute.py --check-auth --brand moment

   # Dry-run multi-platform distribution:
   python3 .agents/skills/video-factory/scripts/distribute.py \
     --video ./marketing_output/moment_friday_night_irl.mp4 \
     --brand moment \
     --platforms youtube,instagram,facebook,tiktok \
     --dry-run
   ```

---

## CLI Quick Reference

| Flag | Description |
| :--- | :--- |
| `--inspect-repo <path>` | Scans a repo for app name, colors, and screenshots, and outputs `BrandConfig` JSON |
| `--repo <path>` | Uses auto-discovered brand look & screenshots from `<path>` |
| `--template <file.json>` | Renders a campaign from a JSON template |
| `--persona "<text>"` | Plans a campaign script via Gemini for the target persona |
| `--format <mode>` | `screen_walkthrough`, `before_after_slider`, or `side_by_side_proof` |
| `--voice <id>` | `en_us_001` (Jessie), `en_us_006` (Male), `en_uk_001` (UK), `en_au_001` (AU) |
| `--accent-color "#HEX"` | Overrides the primary brand accent color |
| `--app-name "Name"` | Overrides the header app title |
| `--screens s1.png s2.png s3.png` | Overrides the screenshots used in `screen_walkthrough` |
| `--before b.jpg --after a.jpg` | Overrides the images used in `before_after_slider` / `side_by_side_proof` |
| `--init-credentials` | Creates `~/.config/video-factory/credentials.json` (`0600` permissions) |
| `--dry-run-publish` | Simulates publishing to YouTube, Instagram, Facebook, and TikTok |
| `--publish` | Publishes live to the selected `--platforms` |
