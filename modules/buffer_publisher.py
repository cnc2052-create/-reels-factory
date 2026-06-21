"""
buffer_publisher.py
Buffer API v1을 통해 영상 + 캡션을 인스타그램에 예약 발행한다.
- 내일부터 하루 1개씩, 지정 시각(UTC)에 순차 예약
"""
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN    = os.getenv("BUFFER_ACCESS_TOKEN", "")
PROFILE_ID      = os.getenv("BUFFER_PROFILE_ID", "")
PUBLISH_HOUR    = int(os.getenv("PUBLISH_HOUR_UTC", "23"))
PUBLISH_MINUTE  = int(os.getenv("PUBLISH_MINUTE_UTC", "0"))

BUFFER_UPLOAD_URL   = "https://api.bufferapp.com/1/media/upload.json"
BUFFER_UPDATE_URL   = "https://api.bufferapp.com/1/updates/create.json"


def _scheduled_at(day_offset: int) -> int:
    """내일(day_offset=1)부터 offset일 뒤 지정 UTC 시각의 Unix 타임스탬프를 반환."""
    now_utc = datetime.now(timezone.utc)
    target = now_utc.replace(hour=PUBLISH_HOUR, minute=PUBLISH_MINUTE, second=0, microsecond=0)
    target += timedelta(days=day_offset)
    # 이미 오늘 지정 시각이 지났으면 하루 추가
    if day_offset == 0 and target <= now_utc:
        target += timedelta(days=1)
    return int(target.timestamp())


def _upload_video(video_path: Path) -> str:
    """Buffer 미디어 업로드 → media_id 반환."""
    with open(video_path, "rb") as f:
        resp = requests.post(
            BUFFER_UPLOAD_URL,
            data={"access_token": ACCESS_TOKEN},
            files={"file": (video_path.name, f, "video/mp4")},
            timeout=120,
        )
    resp.raise_for_status()
    data = resp.json()
    media_id = data.get("id") or data.get("media_id")
    if not media_id:
        raise ValueError(f"미디어 업로드 실패: {data}")
    return str(media_id)


def schedule_post(video_path: Path, caption: str, day_offset: int) -> dict:
    """
    Buffer에 예약 포스트를 생성한다.
    day_offset=1 → 내일, 2 → 모레, ...
    """
    if not ACCESS_TOKEN or not PROFILE_ID:
        raise EnvironmentError(".env 에 BUFFER_ACCESS_TOKEN / BUFFER_PROFILE_ID 가 설정되지 않았습니다.")

    print(f"    미디어 업로드 중: {video_path.name}")
    media_id = _upload_video(video_path)

    scheduled_ts = _scheduled_at(day_offset)
    scheduled_dt = datetime.fromtimestamp(scheduled_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    payload = {
        "access_token": ACCESS_TOKEN,
        "profile_ids[]": PROFILE_ID,
        "text": caption,
        "media[video]": media_id,
        "scheduled_at": scheduled_ts,
        "shorten": "false",
    }

    resp = requests.post(BUFFER_UPDATE_URL, data=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    print(f"    예약 완료 → {scheduled_dt} | update_id: {result.get('updates', [{}])[0].get('id', 'N/A')}")
    return result


def publish_all(content_list: list[dict], video_paths: list[Path]):
    """20개 콘텐츠를 내일부터 하루 1개씩 순차 예약한다."""
    print("\n=== Buffer 예약 발행 시작 ===")
    results = []
    for i, (content, video_path) in enumerate(zip(content_list, video_paths), start=1):
        day_offset = i  # 내일=1, 모레=2, ...
        print(f"\n[{i:02d}/20] {content['theme']}")
        try:
            r = schedule_post(video_path, content["instagram_caption"], day_offset)
            results.append({"index": i, "status": "success", "data": r})
        except Exception as e:
            print(f"    !! 오류 발생: {e}")
            results.append({"index": i, "status": "error", "error": str(e)})

    # 결과 저장
    result_path = Path(__file__).resolve().parent.parent / "output" / "publish_results.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장 완료 → {result_path}")
    return results
