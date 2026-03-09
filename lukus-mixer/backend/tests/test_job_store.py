"""
JobStore (SQLite) 단위 테스트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import tempfile
from pathlib import Path

import pytest

# DB를 임시 디렉터리에 생성하여 테스트 격리
_tmp = tempfile.mkdtemp(prefix="lukus_test_")
os.environ["LUKUS_DATA_DIR"] = _tmp

from job_store import JobStore


@pytest.fixture
def store(tmp_path):
    return JobStore(db_path=tmp_path / "test_jobs.db")


# ── 기본 CRUD ──────────────────────────────

class TestJobCRUD:
    def test_create_and_get(self, store):
        job = store.create_job(
            job_id="j1", file_id="f1", model="htdemucs",
            stems=["vocals", "drums"], original_filename="test.mp3"
        )
        assert job["job_id"] == "j1"
        assert job["status"] == "pending"
        assert job["progress"] == 0

        fetched = store.get_job("j1")
        assert fetched is not None
        assert fetched["file_id"] == "f1"
        assert fetched["stems"] == ["vocals", "drums"]

    def test_get_nonexistent(self, store):
        assert store.get_job("nonexistent") is None

    def test_job_exists(self, store):
        assert not store.job_exists("j1")
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        assert store.job_exists("j1")

    def test_update_status(self, store):
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        store.update_job("j1", status="processing", progress=50, message="처리 중")
        job = store.get_job("j1")
        assert job["status"] == "processing"
        assert job["progress"] == 50
        assert job["message"] == "처리 중"

    def test_update_result(self, store):
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        result = {"vocals": {"name": "vocals", "path": "/tmp/v.mp3"}}
        store.update_job("j1", result=result)
        job = store.get_job("j1")
        assert job["result"]["vocals"]["path"] == "/tmp/v.mp3"

    def test_update_with_log(self, store):
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        store.update_job("j1", log="시작")
        store.update_job("j1", log="완료")
        job = store.get_job("j1")
        assert len(job["logs"]) == 2
        assert "시작" in job["logs"][0]
        assert "완료" in job["logs"][1]

    def test_delete(self, store):
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        store.delete_job("j1")
        assert store.get_job("j1") is None


# ── Mix 관리 ──────────────────────────────

class TestMixOperations:
    def test_add_and_get_mix(self, store):
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        store.add_mix("j1", "m1", {"path": "/tmp/mix.mp3", "prompt": "보컬 키워"})
        mixes = store.get_mixes("j1")
        assert "m1" in mixes
        assert mixes["m1"]["prompt"] == "보컬 키워"

    def test_multiple_mixes(self, store):
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        store.add_mix("j1", "m1", {"path": "/tmp/m1.mp3"})
        store.add_mix("j1", "m2", {"path": "/tmp/m2.mp3"})
        mixes = store.get_mixes("j1")
        assert len(mixes) == 2

    def test_get_mixes_empty(self, store):
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        assert store.get_mixes("j1") == {}


# ── Library ──────────────────────────────

class TestLibrary:
    def test_add_and_get_items(self, store):
        store.add_library_item({"id": "lib1", "name": "test", "created_at": "2026-03-09T10:00:00"})
        items = store.get_library_items()
        assert len(items) == 1
        assert items[0]["name"] == "test"

    def test_library_ordering(self, store):
        store.add_library_item({"id": "a", "name": "first", "created_at": "2026-01-01T00:00:00"})
        store.add_library_item({"id": "b", "name": "second", "created_at": "2026-06-01T00:00:00"})
        items = store.get_library_items()
        assert items[0]["name"] == "second"
        assert items[1]["name"] == "first"


# ── Stale Jobs ──────────────────────────────

class TestStaleJobs:
    def test_mark_stale_on_init(self, tmp_path):
        s1 = JobStore(db_path=tmp_path / "stale.db")
        s1.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        s1.update_job("j1", status="processing", progress=50)

        s2 = JobStore(db_path=tmp_path / "stale.db")
        job = s2.get_job("j1")
        assert job["status"] == "failed"
        assert "재시작" in job["message"]


# ── Old Jobs (TTL) ──────────────────────────

class TestOldJobs:
    def test_list_old_completed_jobs(self, store):
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        store.update_job("j1", status="completed")

        old_jobs = store.list_old_jobs("2099-01-01T00:00:00")
        assert len(old_jobs) == 1

    def test_future_cutoff_returns_nothing(self, store):
        store.create_job("j1", "f1", "htdemucs", ["vocals"], "a.mp3")
        store.update_job("j1", status="completed")

        old_jobs = store.list_old_jobs("2000-01-01T00:00:00")
        assert len(old_jobs) == 0
