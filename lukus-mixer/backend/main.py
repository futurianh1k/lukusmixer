"""
LUKUS Music Mixer - FastAPI Backend
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Demucs 기반 STEM 분리 API

실행:
    cd backend
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict
import asyncio
import uuid
import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Demucs 서비스 임포트
from demucs_service import DemucsService, DEMUCS_MODELS

app = FastAPI(
    title="LUKUS Music Mixer API",
    description="Demucs 기반 음악 STEM 분리 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서비스 인스턴스
demucs_service = DemucsService()

# 작업 저장소 (실제 서비스에서는 Redis 등 사용)
jobs: Dict[str, dict] = {}

# 출력 디렉토리
OUTPUT_DIR = Path(tempfile.gettempdir()) / "lukus_mixer_output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────

class SplitRequest(BaseModel):
    stems: List[str] = ["vocals", "drums", "bass", "other"]
    model: str = "htdemucs"


class MixRequest(BaseModel):
    prompt: str
    commands: Optional[List[dict]] = None


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: float
    message: str
    result: Optional[dict] = None
    logs: Optional[List[str]] = None
    created_at: str
    updated_at: str


class SystemInfo(BaseModel):
    cuda_available: bool
    demucs_available: bool
    audio_separator_available: bool = False
    models: List[dict]


# ──────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "LUKUS Music Mixer API", "version": "1.0.0"}


@app.get("/api/system", response_model=SystemInfo)
async def get_system_info():
    """시스템 정보 조회"""
    return SystemInfo(
        cuda_available=demucs_service.cuda_available,
        demucs_available=demucs_service.demucs_available,
        audio_separator_available=demucs_service.audio_separator_available,
        models=[
            {
                "id": k,
                "name": v["name"],
                "stems": v["stems"],
                "description": v.get("description", ""),
                "engine": v.get("engine", "demucs"),
            }
            for k, v in DEMUCS_MODELS.items()
        ]
    )


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """오디오 파일 업로드"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다")
    
    # 확장자 검증
    allowed_extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"지원하지 않는 형식입니다. 지원: {', '.join(allowed_extensions)}"
        )
    
    # 파일 저장
    file_id = str(uuid.uuid4())
    file_dir = OUTPUT_DIR / file_id
    file_dir.mkdir(exist_ok=True)
    
    file_path = file_dir / f"original{ext}"
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 오디오 정보 추출
    duration = demucs_service.get_audio_duration(str(file_path))
    
    return {
        "file_id": file_id,
        "filename": file.filename,
        "duration": duration,
        "size": len(content),
        "path": str(file_path)
    }


@app.post("/api/split/{file_id}")
async def split_stems(
    file_id: str, 
    request: SplitRequest,
    background_tasks: BackgroundTasks
):
    """STEM 분리 작업 시작"""
    file_dir = OUTPUT_DIR / file_id
    
    # 원본 파일 찾기
    original_file = None
    for ext in [".mp3", ".wav", ".flac", ".ogg", ".m4a"]:
        candidate = file_dir / f"original{ext}"
        if candidate.exists():
            original_file = candidate
            break
    
    if not original_file:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
    
    # 작업 생성
    job_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    jobs[job_id] = {
        "job_id": job_id,
        "file_id": file_id,
        "status": "pending",
        "progress": 0,
        "message": "대기 중...",
        "result": None,
        "created_at": now,
        "updated_at": now,
        "stems": request.stems,
        "model": request.model,
        "original_filename": original_file.name,
    }
    
    # 백그라운드 작업 시작
    background_tasks.add_task(
        process_split_job,
        job_id,
        str(original_file),
        request.model,
        request.stems
    )
    
    return {"job_id": job_id, "status": "pending"}


def _update_job(job_id, log=None, **kwargs):
    jobs[job_id].update(kwargs, updated_at=datetime.now().isoformat())
    if log:
        if "logs" not in jobs[job_id]:
            jobs[job_id]["logs"] = []
        jobs[job_id]["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {log}")
        print(f"  📋 {log}")


