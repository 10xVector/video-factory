import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class BrandThemeConfig:
    app_name: str = "Moment"
    tagline: str = "Make yours"
    header_badge_text: str = "Live Nearby"
    primary_accent_rgb: List[int] = field(default_factory=lambda: [255, 78, 80])   # #FF4E50
    surface_bg_rgb: List[int] = field(default_factory=lambda: [18, 18, 22])        # #121216
    status_bar_time: str = "9:41"
    font_path: str = ""
    tracker_pills: List[str] = field(default_factory=lambda: ["1 · Discover", "2 · Match", "3 · Go Live"])
    sheet_badge_label: str = "why it works"
    sheet_pill_text: str = "Discover → Match → Meet IRL"
    sheet_highlight_pill: str = "Curated IRL"
    enforce_single_piece_lock: bool = False


@dataclass
class HookConfig:
    badge_lines: List[str] = field(default_factory=list)
    voiceover_text: str = ""
    left_pill: str = ""
    right_pill: str = ""
    banner_text: str = ""


@dataclass
class RevealConfig:
    badge_lines: List[str] = field(default_factory=list)
    voiceover_text: str = ""
    sweep_direction: str = "right_to_left"
    hold_start_seconds: float = 0.8
    sweep_duration_seconds: float = 5.5


@dataclass
class BreakdownBullet:
    title: str = ""
    description: str = ""
    badge_text: str = "Key Feature"


@dataclass
class BreakdownConfig:
    badge_lines: List[str] = field(default_factory=list)
    voiceover_text: str = ""
    sheet_title: str = "how it works"
    subtitle_text: str = "Real people · Curated small-group experiences"
    metrics: List[Dict[str, str]] = field(default_factory=list)
    feature_pills: List[Dict[str, str]] = field(default_factory=list)
    bullets: List[BreakdownBullet] = field(default_factory=list)
    button_text: str = "Join Your First Moment Free"


@dataclass
class OutroConfig:
    app_title: str = "Moment — Make yours"
    subtitle: str = "Curated small-group hangouts & real-world connections"
    cta_button_text: str = "Download Free on iOS"
    bottom_pill_lines: List[str] = field(default_factory=lambda: ["Free on the App Store", "Link in bio"])
    voiceover_text: str = "Find your next hangout on Moment."


@dataclass
class ProofConfig:
    badge_lines: List[str] = field(default_factory=list)
    voiceover_text: str = ""
    annotation_type: str = "none"  # "hemline_delta", "ankle_folds", "undertone_split", "callout_box", "none"
    annotation_label: str = ""
    bottom_pill: str = ""


@dataclass
class TakeawayConfig:
    badge_lines: List[str] = field(default_factory=list)
    voiceover_text: str = ""
    bottom_pill: str = ""
    sub_credit: str = ""


