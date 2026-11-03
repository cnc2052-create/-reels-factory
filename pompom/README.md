# 폼폼 PomPom — 숏폼 어필리에이트 공장

올리브영·쿠팡 제휴 릴스를 5개 AI 계정으로 자동 생성·발행하는 시스템

## 수익 구조

```
[쿠팡/올리브영 제품] → [AI 스크립트 생성] → [릴스 발행] → [프로필 링크 클릭] → [구매] → [수수료]
```

## 5개 계정

| 계정 | 니치 | 제휴 플랫폼 | 발행 시간 |
|------|------|------------|---------|
| 💄 뷰티폼 | K-뷰티/스킨케어 | 올리브영+쿠팡 | 월·수·금·일 19:00 |
| 💪 헬스폼 | 건강/영양제 | 쿠팡 | 화·목·토 07:00 |
| 🏠 홈폼 | 살림/인테리어 | 쿠팡 | 월·수·금 11:00 |
| 👗 패션폼 | 가성비 패션 | 쿠팡+무신사 | 화·목·토·일 18:00 |
| 🍜 푸드폼 | 간편식/먹방 | 쿠팡+마켓컬리 | 월·수·금·일 20:00 |

## 실행 방법

```bash
# 환경변수 설정
cp ../.env.example ../.env
# ANTHROPIC_API_KEY, COUPANG_AFFILIATE_ID, BUFFER_* 등 입력

# 5개 계정 전체 콘텐츠 생성
python main.py generate

# 특정 계정만
python main.py generate --account pompom_beauty

# 생성된 콘텐츠 발행 (Buffer 스케줄)
python main.py publish

# 이번 주 발행 스케줄 확인
python main.py schedule

# 계정 현황
python main.py status
```

## 환경변수 추가 항목

```env
ANTHROPIC_API_KEY=sk-ant-...         # Claude AI (스크립트 생성)
COUPANG_AFFILIATE_ID=AF...           # 쿠팡 파트너스 ID
OLIVEYOUNG_AFFILIATE_ID=...          # 올리브영 제휴 코드

# Buffer 계정별 Profile ID
BUFFER_BEAUTY_ID=...
BUFFER_HEALTH_ID=...
BUFFER_HOME_ID=...
BUFFER_FASHION_ID=...
BUFFER_FOOD_ID=...
```

## 파일 구조

```
pompom/
├── config/
│   └── personas.json        # 5개 계정 페르소나 설정
├── modules/
│   ├── product_scout.py     # 제품 스카우팅 (쿠팡/올리브영)
│   ├── content_pipeline.py  # AI 스크립트+캡션 생성
│   └── multi_publisher.py   # 멀티계정 Buffer 발행
├── output/
│   └── generated_contents.json
└── main.py                  # CLI 진입점
```
