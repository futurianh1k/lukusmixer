"""
🎵 SUNO AI Music Mashup Demo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
음악 A + 음악 B → 새로운 음악 C 생성

API Providers 지원:
  1) TTAPI (ttapi.io) — /suno/v1/upload + /suno/v1/mashup
  2) SunoAPI.org  — /api/v1/generate/upload-extend (대안)

실행: pip install gradio requests
      python suno_mashup_demo.py
"""

import gradio as gr
import requests
import time
import json
import os
import tempfile
from pathlib import Path

# ──────────────────────────────────────────────
# API Configuration
# ──────────────────────────────────────────────

API_PROVIDERS = {
    "TTAPI (ttapi.io)": {
        "upload_url": "https://api.ttapi.io/suno/v1/upload",
        "mashup_url": "https://api.ttapi.io/suno/v1/mashup",
        "fetch_url": "https://api.ttapi.io/suno/v1/fetch",
        "cover_url": "https://api.ttapi.io/suno/v1/cover",
        "header_key": "TT-API-KEY",
    },
    "SunoAPI.org": {
        "upload_extend_url": "https://api.sunoapi.org/api/v1/generate/upload-extend",
        "detail_url": "https://api.sunoapi.org/api/v1/generate/detail",
        "header_key": "Authorization",
        "auth_prefix": "Bearer ",
    },
}


# ──────────────────────────────────────────────
# TTAPI Provider Functions
# ──────────────────────────────────────────────

def ttapi_upload_audio(file_path: str, api_key: str) -> dict:
    """TTAPI: 오디오 파일 업로드 → music_id 반환 (무료 엔드포인트)"""
    url = API_PROVIDERS["TTAPI (ttapi.io)"]["upload_url"]
    headers = {"TT-API-KEY": api_key}

    with open(file_path, "rb") as f:
        files = {"file": (Path(file_path).name, f, "audio/mpeg")}
        resp = requests.post(url, headers=headers, files=files, timeout=60)

    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "SUCCESS":
        raise Exception(f"업로드 실패: {data.get('message', json.dumps(data))}")

    music_id = data["data"]["music_id"]
    return {"music_id": music_id, "raw": data}


