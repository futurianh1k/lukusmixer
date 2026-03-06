"""
🎛️ Prompt-Based Music Mixing Demo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
프롬프트 기반 음악 믹싱 도구

파이프라인:
┌─────────────────────────────────────────────────────────────────┐
│  [Kie.ai API]        [LLM/룰베이스]       [로컬 처리]           │
│  ① split_stem    →  ② 프롬프트 파싱  →  ③ 볼륨 조절          │
│  (12트랙 분리)       "전주 드럼 키워줘"     (pydub 등)          │
│                      → instrument: drums                        │
│                      → section: 0~15s                           │
│                      → action: +6dB                             │
│                                            ④ 트랙 합성          │
│                                            → 최종 출력          │
└─────────────────────────────────────────────────────────────────┘

기능:
1. 음악 URL 입력 → STEM 분리 (12트랙)
2. 스펙트로그램 시각화 (원본 + 각 악기별)
3. 구간 선택 → 프롬프트에 타임스탬프 자동 입력
4. 볼륨 프리셋 선택 → 프롬프트에 반영
5. 프롬프트 파싱 → 실제 볼륨 조절 → 믹싱

실행: pip install gradio requests librosa matplotlib pydub numpy
      python prompt_mixing.py

API 참고: https://docs.kie.ai/suno-api/separate-vocals
"""

import gradio as gr
import requests
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
    
    # 한글 폰트 설정
    import matplotlib.font_manager as fm
    
    # 한글 폰트 찾기 (Ubuntu/Linux)
    font_found = False
    for font_name in ['NanumGothic', 'Noto Sans KR', 'Malgun Gothic', 'AppleGothic', 'Noto Sans CJK KR']:
        try:
            font_path = fm.findfont(fm.FontProperties(family=font_name))
            if font_path and 'dejavu' not in font_path.lower():
                plt.rcParams['font.family'] = font_name
                font_found = True
                break
        except:
            continue
    
    # 폰트를 찾지 못하면 영문으로 대체
    if not font_found:
        plt.rcParams['font.family'] = 'DejaVu Sans'
    
    plt.rcParams['axes.unicode_minus'] = False
    
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️ matplotlib 미설치: pip install matplotlib")


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

KIE_API_BASE = "https://api.kie.ai"

ENDPOINTS = {
    "upload_cover": f"{KIE_API_BASE}/api/v1/generate/upload-cover",
    "vocal_removal": f"{KIE_API_BASE}/api/v1/vocal-removal/generate",
    "vocal_info": f"{KIE_API_BASE}/api/v1/vocal-removal/record-info",
    "record_info": f"{KIE_API_BASE}/api/v1/generate/record-info",
}

# 12 STEM 목록
STEM_NAMES = [
    "vocals", "backing_vocals", "drums", "bass", "guitar", 
    "keyboard", "strings", "brass", "woodwinds", "percussion", 
    "synth", "fx"
]

STEM_LABELS_KR = {
    "vocals": "보컬",
    "backing_vocals": "백보컬",
    "drums": "드럼",
    "bass": "베이스",
    "guitar": "기타",
    "keyboard": "키보드/피아노",
    "strings": "현악기",
    "brass": "금관악기",
    "woodwinds": "목관악기",
    "percussion": "타악기",
    "synth": "신디사이저",
    "fx": "이펙트/기타",
}

