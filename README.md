# 🎬 Universal Marketing Video Factory (`video-factory`)

An autonomous **Agent Skill & CLI Engine** for **Claude Code**, **Antigravity**, **Cursor**, and **Codex** that turns any mobile or web app repository into a high-retention 9:16 short-form video studio (TikTok, Instagram Reels, YouTube Shorts, Facebook Reels).

Point your AI coding agent at **any app repository**, and `video-factory` will:
1. **Auto-Inspect Your Repo's Look & Feel** (`scripts/inspect_repo.py`): Reads `app.json`, `package.json`, `README.md`, `tailwind.config.*`, and `globals.css` to extract your app name, tagline, value proposition, brand accent color, dark surface color, and existing screenshots.
2. **Choose the Optimal Visual Template (`scripts/factory/renderer.py`)**:
   - 📱 **`screen_walkthrough`**: Cycles through 2–3 real app UI screenshots inside an iOS status-bar frame with animated step callout pills, a dual-screen feature breakdown card, and a brand-colored CTA outro.
   - ✨ **`before_after_slider`**: Interactive `< >` comparison slider wipe across Before & After images with a multi-axis scoring & coaching sheet (ideal for photo, fashion, fitness, or design apps).
   - ⚖️ **`side_by_side_proof`**: Split-screen Before vs. After visual proof loop.
3. **Generate High-Trust Voiceovers & Master Audio (`scripts/factory/audio.py`)**: Uses the native OG TikTok TTS voices (`en_us_001` Jessie, `en_us_006` Male, `en_uk_001` British, `en_au_001` Australian) with `ffmpeg` loudness normalization (`dynaudnorm`) and transition pop SFX.
4. **Enforce Executive Quality Gates (`scripts/factory/script_manager.py`)**: Certifies 5th-grade plain-English readability (Flesch-Kincaid <= 6.5), high-retention pacing (< 75 words / 15–24s), PG brand safety, and post-render milestone frame extraction.
5. **Publish Headlessly (`scripts/distribute.py`)**: Optional one-command distribution to **YouTube Shorts**, **Instagram Reels**, **Facebook Reels**, and **TikTok**.

---

## 🚀 Quick Install (For Claude Code, Antigravity, Cursor, & Codex Users)

### Option 1: One-Line Installer
Clone and run the installer to register `video-factory` globally across `~/.claude/skills/`, `~/.agents/skills/`, and `~/.gemini/config/skills/`:

```bash
git clone https://github.com/10xVector/video-factory.git
cd video-factory
./install.sh
```

### Option 2: Direct Clone into Claude Code or Workspace
```bash
# Global install for Claude Code (available in all your projects):
git clone https://github.com/10xVector/video-factory.git ~/.claude/skills/video-factory

# Global install for Antigravity / Codex / Cursor:
git clone https://github.com/10xVector/video-factory.git ~/.agents/skills/video-factory

# Or per-project install inside your app repository:
git clone https://github.com/10xVector/video-factory.git .claude/skills/video-factory
```

### System Requirements
- **macOS or Linux** with `python3` (3.9+)
- **FFmpeg** (`brew install ffmpeg` on macOS or `apt install ffmpeg` on Ubuntu)
- **Pillow** (`pip install Pillow`)

---

## 💬 How to Use with Claude Code or Antigravity

Once installed, simply ask your agent in natural language inside any project:

> *"Use the `video-factory` skill to create a 20-second TikTok marketing video for this repo. Inspect our app's colors and screenshots, use the OG TikTok Jessie voice, and target a Friday night hangout angle."*

Or specify a target repo, look, and voice:

> *"Run `video-factory` on `~/code/my-app` with accent color `#6366F1`, voice `en_us_001`, and our 3 onboarding screenshots."*

### What the Agent Will Ask / Configure for You
1. **Target Repo & Screenshots**: Auto-detected from `screenshots/`, `public/marketing/`, or `assets/` (or you can specify any 2–3 portrait images).
2. **App Look & Brand Theme**: Auto-extracted from your Tailwind/CSS theme (`primary_accent_rgb`, `surface_bg_rgb`, `app_name`, `tagline`), with full support for custom overrides.
3. **Voice Selection**:
   - `en_us_001` (`tiktok-jessie` — OG TikTok Female voice, **default**)
   - `en_us_006` (`tiktok-male` — TikTok Male voice)
   - `en_male_narration` (`tiktok-narrator` — Storyteller narrator)
   - `en_uk_001` (`tiktok-uk` — British voice)
   - `en_au_001` (`tiktok-au` — Australian voice)
