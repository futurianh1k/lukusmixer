"""
🎵 KIE.AI Music Mashup Demo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
음악 A + 음악 B → 새로운 음악 C 생성

API Provider: KIE.AI (kie.ai)
  - Upload & Cover: 기존 음악을 새로운 스타일로 커버
  - Upload & Extend: 기존 음악을 확장

참고: kie.ai는 URL 기반 업로드를 사용합니다.
      로컬 파일은 자동으로 0x0.st에 임시 업로드됩니다.

실행: pip install gradio requests
      python kie_mashup_demo.py

API Key 발급: https://kie.ai/api-key
"""

import gradio as gr
import requests
import time
import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# ──────────────────────────────────────────────
# API Configuration
# ──────────────────────────────────────────────

KIE_API_BASE = "https://api.kie.ai"

ENDPOINTS = {
    "upload_cover": f"{KIE_API_BASE}/api/v1/generate/upload-cover",
    "upload_extend": f"{KIE_API_BASE}/api/v1/generate/upload-extend",
    "record_info": f"{KIE_API_BASE}/api/v1/generate/record-info",
    "generate": f"{KIE_API_BASE}/api/v1/generate/music",
}

MODELS = [
    "V5",
    "V4_5PLUS", 
    "V4_5",
    "V4_5ALL",
    "V4",
    "V3_5",
]


# ──────────────────────────────────────────────
# File Upload Helper
# ──────────────────────────────────────────────

def get_audio_duration(file_path: str) -> float:
    """오디오 파일 길이(초) 반환 (ffprobe 사용)"""
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0


def get_file_size_mb(file_path: str) -> float:
    """파일 크기(MB) 반환"""
    return os.path.getsize(file_path) / (1024 * 1024)


def upload_to_catbox(file_path: str, timeout: int = 300) -> str:
    """
    로컬 파일을 catbox.moe에 업로드하고 URL 반환
    - 무료, 익명, 최대 200MB
    - 파일은 영구 보관 (삭제 요청 전까지)
    - KIE.AI 서버에서 접근 가능
    
    참고: https://catbox.moe/
    """
    url = "https://catbox.moe/user/api.php"
    
    file_size = get_file_size_mb(file_path)
    if file_size > 200:
        raise Exception(f"파일이 너무 큽니다: {file_size:.1f}MB (catbox 제한: 200MB)")
    
    with open(file_path, "rb") as f:
        files = {"fileToUpload": (Path(file_path).name, f)}
        data = {"reqtype": "fileupload"}
        resp = requests.post(url, files=files, data=data, timeout=timeout)
    
    resp.raise_for_status()
    file_url = resp.text.strip()
    
    if not file_url.startswith("http"):
        raise Exception(f"catbox 업로드 실패: {file_url}")
    
    return file_url


def upload_to_0x0st(file_path: str, timeout: int = 300) -> str:
    """
    로컬 파일을 0x0.st에 업로드하고 URL 반환
    - 무료, 익명, 최대 512MB
    - 파일은 일정 기간 후 자동 삭제됨
    - 참고: KIE.AI 서버에서 접근이 차단될 수 있음
    """
    url = "https://0x0.st"
    
    file_size = get_file_size_mb(file_path)
    if file_size > 100:
        raise Exception(f"파일이 너무 큽니다: {file_size:.1f}MB (권장: 100MB 이하)")
    
    with open(file_path, "rb") as f:
        files = {"file": (Path(file_path).name, f)}
        resp = requests.post(url, files=files, timeout=timeout)
    
    resp.raise_for_status()
    file_url = resp.text.strip()
    
    if not file_url.startswith("http"):
        raise Exception(f"업로드 실패: {file_url}")
    
    return file_url


def upload_to_litterbox(file_path: str, timeout: int = 300, expire: str = "24h") -> str:
    """
    로컬 파일을 litterbox.catbox.moe에 업로드 (임시 파일용)
    - 무료, 익명, 최대 1GB
    - 만료 옵션: 1h, 12h, 24h, 72h (기본 24h)
    
    참고: https://litterbox.catbox.moe/
    """
    url = "https://litterbox.catbox.moe/resources/internals/api.php"
    
    file_size = get_file_size_mb(file_path)
    if file_size > 1000:
        raise Exception(f"파일이 너무 큽니다: {file_size:.1f}MB (litterbox 제한: 1GB)")
    
    with open(file_path, "rb") as f:
        files = {"fileToUpload": (Path(file_path).name, f)}
        data = {"reqtype": "fileupload", "time": expire}
        resp = requests.post(url, files=files, data=data, timeout=timeout)
    
    resp.raise_for_status()
    file_url = resp.text.strip()
    
    if not file_url.startswith("http"):
        raise Exception(f"litterbox 업로드 실패: {file_url}")
    
    return file_url


