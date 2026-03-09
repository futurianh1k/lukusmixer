"""
믹싱 로직 유닛 테스트
━━━━━━━━━━━━━━━━━━━━━━
execute_mix 함수의 스템 믹싱 및 볼륨 조절 검증

실행:
    cd backend
    python -m pytest tests/test_mixing.py -v

의존성: pydub (pip install pydub), ffmpeg
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pydub = pytest.importorskip("pydub", reason="pydub 미설치 — pip install pydub")
from pydub import AudioSegment
from pydub.generators import Sine

from main import execute_mix


@pytest.fixture
def stem_files(tmp_path):
    """테스트용 스템 WAV 파일 생성 (1kHz 사인파, 5초)"""
    stems = {}
    for name in ["vocals", "drums", "bass", "other"]:
        tone = Sine(1000).to_audio_segment(duration=5000).set_frame_rate(44100)
        path = tmp_path / f"{name}.wav"
        tone.export(str(path), format="wav")
        stems[name] = str(path)
    return stems


class TestExecuteMix:
    """execute_mix 기본 동작"""

    def test_no_commands_returns_original_mix(self, stem_files):
        result_path = execute_mix(stem_files, [])
        assert os.path.exists(result_path)
        result = AudioSegment.from_file(result_path)
        assert len(result) >= 4900  # ~5초 (±100ms 허용)
        os.unlink(result_path)

    def test_volume_up(self, stem_files):
        commands = [{
            "instrument": "vocals",
            "start_sec": 0,
            "end_sec": 5,
            "volume_db": 6.0,
            "original_text": "보컬 크게",
        }]
        result_path = execute_mix(stem_files, commands)
        assert os.path.exists(result_path)
        os.unlink(result_path)

    def test_mute_stem(self, stem_files):
        commands = [{
            "instrument": "drums",
            "start_sec": 0,
            "end_sec": 5,
            "volume_db": -100.0,
            "original_text": "드럼 음소거",
        }]
        result_path = execute_mix(stem_files, commands)
        assert os.path.exists(result_path)
        os.unlink(result_path)

    def test_partial_section(self, stem_files):
        commands = [{
            "instrument": "bass",
            "start_sec": 1,
            "end_sec": 3,
            "volume_db": -6.0,
            "original_text": "1초~3초 베이스 작게",
        }]
        result_path = execute_mix(stem_files, commands)
        assert os.path.exists(result_path)
        result = AudioSegment.from_file(result_path)
        assert len(result) >= 4900
        os.unlink(result_path)

    def test_multiple_commands(self, stem_files):
        commands = [
            {"instrument": "vocals", "start_sec": 0, "end_sec": 5,
             "volume_db": 6.0, "original_text": "보컬 크게"},
            {"instrument": "drums", "start_sec": 0, "end_sec": 5,
             "volume_db": -100.0, "original_text": "드럼 음소거"},
            {"instrument": "bass", "start_sec": 2, "end_sec": 4,
             "volume_db": -6.0, "original_text": "2~4초 베이스 작게"},
        ]
        result_path = execute_mix(stem_files, commands)
        assert os.path.exists(result_path)
        os.unlink(result_path)

    def test_unknown_instrument_ignored(self, stem_files):
        commands = [{
            "instrument": "harpsichord",
            "start_sec": 0,
            "end_sec": 5,
            "volume_db": 6.0,
            "original_text": "하프시코드 크게",
        }]
        result_path = execute_mix(stem_files, commands)
        assert os.path.exists(result_path)
        os.unlink(result_path)

    def test_empty_stems_raises(self):
        with pytest.raises(Exception, match="유효한 스템"):
            execute_mix({}, [])

    def test_output_is_mp3(self, stem_files):
        result_path = execute_mix(stem_files, [])
        assert result_path.endswith(".mp3")
        os.unlink(result_path)
