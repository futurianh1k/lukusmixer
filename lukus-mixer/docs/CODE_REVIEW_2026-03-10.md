# LUKUS Music Mixer — 코드 리뷰 보고서

> **작성일**: 2026-03-10  
> **대상 버전**: Phase 3 완료 (14스템 분리 + Banquet 통합)  
> **리뷰 범위**: 백엔드(main.py, demucs_service.py, banquet_service.py, job_store.py), 프론트엔드(React 11개 파일), 테스트, 문서  
> **프로젝트 위치**: `/mnt/8tb01/cursorworks/LukusMixer/lukus-mixer/`

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | LUKUS Music Mixer (Stem Splitter) |
| **현재 단계** | Phase 3 완료 (14스템 분리) |
| **기술 스택** | FastAPI + React 18 + Vite + Tailwind CSS |
| **AI 엔진** | Demucs v4, BS-RoFormer, MelBand-RoFormer, DrumSep, Banquet |
| **데이터 저장** | SQLite (jobs.db) |
| **실시간 통신** | WebSocket + HTTP 폴링 폴백 |

3컬럼 레이아웃(사이드바 | 업로드+설정+결과 | 믹싱 패널)으로 구성된 풀스택 웹 앱.  
최대 14스템까지 분리하고, 한국어 프롬프트 기반 믹싱을 지원.

### 1.1 지원 모델

| 모델 | 엔진 | 스템 수 | 특징 |
|------|------|---------|------|
| htdemucs | Demucs | 4 | 기본, 빠른 속도 |
| htdemucs_ft | Demucs | 4 | 고품질 (4배 느림) |
| htdemucs_6s | Demucs | 6 | 기타, 피아노 추가 |
| bs_roformer_4s | Chained | 4 | BS-RoFormer + Demucs ft |
| bs_roformer_6s | Chained | 6 | BS-RoFormer + Demucs 6s |
| bs_roformer_10s | Chained 4-Pass | 10 | 보컬/드럼 세분화 |
| **banquet_14s** | **Chained 5-Pass** | **14** | **Banquet 쿼리 기반 롱테일 악기** |

### 1.2 주요 API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/system` | GET | 시스템/모델 정보 |
| `/api/upload` | POST | 오디오 업로드 (Magic number 검증) |
| `/api/split/{file_id}` | POST | STEM 분리 시작 |
| `/api/job/{job_id}` | GET | 작업 상태 조회 |
| `/ws/job/{job_id}` | WebSocket | 실시간 작업 상태 스트리밍 |
| `/api/stream/{job_id}/{stem}` | GET | 스템 스트리밍 |
| `/api/download/{job_id}/{stem}` | GET | 스템 다운로드 |
| `/api/download-all/{job_id}` | GET | ZIP 다운로드 |
| `/api/mix/{job_id}` | POST | 프롬프트 믹싱 실행 |
| `/api/spectrogram/{job_id}/{stem}` | GET | 스펙트로그램 이미지 |
| `/api/library` | GET | 라이브러리 목록 |
| `/api/prompt-history/*` | GET/POST/DELETE | 프롬프트 히스토리 관리 |

---

## 2. 아키텍처 강점

### 2.1 5-Pass AI 파이프라인

```
원본 오디오
  ├── Pass 1: BS-RoFormer → Vocals / Instrumental (SDR 12.97)
  ├── Pass 2: Demucs 6s → drums, bass, guitar, piano, other
  ├── Pass 3: MelBand-RoFormer Karaoke → Lead Vocals / Backing Vocals
  ├── Pass 4: MDX23C DrumSep → kick, snare, toms, cymbals
  └── Pass 5: Banquet Query → strings, brass, woodwinds, synthesizer
```

- 각 단계의 `progress_cb`를 통해 WebSocket으로 진행 상황 실시간 전달
- Semaphore로 GPU 동시 작업 제한 (VRAM 부족 방지)

### 2.2 SQLite 기반 Job 영속화

