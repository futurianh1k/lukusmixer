"""
Demucs Service - STEM 분리 로직
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Demucs 모델 정의
DEMUCS_MODELS = {
    "htdemucs": {
        "name": "4 스템 (기본)",
        "stems": ["vocals", "drums", "bass", "other"],
        "description": "빠른 속도, 4개 스템 분리",
    },
    "htdemucs_ft": {
        "name": "4 스템 (고품질)",
        "stems": ["vocals", "drums", "bass", "other"],
        "description": "최고 품질, 4개 스템 분리 (4배 느림)",
    },
    "htdemucs_6s": {
        "name": "6 스템 (기타/피아노)",
        "stems": ["vocals", "drums", "bass", "guitar", "piano", "other"],
        "description": "6개 스템 분리 (기타, 피아노 추가)",
    },
}

STEM_LABELS = {
    "vocals": {"ko": "보컬", "en": "Vocals", "color": "#22c55e"},
    "drums": {"ko": "드럼", "en": "Drums", "color": "#f97316"},
    "bass": {"ko": "베이스", "en": "Bass", "color": "#8b5cf6"},
    "guitar": {"ko": "기타", "en": "Guitar", "color": "#06b6d4"},
    "piano": {"ko": "피아노", "en": "Piano", "color": "#ec4899"},
    "other": {"ko": "기타 악기", "en": "Other", "color": "#64748b"},
}


class DemucsService:
    def __init__(self):
        self.demucs_available = False
        self.cuda_available = False
        self.librosa_available = False
        
        # Demucs 확인
        try:
            import demucs.separate
            self.demucs_module = demucs.separate
            self.demucs_available = True
        except ImportError:
            print("⚠️ demucs 미설치: pip install -U demucs")
            self.demucs_module = None
        
        # CUDA 확인
        try:
            import torch
            self.cuda_available = torch.cuda.is_available()
        except ImportError:
            pass
        
        # Librosa 확인 (duration 계산용)
        try:
            import librosa
            self.librosa_available = True
        except ImportError:
            pass
    
    def get_audio_duration(self, audio_path: str) -> float:
        """오디오 길이 반환 (초)"""
        if self.librosa_available:
            try:
                import librosa
                y, sr = librosa.load(audio_path, sr=None)
                return len(y) / sr
            except:
                pass
        
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except:
            pass
        
        return 0
    
    def separate(
        self,
        audio_path: str,
        model: str = "htdemucs",
        output_dir: Optional[str] = None,
        mp3_output: bool = True,
    ) -> Dict[str, str]:
        """
        Demucs로 STEM 분리 실행
        
        Returns:
            {stem_name: file_path} 딕셔너리
        """
        if not self.demucs_available:
            raise Exception("demucs가 설치되지 않았습니다. pip install -U demucs")
        
        if not os.path.exists(audio_path):
            raise Exception(f"파일을 찾을 수 없습니다: {audio_path}")
        
        # 출력 디렉토리
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="demucs_")
        
        # 디바이스 결정
        device = "cuda" if self.cuda_available else "cpu"
        
        # Demucs 명령어 구성
        cmd_args = [
            "-n", model,
            "-o", output_dir,
            "-d", device,
        ]
        
        if mp3_output:
            cmd_args.extend(["--mp3", "--mp3-bitrate", "320"])
        
        cmd_args.append(audio_path)
        
        print(f"🎛️ Demucs 실행: model={model}, device={device}")
        
        # Demucs 실행
        try:
            self.demucs_module.main(cmd_args)
        except SystemExit:
            pass  # demucs가 sys.exit() 호출하는 경우
        
        # 결과 파일 수집
        audio_name = Path(audio_path).stem
        output_subdir = Path(output_dir) / model / audio_name
        
        ext = ".mp3" if mp3_output else ".wav"
        
        stems = {}
        model_info = DEMUCS_MODELS.get(model, DEMUCS_MODELS["htdemucs"])
        
        for stem in model_info["stems"]:
            stem_path = output_subdir / f"{stem}{ext}"
            if stem_path.exists():
                stems[stem] = str(stem_path)
                print(f"  ✅ {stem}: {stem_path}")
        
        return stems
    
    def get_waveform_data(self, audio_path: str, samples: int = 1000) -> List[float]:
        """파형 데이터 추출 (시각화용)"""
        if not self.librosa_available:
            return []
        
        try:
            import librosa
            import numpy as np
            
            y, sr = librosa.load(audio_path, sr=22050)
            
            # 다운샘플링
            step = max(1, len(y) // samples)
            waveform = y[::step][:samples]
            
            # 정규화
            max_val = np.max(np.abs(waveform))
            if max_val > 0:
                waveform = waveform / max_val
            
            return waveform.tolist()
        except Exception as e:
            print(f"파형 추출 오류: {e}")
            return []
