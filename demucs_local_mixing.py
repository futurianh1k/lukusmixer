"""
🎛️ Demucs Local Music Mixing Demo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
로컬 Demucs 기반 음악 믹싱 도구 (API 비용 없음!)

파이프라인:
┌─────────────────────────────────────────────────────────────────┐
│  [로컬 Demucs]       [룰베이스]           [로컬 처리]           │
│  ① STEM 분리     →  ② 프롬프트 파싱  →  ③ 볼륨 조절          │
│  (4~6 트랙)          "전주 드럼 키워줘"     (pydub)             │
│  - vocals            → instrument: drums                        │
│  - drums             → section: 0~15s                           │
│  - bass              → action: +6dB                             │
│  - other                                                        │
│  (+ guitar, piano)                    ④ 트랙 합성              │
│                                       → 최종 출력               │
└─────────────────────────────────────────────────────────────────┘

장점:
- API 비용 없음 (완전 무료)
- 로컬 파일 직접 입력 가능
- GPU 가속 지원 (CUDA)

실행:
    pip install gradio demucs pydub librosa matplotlib numpy
    python demucs_local_mixing.py

참고: https://github.com/adefossez/demucs
"""

import gradio as gr
import subprocess
import shutil
import time
import json
import os
import re
import tempfile
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass

# 오디오 처리 라이브러리 (lazy import)
try:
    import librosa
    import librosa.display
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("⚠️ librosa 미설치: pip install librosa")

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("⚠️ pydub 미설치: pip install pydub")

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    
    # 폰트 설정 (영문 사용으로 호환성 확보)
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False
    
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️ matplotlib 미설치: pip install matplotlib")

try:
    import torch
    TORCH_AVAILABLE = True
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    TORCH_AVAILABLE = False
    CUDA_AVAILABLE = False
    print("⚠️ torch 미설치: pip install torch")

# demucs 설치 확인
try:
    import demucs.separate
    DEMUCS_AVAILABLE = True
except ImportError:
    DEMUCS_AVAILABLE = False
    print("⚠️ demucs 미설치: pip install -U demucs")


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

# Demucs 모델 옵션
DEMUCS_MODELS = {
    "htdemucs": {
        "name": "Hybrid Transformer Demucs (기본)",
        "stems": ["vocals", "drums", "bass", "other"],
        "description": "4 스템 분리, 빠른 속도",
    },
    "htdemucs_ft": {
        "name": "Hybrid Transformer Demucs (Fine-tuned)",
        "stems": ["vocals", "drums", "bass", "other"],
        "description": "4 스템 분리, 최고 품질 (4배 느림)",
    },
    "htdemucs_6s": {
        "name": "6-Source Demucs",
        "stems": ["vocals", "drums", "bass", "guitar", "piano", "other"],
        "description": "6 스템 분리 (기타, 피아노 추가)",
    },
}

# STEM 한글 라벨
STEM_LABELS_KR = {
    "vocals": "보컬",
    "drums": "드럼",
    "bass": "베이스",
    "guitar": "기타",
    "piano": "피아노",
    "other": "기타 악기",
}

# STEM 영문 라벨 (폰트 호환성)
STEM_LABELS_EN = {
    "vocals": "Vocals",
    "drums": "Drums",
    "bass": "Bass",
    "guitar": "Guitar",
    "piano": "Piano",
    "other": "Other",
}

# 볼륨 프리셋 (dB)
VOLUME_PRESETS = {
    "크게 (+6dB)": 6,
    "조금 크게 (+3dB)": 3,
    "원본 (0dB)": 0,
    "조금 작게 (-3dB)": -3,
    "작게 (-6dB)": -6,
    "음소거 (-inf)": -100,
}


# ──────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────

@dataclass
class MixingCommand:
    """파싱된 믹싱 명령"""
    instrument: str
    start_sec: float
    end_sec: float
    volume_db: float
    original_text: str


# ──────────────────────────────────────────────
# URL Helpers
# ──────────────────────────────────────────────

def convert_gdrive_url(url: str) -> str:
    """구글 드라이브 공유 URL을 직접 다운로드 URL로 변환"""
    if "uc?export=download" in url:
        return url
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url


def convert_dropbox_url(url: str) -> str:
    """Dropbox 공유 URL을 직접 다운로드 URL로 변환"""
    if "dropbox.com" in url:
        if "dl=0" in url:
            return url.replace("dl=0", "dl=1")
        elif "dl=1" not in url:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}dl=1"
    return url


def prepare_url(url: str) -> str:
    """URL 준비 및 변환"""
    url = url.strip()
    if "drive.google.com" in url:
        return convert_gdrive_url(url)
    if "dropbox.com" in url:
        return convert_dropbox_url(url)
    return url


def download_audio_from_url(url: str, timeout: int = 120) -> str:
    """URL에서 오디오 파일 다운로드"""
    import requests
    
    url = prepare_url(url)
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    
    # 확장자 추출
    content_type = resp.headers.get('content-type', '')
    if 'wav' in content_type or url.endswith('.wav'):
        suffix = '.wav'
    elif 'flac' in content_type or url.endswith('.flac'):
        suffix = '.flac'
    else:
        suffix = '.mp3'
    
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in resp.iter_content(chunk_size=8192):
        tmp.write(chunk)
    tmp.close()
    return tmp.name


# ──────────────────────────────────────────────
# Audio Processing (Local)
# ──────────────────────────────────────────────

