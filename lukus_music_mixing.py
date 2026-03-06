"""
🎛️ LUKUS Music Mixing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
로컬 Demucs 기반 음악 믹싱 도구

실행:
    pip install gradio demucs pydub librosa matplotlib numpy
    python lukus_music_mixing.py

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

try:
    import demucs.separate
    DEMUCS_AVAILABLE = True
except ImportError:
    DEMUCS_AVAILABLE = False
    print("⚠️ demucs 미설치: pip install -U demucs")


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

DEMUCS_MODELS = {
    "htdemucs": {
        "name": "4 스템 (기본)",
        "stems": ["vocals", "drums", "bass", "other"],
        "description": "4 스템 분리, 빠른 속도",
    },
    "htdemucs_ft": {
        "name": "4 스템 (고품질)",
        "stems": ["vocals", "drums", "bass", "other"],
        "description": "4 스템 분리, 최고 품질 (4배 느림)",
    },
    "htdemucs_6s": {
        "name": "6 스템 (기타/피아노)",
        "stems": ["vocals", "drums", "bass", "guitar", "piano", "other"],
        "description": "6 스템 분리 (기타, 피아노 추가)",
    },
}

STEM_LABELS_KR = {
    "vocals": "보컬",
    "drums": "드럼",
    "bass": "베이스",
    "guitar": "기타",
    "piano": "피아노",
    "other": "기타 악기",
}

STEM_LABELS_EN = {
    "vocals": "Vocals",
    "drums": "Drums",
    "bass": "Bass",
    "guitar": "Guitar",
    "piano": "Piano",
    "other": "Other",
}

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
    instrument: str
    start_sec: float
    end_sec: float
    volume_db: float
    original_text: str


# ──────────────────────────────────────────────
# URL Helpers
# ──────────────────────────────────────────────

def convert_gdrive_url(url: str) -> str:
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
    if "dropbox.com" in url:
        if "dl=0" in url:
            return url.replace("dl=0", "dl=1")
        elif "dl=1" not in url:
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}dl=1"
    return url


def prepare_url(url: str) -> str:
    url = url.strip()
    if "drive.google.com" in url:
        return convert_gdrive_url(url)
    if "dropbox.com" in url:
        return convert_dropbox_url(url)
    return url


def download_audio_from_url(url: str, timeout: int = 120) -> str:
    import requests
    
    url = prepare_url(url)
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    
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
    if not LIBROSA_AVAILABLE or not MATPLOTLIB_AVAILABLE:
        return None
    
    try:
        y, sr = librosa.load(audio_path, sr=22050)
        if duration is None:
            duration = len(y) / sr
        
        plt.figure(figsize=(12, 3))
        D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='hz', cmap='magma')
        plt.colorbar(format='%+2.0f dB')
        plt.title(f"Original ({duration:.1f}s)", fontsize=10, fontweight='bold')
        plt.xlabel('Time (sec)')
        plt.ylabel('Hz')
        plt.tight_layout()
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(tmp.name, dpi=100, bbox_inches='tight')
        plt.close()
        
        return tmp.name
    except Exception as e:
        print(f"[DEBUG] 스펙트로그램 생성 오류: {e}")
        return None


def generate_stem_spectrogram(stem_name: str, audio_path: str, duration: float = None) -> str:
    if not LIBROSA_AVAILABLE or not MATPLOTLIB_AVAILABLE:
        return None
    
    try:
        y, sr = librosa.load(audio_path, sr=22050)
        stem_duration = len(y) / sr
        if duration is None:
            duration = stem_duration
        
        plt.figure(figsize=(12, 2.5))
        D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
        
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
        plt.title(f"{en_name} ({stem_duration:.1f}s)", fontsize=10, fontweight='bold')
        plt.xlabel('Time (sec)')
        plt.ylabel('Hz')
        plt.tight_layout()
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(tmp.name, dpi=100, bbox_inches='tight')
        plt.close()
        
        return tmp.name
    except Exception as e:
        print(f"[DEBUG] {stem_name}: 스펙트로그램 생성 오류 - {e}")
        return None


def get_audio_duration(audio_path: str) -> float:
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
    if not PYDUB_AVAILABLE:
        raise Exception("pydub가 설치되지 않았습니다")
    
    audio = AudioSegment.from_file(audio_path)
    
    start_ms = int(start_sec * 1000)
    end_ms = int(end_sec * 1000) if end_sec > 0 else len(audio)
    
    before = audio[:start_ms]
    target = audio[start_ms:end_ms]
    after = audio[end_ms:]
    
    if volume_db <= -100:
        target = AudioSegment.silent(duration=len(target))
    else:
        target = target + volume_db
    
    result = before + target + after
    
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
    result.export(tmp.name, format='mp3')
    return tmp.name


def mix_stems(stem_paths: Dict[str, str], adjustments: List[MixingCommand] = None) -> str:
    if not PYDUB_AVAILABLE:
        raise Exception("pydub가 설치되지 않았습니다")
    
    if not stem_paths:
        raise Exception("믹싱할 스템이 없습니다")
    
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
    if not DEMUCS_AVAILABLE:
        raise Exception("demucs가 설치되지 않았습니다. pip install -U demucs")
    
    if not os.path.exists(audio_path):
        raise Exception(f"파일을 찾을 수 없습니다: {audio_path}")
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="demucs_")
    
    if device == "auto":
        device = "cuda" if CUDA_AVAILABLE else "cpu"
    
    cmd_args = [
        "-n", model,
        "-o", output_dir,
        "-d", device,
    ]
    
    if mp3_output:
        cmd_args.extend(["--mp3", "--mp3-bitrate", "320"])
    
    cmd_args.append(audio_path)
    
    print(f"🎛️ Demucs 실행 중: {' '.join(['demucs'] + cmd_args)}")
    
    try:
        demucs.separate.main(cmd_args)
    except SystemExit:
        pass
    
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
    commands = []
    
    if available_stems is None:
        available_stems = ["vocals", "drums", "bass", "other", "guitar", "piano"]
    
    instrument_map = {
        "보컬": "vocals", "목소리": "vocals", "노래": "vocals", "음성": "vocals",
        "드럼": "drums", "드럼스": "drums",
        "베이스": "bass", "베이스기타": "bass",
        "기타": "guitar", "일렉기타": "guitar", "어쿠스틱기타": "guitar", "전기기타": "guitar",
        "피아노": "piano", "키보드": "piano", "건반": "piano",
        "나머지": "other", "기타악기": "other", "그외": "other", "배경": "other",
    }
    
    section_map = {
        "전주": (0, 15),
        "인트로": (0, 15),
        "도입부": (0, 15),
        "처음": (0, 15),
        "후주": (-30, -1),
        "아웃트로": (-30, -1),
        "끝부분": (-30, -1),
        "전체": (0, -1),
        "모두": (0, -1),
    }
    
    volume_map = {
        "키워": 6, "올려": 6, "크게": 6, "강조": 6, "높여": 6,
        "조금 키워": 3, "약간 키워": 3, "살짝 키워": 3,
        "줄여": -6, "작게": -6, "낮춰": -6,
        "조금 줄여": -3, "약간 줄여": -3,
        "음소거": -100, "뮤트": -100, "없애": -100, "제거": -100,
    }
    
    lines = prompt.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        found_instrument = None
        for kr_name, en_name in instrument_map.items():
            if kr_name in line and en_name in available_stems:
                found_instrument = en_name
                break
        
        if not found_instrument:
            continue
        
        start_sec, end_sec = 0, -1
        
        time_pattern = r'(\d+)분?(\d+)?초?\s*[~\-부터]\s*(\d+)분?(\d+)?초?[까지]?'
        time_match = re.search(time_pattern, line)
        
        if time_match:
            groups = time_match.groups()
            if groups[1]:
                start_sec = int(groups[0]) * 60 + int(groups[1])
            else:
                start_sec = int(groups[0])
            
            if groups[3]:
                end_sec = int(groups[2]) * 60 + int(groups[3])
            elif groups[2]:
                end_sec = int(groups[2])
        else:
            for section_name, (s, e) in section_map.items():
                if section_name in line:
                    if s < 0:
                        start_sec = max(0, total_duration + s)
                        end_sec = total_duration if e < 0 else e
                    else:
                        start_sec = s
                        end_sec = total_duration if e < 0 else e
                    break
        
        volume_db = 0
        for action, db in volume_map.items():
            if action in line:
                volume_db = db
                break
        
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
    logs = []
    
    def log(msg):
        logs.append(msg)
        return "\n".join(logs)
    
    if not audio_file and not audio_url:
        yield "❌ 오디오 파일을 업로드하거나 URL을 입력해주세요.", None, None, {}, []
        return
    
    if not DEMUCS_AVAILABLE:
        yield "❌ demucs가 설치되지 않았습니다. `pip install -U demucs`", None, None, {}, []
        return
    
    try:
        progress(0.05, desc="📂 입력 처리 중...")
        
        if audio_file:
            log_text = log("📂 로컬 파일 사용")
            local_audio = audio_file
        else:
            log_text = log("📂 URL에서 다운로드 중...")
            yield log_text, None, None, {}, []
            local_audio = download_audio_from_url(audio_url)
        
        duration = get_audio_duration(local_audio)
        log_text = log(f"✅ 파일 준비 완료: {duration:.1f}초")
        yield log_text, None, None, {}, []
        
        progress(0.1, desc="📊 스펙트로그램 생성 중...")
        log_text = log("📊 원본 스펙트로그램 생성 중...")
        yield log_text, None, None, {}, []
        
        spectrogram_path = generate_spectrogram(local_audio, "Original Music", duration)
        if spectrogram_path:
            log_text = log("✅ 스펙트로그램 생성 완료")
        yield log_text, spectrogram_path, None, {}, []
        
        progress(0.2, desc="🎛️ STEM 분리 중...")
        log_text = log(f"🎛️ STEM 분리 중 ({model_choice})...")
        log_text = log(f"💻 디바이스: {'CUDA' if CUDA_AVAILABLE else 'CPU'}")
        yield log_text, spectrogram_path, None, {}, []
        
        model_info = DEMUCS_MODELS.get(model_choice, DEMUCS_MODELS["htdemucs"])
        log_text = log(f"📋 분리 트랙: {', '.join([STEM_LABELS_KR.get(s, s) for s in model_info['stems']])}")
        yield log_text, spectrogram_path, None, {}, []
        
        stem_paths = run_demucs_separation(
            audio_path=local_audio,
            model=model_choice,
            mp3_output=True,
        )
        
        progress(0.8, desc="✅ 분리 완료!")
        log_text = log(f"\n🎉 분리 완료! ({len(stem_paths)}개)")
        for stem, path in stem_paths.items():
            log_text = log(f"✅ {STEM_LABELS_KR.get(stem, stem)}")
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
        progress(0.1, desc="📝 프롬프트 파싱 중...")
        log_text = log("📝 프롬프트 파싱 중...")
        yield log_text, None
        
        duration = 180
        if original_audio and os.path.exists(original_audio):
            duration = get_audio_duration(original_audio)
        
        commands = parse_mixing_prompt(prompt, duration, available_stems or list(stems.keys()))
        
        if not commands:
            log_text = log("⚠️ 인식된 명령 없음")
            yield log_text, None
            return
        
        log_text = log(f"✅ {len(commands)}개 명령 인식")
        for cmd in commands:
            log_text = log(f"• {STEM_LABELS_KR.get(cmd.instrument, cmd.instrument)}: "
                          f"{cmd.start_sec:.0f}~{cmd.end_sec:.0f}초, "
                          f"{cmd.volume_db:+.0f}dB")
        yield log_text, None
        
        progress(0.5, desc="🎛️ 믹싱 중...")
        log_text = log("🎛️ 믹싱 중...")
        yield log_text, None
        
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
    kr_name = STEM_LABELS_KR.get(instrument, instrument)
    
    if start_sec == 0 and end_sec <= 0:
        new_line = f"{kr_name} {action}"
    else:
        new_line = f"{start_sec:.0f}초~{end_sec:.0f}초 {kr_name} {action}"
    
    if current_prompt:
        return current_prompt + "\n" + new_line
    return new_line


def update_instrument_choices(available_stems: list):
    if not available_stems:
        available_stems = ["vocals", "drums", "bass", "other"]
    
    choices = [(STEM_LABELS_KR.get(s, s), s) for s in available_stems]
    return gr.update(choices=choices, value=available_stems[0] if available_stems else None)


# ──────────────────────────────────────────────
# Gradio UI - LUKUS Theme
# ──────────────────────────────────────────────

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }

.gradio-container { 
    max-width: 1800px !important; 
    margin: 0 auto !important; 
}

.header-block {
    background: linear-gradient(135deg, #FF6B00 0%, #FF8C00 50%, #FFA500 100%);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
    color: white;
    text-align: center;
    border: none;
    box-shadow: 0 4px 12px rgba(255, 107, 0, 0.3);
}
.header-block h1 { 
    font-size: 32px; 
    font-weight: 700; 
    margin: 0; 
    color: white !important; 
    text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
}

.left-panel {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 12px;
}

.center-panel {
    background: #ffffff;
    border-radius: 8px;
    padding: 8px;
    border: 1px solid #e0e0e0;
}

.right-panel {
    background: #fff8f0;
    border-radius: 8px;
    padding: 12px;
    border: 1px solid #ffd4a8;
}

.section-title {
    color: #FF6B00;
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 2px solid #FF6B00;
}
"""

