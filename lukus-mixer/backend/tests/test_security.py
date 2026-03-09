"""
보안 유틸리티 및 업로드 검증 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_sanitize_filename, _safe_resolve, _validate_audio_magic, 업로드 제한 검증

실행:
    cd backend
    python -m pytest tests/test_security.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import (
    _sanitize_filename,
    _safe_resolve,
    _validate_audio_magic,
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_SIZE,
)
from fastapi import HTTPException


class TestSanitizeFilename:
    """파일명 경로 순회 방지"""

    def test_normal_filename(self):
        assert _sanitize_filename("test.txt") == "test.txt"

    def test_filename_with_path(self):
        assert _sanitize_filename("some/path/test.txt") == "test.txt"

    def test_path_traversal_dots(self):
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_filename("..")
        assert exc_info.value.status_code == 400

    def test_path_traversal_attack(self):
        result = _sanitize_filename("../../../etc/passwd")
        assert result == "passwd"

    def test_empty_filename(self):
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_filename("")
        assert exc_info.value.status_code == 400

    def test_single_dot(self):
        with pytest.raises(HTTPException) as exc_info:
            _sanitize_filename(".")
        assert exc_info.value.status_code == 400

    def test_korean_filename(self):
        assert _sanitize_filename("테스트_파일.txt") == "테스트_파일.txt"

    def test_spaces_in_filename(self):
        assert _sanitize_filename("my file.txt") == "my file.txt"


class TestSafeResolve:
    """경로 범위 검증"""

    def test_valid_path(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        result = _safe_resolve(tmp_path, "sub")
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_path_traversal_blocked(self, tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            _safe_resolve(tmp_path, "..", "..", "etc", "passwd")
        assert exc_info.value.status_code == 400

    def test_nested_valid_path(self, tmp_path):
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        result = _safe_resolve(tmp_path, "a", "b")
        assert str(result).startswith(str(tmp_path.resolve()))


class TestValidateAudioMagic:
    """파일 헤더(Magic number) 검증"""

    def test_mp3_id3_tag(self):
        header = b"ID3\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        assert _validate_audio_magic(header, ".mp3") is True

    def test_mp3_sync_word_fb(self):
        header = b"\xff\xfb\x90\x00" + b"\x00" * 12
        assert _validate_audio_magic(header, ".mp3") is True

    def test_mp3_sync_word_f3(self):
        header = b"\xff\xf3\x90\x00" + b"\x00" * 12
        assert _validate_audio_magic(header, ".mp3") is True

    def test_wav_riff(self):
        header = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 2
        assert _validate_audio_magic(header, ".wav") is True

    def test_flac(self):
        header = b"fLaC\x00\x00\x00\x22" + b"\x00" * 8
        assert _validate_audio_magic(header, ".flac") is True

    def test_ogg(self):
        header = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        assert _validate_audio_magic(header, ".ogg") is True

    def test_m4a_ftyp(self):
        header = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 4
        assert _validate_audio_magic(header, ".m4a") is True

    def test_mismatched_extension(self):
        header = b"ID3\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        assert _validate_audio_magic(header, ".wav") is False

    def test_invalid_header(self):
        header = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        assert _validate_audio_magic(header, ".mp3") is False

    def test_exe_disguised_as_mp3(self):
        header = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 8
        assert _validate_audio_magic(header, ".mp3") is False

    def test_m4a_without_ftyp(self):
        header = b"\x00\x00\x00\x20XXXX" + b"\x00" * 6
        assert _validate_audio_magic(header, ".m4a") is False


class TestAllowedExtensions:
    """허용 확장자 목록 검증"""

    def test_mp3_allowed(self):
        assert ".mp3" in ALLOWED_EXTENSIONS

    def test_wav_allowed(self):
        assert ".wav" in ALLOWED_EXTENSIONS

    def test_flac_allowed(self):
        assert ".flac" in ALLOWED_EXTENSIONS

    def test_exe_not_allowed(self):
        assert ".exe" not in ALLOWED_EXTENSIONS

    def test_py_not_allowed(self):
        assert ".py" not in ALLOWED_EXTENSIONS

    def test_php_not_allowed(self):
        assert ".php" not in ALLOWED_EXTENSIONS


class TestUploadLimits:
    """업로드 크기 제한"""

    def test_max_size_is_reasonable(self):
        assert MAX_UPLOAD_SIZE >= 50 * 1024 * 1024   # 최소 50MB
        assert MAX_UPLOAD_SIZE <= 500 * 1024 * 1024   # 최대 500MB
