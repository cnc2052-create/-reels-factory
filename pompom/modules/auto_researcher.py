# -*- coding: utf-8 -*-
"""
폼폼 자동 제품 리서치 — 쿠팡/올리브영 베스트셀러 스캔 + AI 점수화
"""
import os, json, random
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# 카테고리별 베스트셀러 시드 (실제 운영 시 쿠팡 API/크롤링으로 교체)
BESTSELLERS = {
    "beauty": [
        {"name":"라운드랩 독도 토너 300ml","price":18000,"reviews":42000,"rating":4.8,"platform":"oliveyoung","url":"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A00000137526","commission_pct":3},
        {"name":"조선미녀 선크림 SPF50+ PA++++","price":15000,"reviews":38000,"rating":4.7,"platform":"oliveyoung","url":"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A00000198234","commission_pct":3},
        {"name":"아누아 어성초 77 토너 500ml","price":21000,"reviews":55000,"rating":4.9,"platform":"oliveyoung","url":"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A00000237849","commission_pct":3},
        {"name":"메디힐 마스크팩 10매","price":12000,"reviews":120000,"rating":4.6,"platform":"oliveyoung","url":"https://www.oliveyoung.co.kr/store/goods/getGoodsDetail.do?goodsNo=A00000009814","commission_pct":3},
        {"name":"닥터자르트 시카페어 크림","price":34000,"reviews":29000,"rating":4.8,"platform":"coupang","url":"https://www.coupang.com/vp/products/7111111111","commission_pct":3},
    ],
    "health_fitness": [
        {"name":"뉴트리원 유산균 60캡슐","price":29900,"reviews":85000,"rating":4.7,"platform":"coupang","url":"https://www.coupang.com/vp/products/7200000001","commission_pct":3},
        {"name":"종근당건강 오메가3 60캡슐","price":24900,"reviews":67000,"rating":4.6,"platform":"coupang","url":"https://www.coupang.com/vp/products/7200000002","commission_pct":3},
        {"name":"나우푸드 비타민C 1000mg 100정","price":19800,"reviews":44000,"rating":4.8,"platform":"coupang","url":"https://www.coupang.com/vp/products/7200000003","commission_pct":4},
        {"name":"헬스위 단백질바 초콜릿 12개","price":22000,"reviews":31000,"rating":4.5,"platform":"coupang","url":"https://www.coupang.com/vp/products/7200000004","commission_pct":3},
        {"name":"GNC 비타민D 1000IU 180정","price":17900,"reviews":28000,"rating":4.7,"platform":"coupang","url":"https://www.coupang.com/vp/products/7200000005","commission_pct":4},
    ],
    "home_living": [
        {"name":"락앤락 유리밀폐용기 6P 세트","price":35000,"reviews":92000,"rating":4.8,"platform":"coupang","url":"https://www.coupang.com/vp/products/7300000001","commission_pct":3},
        {"name":"테팔 인덕션 프라이팬 28cm","price":45000,"reviews":56000,"rating":4.7,"platform":"coupang","url":"https://www.coupang.com/vp/products/7300000002","commission_pct":3},
        {"name":"3M 스카치브라이트 수세미 10P","price":8900,"reviews":180000,"rating":4.9,"platform":"coupang","url":"https://www.coupang.com/vp/products/7300000003","commission_pct":3},
        {"name":"에코버 주방세제 500ml","price":12500,"reviews":38000,"rating":4.6,"platform":"coupang","url":"https://www.coupang.com/vp/products/7300000004","commission_pct":3},
        {"name":"이케아 365+ 유리용기 세트","price":29900,"reviews":24000,"rating":4.7,"platform":"coupang","url":"https://www.coupang.com/vp/products/7300000005","commission_pct":3},
    ],
    "fashion": [
        {"name":"무신사 스탠다드 오버핏 맨투맨","price":29000,"reviews":74000,"rating":4.7,"platform":"coupang","url":"https://www.coupang.com/vp/products/7400000001","commission_pct":3},
        {"name":"나이키 에어포스 1 화이트","price":119000,"reviews":88000,"rating":4.8,"platform":"coupang","url":"https://www.coupang.com/vp/products/7400000002","commission_pct":2},
        {"name":"유니클로 에어리즘 반팔 티셔츠","price":19900,"reviews":120000,"rating":4.6,"platform":"coupang","url":"https://www.coupang.com/vp/products/7400000003","commission_pct":3},
        {"name":"아디다스 트레포일 후드티","price":79000,"reviews":42000,"rating":4.7,"platform":"coupang","url":"https://www.coupang.com/vp/products/7400000004","commission_pct":3},
    ],
    "food": [
        {"name":"CJ 비비고 왕교자 1.05kg","price":12900,"reviews":250000,"rating":4.9,"platform":"coupang","url":"https://www.coupang.com/vp/products/7500000001","commission_pct":2},
        {"name":"오뚜기 3분카레 중간맛 10개입","price":9800,"reviews":180000,"rating":4.8,"platform":"coupang","url":"https://www.coupang.com/vp/products/7500000002","commission_pct":2},
        {"name":"풀무원 생면식감 짜파게티 4인","price":8500,"reviews":95000,"rating":4.7,"platform":"coupang","url":"https://www.coupang.com/vp/products/7500000003","commission_pct":2},
        {"name":"곰곰 스팸클래식 200g 6캔","price":24900,"reviews":110000,"rating":4.8,"platform":"coupang","url":"https://www.coupang.com/vp/products/7500000004","commission_pct":2},
    ],
}

