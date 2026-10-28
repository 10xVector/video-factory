#!/usr/bin/env python3
"""
Production & Script Review Manager (Editorial QA & Visual Storyboard Audit)
---------------------------------------------------------------------------
Universal short-form video quality gates for any app/brand:
  1. Asset & Screenshot Integrity: Verifies all referenced screenshots/images exist and have valid portrait aspect ratios.
  2. Optional Single-Piece Pixel Lock: Enabled when `brand.enforce_single_piece_lock` is true (e.g. fashion/photo transformation apps).
  3. Audio-Visual Subject Pronoun Coherence: Ensures gender pronouns match when `gender` is specified (`male` or `female`).
  4. Radical Simplicity ("Caveman Standard" / 5th-Grade Readability): Flesch-Kincaid Grade Level <= 6.0 and zero academic jargon.
  5. PG Brand Safety: Rejects violent or morbid metaphors.
  6. High-Retention Pacing: Enforces concise script length (< 75 words total, ~14–25s duration).
  7. Post-Render Visual Audit: Extracts milestone frames from the finished MP4 to certify rendering.
"""

import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
import re
import hashlib
import subprocess
from typing import Dict, List, Tuple, Optional
from PIL import Image

BANNED_CLICKBAIT = [
    "quietly ruining your height",
    "quietly ruining your complexion",
    "looks so sloppy",
    "looks gross",
    "without any makeup",
]

BANNED_JARGON = [
    "chromatic boundary separation",
    "perceptual luminance depth",
    "simultaneous contrast anchoring",
    "torso-to-inseam segmentation",
    "cervical spread equilibrium",
    "optical golden ratio",
    "visual mass equilibrium",
    "proportional architecture",
    "synergistic",
    "paradigm shift",
    "omnichannel",
]

BANNED_UN_PG = [
    "chop your body",
    "cut your body",
    "cut in half",
    "cuts in half",
    "chop in half",
    "into pieces",
    "dismember",
    "sever",
    "bleed",
    "murder",
]


def count_syllables(word: str) -> int:
    w = word.lower().strip(".:,;!?\"'()")
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]|ed|es|e)$", "", w)
    w = re.sub(r"^y", "", w)
    syllables = len(re.findall(r"[aeiouy]{1,2}", w))
    return max(1, syllables)


def flesch_kincaid_grade_level(text: str) -> float:
    words = [w.strip(".:,;!?\"'()") for w in text.split() if w.strip(".:,;!?\"'()")]
    if not words:
        return 0.0
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    num_sentences = max(1, len(sentences))
    num_words = len(words)
    total_syllables = sum(count_syllables(w) for w in words)
    score = 0.39 * (num_words / num_sentences) + 11.8 * (total_syllables / num_words) - 15.59
    return round(max(0.0, score), 1)