```python
# job_store.py — Thread-safe SQLite 저장소
class JobStore:
    def __init__(self, db_path=None):
        self._db_path = str(db_path or DB_PATH)
        self._local = threading.local()  # 스레드별 연결
        self._init_schema()
        self._mark_stale_jobs()  # 서버 재시작 시 미완료 작업 처리
```

- 서버 재시작 시에도 작업 정보 보존
- WAL 모드로 동시성 개선
- `list_old_jobs()`로 TTL 기반 자동 정리 지원

### 2.3 WebSocket + HTTP 폴링 폴백

```javascript
// useJobWebSocket.js
const connect = () => {
  const ws = new WebSocket(wsUrl);
  ws.onclose = () => {
    if (retriesRef.current >= RECONNECT_MAX) {
      startPolling();  // WS 실패 시 HTTP 폴링으로 전환
    }
  };
};
```

- WebSocket을 지원하지 않는 환경(일부 프록시/CDN)에서도 안전하게 동작

### 2.4 한국어 프롬프트 파서

```python
INSTRUMENT_MAP = {
    "보컬": "vocals", "리드보컬": "lead_vocals", "백킹보컬": "backing_vocals",
    "드럼": "drums", "킥": "kick", "스네어": "snare", ...
    "현악기": "strings", "바이올린": "strings",  # Banquet 14스템 추가
    "금관악기": "brass", "트럼펫": "brass",
    "목관악기": "woodwinds", "플루트": "woodwinds",
    "신디사이저": "synthesizer", "신스": "synthesizer",
}
```

- 긴 키워드 우선 매칭으로 "조금 키워"(3dB)와 "키워"(6dB) 구분
- 14개 악기 한글 키워드 지원

### 2.5 스펙트로그램 인터랙션

```jsx
// ResultPanel.jsx — Spectrogram 컴포넌트
- 클릭으로 구간 시작점 선택 → 두 번째 클릭으로 끝점 선택
- 플로팅 볼륨 메뉴 → 프롬프트 자동 삽입
- 더블클릭으로 확대 모달
- 재생 위치 플레이헤드 동기화
```

### 2.6 TypeScript 타입 정의

```typescript
// frontend/src/types/api.ts
export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  result: Record<string, StemResult> | null;
  logs: string[] | null;
}
```

- 백엔드 Pydantic 모델과 1:1 대응
- JSX → TSX 점진적 마이그레이션 기반 구축

---

## 3. 보안 이슈 현황

### 3.1 ✅ 해결된 보안 이슈

| 이슈 | 상태 | 구현 위치 |
|------|------|----------|
| CORS 와일드카드 | ✅ 해결 | `main.py` — 환경변수로 허용 도메인 관리 |
| 파일 업로드 보안 | ✅ 해결 | Magic number 검증, MIME 타입 검증, 크기 제한 |
| 경로 순회 방지 | ✅ 해결 | `_sanitize_filename()`, `_safe_resolve()` |
| 내부 경로 노출 | ✅ 해결 | API 응답에서 서버 내부 경로 제거 |

### 3.2 ⏳ 미해결 보안 이슈

| 이슈 | 우선순위 | 권장 조치 |
|------|---------|----------|
| **인증/인가 없음** | P1 | JWT 토큰 기반 인증 도입 (ROADMAP 5B-1) |
| **Rate Limiting 없음** | P2 | API 요청 제한 (slowapi/redis) |
| **입력 검증 부족** | P2 | Pydantic strict mode, 정규식 검증 강화 |

---

## 4. 코드 품질 분석

### 4.1 ✅ 잘 구현된 부분

| 항목 | 평가 | 비고 |
|------|------|------|
| 로깅 시스템 | ✅ | `logging` 모듈 활용, 레벨별 로깅 |
| 예외 처리 | ✅ | 구체적 예외 타입 명시 |
| 비동기 처리 | ✅ | `asyncio.to_thread()`로 블로킹 작업 분리 |
| 코드 문서화 | ✅ | 참고 출처 명시, docstring 작성 |
| 테스트 커버리지 | ✅ | 105개 테스트 케이스 |

