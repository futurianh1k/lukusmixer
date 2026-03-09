# CHANGELOG — 2026-03-09 P1 보완 구현

> **작업 유형**: 코드 품질 + 아키텍처 보완 (P1)
> **이전 작업**: P0 보안/품질 수정 완료 후 진행

---

## 변경 요약

### 1. logging 모듈 도입 (P1-1)
- **파일**: `backend/main.py`, `backend/demucs_service.py`
- **내용**:
  - 모든 `print()` 호출을 `logging` 모듈로 교체
  - `lukus.api` / `lukus.demucs` / `lukus.store` 세 개의 네임드 로거 사용
  - 로그 레벨은 환경변수 `LOG_LEVEL`로 제어 (기본: INFO)
  - 로그 포맷: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- **이점**: 로그 레벨 필터링, 파일 로테이션, 외부 수집(ELK 등) 연동 가능

### 2. Job 상태 영속화 — SQLite (P1-2)
- **파일**: `backend/job_store.py` (신규), `backend/main.py`
- **내용**:
  - 새 모듈 `job_store.py` 생성 — SQLite 기반 `JobStore` 클래스
  - in-memory `jobs` dict와 `library_items` list를 완전 교체
  - 테이블: `jobs`, `library_items`
  - WAL 저널 모드 + busy_timeout 설정으로 동시성 안전
  - 서버 재시작 시 미완료(processing/pending) 작업을 자동으로 failed 전환
  - DB 파일 위치: `~/.lukus_mixer/jobs.db` (환경변수 `LUKUS_DATA_DIR`로 변경 가능)
- **이점**: 서버 재시작 시에도 작업 이력 보존, 향후 Redis/PostgreSQL 전환 용이

### 3. 임시 파일 TTL 자동 정리 (P1-3)
- **파일**: `backend/main.py`
- **내용**:
  - FastAPI lifespan 이벤트에 백그라운드 정리 태스크 등록
  - 환경변수로 제어:
    - `FILE_TTL_HOURS`: 파일 보존 시간 (기본 24시간)
    - `CLEANUP_INTERVAL_MINUTES`: 정리 주기 (기본 30분)
  - 완료/실패 작업 중 TTL 초과한 것의 출력 디렉터리 삭제 + DB 레코드 삭제
- **이점**: 디스크 공간 자동 관리, 수동 정리 불필요

### 4. GPU 동시 작업 제한 (P1-4)
- **파일**: `backend/main.py`
- **내용**:
  - `asyncio.Semaphore`를 이용하여 동시 STEM 분리 작업 수 제한
  - 환경변수 `MAX_CONCURRENT_SPLITS`로 제어 (기본 1)
  - 큐 대기 시 "대기 중" 상태를 사용자에게 표시
  - `process_split_job` → `_process_split_inner` 분리로 큐 로직 캡슐화
- **이점**: VRAM 부족으로 인한 OOM 방지, 안정적인 GPU 자원 관리

### 5. 모델 목록 서버 동적 로드 (P1-5)
- **파일**: `frontend/src/App.jsx`
- **내용**:
  - 기존 하드코딩 `MODELS` 배열 제거
  - `useEffect`에서 `/api/system` 호출 → 서버 `DEMUCS_MODELS`를 동적 로드
  - 서버 연결 실패 시 `FALLBACK_MODELS`(최소 1개) 사용
  - `description` 필드명 통일 (기존 `desc` → `description`)
- **이점**: 백엔드에서 모델 추가/변경 시 프론트엔드 재배포 불필요

### 6. FileUpload X 버튼 연결 (P1-6)
- **파일**: `frontend/src/components/FileUpload.jsx`, `frontend/src/App.jsx`
- **내용**:
  - `FileUpload` 컴포넌트에 `onRemove` prop 추가
  - X 버튼 클릭 시 `onRemove()` 호출 + 이벤트 전파 차단
  - `App.jsx`에 `handleRemoveFile` 핸들러 구현:
    - objectURL 해제
    - uploadedFile / results / jobId / jobStatus 상태 초기화
- **이점**: 새 파일 업로드 전 기존 파일 제거 가능, UX 개선

---

## 테스트

### 신규 테스트 파일
- `backend/tests/test_job_store.py` — 15개 테스트
  - JobStore CRUD, Mix 관리, Library, Stale Jobs, Old Jobs (TTL)

### 전체 테스트 결과
```
79 passed in 3.45s (0 warnings)
```

---

## 환경변수 설정 가이드

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `LOG_LEVEL` | `INFO` | 로그 레벨 (DEBUG/INFO/WARNING/ERROR) |
| `LUKUS_DATA_DIR` | `~/.lukus_mixer` | SQLite DB 저장 경로 |
| `FILE_TTL_HOURS` | `24` | 임시 파일 보존 시간 |
| `CLEANUP_INTERVAL_MINUTES` | `30` | 파일 정리 주기 |
| `MAX_CONCURRENT_SPLITS` | `1` | GPU 동시 분리 작업 제한 |
| `ALLOWED_ORIGINS` | `localhost:3000,5173` | CORS 허용 도메인 |
| `MAX_UPLOAD_SIZE` | `209715200` (200MB) | 최대 업로드 파일 크기 |

---

## 참고 출처
- sqlite3 (Python 표준 라이브러리): https://docs.python.org/3/library/sqlite3.html
- logging (Python 표준 라이브러리): https://docs.python.org/3/library/logging.html
- asyncio.Semaphore: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
- FastAPI Lifespan: https://fastapi.tiangolo.com/advanced/events/
