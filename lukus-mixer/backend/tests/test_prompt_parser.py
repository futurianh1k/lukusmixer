"""
프롬프트 파서 유닛 테스트
━━━━━━━━━━━━━━━━━━━━━━━━
main.py의 parse_mixing_prompt, INSTRUMENT_MAP, SECTION_MAP, VOLUME_ACTION_MAP 검증

실행:
    cd backend
    python -m pytest tests/test_prompt_parser.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import (
    parse_mixing_prompt,
    INSTRUMENT_MAP,
    SECTION_MAP,
    VOLUME_ACTION_MAP,
)


BASIC_STEMS = ["vocals", "drums", "bass", "other", "guitar", "piano"]
FULL_STEMS = [
    "lead_vocals", "backing_vocals",
    "kick", "snare", "toms", "cymbals",
    "bass", "guitar", "piano", "other",
]


class TestInstrumentRecognition:
    """한국어 악기 키워드 → 영문 스템명 매핑"""

    def test_basic_korean_keywords(self):
        assert INSTRUMENT_MAP["보컬"] == "vocals"
        assert INSTRUMENT_MAP["드럼"] == "drums"
        assert INSTRUMENT_MAP["베이스"] == "bass"
        assert INSTRUMENT_MAP["기타"] == "guitar"
        assert INSTRUMENT_MAP["피아노"] == "piano"

    def test_10stem_korean_keywords(self):
        assert INSTRUMENT_MAP["리드보컬"] == "lead_vocals"
        assert INSTRUMENT_MAP["백킹보컬"] == "backing_vocals"
        assert INSTRUMENT_MAP["코러스"] == "backing_vocals"
        assert INSTRUMENT_MAP["킥"] == "kick"
        assert INSTRUMENT_MAP["스네어"] == "snare"
        assert INSTRUMENT_MAP["탐"] == "toms"
        assert INSTRUMENT_MAP["심벌즈"] == "cymbals"
        assert INSTRUMENT_MAP["하이햇"] == "cymbals"

    def test_alias_keywords(self):
        assert INSTRUMENT_MAP["목소리"] == "vocals"
        assert INSTRUMENT_MAP["노래"] == "vocals"
        assert INSTRUMENT_MAP["건반"] == "piano"
        assert INSTRUMENT_MAP["전기기타"] == "guitar"
        assert INSTRUMENT_MAP["킥드럼"] == "kick"


class TestSingleLinePrompt:
    """단일 라인 프롬프트 파싱"""

    def test_instrument_volume_up(self):
        cmds = parse_mixing_prompt("보컬 크게", 180, BASIC_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "vocals"
        assert cmds[0]["volume_db"] == 6.0

    def test_instrument_mute(self):
        cmds = parse_mixing_prompt("드럼 음소거", 180, BASIC_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "drums"
        assert cmds[0]["volume_db"] == -100.0

    def test_instrument_volume_down(self):
        cmds = parse_mixing_prompt("베이스 줄여", 180, BASIC_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "bass"
        assert cmds[0]["volume_db"] == -6.0

    def test_no_match_returns_empty(self):
        cmds = parse_mixing_prompt("안녕하세요", 180, BASIC_STEMS)
        assert len(cmds) == 0

    def test_empty_prompt_returns_empty(self):
        cmds = parse_mixing_prompt("", 180, BASIC_STEMS)
        assert len(cmds) == 0

    def test_stem_not_in_available_stems(self):
        cmds = parse_mixing_prompt("피아노 크게", 180, ["vocals", "drums", "bass", "other"])
        assert len(cmds) == 0


class TestSectionRecognition:
    """구간 키워드 인식"""

    def test_intro_section(self):
        cmds = parse_mixing_prompt("전주 드럼 키워", 180, BASIC_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["start_sec"] == 0.0
        assert cmds[0]["end_sec"] == 15.0

    def test_outro_section(self):
        cmds = parse_mixing_prompt("후주 보컬 크게", 180, BASIC_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["start_sec"] == 150.0  # 180 - 30
        assert cmds[0]["end_sec"] == 180.0

    def test_full_section(self):
        cmds = parse_mixing_prompt("전체 기타 음소거", 180, BASIC_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["start_sec"] == 0.0
        assert cmds[0]["end_sec"] == 180.0

    def test_time_range_seconds(self):
        cmds = parse_mixing_prompt("30초~60초 피아노 크게", 180, BASIC_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["start_sec"] == 30.0
        assert cmds[0]["end_sec"] == 60.0

    def test_no_section_defaults_full(self):
        cmds = parse_mixing_prompt("보컬 크게", 180, BASIC_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["start_sec"] == 0.0
        assert cmds[0]["end_sec"] == 180.0


class TestMultiLinePrompt:
    """복수 라인 프롬프트 파싱"""

    def test_multiple_lines(self):
        prompt = "보컬 크게\n드럼 음소거\n베이스 줄여"
        cmds = parse_mixing_prompt(prompt, 180, BASIC_STEMS)
        assert len(cmds) == 3
        assert cmds[0]["instrument"] == "vocals"
        assert cmds[1]["instrument"] == "drums"
        assert cmds[2]["instrument"] == "bass"

    def test_mixed_lines_with_blanks(self):
        prompt = "보컬 크게\n\n\n드럼 줄여"
        cmds = parse_mixing_prompt(prompt, 180, BASIC_STEMS)
        assert len(cmds) == 2

    def test_complex_prompt(self):
        prompt = "전주 드럼 키워줘\n30초~40초 피아노 작게\n기타 음소거\n후주 보컬 키워줘"
        cmds = parse_mixing_prompt(prompt, 180, BASIC_STEMS)
        assert len(cmds) == 4
        assert cmds[0]["instrument"] == "drums"
        assert cmds[0]["start_sec"] == 0.0
        assert cmds[0]["end_sec"] == 15.0
        assert cmds[1]["instrument"] == "piano"
        assert cmds[2]["instrument"] == "guitar"
        assert cmds[2]["volume_db"] == -100.0
        assert cmds[3]["instrument"] == "vocals"
        assert cmds[3]["start_sec"] == 150.0


class TestVolumeActions:
    """볼륨 액션 매핑"""

    def test_volume_max(self):
        cmds = parse_mixing_prompt("보컬 최대로 크게", 180, BASIC_STEMS)
        assert cmds[0]["volume_db"] == 12.0

    def test_volume_very_loud(self):
        cmds = parse_mixing_prompt("드럼 매우 크게", 180, BASIC_STEMS)
        assert cmds[0]["volume_db"] == 9.0

    def test_volume_slight_up(self):
        cmds = parse_mixing_prompt("기타 조금 키워", 180, BASIC_STEMS)
        assert cmds[0]["volume_db"] == 3.0

    def test_volume_slight_down(self):
        cmds = parse_mixing_prompt("피아노 조금 줄여", 180, BASIC_STEMS)
        assert cmds[0]["volume_db"] == -3.0

    def test_volume_very_quiet(self):
        cmds = parse_mixing_prompt("베이스 매우 작게", 180, BASIC_STEMS)
        assert cmds[0]["volume_db"] == -9.0

    def test_volume_remove(self):
        cmds = parse_mixing_prompt("기타 제거", 180, BASIC_STEMS)
        assert cmds[0]["volume_db"] == -100.0


class Test10StemPrompt:
    """10스템 모드 프롬프트"""

    def test_lead_vocals(self):
        cmds = parse_mixing_prompt("리드보컬 크게", 180, FULL_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "lead_vocals"

    def test_backing_vocals_alias(self):
        cmds = parse_mixing_prompt("코러스 줄여", 180, FULL_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "backing_vocals"

    def test_kick_drum(self):
        cmds = parse_mixing_prompt("킥 키워", 180, FULL_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "kick"

    def test_cymbals_alias(self):
        cmds = parse_mixing_prompt("하이햇 음소거", 180, FULL_STEMS)
        assert len(cmds) == 1
        assert cmds[0]["instrument"] == "cymbals"