### 4.2 ⚠️ 개선 필요 항목

| 항목 | 현재 상태 | 권장 개선 |
|------|----------|----------|
| 임포트 위치 | 일부 파일 중간에 위치 | PEP 8 기준 모듈 상단 배치 |
| 타입 힌트 | 백엔드만 적용 | 프론트엔드 TSX 마이그레이션 |
| 환경 변수 문서화 | 코드 내 분산 | `.env.example` 파일 생성 |
| 에러 메시지 국제화 | 한국어 하드코딩 | i18n 라이브러리 도입 |

---

## 5. 프론트엔드 분석

### 5.1 컴포넌트 구조

```
src/
├── App.jsx              # 메인 레이아웃 (3컬럼 / 모바일 탭)
├── components/
│   ├── AudioPlayer.jsx  # 오디오 재생 컴포넌트
│   ├── FileUpload.jsx   # 파일 업로드 (드래그앤드롭)
│   ├── MixingPanel.jsx  # 프롬프트 믹싱 패널
│   ├── ResultPanel.jsx  # 분리 결과 + 스펙트로그램
│   ├── StemSelector.jsx # 스템 선택 UI
│   ├── Sidebar.jsx      # 사이드바 네비게이션
│   └── ErrorBoundary.jsx# 에러 경계
├── hooks/
│   └── useJobWebSocket.js # WebSocket 훅
└── types/
    └── api.ts           # TypeScript 타입 정의
```

### 5.2 ✅ 잘 구현된 UI/UX

| 기능 | 평가 |
|------|------|
| 반응형 레이아웃 | ✅ 데스크톱 3컬럼 / 모바일 탭 전환 |
| Toast 알림 | ✅ react-hot-toast 적용 |
| Error Boundary | ✅ 렌더링 에러 시 UI 복구 |
| 로딩 상태 | ✅ 프로그레스 바, 스피너 |
| 접이식 그룹 | ✅ 보컬/드럼/Banquet 서브그룹 |

### 5.3 ⚠️ 개선 필요 UI

| 항목 | 현재 상태 | 권장 개선 |
|------|----------|----------|
| `confirm()` 사용 | 네이티브 다이얼로그 | 커스텀 모달 컴포넌트 |
| 사이드바 메뉴 | 일부 비활성 메뉴 클릭 가능 | "Coming soon" 표시 또는 disabled |
| 키보드 접근성 | 일부 버튼 포커스 없음 | `tabIndex`, `aria-*` 속성 추가 |

---

## 6. 백엔드 분석

### 6.1 서비스 구조

```
backend/
├── main.py              # FastAPI 앱 + API 엔드포인트
├── demucs_service.py    # STEM 분리 로직 (5-Pass 파이프라인)
├── banquet_service.py   # Banquet 쿼리 기반 분리
├── job_store.py         # SQLite Job 저장소
└── tests/
    ├── test_security.py      # 28개 보안 테스트
    ├── test_prompt_parser.py # 28개 파서 테스트
    ├── test_mixing.py        # 8개 믹싱 테스트
    ├── test_job_store.py     # 15개 저장소 테스트
    └── test_banquet.py       # 26개 Banquet 테스트
```

### 6.2 DemucsService 엔진 분기

```python
def separate(self, audio_path, model, ...):
    engine = DEMUCS_MODELS.get(model, {}).get("engine", "demucs")
    
    if engine == "chained_banquet":
        return self._separate_chained_banquet(...)   # 5-Pass (14스템)
    elif engine == "chained_10s":
        return self._separate_chained_10s(...)       # 4-Pass (10스템)
    elif engine == "chained":
        return self._separate_chained(...)           # 2-Pass (4/6스템)
    else:
        return self._separate_demucs(...)            # 단일 Demucs
```

### 6.3 BanquetService 쿼리 기반 분리

