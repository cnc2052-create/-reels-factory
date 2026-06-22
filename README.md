# 숏폼 자동화 시스템 — Reels Factory

인스타그램 릴스용 카드뉴스를 GPT-4o로 기획하고, Pillow로 인포그래픽 이미지를 합성하여, FFmpeg으로 영상을 만든 뒤 Buffer로 예약 발행하는 자동화 시스템입니다.

---

## ⚠️ 중요: 반드시 Flask 서버로 실행하세요

`templates/index.html` 파일을 브라우저에서 **직접 열면 작동하지 않습니다.**  
Jinja2 템플릿 문법(`{{ }}`, `{% %}`)은 Flask 서버가 처리해야 정상 렌더링됩니다.

---

## 실행 방법

```bash
# 1. 가상환경 활성화 (처음 한 번만 생성)
python -m venv venv
venv\Scripts\activate

# 2. 패키지 설치 (처음 한 번만)
pip install flask openai pillow python-dotenv

# 3. 서버 실행
python app.py

# 4. 브라우저 접속
http://127.0.0.1:5000
```

---

## 사용 흐름

```
STEP 1  콘텐츠 기획  →  GPT-4o가 20개 카드뉴스 주제 + 내용 생성
STEP 2  이미지 검수  →  인포그래픽 카드 이미지 생성 후 썸네일로 확인
STEP 3  영상 생성    →  7초 MP4 릴스 영상 인코딩 (FFmpeg)
STEP 4  Buffer 예약  →  하루 1개씩 인스타그램 자동 예약 발행
```

---

## 필수 환경 설정 (.env)

프로젝트 루트에 `.env` 파일을 만들고 아래 값을 입력하세요.  
`.env` 파일은 GitHub에 **절대 업로드하지 마세요** (`.gitignore`에 포함됨).

```
OPENAI_API_KEY=sk-proj-...
BUFFER_ACCESS_TOKEN=...
BUFFER_PROFILE_ID=...
PUBLISH_HOUR_UTC=23
```

---

## 필요 파일 (assets/ 폴더)

| 파일 | 설명 |
|------|------|
| `assets/background.jpg` | 헤더 배경 이미지 (1080×1920 권장) |
| `assets/Pretendard-Bold.ttf` | 한국어 굵은 폰트 |
| `assets/Pretendard-Regular.ttf` | 한국어 일반 폰트 |
| `assets/*.mp3` | BGM 파일 (여러 개 가능, 랜덤 선택) |

---

## 폴더 구조

```
숏폼 자동화 시스템/
├── app.py                  # Flask 서버 (메인 진입점)
├── main.py                 # CLI 일괄 실행용
├── modules/
│   ├── video_editor.py     # 이미지 합성 + FFmpeg 영상 생성
│   └── buffer_publisher.py # Buffer API 예약 발행
├── templates/
│   └── index.html          # 대시보드 (Flask로만 열 것)
├── static/
│   ├── app.js
│   └── style.css
├── assets/                 # 배경, 폰트, BGM (gitignore)
├── output/                 # 생성된 이미지·영상 (gitignore)
├── .env                    # API 키 (gitignore)
└── venv/                   # 가상환경 (gitignore)
```