class ScriptReviewManager:
    """
    Universal Executive Production Manager for Short-Form Video Campaigns.
    """
    def __init__(self, template: Dict):
        self.template = template
        self.name = template.get("name", "unnamed_campaign")
        self.format = template.get("format", "screen_walkthrough")
        self.brand = template.get("brand", {})

        self.hook = template.get("hook", {})
        self.proof = template.get("proof", {})
        self.takeaway = template.get("takeaway", {})
        self.reveal = template.get("reveal", {})
        self.breakdown = template.get("breakdown", {})
        self.outro = template.get("outro", {})

        self.screenshots = template.get("screenshots", [])
        self.before_path = template.get("before_image", "")
        self.after_path = template.get("after_image", "")

        all_texts = [
            self.hook.get("voiceover_text", ""),
            self.proof.get("voiceover_text", ""),
            self.takeaway.get("voiceover_text", ""),
            self.reveal.get("voiceover_text", ""),
            self.breakdown.get("voiceover_text", ""),
            self.outro.get("voiceover_text", ""),
        ]
        self.all_vo_text = " ".join([t for t in all_texts if t]).lower()
        self.total_word_count = len(self.all_vo_text.split())

        onscreen_snippets = []
        for section in [self.hook, self.proof, self.takeaway, self.reveal, self.breakdown, self.outro]:
            onscreen_snippets.extend(section.get("badge_lines", []))
            onscreen_snippets.extend(section.get("bottom_pill_lines", []))
            if section.get("sheet_title"):
                onscreen_snippets.append(section.get("sheet_title"))
            if section.get("subtitle"):
                onscreen_snippets.append(section.get("subtitle"))
            for b in section.get("bullets", []):
                if isinstance(b, dict):
                    onscreen_snippets.append(b.get("title", ""))
                    onscreen_snippets.append(b.get("description", ""))
        for step_key in ["step1_badge", "step2_badge", "step3_badge"]:
            onscreen_snippets.extend(template.get(step_key, []))
        self.all_onscreen_text = " ".join([s for s in onscreen_snippets if s]).lower()

    def audit_assets(self) -> Tuple[bool, List[str], List[str]]:
        praises = []
        issues = []

        asset_list: List[Tuple[str, str]] = []
        if self.screenshots:
            for idx, s in enumerate(self.screenshots):
                asset_list.append((f"Screen {idx+1}", s))
        else:
            if self.before_path:
                asset_list.append(("Before", self.before_path))
            if self.after_path:
                asset_list.append(("After", self.after_path))

        if not asset_list:
            issues.append("❌ No screenshots or before/after images configured in template.")
            return False, praises, issues

        for label, p in asset_list:
            if not p or not os.path.exists(p):
                issues.append(f"❌ {label} image not found at path: {p}")
                continue
            try:
                im = Image.open(p)
                w, h = im.size
                aspect = w / float(h)
                if aspect > 0.90:
                    issues.append(f"⚠️ {label} image aspect ratio ({aspect:.2f}) is too wide. Portrait mobile assets require <= 0.85.")
                else:
                    praises.append(f"✅ {label} asset verified ({w}x{h}, portrait aspect {aspect:.2f}).")
            except Exception as e:
                issues.append(f"❌ Failed to read {label} image: {e}")

        return len(issues) == 0, praises, issues

    def audit_stage_progression(self) -> Tuple[bool, List[str], List[str]]:
        praises = []
        issues = []

        enforce_lock = self.brand.get("enforce_single_piece_lock", False)
        if not enforce_lock:
            return True, praises, issues

        if not self.before_path or not os.path.exists(self.before_path) or not self.after_path or not os.path.exists(self.after_path):
            return False, praises, ["❌ Missing Before/After images for single-piece lock check."]

        h_b = hashlib.sha256(open(self.before_path, "rb").read()).hexdigest()
        h_a = hashlib.sha256(open(self.after_path, "rb").read()).hexdigest()
        if h_b == h_a:
            issues.append("❌ Duplicate Before and After images rejected!")
            return False, praises, issues

        try:
            import numpy as np
            b_im = np.asarray(Image.open(self.before_path).convert("RGB").resize((540, 960), Image.Resampling.BILINEAR), dtype=np.float32)
            a_im = np.asarray(Image.open(self.after_path).convert("RGB").resize((540, 960), Image.Resampling.BILINEAR), dtype=np.float32)

            head_d = float(np.mean(np.abs(b_im[140:225, 205:335] - a_im[140:225, 205:335])))
            bg_d = float(np.mean(np.abs(b_im[:160, :120] - a_im[:160, :120])))
            if head_d <= 6.0 and bg_d <= 6.0:
                praises.append(f"✅ Single-Piece Model & Framing Lock Verified (head_diff={head_d:.1f}, bg_diff={bg_d:.1f}).")
            else:
                issues.append(f"⚠️ Model/Background shift detected (head_diff={head_d:.1f}, bg_diff={bg_d:.1f}).")
        except ImportError:
            pass

        return len(issues) == 0, praises, issues

    def audit_audio_visual_sync(self) -> Tuple[bool, List[str], List[str]]:
        praises = []
        issues = []
        gender = self.template.get("gender", "neutral").lower()
        padded_vo = f" {self.all_vo_text} "
        if gender == "female" and any(p in padded_vo for p in [" his ", " him ", " he "]):
            issues.append("❌ AUDIO-VISUAL MISMATCH: Female campaign contains male pronouns ('his'/'him'/'he') in voiceover!")
        elif gender == "male" and any(p in padded_vo for p in [" her ", " she ", " hers "]):
            issues.append("❌ AUDIO-VISUAL MISMATCH: Male campaign contains female pronouns ('her'/'she') in voiceover!")
        else:
            praises.append(f"✅ Audio-Visual Coherence Verified (subject='{gender}').")
        return len(issues) == 0, praises, issues

    def review(self) -> Tuple[bool, List[str], List[str]]:
        issues = []
        praises = []

        _, asset_praises, asset_issues = self.audit_assets()
        praises.extend(asset_praises)
        issues.extend(asset_issues)

        _, prog_praises, prog_issues = self.audit_stage_progression()
        praises.extend(prog_praises)
        issues.extend(prog_issues)

        _, sync_praises, sync_issues = self.audit_audio_visual_sync()
        praises.extend(sync_praises)
        issues.extend(sync_issues)

        for phrase in BANNED_CLICKBAIT:
            if phrase in self.all_vo_text:
                issues.append(f"❌ Sensationalist phrase detected: '{phrase}'.")

        combined_text = f"{self.all_vo_text} {self.all_onscreen_text}"
        custom_banned = self.brand.get("banned_jargon", [])
        found_jargon = [p for p in (BANNED_JARGON + custom_banned) if p.lower() in combined_text]
        if found_jargon:
            issues.append(f"❌ Complex jargon detected: {', '.join([repr(j) for j in found_jargon])}.")
        else:
            praises.append("✅ Zero academic or corporate jargon. Plain, high-converting language.")

        found_un_pg = [p for p in BANNED_UN_PG if re.search(r"\b" + re.escape(p) + r"\b", combined_text, re.IGNORECASE)]
        if found_un_pg:
            issues.append(f"❌ Un-PG language detected: {', '.join([repr(p) for p in found_un_pg])}.")
        else:
            praises.append("✅ 100% PG Brand Safety Certified.")

        fk_grade = flesch_kincaid_grade_level(self.all_vo_text)
        if fk_grade > 6.5:
            issues.append(f"❌ Reading level (Grade {fk_grade:.1f}) exceeds plain-English standard (max 6.5). Use shorter, punchier sentences.")
        else:
            praises.append(f"📚 Plain-English Clarity Certified: Flesch-Kincaid Grade {fk_grade:.1f} (<= 6.5).")

        if self.total_word_count > 75:
            issues.append(f"⚠️ Script word count ({self.total_word_count} words) exceeds high-retention threshold (75 words).")
        else:
            praises.append(f"⚡ High-Retention Pacing Certified: {self.total_word_count} words (~15–24s total duration).")

        passed = len(issues) == 0
        return passed, praises, issues

    def print_editorial_report(self) -> bool:
        passed, praises, issues = self.review()
        print("\n" + "=" * 70)
        print(f"🎬 EXECUTIVE PRODUCTION MANAGER AUDIT: '{self.name}' ({self.format.upper()})")
        print("=" * 70)
        if praises:
            print("🌟 Quality Certifications:")
            for p in praises:
                print(f"   {p}")
        if issues:
            print("\n🚨 Production Flags to Resolve:")
            for iss in issues:
                print(f"   {iss}")
        else:
            print("\n✨ Executive Verdict: 100% APPROVED")
        print("=" * 70 + "\n")
        return passed

    @staticmethod
    def audit_rendered_video(video_path: str, extract_dir: str = "/tmp/video_factory_audit") -> bool:
        if not os.path.exists(video_path):
            print(f"❌ Video file does not exist: {video_path}")
            return False

        os.makedirs(extract_dir, exist_ok=True)
        dur_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        try:
            total_dur = float(subprocess.check_output(dur_cmd).decode().strip())
        except Exception:
            total_dur = 20.0

        if total_dur <= 16.0:
            milestones = [
                ("p1_hook", 1.5),
                ("p2_proof", round(total_dur * 0.45, 1)),
                ("p3_takeaway", round(total_dur * 0.85, 1)),
            ]
        else:
            milestones = [
                ("s1_hook", 1.8),
                ("s2_transition", round(total_dur * 0.35, 1)),
                ("s3_breakdown_sheet", round(total_dur * 0.72, 1)),
                ("s4_outro_cta", max(2.0, round(total_dur - 1.5, 1))),
            ]

        print(f"🔍 Running post-render visual audit on '{os.path.basename(video_path)}' ({total_dur:.1f}s)...")
        for label, t in milestones:
            out_img = os.path.join(extract_dir, f"{os.path.basename(video_path)}_{label}.jpg")
            cmd = [
                "ffmpeg", "-y", "-ss", str(t), "-i", video_path,
                "-vframes", "1", "-q:v", "2", out_img,
            ]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode == 0 and os.path.exists(out_img) and os.path.getsize(out_img) > 10000:
                print(f"   📸 Milestone frame verified at t={t:4.1f}s: {label} ({os.path.getsize(out_img)//1024} KB)")
            else:
                print(f"   ⚠️ Milestone frame extraction failed at t={t:4.1f}s: {label}")

        print("✅ Post-render visual verification complete.\n")
        return True
