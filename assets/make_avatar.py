"""Render the ЛОРдок bot profile picture.

Flat-design, gender-neutral doctor + stethoscope on a round brand-blue
background. Renders at 4× (2560 px) and downscales to 640 px for clean
antialiasing — Telegram accepts up to 5 MB PNG/JPG for userpics and
renders avatars as circles.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# Brand palette
BG_DARK = (31, 56, 100)      # #1F3864 — dark blue (ring / accents)
BG_MID = (46, 117, 182)      # #2E75B6 — mid blue (background disc)
BG_LIGHT = (214, 228, 240)   # #D6E4F0 — light blue (inner glow)
WHITE = (255, 255, 255)
COAT_SHADOW = (225, 233, 244)  # subtle coat shading
SKIN = (232, 200, 172)       # neutral skin tone
SKIN_SHADE = (214, 180, 150)
HAIR = (58, 46, 42)          # dark brown-black
EYE = (40, 40, 48)
MOUTH = (180, 90, 80)
STETH_TUBE = (45, 55, 70)    # muted navy, reads well on white
STETH_CHEST = (210, 215, 225)
ACCENT_RED = (198, 64, 64)   # red cross dot on chest piece

SCALE = 4
OUT_SIZE = 640
SIZE = OUT_SIZE * SCALE  # 2560
CENTER = (SIZE // 2, SIZE // 2)

OUT_PATH = Path(__file__).parent / "bot_avatar.png"


def draw_background(draw: ImageDraw.ImageDraw) -> None:
    """Round brand-blue disc + thin darker ring."""
    r = SIZE // 2
    # Outer disc
    draw.ellipse([0, 0, SIZE, SIZE], fill=BG_MID)
    # Inner soft highlight ring — gives depth
    ring = int(SIZE * 0.47)
    draw.ellipse(
        [CENTER[0] - ring, CENTER[1] - ring,
         CENTER[0] + ring, CENTER[1] + ring],
        outline=BG_LIGHT,
        width=max(2, SIZE // 320),
    )


def draw_coat(draw: ImageDraw.ImageDraw) -> None:
    """White doctor's coat — torso silhouette with V-neck."""
    cx, cy = CENTER
    # Shoulders trapezoid — bottom of canvas, wide base
    top_y = int(cy + SIZE * 0.10)     # just below chin
    bot_y = SIZE                       # run off the bottom edge
    shoulder_half = int(SIZE * 0.42)
    waist_half = int(SIZE * 0.55)
    # V-neck notch
    neck_half = int(SIZE * 0.055)
    neck_dip = int(cy + SIZE * 0.18)

    coat_poly = [
        (cx - neck_half, top_y),            # left collar top
        (cx - shoulder_half, top_y + int(SIZE * 0.04)),  # left shoulder
        (cx - waist_half, bot_y),           # left hip
        (cx + waist_half, bot_y),           # right hip
        (cx + shoulder_half, top_y + int(SIZE * 0.04)),  # right shoulder
        (cx + neck_half, top_y),            # right collar top
        (cx, neck_dip),                     # V-neck bottom
    ]
    draw.polygon(coat_poly, fill=WHITE)

    # Subtle shoulder shading — inner soft polygon on each side
    shade_left = [
        (cx - shoulder_half + int(SIZE * 0.015),
         top_y + int(SIZE * 0.045)),
        (cx - waist_half + int(SIZE * 0.025), bot_y),
        (cx - waist_half + int(SIZE * 0.12), bot_y),
        (cx - shoulder_half + int(SIZE * 0.12),
         top_y + int(SIZE * 0.05)),
    ]
    shade_right = [(SIZE - x, y) for x, y in shade_left]
    draw.polygon(shade_left, fill=COAT_SHADOW)
    draw.polygon(shade_right, fill=COAT_SHADOW)


def draw_neck_and_head(draw: ImageDraw.ImageDraw) -> None:
    """Short neck + round head."""
    cx, cy = CENTER
    # Neck rectangle (rounded)
    neck_w = int(SIZE * 0.09)
    neck_top = int(cy + SIZE * 0.03)
    neck_bot = int(cy + SIZE * 0.14)
    draw.rounded_rectangle(
        [cx - neck_w, neck_top, cx + neck_w, neck_bot],
        radius=int(SIZE * 0.02),
        fill=SKIN,
    )
    # Neck shadow under chin
    draw.rectangle(
        [cx - neck_w, neck_top, cx + neck_w, neck_top + int(SIZE * 0.018)],
        fill=SKIN_SHADE,
    )

    # Head — circle
    head_r = int(SIZE * 0.17)
    head_cy = int(cy - SIZE * 0.08)
    draw.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
        fill=SKIN,
    )

    # Ear dots
    ear_r = int(SIZE * 0.018)
    ear_y = head_cy + int(SIZE * 0.005)
    for sign in (-1, 1):
        ex = cx + sign * head_r
        draw.ellipse(
            [ex - ear_r, ear_y - ear_r, ex + ear_r, ear_y + ear_r],
            fill=SKIN_SHADE,
        )


