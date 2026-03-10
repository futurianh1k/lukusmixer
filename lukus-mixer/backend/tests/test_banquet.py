"""
Banquet 서비스 및 14스템 통합 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from banquet_service import (
    BanquetService,
    BANQUET_STEMS,
    QUERY_AUDIO_DIR,
    BANQUET_CHECKPOINT_DIR,
)
from demucs_service import (
    DEMUCS_MODELS,
    STEM_LABELS,
    STEM_HIERARCHY,
)


class TestBanquetStems:
    """Banquet 스템 정의 검증"""

    def test_banquet_stems_defined(self):
        assert len(BANQUET_STEMS) == 4
        assert "strings" in BANQUET_STEMS
        assert "brass" in BANQUET_STEMS
        assert "woodwinds" in BANQUET_STEMS
        assert "synthesizer" in BANQUET_STEMS

    def test_banquet_stems_have_query_files(self):
        for stem, info in BANQUET_STEMS.items():
            assert "query_file" in info
            assert info["query_file"].endswith(".wav")

    def test_banquet_stems_have_labels(self):
        for stem, info in BANQUET_STEMS.items():
            assert "ko" in info
            assert "en" in info
            assert "color" in info

    def test_query_audio_files_exist(self):
        for stem, info in BANQUET_STEMS.items():
            qpath = QUERY_AUDIO_DIR / info["query_file"]
            assert qpath.exists(), f"쿼리 파일 누락: {qpath}"


class TestDemucsModelsBanquet:
    """DEMUCS_MODELS에 banquet_14s 모델 등록 검증"""

    def test_banquet_14s_exists(self):
        assert "banquet_14s" in DEMUCS_MODELS

    def test_banquet_14s_engine(self):
        assert DEMUCS_MODELS["banquet_14s"]["engine"] == "chained_banquet"

    def test_banquet_14s_stem_count(self):
        stems = DEMUCS_MODELS["banquet_14s"]["stems"]
        assert len(stems) == 14

    def test_banquet_14s_contains_new_stems(self):
        stems = DEMUCS_MODELS["banquet_14s"]["stems"]
        for new_stem in ["strings", "brass", "woodwinds", "synthesizer"]:
            assert new_stem in stems, f"새 스템 누락: {new_stem}"

    def test_banquet_14s_retains_10s_stems(self):
        stems = DEMUCS_MODELS["banquet_14s"]["stems"]
        for existing in [
            "lead_vocals", "backing_vocals",
            "kick", "snare", "toms", "cymbals",
            "bass", "guitar", "piano", "other",
        ]:
            assert existing in stems, f"기존 스템 누락: {existing}"


class TestStemLabels:
    """STEM_LABELS에 새 스템 라벨 등록 검증"""

    def test_new_stems_in_labels(self):
        for stem in ["strings", "brass", "woodwinds", "synthesizer"]:
            assert stem in STEM_LABELS, f"STEM_LABELS 누락: {stem}"

    def test_new_stems_have_korean_labels(self):
        expected_ko = {
            "strings": "현악기",
            "brass": "금관악기",
            "woodwinds": "목관악기",
            "synthesizer": "신디사이저",
        }
        for stem, ko in expected_ko.items():
            assert STEM_LABELS[stem]["ko"] == ko


class TestStemHierarchy:
    """STEM_HIERARCHY에 banquet 그룹 등록 검증"""

    def test_banquet_group_exists(self):
        banquet_stems = [k for k, v in STEM_HIERARCHY.items() if v["group"] == "banquet"]
        assert len(banquet_stems) == 4

    def test_banquet_stems_in_hierarchy(self):
        for stem in ["strings", "brass", "woodwinds", "synthesizer"]:
            assert stem in STEM_HIERARCHY
            assert STEM_HIERARCHY[stem]["group"] == "banquet"
            assert STEM_HIERARCHY[stem]["parent"] == "other"


class TestBanquetServiceInit:
    """BanquetService 초기화 검증"""

    def test_service_creates_without_error(self):
        svc = BanquetService()
        assert isinstance(svc, BanquetService)

    def test_available_with_checkpoint(self):
        svc = BanquetService()
        ckpt = BANQUET_CHECKPOINT_DIR / "ev-pre-aug.ckpt"
        if ckpt.exists():
            assert svc.available
        else:
            assert not svc.available

    def test_unavailable_with_bad_path(self):
        svc = BanquetService(checkpoint="/nonexistent/path.ckpt")
        assert not svc.available

    def test_get_default_queries(self):
        svc = BanquetService()
        queries = svc.get_default_queries()
        assert len(queries) == 4
        for stem, path in queries.items():
            assert os.path.exists(path)


class TestPromptParserBanquet:
    """프롬프트 파서에 새 Banquet 키워드 테스트"""

    @pytest.fixture
    def parse(self):
        from main import parse_mixing_prompt
        return parse_mixing_prompt

    @pytest.fixture
    def all_stems(self):
        return DEMUCS_MODELS["banquet_14s"]["stems"]

    def test_strings_keyword(self, parse, all_stems):
        cmds = parse("현악기 키워줘", 180, all_stems)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "strings"

    def test_strings_alias_violin(self, parse, all_stems):
        cmds = parse("바이올린 줄여", 180, all_stems)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "strings"

    def test_brass_keyword(self, parse, all_stems):
        cmds = parse("금관악기 크게", 180, all_stems)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "brass"

    def test_brass_alias_trumpet(self, parse, all_stems):
        cmds = parse("트럼펫 음소거", 180, all_stems)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "brass"

    def test_woodwinds_keyword(self, parse, all_stems):
        cmds = parse("목관악기 작게", 180, all_stems)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "woodwinds"

    def test_woodwinds_alias_flute(self, parse, all_stems):
        cmds = parse("플루트 키워줘", 180, all_stems)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "woodwinds"

    def test_synthesizer_keyword(self, parse, all_stems):
        cmds = parse("신디사이저 줄여", 180, all_stems)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "synthesizer"

    def test_synthesizer_alias_synth(self, parse, all_stems):
        cmds = parse("신스 크게", 180, all_stems)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "synthesizer"

    def test_mixed_14stem_prompt(self, parse, all_stems):
        prompt = """전주 현악기 키워줘
30초~60초 트럼펫 줄여
플루트 음소거
후주 신스 크게"""
        cmds = parse(prompt, 180, all_stems)
        assert len(cmds) == 4
        instruments = [c["instrument"] for c in cmds]
        assert "strings" in instruments
        assert "brass" in instruments
        assert "woodwinds" in instruments
        assert "synthesizer" in instruments
