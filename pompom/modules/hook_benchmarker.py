# -*- coding: utf-8 -*-
"""
폼폼 훅 벤치마커 — autam-video 스킬의 10가지 훅 구조를 어필리에이트 릴스에 적용
"""
import json, random
from typing import Optional

# ═══════════════════════════════════════════════════════════
# 10가지 훅 구조 (autam-video 스킬 기반, 어필리에이트 버전)
# ═══════════════════════════════════════════════════════════
HOOK_STRUCTURES = {
    1: {
        "name": "질문→반전→정답",
        "template": "{product} 효과 있나요? / 아닙니다 / {benefit}입니다",
        "pattern": "많이 물어보시는 / {question}? / 아닙니다 / {answer}입니다",
        "best_for": ["beauty", "health_fitness"],
        "cta_style": "댓글유도",
    },
    2: {
        "name": "착각→반전→정답",
        "template": "처음 보면 / 다들 속습니다 / {wrong} 같지만 / {right}입니다",
        "pattern": "처음 보면 / 다들 속습니다 / {wrong} 같지만 / {right}입니다",
        "best_for": ["fashion", "home_living"],
        "cta_style": "저장유도",
    },
    3: {
        "name": "의문→이유공개",
        "template": "왜 {target}들이 / 선택할까요? / {differentiator}이 / 다릅니다",
        "pattern": "왜 {target}들이 / 선택할까요? / {differentiator}이 / 다릅니다",
        "best_for": ["health_fitness", "beauty"],
        "cta_style": "클릭유도",
    },
    4: {
        "name": "충격→비밀공개",
        "template": "이게 / {product}이 아니라고? / {secret}의 / 비밀",
        "pattern": "이게 / {product}이 아니라고? / {secret}의 / 비밀",
        "best_for": ["beauty", "food"],
        "cta_style": "궁금증유발",
    },
    5: {
        "name": "체험→결론",
        "template": "실제로 써보면 / 더 놀랍니다 / 생각보다 / {result}합니다",
        "pattern": "실제로 써보면 / 더 놀랍니다 / 생각보다 / {result}합니다",
        "best_for": ["all"],
        "cta_style": "구매유도",
    },
    6: {
        "name": "문제→해결",
        "template": "{problem} 고민 / 끝 / 이것 하나면 / 해결됩니다",
        "pattern": "{problem} 고민 / 끝 / 이것 하나면 / 해결됩니다",
        "best_for": ["home_living", "beauty", "health_fitness"],
        "cta_style": "구매유도",
    },
    7: {
        "name": "비교→차이점",
        "template": "일반 {category}와 / 다릅니다 / 차이는 / {diff}입니다",
        "pattern": "일반 {category}와 / 다릅니다 / 차이는 / {diff}입니다",
        "best_for": ["beauty", "fashion", "health_fitness"],
        "cta_style": "클릭유도",
    },
    8: {
        "name": "권위→증명",
        "template": "{authority}도 / 선택한 이유 / 결국 / {reason} 때문입니다",
        "pattern": "{authority}도 / 선택한 이유 / 결국 / {reason} 때문입니다",
        "best_for": ["beauty", "health_fitness"],
        "cta_style": "신뢰구축",
    },
    9: {
        "name": "호기심→확인",
        "template": "사진으론 / 안 보입니다 / 직접 써보면 / 바로 압니다",
        "pattern": "사진으론 / 안 보입니다 / 직접 써보면 / 바로 압니다",
        "best_for": ["beauty", "home_living"],
        "cta_style": "클릭유도",
    },
    10: {
        "name": "숫자→비밀",
        "template": "{number}원의 / 비밀 / 왜 {product}은 / 다를까요?",
        "pattern": "{number}원의 / 비밀 / 왜 {product}은 / 다를까요?",
        "best_for": ["all"],
        "cta_style": "궁금증유발",
    },
}

# 카테고리별 훅 가중치 (성과 기반, 운영하면서 조정)
HOOK_WEIGHTS: dict[str, dict[int, float]] = {
    "beauty": {1: 0.25, 2: 0.10, 3: 0.15, 4: 0.15, 5: 0.10, 6: 0.10, 7: 0.08, 8: 0.05, 9: 0.01, 10: 0.01},
    "health_fitness": {1: 0.20, 2: 0.05, 3: 0.20, 4: 0.10, 5: 0.15, 6: 0.15, 7: 0.10, 8: 0.05, 9: 0.00, 10: 0.00},
    "home_living": {1: 0.10, 2: 0.15, 3: 0.10, 4: 0.08, 5: 0.15, 6: 0.25, 7: 0.10, 8: 0.02, 9: 0.05, 10: 0.00},
    "fashion": {1: 0.10, 2: 0.25, 3: 0.10, 4: 0.10, 5: 0.15, 6: 0.10, 7: 0.15, 8: 0.03, 9: 0.02, 10: 0.00},
    "food": {1: 0.15, 2: 0.10, 3: 0.10, 4: 0.20, 5: 0.20, 6: 0.10, 7: 0.05, 8: 0.02, 9: 0.03, 10: 0.05},
}


def select_hook(niche: str, product: dict, recent_hooks: Optional[list[int]] = None) -> dict:
    """가중치 기반 훅 선택 (최근 사용 제외)"""
    weights = HOOK_WEIGHTS.get(niche, {k: 0.1 for k in range(1, 11)})

    # 최근 3개 훅 가중치 감소
    if recent_hooks:
        weights = dict(weights)
        for h in recent_hooks[-3:]:
            if h in weights:
                weights[h] *= 0.2

    ids = list(weights.keys())
    wts = [weights[i] for i in ids]
    total = sum(wts)
    wts = [w / total for w in wts]

    chosen_id = random.choices(ids, weights=wts, k=1)[0]
    hook = dict(HOOK_STRUCTURES[chosen_id])
    hook["id"] = chosen_id

    return hook


def fill_hook_text(hook: dict, product: dict) -> str:
    """훅 템플릿에 제품 정보를 채워 썸네일 후킹문구 생성 (최대 4줄/한줄 10자)"""
    name = product.get("name", "")
    price = product.get("price", 0)
    angle = product.get("viral_angle", "솔직 리뷰")

    fills = {
        "product": name[:8],
        "benefit": angle[:8],
        "question": f"{name[:5]} 진짜 효과?",
        "answer": angle[:8],
        "wrong": "비싼 제품",
        "right": "가성비 최강",
        "target": "뷰티 고수",
        "differentiator": "성분",
        "secret": name[:5],
        "result": "만족",
        "problem": angle[:5],
        "category": name[:5],
        "diff": angle[:5],
        "authority": "10만 명",
        "reason": angle[:5],
        "number": f"{price:,}",
    }

    text = hook["pattern"]
    for k, v in fills.items():
        text = text.replace("{" + k + "}", str(v))

    # 4줄 / 한 줄 10자 이내 강제
    lines = [l.strip()[:10] for l in text.split("/") if l.strip()][:4]
    return "\n".join(lines)
