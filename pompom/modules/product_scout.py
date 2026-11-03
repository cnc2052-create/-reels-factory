# -*- coding: utf-8 -*-
"""
폼폼 제품 스카우터 — 쿠팡/올리브영 제휴 제품 탐색 및 링크 생성
"""
import os
import json
import random
from datetime import datetime
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", os.getenv("OPENAI_API_KEY", "")))

COUPANG_AFFILIATE_ID = os.getenv("COUPANG_AFFILIATE_ID", "")
OLIVEYOUNG_AFFILIATE_ID = os.getenv("OLIVEYOUNG_AFFILIATE_ID", "")


TRENDING_PRODUCTS = {
    "beauty": [
        {"name": "라운드랩 독도 토너", "category": "스킨케어", "price": 18000, "platform": "oliveyoung", "product_id": "A00000137526"},
        {"name": "메디힐 마스크팩 10매", "category": "마스크팩", "price": 12000, "platform": "oliveyoung", "product_id": "A00000009814"},
        {"name": "아누아 어성초 77 토너", "category": "스킨케어", "price": 21000, "platform": "oliveyoung", "product_id": "A00000237849"},
        {"name": "넘버즈인 1번 워터힐링 토너", "category": "스킨케어", "price": 19800, "platform": "coupang", "product_id": "7581234567"},
        {"name": "조선미녀 선크림 SPF50+", "category": "선크림", "price": 15000, "platform": "oliveyoung", "product_id": "A00000198234"},
    ],
    "health_fitness": [
        {"name": "뉴트리원 유산균 프로바이오틱스", "category": "유산균", "price": 29900, "platform": "coupang", "product_id": "7123456789"},
        {"name": "종근당건강 오메가3", "category": "오메가3", "price": 24900, "platform": "coupang", "product_id": "7234567890"},
        {"name": "나우푸드 비타민C 1000", "category": "비타민", "price": 19800, "platform": "coupang", "product_id": "7345678901"},
        {"name": "헬스위 단백질바 12개입", "category": "단백질", "price": 22000, "platform": "coupang", "product_id": "7456789012"},
    ],
    "home_living": [
        {"name": "락앤락 유리밀폐용기 세트", "category": "주방용품", "price": 35000, "platform": "coupang", "product_id": "7567890123"},
        {"name": "다이슨 에어랩 컴플리트", "category": "미용기기", "price": 649000, "platform": "coupang", "product_id": "7678901234"},
        {"name": "테팔 인덕션 프라이팬", "category": "주방용품", "price": 45000, "platform": "coupang", "product_id": "7789012345"},
        {"name": "에코버 친환경 세제 세트", "category": "청소용품", "price": 28000, "platform": "coupang", "product_id": "7890123456"},
    ],
    "fashion": [
        {"name": "무신사 스탠다드 맨투맨", "category": "의류", "price": 29000, "platform": "coupang", "product_id": "7901234567"},
        {"name": "나이키 에어포스 1", "category": "신발", "price": 119000, "platform": "coupang", "product_id": "7012345678"},
        {"name": "COS 오버핏 셔츠", "category": "의류", "price": 59000, "platform": "coupang", "product_id": "7123456780"},
    ],
    "food": [
        {"name": "CJ 비비고 왕교자 1kg", "category": "냉동식품", "price": 12900, "platform": "coupang", "product_id": "7234567891"},
        {"name": "오뚜기 3분카레 10개입", "category": "간편식", "price": 9800, "platform": "coupang", "product_id": "7345678902"},
        {"name": "풀무원 생면식감 짜파게티", "category": "라면", "price": 8500, "platform": "coupang", "product_id": "7456789013"},
        {"name": "곰곰 스팸 6캔 세트", "category": "통조림", "price": 25000, "platform": "coupang", "product_id": "7567890124"},
    ],
}


def build_affiliate_url(platform: str, product_id: str) -> str:
    if platform == "coupang" and COUPANG_AFFILIATE_ID:
        return f"https://link.coupang.com/a/{COUPANG_AFFILIATE_ID}?itemId={product_id}"
    elif platform == "oliveyoung" and OLIVEYOUNG_AFFILIATE_ID:
        return f"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo={product_id}&afCode={OLIVEYOUNG_AFFILIATE_ID}"
    elif platform == "coupang":
        return f"https://www.coupang.com/vp/products/{product_id}"
    elif platform == "oliveyoung":
        return f"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo={product_id}"
    return ""


def get_trending_products(niche: str, count: int = 3) -> list[dict]:
    products = TRENDING_PRODUCTS.get(niche, [])
    selected = random.sample(products, min(count, len(products)))
    for p in selected:
        p["affiliate_url"] = build_affiliate_url(p["platform"], p["product_id"])
    return selected


def scout_products_with_ai(niche: str, persona: dict) -> list[dict]:
    products = get_trending_products(niche, 3)

    prompt = f"""당신은 {persona['display_name']} 계정의 제품 큐레이터입니다.

페르소나: {persona['personality']}
타겟: {persona['target_audience']}
카테고리: {', '.join(persona['product_categories'])}

다음 제품들 중 이번 주 릴스에 적합한 제품 1개를 선택하고, 선택 이유와 콘텐츠 각도를 제안하세요:

{json.dumps(products, ensure_ascii=False, indent=2)}

JSON 형식으로 응답:
{{
  "selected_product": <제품명>,
  "reason": <선택 이유 1줄>,
  "content_angle": <콘텐츠 접근 방식 1줄>,
  "hook_idea": <첫 3초 훅 아이디어>
}}"""

    try:
        from anthropic import Anthropic as AnthropicClient
        ai_client = AnthropicClient(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        response = ai_client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text
        start = content.find("{")
        end = content.rfind("}") + 1
        suggestion = json.loads(content[start:end])

        for p in products:
            if p["name"] in suggestion.get("selected_product", ""):
                p.update({
                    "content_angle": suggestion.get("content_angle", ""),
                    "hook_idea": suggestion.get("hook_idea", ""),
                    "ai_selected": True,
                })
                return [p]
    except Exception:
        pass

    products[0]["ai_selected"] = False
    return [products[0]]
