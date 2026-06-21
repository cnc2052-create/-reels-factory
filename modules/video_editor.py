"""
video_editor.py
- Pillow로 background.jpg + overlay_text 합성 → 임시 PNG 저장
- FFmpeg으로 이미지 + bgm.mp3 → 7초 MP4 생성
"""
import os
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

BG_PATH    = ASSETS_DIR / "background.jpg"
FONT_PATH  = ASSETS_DIR / "font.ttf"
BGM_PATH   = ASSETS_DIR / "bgm.mp3"

# 영상 설정
VIDEO_DURATION = 7          # 초
FONT_SIZE      = 72         # 기본 폰트 크기
MAX_CHARS_PER_LINE = 16     # 줄당 최대 글자 수 (한글 기준)
BOX_PADDING    = 32         # 반투명 박스 내부 여백(px)
BOX_RADIUS     = 24         # 라운드 모서리 반경(px)
BOX_ALPHA      = 180        # 박스 투명도 (0=투명 255=불투명)
TEXT_COLOR     = (255, 255, 255, 255)
BOX_COLOR      = (0, 0, 0, BOX_ALPHA)


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill):
    """PIL에 라운드 사각형을 그린다 (ImageDraw.rounded_rectangle 호환 fallback 포함)."""
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill)
    except AttributeError:
        # Pillow < 8.2 fallback
        x0, y0, x1, y1 = xy
        draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
        draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
        draw.ellipse([x0, y0, x0 + radius * 2, y0 + radius * 2], fill=fill)
        draw.ellipse([x1 - radius * 2, y0, x1, y0 + radius * 2], fill=fill)
        draw.ellipse([x0, y1 - radius * 2, x0 + radius * 2, y1], fill=fill)
        draw.ellipse([x1 - radius * 2, y1 - radius * 2, x1, y1], fill=fill)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """글자 수 기반 + 픽셀 폭 기반 이중 줄바꿈."""
    # 1차: 글자 수 기준 줄바꿈
    raw_lines = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(paragraph, width=MAX_CHARS_PER_LINE) or [""]
        raw_lines.extend(wrapped)

    # 2차: 픽셀 폭 초과 시 추가 분할
    final_lines = []
    for line in raw_lines:
        bbox = font.getbbox(line)
        if bbox[2] - bbox[0] <= max_width:
            final_lines.append(line)
        else:
            # 한 글자씩 늘려가며 자름
            current = ""
            for char in line:
                test = current + char
                w = font.getbbox(test)[2] - font.getbbox(test)[0]
                if w > max_width:
                    final_lines.append(current)
                    current = char
                else:
                    current = test
            if current:
                final_lines.append(current)

    return final_lines


def compose_image(overlay_text: str, index: int) -> Path:
    """배경 이미지에 텍스트를 합성하여 임시 PNG를 반환한다."""
    bg = Image.open(BG_PATH).convert("RGBA")
    w, h = bg.size

    font = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)

    max_text_width = int(w * 0.8)
    lines = _wrap_text(overlay_text, font, max_text_width)

    # 텍스트 블록 전체 크기 계산
    line_bboxes = [font.getbbox(ln) for ln in lines]
    line_heights = [bb[3] - bb[1] for bb in line_bboxes]
    line_widths  = [bb[2] - bb[0] for bb in line_bboxes]
    line_gap     = int(FONT_SIZE * 0.3)

    total_text_h = sum(line_heights) + line_gap * (len(lines) - 1)
    total_text_w = max(line_widths)

    # 반투명 박스
    box_w = total_text_w + BOX_PADDING * 2
    box_h = total_text_h + BOX_PADDING * 2
    box_x0 = (w - box_w) // 2
    box_y0 = (h - box_h) // 2
    box_x1 = box_x0 + box_w
    box_y1 = box_y0 + box_h

    overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    _draw_rounded_rect(draw, (box_x0, box_y0, box_x1, box_y1), BOX_RADIUS, BOX_COLOR)

    # 텍스트 렌더링 (중앙 정렬)
    y_cursor = box_y0 + BOX_PADDING
    for i, line in enumerate(lines):
        lw = line_widths[i]
        lh = line_heights[i]
        x = (w - lw) // 2
        draw.text((x, y_cursor), line, font=font, fill=TEXT_COLOR)
        y_cursor += lh + line_gap

    combined = Image.alpha_composite(bg, overlay).convert("RGB")

    tmp_path = OUTPUT_DIR / f"_tmp_frame_{index}.png"
    combined.save(tmp_path, "PNG")
    return tmp_path


def create_video(image_path: Path, index: int) -> Path:
    """FFmpeg으로 이미지 + BGM → 7초 MP4."""
    output_path = OUTPUT_DIR / f"output_{index}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(BGM_PATH),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(VIDEO_DURATION),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-shortest",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 오류 (영상 {index}):\n{result.stderr[-800:]}")

    # 임시 PNG 삭제
    image_path.unlink(missing_ok=True)
    return output_path


def build_video(overlay_text: str, index: int) -> Path:
    """이미지 합성 + 영상 생성을 한 번에 처리."""
    print(f"  [영상 {index:02d}] 이미지 합성 중...")
    img = compose_image(overlay_text, index)
    print(f"  [영상 {index:02d}] FFmpeg 인코딩 중...")
    video = create_video(img, index)
    print(f"  [영상 {index:02d}] 완료 → {video.name}")
    return video