4. **Credentials (Optional)**:
   - **No API Key Needed for Agent-Authored Campaigns**: When running inside Claude Code or Antigravity, the agent can write the campaign JSON directly using your repo's context—requiring **zero external LLM API keys**.
   - **Gemini API Key (`GEMINI_API_KEY`)**: Only needed if you run the standalone CLI `--persona` mode to have Gemini brainstorm the script.

---

## 🛠️ Standalone CLI Usage

You can also run the Video Factory directly from your terminal without an agent:

### 1. Inspect Any App Repository
Automatically extract a repo's brand colors, app name, tagline, and screenshots into a `brand.json` file:
```bash
python3 scripts/inspect_repo.py /path/to/your/app --save brand.json
```

### 2. Configure Your Gemini Key & Social Credentials (Optional)
Initialize `~/.config/video-factory/credentials.json` (`0600` permissions):
```bash
# Save your Gemini API key for --persona brainstorming:
python3 scripts/video_factory.py --init-credentials --gemini-key "AIzaSyYourGeminiKey..."

# Check credential status across Gemini, YouTube, Instagram, Facebook, and TikTok:
python3 scripts/video_factory.py --check-auth --app-name my_app
```

You can also set `GEMINI_API_KEY` in your environment or `.env` file.

### 3. Render a Video from a Template JSON
Customize [`examples/moment_friday_hangout.json`](examples/moment_friday_hangout.json) (for `screen_walkthrough`) or [`examples/glow_before_after.json`](examples/glow_before_after.json) (for `before_after_slider`) and run:
```bash
python3 scripts/video_factory.py \
  --template examples/moment_friday_hangout.json \
  --screens /path/to/screen1.png /path/to/screen2.png /path/to/screen3.png \
  --app-name "Moment" \
  --accent-color "#FF4E50" \
  --voice en_us_001 \
  --output-dir ./marketing_output
```

### 4. Auto-Plan & Render from a Persona via Gemini
```bash
python3 scripts/video_factory.py \
  --repo /path/to/your/app \
  --persona "25yo remote worker new to NYC who wants curated small-group hangouts" \
  --voice en_us_001 \
  --save-template ./marketing_output/campaign_plan.json \
  --output-dir ./marketing_output
```

### 5. Publish (or Dry-Run) to YouTube Shorts, Instagram Reels, Facebook Reels, & TikTok
```bash
# Dry-run simulation across all 4 platforms:
python3 scripts/distribute.py \
  --video ./marketing_output/moment_friday_night_irl.mp4 \
  --brand moment \
  --platforms youtube,instagram,facebook,tiktok \
  --dry-run

# Live publish to YouTube Shorts & Instagram Reels:
python3 scripts/distribute.py \
  --video ./marketing_output/moment_friday_night_irl.mp4 \
  --brand moment \
  --platforms youtube,instagram
```

---

## 🎨 Customizing Your App's Look & Feel (`CampaignConfig` Schema)

Every campaign JSON template supports a `brand` block so your video matches your app's exact design system:

```json
{
  "name": "my_app_launch_campaign",
  "output_filename": "my_app_launch.mp4",
  "format": "screen_walkthrough",
  "voice": "en_us_001",
  "screenshots": [
    "screenshots/01-home.png",
    "screenshots/02-detail.png",
    "screenshots/03-Action.png"
  ],
  "brand": {
    "app_name": "MyApp",
    "tagline": "Do it faster",
    "header_badge_text": "Live on iOS",
    "primary_accent_rgb": [255, 78, 80],
    "surface_bg_rgb": [18, 18, 22],
    "status_bar_time": "9:41",
    "tracker_pills": [
      "1 · Discover",
      "2 · Connect",
      "3 · Launch"
    ],
    "sheet_badge_label": "why myapp works",
    "sheet_pill_text": "Discover → Connect → Launch",
    "sheet_highlight_pill": "10x Faster"
  }
}
```

See [`SKILL.md`](SKILL.md) for the complete agent workflow instructions and [`examples/`](examples/) for ready-to-run templates.