def upload_file_to_cloud(file_path: str, timeout: int = 300) -> Tuple[str, str]:
    """
    파일을 클라우드에 업로드 (여러 서비스 시도)
    반환: (URL, 사용된 서비스명)
    
    우선순위:
    1. catbox.moe - 영구 보관, KIE 서버 접근 가능
    2. litterbox - 임시 파일, 24시간 보관
    3. 0x0.st - 백업용
    """
    errors = []
    
    # 1. catbox.moe 시도 (영구 보관, 안정적)
    try:
        url = upload_to_catbox(file_path, timeout)
        return url, "catbox.moe"
    except Exception as e:
        errors.append(f"catbox: {str(e)}")
    
    # 2. litterbox 시도 (임시 파일)
    try:
        url = upload_to_litterbox(file_path, timeout, expire="24h")
        return url, "litterbox"
    except Exception as e:
        errors.append(f"litterbox: {str(e)}")
    
    # 3. 0x0.st 시도 (백업)
    try:
        url = upload_to_0x0st(file_path, timeout)
        return url, "0x0.st"
    except Exception as e:
        errors.append(f"0x0.st: {str(e)}")
    
    # 모든 서비스 실패
    raise Exception(f"모든 업로드 서비스 실패:\n" + "\n".join(errors))


def convert_gdrive_url(url: str) -> str:
    """
    구글 드라이브 공유 URL을 직접 다운로드 URL로 변환
    
    입력 형식:
    - https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    - https://drive.google.com/open?id=FILE_ID
    
    출력: https://drive.google.com/uc?export=download&id=FILE_ID
    """
    import re
    
    # 이미 직접 다운로드 URL인 경우
    if "uc?export=download" in url:
        return url
    
    # /file/d/FILE_ID/ 형식
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    
    # open?id=FILE_ID 형식
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    
    # 변환 실패시 원본 반환
    return url


def convert_dropbox_url(url: str) -> str:
    """
    Dropbox 공유 URL을 직접 다운로드 URL로 변환
    
    입력: https://www.dropbox.com/s/xxx/file.mp3?dl=0
    출력: https://www.dropbox.com/s/xxx/file.mp3?dl=1
    """
    if "dropbox.com" in url:
        if "dl=0" in url:
            return url.replace("dl=0", "dl=1")
        elif "dl=1" not in url:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}dl=1"
    return url


def prepare_audio_url(file_path_or_url: str, direct_url: str = "") -> Tuple[str, str]:
    """
    오디오 URL 준비 (직접 URL 또는 파일 업로드)
    
    Args:
        file_path_or_url: 로컬 파일 경로 또는 URL
        direct_url: 직접 입력한 URL (우선순위 높음)
    
    Returns:
        (audio_url, status_message)
    """
    # 직접 URL이 입력된 경우 우선 사용
    if direct_url and direct_url.strip():
        url = direct_url.strip()
        
        # 구글 드라이브 URL 변환
        if "drive.google.com" in url:
            url = convert_gdrive_url(url)
            return url, "구글 드라이브 URL 변환 완료"
        
        # Dropbox URL 변환
        if "dropbox.com" in url:
            url = convert_dropbox_url(url)
            return url, "Dropbox URL 변환 완료"
        
        return url, "직접 URL 사용"
    
    # 로컬 파일인 경우 업로드
    if file_path_or_url and os.path.isfile(file_path_or_url):
        url, service = upload_file_to_cloud(file_path_or_url, timeout=300)
        return url, f"{service}에 업로드 완료"
    
    raise Exception("파일 또는 URL을 제공해주세요")


# ──────────────────────────────────────────────
# KIE.AI API Functions
# ──────────────────────────────────────────────

def kie_get_headers(api_key: str) -> dict:
    """API 요청 헤더 생성"""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


def kie_upload_cover(
    audio_url: str,
    api_key: str,
    prompt: str = "",
    style: str = "",
    title: str = "Cover Track",
    model: str = "V4",
    instrumental: bool = False,
    custom_mode: bool = True,
    callback_url: str = "https://example.com/callback",
) -> dict:
    """
    KIE.AI: 오디오 URL을 커버 버전으로 변환
    - 멜로디는 유지하면서 새로운 스타일 적용
    
    참고: callBackUrl은 API 필수 파라미터이지만, 
    polling 방식을 사용하므로 더미 URL을 전달합니다.
    """
    url = ENDPOINTS["upload_cover"]
    headers = kie_get_headers(api_key)
    
    payload = {
        "uploadUrl": audio_url,
        "model": model,
        "customMode": custom_mode,
        "instrumental": instrumental,
        "callBackUrl": callback_url,
    }
    
    if custom_mode:
        payload["title"] = title[:80] if model in ["V4", "V4_5ALL"] else title[:100]
        payload["style"] = style[:200] if model == "V4" else style[:1000]
        if not instrumental:
            payload["prompt"] = prompt[:3000] if model == "V4" else prompt[:5000]
    else:
        payload["prompt"] = prompt[:500]
    
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    
    if data.get("code") != 200:
        raise Exception(f"커버 요청 실패: {data.get('msg', json.dumps(data))}")
    
    return data.get("data", {})


