# Custom Query 기능 구현 (2026-03-10)

## 개요
Banquet 모델을 확장하여 사용자가 직접 쿼리 오디오를 업로드하고, 원하는 악기/소리를 분리할 수 있는 **커스텀 쿼리** 기능을 구현했습니다.

## 브랜치
- `feature/custom-query`

---

## 변경 내역

### Backend

#### 1. job_store.py — 커스텀 쿼리 저장소 확장
**새 테이블**: `custom_queries`
```sql
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
```

**새 메서드**:
- `create_custom_query()` — 커스텀 쿼리 생성
- `get_custom_query()` — 단일 쿼리 조회
- `list_custom_queries()` — 모든 쿼리 목록 조회
- `update_custom_query()` — 쿼리 업데이트 (이름, 설명, 색상)
- `delete_custom_query()` — 쿼리 삭제

#### 2. main.py — 커스텀 쿼리 API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/custom-queries/upload` | 쿼리 오디오 업로드 |
| GET | `/api/custom-queries` | 쿼리 목록 조회 |
| GET | `/api/custom-queries/{query_id}` | 단일 쿼리 조회 |
| PATCH | `/api/custom-queries/{query_id}` | 쿼리 업데이트 |
| DELETE | `/api/custom-queries/{query_id}` | 쿼리 삭제 |
| GET | `/api/custom-queries/{query_id}/stream` | 쿼리 오디오 스트리밍 |
| POST | `/api/split-custom/{file_id}` | 커스텀 쿼리 기반 분리 |

**업로드 제한**:
- 최대 파일 크기: 20MB (`MAX_QUERY_SIZE`)
- 최대 길이: 30초 (`MAX_QUERY_DURATION`)
- 최소 길이: 1초
- 지원 형식: MP3, WAV, FLAC, OGG, M4A
- 자동 WAV 변환 (Banquet 호환성)

#### 3. 테스트 코드
- `tests/test_custom_query.py` — 17개 테스트 케이스
  - CRUD 테스트
  - 업데이트 테스트
  - 삭제 테스트
  - 기본값 테스트
  - 타임스탬프 테스트

---

### Frontend

#### 1. types/api.ts — 타입 정의 추가
```typescript
// 새 타입
interface CustomQuery { ... }
interface CustomQueryUploadResponse { ... }
interface CustomQueryListResponse { ... }
interface CustomSplitRequest { ... }
interface CustomSplitResponse { ... }
interface CustomStemResult extends StemResult { ... }
interface CustomQueryManagerProps { ... }

// 색상 프리셋
const QUERY_COLOR_PRESETS = [...] as const;
```

#### 2. CustomQueryManager.tsx — 새 컴포넌트
사용자 커스텀 쿼리를 관리하는 UI 컴포넌트:
- 쿼리 업로드 (드래그 앤 드롭 지원)
- 쿼리 목록 표시
- 쿼리 선택/해제
- 쿼리 미리듣기
- 쿼리 삭제
- 색상 커스터마이징
- 이름 편집

#### 3. App.jsx — 커스텀 쿼리 모드 통합
- 커스텀 쿼리 모드 토글 추가
- `useCustomQuery` 상태로 모드 전환
- `selectedQueryIds`로 선택된 쿼리 관리
- 분리 버튼이 모드에 따라 다른 API 호출

---

## 사용 방법

### 1. 쿼리 업로드
1. 설정 패널에서 "Custom Query Mode" 토글 활성화
2. 쿼리 이름 입력 (선택)
3. 색상 선택 (선택)
4. 쿼리 오디오 파일 업로드 (10-30초 권장)

### 2. 커스텀 분리
1. 분리할 쿼리 선택 (체크박스)
2. "커스텀 분리 (N개 쿼리)" 버튼 클릭
3. 결과 확인 및 다운로드

### 3. 쿼리 관리
- **미리듣기**: 재생 버튼 클릭
- **이름 변경**: 쿼리 이름 옆 편집 버튼
- **색상 변경**: 색상 원형 클릭 후 선택
- **삭제**: 휴지통 버튼 클릭

---

## 기술 참고
- **Banquet (query-bandit)**: https://github.com/kwatcharasupat/query-bandit
- Watcharasupat & Lerch, "A Stem-Agnostic Single-Decoder System for Music Source Separation Beyond Four Stems", ISMIR 2024

---

## 파일 목록

### 수정된 파일
- `backend/job_store.py`
- `backend/main.py`
- `frontend/src/types/api.ts`
- `frontend/src/App.jsx`

### 새 파일
- `backend/tests/test_custom_query.py`
- `frontend/src/components/CustomQueryManager.tsx`
- `History/CHANGELOG_2026-03-10_CustomQuery.md`