```python
class BanquetService:
    def separate_one(self, input_path, query_path, output_path, stem_name):
        # 쿼리 오디오를 레퍼런스로 사용하여 특정 악기 분리
        mixture, fsm = torchaudio.load(input_path)
        query, fsq = torchaudio.load(query_path)
        
        batch = {
            "mixture": {"audio": mixture_t},
            "query": {"audio": query},
            "metadata": {"stem": [stem_name]},
        }
        out = self._system.chunked_inference(batch)
```

- 합성 쿼리 오디오 4종: strings, brass, woodwinds, synthesizer
- 실제 녹음 쿼리로 교체 시 품질 향상 가능

---

## 7. 테스트 현황

### 7.1 테스트 스위트

| 테스트 파일 | 테스트 수 | 대상 |
|------------|-----------|------|
| `test_prompt_parser.py` | 28개 | 악기 매핑, 구간 인식, 볼륨 액션, 14스템 |
| `test_security.py` | 28개 | 파일명 검증, 경로 순회, Magic number |
| `test_mixing.py` | 8개 | 스템 믹싱, 볼륨 조절, 구간 처리 |
| `test_job_store.py` | 15개 | CRUD, 동시성, stale job 처리 |
| `test_banquet.py` | 26개 | Banquet 스템 정의, 파서 키워드 |
| **합계** | **105개** | **전부 통과** ✅ |

### 7.2 실행 방법

```bash
cd lukus-mixer/backend
python -m pytest tests/ -v
```

### 7.3 누락된 테스트

| 영역 | 권장 테스트 추가 |
|------|-----------------|
| API 통합 테스트 | `/api/upload`, `/api/split` E2E 테스트 |
| 프론트엔드 테스트 | Jest + React Testing Library |
| 부하 테스트 | Locust로 동시 요청 처리 검증 |

---

## 8. 성능 분석

### 8.1 스펙트로그램 생성 최적화

```python
def generate_spectrogram_image(audio_path, output_path, label):
    # 최적화된 파라미터
    y, sr = librosa.load(audio_path, sr=8000, mono=True)  # 22050 → 8000
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmax=4000)  # 128 → 64
```

- 샘플레이트 다운샘플링으로 로드 시간 ~3배 단축
- n_mels 감소로 연산량 절반

### 8.2 오디오 길이 계산

```python
def get_audio_duration(self, audio_path):
    # librosa.get_duration() 우선 — 메타데이터만 읽기
    return librosa.get_duration(path=audio_path)
```

- 전체 오디오 메모리 로드 없이 메타데이터만 읽음

### 8.3 개선 권장 사항

| 병목점 | 현재 | 권장 |
|--------|------|------|
| 5-Pass 파이프라인 | 순차 실행 | Pass 3/4 병렬화 가능성 검토 |
| 스펙트로그램 캐싱 | 파일 기반 | Redis 캐시 도입 |
| Banquet 추론 | 순차 4회 | 배치 추론 최적화 |

---

## 9. 우선순위별 개선 권장사항

### 9.1 완료된 항목 (P0~P1)

| 우선순위 | 항목 | 상태 |
|----------|------|------|
| P0 | CORS 보안 | ✅ |
| P0 | 파일 업로드 보안 | ✅ |
| P0 | 경로 순회 방지 | ✅ |
| P0 | 예외 처리 개선 | ✅ |
| P0 | 테스트 코드 작성 | ✅ |
| P1 | logging 모듈 도입 | ✅ |
| P1 | Job 상태 영속화 | ✅ |
| P1 | 임시 파일 TTL 정리 | ✅ |
| P1 | GPU 동시 작업 제한 | ✅ |
| P1 | WebSocket 실시간 로그 | ✅ |
| P1 | 반응형 디자인 | ✅ |
| P2 | Toast 알림 | ✅ |
| P2 | Error Boundary | ✅ |
| P2 | TypeScript 기반 구축 | ✅ |

### 9.2 미완료 항목