@dataclass
class CampaignConfig:
    name: str
    output_filename: str
    # Supported formats:
    # - "screen_walkthrough": Cycles through 2-4 app screenshots in a native iOS frame + feature breakdown card
    # - "before_after_slider" (alias "app_template"): Before/After comparison slider wipe + coaching breakdown card
    # - "side_by_side_proof" (alias "native_loop"): Split side-by-side comparison card
    format: str = "screen_walkthrough"
    voice: str = "en_us_001"
    pitch_shift: float = 0.0
    fps: int = 30
    gender: str = "neutral"

    # Visual assets (supports both multi-screen walkthroughs and before/after pairs)
    screenshots: List[str] = field(default_factory=list)
    before_image: str = ""
    after_image: str = ""
    stage1_image: str = ""
    stage2_image: str = ""

    # Step titles & badges for Scene 2 / Scene 3 transitions
    step1_title: str = "Step 1 · Discover Nearby"
    step2_title: str = "Step 2 · Host Approves"
    step3_title: str = "Step 3 · Group Chat & Meet"
    step1_badge: List[str] = field(default_factory=list)
    step2_badge: List[str] = field(default_factory=list)
    step3_badge: List[str] = field(default_factory=list)

    # Brand look & feel configuration
    brand: BrandThemeConfig = field(default_factory=BrandThemeConfig)

    # Narrative scenes
    hook: HookConfig = field(default_factory=HookConfig)
    proof: ProofConfig = field(default_factory=ProofConfig)
    takeaway: TakeawayConfig = field(default_factory=TakeawayConfig)
    reveal: RevealConfig = field(default_factory=RevealConfig)
    breakdown: BreakdownConfig = field(default_factory=BreakdownConfig)
    outro: OutroConfig = field(default_factory=OutroConfig)

    def to_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def from_json(cls, path: str, brand_override: Optional[Dict[str, Any]] = None) -> "CampaignConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Merge brand config if provided in template or override
        brand_dict = dict(data.get("brand", {}))
        if brand_override:
            if "app_name" in brand_override:
                brand_dict.setdefault("app_name", brand_override["app_name"])
            if "tagline" in brand_override:
                brand_dict.setdefault("tagline", brand_override["tagline"])
            theme = brand_override.get("theme", {})
            for k in ["primary_accent_rgb", "surface_bg_rgb", "header_badge_text", "status_bar_time", "font_path"]:
                if k in theme and k not in brand_dict:
                    brand_dict[k] = theme[k]

        # Detect legacy Glow templates automatically if brand block is absent
        if not brand_dict and ("glow" in str(data.get("outro", {}).get("app_title", "")).lower() or data.get("format") == "app_template"):
            brand_dict = {
                "app_name": "Glow",
                "tagline": "Style",
                "header_badge_text": "12 Axes",
                "primary_accent_rgb": [244, 63, 94],
                "surface_bg_rgb": [12, 12, 16],
                "tracker_pills": ["Base Look · 7.8", "1-Piece Swap", "3+ Axes · 9.5"],
                "sheet_badge_label": "glow rating",
                "sheet_pill_text": "Base 7.8 → 1-Piece Swap → Glow 9.5",
                "sheet_highlight_pill": "+1.7 Glow",
                "enforce_single_piece_lock": True,
            }

        brand = BrandThemeConfig(**{k: v for k, v in brand_dict.items() if k in BrandThemeConfig.__dataclass_fields__})
        hook = HookConfig(**{k: v for k, v in data.get("hook", {}).items() if k in HookConfig.__dataclass_fields__})

        if "proof" in data:
            proof = ProofConfig(**{k: v for k, v in data["proof"].items() if k in ProofConfig.__dataclass_fields__})
        else:
            rev = data.get("reveal", {})
            proof = ProofConfig(
                badge_lines=rev.get("badge_lines", []),
                voiceover_text=rev.get("voiceover_text", ""),
                annotation_type=data.get("annotation_type", "none"),
                annotation_label=data.get("annotation_label", ""),
            )

        if "takeaway" in data:
            takeaway = TakeawayConfig(**{k: v for k, v in data["takeaway"].items() if k in TakeawayConfig.__dataclass_fields__})
        else:
            out = data.get("outro", {})
            takeaway = TakeawayConfig(
                badge_lines=out.get("bottom_pill_lines", []),
                voiceover_text=out.get("voiceover_text", ""),
                bottom_pill=out.get("subtitle", ""),
            )

        reveal = RevealConfig(**{k: v for k, v in data.get("reveal", {}).items() if k in RevealConfig.__dataclass_fields__})

        bd_dict = dict(data.get("breakdown", {}))
        raw_bullets = bd_dict.pop("bullets", [])
        bullets = [
            BreakdownBullet(**{k: v for k, v in b.items() if k in BreakdownBullet.__dataclass_fields__})
            if isinstance(b, dict) else b
            for b in raw_bullets
        ]
        bd_clean = {k: v for k, v in bd_dict.items() if k in BreakdownConfig.__dataclass_fields__}
        breakdown = BreakdownConfig(bullets=bullets, **bd_clean)

        outro_dict = dict(data.get("outro", {}))
        if brand_override and "outro" in brand_override and not data.get("outro"):
            outro_dict.update(brand_override["outro"])
        outro = OutroConfig(**{k: v for k, v in outro_dict.items() if k in OutroConfig.__dataclass_fields__})

        screenshots = data.get("screenshots", [])
        before_img = data.get("before_image", "")
        after_img = data.get("after_image", "")
        if not before_img and screenshots:
            before_img = screenshots[0]
        if not after_img and len(screenshots) > 1:
            after_img = screenshots[1]
        elif not after_img and before_img:
            after_img = before_img

        fmt = data.get("format", "screen_walkthrough" if screenshots else "before_after_slider")

        return cls(
            name=data["name"],
            output_filename=data.get("output_filename", f"{data['name']}.mp4"),
            format=fmt,
            voice=data.get("voice", "en_us_001"),
            pitch_shift=data.get("pitch_shift", 0.0),
            fps=data.get("fps", 30),
            gender=data.get("gender", "neutral"),
            screenshots=screenshots,
            before_image=before_img,
            after_image=after_img,
            stage1_image=data.get("stage1_image", ""),
            stage2_image=data.get("stage2_image", ""),
            step1_title=data.get("step1_title", "Step 1 · Discover"),
            step2_title=data.get("step2_title", "Step 2 · Match & Connect"),
            step3_title=data.get("step3_title", "Step 3 · Meet IRL"),
            step1_badge=data.get("step1_badge", []),
            step2_badge=data.get("step2_badge", []),
            step3_badge=data.get("step3_badge", []),
            brand=brand,
            hook=hook,
            proof=proof,
            takeaway=takeaway,
            reveal=reveal,
            breakdown=breakdown,
            outro=outro,
        )