HEADER_HTML = """
<div class="header-block">
    <h1>🎛️ LUKUS Music Mixing</h1>
</div>
"""


def build_app():
    with gr.Blocks(css=CUSTOM_CSS, title="LUKUS Music Mixing", theme=gr.themes.Soft()) as app:
        
        gr.HTML(HEADER_HTML)
        
        # 상태 저장
        stems_state = gr.State({})
        original_audio_state = gr.State(None)
        available_stems_state = gr.State([])
        duration_state = gr.State(180)
        
        # 3컬럼 레이아웃 (20% | 40% | 40%)
        with gr.Row():
            # ━━━━━ 왼쪽 패널 (20%) - 입력 & 분리 ━━━━━
            with gr.Column(scale=1, min_width=280):
                gr.HTML('<div class="section-title">🎵 음악 입력</div>')
                
                audio_file = gr.Audio(
                    label="파일 업로드",
                    type="filepath",
                    sources=["upload"],
                )
                
                audio_url = gr.Textbox(
                    label="또는 URL 입력",
                    placeholder="Google Drive / Dropbox URL",
                    lines=1,
                )
                
                with gr.Row():
                    preview_btn = gr.Button("🎧 미리듣기", variant="secondary", size="sm")
                
                preview_audio = gr.Audio(label="미리듣기", type="filepath")
                preview_status = gr.Textbox(label="상태", lines=1, interactive=False)
                
                gr.HTML('<div class="section-title" style="margin-top:16px;">🎛️ STEM 분리</div>')
                
                model_choice = gr.Dropdown(
                    choices=[(v["name"], k) for k, v in DEMUCS_MODELS.items()],
                    value="htdemucs",
                    label="모델 선택",
                )
                
                stem_btn = gr.Button("🎛️ 분리 시작", variant="primary", size="lg")
                
                stem_log = gr.Textbox(label="처리 로그", lines=12, interactive=False)
            
            # ━━━━━ 가운데 패널 (40%) - 스펙트로그램 ━━━━━
            with gr.Column(scale=2, min_width=500):
                gr.HTML('<div class="section-title">📊 스펙트로그램</div>')
                
                spectrogram_img = gr.Image(label="Original", type="filepath", height=120)
                
                stem_spec_1 = gr.Image(label="Vocals", type="filepath", height=100)
                stem_spec_2 = gr.Image(label="Drums", type="filepath", height=100)
                stem_spec_3 = gr.Image(label="Bass", type="filepath", height=100)
                stem_spec_4 = gr.Image(label="Other", type="filepath", height=100)
                stem_spec_5 = gr.Image(label="Guitar (6s)", type="filepath", height=100)
                stem_spec_6 = gr.Image(label="Piano (6s)", type="filepath", height=100)
            
            # ━━━━━ 오른쪽 패널 (40%) - 프롬프트 믹싱 ━━━━━
            with gr.Column(scale=2, min_width=500):
                gr.HTML('<div class="section-title">🎯 프롬프트 믹싱</div>')
                
                with gr.Row():
                    select_instrument = gr.Dropdown(
                        choices=[(STEM_LABELS_KR[s], s) for s in ["vocals", "drums", "bass", "other"]],
                        label="악기",
                        value="drums",
                        scale=1,
                    )
                    select_action = gr.Dropdown(
                        choices=list(VOLUME_PRESETS.keys()),
                        label="볼륨",
                        value="크게 (+6dB)",
                        scale=1,
                    )
                
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
                
                selected_range_display = gr.Textbox(
                    label="선택 구간",
                    value="0초 ~ 15초 (15초간)",
                    interactive=False,
                )
                
                add_btn = gr.Button("➕ 프롬프트에 추가", variant="secondary")
                
                mixing_prompt = gr.Textbox(
                    label="믹싱 프롬프트",
                    placeholder="예: 전주 드럼 키워줘\n30초~40초 피아노 작게",
                    lines=6,
                )
                
                mix_btn = gr.Button("🎵 믹싱 실행", variant="primary", size="lg")
                
                mix_log = gr.Textbox(label="믹싱 로그", lines=4, interactive=False)
                
                gr.HTML('<div class="section-title" style="margin-top:16px;">🎧 결과</div>')
                
                result_audio = gr.Audio(label="믹싱 결과", type="filepath")
                
                gr.Markdown("**개별 스템 재생**")
                with gr.Row():
                    stem_audio_1 = gr.Audio(label="Vocals", type="filepath")
                    stem_audio_2 = gr.Audio(label="Drums", type="filepath")
                with gr.Row():
                    stem_audio_3 = gr.Audio(label="Bass", type="filepath")
                    stem_audio_4 = gr.Audio(label="Other", type="filepath")
                with gr.Row():
                    stem_audio_5 = gr.Audio(label="Guitar", type="filepath")
                    stem_audio_6 = gr.Audio(label="Piano", type="filepath")
        
        # ━━━━━ 이벤트 핸들러 ━━━━━
        
        def preview_audio_from_url(url: str):
            if not url or not url.strip():
                return None, "❌ URL을 입력해주세요"
            
            try:
                import requests
                prepared_url = prepare_url(url)
                
                resp = requests.get(prepared_url, timeout=60, stream=True)
                resp.raise_for_status()
                
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
        
        def update_stem_players(stems):
            if not stems:
                return None, None, None, None, None, None
            
            order = ["vocals", "drums", "bass", "other", "guitar", "piano"]
            audios = []
            for stem in order:
                audios.append(stems.get(stem, None))
            return tuple(audios)
        
        def update_stem_spectrograms(stems, duration):
            if not stems:
                return None, None, None, None, None, None
            
            if isinstance(stems, str):
                try:
                    stems = json.loads(stems)
                except:
                    return None, None, None, None, None, None
            
            order = ["vocals", "drums", "bass", "other", "guitar", "piano"]
            spectrograms = []
            
            for stem_name in order:
                stem_path = stems.get(stem_name)
                if stem_path and os.path.exists(stem_path):
                    spec = generate_stem_spectrogram(stem_name, stem_path, duration)
                    spectrograms.append(spec)
                else:
                    spectrograms.append(None)
            
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
        
        def on_add_to_prompt(current, instrument, start, end, action):
            action_text = action.split('(')[0].strip()
            return add_to_prompt(current, instrument, start, end, action_text)
        
        add_btn.click(
            fn=on_add_to_prompt,
            inputs=[mixing_prompt, select_instrument, select_start, select_end, select_action],
            outputs=[mixing_prompt],
        )
        
        mix_btn.click(
            fn=run_mixing,
            inputs=[stems_state, mixing_prompt, original_audio_state, available_stems_state],
            outputs=[mix_log, result_audio],
        )
    
    return app


# ──────────────────────────────────────────────
# Launch
# ──────────────────────────────────────────────

if __name__ == "__main__":
    app = build_app()
    app.queue()
    app.launch(
        server_name="0.0.0.0",
        server_port=7864,
        share=False,
        show_error=True,
    )