def generate_spectrogram(audio_path: str, title: str = "Spectrogram", duration: float = None) -> str:
    """오디오 파일의 스펙트로그램 이미지 생성"""
    if not LIBROSA_AVAILABLE or not MATPLOTLIB_AVAILABLE:
        return None
    
    try:
        y, sr = librosa.load(audio_path, sr=22050)
        if duration is None:
            duration = len(y) / sr
        
        plt.figure(figsize=(14, 4))
        D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='hz', cmap='magma')
        plt.colorbar(format='%+2.0f dB')
        plt.title(f"Original Music ({duration:.1f}s)", fontsize=12, fontweight='bold')
        plt.xlabel('Time (sec)')
        plt.ylabel('Frequency (Hz)')
        plt.tight_layout()
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(tmp.name, dpi=100, bbox_inches='tight')
        plt.close()
        
        return tmp.name
    except Exception as e:
        print(f"[DEBUG] 스펙트로그램 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_stem_spectrogram(stem_name: str, audio_path: str, duration: float = None) -> str:
    """개별 스템의 스펙트로그램 이미지 생성"""
    if not LIBROSA_AVAILABLE or not MATPLOTLIB_AVAILABLE:
        return None
    
    try:
        print(f"[DEBUG] {stem_name}: 스펙트로그램 생성 시작 - {audio_path}")
        
        y, sr = librosa.load(audio_path, sr=22050)
        stem_duration = len(y) / sr
        if duration is None:
            duration = stem_duration
        
        plt.figure(figsize=(14, 3))
        D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
        
        # 스템별 색상 맵
        cmap_map = {
            "vocals": "viridis",
            "drums": "plasma",
            "bass": "inferno",
            "guitar": "cividis",
            "piano": "coolwarm",
            "other": "RdYlBu",
        }
        cmap = cmap_map.get(stem_name, "viridis")
        
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='hz', cmap=cmap)
        plt.colorbar(format='%+2.0f dB')
        
        en_name = STEM_LABELS_EN.get(stem_name, stem_name)
        plt.title(f"{en_name} ({stem_duration:.1f}s)", fontsize=11, fontweight='bold')
        plt.xlabel('Time (sec)')
        plt.ylabel('Frequency (Hz)')
        plt.tight_layout()
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(tmp.name, dpi=100, bbox_inches='tight')
        plt.close()
        
        print(f"[DEBUG] {stem_name}: 스펙트로그램 생성 완료 - {tmp.name}")
        return tmp.name
    except Exception as e:
        print(f"[DEBUG] {stem_name}: 스펙트로그램 생성 오류 - {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_all_spectrograms(audio_path: str, stem_paths: Dict[str, str]) -> str:
    """원본 + 모든 스템의 스펙트로그램을 하나의 이미지로 생성"""
    if not LIBROSA_AVAILABLE or not MATPLOTLIB_AVAILABLE:
        return None
    
    try:
        all_paths = {"Original": audio_path}
        all_paths.update({STEM_LABELS_EN.get(k, k): v for k, v in stem_paths.items() if v and os.path.exists(v)})
        
        n_plots = len(all_paths)
        fig, axes = plt.subplots(n_plots, 1, figsize=(14, 3 * n_plots))
        
        if n_plots == 1:
            axes = [axes]
        
        colors = ['magma', 'viridis', 'plasma', 'inferno', 'cividis', 'coolwarm', 'RdYlBu']
        
        for idx, (ax, (name, path)) in enumerate(zip(axes, all_paths.items())):
            y, sr = librosa.load(path, sr=22050)
            duration = len(y) / sr
            D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
            cmap = colors[idx % len(colors)]
            img = librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='hz', cmap=cmap, ax=ax)
            ax.set_title(f"{name} ({duration:.1f}s)", fontsize=11, fontweight='bold')
            ax.set_xlabel('Time (sec)')
            fig.colorbar(img, ax=ax, format='%+2.0f dB')
        
        plt.tight_layout()
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(tmp.name, dpi=100, bbox_inches='tight')
        plt.close()
        
        return tmp.name
    except Exception as e:
        print(f"[DEBUG] 통합 스펙트로그램 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_audio_duration(audio_path: str) -> float:
    """오디오 길이(초) 반환"""
    if LIBROSA_AVAILABLE:
        try:
            y, sr = librosa.load(audio_path, sr=None)
            return len(y) / sr
        except:
            pass
    
    if PYDUB_AVAILABLE:
        try:
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except:
            pass
    
    return 0


def adjust_volume(audio_path: str, volume_db: float, start_sec: float = 0, end_sec: float = -1) -> str:
    """
    오디오의 특정 구간 볼륨 조절
    
    Args:
        audio_path: 오디오 파일 경로
        volume_db: 볼륨 조절량 (dB)
        start_sec: 시작 시간 (초)
        end_sec: 종료 시간 (초, -1이면 끝까지)
    
    Returns:
        조절된 오디오 파일 경로
    """
    if not PYDUB_AVAILABLE:
        raise Exception("pydub가 설치되지 않았습니다")
    
    audio = AudioSegment.from_file(audio_path)
    
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000) if end_sec > 0 else len(audio)
    
    # 구간 분할
    before = audio[:start_ms]
    target = audio[start_ms:end_ms]
    after = audio[end_ms:]
    
    # 볼륨 조절
    if volume_db <= -100:
        target = AudioSegment.silent(duration=len(target))
    else:
        target = target + volume_db
    
    # 재합성
    result = before + target + after
    
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
    result.export(tmp.name, format='mp3')
    return tmp.name


