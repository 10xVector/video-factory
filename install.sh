#!/usr/bin/env bash
set -euo pipefail

SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🎬 Installing 'video-factory' skill..."

for TARGET_DIR in "$HOME/.claude/skills/video-factory" "$HOME/.agents/skills/video-factory" "$HOME/.gemini/config/skills/video-factory"; do
  mkdir -p "$(dirname "$TARGET_DIR")"
  rm -rf "$TARGET_DIR"
  cp -R "$SKILL_SRC" "$TARGET_DIR"
  rm -rf "$TARGET_DIR/.git"
  echo "  ✅ Installed to: $TARGET_DIR"
done

echo ""
echo "✨ Done! You can now ask Claude Code, Antigravity, Cursor, or Codex:"
echo "   \"Use the video-factory skill to generate a marketing video for this repo.\""
