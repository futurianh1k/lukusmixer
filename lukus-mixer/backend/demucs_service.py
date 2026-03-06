"""
Demucs Service - STEM 분리 로직
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
지원 엔진:
  - Demucs v4 (htdemucs, htdemucs_ft, htdemucs_6s)
  - audio-separator (BS-RoFormer + Demucs 6s 체이닝)

참고 출처:
  - python-audio-separator: https://github.com/nomadkaraoke/python-audio-separator (MIT)
  - BS-RoFormer: https://github.com/lucidrains/BS-RoFormer
  - Demucs v4: https://github.com/facebookresearch/demucs (MIT)
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Callable

# ──────────────────────────────────────────────
# 모델 정의
# ──────────────────────────────────────────────

DEMUCS_MODELS = {
    "htdemucs": {
        "name": "4 스템 (기본)",
        "stems": ["vocals", "drums", "bass", "other"],
        "description": "빠른 속도, 4개 스템 분리",
        "engine": "demucs",
    },
    "htdemucs_ft": {
        "name": "4 스템 (고품질)",
        "stems": ["vocals", "drums", "bass", "other"],
        "description": "최고 품질, 4개 스템 분리 (4배 느림)",
        "engine": "demucs",
    },
    "htdemucs_6s": {
        "name": "6 스템",
        "stems": ["vocals", "drums", "bass", "guitar", "piano", "other"],
        "description": "6개 스템 분리 (기타, 피아노 추가)",
        "engine": "demucs",
    },
    "bs_roformer_6s": {
        "name": "6 스템 (고급 보컬)",
        "stems": ["vocals", "drums", "bass", "guitar", "piano", "other"],
        "description": "BS-RoFormer 보컬(SDR 12.97) + Demucs 6s 반주 — 최고 품질 체이닝",
        "engine": "chained",
        "pipeline": ["bs_roformer_vocal", "demucs_6s_instrumental"],
    },
    "bs_roformer_4s": {
        "name": "4 스템 (고급 보컬)",
        "stems": ["vocals", "drums", "bass", "other"],
        "description": "BS-RoFormer 보컬(SDR 12.97) + Demucs ft 반주",
        "engine": "chained",
        "pipeline": ["bs_roformer_vocal", "demucs_ft_instrumental"],
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

BS_ROFORMER_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"


class DemucsService:
    def __init__(self):
        self.demucs_available = False
        self.cuda_available = False
        self.librosa_available = False
        self.audio_separator_available = False

        # Demucs 확인
        try:
            import demucs.separate
            self.demucs_module = demucs.separate
            self.demucs_available = True
        except ImportError:
            print("⚠️ demucs 미설치: pip install -U demucs")
            self.demucs_module = None

        # audio-separator 확인
        try:
            from audio_separator.separator import Separator
            self.audio_separator_available = True
        except ImportError:
            print("⚠️ audio-separator 미설치: pip install audio-separator[gpu]")

        # CUDA 확인
        try:
            import torch
            self.cuda_available = torch.cuda.is_available()
        except ImportError:
            pass

        # Librosa 확인
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

    # ──────────────────────────────────────────
    # 메인 분리 진입점
    # ──────────────────────────────────────────

    def separate(
        self,
        audio_path: str,
        model: str = "htdemucs",
        output_dir: Optional[str] = None,
        mp3_output: bool = True,
        progress_cb: Optional[Callable] = None,
    ) -> Dict[str, str]:
        """
        STEM 분리 실행 — 엔진 자동 선택

        Returns: {stem_name: file_path}
        """
        model_info = DEMUCS_MODELS.get(model)
        if not model_info:
            raise Exception(f"알 수 없는 모델: {model}")

        engine = model_info.get("engine", "demucs")

        if engine == "chained":
            return self._separate_chained(audio_path, model, output_dir, mp3_output, progress_cb)
        else:
            return self._separate_demucs(audio_path, model, output_dir, mp3_output, progress_cb)

    # ──────────────────────────────────────────
    # Engine: Demucs (기존)
    # ──────────────────────────────────────────

    def _separate_demucs(
        self, audio_path, model, output_dir, mp3_output, progress_cb
    ) -> Dict[str, str]:
        if not self.demucs_available:
            raise Exception("demucs가 설치되지 않았습니다. pip install -U demucs")

        if not os.path.exists(audio_path):
            raise Exception(f"파일을 찾을 수 없습니다: {audio_path}")

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="demucs_")

        device = "cuda" if self.cuda_available else "cpu"

        cmd_args = ["-n", model, "-o", output_dir, "-d", device]
        if mp3_output:
            cmd_args.extend(["--mp3", "--mp3-bitrate", "320"])
        cmd_args.append(audio_path)

        if progress_cb:
            progress_cb(f"Demucs 실행 중 (model={model}, device={device})")
        print(f"🎛️ Demucs 실행: model={model}, device={device}")

        try:
            self.demucs_module.main(cmd_args)
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
                print(f"  ✅ {stem}: {stem_path}")

        return stems

    # ──────────────────────────────────────────
    # Engine: Chained (BS-RoFormer + Demucs)
    # ──────────────────────────────────────────

    def _separate_chained(
        self, audio_path, model, output_dir, mp3_output, progress_cb
    ) -> Dict[str, str]:
        """
        다단계 체이닝 파이프라인:
          Pass 1: BS-RoFormer → Vocals / Instrumental
          Pass 2: Demucs → Instrumental → drums, bass, guitar, piano, other
        """
        if not self.audio_separator_available:
            raise Exception(
                "audio-separator가 설치되지 않았습니다. pip install audio-separator[gpu]"
            )

        if not os.path.exists(audio_path):
            raise Exception(f"파일을 찾을 수 없습니다: {audio_path}")

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="chained_")
        os.makedirs(output_dir, exist_ok=True)

        from audio_separator.separator import Separator

        model_info = DEMUCS_MODELS.get(model, DEMUCS_MODELS["bs_roformer_6s"])
        expected_stems = model_info["stems"]

        # 4스템 vs 6스템에 따라 Pass 2 모델 결정
        is_6s = "guitar" in expected_stems or "piano" in expected_stems
        demucs_model_name = "htdemucs_6s" if is_6s else "htdemucs_ft"

        work_dir = tempfile.mkdtemp(prefix="chain_work_")
        stems: Dict[str, str] = {}
        ext = ".mp3" if mp3_output else ".wav"

        try:
            # ═══ Pass 1: BS-RoFormer 보컬/반주 분리 ═══
            if progress_cb:
                progress_cb("Pass 1/2: BS-RoFormer 보컬 분리 (최고 품질)...")
            print(f"🎤 Pass 1: BS-RoFormer 보컬/반주 분리")

            sep = Separator(output_dir=work_dir)
            sep.load_model(BS_ROFORMER_MODEL)
            pass1_results = sep.separate(audio_path)

            vocal_wav = None
            instrumental_wav = None
            for f in pass1_results:
                full = os.path.join(work_dir, f)
                if "Vocal" in f:
                    vocal_wav = full
                elif "Instrumental" in f:
                    instrumental_wav = full

            if not vocal_wav or not instrumental_wav:
                raise Exception("BS-RoFormer 분리 실패: Vocals/Instrumental 파일 없음")

            print(f"  ✅ Vocals: {vocal_wav}")
            print(f"  ✅ Instrumental: {instrumental_wav}")

            # vocals를 mp3로 변환하여 최종 출력
            vocals_final = os.path.join(output_dir, f"vocals{ext}")
            self._convert_audio(vocal_wav, vocals_final, mp3_output)
            stems["vocals"] = vocals_final

            # ═══ Pass 2: Demucs로 반주 분리 ═══
            if progress_cb:
                progress_cb(f"Pass 2/2: Demucs {demucs_model_name} 반주 분리...")
            print(f"🎛️ Pass 2: Demucs {demucs_model_name} 반주 분리")

            sep.load_model(f"{demucs_model_name}.yaml")
            pass2_results = sep.separate(instrumental_wav)

            stem_map = {
                "Drums": "drums", "Bass": "bass", "Guitar": "guitar",
                "Piano": "piano", "Other": "other", "Vocals": "_skip",
            }

            for f in pass2_results:
                full = os.path.join(work_dir, f)
                matched_stem = None
                for key, stem_name in stem_map.items():
                    if f"({key})" in f:
                        matched_stem = stem_name
                        break

                if matched_stem and matched_stem != "_skip" and matched_stem in expected_stems:
                    final_path = os.path.join(output_dir, f"{matched_stem}{ext}")
                    self._convert_audio(full, final_path, mp3_output)
                    stems[matched_stem] = final_path
                    print(f"  ✅ {matched_stem}: {final_path}")

            # Demucs 6s가 반주에서 vocals를 또 뽑을 수 있으므로, 
            # "other"에 합산하거나 버림
            if "other" not in stems:
                for f in pass2_results:
                    if "(Other)" in f:
                        full = os.path.join(work_dir, f)
                        final_path = os.path.join(output_dir, f"other{ext}")
                        self._convert_audio(full, final_path, mp3_output)
                        stems["other"] = final_path

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        return stems

    def _convert_audio(self, src: str, dst: str, to_mp3: bool):
        """WAV → MP3 변환 (또는 그냥 복사)"""
        if to_mp3 and dst.endswith(".mp3"):
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(src)
                audio.export(dst, format="mp3", bitrate="320k")
                return
            except Exception as e:
                print(f"  ⚠️ MP3 변환 실패, WAV 복사: {e}")
        shutil.copy2(src, dst)

    # ──────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────

    def get_waveform_data(self, audio_path: str, samples: int = 1000) -> List[float]:
        """파형 데이터 추출 (시각화용)"""
        if not self.librosa_available:
            return []
        try:
            import librosa
            import numpy as np
            y, sr = librosa.load(audio_path, sr=22050)
            step = max(1, len(y) // samples)
            waveform = y[::step][:samples]
            max_val = np.max(np.abs(waveform))
            if max_val > 0:
                waveform = waveform / max_val
            return waveform.tolist()
        except Exception as e:
            print(f"파형 추출 오류: {e}")
            return []
