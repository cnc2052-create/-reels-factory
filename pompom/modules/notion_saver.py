# -*- coding: utf-8 -*-
"""
폼폼 → 노션 자동 저장
DB ID: 49c2fe44642647758fc07be27b96ccaa (릴스 콘텐츠 관리)
"""
import os, requests
from datetime import datetime, timezone, timedelta

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DB_ID = os.getenv("NOTION_DB_ID", "49c2fe44642647758fc07be27b96ccaa")
KST = timezone(timedelta(hours=9))

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

ACCOUNT_MAP = {
    "pompom_beauty": "💄 뷰티폼",
    "pompom_health": "💪 헬스폼",
    "pompom_home": "🏠 홈폼",
    "pompom_fashion": "👗 패션폼",
    "pompom_food": "🍜 푸드폼",
}


def save_to_notion(script_data: dict, account_id: str, buffer_post_id: str = "") -> str:
    """생성된 스크립트를 노션 DB에 저장, 노션 페이지 ID 반환"""
    if not NOTION_TOKEN:
        print("[Notion] TOKEN 없음 — 저장 건너뜀")
        return ""

    now_kst = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S")
    today = datetime.now(KST).strftime("%Y%m%d")
    product = script_data.get("product", {})
    hook_name = script_data.get("hook_name", "")
    account_label = ACCOUNT_MAP.get(account_id, account_id)

    title = f"{today}_{account_label}_{product.get('name','')[:15]}_{hook_name}"

    caption_full = script_data.get("caption", "")
    caption_lines = caption_full[:2000]  # Notion 텍스트 한도

    scenes_text = "\n".join(
        f"[{s['sec']}] {s['action']} | 자막: {s['caption']}"
        for s in script_data.get("scenes", [])
    )
    narration_text = "\n".join(script_data.get("narration", []))

    body = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": title}}]},
            "계정": {"select": {"name": account_label}},
            "제품명": {"rich_text": [{"text": {"content": product.get("name", "")}}]},
            "가격": {"number": product.get("price", 0)},
            "플랫폼": {"select": {"name": product.get("platform", "coupang")}},
            "제휴URL": {"url": product.get("affiliate_url", "")},
            "훅구조": {"select": {"name": f"{script_data.get('hook_id',1)}번 {hook_name}"}},
            "상태": {"select": {"name": "스크립트완료"}},
            "생성일": {"date": {"start": now_kst}},
            "Buffer포스트ID": {"rich_text": [{"text": {"content": buffer_post_id}}]},
        },
        "children": [
            {
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "📝 나레이션"}}]}
            },
            {
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": narration_text}}]}
            },
            {
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "🎬 장면 구성"}}]}
            },
            {
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": scenes_text}}]}
            },
            {
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "📸 인스타 캡션"}}]}
            },
            {
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": caption_lines}}]}
            },
            {
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "🤖 Higgsfield 프롬프트"}}]}
            },
            {
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": script_data.get("higgsfield_prompt","")}}]}
            },
        ]
    }

    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=body)
    if r.status_code == 200:
        page_id = r.json().get("id", "")
        print(f"[Notion] 저장 완료: {title} ({page_id})")
        return page_id
    else:
        print(f"[Notion] 저장 실패 {r.status_code}: {r.text[:200]}")
        return ""