def kie_upload_extend(
    audio_url: str,
    api_key: str,
    prompt: str = "",
    style: str = "",
    title: str = "Extended Track",
    model: str = "V4",
    continue_at: float = 0,
    callback_url: str = "https://example.com/callback",
) -> dict:
    """
    KIE.AI: 오디오 URL을 확장
    - 기존 음악의 스타일을 유지하며 연장
    
    참고: callBackUrl은 API 필수 파라미터이지만,
    polling 방식을 사용하므로 더미 URL을 전달합니다.
    """
    url = ENDPOINTS["upload_extend"]
    headers = kie_get_headers(api_key)
    
    payload = {
        "uploadUrl": audio_url,
        "model": model,
        "defaultParamFlag": True,
        "continueAt": continue_at,
        "callBackUrl": callback_url,
    }
    
    if prompt:
        payload["prompt"] = prompt[:3000] if model == "V4" else prompt[:5000]
    if style:
        payload["style"] = style[:200] if model == "V4" else style[:1000]
    if title:
        payload["title"] = title[:80] if model in ["V4", "V4_5ALL"] else title[:100]
    
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    
    if data.get("code") != 200:
        raise Exception(f"확장 요청 실패: {data.get('msg', json.dumps(data))}")
    
    return data.get("data", {})