def ttapi_mashup(music_id_a: str, music_id_b: str, api_key: str) -> dict:
    """TTAPI: 두 곡을 매시업하여 새로운 곡 생성"""
    url = API_PROVIDERS["TTAPI (ttapi.io)"]["mashup_url"]
    headers = {"TT-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {
        "music_ids": [music_id_a, music_id_b],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "SUCCESS":
        raise Exception(f"매시업 실패: {data.get('message', json.dumps(data))}")
    return data["data"]


def ttapi_fetch_result(job_id: str, api_key: str, max_retries: int = 60, interval: int = 5) -> dict:
    """TTAPI: 비동기 작업 결과 폴링"""
    url = API_PROVIDERS["TTAPI (ttapi.io)"]["fetch_url"]
    headers = {"TT-API-KEY": api_key, "Content-Type": "application/json"}

    for i in range(max_retries):
        resp = requests.post(url, headers=headers, json={"jobId": job_id}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status", "")
        progress = data.get("data", {}).get("progress", "")

        if status == "SUCCESS" and data.get("data", {}).get("musics"):
            return data["data"]

        if "FAIL" in status.upper() or "ERROR" in status.upper():
            raise Exception(f"작업 실패: {json.dumps(data)}")

        time.sleep(interval)

    raise Exception("시간 초과: 결과를 받지 못했습니다 (5분 대기 후 타임아웃)")


# ──────────────────────────────────────────────
# SunoAPI.org Provider Functions
# ──────────────────────────────────────────────

def sunoapi_upload_and_generate(file_url: str, api_key: str, style: str = "Pop",
                                 title: str = "Mashup Track", prompt: str = "") -> dict:
    """SunoAPI.org: 오디오 업로드 + 확장 생성"""
    url = API_PROVIDERS["SunoAPI.org"]["upload_extend_url"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "uploadUrl": file_url,
        "defaultParamFlag": True,
        "model": "V4_5ALL",
        "instrumental": False,
        "prompt": prompt or "Create a dynamic mashup blend",
        "style": style,
        "title": title,
        "continueAt": 0,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ──────────────────────────────────────────────
# Main Mashup Pipeline
# ──────────────────────────────────────────────

def run_mashup(file_a, file_b, api_key, provider, progress=gr.Progress()):
    """메인 매시업 파이프라인"""
    logs = []

    def log(msg):
        logs.append(msg)
        return "\n".join(logs)

    if not api_key or api_key.strip() == "":
        return "❌ API Key를 입력해주세요.", None, None, None

    if file_a is None or file_b is None:
        return "❌ 음악 파일 A와 B를 모두 업로드해주세요.", None, None, None

    try:
        if provider == "TTAPI (ttapi.io)":
            # ── Step 1: 음악 A 업로드 ──
            progress(0.1, desc="🎵 음악 A 업로드 중...")
            log_text = log("📤 [1/4] 음악 A 업로드 중...")
            yield log_text, None, None, None

            result_a = ttapi_upload_audio(file_a, api_key)
            mid_a = result_a["music_id"]
            log_text = log(f"  ✅ 음악 A → music_id: {mid_a}")
            yield log_text, None, None, None

            # ── Step 2: 음악 B 업로드 ──
            progress(0.3, desc="🎵 음악 B 업로드 중...")
            log_text = log("📤 [2/4] 음악 B 업로드 중...")
            yield log_text, None, None, None

            result_b = ttapi_upload_audio(file_b, api_key)
            mid_b = result_b["music_id"]
            log_text = log(f"  ✅ 음악 B → music_id: {mid_b}")
            yield log_text, None, None, None

            # ── Step 3: 매시업 요청 ──
            progress(0.5, desc="🎶 매시업 생성 요청 중...")
            log_text = log("🔀 [3/4] 매시업 생성 요청 중...")
            yield log_text, None, None, None

            mashup_result = ttapi_mashup(mid_a, mid_b, api_key)
            job_id = mashup_result.get("jobId", "")
            log_text = log(f"  ✅ 작업 ID: {job_id}")
            yield log_text, None, None, None

            # ── Step 4: 결과 폴링 ──
            progress(0.6, desc="⏳ 생성 결과 대기 중...")
            log_text = log("⏳ [4/4] 결과 대기 중... (최대 5분)")
            yield log_text, None, None, None

            fetch_url = API_PROVIDERS["TTAPI (ttapi.io)"]["fetch_url"]
            headers = {"TT-API-KEY": api_key, "Content-Type": "application/json"}

            for attempt in range(60):
                resp = requests.post(fetch_url, headers=headers,
                                     json={"jobId": job_id}, timeout=30)
                data = resp.json()

                p = data.get("data", {}).get("progress", "0%")
                progress(0.6 + 0.35 * (attempt / 60), desc=f"⏳ 진행: {p}")

                if data.get("status") == "SUCCESS" and data.get("data", {}).get("musics"):
                    musics = data["data"]["musics"]
                    first = musics[0]

                    audio_url = first.get("audioUrl", "")
                    image_url = first.get("imageUrl", "")
                    title = first.get("title", "Mashup Result")

                    log_text = log(f"\n🎉 매시업 완료!")
                    log_text = log(f"  📌 제목: {title}")
                    log_text = log(f"  🔗 오디오: {audio_url}")

                    # 오디오 파일 다운로드
                    audio_path = None
                    if audio_url:
                        audio_resp = requests.get(audio_url, timeout=60)
                        suffix = ".mp3" if ".mp3" in audio_url else ".wav"
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                        tmp.write(audio_resp.content)
                        tmp.close()
                        audio_path = tmp.name

                    progress(1.0, desc="✅ 완료!")
                    yield log_text, audio_path, image_url, json.dumps(data, indent=2, ensure_ascii=False)
                    return

                if "FAIL" in data.get("status", "").upper():
                    log_text = log(f"\n❌ 생성 실패: {json.dumps(data, ensure_ascii=False)}")
                    yield log_text, None, None, json.dumps(data, indent=2, ensure_ascii=False)
                    return

                time.sleep(5)

            log_text = log("\n⏰ 시간 초과: 5분 내 결과를 받지 못했습니다.")
            yield log_text, None, None, None

        elif provider == "SunoAPI.org":
            log_text = log("ℹ️ SunoAPI.org는 직접 파일 업로드가 아닌 URL 기반입니다.")
            log_text = log("   파일을 먼저 클라우드 스토리지에 업로드한 후 URL을 사용해주세요.")
            log_text = log("   TTAPI 프로바이더 사용을 권장합니다.")
            yield log_text, None, None, None

    except requests.exceptions.HTTPError as e:
        error_body = ""
        if e.response is not None:
            try:
                error_body = e.response.json()
            except Exception:
                error_body = e.response.text
        log_text = log(f"\n❌ HTTP 오류: {e}\n   응답: {error_body}")
        yield log_text, None, None, None

    except Exception as e:
        log_text = log(f"\n❌ 오류 발생: {str(e)}")
        yield log_text, None, None, None


# ──────────────────────────────────────────────
# Alternative: Cover (Remix) Mode
# ──────────────────────────────────────────────

def run_cover_remix(file_a, api_key, style_tags, lyrics, title, model, progress=gr.Progress()):
    """업로드한 음악을 새로운 스타일로 커버/리믹스"""
    logs = []

    def log(msg):
        logs.append(msg)
        return "\n".join(logs)

    if not api_key or not file_a:
        return "❌ API Key와 음악 파일을 확인해주세요.", None, None

    try:
        # Step 1: Upload
        progress(0.1, desc="📤 음악 업로드 중...")
        log_text = log("📤 [1/3] 음악 업로드 중...")
        yield log_text, None, None

        result = ttapi_upload_audio(file_a, api_key)
        mid = result["music_id"]
        log_text = log(f"  ✅ music_id: {mid}")
        yield log_text, None, None

        # Step 2: Cover request
        progress(0.3, desc="🎨 커버 생성 요청 중...")
        log_text = log("🎨 [2/3] 커버/리믹스 생성 요청 중...")
        yield log_text, None, None

        url = API_PROVIDERS["TTAPI (ttapi.io)"]["cover_url"]
        headers = {"TT-API-KEY": api_key, "Content-Type": "application/json"}
        payload = {
            "music_id": mid,
            "mv": model,
            "prompt": lyrics or "",
            "title": title or "Cover Remix",
            "tags": style_tags or "pop electronic",
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "SUCCESS":
            log_text = log(f"❌ 커버 요청 실패: {json.dumps(data, ensure_ascii=False)}")
            yield log_text, None, None
            return

        job_id = data["data"]["jobId"]
        log_text = log(f"  ✅ 작업 ID: {job_id}")
        yield log_text, None, None

        # Step 3: Poll
        progress(0.5, desc="⏳ 결과 대기 중...")
        log_text = log("⏳ [3/3] 결과 대기 중...")
        yield log_text, None, None

        fetch_url = API_PROVIDERS["TTAPI (ttapi.io)"]["fetch_url"]
        for attempt in range(60):
            resp = requests.post(fetch_url, headers=headers, json={"jobId": job_id}, timeout=30)
            data = resp.json()
            p = data.get("data", {}).get("progress", "0%")
            progress(0.5 + 0.45 * (attempt / 60), desc=f"⏳ {p}")

            if data.get("status") == "SUCCESS" and data.get("data", {}).get("musics"):
                first = data["data"]["musics"][0]
                audio_url = first.get("audioUrl", "")

                audio_path = None
                if audio_url:
                    audio_resp = requests.get(audio_url, timeout=60)
                    suffix = ".mp3" if ".mp3" in audio_url else ".wav"
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    tmp.write(audio_resp.content)
                    tmp.close()
                    audio_path = tmp.name

                log_text = log(f"\n🎉 커버 생성 완료!")
                log_text = log(f"  📌 {first.get('title', 'N/A')}")
                progress(1.0)
                yield log_text, audio_path, json.dumps(data, indent=2, ensure_ascii=False)
                return

            if "FAIL" in data.get("status", "").upper():
                log_text = log(f"\n❌ 실패: {json.dumps(data, ensure_ascii=False)}")
                yield log_text, None, json.dumps(data, indent=2, ensure_ascii=False)
                return

            time.sleep(5)

        log_text = log("\n⏰ 시간 초과")
        yield log_text, None, None

    except Exception as e:
        log_text = log(f"\n❌ 오류: {str(e)}")
        yield log_text, None, None


# ──────────────────────────────────────────────
# Gradio UI
# ──────────────────────────────────────────────

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }
code, pre, .mono { font-family: 'JetBrains Mono', monospace !important; }

.gradio-container {
    max-width: 1100px !important;
    margin: 0 auto !important;
}

.header-block {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 16px;
    color: white;
    text-align: center;
}
.header-block h1 {
    font-size: 28px;
    font-weight: 700;
    margin: 0;
    color: #e94560 !important;
}
.header-block p {
    margin: 8px 0 0 0;
    font-size: 14px;
    color: #a8b2d1;
}

.info-box {
    background: #f0f4ff;
    border-left: 4px solid #0f3460;
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
    font-size: 13px;
    line-height: 1.8;
}
"""

HEADER_HTML = """
<div class="header-block">
    <h1>🎵 SUNO AI Music Mashup</h1>
    <p>음악 A + 음악 B → AI가 만드는 새로운 음악 C</p>
    <p style="font-size:12px; color:#8892b0; margin-top:4px;">
        Powered by TTAPI.io Suno API &nbsp;|&nbsp; Upload → Mashup → Download
    </p>
</div>
"""

INFO_HTML = """
<div class="info-box">
    <strong>🔑 API Key 발급 방법</strong><br>
    ① <a href="https://ttapi.io" target="_blank">ttapi.io</a> 회원가입<br>
    ② Dashboard → API Key 복사<br>
    ③ 위 입력란에 붙여넣기<br><br>
    <strong>📋 지원 포맷:</strong> MP3, WAV, OGG, FLAC (최대 8분)<br>
    <strong>💰 비용:</strong> Upload은 무료, Mashup/Cover는 크레딧 차감
</div>
"""

WORKFLOW_HTML = """
<div style="text-align:center; padding:12px; background:#f8f9fa; border-radius:12px; margin:8px 0;">
    <span style="font-size:32px;">🎵</span>
    <span style="font-size:20px; color:#999; margin:0 8px;">+</span>
    <span style="font-size:32px;">🎶</span>
    <span style="font-size:20px; color:#999; margin:0 8px;">→</span>
    <span style="font-size:18px; color:#e94560; font-weight:700;">AI 매시업</span>
    <span style="font-size:20px; color:#999; margin:0 8px;">→</span>
    <span style="font-size:32px;">🎧</span>
    <br>
    <span style="font-size:12px; color:#888;">Music A &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Music B &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Suno AI &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Music C</span>
</div>
"""


def build_app():
    with gr.Blocks(css=CUSTOM_CSS, title="SUNO AI Music Mashup", theme=gr.themes.Soft()) as app:

        gr.HTML(HEADER_HTML)

        # ── Settings ──
        with gr.Row():
            with gr.Column(scale=3):
                api_key = gr.Textbox(
                    label="🔑 API Key (TTAPI)",
                    placeholder="ttapi-xxxxxxxxxxxxxxxx",
                    type="password",
                    info="ttapi.io에서 발급받은 API Key를 입력하세요"
                )
            with gr.Column(scale=1):
                provider = gr.Dropdown(
                    choices=list(API_PROVIDERS.keys()),
                    value="TTAPI (ttapi.io)",
                    label="API Provider",
                )

        # ── Tabs ──
        with gr.Tabs():

            # ━━━━━ Tab 1: Mashup ━━━━━
            with gr.TabItem("🔀 매시업 (A+B → C)", id="mashup"):
                gr.HTML(WORKFLOW_HTML)

                with gr.Row(equal_height=True):
                    with gr.Column():
                        audio_a = gr.Audio(
                            label="🎵 음악 A 업로드",
                            type="filepath",
                            sources=["upload"],
                        )
                    with gr.Column():
                        audio_b = gr.Audio(
                            label="🎶 음악 B 업로드",
                            type="filepath",
                            sources=["upload"],
                        )

                mashup_btn = gr.Button(
                    "🚀 매시업 시작",
                    variant="primary",
                    size="lg",
                )

                with gr.Row():
                    with gr.Column(scale=2):
                        mashup_log = gr.Textbox(
                            label="📋 처리 로그",
                            lines=12,
                            interactive=False,
                        )
                    with gr.Column(scale=1):
                        gr.HTML(INFO_HTML)

                gr.Markdown("### 🎧 생성 결과")
                with gr.Row():
                    with gr.Column(scale=2):
                        result_audio = gr.Audio(label="생성된 음악 C", type="filepath")
                    with gr.Column(scale=1):
                        result_image = gr.Image(label="앨범 커버", type="filepath")

                with gr.Accordion("📄 Raw API Response", open=False):
                    result_json = gr.Code(label="JSON", language="json")

                mashup_btn.click(
                    fn=run_mashup,
                    inputs=[audio_a, audio_b, api_key, provider],
                    outputs=[mashup_log, result_audio, result_image, result_json],
                )

            # ━━━━━ Tab 2: Cover / Remix ━━━━━
            with gr.TabItem("🎨 커버 / 리믹스", id="cover"):
                gr.Markdown(
                    "업로드한 음악의 스타일을 변경하여 새로운 버전을 만듭니다.\n"
                    "예: 발라드 → 일렉트로닉, 팝 → 재즈 등"
                )

                with gr.Row():
                    with gr.Column():
                        cover_audio = gr.Audio(
                            label="🎵 원본 음악 업로드",
                            type="filepath",
                            sources=["upload"],
                        )
                    with gr.Column():
                        cover_style = gr.Textbox(
                            label="🎭 스타일 태그",
                            placeholder="예: jazz, electronic, k-pop, orchestral",
                            value="electronic dance pop",
                        )
                        cover_title = gr.Textbox(
                            label="📝 제목",
                            placeholder="새 곡 제목",
                            value="My Remix",
                        )
                        cover_lyrics = gr.Textbox(
                            label="✍️ 가사 (선택사항)",
                            placeholder="가사를 입력하세요 (비워두면 자동 생성)",
                            lines=3,
                        )
                        cover_model = gr.Dropdown(
                            label="🤖 모델",
                            choices=[
                                "chirp-v4-5-all",
                                "chirp-v4-5+",
                                "chirp-v4-5",
                                "chirp-v4",
                                "chirp-v3-5",
                            ],
                            value="chirp-v4-5+",
                        )

                cover_btn = gr.Button("🎨 커버 생성", variant="primary", size="lg")

                cover_log = gr.Textbox(label="📋 처리 로그", lines=10, interactive=False)
                cover_result = gr.Audio(label="🎧 생성된 커버", type="filepath")

                with gr.Accordion("📄 Raw API Response", open=False):
                    cover_json = gr.Code(label="JSON", language="json")

                cover_btn.click(
                    fn=run_cover_remix,
                    inputs=[cover_audio, api_key, cover_style, cover_lyrics, cover_title, cover_model],
                    outputs=[cover_log, cover_result, cover_json],
                )

            # ━━━━━ Tab 3: API 가이드 ━━━━━
            with gr.TabItem("📖 API 가이드", id="guide"):
                gr.Markdown("""
## SUNO API 워크플로우

### 1. 매시업 (Mashup) 파이프라인

```
[음악 A 파일] ─┬─ Upload ──→ music_id_A ─┐
               │                          ├─ Mashup ──→ jobId ──→ Fetch (폴링) ──→ 음악 C
[음악 B 파일] ─┴─ Upload ──→ music_id_B ─┘
```

| 단계 | API Endpoint | 설명 |
|------|-------------|------|
| 1 | `POST /suno/v1/upload` | 오디오 파일 업로드 (무료) → `music_id` 반환 |
| 2 | `POST /suno/v1/mashup` | 두 music_id로 매시업 요청 → `jobId` 반환 |
| 3 | `POST /suno/v1/fetch` | jobId로 결과 폴링 → 완료 시 오디오 URL 반환 |

### 2. 커버/리믹스 파이프라인

```
[음악 파일] ──→ Upload ──→ music_id ──→ Cover (스타일 지정) ──→ Fetch ──→ 리믹스 결과
```

### 3. Python 코드 예시

```python
import requests

API_KEY = "your-ttapi-key"
headers = {"TT-API-KEY": API_KEY}

# Step 1: Upload
with open("song_a.mp3", "rb") as f:
    resp = requests.post(
        "https://api.ttapi.io/suno/v1/upload",
        headers=headers,
        files={"file": f}
    )
    music_id_a = resp.json()["data"]["music_id"]

# Step 2: Mashup
resp = requests.post(
    "https://api.ttapi.io/suno/v1/mashup",
    headers=headers,
    json={"music_ids": [music_id_a, music_id_b]}
)
job_id = resp.json()["data"]["jobId"]

# Step 3: Poll for result
while True:
    resp = requests.post(
        "https://api.ttapi.io/suno/v1/fetch",
        headers=headers,
        json={"jobId": job_id}
    )
    data = resp.json()
    if data["status"] == "SUCCESS" and data["data"].get("musics"):
        audio_url = data["data"]["musics"][0]["audioUrl"]
        break
    time.sleep(5)
```

### 4. 참고 링크
- **TTAPI 공식 문서**: [ttapi.io/docs](https://ttapi.io/docs/apiReference/suno/generate)
- **Kie.ai (대안)**: [kie.ai/suno-api](https://kie.ai/suno-api) — 매시업 2곡 업로드 지원
- **SunoAPI.org**: [docs.sunoapi.org](https://docs.sunoapi.org/) — Upload & Extend 지원
- **오픈소스 suno-api**: [github.com/gcui-art/suno-api](https://github.com/gcui-art/suno-api)
                """)

        # Footer
        gr.HTML("""
        <div style="text-align:center; padding:16px; color:#888; font-size:12px; border-top:1px solid #eee; margin-top:16px;">
            SUNO AI Music Mashup Demo &nbsp;|&nbsp; API by TTAPI.io &nbsp;|&nbsp;
            ⚠️ 비공식 API를 사용하며 상업적 이용 시 라이선스를 확인하세요.
        </div>
        """)

    return app


# ──────────────────────────────────────────────
# Launch
# ──────────────────────────────────────────────

if __name__ == "__main__":
    app = build_app()
    app.queue()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
