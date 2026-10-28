import os
if os.path.exists("/etc/ssl/cert.pem"):
    os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/cert.pem")
import math
import subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from typing import Dict, List, Tuple, Optional
from .config import CampaignConfig

WIDTH = 1080
HEIGHT = 1920

DEFAULT_FONT_PATHS = [
    "/System/Library/Fonts/SFNSRounded.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def resolve_font_path(custom_path: str = "") -> str:
    if custom_path and os.path.exists(custom_path):
        return custom_path
    for p in DEFAULT_FONT_PATHS:
        if os.path.exists(p):
            return p
    return ""


def get_font(size: int, custom_path: str = ""):
    fp = resolve_font_path(custom_path)
    if fp:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            pass
    return ImageFont.load_default()


font_h1 = get_font(52)
font_h2 = get_font(40)
font_body = get_font(32)
font_small = get_font(24)


def _rgba(rgb_list: List[int], alpha: int = 255) -> Tuple[int, int, int, int]:
    if len(rgb_list) >= 3:
        return (int(rgb_list[0]), int(rgb_list[1]), int(rgb_list[2]), alpha)
    return (255, 78, 80, alpha)


def cover_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    ratio = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * ratio)
    new_h = int(src_h * ratio)
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def draw_sparkle(d: ImageDraw.Draw, cx: int, cy: int, r_outer: int = 15, r_inner: int = 6, fill=(255, 78, 80, 255)):
    points = []
    for i in range(8):
        angle = i * math.pi / 4.0
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.sin(angle), cy - r * math.cos(angle)))
    d.polygon(points, fill=fill)


def draw_pill_badge(
    base_img: Image.Image,
    lines: List[str],
    y_top: int,
    font: ImageFont.ImageFont = font_h2,
    pill_bg=(14, 14, 18, 240),
    text_color=(255, 255, 255),
) -> Image.Image:
    if not lines:
        return base_img

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    line_boxes = [d.textbbox((0, 0), l, font=font) for l in lines]
    line_widths = [b[2] - b[0] for b in line_boxes]
    line_heights = [b[3] - b[1] for b in line_boxes]

    max_w = max(line_widths)
    total_h = sum(line_heights) + (len(lines) - 1) * 16

    pad_x = 48
    pad_y = 22 if len(lines) == 1 else 26
    box_w = max_w + pad_x * 2
    box_h = total_h + pad_y * 2
    box_x = (WIDTH - box_w) // 2
    box_y = y_top

    d.rounded_rectangle(
        (box_x, box_y, box_x + box_w, box_y + box_h),
        radius=36,
        fill=pill_bg,
        outline=(255, 255, 255, 70),
        width=2,
    )

    cur_y = box_y + pad_y
    for i, line in enumerate(lines):
        w = line_widths[i]
        lx = (WIDTH - w) // 2
        d.text((lx, cur_y), line, font=font, fill=text_color)
        cur_y += line_heights[i] + 16

    return Image.alpha_composite(base_img, overlay)