# 최근 사용 이력 (중복 방지)
_used_products: dict[str, list[str]] = {}


def _score_product(p: dict) -> float:
    """리뷰수·평점·수수료율 가중 점수"""
    review_score = min(p["reviews"] / 100000, 1.0) * 40
    rating_score = (p["rating"] - 4.0) / 1.0 * 30
    commission_score = p["commission_pct"] / 5 * 30
    return review_score + rating_score + commission_score


def research_top_product(niche: str, persona: dict, exclude_recent: int = 3) -> dict:
    """카테고리 베스트셀러 중 AI가 최적 제품 선정"""
    candidates = BESTSELLERS.get(niche, [])
    if not candidates:
        return {}

    # 최근 사용 제품 제외
    used = _used_products.get(niche, [])
    fresh = [p for p in candidates if p["name"] not in used[-exclude_recent:]]
    if not fresh:
        fresh = candidates

    # 점수 기반 TOP 3
    scored = sorted(fresh, key=_score_product, reverse=True)[:3]

    # Claude에게 페르소나 맞춤 최종 선택 위임
    prompt = f"""폼폼 {persona['name']} 계정 ({persona['personality'][:40]})에 가장 적합한 제품 1개를 선택하세요.

후보:
{json.dumps(scored, ensure_ascii=False, indent=2)}

JSON으로만 응답:
{{"selected_index": 0, "reason": "한 줄 이유", "viral_angle": "바이럴 각도"}}"""

    try:
        r = client.messages.create(
            model="claude-haiku-5-5", max_tokens=200,
            messages=[{"role":"user","content":prompt}]
        )
        txt = r.content[0].text
        data = json.loads(txt[txt.find("{"):txt.rfind("}")+1])
        product = scored[data.get("selected_index", 0)]
        product["viral_angle"] = data.get("viral_angle", "")
    except Exception:
        product = scored[0]
        product["viral_angle"] = "솔직 리뷰"

    # 제휴 URL 조립
    aff_id = os.getenv("COUPANG_AFFILIATE_ID", "")
    oly_id = os.getenv("OLIVEYOUNG_AFFILIATE_ID", "")
    if product["platform"] == "coupang" and aff_id:
        product["affiliate_url"] = f"https://link.coupang.com/a/{aff_id}?url={product['url']}"
    elif product["platform"] == "oliveyoung" and oly_id:
        product["affiliate_url"] = product["url"] + f"&afCode={oly_id}"
    else:
        product["affiliate_url"] = product["url"]

    # 사용 이력 기록
    _used_products.setdefault(niche, []).append(product["name"])

    return product
