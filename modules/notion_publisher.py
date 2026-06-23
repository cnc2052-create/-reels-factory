# -*- coding: utf-8 -*-
import os
import requests

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DB_ID = os.getenv("NOTION_DB_ID", "")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


def save_to_notion(
    title: str,
    channel: str,
    category: str,
    video_filename: str,
    caption: str,
    hashtags: str,
    platforms: list[str] | None = None,
) -> dict:
    if not NOTION_TOKEN or not NOTION_DB_ID:
        return {"ok": False, "error": "NOTION_TOKEN 또는 NOTION_DB_ID 미설정"}

    if platforms is None:
        platforms = ["Instagram"]

    platform_options = [{"name": p} for p in platforms]

    # 캡션과 해시태그 분리 (해시태그가 캡션 안에 포함된 경우)
    caption_text = caption
    hashtag_text = hashtags

    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "콘텐츠 제목": {"title": [{"text": {"content": title}}]},
            "채널": {"select": {"name": channel}},
            "카테고리": {"rich_text": [{"text": {"content": category}}]},
            "영상 파일명": {"rich_text": [{"text": {"content": video_filename}}]},
            "인스타 캡션": {"rich_text": [{"text": {"content": caption_text}}]},
            "해시태그": {"rich_text": [{"text": {"content": hashtag_text}}]},
            "플랫폼": {"multi_select": platform_options},
            "상태": {"select": {"name": "영상완료"}},
        },
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )

    if resp.status_code == 200:
        return {"ok": True, "url": resp.json().get("url", "")}
    else:
        return {"ok": False, "error": resp.text}


def update_status(page_id: str, status: str) -> bool:
    payload = {
        "properties": {
            "상태": {"select": {"name": status}}
        }
    }
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    return resp.status_code == 200