def draw_brand_app_header(
    base_img: Image.Image,
    app_name: str = "Moment",
    badge_text: str = "Live Nearby",
    status_time: str = "9:41",
    show_badge: bool = True,
) -> Image.Image:
    """Renders the iOS navigation header with customizable app title and right status pill."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # Status bar
    d.text((90, 80), status_time, font=font_body, fill=(255, 255, 255, 220))
    d.rounded_rectangle((WIDTH - 150, 86, WIDTH - 100, 110), radius=6, outline=(255, 255, 255, 200), width=2)
    d.rounded_rectangle((WIDTH - 146, 90, WIDTH - 108, 106), radius=3, fill=(255, 255, 255, 200))
    # Centered App Logo / Title
    title_font = get_font(56)
    tb_title = d.textbbox((0, 0), app_name, font=title_font)
    tw_title = tb_title[2] - tb_title[0]
    d.text(((WIDTH - tw_title) // 2, 160), app_name, font=title_font, fill=(255, 255, 255, 255))
    if show_badge and badge_text:
        tb = d.textbbox((0, 0), badge_text, font=font_small)
        tw = tb[2] - tb[0]
        pill_w = max(156, tw + 44)
        pill_x2 = WIDTH - 64
        pill_x1 = pill_x2 - pill_w
        pill_y1, pill_y2 = 168, 218
        d.rounded_rectangle(
            (pill_x1, pill_y1, pill_x2, pill_y2),
            radius=25,
            fill=(255, 255, 255, 30),
            outline=(255, 255, 255, 65),
            width=1,
        )
        d.text((pill_x1 + (pill_w - tw) // 2, 178), badge_text, font=font_small, fill=(255, 255, 255, 240))
    return Image.alpha_composite(base_img, overlay)


# ==============================================================================
# 1. Screen Walkthrough Renderer (For Mobile/Web Apps: Moment, Listen, SaaS, etc.)
# ==============================================================================

class ScreenWalkthroughRenderer:
    """
    Renders 1080x1920 vertical videos showcasing a multi-screen app journey
    (e.g., Screen 1: Hook/Discover -> Screen 2: Detail/Match -> Screen 3: Feature Breakdown Sheet -> Screen 4: Brand Outro).
    Uses the target app's real screenshots, brand colors, and typography.
    """
    def __init__(self, config: CampaignConfig, timing: Dict):
        self.config = config
        self.timing = timing
        self.fps = config.fps
        self.total_frames = int(timing["total_seconds"] * self.fps)
        self.scenes = timing["scenes"]
        self.accent_rgba = _rgba(config.brand.primary_accent_rgb, 255)
        self.accent_soft = _rgba(config.brand.primary_accent_rgb, 235)
        self.surface_rgba = _rgba(config.brand.surface_bg_rgb, 195)

        # Resolve list of 1..3 screenshots
        raw_paths = [p for p in config.screenshots if p and os.path.exists(p)]
        if not raw_paths:
            for fallback in [config.before_image, config.after_image, config.stage1_image]:
                if fallback and os.path.exists(fallback):
                    raw_paths.append(fallback)
        if not raw_paths:
            raise ValueError("No valid screenshots or images provided for ScreenWalkthroughRenderer.")

        while len(raw_paths) < 3:
            raw_paths.append(raw_paths[-1])

        self.screens_raw = [Image.open(p).convert("RGBA") for p in raw_paths[:3]]

        src_w, src_h = self.screens_raw[0].size
        self.aspect = min(0.70, max(0.46, src_w / float(src_h)))

        self.CARD_H = 1230
        self.CARD_W = int(self.CARD_H * self.aspect)
        self.CARD_X = (WIDTH - self.CARD_W) // 2
        self.CARD_Y = 300

        self.screen_cards = [
            cover_resize(im, self.CARD_W, self.CARD_H) for im in self.screens_raw
        ]

        # Ambient blurred backgrounds per screen
        self.bgs = []
        dark_ov = Image.new("RGBA", (WIDTH, HEIGHT), self.surface_rgba)
        for im in self.screens_raw:
            bg_blur = cover_resize(im, WIDTH, HEIGHT).filter(ImageFilter.GaussianBlur(42))
            self.bgs.append(Image.alpha_composite(bg_blur, dark_ov))

        self.card_mask = Image.new("L", (self.CARD_W, self.CARD_H), 0)
        ImageDraw.Draw(self.card_mask).rounded_rectangle((0, 0, self.CARD_W, self.CARD_H), radius=44, fill=255)

        self.scene3_base = self._build_scene3_feature_sheet()

    def _draw_progression_bar(self, frame: Image.Image, active_step: int) -> Image.Image:
        ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        pills = self.config.brand.tracker_pills or ["1 · Discover", "2 · Match", "3 · Meet IRL"]
        while len(pills) < 3:
            pills.append(f"Step {len(pills)+1}")
        labels = [(pills[0], 0), (pills[1], 1), (pills[2], 2)]

        pill_w = 284
        pill_h = 48
        gap = 20
        total_w = len(labels) * pill_w + (len(labels) - 1) * gap
        start_x = (WIDTH - total_w) // 2
        y = 230
        font_p = get_font(23)

        for idx, (text, step_num) in enumerate(labels):
            px = start_x + idx * (pill_w + gap)
            is_active = (step_num == active_step)
            is_done = (step_num < active_step)
            if is_active:
                bg_col = self.accent_rgba
                out_col = (255, 255, 255, 225)
                txt_col = (255, 255, 255, 255)
            elif is_done:
                bg_col = (45, 45, 58, 225)
                out_col = _rgba(self.config.brand.primary_accent_rgb, 150)
                txt_col = (245, 245, 250, 235)
            else:
                bg_col = (22, 22, 30, 200)
                out_col = (255, 255, 255, 55)
                txt_col = (165, 165, 178, 215)
            d.rounded_rectangle((px, y, px + pill_w, y + pill_h), radius=24, fill=bg_col, outline=out_col, width=2)
            bbox = d.textbbox((0, 0), text, font=font_p)
            tw = bbox[2] - bbox[0]
            d.text((px + (pill_w - tw) // 2, y + 11), text, font=font_p, fill=txt_col)
        return Image.alpha_composite(frame, ov)

    def _decorate_phone_card(
        self,
        card_img: Image.Image,
        top_pill: str,
        bottom_banner: str = "",
    ) -> Image.Image:
        cw, ch = card_img.size
        ov = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        # Subtle glass phone bezel border
        d.rounded_rectangle((2, 2, cw - 2, ch - 2), radius=44, outline=(255, 255, 255, 75), width=3)

        if top_pill:
            f_pill = get_font(22)
            rb_box = d.textbbox((0, 0), top_pill, font=f_pill)
            rw = (rb_box[2] - rb_box[0]) + 46
            d.rounded_rectangle((cw - 20 - rw, 20, cw - 20, 66), radius=23, fill=self.accent_soft)
            d.text((cw - 20 - rw + 18, 30), top_pill, font=f_pill, fill=(255, 255, 255, 255))
            draw_sparkle(d, cw - 36, 43, r_outer=8, r_inner=3, fill=(253, 224, 71, 255))

        if bottom_banner:
            f_dim = get_font(23)
            clean_b = bottom_banner.replace("✨", "").strip()
            db_box = d.textbbox((0, 0), clean_b, font=f_dim)
            dw = (db_box[2] - db_box[0]) + 48
            dx = (cw - dw) // 2
            dy = ch - 78
            d.rounded_rectangle(
                (dx, dy, dx + dw, dy + 54),
                radius=27,
                fill=(14, 14, 20, 235),
                outline=self.accent_soft,
                width=2,
            )
            d.text((dx + 24, dy + 13), clean_b, font=f_dim, fill=(255, 255, 255, 255))

        return Image.alpha_composite(card_img, ov)

    def _build_scene3_feature_sheet(self) -> Image.Image:
        bg = Image.new("RGBA", (WIDTH, HEIGHT), (248, 248, 250, 255))
        d = ImageDraw.Draw(bg)

        # Status Bar
        d.text((90, 60), self.config.brand.status_bar_time, font=font_body, fill=(30, 30, 30, 255))
        d.rounded_rectangle((WIDTH - 150, 66, WIDTH - 100, 90), radius=6, outline=(30, 30, 30, 200), width=2)
        d.rounded_rectangle((WIDTH - 146, 70, WIDTH - 108, 86), radius=3, fill=(30, 30, 30, 200))

        # Top dual-screen showcase (Screen 1 & Screen 2 side by side)
        card_h = 740
        card_w = int(card_h * self.aspect)
        gap = 28
        total_top_w = card_w * 2 + gap
        start_x = (WIDTH - total_top_w) // 2
        card_y = 225

        cmask = Image.new("L", (card_w, card_h), 0)
        ImageDraw.Draw(cmask).rounded_rectangle((0, 0, card_w, card_h), radius=30, fill=255)

        for idx in range(2):
            c_im = cover_resize(self.screens_raw[min(idx, len(self.screens_raw) - 1)], card_w, card_h)
            cx = start_x + idx * (card_w + gap)
            bg.paste(c_im, (cx, card_y), cmask)
            d.rounded_rectangle((cx, card_y, cx + card_w, card_y + card_h), radius=30, outline=(215, 215, 225, 255), width=2)

        sub_text = self.config.breakdown.subtitle_text or f"{self.config.brand.app_name} · {self.config.brand.tagline}"
        sbbox = d.textbbox((0, 0), sub_text, font=get_font(25))
        sw = sbbox[2] - sbbox[0]
        d.text(((WIDTH - sw) // 2, card_y + card_h + 18), sub_text, font=get_font(25), fill=(100, 100, 112, 255))

        # Feature Breakdown Card
        box_w = 960
        box_h = 700
        box_x = (WIDTH - box_w) // 2
        box_y = card_y + card_h + 64

        d.rounded_rectangle(
            (box_x, box_y, box_x + box_w, box_y + box_h),
            radius=36,
            fill=(242, 242, 246, 255),
            outline=(228, 228, 234, 255),
            width=2,
        )

        # Row 1: Brand Sparkle + Sheet Badge Label + Highlight Pill
        draw_sparkle(d, box_x + 44, box_y + 42, r_outer=14, r_inner=5, fill=self.accent_rgba)
        badge_lbl = self.config.brand.sheet_badge_label or self.config.breakdown.sheet_title or "why it works"
        f_badge_lbl = get_font(28)
        d.text((box_x + 70, box_y + 25), badge_lbl, font=f_badge_lbl, fill=self.accent_rgba)
        lbl_box = d.textbbox((0, 0), badge_lbl, font=f_badge_lbl)
        lbl_w = lbl_box[2] - lbl_box[0]

        hi_pill = self.config.brand.sheet_highlight_pill or "Live App"
        hi_x1 = box_x + box_w - 216
        d.rounded_rectangle((hi_x1, box_y + 18, box_x + box_w - 32, box_y + 66), radius=24, fill=self.accent_rgba)
        hb_box = d.textbbox((0, 0), hi_pill, font=get_font(22))
        hbw = hb_box[2] - hb_box[0]
        d.text((hi_x1 + (184 - hbw) // 2, box_y + 29), hi_pill, font=get_font(22), fill=(255, 255, 255, 255))

        mid_pill = self.config.brand.sheet_pill_text or "Discover → Match → Meet IRL"
        f_mid = get_font(20)
        mp_box = d.textbbox((0, 0), mid_pill, font=f_mid)
        mp_w = (mp_box[2] - mp_box[0]) + 40
        mp_x1 = max(box_x + 88 + lbl_w, (box_x + 70 + lbl_w + hi_x1 - mp_w) // 2)
        mp_x2 = min(hi_x1 - 16, mp_x1 + mp_w)
        if mp_x2 - mp_x1 > 120:
            d.rounded_rectangle((mp_x1, box_y + 20, mp_x2, box_y + 64), radius=22, fill=(255, 255, 255, 255))
            d.text((mp_x1 + 20, box_y + 30), mid_pill, font=f_mid, fill=(40, 40, 48, 255))

        # Summary Metrics Card
        sc_y = box_y + 84
        d.rounded_rectangle((box_x + 32, sc_y, box_x + box_w - 32, sc_y + 128), radius=24, fill=(255, 255, 255, 255))
        metrics = self.config.breakdown.metrics or [
            {"label": "STEP 1", "value": "Discover"},
            {"label": "STEP 2", "value": "Apply"},
            {"label": "STEP 3", "value": "Group Chat"},
            {"label": "RESULT", "value": "Real Plans"},
        ]
        col_w = (box_w - 96) // max(1, len(metrics[:4]))
        for idx, m in enumerate(metrics[:4]):
            mx = box_x + 56 + idx * col_w
            is_last = (idx == len(metrics[:4]) - 1)
            lbl_col = self.accent_rgba if is_last else (130, 130, 140, 255)
            val_col = self.accent_rgba if is_last else (25, 25, 32, 255)
            d.text((mx, sc_y + 18), m.get("label", "").upper(), font=get_font(18), fill=lbl_col)
            d.text((mx, sc_y + 46), m.get("value", ""), font=get_font(34), fill=val_col)

        # Feature Pills Grid (4 or 6 pills)
        grid_y = sc_y + 148
        d.text((box_x + 36, grid_y), f"{self.config.brand.app_name} experience highlights", font=get_font(22), fill=(100, 100, 112, 255))
        f_pills = self.config.breakdown.feature_pills or [
            {"name": "Curated Hosts", "tag": "Verified"},
            {"name": "Small Groups", "tag": "4–8 People"},
            {"name": "Vibe Matching", "tag": "Instant"},
            {"name": "Group Chat", "tag": "Built-In"},
        ]
        pill_w = (box_w - 84) // 2
        pill_h = 48
        start_py = grid_y + 34
        for idx, fp in enumerate(f_pills[:6]):
            col = idx % 2
            row = idx // 2
            px = box_x + 32 + col * (pill_w + 20)
            py = start_py + row * (pill_h + 10)
            d.rounded_rectangle((px, py, px + pill_w, py + pill_h), radius=14, fill=(255, 255, 255, 255))
            d.text((px + 20, py + 11), fp.get("name", ""), font=get_font(22), fill=(25, 25, 32, 255))
            tag_str = fp.get("tag", "")
            tb = d.textbbox((0, 0), tag_str, font=get_font(21))
            tw = tb[2] - tb[0]
            d.text((px + pill_w - tw - 20, py + 11), tag_str, font=get_font(21), fill=self.accent_rgba)

        # Bullets (2 punchy takeaways)
        rows_used = math.ceil(len(f_pills[:6]) / 2.0)
        cur_by = start_py + rows_used * (pill_h + 10) + 18
        for b in self.config.breakdown.bullets[:2]:
            d.text((box_x + 36, cur_by), b.title, font=get_font(26), fill=(20, 20, 25, 255))
            b_tag = getattr(b, "badge_text", "") or "Included"
            d.rounded_rectangle((box_x + box_w - 170, cur_by - 2, box_x + box_w - 36, cur_by + 32), radius=16, fill=(255, 235, 238, 255))
            bt_box = d.textbbox((0, 0), b_tag, font=get_font(19))
            btw = bt_box[2] - bt_box[0]
            d.text((box_x + box_w - 170 + (134 - btw) // 2, cur_by + 4), b_tag, font=get_font(19), fill=self.accent_rgba)
            d.text((box_x + 36, cur_by + 34), b.description, font=get_font(22), fill=(95, 95, 108, 255))
            cur_by += 78

        # Bottom CTA Button
        btn_w = 960
        btn_h = 82
        btn_x = (WIDTH - btn_w) // 2
        btn_y = box_y + box_h + 22
        d.rounded_rectangle((btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), radius=41, fill=self.accent_rgba)
        btn_title = self.config.breakdown.button_text or f"Try {self.config.brand.app_name} Free"
        bbox = d.textbbox((0, 0), btn_title, font=get_font(30))
        tw = bbox[2] - bbox[0]
        d.text(((WIDTH - tw) // 2, btn_y + 23), btn_title, font=get_font(30), fill=(255, 255, 255, 255))

        return bg

    def _render_screen_transition(
        self,
        from_card: Image.Image,
        to_card: Image.Image,
        bg_img: Image.Image,
        progress: float,
        active_step: int,
        top_pill: str,
        bottom_banner: str,
        bottom_badge: List[str],
    ) -> Image.Image:
        # Smooth slide/wipe transition across the phone card
        split_x = int(self.CARD_W * (1.0 - progress))
        card_composite = to_card.copy()
        if split_x > 4:
            left_crop = from_card.crop((0, 0, split_x, self.CARD_H))
            card_composite.paste(left_crop, (0, 0))

        card_composite = self._decorate_phone_card(card_composite, top_pill=top_pill, bottom_banner=bottom_banner)

        frame = bg_img.copy()
        frame.paste(card_composite, (self.CARD_X, self.CARD_Y), self.card_mask)
        frame = draw_brand_app_header(
            frame,
            app_name=self.config.brand.app_name,
            badge_text=self.config.brand.header_badge_text,
            status_time=self.config.brand.status_bar_time,
        )
        frame = self._draw_progression_bar(frame, active_step=active_step)

        if 4 < split_x < self.CARD_W - 4:
            div_x = self.CARD_X + split_x
            d = ImageDraw.Draw(frame)
            d.line((div_x, self.CARD_Y, div_x, self.CARD_Y + self.CARD_H), fill=(255, 255, 255, 240), width=4)
            knob_r = 30
            knob_y = self.CARD_Y + self.CARD_H // 2
            d.ellipse(
                (div_x - knob_r, knob_y - knob_r, div_x + knob_r, knob_y + knob_r),
                fill=self.accent_rgba,
                outline=(255, 255, 255, 230),
                width=2,
            )
            d.text((div_x - 16, knob_y - 15), "< >", font=font_small, fill=(255, 255, 255, 255))

        clean_badge = [b.replace("✨", "").strip() for b in bottom_badge]
        frame = draw_pill_badge(frame, clean_badge, y_top=1575, font=font_h2)
        return frame

    def render_frame(self, f_idx: int) -> Image.Image:
        time_s = f_idx / self.fps
        s1 = self.scenes[0]
        s2 = self.scenes[1]
        s3 = self.scenes[2]

        # Scene 1: Hook on Screen 1
        if time_s < s1["end"]:
            frame = self.bgs[0].copy()
            c1 = self._decorate_phone_card(
                self.screen_cards[0].copy(),
                top_pill=self.config.hook.right_pill or self.config.brand.header_badge_text,
                bottom_banner=self.config.hook.banner_text or self.config.step1_title,
            )
            frame.paste(c1, (self.CARD_X, self.CARD_Y), self.card_mask)
            frame = draw_brand_app_header(
                frame,
                app_name=self.config.brand.app_name,
                badge_text=self.config.brand.header_badge_text,
                status_time=self.config.brand.status_bar_time,
            )
            frame = self._draw_progression_bar(frame, active_step=0)
            frame = draw_pill_badge(frame, self.config.hook.badge_lines, y_top=1575, font=font_h2)
            return frame

        # Scene 2: Wipe from Screen 1 -> Screen 2, then hold Screen 2
        elif time_s < s2["end"]:
            s2_dur = max(0.1, s2["end"] - s2["start"])
            s2_prog = (time_s - s2["start"]) / s2_dur
            t = min(1.0, max(0.0, s2_prog / 0.36))
            smooth = t * t * (3.0 - 2.0 * t)
            badge = self.config.step1_badge if (s2_prog < 0.52 and self.config.step1_badge) else (self.config.step2_badge or self.config.reveal.badge_lines)
            banner = self.config.step1_title if s2_prog < 0.52 else self.config.step2_title
            return self._render_screen_transition(
                from_card=self.screen_cards[0],
                to_card=self.screen_cards[1],
                bg_img=self.bgs[1],
                progress=smooth,
                active_step=1,
                top_pill=self.config.brand.app_name,
                bottom_banner=banner,
                bottom_badge=badge,
            )

        # Scene 3: Screen 3 Hold (First 38%) -> Feature Breakdown Sheet (Remaining 62%)
        elif time_s < s3["end"]:
            s3_dur = max(0.1, s3["end"] - s3["start"])
            s3_prog = (time_s - s3["start"]) / s3_dur
            if s3_prog < 0.38:
                badge3 = self.config.step3_badge if self.config.step3_badge else self.config.breakdown.badge_lines
                return self._render_screen_transition(
                    from_card=self.screen_cards[1],
                    to_card=self.screen_cards[2],
                    bg_img=self.bgs[2],
                    progress=1.0,
                    active_step=2,
                    top_pill=self.config.brand.sheet_highlight_pill,
                    bottom_banner=self.config.step3_title,
                    bottom_badge=badge3,
                )
            else:
                frame = self.scene3_base.copy()
                badge_font = get_font(34) if len(self.config.breakdown.badge_lines) == 1 else get_font(30)
                frame = draw_pill_badge(
                    frame,
                    self.config.breakdown.badge_lines,
                    y_top=68,
                    font=badge_font,
                    pill_bg=(14, 14, 18, 245),
                )
                return frame

        # Scene 4: Outro & Call to Action
        else:
            frame = self.bgs[-1].copy()
            ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 145))
            frame = Image.alpha_composite(frame, ov)

            small_h = 860
            small_w = int(small_h * self.aspect)
            small_x = (WIDTH - small_w) // 2
            small_y = 250
            small_card = cover_resize(self.screens_raw[-1], small_w, small_h)
            smask = Image.new("L", (small_w, small_h), 0)
            ImageDraw.Draw(smask).rounded_rectangle((0, 0, small_w, small_h), radius=36, fill=255)
            frame.paste(small_card, (small_x, small_y), smask)

            d = ImageDraw.Draw(frame)
            app_t = self.config.outro.app_title
            bbox1 = d.textbbox((0, 0), app_t, font=get_font(48))
            d.text(((WIDTH - (bbox1[2] - bbox1[0])) // 2, 1160), app_t, font=get_font(48), fill=(255, 255, 255, 255))

            sub_t = self.config.outro.subtitle
            bbox2 = d.textbbox((0, 0), sub_t, font=font_body)
            d.text(((WIDTH - (bbox2[2] - bbox2[0])) // 2, 1230), sub_t, font=font_body, fill=(220, 220, 220, 240))

            btn_w = 780
            btn_h = 96
            btn_x = (WIDTH - btn_w) // 2
            btn_y = 1330
            d.rounded_rectangle((btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), radius=48, fill=self.accent_rgba)
            cta_t = self.config.outro.cta_button_text
            bbox3 = d.textbbox((0, 0), cta_t, font=get_font(38))
            d.text(((WIDTH - (bbox3[2] - bbox3[0])) // 2, btn_y + 26), cta_t, font=get_font(38), fill=(255, 255, 255, 255))

            frame = draw_pill_badge(frame, self.config.outro.bottom_pill_lines, y_top=1540, font=font_h2)
            return frame

    def render_video(self, temp_mp4_path: str):
        print(f"🎬 [Screen Walkthrough Renderer — {self.config.brand.app_name}] Rendering {self.total_frames} frames @ {self.fps} fps ({self.total_frames/self.fps:.1f}s)...")
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-pix_fmt", "rgba",
            "-r", str(self.fps),
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "18",
            temp_mp4_path,
        ]
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
        for i in range(self.total_frames):
            frame = self.render_frame(i)
            proc.stdin.write(frame.tobytes())
            if i % int(self.total_frames / 10 or 1) == 0:
                print(f"   Progress: {int(i / self.total_frames * 100)}% ({i}/{self.total_frames} frames)")
        proc.stdin.close()
        proc.wait()
        print("✅ Screen Walkthrough frames rendered successfully!")


# ==============================================================================
# 2. Before/After Slider Renderer (For Transformation Apps: Glow, Photo/Design/Fitness)
# ==============================================================================

class BeforeAfterSliderRenderer:
    """
    Renders 1080x1920 video ads with an interactive Before/After comparison slider
    and coaching breakdown sheet, parameterized by `config.brand`.
    """
    def __init__(self, config: CampaignConfig, timing: Dict):
        self.config = config
        self.timing = timing
        self.fps = config.fps
        self.total_frames = int(timing["total_seconds"] * self.fps)
        self.scenes = timing["scenes"]
        self.accent_rgba = _rgba(config.brand.primary_accent_rgb, 255)
        self.accent_soft = _rgba(config.brand.primary_accent_rgb, 240)

        self.before_raw = Image.open(config.before_image).convert("RGBA")
        self.after_raw = Image.open(config.after_image).convert("RGBA")

        src_w, src_h = self.before_raw.size
        self.aspect = src_w / float(src_h)

        self.CARD_H = 1230
        self.CARD_W = int(self.CARD_H * self.aspect)
        self.CARD_X = (WIDTH - self.CARD_W) // 2
        self.CARD_Y = 300

        self.before_card = self.before_raw.resize((self.CARD_W, self.CARD_H), Image.Resampling.LANCZOS)
        self.after_card = self.after_raw.resize((self.CARD_W, self.CARD_H), Image.Resampling.LANCZOS)

        bg_b = cover_resize(self.before_raw, WIDTH, HEIGHT).filter(ImageFilter.GaussianBlur(38))
        dark_ov = Image.new("RGBA", (WIDTH, HEIGHT), _rgba(config.brand.surface_bg_rgb, 175))
        self.bg_before = Image.alpha_composite(bg_b, dark_ov)

        bg_a = cover_resize(self.after_raw, WIDTH, HEIGHT).filter(ImageFilter.GaussianBlur(38))
        self.bg_after = Image.alpha_composite(bg_a, dark_ov)

        self.card_mask = Image.new("L", (self.CARD_W, self.CARD_H), 0)
        ImageDraw.Draw(self.card_mask).rounded_rectangle((0, 0, self.CARD_W, self.CARD_H), radius=40, fill=255)

        self.scene3_base = self._build_scene3_screen()

    def _draw_progression_bar(self, frame: Image.Image, active_step: int) -> Image.Image:
        ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        pills = self.config.brand.tracker_pills or ["Base Look · 7.8", "1-Piece Swap", "3+ Axes · 9.5"]
        while len(pills) < 3:
            pills.append(f"Step {len(pills)+1}")
        labels = [(pills[0], 0), (pills[1], 1), (pills[2], 2)]
        pill_w = 278
        pill_h = 48
        gap = 22
        total_w = len(labels) * pill_w + (len(labels) - 1) * gap
        start_x = (WIDTH - total_w) // 2
        y = 230
        font_p = get_font(23)
        for idx, (text, step_num) in enumerate(labels):
            px = start_x + idx * (pill_w + gap)
            is_active = (step_num == active_step)
            is_done = (step_num < active_step)
            if is_active:
                bg_col = self.accent_rgba
                out_col = (255, 255, 255, 220)
                txt_col = (255, 255, 255, 255)
            elif is_done:
                bg_col = (45, 45, 58, 225)
                out_col = _rgba(self.config.brand.primary_accent_rgb, 150)
                txt_col = (245, 245, 250, 235)
            else:
                bg_col = (22, 22, 30, 200)
                out_col = (255, 255, 255, 55)
                txt_col = (165, 165, 178, 215)
            d.rounded_rectangle((px, y, px + pill_w, y + pill_h), radius=24, fill=bg_col, outline=out_col, width=2)
            bbox = d.textbbox((0, 0), text, font=font_p)
            tw = bbox[2] - bbox[0]
            d.text((px + (pill_w - tw) // 2, y + 11), text, font=font_p, fill=txt_col)
        return Image.alpha_composite(frame, ov)

    def _draw_card_dimension_header(
        self,
        card_img: Image.Image,
        left_label: str,
        right_label: str,
        dim_banner: str = "",
        show_left_pill: bool = True,
    ) -> Image.Image:
        cw, ch = card_img.size
        ov = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        left_clean = left_label.replace("✨", "").strip()
        right_clean = right_label.replace("✨", "").strip()
        dim_clean = dim_banner.replace("✨", "").strip()
        f_pill = get_font(23)
        if show_left_pill and left_clean:
            lb_box = d.textbbox((0, 0), left_clean, font=f_pill)
            lw = (lb_box[2] - lb_box[0]) + 36
            d.rounded_rectangle((20, 20, 20 + lw, 68), radius=24, fill=(24, 24, 32, 210))
            d.text((38, 31), left_clean, font=f_pill, fill=(255, 255, 255, 245))
        if right_clean:
            rb_box = d.textbbox((0, 0), right_clean, font=f_pill)
            rw = (rb_box[2] - rb_box[0]) + 46
            d.rounded_rectangle((cw - 20 - rw, 20, cw - 20, 68), radius=24, fill=self.accent_soft)
            d.text((cw - 20 - rw + 18, 31), right_clean, font=f_pill, fill=(255, 255, 255, 255))
            draw_sparkle(d, cw - 36, 44, r_outer=9, r_inner=3, fill=(253, 224, 71, 255))
        if dim_clean:
            f_dim = get_font(24)
            db_box = d.textbbox((0, 0), dim_clean, font=f_dim)
            dw = (db_box[2] - db_box[0]) + 48
            dx = (cw - dw) // 2
            dy = ch - 78
            d.rounded_rectangle((dx, dy, dx + dw, dy + 54), radius=27, fill=(14, 14, 20, 230), outline=self.accent_soft, width=2)
            d.text((dx + 24, dy + 13), dim_clean, font=f_dim, fill=(255, 255, 255, 255))
        return Image.alpha_composite(card_img, ov)

    def _build_scene3_screen(self) -> Image.Image:
        bg = Image.new("RGBA", (WIDTH, HEIGHT), (248, 248, 250, 255))
        d = ImageDraw.Draw(bg)

        d.text((90, 60), self.config.brand.status_bar_time, font=font_body, fill=(30, 30, 30, 255))
        d.rounded_rectangle((WIDTH - 150, 66, WIDTH - 100, 90), radius=6, outline=(30, 30, 30, 200), width=2)
        d.rounded_rectangle((WIDTH - 146, 70, WIDTH - 108, 86), radius=3, fill=(30, 30, 30, 200))

        card_h = 780
        card_w = int(card_h * self.aspect)
        card_x = (WIDTH - card_w) // 2
        card_y = 220

        c_before = self.before_raw.resize((card_w, card_h), Image.Resampling.LANCZOS)
        c_after = self.after_raw.resize((card_w, card_h), Image.Resampling.LANCZOS)

        split_x = card_w // 2
        card_img = c_after.copy()
        card_img.paste(c_before.crop((0, 0, split_x, card_h)), (0, 0))
        card_img = self._draw_card_dimension_header(card_img, "Before", f"{self.config.brand.app_name} After", show_left_pill=True)

        cd = ImageDraw.Draw(card_img)
        cd.line((split_x, 0, split_x, card_h), fill=(255, 255, 255, 240), width=4)
        cd.ellipse((split_x - 28, card_h // 2 - 28, split_x + 28, card_h // 2 + 28), fill=(255, 255, 255, 250), outline=(200, 200, 200, 180), width=2)
        cd.text((split_x - 14, card_h // 2 - 14), "< >", font=get_font(20), fill=(40, 40, 40, 240))

        cmask = Image.new("L", (card_w, card_h), 0)
        ImageDraw.Draw(cmask).rounded_rectangle((0, 0, card_w, card_h), radius=34, fill=255)
        bg.paste(card_img, (card_x, card_y), cmask)

        sub_text = self.config.breakdown.subtitle_text or "1-piece upgrade complete · 3+ dimensions unlocked"
        sbbox = d.textbbox((0, 0), sub_text, font=get_font(26))
        sw = sbbox[2] - sbbox[0]
        d.text(((WIDTH - sw) // 2, card_y + card_h + 16), sub_text, font=get_font(26), fill=(110, 110, 120, 255))

        box_w = 960
        box_h = 685
        box_x = (WIDTH - box_w) // 2
        box_y = card_y + card_h + 62

        d.rounded_rectangle((box_x, box_y, box_x + box_w, box_y + box_h), radius=36, fill=(242, 242, 246, 255), outline=(228, 228, 234, 255), width=2)

        draw_sparkle(d, box_x + 44, box_y + 42, r_outer=14, r_inner=5, fill=self.accent_rgba)
        d.text((box_x + 70, box_y + 24), self.config.brand.sheet_badge_label, font=get_font(30), fill=self.accent_rgba)

        d.rounded_rectangle((box_x + 270, box_y + 20, box_x + 710, box_y + 64), radius=22, fill=(255, 255, 255, 255))
        d.text((box_x + 304, box_y + 29), self.config.brand.sheet_pill_text, font=get_font(21), fill=(40, 40, 48, 255))

        d.rounded_rectangle((box_x + box_w - 210, box_y + 18, box_x + box_w - 32, box_y + 66), radius=24, fill=self.accent_rgba)
        d.text((box_x + box_w - 186, box_y + 28), self.config.brand.sheet_highlight_pill, font=get_font(24), fill=(255, 255, 255, 255))

        sc_y = box_y + 82
        d.rounded_rectangle((box_x + 32, sc_y, box_x + box_w - 32, sc_y + 132), radius=24, fill=(255, 255, 255, 255))
        d.text((box_x + 60, sc_y + 14), "BASE LOOK", font=get_font(18), fill=(130, 130, 140, 255))
        d.text((box_x + 60, sc_y + 38), "7.8", font=get_font(42), fill=(20, 20, 25, 255))

        d.text((box_x + 260, sc_y + 14), "CHANGED", font=get_font(18), fill=(130, 130, 140, 255))
        d.text((box_x + 260, sc_y + 38), "1 Piece", font=get_font(38), fill=(60, 60, 72, 255))

        d.text((box_x + 475, sc_y + 14), "UNLOCKED", font=get_font(18), fill=(130, 130, 140, 255))
        d.text((box_x + 475, sc_y + 38), "3+ Axes", font=get_font(38), fill=self.accent_rgba)

        d.text((box_x + box_w - 220, sc_y + 14), "FINAL SCORE", font=get_font(18), fill=self.accent_rgba)
        d.text((box_x + box_w - 220, sc_y + 38), "9.5", font=get_font(44), fill=self.accent_rgba)
        d.text((box_x + box_w - 145, sc_y + 54), "/10", font=get_font(24), fill=(140, 140, 150, 255))

        bar_x1, bar_x2 = box_x + 60, box_x + box_w - 60
        bar_y = sc_y + 104
        d.rounded_rectangle((bar_x1, bar_y, bar_x2, bar_y + 12), radius=6, fill=(232, 232, 238, 255))
        fill_w = int((bar_x2 - bar_x1) * 0.95)
        d.rounded_rectangle((bar_x1, bar_y, bar_x1 + fill_w, bar_y + 12), radius=6, fill=self.accent_rgba)

        grid_y = sc_y + 150
        d.text((box_x + 36, grid_y), f"{self.config.brand.app_name} breakdown", font=get_font(22), fill=(100, 100, 112, 255))

        axes = [
            ("Fit", "+0.6"), ("Silhouette", "+0.6"),
            ("Proportion", "+0.7"), ("Contrast", "+0.5"),
            ("Drape", "+0.6"), ("Cohesion", "+0.6"),
        ]
        pill_w = (box_w - 84) // 2
        pill_h = 46
        start_py = grid_y + 34
        for idx, (ax_name, ax_delta) in enumerate(axes):
            col = idx % 2
            row = idx // 2
            px = box_x + 32 + col * (pill_w + 20)
            py = start_py + row * (pill_h + 10)
            d.rounded_rectangle((px, py, px + pill_w, py + pill_h), radius=14, fill=(255, 255, 255, 255))
            d.text((px + 20, py + 10), ax_name, font=get_font(22), fill=(25, 25, 32, 255))
            d.text((px + pill_w - 72, py + 10), ax_delta, font=get_font(22), fill=self.accent_rgba)

        bullets = self.config.breakdown.bullets
        cur_by = start_py + 3 * (pill_h + 10) + 14
        for b in bullets[:2]:
            d.text((box_x + 36, cur_by), b.title, font=get_font(26), fill=(20, 20, 25, 255))
            d.rounded_rectangle((box_x + box_w - 150, cur_by - 2, box_x + box_w - 36, cur_by + 32), radius=16, fill=(252, 231, 243, 255))
            d.text((box_x + box_w - 134, cur_by + 3), "+0.9 pts", font=get_font(20), fill=self.accent_rgba)
            d.text((box_x + 36, cur_by + 34), b.description, font=get_font(22), fill=(95, 95, 108, 255))
            cur_by += 78

        btn_w = 960
        btn_h = 82
        btn_x = (WIDTH - btn_w) // 2
        btn_y = box_y + box_h + 22
        d.rounded_rectangle((btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), radius=41, fill=self.accent_rgba)
        btn_title = self.config.breakdown.button_text
        bbox = d.textbbox((0, 0), btn_title, font=get_font(30))
        tw = bbox[2] - bbox[0]
        d.text(((WIDTH - tw) // 2, btn_y + 23), btn_title, font=get_font(30), fill=(255, 255, 255, 255))

        return bg

    def _render_slider_step(
        self,
        from_card: Image.Image,
        to_card: Image.Image,
        reveal: float,
        active_step: int,
        left_label: str,
        right_label: str,
        dim_banner: str,
        bottom_badge: List[str],
    ) -> Image.Image:
        split_x = int(self.CARD_W * reveal)
        card_composite = to_card.copy()
        if split_x > 4:
            left_crop = from_card.crop((0, 0, split_x, self.CARD_H))
            card_composite.paste(left_crop, (0, 0))
        show_left = (split_x > 90)
        card_composite = self._draw_card_dimension_header(
            card_composite, left_label, right_label, dim_banner, show_left_pill=show_left
        )

        frame = self.bg_after.copy()
        frame.paste(card_composite, (self.CARD_X, self.CARD_Y), self.card_mask)
        frame = draw_brand_app_header(
            frame,
            app_name=self.config.brand.app_name,
            badge_text=self.config.brand.header_badge_text,
            status_time=self.config.brand.status_bar_time,
        )
        frame = self._draw_progression_bar(frame, active_step=active_step)

        if 4 < split_x < self.CARD_W - 4:
            div_x = self.CARD_X + split_x
            d = ImageDraw.Draw(frame)
            d.line((div_x, self.CARD_Y, div_x, self.CARD_Y + self.CARD_H), fill=(255, 255, 255, 240), width=4)
            knob_r = 32
            knob_y = self.CARD_Y + self.CARD_H // 2
            d.ellipse(
                (div_x - knob_r, knob_y - knob_r, div_x + knob_r, knob_y + knob_r),
                fill=(255, 255, 255, 245),
                outline=(200, 200, 200, 180),
                width=2,
            )
            d.text((div_x - 18, knob_y - 16), "< >", font=font_small, fill=(20, 20, 20, 240))
        clean_badge = [b.replace("✨", "").strip() for b in bottom_badge]
        frame = draw_pill_badge(frame, clean_badge, y_top=1575, font=font_h2)
        return frame

    def render_frame(self, f_idx: int) -> Image.Image:
        time_s = f_idx / self.fps
        s1 = self.scenes[0]
        s2 = self.scenes[1]
        s3 = self.scenes[2]

        if time_s < s1["end"]:
            frame = self.bg_before.copy()
            c_before = self._draw_card_dimension_header(
                self.before_card.copy(),
                self.config.hook.left_pill or "Base 7.8",
                self.config.hook.right_pill or "Target 9.5",
                self.config.hook.banner_text or "Spot the 1 Mistake",
                show_left_pill=True,
            )
            frame.paste(c_before, (self.CARD_X, self.CARD_Y), self.card_mask)
            frame = draw_brand_app_header(
                frame,
                app_name=self.config.brand.app_name,
                badge_text=self.config.brand.header_badge_text,
                status_time=self.config.brand.status_bar_time,
            )
            frame = self._draw_progression_bar(frame, active_step=0)
            frame = draw_pill_badge(frame, self.config.hook.badge_lines, y_top=1575, font=font_h2)
            return frame

        elif time_s < s2["end"]:
            s2_dur = max(0.1, s2["end"] - s2["start"])
            s2_prog = (time_s - s2["start"]) / s2_dur
            t = min(1.0, max(0.0, s2_prog / 0.38))
            smooth = t * t * (3.0 - 2.0 * t)
            reveal = 1.0 - smooth
            if s2_prog < 0.52:
                badge1 = self.config.step1_badge if self.config.step1_badge else self.config.reveal.badge_lines
                return self._render_slider_step(
                    from_card=self.before_card,
                    to_card=self.after_card,
                    reveal=reveal,
                    active_step=1,
                    left_label="Base 7.8",
                    right_label=f"{self.config.brand.app_name} 9.5",
                    dim_banner=self.config.step1_title,
                    bottom_badge=badge1,
                )
            else:
                badge2 = self.config.step2_badge if self.config.step2_badge else self.config.reveal.badge_lines
                return self._render_slider_step(
                    from_card=self.before_card,
                    to_card=self.after_card,
                    reveal=0.0,
                    active_step=2,
                    left_label="",
                    right_label=f"{self.config.brand.app_name} 9.5",
                    dim_banner=self.config.step2_title,
                    bottom_badge=badge2,
                )

        elif time_s < s3["end"]:
            s3_dur = max(0.1, s3["end"] - s3["start"])
            s3_prog = (time_s - s3["start"]) / s3_dur
            if s3_prog < 0.38:
                badge3 = self.config.step3_badge if self.config.step3_badge else self.config.breakdown.badge_lines
                return self._render_slider_step(
                    from_card=self.before_card,
                    to_card=self.after_card,
                    reveal=0.0,
                    active_step=2,
                    left_label="",
                    right_label=f"{self.config.brand.app_name} 9.5",
                    dim_banner=self.config.step3_title,
                    bottom_badge=badge3,
                )
            else:
                frame = self.scene3_base.copy()
                badge_font = get_font(34) if len(self.config.breakdown.badge_lines) == 1 else get_font(30)
                frame = draw_pill_badge(frame, self.config.breakdown.badge_lines, y_top=68, font=badge_font, pill_bg=(14, 14, 18, 245))
                return frame

        else:
            frame = self.bg_after.copy()
            ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 140))
            frame = Image.alpha_composite(frame, ov)

            small_h = 860
            small_w = int(small_h * self.aspect)
            small_x = (WIDTH - small_w) // 2
            small_y = 250
            small_card = self.after_raw.resize((small_w, small_h), Image.Resampling.LANCZOS)
            smask = Image.new("L", (small_w, small_h), 0)
            ImageDraw.Draw(smask).rounded_rectangle((0, 0, small_w, small_h), radius=36, fill=255)
            frame.paste(small_card, (small_x, small_y), smask)

            d = ImageDraw.Draw(frame)
            app_t = self.config.outro.app_title
            bbox1 = d.textbbox((0, 0), app_t, font=get_font(48))
            d.text(((WIDTH - (bbox1[2] - bbox1[0])) // 2, 1160), app_t, font=get_font(48), fill=(255, 255, 255, 255))

            sub_t = self.config.outro.subtitle
            bbox2 = d.textbbox((0, 0), sub_t, font=font_body)
            d.text(((WIDTH - (bbox2[2] - bbox2[0])) // 2, 1230), sub_t, font=font_body, fill=(220, 220, 220, 240))

            btn_w = 780
            btn_h = 96
            btn_x = (WIDTH - btn_w) // 2
            btn_y = 1330
            d.rounded_rectangle((btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), radius=48, fill=self.accent_rgba)
            cta_t = self.config.outro.cta_button_text
            bbox3 = d.textbbox((0, 0), cta_t, font=get_font(38))
            d.text(((WIDTH - (bbox3[2] - bbox3[0])) // 2, btn_y + 26), cta_t, font=get_font(38), fill=(255, 255, 255, 255))

            frame = draw_pill_badge(frame, self.config.outro.bottom_pill_lines, y_top=1540, font=font_h2)
            return frame

    def render_video(self, temp_mp4_path: str):
        print(f"🎬 [Before/After Slider Renderer — {self.config.brand.app_name}] Rendering {self.total_frames} frames @ {self.fps} fps ({self.total_frames/self.fps:.1f}s)...")
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-pix_fmt", "rgba",
            "-r", str(self.fps),
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "18",
            temp_mp4_path,
        ]
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
        for i in range(self.total_frames):
            frame = self.render_frame(i)
            proc.stdin.write(frame.tobytes())
            if i % int(self.total_frames / 10 or 1) == 0:
                print(f"   Progress: {int(i / self.total_frames * 100)}% ({i}/{self.total_frames} frames)")
        proc.stdin.close()
        proc.wait()
        print("✅ Before/After Slider frames rendered successfully!")


# ==============================================================================
# 3. Side-by-Side Proof Renderer (`side_by_side_proof` / `native_loop`)
# ==============================================================================

class SideBySideProofRenderer:
    def __init__(self, config: CampaignConfig, timing: Dict):
        self.config = config
        self.timing = timing
        self.fps = config.fps
        self.total_frames = int(timing["total_seconds"] * self.fps)
        self.phases = timing.get("phases", timing.get("scenes", []))
        self.accent_rgba = _rgba(config.brand.primary_accent_rgb, 255)

        self.before_raw = Image.open(config.before_image).convert("RGBA")
        self.after_raw = Image.open(config.after_image).convert("RGBA")

        bg_blur = self.before_raw.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(50))
        dark_ov = Image.new("RGBA", (WIDTH, HEIGHT), _rgba(config.brand.surface_bg_rgb, 215))
        self.base_bg = Image.alpha_composite(bg_blur, dark_ov)

        self.card_w = 505
        self.card_h = 1380
        self.card_y = 260
        self.card_x1 = 25
        self.card_x2 = 550

        scale = self.card_h / float(self.before_raw.height)
        scaled_w = int(self.before_raw.width * scale)
        b_scaled = self.before_raw.resize((scaled_w, self.card_h), Image.Resampling.LANCZOS)
        a_scaled = self.after_raw.resize((scaled_w, self.card_h), Image.Resampling.LANCZOS)

        crop_x = max(0, (scaled_w - self.card_w) // 2)
        self.b_crop = b_scaled.crop((crop_x, 0, crop_x + self.card_w, self.card_h))
        self.a_crop = a_scaled.crop((crop_x, 0, crop_x + self.card_w, self.card_h))

        cmask = Image.new("L", (self.card_w, self.card_h), 0)
        ImageDraw.Draw(cmask).rounded_rectangle((0, 0, self.card_w, self.card_h), radius=28, fill=255)

        self.base_frame = self.base_bg.copy()
        self.base_frame.paste(self.b_crop, (self.card_x1, self.card_y), cmask)
        self.base_frame.paste(self.a_crop, (self.card_x2, self.card_y), cmask)

        d = ImageDraw.Draw(self.base_frame)

        def draw_badge(bx, by, text, bg_col):
            b_font = get_font(22)
            bbox = d.textbbox((0, 0), text, font=b_font)
            bw = (bbox[2] - bbox[0]) + 28
            bh = (bbox[3] - bbox[1]) + 16
            d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=12, fill=bg_col)
            d.text((bx + 14, by + 8), text, font=b_font, fill=(255, 255, 255, 255))

        draw_badge(self.card_x1 + 18, self.card_y + 18, "BEFORE", (20, 20, 25, 230))
        draw_badge(self.card_x2 + 18, self.card_y + 18, "AFTER", self.accent_rgba)

        if len(self.phases) >= 3:
            self.p1_end = self.phases[0]["end"]
            self.p2_end = self.phases[1]["end"]
            self.p3_end = self.phases[2]["end"]
        else:
            self.p1_end = timing["total_seconds"] * 0.33
            self.p2_end = timing["total_seconds"] * 0.66
            self.p3_end = timing["total_seconds"]

    def draw_top_badge(self, img: Image.Image, lines: List[str], color2=(255, 78, 80, 255)) -> Image.Image:
        if not lines:
            return img
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        font1 = get_font(38)
        font2 = get_font(34)
        boxes = [d.textbbox((0, 0), lines[0], font=font1)]
        if len(lines) > 1:
            boxes.append(d.textbbox((0, 0), lines[1], font=font2))
        max_w = max(b[2] - b[0] for b in boxes)
        total_h = sum(b[3] - b[1] for b in boxes) + (14 if len(lines) > 1 else 0)
        box_w = max_w + 64
        box_h = total_h + 44
        box_x = (WIDTH - box_w) // 2
        box_y = 80
        d.rounded_rectangle((box_x, box_y, box_x + box_w, box_y + box_h), radius=28, fill=(10, 10, 14, 248), outline=(255, 255, 255, 75), width=2)
        w0 = boxes[0][2] - boxes[0][0]
        d.text(((WIDTH - w0) // 2, box_y + 20), lines[0], font=font1, fill=(255, 255, 255, 255))
        if len(lines) > 1:
            w1 = boxes[1][2] - boxes[1][0]
            d.text(((WIDTH - w1) // 2, box_y + 20 + (boxes[0][3] - boxes[0][1]) + 14), lines[1], font=font2, fill=color2)
        return Image.alpha_composite(img, overlay)

    def draw_bottom_pill(self, img: Image.Image, text: str, sub_credit: str = "") -> Image.Image:
        if not text:
            return img
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        font = get_font(28)
        bbox = d.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pw = tw + 56
        ph = th + 28
        px = (WIDTH - pw) // 2
        py = 1675
        d.rounded_rectangle((px, py, px + pw, py + ph), radius=24, fill=(14, 14, 18, 235), outline=(255, 255, 255, 60), width=1)
        d.text(((WIDTH - tw) // 2, py + 14), text, font=font, fill=(255, 255, 255, 240))
        if sub_credit:
            c_font = get_font(22)
            cbox = d.textbbox((0, 0), sub_credit, font=c_font)
            cw = cbox[2] - cbox[0]
            d.text(((WIDTH - cw) // 2, py + ph + 16), sub_credit, font=c_font, fill=(150, 150, 160, 220))
        return Image.alpha_composite(img, overlay)

    def render_frame(self, f_idx: int) -> Image.Image:
        time_s = f_idx / self.fps
        f = self.base_frame.copy()
        if time_s < self.p1_end:
            f = self.draw_top_badge(f, self.config.hook.badge_lines, color2=(255, 220, 100, 255))
            bot_text = getattr(self.config.proof, "bottom_pill", "") or f"Spot the difference · {self.config.brand.app_name}"
            f = self.draw_bottom_pill(f, bot_text)
        elif time_s < self.p2_end:
            f = self.draw_top_badge(f, self.config.proof.badge_lines, color2=self.accent_rgba)
            bot_text = getattr(self.config.proof, "bottom_pill", "") or f"Why it works · {self.config.brand.app_name}"
            f = self.draw_bottom_pill(f, bot_text)
        else:
            f = self.draw_top_badge(f, self.config.takeaway.badge_lines, color2=(70, 255, 140, 255))
            bot_text = getattr(self.config.takeaway, "bottom_pill", "") or self.config.outro.cta_button_text
            sub_c = getattr(self.config.takeaway, "sub_credit", "") or f"{self.config.brand.app_name} • {self.config.brand.tagline}"
            f = self.draw_bottom_pill(f, bot_text, sub_credit=sub_c)
        return f

    def render_video(self, temp_mp4_path: str):
        print(f"🎬 [Side-by-Side Proof Renderer — {self.config.brand.app_name}] Rendering {self.total_frames} frames @ {self.fps} fps...")
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-pix_fmt", "rgba",
            "-r", str(self.fps),
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "18",
            temp_mp4_path,
        ]
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
        for i in range(self.total_frames):
            frame = self.render_frame(i)
            proc.stdin.write(frame.tobytes())
            if i % int(self.total_frames / 10 or 1) == 0:
                print(f"   Progress: {int(i / self.total_frames * 100)}% ({i}/{self.total_frames} frames)")
        proc.stdin.close()
        proc.wait()
        print("✅ Side-by-Side Proof frames rendered successfully!")


# ==============================================================================
# Unified Video Renderer Router
# ==============================================================================

class VideoRenderer:
    def __init__(self, config: CampaignConfig, timing: Dict):
        self.config = config
        self.timing = timing
        fmt = getattr(config, "format", "screen_walkthrough").lower()
        if fmt in ("native_loop", "side_by_side_proof"):
            self.engine = SideBySideProofRenderer(config, timing)
        elif fmt in ("before_after_slider", "app_template") and not config.screenshots:
            self.engine = BeforeAfterSliderRenderer(config, timing)
        elif fmt == "before_after_slider":
            self.engine = BeforeAfterSliderRenderer(config, timing)
        else:
            self.engine = ScreenWalkthroughRenderer(config, timing)

    def render_video(self, temp_mp4_path: str):
        self.engine.render_video(temp_mp4_path)
