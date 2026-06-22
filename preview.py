# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFont
import pathlib

assets = pathlib.Path(__file__).parent / "assets"
out_dir = pathlib.Path(__file__).parent / "output"
out_dir.mkdir(exist_ok=True)

bg = Image.open(assets / "background.jpg").convert("RGBA")
w, h = bg.size

font = ImageFont.truetype(str(assets / "Pretendard-Bold.ttf"), 72)
lines = ["오늘도", "최선을 다하면", "내일이 달라진다"]

bboxes = [font.getbbox(l) for l in lines]
lws = [b[2]-b[0] for b in bboxes]
lhs = [b[3]-b[1] for b in bboxes]
gap = 22
total_h = sum(lhs) + gap*(len(lines)-1)
pad = 32

overlay = Image.new("RGBA", bg.size, (0,0,0,0))
draw = ImageDraw.Draw(overlay)

bx0 = (w - max(lws))//2 - pad
by0 = (h - total_h)//2 - pad
bx1 = bx0 + max(lws) + pad*2
by1 = by0 + total_h + pad*2

draw.rounded_rectangle((bx0, by0, bx1, by1), radius=24, fill=(0,0,0,180))

y = by0 + pad
for i, line in enumerate(lines):
    x = (w - lws[i])//2
    draw.text((x, y), line, font=font, fill=(255,255,255,255))
    y += lhs[i] + gap

result = Image.alpha_composite(bg, overlay).convert("RGB")
out_path = out_dir / "preview.jpg"
result.save(out_path, quality=95)
print("저장 완료:", out_path)