def draw_hair(draw: ImageDraw.ImageDraw) -> None:
    """Short cap of hair — gender-neutral."""
    cx, cy = CENTER
    head_r = int(SIZE * 0.17)
    head_cy = int(cy - SIZE * 0.08)
    # Hair cap: pieslice over top ~140 deg
    pad = int(SIZE * 0.008)
    box = [
        cx - head_r - pad,
        head_cy - head_r - pad,
        cx + head_r + pad,
        head_cy + head_r + pad,
    ]
    # Draw pieslice from 200° to 340° (top arc)
    draw.pieslice(box, start=200, end=340, fill=HAIR)
    # Small side sweep to cover temples
    draw.pieslice(
        [cx - head_r, head_cy - int(head_r * 0.95),
         cx + head_r, head_cy + int(head_r * 0.15)],
        start=180, end=360, fill=HAIR,
    )


def draw_face(draw: ImageDraw.ImageDraw) -> None:
    """Eyes and friendly smile."""
    cx, cy = CENTER
    head_cy = int(cy - SIZE * 0.08)
    # Eyes — two small filled circles
    eye_off = int(SIZE * 0.06)
    eye_y = head_cy + int(SIZE * 0.015)
    eye_r = int(SIZE * 0.013)
    for sign in (-1, 1):
        ex = cx + sign * eye_off
        draw.ellipse(
            [ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
            fill=EYE,
        )
    # Smile arc
    mouth_w = int(SIZE * 0.07)
    mouth_h = int(SIZE * 0.035)
    mouth_cy = head_cy + int(SIZE * 0.075)
    draw.arc(
        [cx - mouth_w, mouth_cy - mouth_h,
         cx + mouth_w, mouth_cy + mouth_h],
        start=20, end=160,
        fill=MOUTH,
        width=max(3, SIZE // 320),
    )


def draw_stethoscope(draw: ImageDraw.ImageDraw) -> None:
    """Stethoscope: two tubes from behind shoulders → Y → chest piece."""
    cx, cy = CENTER
    tube_w = max(6, SIZE // 130)

    # Left tube control curve — from behind left shoulder down to Y junction
    left_start = (cx - int(SIZE * 0.23), int(cy + SIZE * 0.10))
    right_start = (cx + int(SIZE * 0.23), int(cy + SIZE * 0.10))
    y_junction = (cx, int(cy + SIZE * 0.28))

    # Approximate each side with a polyline sampled from a quadratic Bezier
    def bezier(p0, p1, p2, steps=80):
        pts = []
        for i in range(steps + 1):
            t = i / steps
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
            pts.append((x, y))
        return pts

    left_ctrl = (cx - int(SIZE * 0.28), int(cy + SIZE * 0.30))
    right_ctrl = (cx + int(SIZE * 0.28), int(cy + SIZE * 0.30))

    left_curve = bezier(left_start, left_ctrl, y_junction)
    right_curve = bezier(right_start, right_ctrl, y_junction)

    draw.line(left_curve, fill=STETH_TUBE, width=tube_w, joint="curve")
    draw.line(right_curve, fill=STETH_TUBE, width=tube_w, joint="curve")

    # Vertical tube to chest piece
    chest_y = int(cy + SIZE * 0.40)
    draw.line(
        [y_junction, (cx, chest_y)],
        fill=STETH_TUBE,
        width=tube_w,
    )

    # Chest piece — larger disc with accent
    disc_r = int(SIZE * 0.045)
    draw.ellipse(
        [cx - disc_r, chest_y - disc_r, cx + disc_r, chest_y + disc_r],
        fill=STETH_CHEST,
        outline=STETH_TUBE,
        width=max(3, SIZE // 320),
    )
    # Tiny red accent in the middle
    dot_r = int(SIZE * 0.012)
    draw.ellipse(
        [cx - dot_r, chest_y - dot_r, cx + dot_r, chest_y + dot_r],
        fill=ACCENT_RED,
    )

    # Ear tips — small round caps at the tube starts
    cap_r = max(4, SIZE // 200)
    for p in (left_start, right_start):
        draw.ellipse(
            [p[0] - cap_r, p[1] - cap_r, p[0] + cap_r, p[1] + cap_r],
            fill=STETH_TUBE,
        )


def main() -> None:
    # Work on an RGBA canvas so the disc has clean edges when downscaled.
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Brand disc background
    draw_background(draw)

    # 2. Coat (behind neck / head / stethoscope)
    draw_coat(draw)

    # 3. Neck + head + ears
    draw_neck_and_head(draw)

    # 4. Hair cap
    draw_hair(draw)

    # 5. Face features
    draw_face(draw)

    # 6. Stethoscope (on top of coat)
    draw_stethoscope(draw)

    # Mask everything outside the circle (Telegram crops to circle anyway,
    # but this makes the PNG clean if viewed elsewhere).
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, SIZE, SIZE], fill=255)
    img.putalpha(mask)

    # Subtle outer shadow ring for polish (darken a 1-px band at the edge)
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ShadowDraw = ImageDraw.Draw(shadow)
    ShadowDraw.ellipse(
        [4, 4, SIZE - 4, SIZE - 4],
        outline=BG_DARK,
        width=max(2, SIZE // 256),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=SIZE // 300))
    img = Image.alpha_composite(img, shadow)

    # Downscale with LANCZOS for clean result
    final = img.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)

    # Flatten onto opaque background — Telegram profile pics must be opaque
    flat = Image.new("RGB", (OUT_SIZE, OUT_SIZE), WHITE)
    flat.paste(final, mask=final.split()[3])
    flat.save(OUT_PATH, format="PNG", optimize=True)

    print(f"Saved: {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