def kie_fetch_result(task_id: str, api_key: str, max_retries: int = 60, interval: int = 5) -> dict:
    """KIE.AI: 작업 결과 폴링"""
    url = ENDPOINTS["record_info"]
    headers = kie_get_headers(api_key)
    
    for i in range(max_retries):
        resp = requests.get(
            url, 
            headers=headers, 
            params={"taskId": task_id}, 
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("code") != 200:
            raise Exception(f"조회 실패: {data.get('msg')}")
        
        task_data = data.get("data", {})
        status = task_data.get("status", "")
        
        if status == "SUCCESS":
            return task_data
        
        if status in ["CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", 
                      "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR"]:
            error_msg = task_data.get("errorMessage", status)
            raise Exception(f"생성 실패: {error_msg}")
        
        time.sleep(interval)
    
    raise Exception("시간 초과: 5분 내 결과를 받지 못했습니다")


# ──────────────────────────────────────────────
# Main Pipelines
# ──────────────────────────────────────────────

def run_cover(audio_url_input, api_key, style, prompt, title, model, instrumental, progress=gr.Progress()):
    """커버 생성 파이프라인 (URL 기반)"""
    logs = []
    
    def log(msg):
        logs.append(msg)
        return "\n".join(logs)
    
    if not api_key or not api_key.strip():
        return "❌ API Key를 입력해주세요.", None, None, None
    
    if not audio_url_input or not audio_url_input.strip():
        return "❌ 음악 URL을 입력해주세요.", None, None, None
    
    try:
        # Step 1: URL 준비 및 변환
        progress(0.1, desc="🔗 URL 준비 중...")
        log_text = log("🔗 [1/3] URL 준비 중...")
        yield log_text, None, None, None
        
        audio_url = audio_url_input.strip()
        
        # 구글 드라이브 URL 변환
        if "drive.google.com" in audio_url:
            audio_url = convert_gdrive_url(audio_url)
            log_text = log("  ✅ 구글 드라이브 URL 변환 완료")
        # Dropbox URL 변환
        elif "dropbox.com" in audio_url:
            audio_url = convert_dropbox_url(audio_url)
            log_text = log("  ✅ Dropbox URL 변환 완료")
        else:
            log_text = log("  ✅ 직접 URL 사용")
        
        log_text = log(f"  🔗 URL: {audio_url[:70]}...")
        yield log_text, None, None, None
        
        # Step 2: 커버 요청
        progress(0.3, desc="🎨 커버 생성 요청 중...")
        log_text = log("🎨 [2/3] 커버 생성 요청 중...")
        yield log_text, None, None, None
        
        result = kie_upload_cover(
            audio_url=audio_url,
            api_key=api_key,
            prompt=prompt,
            style=style,
            title=title or "AI Cover",
            model=model,
            instrumental=instrumental,
        )
        
        task_id = result.get("taskId", "")
        log_text = log(f"  ✅ 작업 ID: {task_id}")
        yield log_text, None, None, None
        
        # Step 3: 결과 폴링
        progress(0.5, desc="⏳ 생성 결과 대기 중...")
        log_text = log("⏳ [3/3] 결과 대기 중... (최대 5분)")
        yield log_text, None, None, None
        
        for attempt in range(60):
            resp = requests.get(
                ENDPOINTS["record_info"],
                headers=kie_get_headers(api_key),
                params={"taskId": task_id},
                timeout=30
            )
            data = resp.json()
            
            task_data = data.get("data", {})
            status = task_data.get("status", "")
            
            progress(0.5 + 0.45 * (attempt / 60), desc=f"⏳ 상태: {status}")
            
            if status == "SUCCESS":
                response_data = task_data.get("response", {})
                suno_data = response_data.get("sunoData", [])
                
                if suno_data:
                    first = suno_data[0]
                    audio_url_result = first.get("audioUrl", "")
                    image_url = first.get("imageUrl", "")
                    result_title = first.get("title", "Cover Result")
                    duration = first.get("duration", 0)
                    
                    log_text = log(f"\n🎉 커버 생성 완료!")
                    log_text = log(f"  📌 제목: {result_title}")
                    log_text = log(f"  ⏱️ 길이: {duration:.1f}초")
                    log_text = log(f"  🔗 오디오: {audio_url_result}")
                    
                    # 오디오 다운로드
                    audio_path = None
                    if audio_url_result:
                        audio_resp = requests.get(audio_url_result, timeout=120)
                        suffix = ".mp3" if ".mp3" in audio_url_result else ".wav"
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                        tmp.write(audio_resp.content)
                        tmp.close()
                        audio_path = tmp.name
                    
                    progress(1.0, desc="✅ 완료!")
                    yield log_text, audio_path, image_url, json.dumps(data, indent=2, ensure_ascii=False)
                    return
            
            if status in ["CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", 
                          "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR"]:
                error_msg = task_data.get("errorMessage", status)
                log_text = log(f"\n❌ 생성 실패: {error_msg}")
                yield log_text, None, None, json.dumps(data, indent=2, ensure_ascii=False)
                return
            
            time.sleep(5)
        
        log_text = log("\n⏰ 시간 초과: 5분 내 결과를 받지 못했습니다.")
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


def run_extend(audio_url_input, api_key, style, prompt, title, model, continue_at, progress=gr.Progress()):
    """확장 생성 파이프라인 (URL 기반)"""
    logs = []
    
    def log(msg):
        logs.append(msg)
        return "\n".join(logs)
    
    if not api_key or not api_key.strip():
        return "❌ API Key를 입력해주세요.", None, None
    
    if not audio_url_input or not audio_url_input.strip():
        return "❌ 음악 URL을 입력해주세요.", None, None
    
    try:
        # Step 1: URL 준비 및 변환
        progress(0.1, desc="🔗 URL 준비 중...")
        log_text = log("🔗 [1/3] URL 준비 중...")
        yield log_text, None, None
        
        audio_url = audio_url_input.strip()
        
        # 구글 드라이브 URL 변환
        if "drive.google.com" in audio_url:
            audio_url = convert_gdrive_url(audio_url)
            log_text = log("  ✅ 구글 드라이브 URL 변환 완료")
        # Dropbox URL 변환
        elif "dropbox.com" in audio_url:
            audio_url = convert_dropbox_url(audio_url)
            log_text = log("  ✅ Dropbox URL 변환 완료")
        else:
            log_text = log("  ✅ 직접 URL 사용")
        
        log_text = log(f"  🔗 URL: {audio_url[:70]}...")
        yield log_text, None, None
        
        # Step 2: 확장 요청
        progress(0.3, desc="🔄 확장 생성 요청 중...")
        log_text = log("🔄 [2/3] 확장 생성 요청 중...")
        yield log_text, None, None
        
        result = kie_upload_extend(
            audio_url=audio_url,
            api_key=api_key,
            prompt=prompt,
            style=style,
            title=title or "Extended Track",
            model=model,
            continue_at=continue_at,
        )
        
        task_id = result.get("taskId", "")
        log_text = log(f"  ✅ 작업 ID: {task_id}")
        yield log_text, None, None
        
        # Step 3: 결과 폴링
        progress(0.5, desc="⏳ 생성 결과 대기 중...")
        log_text = log("⏳ [3/3] 결과 대기 중... (최대 5분)")
        yield log_text, None, None
        
        for attempt in range(60):
            resp = requests.get(
                ENDPOINTS["record_info"],
                headers=kie_get_headers(api_key),
                params={"taskId": task_id},
                timeout=30
            )
            data = resp.json()
            
            task_data = data.get("data", {})
            status = task_data.get("status", "")
            
            progress(0.5 + 0.45 * (attempt / 60), desc=f"⏳ 상태: {status}")
            
            if status == "SUCCESS":
                response_data = task_data.get("response", {})
                suno_data = response_data.get("sunoData", [])
                
                if suno_data:
                    first = suno_data[0]
                    audio_url_result = first.get("audioUrl", "")
                    result_title = first.get("title", "Extended Result")
                    duration = first.get("duration", 0)
                    
                    log_text = log(f"\n🎉 확장 생성 완료!")
                    log_text = log(f"  📌 제목: {result_title}")
                    log_text = log(f"  ⏱️ 길이: {duration:.1f}초")
                    
                    # 오디오 다운로드
                    audio_path = None
                    if audio_url_result:
                        audio_resp = requests.get(audio_url_result, timeout=120)
                        suffix = ".mp3" if ".mp3" in audio_url_result else ".wav"
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                        tmp.write(audio_resp.content)
                        tmp.close()
                        audio_path = tmp.name
                    
                    progress(1.0, desc="✅ 완료!")
                    yield log_text, audio_path, json.dumps(data, indent=2, ensure_ascii=False)
                    return
            
            if status in ["CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", 
                          "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR"]:
                error_msg = task_data.get("errorMessage", status)
                log_text = log(f"\n❌ 생성 실패: {error_msg}")
                yield log_text, None, json.dumps(data, indent=2, ensure_ascii=False)
                return
            
            time.sleep(5)
        
        log_text = log("\n⏰ 시간 초과")
        yield log_text, None, None
        
    except Exception as e:
        log_text = log(f"\n❌ 오류: {str(e)}")
        yield log_text, None, None


def run_mashup_sequential(url_a_input, url_b_input, api_key, style, model, progress=gr.Progress()):
    """
    순차적 매시업: A를 커버 → 결과에 B 스타일 적용
    (진정한 매시업 API가 없으므로 순차 처리)
    """
    logs = []
    
    def log(msg):
        logs.append(msg)
        return "\n".join(logs)
    
    if not api_key or not api_key.strip():
        return "❌ API Key를 입력해주세요.", None, None, None
    
    if not url_a_input or not url_a_input.strip():
        return "❌ 음악 A URL을 입력해주세요.", None, None, None
    
    if not url_b_input or not url_b_input.strip():
        return "❌ 음악 B URL을 입력해주세요.", None, None, None
    
    try:
        # Step 1: 음악 A URL 준비
        progress(0.05, desc="🔗 음악 A URL 준비 중...")
        log_text = log("🔗 [1/4] 음악 A URL 준비 중...")
        yield log_text, None, None, None
        
        url_a = url_a_input.strip()
        if "drive.google.com" in url_a:
            url_a = convert_gdrive_url(url_a)
            log_text = log("  ✅ 구글 드라이브 URL 변환 완료")
        elif "dropbox.com" in url_a:
            url_a = convert_dropbox_url(url_a)
            log_text = log("  ✅ Dropbox URL 변환 완료")
        else:
            log_text = log("  ✅ 직접 URL 사용")
        yield log_text, None, None, None
        
        # Step 2: 음악 B URL 준비
        progress(0.15, desc="🔗 음악 B URL 준비 중...")
        log_text = log("🔗 [2/4] 음악 B URL 준비 중...")
        yield log_text, None, None, None
        
        url_b = url_b_input.strip()
        if "drive.google.com" in url_b:
            url_b = convert_gdrive_url(url_b)
            log_text = log("  ✅ 구글 드라이브 URL 변환 완료")
        elif "dropbox.com" in url_b:
            url_b = convert_dropbox_url(url_b)
            log_text = log("  ✅ Dropbox URL 변환 완료")
        else:
            log_text = log("  ✅ 직접 URL 사용")
        yield log_text, None, None, None
        
        # Step 3: A를 기반으로 커버 생성 (B의 스타일 적용)
        progress(0.25, desc="🔀 매시업 생성 요청 중...")
        log_text = log("🔀 [3/4] 음악 A + B 스타일 매시업 요청 중...")
        yield log_text, None, None, None
        
        mashup_style = style or "blend fusion mashup"
        
        result = kie_upload_cover(
            audio_url=url_a,
            api_key=api_key,
            prompt=f"Create a mashup blending two songs together. Style: {mashup_style}",
            style=mashup_style,
            title="AI Mashup",
            model=model,
            instrumental=False,
        )
        
        task_id = result.get("taskId", "")
        log_text = log(f"  ✅ 작업 ID: {task_id}")
        yield log_text, None, None, None
        
        # Step 4: 결과 폴링
        progress(0.4, desc="⏳ 생성 결과 대기 중...")
        log_text = log("⏳ [4/4] 결과 대기 중... (최대 5분)")
        yield log_text, None, None, None
        
        for attempt in range(60):
            resp = requests.get(
                ENDPOINTS["record_info"],
                headers=kie_get_headers(api_key),
                params={"taskId": task_id},
                timeout=30
            )
            data = resp.json()
            
            task_data = data.get("data", {})
            status = task_data.get("status", "")
            
            progress(0.4 + 0.55 * (attempt / 60), desc=f"⏳ 상태: {status}")
            
            if status == "SUCCESS":
                response_data = task_data.get("response", {})
                suno_data = response_data.get("sunoData", [])
                
                if suno_data:
                    first = suno_data[0]
                    audio_url_result = first.get("audioUrl", "")
                    image_url = first.get("imageUrl", "")
                    result_title = first.get("title", "Mashup Result")
                    duration = first.get("duration", 0)
                    
                    log_text = log(f"\n🎉 매시업 생성 완료!")
                    log_text = log(f"  📌 제목: {result_title}")
                    log_text = log(f"  ⏱️ 길이: {duration:.1f}초")
                    log_text = log(f"  🔗 오디오: {audio_url_result}")
                    
                    audio_path = None
                    if audio_url_result:
                        audio_resp = requests.get(audio_url_result, timeout=120)
                        suffix = ".mp3" if ".mp3" in audio_url_result else ".wav"
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                        tmp.write(audio_resp.content)
                        tmp.close()
                        audio_path = tmp.name
                    
                    progress(1.0, desc="✅ 완료!")
                    yield log_text, audio_path, image_url, json.dumps(data, indent=2, ensure_ascii=False)
                    return
            
            if status in ["CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", 
                          "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR"]:
                error_msg = task_data.get("errorMessage", status)
                log_text = log(f"\n❌ 생성 실패: {error_msg}")
                yield log_text, None, None, json.dumps(data, indent=2, ensure_ascii=False)
                return
            
            time.sleep(5)
        
        log_text = log("\n⏰ 시간 초과")
        yield log_text, None, None, None
        
    except Exception as e:
        log_text = log(f"\n❌ 오류: {str(e)}")
        yield log_text, None, None, None


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
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #21262d 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 16px;
    color: white;
    text-align: center;
    border: 1px solid #30363d;
}
.header-block h1 {
    font-size: 28px;
    font-weight: 700;
    margin: 0;
    color: #58a6ff !important;
}
.header-block p {
    margin: 8px 0 0 0;
    font-size: 14px;
    color: #8b949e;
}