# 영문 라벨 (폰트 문제 대비)
STEM_LABELS_EN = {
    "vocals": "Vocals",
    "backing_vocals": "Backing Vocals",
    "drums": "Drums",
    "bass": "Bass",
    "guitar": "Guitar",
    "keyboard": "Keyboard/Piano",
    "strings": "Strings",
    "brass": "Brass",
    "woodwinds": "Woodwinds",
    "percussion": "Percussion",
    "synth": "Synth",
    "fx": "FX/Other",
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


def download_audio(url: str, timeout: int = 120) -> str:
    """URL에서 오디오 파일 다운로드"""
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
# KIE API Functions
# ──────────────────────────────────────────────

def kie_get_headers(api_key: str) -> dict:
    """API 요청 헤더"""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


def kie_upload_for_stem(
    audio_url: str,
    api_key: str,
    model: str = "V4",
) -> dict:
    """
    음원을 KIE에 업로드 (STEM 분리를 위한 전처리)
    upload-cover API를 사용하여 taskId/audioId 획득
    """
    url = ENDPOINTS["upload_cover"]
    headers = kie_get_headers(api_key)
    
    payload = {
        "uploadUrl": audio_url,
        "model": model,
        "customMode": False,
        "instrumental": True,
        "prompt": "instrumental version",
        "callBackUrl": "https://example.com/callback",
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    
    if data.get("code") != 200:
        raise Exception(f"업로드 실패: {data.get('msg', json.dumps(data))}")
    
    return data.get("data", {})


def kie_split_stem(
    task_id: str,
    audio_id: str,
    api_key: str,
) -> dict:
    """
    KIE API: 12트랙 STEM 분리
    - vocals, backing_vocals, drums, bass, guitar, keyboard
    - strings, brass, woodwinds, percussion, synth, fx
    """
    url = ENDPOINTS["vocal_removal"]
    headers = kie_get_headers(api_key)
    
    payload = {
        "taskId": task_id,
        "audioId": audio_id,
        "type": "split_stem",
        "callBackUrl": "https://example.com/callback",
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    
    if data.get("code") != 200:
        raise Exception(f"STEM 분리 요청 실패: {data.get('msg', json.dumps(data))}")
    
    return data.get("data", {})


def kie_get_stem_result(task_id: str, api_key: str, max_retries: int = 60) -> dict:
    """STEM 분리 결과 폴링"""
    url = ENDPOINTS["vocal_info"]
    headers = kie_get_headers(api_key)
    
    for i in range(max_retries):
        resp = requests.get(
            url,
            headers=headers,
            params={"taskId": task_id},
            timeout=30
        )
        data = resp.json()
        
        if data.get("code") != 200:
            time.sleep(5)
            continue
        
        task_data = data.get("data", {})
        status = task_data.get("status", "")
        
        if status == "SUCCESS":
            return task_data
        
        if "FAILED" in status or "ERROR" in status:
            error_msg = task_data.get("errorMsg", task_data.get("error", ""))
            print(f"[DEBUG] STEM 분리 실패 응답: {json.dumps(task_data, ensure_ascii=False, indent=2)}")
            raise Exception(f"STEM 분리 실패: {status} - {error_msg}")
        
        time.sleep(5)
    
    raise Exception("STEM 분리 시간 초과")


def kie_get_cover_result(task_id: str, api_key: str, max_retries: int = 60) -> dict:
    """커버 생성 결과 폴링"""
    url = ENDPOINTS["record_info"]
    headers = kie_get_headers(api_key)
    
    for i in range(max_retries):
        resp = requests.get(
            url,
            headers=headers,
            params={"taskId": task_id},
            timeout=30
        )
        data = resp.json()
        
        if data.get("code") != 200:
            time.sleep(5)
            continue
        
        task_data = data.get("data", {})
        status = task_data.get("status", "")
        
        if status == "SUCCESS":
            return task_data
        
        if "FAILED" in status or "ERROR" in status:
            error_msg = task_data.get("errorMsg", task_data.get("error", ""))
            print(f"[DEBUG] API 실패 응답 전체: {json.dumps(task_data, ensure_ascii=False, indent=2)}")
            raise Exception(f"처리 실패: {status} - {error_msg}")
        
        time.sleep(5)
    
    raise Exception("처리 시간 초과")


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
        print(f"스펙트로그램 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_stem_spectrograms(stem_paths: Dict[str, str], duration: float = None) -> Dict[str, str]:
    """
    각 스템별 스펙트로그램 이미지 생성
    
    Args:
        stem_paths: {stem_name: file_path or url} 딕셔너리
        duration: 총 길이 (초)
    
    Returns:
        {stem_name: spectrogram_image_path} 딕셔너리
    """
    if not LIBROSA_AVAILABLE or not MATPLOTLIB_AVAILABLE:
        print("[DEBUG] librosa 또는 matplotlib 미설치")
        return {}
    
    spectrograms = {}
    print(f"[DEBUG] generate_stem_spectrograms 호출: {len(stem_paths)}개 스템")
    
    for stem_name, path_or_url in stem_paths.items():
        if not path_or_url:
            print(f"[DEBUG] {stem_name}: URL 없음, 스킵")
            continue
        
        try:
            print(f"[DEBUG] {stem_name}: 처리 시작 - {path_or_url[:50]}...")
            
            # URL인 경우 다운로드
            if path_or_url.startswith('http'):
                print(f"[DEBUG] {stem_name}: URL에서 다운로드 중...")
                local_path = download_audio(path_or_url)
                print(f"[DEBUG] {stem_name}: 다운로드 완료 - {local_path}")
            else:
                local_path = path_or_url
            
            if not os.path.exists(local_path):
                print(f"[DEBUG] {stem_name}: 파일 없음 - {local_path}")
                continue
            
            y, sr = librosa.load(local_path, sr=22050)
            stem_duration = len(y) / sr
            if duration is None:
                duration = stem_duration
            
            plt.figure(figsize=(14, 3))
            D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
            librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='hz', cmap='viridis')
            plt.colorbar(format='%+2.0f dB')
            
            # 영문 라벨 사용 (폰트 호환성)
            en_name = STEM_LABELS_EN.get(stem_name, stem_name)
            plt.title(f"{en_name} ({stem_duration:.1f}s)", fontsize=11, fontweight='bold')
            plt.xlabel('Time (sec)')
            plt.ylabel('Frequency (Hz)')
            plt.tight_layout()
            
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            plt.savefig(tmp.name, dpi=100, bbox_inches='tight')
            plt.close()
            
            spectrograms[stem_name] = tmp.name
            print(f"[DEBUG] {stem_name}: 스펙트로그램 생성 완료 - {tmp.name}")
            
        except Exception as e:
            print(f"스펙트로그램 생성 오류 ({stem_name}): {e}")
            continue
    
    return spectrograms


def generate_combined_spectrogram(original_path: str, stem_paths: Dict[str, str]) -> str:
    """
    원본 + 모든 스템의 스펙트로그램을 하나의 이미지로 생성
    
    Args:
        original_path: 원본 오디오 파일 경로
        stem_paths: {stem_name: file_path or url} 딕셔너리
    
    Returns:
        통합 스펙트로그램 이미지 경로
    """
    if not LIBROSA_AVAILABLE or not MATPLOTLIB_AVAILABLE:
        return None
    
    try:
        # 원본 로드
        y_orig, sr = librosa.load(original_path, sr=22050)
        duration = len(y_orig) / sr
        
        # 유효한 스템 필터링 (URL 다운로드)
        valid_stems = {}
        for stem_name, path_or_url in stem_paths.items():
            if not path_or_url:
                continue
            try:
                if path_or_url.startswith('http'):
                    local_path = download_audio(path_or_url)
                else:
                    local_path = path_or_url
                if os.path.exists(local_path):
                    valid_stems[stem_name] = local_path
            except:
                continue
        
        n_plots = 1 + len(valid_stems)
        fig, axes = plt.subplots(n_plots, 1, figsize=(14, 2.5 * n_plots))
        
        if n_plots == 1:
            axes = [axes]
        
        # 원본 스펙트로그램
        D_orig = librosa.amplitude_to_db(np.abs(librosa.stft(y_orig)), ref=np.max)
        img = librosa.display.specshow(D_orig, sr=sr, x_axis='time', y_axis='hz', 
                                       cmap='magma', ax=axes[0])
        axes[0].set_title(f"Original ({duration:.1f}s)", fontsize=11, fontweight='bold')
        axes[0].set_xlabel('')
        fig.colorbar(img, ax=axes[0], format='%+2.0f dB')
        
        # 스템별 스펙트로그램
        colors = ['viridis', 'plasma', 'inferno', 'cividis', 'coolwarm', 'RdYlBu']
        for idx, (stem_name, local_path) in enumerate(valid_stems.items()):
            ax = axes[idx + 1]
            y, _ = librosa.load(local_path, sr=22050)
            D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
            
            cmap = colors[idx % len(colors)]
            img = librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='hz', 
                                          cmap=cmap, ax=ax)
            en_name = STEM_LABELS_EN.get(stem_name, stem_name)
            ax.set_title(f"{en_name}", fontsize=11, fontweight='bold')
            if idx < len(valid_stems) - 1:
                ax.set_xlabel('')
            else:
                ax.set_xlabel('Time (sec)')
            fig.colorbar(img, ax=ax, format='%+2.0f dB')
        
        plt.tight_layout()
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(tmp.name, dpi=100, bbox_inches='tight')
        plt.close()
        
        return tmp.name
        
    except Exception as e:
        print(f"통합 스펙트로그램 생성 오류: {e}")
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
    
    # 첫 번째 스템을 기준으로
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
# Prompt Parsing (Rule-based)
# ──────────────────────────────────────────────

def parse_mixing_prompt(prompt: str, total_duration: float = 180) -> List[MixingCommand]:
    """
    프롬프트를 파싱하여 믹싱 명령 추출
    
    예시:
    - "전주 드럼 키워줘" → drums, 0~15s, +6dB
    - "30초~40초 피아노 키워줘" → keyboard, 30~40s, +6dB
    - "기타 작게 해줘" → guitar, 0~end, -6dB
    - "1분30초부터 2분까지 베이스 음소거" → bass, 90~120s, -inf
    
    Returns:
        MixingCommand 리스트
    """
    commands = []
    
    # 악기 이름 매핑 (한글 → 영문)
    instrument_map = {
        "보컬": "vocals", "목소리": "vocals", "노래": "vocals",
        "백보컬": "backing_vocals", "코러스": "backing_vocals",
        "드럼": "drums", "드럼스": "drums",
        "베이스": "bass", "베이스기타": "bass",
        "기타": "guitar", "일렉기타": "guitar", "어쿠스틱기타": "guitar",
        "피아노": "keyboard", "키보드": "keyboard", "건반": "keyboard",
        "현악기": "strings", "스트링": "strings", "바이올린": "strings",
        "금관악기": "brass", "트럼펫": "brass", "호른": "brass",
        "목관악기": "woodwinds", "플룻": "woodwinds", "클라리넷": "woodwinds",
        "타악기": "percussion", "퍼커션": "percussion",
        "신디사이저": "synth", "신스": "synth",
        "이펙트": "fx", "효과음": "fx",
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
        "키워": 6, "올려": 6, "크게": 6, "강조": 6,
        "조금 키워": 3, "약간 키워": 3, "살짝 키워": 3,
        "줄여": -6, "작게": -6, "낮춰": -6,
        "조금 줄여": -3, "약간 줄여": -3,
        "음소거": -100, "뮤트": -100, "없애": -100,
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
            if kr_name in line:
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

def run_stem_separation(audio_url: str, api_key: str, progress=gr.Progress()):
    """STEM 분리 파이프라인"""
    logs = []
    duration = 180  # 기본값
    
    def log(msg):
        logs.append(msg)
        return "\n".join(logs)
    
    if not api_key or not api_key.strip():
        yield "❌ API Key를 입력해주세요.", None, None, {}, 180
        return
    
    if not audio_url or not audio_url.strip():
        yield "❌ 음악 URL을 입력해주세요.", None, None, {}, 180
        return
    
    try:
        # Step 1: URL 준비
        progress(0.05, desc="🔗 URL 준비 중...")
        log_text = log("🔗 [1/5] URL 준비 중...")
        yield log_text, None, None, {}, duration
        
        prepared_url = prepare_url(audio_url)
        log_text = log(f"  ✅ URL: {prepared_url[:60]}...")
        yield log_text, None, None, {}, duration
        
        # Step 2: 오디오 다운로드 (스펙트로그램용)
        progress(0.1, desc="📥 오디오 다운로드 중...")
        log_text = log("📥 [2/5] 오디오 다운로드 중...")
        yield log_text, None, None, {}, duration
        
        local_audio = download_audio(prepared_url)
        duration = get_audio_duration(local_audio)
        log_text = log(f"  ✅ 다운로드 완료: {duration:.1f}초")
        yield log_text, None, None, {}, duration
        
        # Step 3: 원본 스펙트로그램 생성
        progress(0.2, desc="📊 스펙트로그램 생성 중...")
        log_text = log("📊 [3/5] 스펙트로그램 생성 중...")
        yield log_text, None, None, {}, duration
        
        spectrogram_path = generate_spectrogram(local_audio, "원본 음악", duration)
        if spectrogram_path:
            log_text = log("  ✅ 스펙트로그램 생성 완료")
        else:
            log_text = log("  ⚠️ 스펙트로그램 생성 실패 (librosa/matplotlib 필요)")
        yield log_text, spectrogram_path, None, {}, duration
        
        # Step 4: KIE API로 업로드
        progress(0.3, desc="☁️ KIE API 업로드 중...")
        log_text = log("☁️ [4/5] KIE API로 음원 등록 중...")
        yield log_text, spectrogram_path, None, {}, duration
        
        upload_result = kie_upload_for_stem(prepared_url, api_key)
        task_id = upload_result.get("taskId", "")
        log_text = log(f"  ✅ Task ID: {task_id}")
        yield log_text, spectrogram_path, None, {}, duration
        
        # 커버 결과 대기 (audioId 획득)
        log_text = log("  ⏳ 처리 대기 중...")
        yield log_text, spectrogram_path, None, {}, duration
        
        cover_result = kie_get_cover_result(task_id, api_key)
        
        response_data = cover_result.get("response", {})
        suno_data = response_data.get("sunoData", [])
        
        if not suno_data:
            log_text = log("  ❌ 오디오 ID를 가져올 수 없습니다")
            yield log_text, spectrogram_path, None, {}, duration
            return
        
        audio_id = suno_data[0].get("id", "")
        log_text = log(f"  ✅ Audio ID: {audio_id}")
        yield log_text, spectrogram_path, None, {}, duration
        
        # Step 5: STEM 분리 요청
        progress(0.5, desc="🎛️ STEM 분리 요청 중...")
        log_text = log("🎛️ [5/5] STEM 분리 요청 중 (12트랙)...")
        log_text = log("  💰 50 크레딧 사용")
        yield log_text, spectrogram_path, None, {}, duration
        
        stem_result = kie_split_stem(task_id, audio_id, api_key)
        stem_task_id = stem_result.get("taskId", task_id)
        log_text = log(f"  ✅ STEM Task ID: {stem_task_id}")
        yield log_text, spectrogram_path, None, {}, duration
        
        # STEM 분리 결과 대기
        log_text = log("  ⏳ STEM 분리 대기 중... (1~5분 소요)")
        yield log_text, spectrogram_path, None, {}, duration
        
        for attempt in range(60):
            progress(0.5 + 0.4 * (attempt / 60), desc=f"⏳ 대기 중... ({attempt * 5}초)")
            
            try:
                stem_info = kie_get_stem_result(stem_task_id, api_key, max_retries=1)
                
                # 결과 파싱
                vocal_info = stem_info.get("vocal_separation_info", {})
                
                if vocal_info:
                    stems = {}
                    for stem in STEM_NAMES:
                        url_key = f"{stem}_url"
                        if url_key in vocal_info:
                            stems[stem] = vocal_info[url_key]
                    
                    log_text = log(f"\n🎉 STEM 분리 완료! ({len(stems)}개 트랙)")
                    for stem, url in stems.items():
                        if url:
                            log_text = log(f"  ✅ {STEM_LABELS_KR.get(stem, stem)}: 준비됨")
                    
                    progress(1.0, desc="✅ 완료!")
                    yield log_text, spectrogram_path, local_audio, stems, duration
                    return
                    
            except Exception as e:
                pass
            
            time.sleep(5)
        
        log_text = log("\n⏰ 시간 초과: STEM 분리 결과를 받지 못했습니다")
        yield log_text, spectrogram_path, local_audio, {}, duration
        
    except Exception as e:
        log_text = log(f"\n❌ 오류: {str(e)}")
        yield log_text, None, None, {}, 180


def run_mixing(
    stems_json: str,
    prompt: str,
    original_audio: str,
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
        stems = json.loads(stems_json) if isinstance(stems_json, str) else stems_json
    except:
        yield "❌ STEM 데이터 파싱 오류", None
        return
    
    try:
        # Step 1: 프롬프트 파싱
        progress(0.1, desc="📝 프롬프트 파싱 중...")
        log_text = log("📝 [1/3] 프롬프트 파싱 중...")
        yield log_text, None
        
        # 오디오 길이 추정 (원본 오디오에서)
        duration = 180
        if original_audio and os.path.exists(original_audio):
            duration = get_audio_duration(original_audio)
        
        commands = parse_mixing_prompt(prompt, duration)
        
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
        
        # Step 2: STEM 다운로드
        progress(0.3, desc="📥 STEM 다운로드 중...")
        log_text = log("📥 [2/3] STEM 다운로드 중...")
        yield log_text, None
        
        local_stems = {}
        for stem_name, url in stems.items():
            if url and stem_name in [cmd.instrument for cmd in commands]:
                try:
                    local_path = download_audio(url)
                    local_stems[stem_name] = local_path
                    log_text = log(f"  ✅ {STEM_LABELS_KR.get(stem_name, stem_name)} 다운로드 완료")
                    yield log_text, None
                except Exception as e:
                    log_text = log(f"  ⚠️ {stem_name} 다운로드 실패: {e}")
                    yield log_text, None
        
        # Step 3: 볼륨 조절 및 믹싱
        progress(0.6, desc="🎛️ 볼륨 조절 중...")
        log_text = log("🎛️ [3/3] 볼륨 조절 및 믹싱 중...")
        yield log_text, None
        
        # 전체 스템 다운로드 (믹싱용)
        all_stems = {}
        for stem_name, url in stems.items():
            if url:
                if stem_name in local_stems:
                    all_stems[stem_name] = local_stems[stem_name]
                else:
                    try:
                        local_path = download_audio(url)
                        all_stems[stem_name] = local_path
                    except:
                        pass
        
        # 믹싱 실행
        result_path = mix_stems(all_stems, commands)
        
        log_text = log("\n🎉 믹싱 완료!")
        progress(1.0, desc="✅ 완료!")
        yield log_text, result_path
        
    except Exception as e:
        log_text = log(f"\n❌ 오류: {str(e)}")
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


# ──────────────────────────────────────────────
# Gradio UI
# ──────────────────────────────────────────────

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }

.gradio-container { max-width: 1200px !important; margin: 0 auto !important; }

.header-block {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 16px;
    color: white;
    text-align: center;
    border: 1px solid #30363d;
}
.header-block h1 { font-size: 28px; font-weight: 700; margin: 0; color: #e94560 !important; }
.header-block p { margin: 8px 0 0 0; font-size: 14px; color: #8b949e; }

.info-box {
    background: #161b22;
    border-left: 4px solid #e94560;
    border-radius: 8px;
    padding: 16px;
    font-size: 13px;
    line-height: 1.8;
    color: #c9d1d9;
}
"""

HEADER_HTML = """
<div class="header-block">
    <h1>🎛️ Prompt-Based Music Mixing</h1>
    <p>프롬프트 기반 음악 믹싱 도구</p>
    <p style="font-size:12px; color:#8b949e; margin-top:4px;">
        STEM 분리 → 스펙트로그램 시각화 → 프롬프트 믹싱
    </p>
</div>
"""


def build_app():
    with gr.Blocks(css=CUSTOM_CSS, title="Prompt Mixing", theme=gr.themes.Soft()) as app:
        
        gr.HTML(HEADER_HTML)
        
        # 상태 저장
        stems_state = gr.State({})
        original_audio_state = gr.State(None)
        duration_state = gr.State(180)  # 오디오 길이 저장
        stem_spectrograms_state = gr.State({})  # 스템별 스펙트로그램 경로
        
        # API Key
        with gr.Row():
            api_key = gr.Textbox(
                label="🔑 KIE.AI API Key",
                placeholder="your-api-key-here",
                type="password",
                scale=3,
            )
        
        # ━━━━━ Step 0: 음악 미리듣기 ━━━━━
        gr.Markdown("## 0️⃣ 음악 확인 (미리듣기)")
        
        with gr.Row():
            with gr.Column(scale=2):
                audio_url = gr.Textbox(
                    label="🔗 음악 URL",
                    placeholder="https://drive.google.com/file/d/.../view?usp=sharing",
                    info="구글 드라이브, Dropbox 공유 링크",
                )
                with gr.Row():
                    preview_btn = gr.Button("🎧 미리듣기", variant="secondary", size="sm")
                    preview_status = gr.Textbox(label="상태", lines=1, interactive=False, scale=2)
            
            with gr.Column(scale=1):
                preview_audio = gr.Audio(label="🎵 원본 음악 미리듣기", type="filepath")
        
        # ━━━━━ Step 1: STEM 분리 ━━━━━
        gr.Markdown("## 1️⃣ 음원 분리 (STEM Separation)")
        
        with gr.Row():
            with gr.Column(scale=2):
                stem_btn = gr.Button("🎛️ STEM 분리 시작 (50 크레딧)", variant="primary", size="lg")
            
            with gr.Column(scale=1):
                gr.HTML("""
                <div class="info-box">
                    <strong>📋 STEM 분리 결과 (12트랙)</strong><br>
                    보컬, 백보컬, 드럼, 베이스, 기타,<br>
                    키보드, 현악기, 금관, 목관, 타악기,<br>
                    신디사이저, 이펙트
                </div>
                """)
        
        stem_log = gr.Textbox(label="📋 처리 로그", lines=8, interactive=False)
        
        # 원본 스펙트로그램
        gr.Markdown("### 📊 원본 스펙트로그램")
        with gr.Row():
            spectrogram_img = gr.Image(label="원본 음악 스펙트로그램", type="filepath")
        
        # 악기별 스펙트로그램
        gr.Markdown("### 🎹 악기별 스펙트로그램 (구간 선택용)")
        gr.Markdown("*스펙트로그램의 시간축을 보고 아래 슬라이더로 구간을 선택하세요*")
        
        with gr.Row():
            stem_spec_1 = gr.Image(label="보컬", type="filepath", visible=True)
            stem_spec_2 = gr.Image(label="드럼", type="filepath", visible=True)
        with gr.Row():
            stem_spec_3 = gr.Image(label="베이스", type="filepath", visible=True)
            stem_spec_4 = gr.Image(label="기타", type="filepath", visible=True)
        with gr.Row():
            stem_spec_5 = gr.Image(label="키보드", type="filepath", visible=True)
            stem_spec_6 = gr.Image(label="기타 악기", type="filepath", visible=True)
        
        # ━━━━━ Step 2: 프롬프트 믹싱 ━━━━━
        gr.Markdown("## 2️⃣ 프롬프트 믹싱")
        
        with gr.Row():
            with gr.Column(scale=2):
                # 구간 선택 도우미 - 슬라이더 방식
                gr.Markdown("### 🎯 구간 & 볼륨 선택 도우미")
                gr.Markdown("*스펙트로그램을 보고 슬라이더로 구간을 선택하세요*")
                
                with gr.Row():
                    select_instrument = gr.Dropdown(
                        choices=[(STEM_LABELS_KR[s], s) for s in STEM_NAMES],
                        label="악기 선택",
                        value="drums",
                    )
                    select_action = gr.Dropdown(
                        choices=list(VOLUME_PRESETS.keys()),
                        label="볼륨 조절",
                        value="크게 (+6dB)",
                    )
                
                # 구간 선택 슬라이더
                with gr.Row():
                    select_start = gr.Slider(
                        label="시작 (초)", 
                        value=0, 
                        minimum=0, 
                        maximum=300,
                        step=1,
                        info="스펙트로그램에서 시작 지점 선택"
                    )
                    select_end = gr.Slider(
                        label="끝 (초)", 
                        value=15, 
                        minimum=0, 
                        maximum=300,
                        step=1,
                        info="스펙트로그램에서 종료 지점 선택"
                    )
                
                # 선택된 구간 표시
                selected_range_display = gr.Textbox(
                    label="선택된 구간", 
                    value="0초 ~ 15초 (15초 구간)",
                    interactive=False,
                    lines=1,
                )
                
                add_btn = gr.Button("➕ 프롬프트에 추가", variant="secondary", size="lg")
                
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
                    • 후주 현악기 키워줘<br><br>
                    <strong>인식 가능한 악기:</strong><br>
                    보컬, 드럼, 베이스, 기타, 피아노,<br>
                    현악기, 타악기, 신디사이저 등
                </div>
                """)
        
        mix_log = gr.Textbox(label="📋 믹싱 로그", lines=6, interactive=False)
        
        # ━━━━━ 결과 ━━━━━
        gr.Markdown("## 3️⃣ 믹싱 결과 확인")
        gr.Markdown("*볼륨 조절이 적용된 최종 믹싱 결과를 들어보세요*")
        
        with gr.Row():
            result_audio = gr.Audio(label="🎧 믹싱 결과 (모든 트랙 합성)", type="filepath")
        
        # ━━━━━ 이벤트 핸들러 ━━━━━
        
        # 미리듣기 기능
        def preview_audio_from_url(url):
            """URL에서 오디오를 다운로드하여 미리듣기"""
            if not url or not url.strip():
                return None, "❌ URL을 입력해주세요", 180
            
            try:
                local_path = download_audio(url)
                duration = get_audio_duration(local_path)
                return local_path, f"✅ 다운로드 완료: {duration:.1f}초", duration
            except Exception as e:
                return None, f"❌ 오류: {str(e)}", 180
        
        preview_btn.click(
            fn=preview_audio_from_url,
            inputs=[audio_url],
            outputs=[preview_audio, preview_status, duration_state],
        )
        
        # 슬라이더 최대값 업데이트 및 구간 표시
        def update_slider_max(duration):
            """오디오 길이에 따라 슬라이더 최대값 업데이트"""
            max_val = int(duration) if duration else 300
            return (
                gr.update(maximum=max_val),
                gr.update(maximum=max_val, value=min(15, max_val)),
            )
        
        duration_state.change(
            fn=update_slider_max,
            inputs=[duration_state],
            outputs=[select_start, select_end],
        )
        
        # 구간 선택 표시 업데이트
        def update_range_display(start, end):
            """선택된 구간 텍스트 업데이트"""
            duration = end - start
            return f"{int(start)}초 ~ {int(end)}초 ({int(duration)}초 구간)"
        
        select_start.change(
            fn=update_range_display,
            inputs=[select_start, select_end],
            outputs=[selected_range_display],
        )
        select_end.change(
            fn=update_range_display,
            inputs=[select_start, select_end],
            outputs=[selected_range_display],
        )
        
        # STEM 분리 후 스펙트로그램 업데이트
        def update_stem_spectrograms(stems, duration):
            """스템별 스펙트로그램 생성"""
            print(f"[DEBUG] update_stem_spectrograms 호출")
            print(f"[DEBUG] stems 타입: {type(stems)}, duration: {duration}")
            
            if not stems:
                print("[DEBUG] stems가 비어있음 - 스펙트로그램 생성 스킵")
                return None, None, None, None, None, None
            
            # dict가 아닌 경우 변환 시도
            if isinstance(stems, str):
                try:
                    stems = json.loads(stems)
                    print(f"[DEBUG] stems JSON 파싱 완료: {len(stems)}개")
                except:
                    print("[DEBUG] stems JSON 파싱 실패")
                    return None, None, None, None, None, None
            
            print(f"[DEBUG] stems 내용: {list(stems.keys())}")
            
            # 주요 6개 스템만 표시
            stem_order = ["vocals", "drums", "bass", "guitar", "keyboard", "other"]
            fallback_map = {
                "other": ["strings", "synth", "percussion", "fx", "brass", "woodwinds", "backing_vocals"]
            }
            
            results = []
            for stem_name in stem_order:
                path_or_url = stems.get(stem_name)
                
                # fallback 처리
                if not path_or_url and stem_name in fallback_map:
                    for fallback in fallback_map[stem_name]:
                        if stems.get(fallback):
                            path_or_url = stems.get(fallback)
                            print(f"[DEBUG] {stem_name} -> fallback: {fallback}")
                            break
                
                if path_or_url:
                    try:
                        print(f"[DEBUG] {stem_name}: 스펙트로그램 생성 시작")
                        spec_path = generate_stem_spectrograms({stem_name: path_or_url}, duration)
                        result = spec_path.get(stem_name)
                        results.append(result)
                        print(f"[DEBUG] {stem_name}: 결과 = {result}")
                    except Exception as e:
                        print(f"[DEBUG] {stem_name}: 오류 - {e}")
                        import traceback
                        traceback.print_exc()
                        results.append(None)
                else:
                    print(f"[DEBUG] {stem_name}: URL 없음")
                    results.append(None)
            
            # 6개로 맞추기
            while len(results) < 6:
                results.append(None)
            
            print(f"[DEBUG] 최종 결과: {[r is not None for r in results[:6]]}")
            return tuple(results[:6])
        
        # STEM 분리 완료 시 스펙트로그램 업데이트
        stem_btn.click(
            fn=run_stem_separation,
            inputs=[audio_url, api_key],
            outputs=[stem_log, spectrogram_img, original_audio_state, stems_state, duration_state],
        ).then(
            fn=update_stem_spectrograms,
            inputs=[stems_state, duration_state],
            outputs=[stem_spec_1, stem_spec_2, stem_spec_3, stem_spec_4, stem_spec_5, stem_spec_6],
        )
        
        # 프롬프트에 추가
        def on_add_to_prompt(current, instrument, start, end, action):
            action_text = action.split('(')[0].strip()  # "(+6dB)" 제거
            return add_to_prompt(current, instrument, float(start), float(end), action_text)
        
        add_btn.click(
            fn=on_add_to_prompt,
            inputs=[mixing_prompt, select_instrument, select_start, select_end, select_action],
            outputs=[mixing_prompt],
        )
        
        # 믹싱 실행
        mix_btn.click(
            fn=run_mixing,
            inputs=[stems_state, mixing_prompt, original_audio_state],
            outputs=[mix_log, result_audio],
        )
        
        # ━━━━━ 가이드 ━━━━━
        with gr.Accordion("📖 사용 가이드", open=False):
            gr.Markdown("""
## 사용 방법

### Step 1: 음원 분리
1. KIE.AI API Key 입력 ([발급 페이지](https://kie.ai/api-key))
2. 음악 URL 입력 (구글 드라이브 권장)
3. "STEM 분리 시작" 클릭 (50 크레딧 소요)
4. 12개 트랙으로 분리됨

### Step 2: 프롬프트 믹싱
1. **구간 선택 도우미** 사용하여 명령 추가
   - 악기 선택 → 시작/끝 시간 입력 → 볼륨 선택 → "추가" 클릭
2. 또는 **직접 프롬프트 입력**
   - 예: "전주 드럼 키워줘", "30초~40초 피아노 작게"

### Step 3: 결과 확인
- 믹싱된 음악 재생 및 다운로드

---

### 프롬프트 문법

| 구간 키워드 | 의미 |
|------------|------|
| 전주, 인트로 | 0~15초 |
| 후주, 아웃트로 | 마지막 30초 |
| 전체 | 전체 구간 |
| 30초~40초 | 특정 구간 |

| 액션 키워드 | 효과 |
|------------|------|
| 키워, 크게 | +6dB |
| 조금 키워 | +3dB |
| 줄여, 작게 | -6dB |
| 음소거 | 완전 제거 |

---

### 비용

- STEM 분리: **50 크레딧** (12트랙)
- 업로드 처리: 약 10~30 크레딧
            """)
        
        # Footer
        gr.HTML("""
        <div style="text-align:center; padding:16px; color:#8b949e; font-size:12px; 
                    border-top:1px solid #30363d; margin-top:16px;">
            Prompt-Based Music Mixing &nbsp;|&nbsp; 
            STEM: KIE.AI API &nbsp;|&nbsp;
            믹싱: pydub (로컬)
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
        server_port=7862,
        share=False,
        show_error=True,
    )
