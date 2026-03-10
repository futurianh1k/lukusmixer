"""
Job Store — SQLite 기반 작업 상태 영속화
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
서버 재시작 시에도 진행 중이던 작업 정보를 보존합니다.

참고:
  - sqlite3: Python 표준 라이브러리 (추가 설치 불필요)
  - JSON 직렬화로 유연한 스키마 유지
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("lukus.store")

_DB_DIR = Path(os.environ.get("LUKUS_DATA_DIR", Path.home() / ".lukus_mixer"))
_DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = _DB_DIR / "jobs.db"


class JobStore:
    """Thread-safe SQLite 기반 Job 저장소"""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = str(db_path or DB_PATH)
        self._local = threading.local()
        self._init_schema()
        self._mark_stale_jobs()
        logger.info("JobStore 초기화 완료: %s", self._db_path)

    def _conn(self) -> sqlite3.Connection:
        if not getattr(self._local, "conn", None):
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self):
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id       TEXT PRIMARY KEY,
                file_id      TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                progress     REAL NOT NULL DEFAULT 0,
                message      TEXT NOT NULL DEFAULT '',
                result_json  TEXT,
                mixes_json   TEXT,
                logs_json    TEXT,
                stems_json   TEXT,
                model        TEXT,
                original_filename TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS library_items (
                id           TEXT PRIMARY KEY,
                data_json    TEXT NOT NULL,
                created_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS custom_queries (
                query_id     TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT,
                file_path    TEXT NOT NULL,
                color        TEXT DEFAULT '#94a3b8',
                duration     REAL,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
            CREATE INDEX IF NOT EXISTS idx_custom_queries_created ON custom_queries(created_at);
        """)
        conn.commit()

    def _mark_stale_jobs(self):
        """서버 재시작 시 processing 상태였던 작업을 failed로 변경"""
        conn = self._conn()
        now = datetime.now().isoformat()
        cur = conn.execute(
            "UPDATE jobs SET status='failed', message='서버 재시작으로 중단됨', updated_at=? "
            "WHERE status IN ('pending', 'processing')",
            (now,),
        )
        if cur.rowcount:
            logger.warning("서버 재시작: %d개 미완료 작업을 failed로 전환", cur.rowcount)
        conn.commit()

    # ── Job CRUD ──────────────────────────────

    def create_job(
        self,
        job_id: str,
        file_id: str,
        model: str,
        stems: List[str],
        original_filename: str,
    ) -> dict:
        now = datetime.now().isoformat()
        job = {
            "job_id": job_id,
            "file_id": file_id,
            "status": "pending",
            "progress": 0,
            "message": "대기 중...",
            "result": None,
            "mixes": {},
            "logs": [],
            "created_at": now,
            "updated_at": now,
            "stems": stems,
            "model": model,
            "original_filename": original_filename,
        }
        conn = self._conn()
        conn.execute(
            "INSERT INTO jobs (job_id, file_id, status, progress, message, "
            "result_json, mixes_json, logs_json, stems_json, model, "
            "original_filename, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                job_id, file_id, "pending", 0, "대기 중...",
                None, json.dumps({}), json.dumps([]), json.dumps(stems),
                model, original_filename, now, now,
            ),
        )
        conn.commit()
        return job

    def get_job(self, job_id: str) -> Optional[dict]:
        row = self._conn().execute(
            "SELECT * FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def job_exists(self, job_id: str) -> bool:
        row = self._conn().execute(
            "SELECT 1 FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        return row is not None

    def update_job(self, job_id: str, log: Optional[str] = None, **kwargs):
        conn = self._conn()
        now = datetime.now().isoformat()

        sets = ["updated_at=?"]
        params: list = [now]

        field_map = {
            "status": "status",
            "progress": "progress",
            "message": "message",
            "model": "model",
            "original_filename": "original_filename",
        }
        for py_key, col in field_map.items():
            if py_key in kwargs:
                sets.append(f"{col}=?")
                params.append(kwargs[py_key])

        if "result" in kwargs:
            sets.append("result_json=?")
            params.append(json.dumps(kwargs["result"]) if kwargs["result"] else None)

        if "mixes" in kwargs:
            sets.append("mixes_json=?")
            params.append(json.dumps(kwargs["mixes"]))

        if log is not None:
            row = conn.execute(
                "SELECT logs_json FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            logs = json.loads(row["logs_json"]) if row and row["logs_json"] else []
            logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {log}")
            sets.append("logs_json=?")
            params.append(json.dumps(logs))

        params.append(job_id)
        conn.execute(
            f"UPDATE jobs SET {', '.join(sets)} WHERE job_id=?", params
        )
        conn.commit()

    def delete_job(self, job_id: str):
        conn = self._conn()
        conn.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
        conn.commit()

    def add_mix(self, job_id: str, mix_id: str, mix_data: dict):
        conn = self._conn()
        row = conn.execute(
            "SELECT mixes_json FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        mixes = json.loads(row["mixes_json"]) if row and row["mixes_json"] else {}
        mixes[mix_id] = mix_data
        conn.execute(
            "UPDATE jobs SET mixes_json=?, updated_at=? WHERE job_id=?",
            (json.dumps(mixes), datetime.now().isoformat(), job_id),
        )
        conn.commit()

    def get_mixes(self, job_id: str) -> dict:
        row = self._conn().execute(
            "SELECT mixes_json FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if not row or not row["mixes_json"]:
            return {}
        return json.loads(row["mixes_json"])

    # ── Library CRUD ──────────────────────────

    def add_library_item(self, item: dict):
        conn = self._conn()
        conn.execute(
            "INSERT INTO library_items (id, data_json, created_at) VALUES (?,?,?)",
            (item["id"], json.dumps(item), item.get("created_at", datetime.now().isoformat())),
        )
        conn.commit()

    def get_library_items(self) -> List[dict]:
        rows = self._conn().execute(
            "SELECT data_json FROM library_items ORDER BY created_at DESC"
        ).fetchall()
        return [json.loads(r["data_json"]) for r in rows]

    # ── Custom Query CRUD ─────────────────────

    def create_custom_query(
        self,
        query_id: str,
        name: str,
        file_path: str,
        description: str = "",
        color: str = "#94a3b8",
        duration: Optional[float] = None,
    ) -> dict:
        """커스텀 쿼리 생성"""
        now = datetime.now().isoformat()
        query = {
            "query_id": query_id,
            "name": name,
            "description": description,
            "file_path": file_path,
            "color": color,
            "duration": duration,
            "created_at": now,
            "updated_at": now,
        }
        conn = self._conn()
        conn.execute(
            "INSERT INTO custom_queries "
            "(query_id, name, description, file_path, color, duration, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (query_id, name, description, file_path, color, duration, now, now),
        )
        conn.commit()
        logger.info("커스텀 쿼리 생성: %s (%s)", name, query_id)
        return query

    def get_custom_query(self, query_id: str) -> Optional[dict]:
        """단일 커스텀 쿼리 조회"""
        row = self._conn().execute(
            "SELECT * FROM custom_queries WHERE query_id=?", (query_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_custom_queries(self) -> List[dict]:
        """모든 커스텀 쿼리 목록 조회"""
        rows = self._conn().execute(
            "SELECT * FROM custom_queries ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_custom_query(self, query_id: str, **kwargs) -> bool:
        """커스텀 쿼리 업데이트"""
        conn = self._conn()
        now = datetime.now().isoformat()

        allowed = {"name", "description", "color", "duration"}
        sets = ["updated_at=?"]
        params: list = [now]

        for key, val in kwargs.items():
            if key in allowed:
                sets.append(f"{key}=?")
                params.append(val)

        params.append(query_id)
        cur = conn.execute(
            f"UPDATE custom_queries SET {', '.join(sets)} WHERE query_id=?", params
        )
        conn.commit()
        return cur.rowcount > 0

    def delete_custom_query(self, query_id: str) -> bool:
        """커스텀 쿼리 삭제"""
        conn = self._conn()
        cur = conn.execute("DELETE FROM custom_queries WHERE query_id=?", (query_id,))
        conn.commit()
        return cur.rowcount > 0

    # ── 정리 ──────────────────────────────────

    def list_old_jobs(self, before_iso: str) -> List[dict]:
        """지정 시각 이전의 완료/실패 작업 목록"""
        rows = self._conn().execute(
            "SELECT * FROM jobs WHERE updated_at < ? AND status IN ('completed', 'failed')",
            (before_iso,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ── 내부 ──────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["result"] = json.loads(d.pop("result_json")) if d.get("result_json") else None
        d["mixes"] = json.loads(d.pop("mixes_json")) if d.get("mixes_json") else {}
        d["logs"] = json.loads(d.pop("logs_json")) if d.get("logs_json") else []
        d["stems"] = json.loads(d.pop("stems_json")) if d.get("stems_json") else []
        return d
