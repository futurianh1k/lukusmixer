"""
Demucs Service - STEM 분리 로직
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
지원 엔진:
  - Demucs v4 (htdemucs, htdemucs_ft, htdemucs_6s)
  - audio-separator 체이닝:
    * BS-RoFormer + Demucs (6스템)
    * BS-RoFormer + Demucs + MelBand-RoFormer + DrumSep (10스템)

참고 출처:
  - python-audio-separator: https://github.com/nomadkaraoke/python-audio-separator (MIT)
  - BS-RoFormer: https://github.com/lucidrains/BS-RoFormer
  - Demucs v4: https://github.com/facebookresearch/demucs (MIT)
  - MelBand-RoFormer Karaoke: aufr33 & viperx (보컬 세분화용)
  - MDX23C DrumSep: aufr33 & jarredou (드럼 세분화용)
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
    "bs_roformer_10s": {
        "name": "10 스템 (보컬+드럼 세분화)",
        "stems": [
            "lead_vocals", "backing_vocals",
            "kick", "snare", "toms", "cymbals",
            "bass", "guitar", "piano", "other",
        ],
        "description": "BS-RoFormer + Demucs 6s + MelBand Karaoke + DrumSep — 10스템 최고 품질",
        "engine": "chained_10s",
    },
}

STEM_LABELS = {
    "vocals": {"ko": "보컬", "en": "Vocals", "color": "#22c55e"},
    "lead_vocals": {"ko": "리드 보컬", "en": "Lead Vocals", "color": "#22c55e"},
    "backing_vocals": {"ko": "백킹 보컬", "en": "Backing Vocals", "color": "#4ade80"},
    "drums": {"ko": "드럼", "en": "Drums", "color": "#f97316"},
    "kick": {"ko": "킥", "en": "Kick", "color": "#f97316"},
    "snare": {"ko": "스네어", "en": "Snare", "color": "#fb923c"},
    "toms": {"ko": "탐", "en": "Toms", "color": "#fdba74"},
    "cymbals": {"ko": "심벌즈", "en": "Cymbals", "color": "#fde68a"},
    "bass": {"ko": "베이스", "en": "Bass", "color": "#8b5cf6"},
    "guitar": {"ko": "기타", "en": "Guitar", "color": "#06b6d4"},
    "piano": {"ko": "피아노", "en": "Piano", "color": "#ec4899"},
    "other": {"ko": "기타 악기", "en": "Other", "color": "#64748b"},
}

# 10스템에서 하위 스템 계층 구조 (UI 트리 표시용)
STEM_HIERARCHY = {
    "lead_vocals": {"parent": "vocals", "group": "vocals"},
    "backing_vocals": {"parent": "vocals", "group": "vocals"},
    "kick": {"parent": "drums", "group": "drums"},
    "snare": {"parent": "drums", "group": "drums"},
    "toms": {"parent": "drums", "group": "drums"},
    "cymbals": {"parent": "drums", "group": "drums"},
}

BS_ROFORMER_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
MELBAND_KARAOKE_MODEL = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"
DRUMSEP_MODEL = "MDX23C-DrumSep-aufr33-jarredou.ckpt"


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
        """오디오 길이 반환 (초) — librosa.get_duration 우선, fallback으로 pydub"""
        if self.librosa_available:
            try:
                import librosa
                return librosa.get_duration(path=audio_path)
            except Exception as e:
                print(f"⚠️ librosa duration 실패: {e}")
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except Exception as e:
            print(f"⚠️ pydub duration 실패: {e}")
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

        if engine == "chained_10s":
            return self._separate_chained_10s(audio_path, model, output_dir, mp3_output, progress_cb)
        elif engine == "chained":
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

    # ──────────────────────────────────────────
    # Engine: Chained 10-stem
    # ──────────────────────────────────────────

    def _separate_chained_10s(
        self, audio_path, model, output_dir, mp3_output, progress_cb
    ) -> Dict[str, str]:
        """
        4-Pass 체이닝 파이프라인 (10스템):
          Pass 1: BS-RoFormer → Vocals / Instrumental
          Pass 2: Demucs 6s → Instrumental → drums, bass, guitar, piano, other
          Pass 3: MelBand-RoFormer Karaoke → Vocals → Lead Vocals / Backing Vocals
          Pass 4: MDX23C DrumSep → Drums → kick, snare, toms, hh, ride, crash → (hh+ride+crash → cymbals)
        """
        if not self.audio_separator_available:
            raise Exception(
                "audio-separator가 설치되지 않았습니다. pip install audio-separator[gpu]"
            )

        if not os.path.exists(audio_path):
            raise Exception(f"파일을 찾을 수 없습니다: {audio_path}")

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="chained10_")
        os.makedirs(output_dir, exist_ok=True)

        from audio_separator.separator import Separator

        work_dir = tempfile.mkdtemp(prefix="chain10_work_")
        stems: Dict[str, str] = {}
        ext = ".mp3" if mp3_output else ".wav"

        try:
            # ═══ Pass 1/4: BS-RoFormer 보컬/반주 분리 ═══
            if progress_cb:
                progress_cb("Pass 1/4: BS-RoFormer 보컬 분리 (최고 품질)...")
            print(f"🎤 Pass 1/4: BS-RoFormer 보컬/반주 분리")

            pass1_dir = os.path.join(work_dir, "pass1")
            os.makedirs(pass1_dir)
            sep = Separator(output_dir=pass1_dir)
            sep.load_model(BS_ROFORMER_MODEL)
            pass1_results = sep.separate(audio_path)

            vocal_wav = None
            instrumental_wav = None
            for f in pass1_results:
                full = os.path.join(pass1_dir, f)
                if "Vocal" in f:
                    vocal_wav = full
                elif "Instrumental" in f:
                    instrumental_wav = full

            if not vocal_wav or not instrumental_wav:
                raise Exception("Pass 1 실패: Vocals/Instrumental 파일 없음")
            print(f"  ✅ Pass 1 완료")

            # ═══ Pass 2/4: Demucs 6s 반주 분리 ═══
            if progress_cb:
                progress_cb("Pass 2/4: Demucs 6s 반주 분리...")
            print(f"🎛️ Pass 2/4: Demucs 6s 반주 분리")

            pass2_dir = os.path.join(work_dir, "pass2")
            os.makedirs(pass2_dir)
            sep2 = Separator(output_dir=pass2_dir)
            sep2.load_model("htdemucs_6s.yaml")
            pass2_results = sep2.separate(instrumental_wav)

            drums_wav = None
            stem_map_p2 = {
                "Drums": "drums", "Bass": "bass", "Guitar": "guitar",
                "Piano": "piano", "Other": "other", "Vocals": "_skip",
            }

            for f in pass2_results:
                full = os.path.join(pass2_dir, f)
                for key, stem_name in stem_map_p2.items():
                    if f"({key})" in f:
                        if stem_name == "drums":
                            drums_wav = full
                        elif stem_name != "_skip":
                            final_path = os.path.join(output_dir, f"{stem_name}{ext}")
                            self._convert_audio(full, final_path, mp3_output)
                            stems[stem_name] = final_path
                            print(f"  ✅ {stem_name}: {final_path}")
                        break

            if not drums_wav:
                raise Exception("Pass 2 실패: Drums 파일 없음")
            print(f"  ✅ Pass 2 완료")

            # ═══ Pass 3/4: MelBand-RoFormer 보컬 세분화 ═══
            if progress_cb:
                progress_cb("Pass 3/4: MelBand-RoFormer 보컬 세분화 (Lead/Backing)...")
            print(f"🎙️ Pass 3/4: MelBand-RoFormer 보컬 세분화")

            pass3_dir = os.path.join(work_dir, "pass3")
            os.makedirs(pass3_dir)
            sep3 = Separator(output_dir=pass3_dir)
            sep3.load_model(MELBAND_KARAOKE_MODEL)
            pass3_results = sep3.separate(vocal_wav)

            mel_tag = "mel_band_roformer_karaoke"
            for f in pass3_results:
                full = os.path.join(pass3_dir, f)
                if f"(Instrumental)_{mel_tag}" in f:
                    final_path = os.path.join(output_dir, f"backing_vocals{ext}")
                    self._convert_audio(full, final_path, mp3_output)
                    stems["backing_vocals"] = final_path
                    print(f"  ✅ backing_vocals: {final_path}")
                elif f"(Vocals)_{mel_tag}" in f:
                    final_path = os.path.join(output_dir, f"lead_vocals{ext}")
                    self._convert_audio(full, final_path, mp3_output)
                    stems["lead_vocals"] = final_path
                    print(f"  ✅ lead_vocals: {final_path}")

            print(f"  ✅ Pass 3 완료")

            # ═══ Pass 4/4: DrumSep 드럼 세분화 ═══
            if progress_cb:
                progress_cb("Pass 4/4: DrumSep 드럼 세분화 (Kick/Snare/Toms/Cymbals)...")
            print(f"🥁 Pass 4/4: DrumSep 드럼 세분화")

            pass4_dir = os.path.join(work_dir, "pass4")
            os.makedirs(pass4_dir)
            sep4 = Separator(output_dir=pass4_dir)
            sep4.load_model(DRUMSEP_MODEL)
            pass4_results = sep4.separate(drums_wav)

            cymbal_parts = []
            drum_stem_map = {
                "kick": "kick", "snare": "snare", "toms": "toms",
            }
            cymbal_stems = ["hh", "ride", "crash"]

            for f in pass4_results:
                full = os.path.join(pass4_dir, f)
                matched = False
                for key, stem_name in drum_stem_map.items():
                    if f"({key})" in f:
                        final_path = os.path.join(output_dir, f"{stem_name}{ext}")
                        self._convert_audio(full, final_path, mp3_output)
                        stems[stem_name] = final_path
                        print(f"  ✅ {stem_name}: {final_path}")
                        matched = True
                        break
                if not matched:
                    for cs in cymbal_stems:
                        if f"({cs})" in f:
                            cymbal_parts.append(full)
                            break

            if cymbal_parts:
                cymbals_path = os.path.join(output_dir, f"cymbals{ext}")
                self._merge_audio_files(cymbal_parts, cymbals_path, mp3_output)
                stems["cymbals"] = cymbals_path
                print(f"  ✅ cymbals (hh+ride+crash 합산): {cymbals_path}")

            print(f"  ✅ Pass 4 완료")

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        return stems

    def _merge_audio_files(self, sources: List[str], dst: str, to_mp3: bool):
        """여러 WAV 파일을 합산하여 하나로 병합"""
        try:
            from pydub import AudioSegment
            combined = None
            for src in sources:
                audio = AudioSegment.from_file(src)
                if combined is None:
                    combined = audio
                else:
                    combined = combined.overlay(audio)
            if combined:
                fmt = "mp3" if to_mp3 and dst.endswith(".mp3") else "wav"
                combined.export(dst, format=fmt, bitrate="320k" if fmt == "mp3" else None)
        except (ImportError, IOError, ValueError) as e:
            print(f"  ⚠️ 오디오 병합 실패 ({type(e).__name__}): {e}")
            if sources:
                shutil.copy2(sources[0], dst)

    def _convert_audio(self, src: str, dst: str, to_mp3: bool):
        """WAV → MP3 변환 (또는 그냥 복사)"""
        if to_mp3 and dst.endswith(".mp3"):
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(src)
                audio.export(dst, format="mp3", bitrate="320k")
                return
            except (ImportError, IOError, ValueError) as e:
                print(f"  ⚠️ MP3 변환 실패, WAV 복사 ({type(e).__name__}): {e}")
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
        except (RuntimeError, IOError, ValueError) as e:
            print(f"⚠️ 파형 추출 오류 ({type(e).__name__}): {e}")
            return []