async def process_split_job(
    job_id: str, 
    audio_path: str, 
    model: str, 
    requested_stems: List[str]
):
    """백그라운드 STEM 분리 작업"""
    try:
        _update_job(job_id, status="processing", progress=10, message="STEM 분리 시작...",
                    log=f"STEM 분리 시작 (model={model})")

        # 원본 스펙트로그램 미리 생성
        _update_job(job_id, progress=15, message="원본 스펙트로그램 생성 중...",
                    log="원본 스펙트로그램 생성 중...")
        original_spec_path = Path(audio_path).parent / "original_spectrogram.png"
        try:
            await asyncio.to_thread(
                generate_spectrogram_image, audio_path, str(original_spec_path), "Original"
            )
        except Exception as e:
            print(f"⚠️ 원본 스펙트로그램 실패: {e}")

        # STEM 분리 실행
        engine = DEMUCS_MODELS.get(model, {}).get("engine", "demucs")
        engine_label = "BS-RoFormer + Demucs 체이닝" if engine == "chained" else f"Demucs ({model})"
        _update_job(job_id, progress=20, message="AI 처리 중...",
                    log=f"{engine_label} AI 처리 시작...")

        def _progress_log(msg):
            _update_job(job_id, log=msg)

        stem_paths = await asyncio.to_thread(
            demucs_service.separate,
            audio_path,
            model,
            None,
            True,
            _progress_log,
        )

        _update_job(job_id, progress=80, message="분리 완료, 스펙트로그램 생성 중...",
                    log=f"{engine_label} 완료 → {len(stem_paths)}개 스템 검출")
        
        # 결과 필터링 + 스펙트로그램 동시 생성
        result_stems = {}
        total = len([s for s in stem_paths if s in requested_stems])
        for i, (stem_name, stem_path) in enumerate(stem_paths.items()):
            if stem_name not in requested_stems:
                continue
            dur = demucs_service.get_audio_duration(stem_path)
            spec_path = Path(stem_path).parent / f"{stem_name}_spectrogram.png"
            
            _update_job(job_id, progress=80 + int(18 * (i + 1) / max(total, 1)),
                        message=f"스펙트로그램 생성 중... ({i+1}/{total})")
            try:
                await asyncio.to_thread(
                    generate_spectrogram_image, stem_path, str(spec_path), stem_name
                )
            except Exception as e:
                print(f"⚠️ {stem_name} 스펙트로그램 실패: {e}")

            result_stems[stem_name] = {
                "name": stem_name,
                "path": stem_path,
                "duration": dur,
                "spectrogram": str(spec_path) if spec_path.exists() else None,
            }
        
        _update_job(job_id, status="completed", progress=100,
                    message=f"완료! {len(result_stems)}개 스템 분리됨",
                    result=result_stems,
                    log=f"✅ 모든 작업 완료 ({len(result_stems)}개 스템 + 스펙트로그램)")
        
    except Exception as e:
        _update_job(job_id, status="failed", progress=0, message=f"오류: {str(e)}")