def mix_stems(stem_paths: Dict[str, str], adjustments: List[MixingCommand] = None) -> str:
    """
    여러 스템을 믹싱
    
    Args:
        stem_paths: {stem_name: file_path} 딕셔너리
        adjustments: 볼륨 조절 명령 리스트
    
    Returns:
        믹싱된 오디오 파일 경로
    """
    if not PYDUB_AVAILABLE:
        raise Exception("pydub가 설치되지 않았습니다")
    
    if not stem_paths:
        raise Exception("믹싱할 스템이 없습니다")
    
    # 스템 로드
    stems = {}
    base_length = 0
    
    for name, path in stem_paths.items():
        if path and os.path.exists(path):
            audio = AudioSegment.from_file(path)
            stems[name] = audio
            if len(audio) > base_length:
                base_length = len(audio)
    
    if not stems:
        raise Exception("유효한 스템이 없습니다")
    
    # 볼륨 조절 적용
    if adjustments:
        for cmd in adjustments:
            if cmd.instrument in stems:
                audio = stems[cmd.instrument]
                start_ms = int(cmd.start_sec * 1000)
                end_ms = int(cmd.end_sec * 1000) if cmd.end_sec > 0 else len(audio)
                
                before = audio[:start_ms]
                target = audio[start_ms:end_ms]
                after = audio[end_ms:]
                
                if cmd.volume_db <= -100:
                    target = AudioSegment.silent(duration=len(target))
                else:
                    target = target + cmd.volume_db
                
                stems[cmd.instrument] = before + target + after
    
    # 믹싱 (오버레이)
    result = AudioSegment.silent(duration=base_length)
    for name, audio in stems.items():
        result = result.overlay(audio)
    
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
    result.export(tmp.name, format='mp3')
    return tmp.name


# ──────────────────────────────────────────────
# Demucs STEM Separation (Local)
# ──────────────────────────────────────────────

def run_demucs_separation(
    audio_path: str,
    model: str = "htdemucs",
    output_dir: str = None,
    mp3_output: bool = True,
    device: str = "auto",
) -> Dict[str, str]:
    """
    Demucs로 STEM 분리 실행
    
    Args:
        audio_path: 입력 오디오 파일 경로
        model: 모델 이름 (htdemucs, htdemucs_ft, htdemucs_6s)
        output_dir: 출력 디렉토리 (None이면 자동 생성)
        mp3_output: MP3로 출력할지 여부
        device: 디바이스 (auto, cuda, cpu)
    
    Returns:
        {stem_name: file_path} 딕셔너리
    """
    if not DEMUCS_AVAILABLE:
        raise Exception("demucs가 설치되지 않았습니다. pip install -U demucs")
    
    if not os.path.exists(audio_path):
        raise Exception(f"파일을 찾을 수 없습니다: {audio_path}")
    
    # 출력 디렉토리 설정
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="demucs_")
    
    # 디바이스 결정
    if device == "auto":
        device = "cuda" if CUDA_AVAILABLE else "cpu"
    
    # demucs 명령어 구성
    cmd_args = [
        "-n", model,
        "-o", output_dir,
        "-d", device,
    ]
    
    if mp3_output:
        cmd_args.extend(["--mp3", "--mp3-bitrate", "320"])
    
    cmd_args.append(audio_path)
    
    # demucs 실행
    print(f"🎛️ Demucs 실행 중: {' '.join(['demucs'] + cmd_args)}")
    
    try:
        demucs.separate.main(cmd_args)
    except SystemExit:
        pass  # demucs가 sys.exit() 호출하는 경우
    
    # 결과 파일 경로 생성
    audio_name = Path(audio_path).stem
    output_subdir = Path(output_dir) / model / audio_name
    
    ext = ".mp3" if mp3_output else ".wav"
    
    stems = {}
    model_info = DEMUCS_MODELS.get(model, DEMUCS_MODELS["htdemucs"])
    
    for stem in model_info["stems"]:
        stem_path = output_subdir / f"{stem}{ext}"
        if stem_path.exists():
            stems[stem] = str(stem_path)
    
    return stems


# ──────────────────────────────────────────────
# Prompt Parsing (Rule-based)
# ──────────────────────────────────────────────

