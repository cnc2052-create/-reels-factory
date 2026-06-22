# -*- coding: utf-8 -*-
"""
buffer_publisher.py — Multi-platform Buffer 예약 발행
Instagram Reels + TikTok + YouTube Shorts 동시 지원
"""
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN", "")

BUFFER_UPDATE_URL = "https://api.bufferapp.com/1/updates/create.json"
BUFFER_UPLOAD_URL = "https://api.bufferapp.com/1/media/upload.json"

PLATFORM_LABEL = {
    "instagram": "Instagram Reels",
    "tiktok":    "TikTok",
    "youtube":   "YouTube Shorts",
}

KST = timezone(timedelta(hours=9))


def _kst_to_utc_ts(date: datetime, time_str: str) -> int:
    """KST 날짜 + 'HH:MM' 문자열 → UTC Unix timestamp"""
    h, m    = map(int, time_str.split(":"))
    kst_dt  = date.replace(hour=h, minute=m, second=0, microsecond=0, tzinfo=KST)
    return int(kst_dt.timestamp())


def _schedule_times(day_offset: int, times_kst: list) -> list[int]:
    """
    day_offset=1 → 내일부터.
    times_kst = ['09:00','14:00','19:00'] 형태.
    반환: UTC Unix timestamp 리스트.
    """
    base = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    base += timedelta(days=day_offset)
    return [_kst_to_utc_ts(base, t) for t in times_kst]


def _upload_video(video_path: Path) -> str:
    """Buffer 미디어 업로드 → media_id 반환"""
    with open(video_path, "rb") as f:
        resp = requests.post(
            BUFFER_UPLOAD_URL,
            data={"access_token": ACCESS_TOKEN},
            files={"file": (video_path.name, f, "video/mp4")},
            timeout=120,
        )
    resp.raise_for_status()
    data     = resp.json()
    media_id = data.get("id") or data.get("media_id")
    if not media_id:
        raise ValueError(f"미디어 업로드 실패: {data}")
    return str(media_id)


def schedule_post(
    video_path: Path,
    caption: str,
    profile_id: str,
    scheduled_at: int,
) -> dict:
    """단일 profile_id에 영상+캡션 예약"""
    if not ACCESS_TOKEN:
        raise EnvironmentError(".env에 BUFFER_ACCESS_TOKEN이 없습니다.")
    if not profile_id:
        raise ValueError("profile_id가 비어 있습니다.")

    media_id = _upload_video(video_path)

    payload = {
        "access_token":  ACCESS_TOKEN,
        "profile_ids[]": profile_id,
        "text":          caption,
        "media[video]":  media_id,
        "scheduled_at":  scheduled_at,
        "shorten":       "false",
    }
    resp = requests.post(BUFFER_UPDATE_URL, data=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def publish_all(
    content_list: list[dict],
    video_paths:  list[Path],
    caption_dir:  Path,
    channel:      dict,
    platforms:    list[str],
    times_kst:    list[str],
    on_progress=None,
) -> list[dict]:
    """
    전체 콘텐츠를 선택된 플랫폼 × 선택된 채널로 일괄 예약.

    - channel: channels.json의 단일 채널 dict
    - platforms: ['instagram','tiktok','youtube'] 중 선택된 것
    - times_kst: ['09:00','14:00','19:00'] — 하루 N개 게시 시각 (KST)
    - on_progress(record): 진행 상황 콜백 (선택)
    """
    results = []
    total   = len(content_list)

    for idx, (content, video_path) in enumerate(zip(content_list, video_paths), start=1):
        # 캡션: 저장 파일 우선
        cap_file = caption_dir / f"post_{idx}.txt"
        caption  = cap_file.read_text(encoding="utf-8").strip() if cap_file.exists() \
                   else content.get("instagram_caption", "")

        # 예약 시각 결정 (day_offset = 몇 번째 콘텐츠인지 기준)
        # times_kst가 3개면 3일에 걸쳐 하루 1개씩 → 또는 하루에 3개
        # 여기서는 "하루에 N개" 방식: day=ceil(idx/len(times)), slot=idx%len(times)
        n_times     = len(times_kst) if times_kst else 1
        day_offset  = ((idx - 1) // n_times) + 1
        slot_index  = (idx - 1) % n_times
        slot_time   = times_kst[slot_index] if times_kst else "09:00"
        scheduled_ts = _schedule_times(day_offset, [slot_time])[0]

        scheduled_str = datetime.fromtimestamp(scheduled_ts, tz=KST).strftime("%m/%d %H:%M KST")
        item_result   = {"index": idx, "theme": content.get("theme", ""), "platforms": {}}

        for platform in platforms:
            pinfo      = channel.get("platforms", {}).get(platform, {})
            profile_id = pinfo.get("profile_id", "")
            label      = PLATFORM_LABEL.get(platform, platform)

            if not profile_id:
                item_result["platforms"][platform] = {
                    "status": "skip", "message": f"{label} profile_id 미설정"
                }
                continue

            try:
                resp = schedule_post(video_path, caption, profile_id, scheduled_ts)
                update_id = (resp.get("updates") or [{}])[0].get("id", "N/A")
                item_result["platforms"][platform] = {
                    "status":    "success",
                    "update_id": update_id,
                    "scheduled": scheduled_str,
                }
                print(f"  [{idx:02d}] {label} 예약 완료 → {scheduled_str}")
            except Exception as e:
                # 플랫폼 실패해도 다음 플랫폼 계속 진행
                item_result["platforms"][platform] = {
                    "status": "error", "message": str(e)
                }
                print(f"  [{idx:02d}] {label} 오류: {e}")

        results.append(item_result)
        if on_progress:
            on_progress(item_result)

    # 결과 저장
    result_path = video_paths[0].parent.parent / "publish_results.json" if video_paths else Path("publish_results.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results
