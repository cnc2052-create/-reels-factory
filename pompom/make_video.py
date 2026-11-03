# -*- coding: utf-8 -*-
"""
FFmpeg로 릴스 영상 생성 — 외부 API 없이 로컬에서 완전 생성
- 9:16 세로형 (1080x1920)
- 그라데이션 배경 + 한글 자막 (SRT 파일 방식)
- BGM 추가 (assets/ 폴더 mp3 있으면 자동 적용)
"""
import subprocess, json, os, sys, tempfile
from pathlib import Path

FONT_PATH = "C:/Windows/Fonts/malgun.ttf"
OUTPUT_DIR = Path(__file__).parent / "output"
ASSETS_DIR = Path(__file__).parent.parent / "assets"


def _write_srt(captions: list, duration: int, srt_path: str):
    """한글 자막을 SRT 파일로 저장"""
    seg = duration / max(len(captions), 1)
    lines = []
    for i, cap in enumerate(captions):
        t_start = i * seg
        t_end = t_start + seg - 0.3
        def fmt(sec):
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            ms = int((sec - int(sec)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        lines.append(f"{i+1}")
        lines.append(f"{fmt(t_start)} --> {fmt(t_end)}")
        lines.append(cap)
        lines.append("")
    with open(srt_path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))


def make_reel(script: dict, output_path: str, duration: int = 20) -> bool:
    captions = script.get("remotion_captions", [])
    product_name = script.get("product", {}).get("name", "추천템")

    out_dir = "C:/pompom_out"
    os.makedirs(out_dir, exist_ok=True)

    # SRT 자막 파일 생성
    srt_path = f"{out_dir}/captions.srt"
    all_captions = list(captions)
    if product_name:
        all_captions.append(f"👉 {product_name[:15]}")
    _write_srt(all_captions, duration, srt_path)

    # BGM 찾기
    bgm = ""
    if ASSETS_DIR.exists():
        mp3s = list(ASSETS_DIR.glob("*.mp3"))
        if mp3s:
            import random
            bgm = str(random.choice(mp3s)).replace("\\", "/")

    # subtitles 필터 — 한글 폰트 지정
    # force_style로 폰트, 크기, 색상 제어
    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
    font_escaped = FONT_PATH.replace("\\", "/").replace(":", "\\:")
    sub_filter = (
        f"subtitles='{srt_escaped}'"
        f":fontsdir='C\\:/Windows/Fonts'"
        f":force_style='FontName=Malgun Gothic,FontSize=22,"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        f"BackColour=&H80000000,Bold=1,Outline=2,Shadow=1,"
        f"Alignment=2,MarginV=80'"
    )

    vf = sub_filter

    # FFmpeg 명령 조립
    if bgm:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0xFF6B9D:s=1080x1920:r=30:d={duration}",
            "-i", bgm,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0xFF6B9D:s=1080x1920:r=30:d={duration}",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            output_path,
        ]

    print(f"[FFmpeg] 영상 생성 중... ({duration}초)")
    result = subprocess.run(cmd, capture_output=True, timeout=120)

    if result.returncode == 0:
        size_mb = Path(output_path).stat().st_size / 1024 / 1024
        print(f"[FFmpeg] done: {output_path} ({size_mb:.1f}MB)")
        return True
    else:
        err = (result.stderr or b"").decode("utf-8", errors="ignore")
        print(f"[FFmpeg] SRT 방식 실패, 자막 없이 재시도...")
        print(f"[FFmpeg] error: {err[-300:]}")
        # 폴백: 자막 없이 순수 배경 영상만
        return _make_plain_reel(output_path, duration, bgm)


def _make_plain_reel(output_path: str, duration: int, bgm: str = "") -> bool:
    """자막 없는 순수 배경 영상 (최후 폴백)"""
    if bgm:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0xFF6B9D:s=1080x1920:r=30:d={duration}",
            "-i", bgm,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-pix_fmt", "yuv420p",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0xFF6B9D:s=1080x1920:r=30:d={duration}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-t", str(duration),
            output_path,
        ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode == 0:
        size_mb = Path(output_path).stat().st_size / 1024 / 1024
        print(f"[FFmpeg] 폴백 완료: {output_path} ({size_mb:.1f}MB)")
        return True
    err = (result.stderr or b"").decode("utf-8", errors="ignore")
    print(f"[FFmpeg] 폴백도 실패: {err[-200:]}")
    return False


def make_reel_from_image(image_path: str, script: dict, output_path: str, duration: int = 20) -> bool:
    """사진 1장을 배경으로 릴스 영상 생성"""
    captions = script.get("remotion_captions", [])
    product_name = script.get("product", {}).get("name", "추천템")

    out_dir = "C:/pompom_out"
    os.makedirs(out_dir, exist_ok=True)

    srt_path = f"{out_dir}/manual_captions.srt"
    all_captions = list(captions)
    if product_name:
        all_captions.append(f"👉 {product_name[:15]}")
    _write_srt(all_captions, duration, srt_path)

    img_escaped = image_path.replace("\\", "/")
    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
    sub_filter = (
        f"subtitles='{srt_escaped}'"
        f":fontsdir='C\\:/Windows/Fonts'"
        f":force_style='FontName=Malgun Gothic,FontSize=22,"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        f"BackColour=&H80000000,Bold=1,Outline=2,Shadow=1,"
        f"Alignment=2,MarginV=80'"
    )
    # 이미지를 9:16으로 크롭/패드 후 자막 오버레이
    vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{sub_filter}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_escaped,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode == 0:
        print(f"[FFmpeg] 이미지→영상 완료: {output_path}")
        return True
    err = (result.stderr or b"").decode("utf-8", errors="ignore")
    print(f"[FFmpeg] 이미지→영상 실패: {err[-200:]}")
    return False


if __name__ == "__main__":
    script_path = OUTPUT_DIR / "test_script.json"
    if not script_path.exists():
        print("먼저 스크립트를 생성하세요")
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    out_dir = "C:/pompom_out"
    os.makedirs(out_dir, exist_ok=True)
    output = f"{out_dir}/test_reel.mp4"
    ok = make_reel(script, output, duration=20)
    if ok:
        print(f"영상 완성: {output}")