def parse_mixing_prompt(prompt: str, total_duration: float = 180, available_stems: List[str] = None) -> List[MixingCommand]:
    """
    프롬프트를 파싱하여 믹싱 명령 추출
    
    예시:
    - "전주 드럼 키워줘" → drums, 0~15s, +6dB
    - "30초~40초 피아노 키워줘" → piano, 30~40s, +6dB
    - "기타 작게 해줘" → guitar, 0~end, -6dB
    - "1분30초부터 2분까지 베이스 음소거" → bass, 90~120s, -inf
    
    Returns:
        MixingCommand 리스트
    """
    commands = []
    
    # 사용 가능한 스템 (기본값)
    if available_stems is None:
        available_stems = ["vocals", "drums", "bass", "other", "guitar", "piano"]
    
    # 악기 이름 매핑 (한글 → 영문)
    instrument_map = {
        "보컬": "vocals", "목소리": "vocals", "노래": "vocals", "음성": "vocals",
        "드럼": "drums", "드럼스": "drums",
        "베이스": "bass", "베이스기타": "bass",
        "기타": "guitar", "일렉기타": "guitar", "어쿠스틱기타": "guitar", "전기기타": "guitar",
        "피아노": "piano", "키보드": "piano", "건반": "piano",
        "나머지": "other", "기타악기": "other", "그외": "other", "배경": "other",
    }
    
    # 구간 패턴 매핑
    section_map = {
        "전주": (0, 15),
        "인트로": (0, 15),
        "도입부": (0, 15),
        "처음": (0, 15),
        "후주": (-30, -1),  # 마지막 30초
        "아웃트로": (-30, -1),
        "끝부분": (-30, -1),
        "전체": (0, -1),
        "모두": (0, -1),
    }
    
    # 볼륨 액션 매핑
    volume_map = {
        "키워": 6, "올려": 6, "크게": 6, "강조": 6, "높여": 6,
        "조금 키워": 3, "약간 키워": 3, "살짝 키워": 3,
        "줄여": -6, "작게": -6, "낮춰": -6,
        "조금 줄여": -3, "약간 줄여": -3,
        "음소거": -100, "뮤트": -100, "없애": -100, "제거": -100,
    }
    
    # 프롬프트를 줄 단위로 분리
    lines = prompt.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 악기 찾기
        found_instrument = None
        for kr_name, en_name in instrument_map.items():
            if kr_name in line and en_name in available_stems:
                found_instrument = en_name
                break
        
        if not found_instrument:
            continue
        
        # 구간 찾기
        start_sec, end_sec = 0, -1
        
        # 시간 패턴: "30초~40초", "1분30초~2분", "30초부터 40초까지"
        time_pattern = r'(\d+)분?(\d+)?초?\s*[~\-부터]\s*(\d+)분?(\d+)?초?[까지]?'
        time_match = re.search(time_pattern, line)
        
        if time_match:
            groups = time_match.groups()
            if groups[1]:  # X분Y초
                start_sec = int(groups[0]) * 60 + int(groups[1])
            else:
                start_sec = int(groups[0])
            
            if groups[3]:  # X분Y초
                end_sec = int(groups[2]) * 60 + int(groups[3])
            elif groups[2]:
                end_sec = int(groups[2])
        else:
            # 구간 키워드 찾기
            for section_name, (s, e) in section_map.items():
                if section_name in line:
                    if s < 0:
                        start_sec = max(0, total_duration + s)
                        end_sec = total_duration if e < 0 else e
                    else:
                        start_sec = s
                        end_sec = total_duration if e < 0 else e
                    break
        
        # 볼륨 액션 찾기
        volume_db = 0
        for action, db in volume_map.items():
            if action in line:
                volume_db = db
                break
        
        # 명령 생성
        if end_sec < 0:
            end_sec = total_duration
        
        cmd = MixingCommand(
            instrument=found_instrument,
            start_sec=start_sec,
            end_sec=end_sec,
            volume_db=volume_db,
            original_text=line
        )
        commands.append(cmd)
    
    return commands


# ──────────────────────────────────────────────
# Main Pipeline
# ──────────────────────────────────────────────