@app.get("/api/job/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """작업 상태 조회"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    job = jobs[job_id]
    return JobStatus(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        result=job.get("result"),
        logs=job.get("logs"),
        created_at=job["created_at"],
        updated_at=job["updated_at"]
    )


def _get_original_name(job_id: str) -> str:
    """원본 파일명(확장자 제외) 가져오기"""
    job = jobs.get(job_id, {})
    file_id = job.get("file_id", "")
    file_dir = OUTPUT_DIR / file_id
    for ext in [".mp3", ".wav", ".flac", ".ogg", ".m4a"]:
        candidate = file_dir / f"original{ext}"
        if candidate.exists():
            return candidate.stem
    return "audio"


@app.get("/api/download/{job_id}/{stem_name}")
async def download_stem(job_id: str, stem_name: str):
    """분리된 스템 다운로드 (파일명_stem.mp3 형식)"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="작업이 완료되지 않았습니다")
    
    if not job.get("result") or stem_name not in job["result"]:
        raise HTTPException(status_code=404, detail="스템을 찾을 수 없습니다")
    
    stem_path = job["result"][stem_name]["path"]
    if not os.path.exists(stem_path):
        raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다")
    
    original_name = job.get("original_filename", "audio").rsplit('.', 1)[0]
    download_name = f"{original_name}_{stem_name}.mp3"
    
    return FileResponse(
        stem_path,
        media_type="audio/mpeg",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
    )


@app.get("/api/download-all/{job_id}")
async def download_all_stems(job_id: str):
    """모든 스템을 ZIP으로 다운로드"""
    import zipfile
    
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    job = jobs[job_id]
    if job["status"] != "completed" or not job.get("result"):
        raise HTTPException(status_code=400, detail="작업이 완료되지 않았습니다")
    
    original_name = job.get("original_filename", "audio").rsplit('.', 1)[0]
    zip_path = OUTPUT_DIR / f"{job_id}_stems.zip"
    
    with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
        for stem_name, info in job["result"].items():
            if os.path.exists(info["path"]):
                zf.write(info["path"], f"{original_name}_{stem_name}.mp3")
    
    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename=f"{original_name}_stems.zip",
        headers={"Content-Disposition": f'attachment; filename="{original_name}_stems.zip"'}
    )


@app.get("/api/download-mix/{job_id}/{mix_id}")
async def download_mix(job_id: str, mix_id: str):
    """믹싱 결과 다운로드"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    mixes = jobs[job_id].get("mixes", {})
    if mix_id not in mixes:
        raise HTTPException(status_code=404, detail="믹싱 결과를 찾을 수 없습니다")
    
    mix_path = mixes[mix_id]["path"]
    if not os.path.exists(mix_path):
        raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다")
    
    original_name = jobs[job_id].get("original_filename", "audio").rsplit('.', 1)[0]
    download_name = f"{original_name}_mixed.mp3"
    
    return FileResponse(
        mix_path,
        media_type="audio/mpeg",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
    )


@app.get("/api/stream/{job_id}/{stem_name}")
async def stream_stem(job_id: str, stem_name: str):
    """분리된 스템 파일 반환 (seek 지원을 위해 FileResponse 사용)"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="작업이 완료되지 않았습니다")
    
    if not job.get("result") or stem_name not in job["result"]:
        raise HTTPException(status_code=404, detail="스템을 찾을 수 없습니다")
    
    stem_path = job["result"][stem_name]["path"]
    if not os.path.exists(stem_path):
        raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다")
    
    return FileResponse(stem_path, media_type="audio/mpeg")


# ──────────────────────────────────────────────
# Prompt Mixing
# 참고: demucs_local_mixing.py의 parse_mixing_prompt, mix_stems 로직 이식
# ──────────────────────────────────────────────

INSTRUMENT_MAP = {
    "보컬": "vocals", "목소리": "vocals", "노래": "vocals", "음성": "vocals",
    "드럼": "drums", "드럼스": "drums",
    "베이스": "bass", "베이스기타": "bass",
    "기타": "guitar", "일렉기타": "guitar", "어쿠스틱기타": "guitar", "전기기타": "guitar",
    "피아노": "piano", "키보드": "piano", "건반": "piano",
    "나머지": "other", "기타악기": "other", "그외": "other", "배경": "other",
}

SECTION_MAP = {
    "전주": (0, 15), "인트로": (0, 15), "도입부": (0, 15), "처음": (0, 15),
    "후주": (-30, -1), "아웃트로": (-30, -1), "끝부분": (-30, -1),
    "전체": (0, -1), "모두": (0, -1),
}

VOLUME_ACTION_MAP = {
    "키워": 6, "올려": 6, "크게": 6, "강조": 6, "높여": 6,
    "조금 키워": 3, "약간 키워": 3, "살짝 키워": 3,
    "줄여": -6, "작게": -6, "낮춰": -6,
    "조금 줄여": -3, "약간 줄여": -3,
    "음소거": -100, "뮤트": -100, "없애": -100, "제거": -100,
}

import re


def parse_mixing_prompt(prompt: str, total_duration: float = 180,
                        available_stems: List[str] = None) -> List[dict]:
    """룰베이스 프롬프트 파싱 → 믹싱 명령 리스트"""
    if available_stems is None:
        available_stems = ["vocals", "drums", "bass", "other", "guitar", "piano"]

    commands = []
    lines = prompt.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        found_instrument = None
        for kr_name, en_name in INSTRUMENT_MAP.items():
            if kr_name in line and en_name in available_stems:
                found_instrument = en_name
                break
        if not found_instrument:
            continue

        start_sec, end_sec = 0.0, float(total_duration)

        time_pattern = r'(\d+)분?(\d+)?초?\s*[~\-부터]\s*(\d+)분?(\d+)?초?[까지]?'
        time_match = re.search(time_pattern, line)

        if time_match:
            g = time_match.groups()
            start_sec = float(int(g[0]) * 60 + int(g[1])) if g[1] else float(int(g[0]))
            end_sec = float(int(g[2]) * 60 + int(g[3])) if g[3] else float(int(g[2]))
        else:
            for section_name, (s, e) in SECTION_MAP.items():
                if section_name in line:
                    start_sec = max(0.0, total_duration + s) if s < 0 else float(s)
                    end_sec = total_duration if e < 0 else float(e)
                    break

        volume_db = 0.0
        for action, db in VOLUME_ACTION_MAP.items():
            if action in line:
                volume_db = float(db)
                break

        commands.append({
            "instrument": found_instrument,
            "start_sec": start_sec,
            "end_sec": end_sec,
            "volume_db": volume_db,
            "original_text": line,
        })

    return commands


def execute_mix(stem_paths: Dict[str, str], commands: List[dict]) -> str:
    """
    pydub으로 스템별 볼륨 조절 후 믹싱
    참고: pydub - https://github.com/jiaaro/pydub
    """
    from pydub import AudioSegment

    stems = {}
    base_length = 0
    for name, path in stem_paths.items():
        if path and os.path.exists(path):
            audio = AudioSegment.from_file(path)
            stems[name] = audio
            base_length = max(base_length, len(audio))

    if not stems:
        raise Exception("유효한 스템이 없습니다")

    for cmd in commands:
        inst = cmd["instrument"]
        if inst not in stems:
            continue
        audio = stems[inst]
        s_ms = int(cmd["start_sec"] * 1000)
        e_ms = int(cmd["end_sec"] * 1000) if cmd["end_sec"] > 0 else len(audio)

        before = audio[:s_ms]
        target = audio[s_ms:e_ms]
        after = audio[e_ms:]

        if cmd["volume_db"] <= -100:
            target = AudioSegment.silent(duration=len(target))
        else:
            target = target + cmd["volume_db"]

        stems[inst] = before + target + after

    result = AudioSegment.silent(duration=base_length)
    for audio in stems.values():
        result = result.overlay(audio)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=str(OUTPUT_DIR))
    result.export(tmp.name, format='mp3', bitrate='320k')
    return tmp.name


@app.post("/api/mix/{job_id}")
async def mix_stems_api(job_id: str, request: MixRequest):
    """프롬프트 기반 믹싱 실행"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    job = jobs[job_id]
    if job["status"] != "completed" or not job.get("result"):
        raise HTTPException(status_code=400, detail="STEM 분리가 완료되지 않았습니다")

    stem_paths = {name: info["path"] for name, info in job["result"].items()}
    available_stems = list(stem_paths.keys())

    # 원본 파일에서 총 길이 추출
    file_id = job.get("file_id", "")
    total_duration = 180.0
    for info in job["result"].values():
        if info.get("duration"):
            total_duration = info["duration"]
            break

    # 프롬프트 파싱
    if request.commands:
        commands = request.commands
    else:
        commands = parse_mixing_prompt(request.prompt, total_duration, available_stems)

    if not commands:
        raise HTTPException(status_code=400, detail="인식된 명령이 없습니다. 프롬프트 형식을 확인해주세요.")

    try:
        result_path = await asyncio.to_thread(execute_mix, stem_paths, commands)
        mix_id = str(uuid.uuid4())

        if "mixes" not in jobs[job_id]:
            jobs[job_id]["mixes"] = {}
        jobs[job_id]["mixes"][mix_id] = {
            "path": result_path,
            "commands": commands,
            "prompt": request.prompt,
        }

        return {
            "mix_id": mix_id,
            "commands": commands,
            "stream_url": f"/api/stream-mix/{job_id}/{mix_id}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/parse-prompt/{job_id}")
async def parse_prompt_api(job_id: str, request: MixRequest):
    """프롬프트만 파싱하여 미리보기 (실행 없이)"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    job = jobs[job_id]
    available_stems = list(job.get("result", {}).keys())

    total_duration = 180.0
    if job.get("result"):
        for info in job["result"].values():
            if info.get("duration"):
                total_duration = info["duration"]
                break

    commands = parse_mixing_prompt(request.prompt, total_duration, available_stems)
    return {"commands": commands}


@app.get("/api/stream-mix/{job_id}/{mix_id}")
async def stream_mix(job_id: str, mix_id: str):
    """믹싱 결과 파일 반환 (seek 지원을 위해 FileResponse 사용)"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    mixes = jobs[job_id].get("mixes", {})
    if mix_id not in mixes:
        raise HTTPException(status_code=404, detail="믹싱 결과를 찾을 수 없습니다")

    mix_path = mixes[mix_id]["path"]
    if not os.path.exists(mix_path):
        raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다")

    return FileResponse(mix_path, media_type="audio/mpeg")


@app.get("/api/spectrogram/{job_id}/{stem_name}")
async def get_spectrogram(job_id: str, stem_name: str):
    """스템의 스펙트로그램 이미지 생성 및 반환"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="작업이 완료되지 않았습니다")
    
    if not job.get("result") or stem_name not in job["result"]:
        raise HTTPException(status_code=404, detail="스템을 찾을 수 없습니다")
    
    stem_path = job["result"][stem_name]["path"]
    if not os.path.exists(stem_path):
        raise HTTPException(status_code=404, detail="파일이 존재하지 않습니다")
    
    # 캐시된 스펙트로그램 확인
    cache_path = Path(stem_path).parent / f"{stem_name}_spectrogram.png"
    if cache_path.exists():
        return FileResponse(str(cache_path), media_type="image/png")
    
    # 스펙트로그램 생성
    try:
        spectrogram_path = await asyncio.to_thread(
            generate_spectrogram_image, stem_path, str(cache_path), stem_name
        )
        return FileResponse(spectrogram_path, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스펙트로그램 생성 실패: {str(e)}")


@app.get("/api/spectrogram-original/{file_id}")
async def get_original_spectrogram(file_id: str):
    """원본 파일의 스펙트로그램 이미지 생성 및 반환"""
    file_dir = OUTPUT_DIR / file_id
    
    original_file = None
    for ext in [".mp3", ".wav", ".flac", ".ogg", ".m4a"]:
        candidate = file_dir / f"original{ext}"
        if candidate.exists():
            original_file = candidate
            break
    
    if not original_file:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
    
    cache_path = file_dir / "original_spectrogram.png"
    if cache_path.exists():
        return FileResponse(str(cache_path), media_type="image/png")
    
    try:
        spectrogram_path = await asyncio.to_thread(
            generate_spectrogram_image, str(original_file), str(cache_path), "Original"
        )
        return FileResponse(spectrogram_path, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스펙트로그램 생성 실패: {str(e)}")


import time as _time

_SPEC_COLORS = {
    "vocals": "#22c55e", "drums": "#f97316", "bass": "#8b5cf6",
    "guitar": "#06b6d4", "piano": "#ec4899", "other": "#64748b",
    "Original": "#f97316",
}


def generate_spectrogram_image(audio_path: str, output_path: str, label: str) -> str:
    """
    librosa + matplotlib로 스펙트로그램 PNG 생성 (최적화 버전)
    - sr=8000 (22050→8000: 로드 시간 ~3배 단축)
    - n_mels=64 (128→64: 연산량 절반)
    - dpi=72, 축 숨김으로 렌더링 최적화
    참고: librosa specshow - https://librosa.org/doc/latest/generated/librosa.display.specshow.html
    """
    t0 = _time.time()
    import librosa
    import librosa.display
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    y, sr = librosa.load(audio_path, sr=8000, mono=True)
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmax=4000, hop_length=256)
    S_dB = librosa.power_to_db(S, ref=np.max)

    fig, ax = plt.subplots(1, 1, figsize=(10, 1.5), dpi=72)
    fig.patch.set_facecolor('#0f172a')
    ax.set_facecolor('#0f172a')

    accent = _SPEC_COLORS.get(label, "#f97316")
    cmap = LinearSegmentedColormap.from_list(
        'c', ['#0f172a', accent + '40', accent + '99', accent], N=128
    )

    librosa.display.specshow(S_dB, sr=sr, x_axis='time', y_axis=None,
                             ax=ax, cmap=cmap, fmax=4000, hop_length=256)
    ax.set_ylabel('')
    ax.set_yticks([])
    ax.set_xlabel('')

    audio_duration = len(y) / sr
    if audio_duration <= 30:
        tick_interval = 2
    elif audio_duration <= 60:
        tick_interval = 5
    elif audio_duration <= 180:
        tick_interval = 10
    else:
        tick_interval = 15
    import matplotlib.ticker as mticker
    ax.xaxis.set_major_locator(mticker.MultipleLocator(tick_interval))
    ax.xaxis.set_minor_locator(mticker.MultipleLocator(tick_interval / 2))

    ax.tick_params(axis='x', which='major', colors='#e2e8f0', labelsize=9,
                   length=4, pad=2, width=0.8)
    ax.tick_params(axis='x', which='minor', colors='#64748b',
                   length=2, width=0.5)

    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.subplots_adjust(left=0.01, right=0.99, top=1, bottom=0.22)
    plt.savefig(output_path, facecolor='#0f172a', edgecolor='none',
                pad_inches=0)
    plt.close(fig)

    print(f"  📊 스펙트로그램 생성: {label} ({_time.time() - t0:.1f}s)")
    return output_path


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    """작업 삭제"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    job = jobs[job_id]
    if job.get("result"):
        for stem_info in job["result"].values():
            try:
                if os.path.exists(stem_info["path"]):
                    os.remove(stem_info["path"])
            except:
                pass
    
    del jobs[job_id]
    return {"message": "삭제 완료"}


# ──────────────────────────────────────────────
# Library
# ──────────────────────────────────────────────

LIBRARY_DIR = OUTPUT_DIR / "library"
LIBRARY_DIR.mkdir(exist_ok=True)
library_items: List[dict] = []


@app.get("/api/library")
async def get_library():
    """라이브러리 목록 조회"""
    return {"items": library_items}


@app.post("/api/library/add")
async def add_to_library(data: dict):
    """결과물을 라이브러리에 추가"""
    job_id = data.get("job_id")
    mix_id = data.get("mix_id")

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    job = jobs[job_id]
    original_name = job.get("original_filename", "audio").rsplit('.', 1)[0]

    item_id = str(uuid.uuid4())
    item = {
        "id": item_id,
        "name": original_name,
        "job_id": job_id,
        "created_at": datetime.now().isoformat(),
        "stems": {},
        "mix": None,
    }

    # 스템 파일 복사
    if job.get("result"):
        dest_dir = LIBRARY_DIR / item_id
        dest_dir.mkdir(exist_ok=True)
        for stem_name, info in job["result"].items():
            if os.path.exists(info["path"]):
                dest = dest_dir / f"{original_name}_{stem_name}.mp3"
                shutil.copy2(info["path"], str(dest))
                item["stems"][stem_name] = str(dest)

    # 믹스 결과 복사
    if mix_id and job.get("mixes", {}).get(mix_id):
        mix_path = job["mixes"][mix_id]["path"]
        if os.path.exists(mix_path):
            dest_dir = LIBRARY_DIR / item_id
            dest_dir.mkdir(exist_ok=True)
            dest = dest_dir / f"{original_name}_mixed.mp3"
            shutil.copy2(mix_path, str(dest))
            item["mix"] = str(dest)

    library_items.append(item)
    return {"item": item, "message": f"'{original_name}' 라이브러리에 추가됨"}


# ──────────────────────────────────────────────
# Prompt History
# ──────────────────────────────────────────────

HISTORY_DIR = OUTPUT_DIR / "prompt_history"
HISTORY_DIR.mkdir(exist_ok=True)


@app.post("/api/prompt-history/save")
async def save_prompt_history(data: dict):
    """프롬프트를 파일로 저장 (파일명_%datetime% 형식)"""
    prompt = data.get("prompt", "").strip()
    original_filename = data.get("original_filename", "prompt")
    mix_result_info = data.get("mix_result_info", "")

    if not prompt:
        raise HTTPException(status_code=400, detail="프롬프트가 비어있습니다")

    base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_{ts}.txt"
    filepath = HISTORY_DIR / filename

    content_lines = [
        f"# LUKUS Prompt History",
        f"# File: {original_filename}",
        f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"[Prompt]",
        prompt,
    ]
    if mix_result_info:
        content_lines.extend(["", "[Mix Result]", mix_result_info])

    filepath.write_text("\n".join(content_lines), encoding="utf-8")

    return {
        "filename": filename,
        "path": str(filepath),
        "message": f"프롬프트 저장됨: {filename}",
    }


@app.get("/api/prompt-history")
async def list_prompt_history():
    """저장된 프롬프트 히스토리 목록"""
    items = []
    for f in sorted(HISTORY_DIR.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
        text = f.read_text(encoding="utf-8")
        prompt_section = ""
        in_prompt = False
        for line in text.split("\n"):
            if line.strip() == "[Prompt]":
                in_prompt = True
                continue
            if line.strip().startswith("[") and in_prompt:
                break
            if in_prompt:
                prompt_section += line + "\n"

        items.append({
            "filename": f.name,
            "prompt": prompt_section.strip(),
            "created_at": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "size": f.stat().st_size,
        })
    return {"items": items}


@app.delete("/api/prompt-history/{filename}")
async def delete_prompt_history(filename: str):
    """프롬프트 히스토리 삭제"""
    filepath = HISTORY_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
    filepath.unlink()
    return {"message": f"삭제됨: {filename}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
