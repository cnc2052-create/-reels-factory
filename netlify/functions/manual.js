// Netlify Function — 수동 업로드 (사진→영상)
const RENDER_URL = process.env.RENDER_BACKEND_URL || "";

exports.handler = async (event) => {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
  };
  if (event.httpMethod === "OPTIONS") return { statusCode: 204, headers, body: "" };

  if (!RENDER_URL) {
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        job_id: "manual-demo-" + Date.now().toString(36),
        status: "queued",
        message: "RENDER_BACKEND_URL 환경변수를 설정하면 실제 동작합니다.",
      }),
    };
  }

  try {
    const res = await fetch(`${RENDER_URL}/api/manual`, {
      method: "POST",
      headers: { "Content-Type": event.headers["content-type"] || "application/octet-stream" },
      body: event.body,
    });
    const data = await res.json();
    return { statusCode: 200, headers, body: JSON.stringify(data) };
  } catch (e) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: e.message }) };
  }
};