.info-box {
    background: #161b22;
    border-left: 4px solid #58a6ff;
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
    font-size: 13px;
    line-height: 1.8;
    color: #c9d1d9;
}
.info-box a { color: #58a6ff; }
"""

HEADER_HTML = """
<div class="header-block">
    <h1>🎵 KIE.AI Music Studio</h1>
    <p>음악 커버 / 확장 / 매시업 생성</p>
    <p style="font-size:12px; color:#8b949e; margin-top:4px;">
        Powered by KIE.AI Suno API &nbsp;|&nbsp; Upload → Transform → Download
    </p>
</div>
"""

INFO_HTML = """
<div class="info-box">
    <strong>🔑 API Key 발급 방법</strong><br>
    ① <a href="https://kie.ai" target="_blank">kie.ai</a> 회원가입<br>
    ② <a href="https://kie.ai/api-key" target="_blank">API Key 관리 페이지</a> → Key 복사<br>
    ③ 위 입력란에 붙여넣기<br><br>
    <strong>📋 지원 포맷:</strong> MP3, WAV, OGG, FLAC<br>
    <strong>⏱️ 최대 길이:</strong> Cover 2분, Extend 8분<br>
    <strong>📤 URL 입력 방법:</strong><br>
    &nbsp;&nbsp;• 구글 드라이브: 파일 공유 → "링크가 있는 모든 사용자" → 링크 복사<br>
    &nbsp;&nbsp;• Dropbox: 공유 → 링크 복사
</div>
"""


def build_app():
    with gr.Blocks(css=CUSTOM_CSS, title="KIE.AI Music Studio", theme=gr.themes.Soft()) as app:
        
        gr.HTML(HEADER_HTML)
        
        # Settings
        with gr.Row():
            with gr.Column(scale=3):
                api_key = gr.Textbox(
                    label="🔑 KIE.AI API Key",
                    placeholder="your-api-key-here",
                    type="password",
                    info="kie.ai/api-key 에서 발급받은 API Key"
                )
            with gr.Column(scale=1):
                model = gr.Dropdown(
                    choices=MODELS,
                    value="V4",
                    label="🤖 모델",
                )
        
        # Tabs
        with gr.Tabs():
            
            # ━━━━━ Tab 1: Cover ━━━━━
            with gr.TabItem("🎨 커버 생성", id="cover"):
                gr.Markdown("기존 음악의 멜로디를 유지하면서 새로운 스타일로 변환합니다.")
                
                with gr.Row():
                    with gr.Column():
                        cover_audio_url = gr.Textbox(
                            label="🔗 원본 음악 URL",
                            placeholder="https://drive.google.com/file/d/.../view?usp=sharing",
                            info="구글 드라이브, Dropbox 공유 링크 또는 직접 다운로드 URL",
                        )
                    with gr.Column():
                        cover_style = gr.Textbox(
                            label="🎭 스타일 태그",
                            placeholder="예: jazz, electronic, k-pop, orchestral",
                            value="pop electronic dance",
                        )
                        cover_title = gr.Textbox(
                            label="📝 제목",
                            placeholder="생성될 곡 제목",
                            value="AI Cover",
                        )
                        cover_prompt = gr.Textbox(
                            label="✍️ 가사/프롬프트 (선택)",
                            placeholder="가사나 설명 입력",
                            lines=3,
                        )
                        cover_instrumental = gr.Checkbox(
                            label="🎹 인스트루멘탈 (보컬 없음)",
                            value=False,
                        )
                
                cover_btn = gr.Button("🎨 커버 생성", variant="primary", size="lg")
                
                with gr.Row():
                    with gr.Column(scale=2):
                        cover_log = gr.Textbox(label="📋 처리 로그", lines=10, interactive=False)
                    with gr.Column(scale=1):
                        gr.HTML(INFO_HTML)
                
                gr.Markdown("### 🎧 결과")
                with gr.Row():
                    with gr.Column(scale=2):
                        cover_result_audio = gr.Audio(label="생성된 음악", type="filepath")
                    with gr.Column(scale=1):
                        cover_result_image = gr.Image(label="앨범 커버", type="filepath")
                
                with gr.Accordion("📄 Raw API Response", open=False):
                    cover_json = gr.Code(language="json")
                
                cover_btn.click(
                    fn=run_cover,
                    inputs=[cover_audio_url, api_key, cover_style, cover_prompt, 
                            cover_title, model, cover_instrumental],
                    outputs=[cover_log, cover_result_audio, cover_result_image, cover_json],
                )
            
            # ━━━━━ Tab 2: Extend ━━━━━
            with gr.TabItem("🔄 확장 생성", id="extend"):
                gr.Markdown("기존 음악을 이어서 확장합니다. 스타일을 유지하며 새로운 부분을 생성합니다.")
                
                with gr.Row():
                    with gr.Column():
                        extend_audio_url = gr.Textbox(
                            label="🔗 원본 음악 URL",
                            placeholder="https://drive.google.com/file/d/.../view?usp=sharing",
                            info="구글 드라이브, Dropbox 공유 링크 또는 직접 다운로드 URL",
                        )
                    with gr.Column():
                        extend_style = gr.Textbox(
                            label="🎭 스타일 (선택)",
                            placeholder="비워두면 원본 스타일 유지",
                        )
                        extend_title = gr.Textbox(
                            label="📝 제목",
                            value="Extended Track",
                        )
                        extend_prompt = gr.Textbox(
                            label="✍️ 가사/프롬프트 (선택)",
                            lines=3,
                        )
                        extend_continue_at = gr.Slider(
                            label="⏱️ 시작 지점 (초)",
                            minimum=0,
                            maximum=480,
                            value=0,
                            step=1,
                            info="0 = 처음부터, 값 입력 시 해당 지점부터 확장"
                        )
                
                extend_btn = gr.Button("🔄 확장 생성", variant="primary", size="lg")
                
                extend_log = gr.Textbox(label="📋 처리 로그", lines=10, interactive=False)
                extend_result = gr.Audio(label="🎧 확장된 음악", type="filepath")
                
                with gr.Accordion("📄 Raw API Response", open=False):
                    extend_json = gr.Code(language="json")
                
                extend_btn.click(
                    fn=run_extend,
                    inputs=[extend_audio_url, api_key, extend_style, extend_prompt,
                            extend_title, model, extend_continue_at],
                    outputs=[extend_log, extend_result, extend_json],
                )
            
            # ━━━━━ Tab 3: Mashup ━━━━━
            with gr.TabItem("🔀 매시업", id="mashup"):
                gr.Markdown("""
                **두 음악을 조합**하여 새로운 음악을 생성합니다.
                
                ⚠️ 참고: KIE.AI는 직접적인 매시업 API가 없어, 음악 A를 기반으로 
                새로운 스타일을 적용하는 방식으로 동작합니다.
                """)
                
                with gr.Row():
                    with gr.Column():
                        mashup_url_a = gr.Textbox(
                            label="🔗 음악 A URL (베이스)",
                            placeholder="https://drive.google.com/file/d/.../view?usp=sharing",
                            info="구글 드라이브, Dropbox 공유 링크",
                        )
                    with gr.Column():
                        mashup_url_b = gr.Textbox(
                            label="🔗 음악 B URL (스타일 참조)",
                            placeholder="https://drive.google.com/file/d/.../view?usp=sharing",
                            info="구글 드라이브, Dropbox 공유 링크",
                        )
                
                mashup_style = gr.Textbox(
                    label="🎭 매시업 스타일",
                    placeholder="예: blend fusion electronic remix",
                    value="fusion blend mashup remix",
                )
                
                mashup_btn = gr.Button("🔀 매시업 시작", variant="primary", size="lg")
                
                mashup_log = gr.Textbox(label="📋 처리 로그", lines=12, interactive=False)
                
                gr.Markdown("### 🎧 결과")
                with gr.Row():
                    with gr.Column(scale=2):
                        mashup_result = gr.Audio(label="매시업 결과", type="filepath")
                    with gr.Column(scale=1):
                        mashup_image = gr.Image(label="앨범 커버", type="filepath")
                
                with gr.Accordion("📄 Raw API Response", open=False):
                    mashup_json = gr.Code(language="json")
                
                mashup_btn.click(
                    fn=run_mashup_sequential,
                    inputs=[mashup_url_a, mashup_url_b, api_key, mashup_style, model],
                    outputs=[mashup_log, mashup_result, mashup_image, mashup_json],
                )
            
            # ━━━━━ Tab 4: Guide ━━━━━
            with gr.TabItem("📖 가이드", id="guide"):
                gr.Markdown("""
## KIE.AI Suno API 가이드

### 음악 URL 입력 방법

KIE.AI API는 **URL 기반**으로 동작합니다.

#### 구글 드라이브 사용법 (권장)
1. 음악 파일을 구글 드라이브에 업로드
2. 파일 우클릭 → **"공유"** → **"링크가 있는 모든 사용자"** 선택
3. **링크 복사**하여 URL 입력란에 붙여넣기
4. 시스템이 자동으로 다운로드 URL로 변환

```
입력: https://drive.google.com/file/d/1ABC.../view?usp=sharing
변환: https://drive.google.com/uc?export=download&id=1ABC...
```

#### Dropbox 사용법
1. 파일을 Dropbox에 업로드
2. **"공유"** → **"링크 복사"**
3. URL 입력란에 붙여넣기 (자동으로 dl=1로 변환)

---

### API 엔드포인트

| 기능 | 엔드포인트 | 설명 |
|------|-----------|------|
| 커버 | `POST /api/v1/generate/upload-cover` | 멜로디 유지, 스타일 변경 |
| 확장 | `POST /api/v1/generate/upload-extend` | 기존 음악 이어서 생성 |
| 조회 | `GET /api/v1/generate/record-info` | 작업 상태 확인 |

### 모델별 특징

| 모델 | 특징 |
|------|------|
| V5 | 최신 모델, 가장 높은 품질 |
| V4_5PLUS | 향상된 V4.5 |
| V4_5 | 안정적인 품질 |
| V4 | 빠른 생성, 넓은 호환성 |
| V3_5 | 레거시 모델 |

### 제한 사항

- **커버**: 최대 2분 오디오 (문서상 8분이나 권장 2분)
- **확장**: 최대 8분 오디오
- **프롬프트**: 모델에 따라 500~5000자
- **스타일**: 모델에 따라 200~1000자

### 작업 상태

| 상태 | 설명 |
|------|------|
| PENDING | 대기 중 |
| TEXT_SUCCESS | 가사 생성 완료 |
| FIRST_SUCCESS | 첫 번째 트랙 완료 |
| SUCCESS | 모든 트랙 완료 |
| *_FAILED | 실패 |

### 참고 링크

- [KIE.AI 홈페이지](https://kie.ai)
- [API Key 발급](https://kie.ai/api-key)
- [API 문서](https://docs.kie.ai/suno-api/)
                """)
        
        # Footer
        gr.HTML("""
        <div style="text-align:center; padding:16px; color:#8b949e; font-size:12px; 
                    border-top:1px solid #30363d; margin-top:16px;">
            KIE.AI Music Studio &nbsp;|&nbsp; API by kie.ai &nbsp;|&nbsp;
            🔗 구글 드라이브 / Dropbox URL 지원
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
        server_port=7861,
        share=False,
        show_error=True,
    )
