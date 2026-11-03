# -*- coding: utf-8 -*-
"""
폼폼 멀티 플랫폼 퍼블리셔
- Instagram: Meta Graph API (픽슬리 계정)
- TikTok: TikTok Content Posting API (오늘의독템)
- YouTube: YouTube Data API v3 (오늘의독템)
- Buffer: 예약 발행 (보조 / Instagram 전용)
"""
import os, json, time, requests
from datetime import datetime, timedelta
from pathlib import Path

# ── 환경변수 ──────────────────────────────────────────────
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN", "")

# Instagram (Meta Graph API)
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")         # 장기 토큰
IG_USER_ID = os.getenv("IG_USER_ID", "")                   # 픽슬리 계정 ID

# TikTok
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "") # TikTok Content Posting API
TIKTOK_OPEN_ID = os.getenv("TIKTOK_OPEN_ID", "")

# YouTube (OAuth2)
YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN", "")       # 오늘의독템 채널

# Buffer (보조)
BUFFER_BEAUTY_ID = os.getenv("BUFFER_BEAUTY_ID", "")
BUFFER_HEALTH_ID = os.getenv("BUFFER_HEALTH_ID", "")
BUFFER_HOME_ID = os.getenv("BUFFER_HOME_ID", "")
BUFFER_FASHION_ID = os.getenv("BUFFER_FASHION_ID", "")
BUFFER_FOOD_ID = os.getenv("BUFFER_FOOD_ID", "")

ACCOUNT_BUFFER_IDS = {
    "pompom_beauty": BUFFER_BEAUTY_ID,
    "pompom_health": BUFFER_HEALTH_ID,
    "pompom_home": BUFFER_HOME_ID,
    "pompom_fashion": BUFFER_FASHION_ID,
    "pompom_food": BUFFER_FOOD_ID,
}


# ═══════════════════════════════════════════════════════════
# 1. Instagram Reels 업로드 (Meta Graph API)
# ═══════════════════════════════════════════════════════════
def upload_instagram_reels(video_url: str, caption: str) -> dict:
    """
    Meta Graph API로 릴스 업로드
    video_url: 외부에서 접근 가능한 영상 URL (or 로컬 → 임시 서버 필요)
    """
    if not IG_ACCESS_TOKEN or not IG_USER_ID:
        return {"ok": False, "error": "IG_ACCESS_TOKEN 또는 IG_USER_ID 없음 — .env 확인"}

    try:
        # Step 1: 미디어 컨테이너 생성
        r1 = requests.post(
            f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
            params={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption[:2200],
                "access_token": IG_ACCESS_TOKEN,
            }, timeout=30,
        )
        container = r1.json()
        container_id = container.get("id")
        if not container_id:
            return {"ok": False, "error": f"컨테이너 생성 실패: {container}"}

        # Step 2: 업로드 완료 대기
        for _ in range(20):
            time.sleep(15)
            r_check = requests.get(
                f"https://graph.facebook.com/v19.0/{container_id}",
                params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
                timeout=10,
            )
            status = r_check.json().get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                return {"ok": False, "error": "업로드 처리 실패"}

        # Step 3: 게시
        r2 = requests.post(
            f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
            params={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
            timeout=30,
        )
        result = r2.json()
        media_id = result.get("id")
        print(f"[Instagram] 업로드 완료: {media_id}")
        return {"ok": bool(media_id), "media_id": media_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 2. TikTok 영상 업로드 (Content Posting API)
# ═══════════════════════════════════════════════════════════
def upload_tiktok(video_path: str, caption: str) -> dict:
    """TikTok Content Posting API — 파일 직접 업로드"""
    if not TIKTOK_ACCESS_TOKEN:
        return {"ok": False, "error": "TIKTOK_ACCESS_TOKEN 없음 — .env 확인"}

    try:
        fsize = Path(video_path).stat().st_size

        # Step 1: 업로드 초기화
        r1 = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={"Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}", "Content-Type": "application/json"},
            json={
                "post_info": {
                    "title": caption[:150],
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False, "disable_comment": False, "disable_stitch": False,
                },
                "source_info": {"source": "FILE_UPLOAD", "video_size": fsize, "chunk_size": fsize, "total_chunk_count": 1},
            }, timeout=30,
        )
        init_data = r1.json().get("data", {})
        upload_url = init_data.get("upload_url")
        publish_id = init_data.get("publish_id")
        if not upload_url:
            return {"ok": False, "error": f"TikTok init 실패: {r1.text[:200]}"}

        # Step 2: 파일 업로드
        with open(video_path, "rb") as vf:
            r2 = requests.put(
                upload_url,
                headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{fsize-1}/{fsize}"},
                data=vf, timeout=120,
            )
        if r2.status_code not in (200, 201):
            return {"ok": False, "error": f"TikTok 업로드 실패: {r2.status_code}"}

        print(f"[TikTok] 업로드 완료: {publish_id}")
        return {"ok": True, "publish_id": publish_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 3. YouTube Shorts 업로드 (Data API v3)
# ═══════════════════════════════════════════════════════════
def _refresh_yt_token() -> str:
    """YouTube OAuth2 액세스 토큰 갱신"""
    if not YT_REFRESH_TOKEN:
        return ""
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": YT_CLIENT_ID,
        "client_secret": YT_CLIENT_SECRET,
        "refresh_token": YT_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }, timeout=10)
    return r.json().get("access_token", "")