def run_stem_separation(
    audio_file,
    audio_url: str,
    model_choice: str,
    progress=gr.Progress()
):
    """STEM 분리 파이프라인"""
    logs = []
    
    def log(msg):
        logs.append(msg)
        return "\n".join(logs)
    
    # 입력 확인
    if not audio_file and not audio_url:
        yield "❌ 오디오 파일을 업로드하거나 URL을 입력해주세요.", None, None, {}, []
        return
    
    if not DEMUCS_AVAILABLE:
        yield "❌ demucs가 설치되지 않았습니다. `pip install -U demucs`", None, None, {}, []
        return
    
    try:
        # Step 1: 입력 처리
        progress(0.05, desc="📂 입력 처리 중...")
        
        if audio_file:
            log_text = log("📂 [1/4] 로컬 파일 사용")
            local_audio = audio_file
        else:
            log_text = log("📂 [1/4] URL에서 다운로드 중...")
            yield log_text, None, None, {}, []
            local_audio = download_audio_from_url(audio_url)
        
        duration = get_audio_duration(local_audio)
        log_text = log(f"  ✅ 파일 준비 완료: {duration:.1f}초")
        print(f"[DEBUG] 오디오 길이: {duration:.1f}초")
        yield log_text, None, None, {}, []
        
        # Step 2: 원본 스펙트로그램 생성
        progress(0.1, desc="📊 스펙트로그램 생성 중...")
        log_text = log("📊 [2/4] 원본 스펙트로그램 생성 중...")
        yield log_text, None, None, {}, []
        
        spectrogram_path = generate_spectrogram(local_audio, "Original Music", duration)
        if spectrogram_path:
            log_text = log("  ✅ 스펙트로그램 생성 완료")
            print(f"[DEBUG] 원본 스펙트로그램 생성: {spectrogram_path}")
        else:
            log_text = log("  ⚠️ 스펙트로그램 생성 실패 (librosa/matplotlib 필요)")
        yield log_text, spectrogram_path, None, {}, []
        
        # Step 3: Demucs STEM 분리
        progress(0.2, desc="🎛️ STEM 분리 중...")
        log_text = log(f"🎛️ [3/4] Demucs STEM 분리 중 (모델: {model_choice})...")
        log_text = log(f"  💻 디바이스: {'CUDA (GPU)' if CUDA_AVAILABLE else 'CPU'}")
        yield log_text, spectrogram_path, None, {}, []
        
        model_info = DEMUCS_MODELS.get(model_choice, DEMUCS_MODELS["htdemucs"])
        log_text = log(f"  📋 분리될 트랙: {', '.join([STEM_LABELS_KR.get(s, s) for s in model_info['stems']])}")
        yield log_text, spectrogram_path, None, {}, []
        
        # Demucs 실행
        print(f"[DEBUG] Demucs 실행 시작: 모델={model_choice}")
        stem_paths = run_demucs_separation(
            audio_path=local_audio,
            model=model_choice,
            mp3_output=True,
        )
        print(f"[DEBUG] Demucs 실행 완료: {stem_paths}")
        
        progress(0.8, desc="✅ 분리 완료!")
        log_text = log(f"\n🎉 STEM 분리 완료! ({len(stem_paths)}개 트랙)")
        for stem, path in stem_paths.items():
            log_text = log(f"  ✅ {STEM_LABELS_KR.get(stem, stem)}: {Path(path).name}")
        yield log_text, spectrogram_path, None, {}, []
        
        # Step 4: 원본 스펙트로그램만 표시 (악기별은 별도 업데이트)
        progress(0.9, desc="📊 완료 중...")
        log_text = log("📊 [4/4] 원본 스펙트로그램 표시 중... (악기별 스펙트로그램은 곧 생성됩니다)")
        yield log_text, spectrogram_path, local_audio, stem_paths, list(stem_paths.keys())
        
        progress(1.0, desc="✅ 완료!")
        
    except Exception as e:
        log_text = log(f"\n❌ 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        log_text = log(traceback.format_exc())
        yield log_text, None, None, {}, []


def run_mixing(
    stems_json: str,
    prompt: str,
    original_audio: str,
    available_stems: list,
    progress=gr.Progress()
):
    """프롬프트 기반 믹싱 파이프라인"""
    logs = []
    
    def log(msg):
        logs.append(msg)
        return "\n".join(logs)
    
    if not stems_json:
        yield "❌ 먼저 STEM 분리를 실행해주세요.", None
        return
    
    if not prompt or not prompt.strip():
        yield "❌ 믹싱 프롬프트를 입력해주세요.", None
        return
    
    try:
        stems = stems_json if isinstance(stems_json, dict) else json.loads(stems_json)
    except:
        yield "❌ STEM 데이터 파싱 오류", None
        return
    
    try:
        # Step 1: 프롬프트 파싱
        progress(0.1, desc="📝 프롬프트 파싱 중...")
        log_text = log("📝 [1/2] 프롬프트 파싱 중...")
        yield log_text, None
        
        # 오디오 길이 추정
        duration = 180
        if original_audio and os.path.exists(original_audio):
            duration = get_audio_duration(original_audio)
        
        commands = parse_mixing_prompt(prompt, duration, available_stems or list(stems.keys()))
        
        if not commands:
            log_text = log("  ⚠️ 인식된 명령이 없습니다. 프롬프트 형식을 확인해주세요.")
            log_text = log("  예시: '전주 드럼 키워줘', '30초~40초 피아노 작게'")
            yield log_text, None
            return
        
        log_text = log(f"  ✅ {len(commands)}개 명령 인식")
        for cmd in commands:
            log_text = log(f"    • {STEM_LABELS_KR.get(cmd.instrument, cmd.instrument)}: "
                          f"{cmd.start_sec:.0f}~{cmd.end_sec:.0f}초, "
                          f"{cmd.volume_db:+.0f}dB")
        yield log_text, None
        
        # Step 2: 볼륨 조절 및 믹싱
        progress(0.5, desc="🎛️ 믹싱 중...")
        log_text = log("🎛️ [2/2] 볼륨 조절 및 믹싱 중...")
        yield log_text, None
        
        # 믹싱 실행
        result_path = mix_stems(stems, commands)
        
        log_text = log("\n🎉 믹싱 완료!")
        progress(1.0, desc="✅ 완료!")
        yield log_text, result_path
        
    except Exception as e:
        log_text = log(f"\n❌ 오류: {str(e)}")
        import traceback
        log_text = log(traceback.format_exc())
        yield log_text, None


def add_to_prompt(current_prompt: str, instrument: str, start_sec: float, end_sec: float, action: str) -> str:
    """프롬프트에 명령 추가"""
    kr_name = STEM_LABELS_KR.get(instrument, instrument)
    
    if start_sec == 0 and end_sec <= 0:
        new_line = f"{kr_name} {action}"
    else:
        new_line = f"{start_sec:.0f}초~{end_sec:.0f}초 {kr_name} {action}"
    
    if current_prompt:
        return current_prompt + "\n" + new_line
    return new_line


def update_instrument_choices(available_stems: list):
    """사용 가능한 악기 목록 업데이트"""
    if not available_stems:
        available_stems = ["vocals", "drums", "bass", "other"]
    
    choices = [(STEM_LABELS_KR.get(s, s), s) for s in available_stems]
    return gr.update(choices=choices, value=available_stems[0] if available_stems else None)


# ──────────────────────────────────────────────
# Gradio UI
# ──────────────────────────────────────────────

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }

.gradio-container { max-width: 1200px !important; margin: 0 auto !important; }

