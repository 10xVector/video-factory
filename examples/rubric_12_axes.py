"""
Glow 12-Axis Fashion Evaluation Rubric (Ticket #1).

Addresses: "Sometimes the agent thinks the fashion looks good but to someone else it looks
like a downgrade so how do we stir the agent to the right direction"

Defines the 12 core fashion evaluation dimensions, their 1.0–10.0 scoring anchors,
visual/structural indicators, and prompt-steering remedies when an axis regresses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class FashionAxis:
    key: str
    name: str
    ticket_definition: str
    eval_criteria: str
    low_score_anchor: str   # 1.0 - 4.5 (Downgrade / Poor)
    mid_score_anchor: str   # 5.0 - 7.5 (Acceptable / Casual Baseline)
    high_score_anchor: str  # 8.0 - 10.0 (Elevated / Editorial / Intentional)
    steering_remedy: str    # Actionable prompt steering instruction when this axis regresses


RUBRIC_12_AXES: List[FashionAxis] = [
    FashionAxis(
        key="fit",
        name="Fit",
        ticket_definition="How clothing sits on your body: tight, relaxed, oversized, tailored.",
        eval_criteria=(
            "Shoulder seams align with natural deltoids, chest and waist skim comfortably with room to breathe "
            "(never constricting or skin-tight), and pants have generous room through the upper thighs (zero thigh clinging)."
        ),
        low_score_anchor="Garments pull tightly across torso or upper thighs, choke the neck, or balloon sloppily.",
        mid_score_anchor="Wearable fit, but jeans/pants cling slightly at the upper thighs or top feels slightly stiff.",
        high_score_anchor="Effortlessly comfortable, breathable fit through torso and upper thighs that honors the wearer's frame.",
        steering_remedy=(
            "STEER [Fit]: Ensure generous, relaxed drape through the upper thighs (never tight on the thighs) and "
            "breathable comfort through the chest/neck (avoid tight mock-necks)."
        ),
    ),
    FashionAxis(
        key="silhouette",
        name="Silhouette",
        ticket_definition="The overall outline: broad shoulders, tapered waist, wide legs, straight shape.",
        eval_criteria=(
            "Balanced top-to-bottom outer contour where leg volume proportionally supports upper-body and jacket width "
            "(never skinny/tapered legs under a broad or stocky torso)."
        ),
        low_score_anchor="Top-heavy 'ice cream cone' silhouette (broad jacket over skinny legs) or formless frumpy blob.",
        mid_score_anchor="Basic everyday outline; leg width is slightly narrow relative to the upper layer.",
        high_score_anchor="Harmonious architectural outline with full-cut wide-straight legs balancing the shoulders.",
        steering_remedy=(
            "STEER [Silhouette]: Widen leg cut to a full-cut wide-straight leg from hip to ankle so lower-body volume "
            "balances shoulder/jacket width (never taper pants on broad or stocky frames)."
        ),
    ),
    FashionAxis(
        key="proportion",
        name="Proportion",
        ticket_definition="How the lengths and sizes relate: cropped jacket with high-waisted pants, rule of thirds (1/3 top to 2/3 leg).",
        eval_criteria=(
            "Outerwear/jacket or untucked top ends cleanly at the natural waist / belt line (never hanging long over the hips) "
            "to establish a flattering 1/3 torso to 2/3 leg visual split."
        ),
        low_score_anchor="Long untucked tee or hip-covering chore jacket drops the waistline and makes legs look short.",
        mid_score_anchor="Neutral waist placement; slightly low jacket/shirt hem or raw-looking crop.",
        high_score_anchor="Clean 1/3 top to 2/3 leg rule-of-thirds split using a waist-cropped jacket over high/natural-rise bottoms.",
        steering_remedy=(
            "STEER [Proportion]: Use a waist-length cropped jacket/cardigan ending right at the belt line so legs look long "
            "(never let long untucked tops or long chore jackets shorten the legs)."
        ),
    ),
    FashionAxis(
        key="contrast",
        name="Contrast",
        ticket_definition="Differences in light/dark, color, texture, or volume that draw attention and frame skin tone against background.",
        eval_criteria=(
            "Crisp light/dark or rich seasonal color contrast between inner top, outer layer, and bottoms that brightens "
            "skin tone and pops against the backdrop (never dull, muddy washed-out grey-on-faded-black)."
        ),
        low_score_anchor="Dull, muddy, washed-out grey/charcoal blending into faded black, or washes out skin tone.",
        mid_score_anchor="Safe neutral palette, but lacks a crisp inner/outer contrast pop.",
        high_score_anchor="Rich, saturated seasonal tone paired with a crisp contrasting inner layer (e.g. warm cream under oxblood/rust).",
        steering_remedy=(
            "STEER [Contrast]: Replace dull washed-out grey tees with a crisp contrasting inner layer (warm cream/ivory "
            "or rich saturated knit) under a rich seasonal outer layer so the outfit pops."
        ),
    ),
    FashionAxis(
        key="drape",
        name="Drape",
        ticket_definition="How fabric hangs and moves: fluid and flowing versus stiff and structured, no messy ankle bunching.",
        eval_criteria=(
            "Fabric falls loosely and fluidly from the widest part of the hip straight through the thigh to a clean "
            "break at the shoe, with zero upper-thigh tightness and zero ankle puddling."
        ),
        low_score_anchor="Tight pulling across the thighs, stiff corporate creases, or heavy accordion stacking at the ankles.",
        mid_score_anchor="Moderate drape with slight tightness at the hip/thigh or minor knee creasing.",
        high_score_anchor="Fluid, unconstructed vertical hang from hip through thigh to shoe hem.",
        steering_remedy=(
            "STEER [Drape]: Let trousers/denim fall loosely from the widest part of the hip with generous thigh room "
            "and a clean break at the shoe."
        ),
    ),
    FashionAxis(
        key="structure",
        name="Structure",
        ticket_definition="How much a garment holds its shape, such as a blazer versus a soft cardigan.",
        eval_criteria=(
            "Appropriate garment architecture in collars, lapels, shoulders, and waistbands so pieces hold their "
            "intended form rather than collapsing limply."
        ),
        low_score_anchor="Collapsed collars, limp shapeless knits, or overly rigid armor-like distortion.",
        mid_score_anchor="Casual jersey/cotton softness; holds basic shape.",
        high_score_anchor="Crisp collar stand, defined shoulder seam, and substantial fabric weight that holds its shape.",
        steering_remedy=(
            "STEER [Structure]: Specify heavyweight or structured fabrics (e.g. heavyweight cotton, structured wool/twill, "
            "crisp collar stand) so garments hold architectural shape at the collar and shoulder."
        ),
    ),
    FashionAxis(
        key="balance",
        name="Balance",
        ticket_definition="How visual weight is distributed: e.g. a bulky jacket paired with substantial shoes.",
        eval_criteria=(
            "Visual weight is anchored harmoniously between upper body and footwear (e.g. wide trousers or layered "
            "outerwear grounded by substantial loafers, derbies, or structured sneakers rather than flimsy footwear)."
        ),
        low_score_anchor="Top-heavy bulk with tiny/flimsy shoes, or cavernous wide pants overwhelming a tiny tight top.",
        mid_score_anchor="Even everyday weight distribution without major top/bottom mismatch.",
        high_score_anchor="Harmonious visual equilibrium — upper layering weight is grounded by substantial, matching footwear.",
        steering_remedy=(
            "STEER [Balance]: Ground wider trousers or layered tops with substantial footwear (lug-sole loafers, "
            "leather derbies, structured trainers) in a tone that anchors the lower half."
        ),
    ),
    FashionAxis(
        key="pattern_scale",
        name="Pattern & scale",
        ticket_definition="Prints and their size: thin stripes, large checks, small florals, or clean tonal solids.",
        eval_criteria=(
            "Pattern scale or solid texture is proportional to the wearer's frame and never introduces noisy visual "
            "clutter or widening horizontal bands."
        ),
        low_score_anchor="Loud clashing prints, widening thick horizontal stripes, or busy graphic clutter.",
        mid_score_anchor="Plain flat solids or standard casual graphics.",
        high_score_anchor="Refined tonal solids, subtle weave/knit textures, or frame-proportional fine patterns.",
        steering_remedy=(
            "STEER [Pattern & scale]: Favor rich tonal solids and tactile fabric weaves (ribbed knit, twill, selvedge, "
            "oxford) over loud graphics or widening horizontal stripes."
        ),
    ),
    FashionAxis(
        key="layering",
        name="Layering",
        ticket_definition="Combining pieces to create depth, visible edges, and different lengths appropriate for the climate.",
        eval_criteria=(
            "Layers create clean vertical center lines (e.g. open overshirt/jacket over base tee) with visible edge "
            "separation and fabric weights that match the real physical climate/setting."
        ),
        low_score_anchor="Weather-inappropriate heavy coats in summer heat, or bulky stuffed layers that add mass.",
        mid_score_anchor="Single-layer everyday outfit or basic hoodie/jacket pairing.",
        high_score_anchor="Climate-appropriate dimensional layering with clean open vertical lines and distinct hem depths.",
        steering_remedy=(
            "STEER [Layering]: Match layer count and fabric weight strictly to the real photo setting/climate; use "
            "open mid-layers to create a slimming vertical center column."
        ),
    ),
    FashionAxis(
        key="details",
        name="Details",
        ticket_definition="Necklines, collars, seams, buttons, cuffs, and accessories (zero collar bleed).",
        eval_criteria=(
            "Crisp neckline/collar execution, clean cuff roll or break, neat button/placket alignment, and zero "
            "old-shirt collar bleed or artifacting around the neck/nape."
        ),
        low_score_anchor="Old shirt collar bleeding through at the neck, sloppy cuffs, or muddled neckline seams.",
        mid_score_anchor="Clean basic neckline and hems without notable artifacting or elevated hardware/trim.",
        high_score_anchor="Impeccable collar framing, zero old-garment bleed, clean cuffs, and refined hardware/seams.",
        steering_remedy=(
            "STEER [Details]: Completely replace the original collar/neckline at front and nape with zero old-shirt "
            "bleed; sharpen lapel, button placket, and cuff edges."
        ),
    ),
    FashionAxis(
        key="cohesion",
        name="Cohesion",
        ticket_definition="How well the pieces feel connected through style, color, or repeated details.",
        eval_criteria=(
            "Hair, top, bottoms, and shoes belong to the same intentional style vocabulary and seasonal color family, "
            "fitting the real physical scene naturally."
        ),
        low_score_anchor="Disjointed pieces from conflicting formalities/palettes or costume-like mismatch with the scene.",
        mid_score_anchor="Passable casual combination, though pieces feel assembled randomly rather than curated.",
        high_score_anchor="Every piece (hair, top, trousers, shoes) speaks the same style language and seasonal palette.",
        steering_remedy=(
            "STEER [Cohesion]: Lock hair, top, trousers, and shoes into a single unified style preset and seasonal "
            "color family that belongs naturally in the physical scene."
        ),
    ),
    FashionAxis(
        key="focal_point",
        name="Focal point",
        ticket_definition="The element you notice first: face framing, collar contrast, or statement jacket.",
        eval_criteria=(
            "The outfit directs the viewer's eye immediately to the wearer's face and upper collar/jacket framing "
            "rather than distracting with loud shoes or messy hems."
        ),
        low_score_anchor="Eye is pulled away from the face by bright ankle stop-signs, messy bunching, or loud graphic noise.",
        mid_score_anchor="No glaring distraction, though the neckline/hair doesn't actively frame the face.",
        high_score_anchor="Unmistakable upward draw — hair framing, collar contrast, and jacket lines pull attention straight to the face.",
        steering_remedy=(
            "STEER [Focal point]: Frame the face with an intentional neckline/collar contrast and quiet the lower half "
            "(no bright contrasting shoes that steal attention from the face)."
        ),
    ),
]

AXIS_BY_KEY: Dict[str, FashionAxis] = {axis.key: axis for axis in RUBRIC_12_AXES}
AXIS_KEYS: List[str] = [axis.key for axis in RUBRIC_12_AXES]


def format_rubric_for_prompt() -> str:
    """Formats all 12 fashion axes for the Gemini Vision judge prompt."""
    lines: List[str] = []
    for idx, axis in enumerate(RUBRIC_12_AXES, start=1):
        lines.append(
            f"{idx}. `{axis.key}` ({axis.name}): {axis.ticket_definition}\n"
            f"   - Criteria: {axis.eval_criteria}\n"
            f"   - 1.0–4.5: {axis.low_score_anchor}\n"
            f"   - 5.0–7.5: {axis.mid_score_anchor}\n"
            f"   - 8.0–10.0: {axis.high_score_anchor}"
        )
    return "\n".join(lines)
