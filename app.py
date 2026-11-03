# -*- coding: utf-8 -*-
"""
폼폼 PomPom — 웹 대시보드 (Flask)
- AI 자동 기획 + 영상 생성 + 업로드
- 수동 모드: 사진 1장 업로드 → 영상 생성
"""
import io, json, os, threading, uuid
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_file

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
BASE_DIR   = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# job 상태 저장
jobs: dict = {}


# ── 폼폼 모듈 임포트 ──────────────────────────────────
def _import_pompom():
    import sys
    sys.path.insert(0, str(BASE_DIR))
    from pompom.modules.auto_researcher import research_top_product, PERSONAS
    from pompom.modules.content_pipeline import run_pipeline
    from pompom.modules.notion_saver import save_to_notion
    return research_top_product, run_pipeline, save_to_notion, PERSONAS


# ── 라우트 ──────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


@app.route("/api/jobs")
def api_jobs():
    return jsonify(list(jobs.values()))


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """AI 자동 기획 + 영상 생성"""
    data = request.json or {}
    niche   = data.get("niche", "beauty")
    persona_id = data.get("persona", "pompom_beauty")

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"id": job_id, "type": "auto", "status": "running",
                    "niche": niche, "created": datetime.now().isoformat()}

    def run():
        try:
            research_top_product, run_pipeline, save_to_notion, PERSONAS = _import_pompom()
            persona = next((p for p in PERSONAS if p["account_id"] == persona_id), PERSONAS[0])
            product = research_top_product(niche, persona)
            script  = run_pipeline(persona, product)
            save_to_notion(script, persona_id)

            # FFmpeg 영상 생성
            from pompom.make_video import make_reel
            out = f"C:/pompom_out/{job_id}_final.mp4"
            make_reel(script, out, duration=20)

            jobs[job_id].update({
                "status": "done",
                "product": product.get("name", ""),
                "video": out,
                "caption": script.get("caption", ""),
                "hook": script.get("hook_text", ""),
            })
        except Exception as e:
            jobs[job_id].update({"status": "error", "error": str(e)})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/manual", methods=["POST"])
def api_manual():
    """수동 모드: 사진 1장 + 설명 → 영상 생성"""
    if "image" not in request.files:
        return jsonify({"error": "이미지 파일 필요"}), 400

    file = request.files["image"]
    product_name = request.form.get("product_name", "제품")
    product_price = int(request.form.get("price", "0") or 0)
    description = request.form.get("description", "")
    niche = request.form.get("niche", "beauty")

    job_id = str(uuid.uuid4())[:8]
    img_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
    file.save(img_path)

    jobs[job_id] = {"id": job_id, "type": "manual", "status": "running",
                    "product": product_name, "created": datetime.now().isoformat()}

    def run():
        try:
            research_top_product, run_pipeline, save_to_notion, PERSONAS = _import_pompom()
            from pompom.modules.hook_benchmarker import select_hook
            from pompom.modules.content_pipeline import generate_script

            persona = PERSONAS[0]
            product = {
                "name": product_name,
                "price": product_price,
                "viral_angle": description or f"{product_name} 꿀템 발견",
                "affiliate_url": "",
                "image_path": str(img_path),
            }
            hook = select_hook(niche, product, [])
            script = generate_script(persona, product, hook)
            script["product"] = product
            script["image_path"] = str(img_path)

            # 영상 생성 (업로드된 이미지를 배경으로 활용)
            from pompom.make_video import make_reel_from_image
            out = f"C:/pompom_out/{job_id}_manual.mp4"
            ok = make_reel_from_image(str(img_path), script, out)
            if not ok:
                from pompom.make_video import make_reel
                make_reel(script, out, duration=20)

            save_to_notion(script, persona["account_id"])
            jobs[job_id].update({
                "status": "done",
                "video": out,
                "caption": script.get("caption", ""),
                "hook": script.get("hook_text", ""),
            })
        except Exception as e:
            jobs[job_id].update({"status": "error", "error": str(e)})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/job/<job_id>")
def api_job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "없음"}), 404
    return jsonify(job)


@app.route("/api/notion")
def api_notion():
    """Notion DB에서 최근 콘텐츠 목록"""
    try:
        import requests as req
        token  = os.getenv("NOTION_TOKEN", "")
        db_id  = os.getenv("NOTION_DB_ID", "")
        if not token or not db_id:
            return jsonify([])
        r = req.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers={"Authorization": f"Bearer {token}",
                     "Notion-Version": "2022-06-28",
                     "Content-Type": "application/json"},
            json={"page_size": 20, "sorts": [{"property": "생성일", "direction": "descending"}]},
            timeout=10,
        )
        results = r.json().get("results", [])
        items = []
        for p in results:
            props = p.get("properties", {})
            def txt(key):
                v = props.get(key, {})
                t = v.get("type", "")
                if t == "title": return "".join(x["text"]["content"] for x in v.get("title", []))
                if t == "rich_text": return "".join(x["text"]["content"] for x in v.get("rich_text", []))
                if t == "select": return (v.get("select") or {}).get("name", "")
                if t == "number": return v.get("number", 0)
                return ""
            items.append({
                "id": p["id"],
                "name": txt("이름") or txt("Name"),
                "product": txt("제품명"),
                "platform": txt("플랫폼"),
                "status": txt("상태"),
                "hook": txt("훅구조"),
                "created": p.get("created_time", ""),
            })
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