.header-block {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #21262d 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 16px;
    color: white;
    text-align: center;
    border: 1px solid #30363d;
}
.header-block h1 { font-size: 28px; font-weight: 700; margin: 0; color: #58a6ff !important; }
.header-block p { margin: 8px 0 0 0; font-size: 14px; color: #8b949e; }

.info-box {
    background: #161b22;
    border-left: 4px solid #58a6ff;
    border-radius: 8px;
    padding: 16px;
    font-size: 13px;
    line-height: 1.8;
    color: #c9d1d9;
}

.free-badge {
    background: linear-gradient(135deg, #238636, #2ea043);
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
    margin-top: 8px;
}
"""

HEADER_HTML = """
<div class="header-block">
    <h1>🎛️ Demucs Local Music Mixing</h1>
    <p>로컬 Demucs 기반 음악 믹싱 도구</p>
    <p style="font-size:12px; color:#8b949e; margin-top:4px;">
        STEM 분리 → 스펙트로그램 시각화 → 프롬프트 믹싱
    </p>
    <div class="free-badge">💚 API 비용 없음 (완전 무료)</div>
</div>
"""


def build_app():
    with gr.Blocks(css=CUSTOM_CSS, title="Demucs Local Mixing", theme=gr.themes.Soft()) as app:
        
        gr.HTML(HEADER_HTML)
        
        # 상태 저장
        stems_state = gr.State({})
        original_audio_state = gr.State(None)
        available_stems_state = gr.State([])
        duration_state = gr.State(180)  # 오디오 길이 저장
        
        # 시스템 정보
        with gr.Row():
            gr.HTML(f"""
            <div class="info-box" style="margin-bottom:16px;">
                <strong>🖥️ 시스템 정보</strong><br>
                • PyTorch: {'✅ 설치됨' if TORCH_AVAILABLE else '❌ 미설치'}<br>
                • CUDA (GPU): {'✅ 사용 가능' if CUDA_AVAILABLE else '❌ CPU만 사용'}<br>
                • Demucs: {'✅ 설치됨' if DEMUCS_AVAILABLE else '❌ 미설치 (pip install -U demucs)'}<br>
                • Pydub: {'✅ 설치됨' if PYDUB_AVAILABLE else '❌ 미설치 (pip install pydub)'}
            </div>
            """)
        
        # ━━━━━ Step 0: 음악 미리듣기 ━━━━━
        gr.Markdown("## 0️⃣ 음악 입력 및 미리듣기")
        
        with gr.Row():
            with gr.Column(scale=2):
                audio_file = gr.Audio(
                    label="🎵 오디오 파일 업로드",
                    type="filepath",
                    sources=["upload"],
                )
                gr.Markdown("**또는**")
                audio_url = gr.Textbox(
                    label="🔗 오디오 URL",
                    placeholder="https://drive.google.com/file/d/.../view?usp=sharing",
                    info="구글 드라이브, Dropbox 공유 링크",
                )
                with gr.Row():
                    preview_btn = gr.Button("🎧 URL 미리듣기", variant="secondary", size="sm")
                    preview_status = gr.Textbox(label="상태", lines=1, interactive=False, scale=2)
            
            with gr.Column(scale=1):
                preview_audio = gr.Audio(label="🎵 미리듣기", type="filepath")
        
        # ━━━━━ Step 1: STEM 분리 ━━━━━
        gr.Markdown("## 1️⃣ 음원 분리 (STEM Separation)")
        
        with gr.Row():
            with gr.Column(scale=2):
                model_choice = gr.Dropdown(
                    choices=[(v["name"], k) for k, v in DEMUCS_MODELS.items()],
                    value="htdemucs",
                    label="🎛️ Demucs 모델",
                    info="htdemucs_6s: 기타/피아노 추가, htdemucs_ft: 최고 품질",
                )
                stem_btn = gr.Button("🎛️ STEM 분리 시작 (무료!)", variant="primary", size="lg")
            
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="info-box">
                    <strong>📋 모델별 출력 스템</strong><br><br>
                    <strong>htdemucs (기본)</strong><br>
                    보컬, 드럼, 베이스, 기타악기<br><br>
                    <strong>htdemucs_6s</strong><br>
                    보컬, 드럼, 베이스, 기타, 피아노, 기타악기<br><br>
                    <strong>htdemucs_ft</strong><br>
                    최고 품질 (4배 느림)
                </div>
                """)
        
        stem_log = gr.Textbox(label="📋 처리 로그", lines=10, interactive=False)
        
        # 원본 스펙트로그램
        gr.Markdown("### 📊 원본 스펙트로그램")
        with gr.Row():
            spectrogram_img = gr.Image(label="Original Music", type="filepath")
        
        # 악기별 스펙트로그램
        gr.Markdown("### 🎹 악기별 스펙트로그램 (구간 선택용)")
        gr.Markdown("*스펙트로그램의 시간축을 보고 아래 슬라이더로 구간을 선택하세요*")
        
        with gr.Row():
            stem_spec_1 = gr.Image(label="Vocals", type="filepath")
            stem_spec_2 = gr.Image(label="Drums", type="filepath")
        with gr.Row():
            stem_spec_3 = gr.Image(label="Bass", type="filepath")
            stem_spec_4 = gr.Image(label="Other", type="filepath")
        with gr.Row():
            stem_spec_5 = gr.Image(label="Guitar (6s model)", type="filepath")
            stem_spec_6 = gr.Image(label="Piano (6s model)", type="filepath")
        
        # ━━━━━ Step 2: 프롬프트 믹싱 ━━━━━
        gr.Markdown("## 2️⃣ 프롬프트 믹싱")
        
        with gr.Row():
            with gr.Column(scale=2):
                # 구간 선택 도우미
                gr.Markdown("### 🎯 구간 & 볼륨 선택 도우미")
                gr.Markdown("*위 스펙트로그램을 보고 시작/끝 구간을 슬라이더로 선택하세요*")
                
                with gr.Row():
                    select_instrument = gr.Dropdown(
                        choices=[(STEM_LABELS_KR[s], s) for s in ["vocals", "drums", "bass", "other"]],
                        label="🎹 악기 선택",
                        value="drums",
                    )
                    select_action = gr.Dropdown(
                        choices=list(VOLUME_PRESETS.keys()),
                        label="🔊 볼륨 조절",
                        value="크게 (+6dB)",
                    )
                
                gr.Markdown("**⏱️ 구간 선택 (스펙트로그램 참고)**")
                with gr.Row():
                    select_start = gr.Slider(
                        label="시작 (초)",
                        minimum=0,
                        maximum=300,
                        step=1,
                        value=0,
                    )
                    select_end = gr.Slider(
                        label="끝 (초)",
                        minimum=0,
                        maximum=300,
                        step=1,
                        value=15,
                    )
                
                # 선택된 구간 표시
                selected_range_display = gr.Textbox(
                    label="선택된 구간",
                    value="0초 ~ 15초 (15초간)",
                    interactive=False,
                )
                
                add_btn = gr.Button("➕ 프롬프트에 추가", variant="secondary")
                
                # 프롬프트 입력
                gr.Markdown("### ✍️ 믹싱 프롬프트")
                mixing_prompt = gr.Textbox(
                    label="믹싱 명령",
                    placeholder="예시:\n전주 드럼 키워줘\n30초~40초 피아노 작게\n기타 음소거",
                    lines=6,
                )
                
                mix_btn = gr.Button("🎵 믹싱 실행", variant="primary", size="lg")
            
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="info-box">
                    <strong>📝 프롬프트 예시</strong><br><br>
                    • 전주 드럼 키워줘<br>
                    • 30초~40초 피아노 작게<br>
                    • 1분~1분30초 기타 키워줘<br>
                    • 베이스 음소거<br>
                    • 후주 보컬 키워줘<br><br>
                    <strong>인식 가능한 악기:</strong><br>
                    보컬, 드럼, 베이스, 기타, 피아노
                </div>
                """)
        
        mix_log = gr.Textbox(label="📋 믹싱 로그", lines=6, interactive=False)
        
        # ━━━━━ 결과 ━━━━━
        gr.Markdown("## 3️⃣ 결과")
        with gr.Row():
            with gr.Column():
                result_audio = gr.Audio(label="🎧 믹싱 결과", type="filepath")
        
        # 개별 스템 재생
        gr.Markdown("### 🎹 개별 스템 (오디오 재생)")
        with gr.Row():
            stem_audio_1 = gr.Audio(label="보컬 (Vocals)", type="filepath", visible=True)
            stem_audio_2 = gr.Audio(label="드럼 (Drums)", type="filepath", visible=True)
            stem_audio_3 = gr.Audio(label="베이스 (Bass)", type="filepath", visible=True)
        with gr.Row():
            stem_audio_4 = gr.Audio(label="기타악기 (Other)", type="filepath", visible=True)
            stem_audio_5 = gr.Audio(label="기타 (Guitar) - 6s모델", type="filepath", visible=True)
            stem_audio_6 = gr.Audio(label="피아노 (Piano) - 6s모델", type="filepath", visible=True)
        
        # ━━━━━ 이벤트 핸들러 ━━━━━
        
        # URL 미리듣기
        def preview_audio_from_url(url: str):
            if not url or not url.strip():
                return None, "❌ URL을 입력해주세요"
            
            try:
                import requests
                prepared_url = prepare_url(url)
                print(f"[DEBUG] 미리듣기 다운로드: {prepared_url}")
                
                resp = requests.get(prepared_url, timeout=60, stream=True)
                resp.raise_for_status()
                
                # 확장자 결정
                content_type = resp.headers.get('content-type', '')
                if 'wav' in content_type or url.endswith('.wav'):
                    suffix = '.wav'
                elif 'flac' in content_type or url.endswith('.flac'):
                    suffix = '.flac'
                else:
                    suffix = '.mp3'
                
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                for chunk in resp.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp.close()
                
                duration = get_audio_duration(tmp.name)
                return tmp.name, f"✅ 로드 완료 ({duration:.1f}초)"
            except Exception as e:
                return None, f"❌ 오류: {str(e)}"
        
        preview_btn.click(
            fn=preview_audio_from_url,
            inputs=[audio_url],
            outputs=[preview_audio, preview_status],
        )
        
        # 슬라이더 최대값 업데이트 (duration 기반)
        def update_slider_max(duration):
            max_val = max(30, int(duration) + 10) if duration else 300
            return (
                gr.update(maximum=max_val),
                gr.update(maximum=max_val),
            )
        
        duration_state.change(
            fn=update_slider_max,
            inputs=[duration_state],
            outputs=[select_start, select_end],
        )
        
        # 선택된 구간 표시 업데이트
        def update_selected_range(start, end):
            duration = end - start
            return f"{int(start)}초 ~ {int(end)}초 ({int(duration)}초간)"
        
        select_start.change(
            fn=update_selected_range,
            inputs=[select_start, select_end],
            outputs=[selected_range_display],
        )
        select_end.change(
            fn=update_selected_range,
            inputs=[select_start, select_end],
            outputs=[selected_range_display],
        )
        
        # STEM 분리 완료 시 개별 스템 오디오 업데이트
        def update_stem_players(stems):
            if not stems:
                return None, None, None, None, None, None
            
            order = ["vocals", "drums", "bass", "other", "guitar", "piano"]
            audios = []
            for stem in order:  # 6개 모두 처리
                audios.append(stems.get(stem, None))
            return tuple(audios)
        
        # 악기별 스펙트로그램 생성
        def update_stem_spectrograms(stems, duration):
            print(f"[DEBUG] update_stem_spectrograms 호출됨")
            print(f"[DEBUG] stems 타입: {type(stems)}")
            print(f"[DEBUG] stems 내용: {stems}")
            print(f"[DEBUG] duration: {duration}")
            
            if not stems:
                print("[DEBUG] stems가 비어있음 - 빈 결과 반환")
                return None, None, None, None, None, None
            
            # dict 변환 처리
            if isinstance(stems, str):
                try:
                    stems = json.loads(stems)
                except:
                    print("[DEBUG] JSON 파싱 실패")
                    return None, None, None, None, None, None
            
            order = ["vocals", "drums", "bass", "other", "guitar", "piano"]
            spectrograms = []
            
            for stem_name in order:
                stem_path = stems.get(stem_name)
                if stem_path and os.path.exists(stem_path):
                    print(f"[DEBUG] {stem_name} 스펙트로그램 생성 시작: {stem_path}")
                    spec = generate_stem_spectrogram(stem_name, stem_path, duration)
                    spectrograms.append(spec)
                    print(f"[DEBUG] {stem_name} 스펙트로그램 결과: {spec}")
                else:
                    print(f"[DEBUG] {stem_name}: 경로 없음 또는 파일 없음 - {stem_path}")
                    spectrograms.append(None)
            
            print(f"[DEBUG] 최종 스펙트로그램 결과: {len(spectrograms)}개")
            return tuple(spectrograms)
        
        stem_btn.click(
            fn=run_stem_separation,
            inputs=[audio_file, audio_url, model_choice],
            outputs=[stem_log, spectrogram_img, original_audio_state, stems_state, available_stems_state],
        ).then(
            fn=lambda stems: get_audio_duration(list(stems.values())[0]) if stems else 180,
            inputs=[stems_state],
            outputs=[duration_state],
        ).then(
            fn=update_stem_players,
            inputs=[stems_state],
            outputs=[stem_audio_1, stem_audio_2, stem_audio_3, stem_audio_4, stem_audio_5, stem_audio_6],
        ).then(
            fn=update_stem_spectrograms,
            inputs=[stems_state, duration_state],
            outputs=[stem_spec_1, stem_spec_2, stem_spec_3, stem_spec_4, stem_spec_5, stem_spec_6],
        ).then(
            fn=update_instrument_choices,
            inputs=[available_stems_state],
            outputs=[select_instrument],
        )
        
        # 프롬프트에 추가
        def on_add_to_prompt(current, instrument, start, end, action):
            action_text = action.split('(')[0].strip()  # "(+6dB)" 제거
            return add_to_prompt(current, instrument, start, end, action_text)
        
        add_btn.click(
            fn=on_add_to_prompt,
            inputs=[mixing_prompt, select_instrument, select_start, select_end, select_action],
            outputs=[mixing_prompt],
        )
        
        # 믹싱 실행
        mix_btn.click(
            fn=run_mixing,
            inputs=[stems_state, mixing_prompt, original_audio_state, available_stems_state],
            outputs=[mix_log, result_audio],
        )
        
        # ━━━━━ 가이드 ━━━━━
        with gr.Accordion("📖 사용 가이드", open=False):
            gr.Markdown("""
## 설치

```bash
# 필수
pip install gradio demucs pydub

# 권장 (스펙트로그램)
pip install librosa matplotlib numpy

# Ubuntu ffmpeg
sudo apt install ffmpeg
```

## 사용 방법

### Step 1: 음원 분리
1. **파일 업로드** 또는 **URL 입력**
2. Demucs 모델 선택:
   - `htdemucs`: 빠른 속도 (기본)
   - `htdemucs_6s`: 기타/피아노 추가
   - `htdemucs_ft`: 최고 품질 (느림)
3. "STEM 분리 시작" 클릭

### Step 2: 프롬프트 믹싱
1. **구간 선택 도우미** 또는 **직접 입력**
2. "믹싱 실행" 클릭

---

### 프롬프트 문법

| 구간 키워드 | 의미 |
|------------|------|
| 전주, 인트로 | 0~15초 |
| 후주, 아웃트로 | 마지막 30초 |
| 30초~40초 | 특정 구간 |

| 액션 키워드 | 효과 |
|------------|------|
| 키워, 크게 | +6dB |
| 작게, 줄여 | -6dB |
| 음소거 | 완전 제거 |

---

### 비용 비교

| 방식 | 비용 |
|------|------|
| KIE.AI API | 50~80 크레딧/곡 |
| **Demucs 로컬** | **무료!** |

---

### 시스템 요구사항

- **CPU**: 곡 길이의 약 1.5배 시간 소요
- **GPU (CUDA)**: 실시간보다 빠름
- **RAM**: 최소 4GB (GPU: 3~7GB VRAM)
            """)
        
        # Footer
        gr.HTML("""
        <div style="text-align:center; padding:16px; color:#8b949e; font-size:12px; 
                    border-top:1px solid #30363d; margin-top:16px;">
            Demucs Local Music Mixing &nbsp;|&nbsp; 
            STEM: Hybrid Transformer Demucs (로컬) &nbsp;|&nbsp;
            믹싱: pydub &nbsp;|&nbsp;
            💚 API 비용 없음
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
        server_port=7863,
        share=False,
        show_error=True,
    )