def upload_youtube_shorts(video_path: str, title: str, description: str, tags: list[str]) -> dict:
    """YouTube Shorts 업로드"""
    if not YT_REFRESH_TOKEN:
        return {"ok": False, "error": "YT_REFRESH_TOKEN 없음 — .env 확인"}

    access_token = _refresh_yt_token()
    if not access_token:
        return {"ok": False, "error": "YouTube 토큰 갱신 실패"}

    try:
        fsize = Path(video_path).stat().st_size

        # Resumable upload 초기화
        metadata = {
            "snippet": {
                "title": (title + " #Shorts")[:100],
                "description": description[:5000],
                "tags": tags[:30],
                "categoryId": "22",
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }
        r1 = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Upload-Content-Type": "video/mp4",
                "X-Upload-Content-Length": str(fsize),
            },
            json=metadata, timeout=30,
        )
        upload_url = r1.headers.get("Location")
        if not upload_url:
            return {"ok": False, "error": f"YouTube init 실패: {r1.text[:200]}"}

        # 파일 업로드
        with open(video_path, "rb") as vf:
            r2 = requests.put(
                upload_url,
                headers={"Content-Type": "video/mp4", "Content-Length": str(fsize)},
                data=vf, timeout=300,
            )
        result = r2.json()
        video_id = result.get("id")
        print(f"[YouTube] 업로드 완료: https://youtu.be/{video_id}")
        return {"ok": bool(video_id), "video_id": video_id, "url": f"https://youtu.be/{video_id}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 4. Buffer 예약 (인스타 보조 / video_url 방식)
# ═══════════════════════════════════════════════════════════
def schedule_post_buffer(account_id: str, caption: str, scheduled_at: datetime) -> dict:
    profile_id = ACCOUNT_BUFFER_IDS.get(account_id, "")
    if not profile_id or not BUFFER_ACCESS_TOKEN:
        return {"ok": False, "error": f"Buffer 미설정: {account_id}"}
    try:
        resp = requests.post(
            "https://api.bufferapp.com/1/updates/create.json",
            data={
                "profile_ids[]": profile_id,
                "text": caption,
                "scheduled_at": scheduled_at.isoformat(),
                "access_token": BUFFER_ACCESS_TOKEN,
            }, timeout=30,
        )
        result = resp.json()
        return {"ok": result.get("success", False), "buffer_id": result.get("id")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 5. 전체 멀티플랫폼 발행
# ═══════════════════════════════════════════════════════════
def publish_all_platforms(content: dict, account_id: str, persona: dict) -> dict:
    """Instagram + TikTok + YouTube 동시 업로드"""
    video_path = content.get("final_video_path") or content.get("raw_video_path", "")
    caption = content.get("caption", "")
    product = content.get("product", {})
    affiliate_url = product.get("affiliate_url", "")

    # 캡션에 제휴 링크 추가
    full_caption = f"{caption}\n\n🛒 구매링크: {affiliate_url}" if affiliate_url else caption

    title = f"{product.get('name','')} 솔직 리뷰 | {content.get('hook_name','')}"
    tags = ["쇼핑", "제품리뷰", "핫딜", "추천템", product.get("platform","쿠팡")]

    results = {}

    # Instagram
    if video_path:
        results["instagram"] = upload_instagram_reels(
            video_url="",  # 로컬 파일은 CDN URL 필요 — 운영 시 S3/Cloudflare 연동
            caption=full_caption,
        )
    else:
        results["instagram"] = {"ok": False, "error": "영상 없음"}

    # TikTok
    if video_path and Path(video_path).exists():
        results["tiktok"] = upload_tiktok(video_path, full_caption[:2200])
    else:
        results["tiktok"] = {"ok": False, "error": "영상 파일 없음"}

    # YouTube Shorts
    if video_path and Path(video_path).exists():
        results["youtube"] = upload_youtube_shorts(
            video_path, title, full_caption, tags
        )
    else:
        results["youtube"] = {"ok": False, "error": "영상 파일 없음"}

    # Buffer 예약 (보조)
    posting_time = persona.get("posting_time", "19:00")
    hour, minute = map(int, posting_time.split(":"))
    now = datetime.now()
    scheduled = now.replace(hour=hour, minute=minute, second=0)
    if scheduled <= now:
        scheduled += timedelta(days=1)
    results["buffer"] = schedule_post_buffer(account_id, full_caption, scheduled)

    # 결과 요약
    ok_count = sum(1 for r in results.values() if r.get("ok"))
    print(f"\n[발행 결과] {persona['name']}: {ok_count}/4 플랫폼 성공")
    for platform, r in results.items():
        status = "✅" if r.get("ok") else f"⚠️ {r.get('error','')[:40]}"
        print(f"  {platform}: {status}")

    return results


def publish_all_accounts(contents: dict, personas: list[dict]) -> list[dict]:
    results = []
    persona_map = {p.get("account_id", p.get("id", "")): p for p in personas}

    for account_id, content in contents.items():
        persona = persona_map.get(account_id)
        if not persona:
            continue
        platform_results = publish_all_platforms(content, account_id, persona)
        results.append({
            "account": account_id,
            "persona_name": persona["name"],
            "product": content.get("product", {}).get("name", ""),
            "scheduled_at": datetime.now().isoformat(),
            "platforms": platform_results,
            "buffer": platform_results.get("buffer", {}),
        })

    return results


def get_posting_schedule(personas: list[dict]) -> list[dict]:
    schedule = []
    today = datetime.now()
    days_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

    for persona in personas:
        posting_time = persona.get("posting_time", "19:00")
        posting_days = [days_map[d] for d in persona.get("posting_days", ["mon", "wed", "fri"])]
        for offset in range(7):
            target = today + timedelta(days=offset)
            if target.weekday() in posting_days:
                h, m = map(int, posting_time.split(":"))
                post_time = target.replace(hour=h, minute=m, second=0, microsecond=0)
                schedule.append({
                    "account": persona.get("account_id", persona.get("id", "")),
                    "name": persona["name"],
                    "datetime": post_time.isoformat(),
                    "niche": persona.get("niche", ""),
                })

    return sorted(schedule, key=lambda x: x["datetime"])
