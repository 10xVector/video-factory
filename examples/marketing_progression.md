# Marketing Video Rule: Single High-Impact Piece Isolation & Zero Model-Size Drift

Every Glow educational marketing video (`marketing/factory/templates/educational_*.json`) must follow the **Single High-Impact Piece ("Everything right except 1 piece → 1 Swap unlocks 3+ Dimensions")** format and pass all 4 mathematical quality gates in `ScriptReviewManager.audit_stage_progression()`:

## 1. Creative & Pedagogical Format ("1 Piece → 3+ Dimensions")
- **Base Look (`7.8/10`)**: Everything in the outfit already works *except* for **1 specific piece** holding it back (or 1 missing outer layer/focal piece).
- **1-Piece Swap (`7.8 → 9.5 ✨`)**: Only **ONE garment zone** changes between `before_image` and `after_image` (either ONLY the Lower Body pants/skirt & shoes while the top stays 100% locked, OR ONLY the Upper Body top/outerwear while the pants/skirt & shoes stay 100% locked).
- **Multi-Dimension Breakdown (`3+ Axes Unlocked`)**: Show how that single piece upgrade boosts **3+ dimensions at once** (`step1_title` / `step2_title` / `step3_title` + 12-Axis Fashion Methodology sheet).

## 2. Hard Mathematical Quality Gates (`script_manager.py`)
Before any video is rendered by `video_factory.py`, `ScriptReviewManager.audit_stage_progression()` enforces:
1. **Gate 1 — Model Size & Head Position Lock (`head_diff <= 6.0`)**:
   - Measures pixel diff in the Head/Face anchor box (`y=0.14..0.23, x=0.38..0.62`). Any shift in model scale or head position (`head_diff > 6.0`) is automatically rejected (`❌ MODEL SIZE / HEAD SHIFT REJECTED`).
2. **Gate 2 — Camera & Background Framing Lock (`bg_diff <= 6.0`)**:
   - Measures pixel diff in the background anchor box (`y=0.0..0.16, x=0.0..0.22`). Any camera zoom or background shift (`bg_diff > 6.0`) is automatically rejected.
3. **Gate 3 — Single-Piece Garment Isolation (`unchanged_zone_diff <= 8.0` and `ratio >= 5.0x`)**:
   - Verifies that ONLY ONE garment zone (Upper Body OR Lower Body) changes while the other stays pixel-locked (`❌ MULTI-PIECE / FULL-OUTFIT SWAP REJECTED`).
4. **Gate 4 — High-Impact Visual Upgrade (`changed_zone_diff >= 15.0`)**:
   - Verifies that the single swapped piece creates a clear, high-impact visual difference (`❌ LOW-IMPACT / NO-OP SWAP REJECTED`).
