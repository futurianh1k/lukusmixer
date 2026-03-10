"""
Custom Query (커스텀 쿼리) 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
사용자 커스텀 쿼리 업로드, 조회, 삭제 기능 테스트
"""

import os
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="lukus_custom_query_test_")
os.environ["LUKUS_DATA_DIR"] = _tmp

from job_store import JobStore


@pytest.fixture
def store(tmp_path):
    return JobStore(db_path=tmp_path / "test_custom_query.db")


class TestCustomQueryCRUD:
    """커스텀 쿼리 CRUD 테스트"""

    def test_create_custom_query(self, store):
        """쿼리 생성 테스트"""
        query = store.create_custom_query(
            query_id="q1",
            name="바이올린",
            file_path="/tmp/violin.wav",
            description="바이올린 레퍼런스",
            color="#a78bfa",
            duration=10.5,
        )
        assert query["query_id"] == "q1"
        assert query["name"] == "바이올린"
        assert query["color"] == "#a78bfa"
        assert query["duration"] == 10.5

    def test_get_custom_query(self, store):
        """쿼리 조회 테스트"""
        store.create_custom_query(
            query_id="q1",
            name="피아노",
            file_path="/tmp/piano.wav",
        )
        fetched = store.get_custom_query("q1")
        assert fetched is not None
        assert fetched["name"] == "피아노"

    def test_get_nonexistent_query(self, store):
        """존재하지 않는 쿼리 조회"""
        assert store.get_custom_query("nonexistent") is None

    def test_list_custom_queries(self, store):
        """쿼리 목록 조회 테스트"""
        store.create_custom_query("q1", "바이올린", "/tmp/v.wav")
        store.create_custom_query("q2", "트럼펫", "/tmp/t.wav")
        store.create_custom_query("q3", "드럼", "/tmp/d.wav")

        queries = store.list_custom_queries()
        assert len(queries) == 3
        assert queries[0]["name"] == "드럼"

    def test_list_empty(self, store):
        """빈 목록 조회"""
        queries = store.list_custom_queries()
        assert queries == []


class TestCustomQueryUpdate:
    """커스텀 쿼리 업데이트 테스트"""

    def test_update_name(self, store):
        """이름 업데이트"""
        store.create_custom_query("q1", "Original", "/tmp/o.wav")
        result = store.update_custom_query("q1", name="Updated")
        assert result is True

        query = store.get_custom_query("q1")
        assert query["name"] == "Updated"

    def test_update_color(self, store):
        """색상 업데이트"""
        store.create_custom_query("q1", "Test", "/tmp/t.wav", color="#000000")
        store.update_custom_query("q1", color="#ff0000")

        query = store.get_custom_query("q1")
        assert query["color"] == "#ff0000"

    def test_update_description(self, store):
        """설명 업데이트"""
        store.create_custom_query("q1", "Test", "/tmp/t.wav")
        store.update_custom_query("q1", description="새로운 설명")

        query = store.get_custom_query("q1")
        assert query["description"] == "새로운 설명"

    def test_update_multiple_fields(self, store):
        """여러 필드 동시 업데이트"""
        store.create_custom_query("q1", "Test", "/tmp/t.wav")
        store.update_custom_query("q1", name="New Name", color="#123456", description="Desc")

        query = store.get_custom_query("q1")
        assert query["name"] == "New Name"
        assert query["color"] == "#123456"
        assert query["description"] == "Desc"

    def test_update_nonexistent(self, store):
        """존재하지 않는 쿼리 업데이트"""
        result = store.update_custom_query("nonexistent", name="Test")
        assert result is False


class TestCustomQueryDelete:
    """커스텀 쿼리 삭제 테스트"""

    def test_delete_query(self, store):
        """쿼리 삭제"""
        store.create_custom_query("q1", "ToDelete", "/tmp/d.wav")
        result = store.delete_custom_query("q1")
        assert result is True
        assert store.get_custom_query("q1") is None

    def test_delete_nonexistent(self, store):
        """존재하지 않는 쿼리 삭제"""
        result = store.delete_custom_query("nonexistent")
        assert result is False


class TestCustomQueryDefaults:
    """기본값 테스트"""

    def test_default_color(self, store):
        """기본 색상"""
        store.create_custom_query("q1", "Test", "/tmp/t.wav")
        query = store.get_custom_query("q1")
        assert query["color"] == "#94a3b8"

    def test_default_description(self, store):
        """기본 설명"""
        store.create_custom_query("q1", "Test", "/tmp/t.wav")
        query = store.get_custom_query("q1")
        assert query["description"] == ""

    def test_null_duration(self, store):
        """duration이 None인 경우"""
        store.create_custom_query("q1", "Test", "/tmp/t.wav", duration=None)
        query = store.get_custom_query("q1")
        assert query["duration"] is None


class TestCustomQueryTimestamps:
    """타임스탬프 테스트"""

    def test_created_at_set(self, store):
        """생성 시각 설정"""
        store.create_custom_query("q1", "Test", "/tmp/t.wav")
        query = store.get_custom_query("q1")
        assert query["created_at"] is not None
        assert "T" in query["created_at"]

    def test_updated_at_changes(self, store):
        """업데이트 시각 변경"""
        store.create_custom_query("q1", "Test", "/tmp/t.wav")
        q1 = store.get_custom_query("q1")
        original_updated = q1["updated_at"]

        import time
        time.sleep(0.1)

        store.update_custom_query("q1", name="Changed")
        q2 = store.get_custom_query("q1")
        assert q2["updated_at"] >= original_updated