| 우선순위 | 항목 | 권장 조치 |
|----------|------|----------|
| **P1** | **인증/인가** | JWT + 역할 기반 접근 제어 |
| P2 | Rate Limiting | slowapi 또는 Redis 기반 |
| P2 | Docker 컨테이너화 | Dockerfile + docker-compose |
| P2 | CI/CD 파이프라인 | GitHub Actions |
| P3 | 프론트엔드 TSX 전환 | 점진적 마이그레이션 |
| P3 | i18n 국제화 | react-i18next |

---

## 10. Banquet 14스템 상세

### 10.1 쿼리 기반 분리 원리

Banquet은 **"쿼리 오디오"**를 레퍼런스로 사용하여 해당 악기를 분리합니다.

```
입력: Other 스템 (guitar, piano 제외한 나머지)
       + 쿼리 오디오 (예: 바이올린 10초)
출력: 해당 악기 스템 (strings)
```

### 10.2 합성 쿼리 오디오

| 악기 | 쿼리 파일 | 생성 방법 |
|------|----------|----------|
| strings | `strings_query.wav` | 바이올린 + 첼로 합성 |
| brass | `brass_query.wav` | 트럼펫 + 트롬본 합성 |
| woodwinds | `woodwinds_query.wav` | 플루트 + 클라리넷 합성 |
| synthesizer | `synthesizer_query.wav` | 신스 패드 합성 |

### 10.3 향후 개선 방향

1. **실제 녹음 쿼리**: 합성 대신 실제 녹음으로 교체 시 품질 향상
2. **사용자 커스텀 쿼리**: 사용자가 직접 쿼리 오디오 업로드 기능
3. **쿼리 라이브러리**: 다양한 악기 쿼리 프리셋 제공

---

## 11. 총평

### 11.1 강점

- **5-Pass AI 파이프라인**: 단일 오디오에서 14개 악기 스템 분리
- **Banquet 쿼리 기반 접근**: 사전 정의되지 않은 악기도 분리 가능
- **실시간 WebSocket 통신**: 작업 진행 상황 실시간 전달
- **SQLite 영속화**: 서버 재시작 시에도 작업 정보 보존
- **105개 테스트**: 회귀 방지 체계 견고
- **보안 강화**: 경로 순회 방지, Magic number 검증

### 11.2 개선 필요

- **인증 시스템 부재**: 프로덕션 배포 전 필수 구현
- **프론트엔드 TypeScript**: 점진적 마이그레이션 필요
- **Docker 컨테이너화**: 배포 일관성을 위해 필요

### 11.3 권장 다음 단계

1. **Phase 4**: 인증/인가 시스템 구현
2. **Phase 5**: Docker + CI/CD 파이프라인
3. **Phase 6**: 사용자 커스텀 쿼리 업로드 기능

---

## 참고 출처

| 리소스 | URL | 라이선스 |
|--------|-----|---------|
| python-audio-separator | https://github.com/nomadkaraoke/python-audio-separator | MIT |
| BS-RoFormer | https://github.com/lucidrains/BS-RoFormer | MIT |
| Demucs v4 | https://github.com/facebookresearch/demucs | MIT |
| MelBand-RoFormer Karaoke | aufr33 & viperx | — |
| MDX23C DrumSep | aufr33 & jarredou | — |
| **Banquet (query-bandit)** | https://github.com/kwatcharasupat/query-bandit | MIT |
| **PaSST** | https://github.com/kkoutini/PaSST | Apache-2.0 |
| 모델 가중치 | https://zenodo.org/records/13694558 | — |
| 파일 시그니처 참고 | https://en.wikipedia.org/wiki/List_of_file_signatures | — |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-03-09 | v1.0 | 최초 코드 리뷰 (Phase 2, 10스템) |
| 2026-03-09 | v1.1 | Phase 3 Banquet 14스템 통합 |
| 2026-03-10 | v2.0 | 전체 재검토, 아키텍처 분석 추가 |
