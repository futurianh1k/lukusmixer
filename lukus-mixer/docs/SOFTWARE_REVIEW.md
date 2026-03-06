# LUKUS Music Mixer — 소프트웨어 리뷰
> **리뷰 일자**: 2026-03-06
> **버전**: v1.0 (Phase 1 완료)

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|---|---|
| **이름** | LUKUS Music Mixer |
| **목적** | AI 기반 음악 STEM(악기) 분리 + 프롬프트 기반 리믹싱 웹 애플리케이션 |
| **UI 참고** | Loudly Stem Splitter, LALAL.AI |
| **라이선스** | MIT (오픈소스 모델 활용) |

---

## 2. 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (React)                          │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────────┐   │
│  │ Sidebar   │   │ ResultPanel  │   │   MixingPanel        │   │
│  │ -Upload   │   │ -AudioPlayer │   │   -프롬프트 입력     │   │
│  │ -Model    │   │ -Spectrogram │   │   -볼륨/구간 설정    │   │
│  │ -Stems    │   │ -Playhead    │   │   -히스토리 관리     │   │
│  │ -Logs     │   │ -Downloads   │   │   -믹싱 결과 재생    │   │
│  └──────────┘   └──────────────┘   └──────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (Vite Proxy → :8000)
┌───────────────────────────▼─────────────────────────────────────┐
│                     FastAPI Backend (:8000)                      │
│  ┌────────────────────┐   ┌────────────────────────────────┐   │
│  │ API Endpoints       │   │ DemucsService                  │   │
│  │ - /api/upload       │   │ - Demucs v4 (4/6 스템)         │   │
│  │ - /api/split        │   │ - BS-RoFormer + Demucs (체이닝) │   │
│  │ - /api/mix          │   │ - audio-separator 통합          │   │
│  │ - /api/download     │   │ - WAV → MP3 변환                │   │
│  │ - /api/library      │   └────────────────────────────────┘   │
│  │ - /api/prompt-*     │   ┌────────────────────────────────┐   │
│  └────────────────────┘   │ 스펙트로그램 생성 (librosa)      │   │
│                            │ 프롬프트 파싱 (규칙 기반)        │   │
│                            │ 오디오 믹싱 (pydub)              │   │
│                            └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
                    ┌───────▼───────┐
                    │ GPU (CUDA)     │
                    │ - PyTorch      │
                    │ - ONNX Runtime │
                    └───────────────┘
```

### 기술 스택

| 계층 | 기술 | 버전 |
|---|---|---|
| **Frontend** | React + Vite + Tailwind CSS | 18.2 / 5.0 / 3.4 |
| **UI 라이브러리** | lucide-react, react-dropzone, axios | - |
| **Backend** | FastAPI + Uvicorn | 0.100+ / 0.23+ |
| **AI 엔진 (기본)** | Demucs v4 (htdemucs, htdemucs_ft, htdemucs_6s) | 4.0+ |
| **AI 엔진 (고급)** | audio-separator (BS-RoFormer) | 0.41.1 |
| **오디오 처리** | librosa, pydub, matplotlib | - |
| **GPU** | PyTorch + CUDA, ONNX Runtime GPU | 2.0+ |

---

## 3. 기능 현황

### 3.1 STEM 분리

| 모델 | 엔진 | 스템 수 | 속도 (158초 기준) | 보컬 품질 |
|---|---|---|---|---|
| htdemucs | Demucs | 4 | ~15초 | 보통 (SDR ~10) |
| htdemucs_ft | Demucs | 4 | ~60초 | 좋음 |
| htdemucs_6s | Demucs | 6 | ~20초 | 보통 |
| **bs_roformer_4s** | 체이닝 (PRO) | 4 | ~35초 | **최상 (SDR 12.97)** |
| **bs_roformer_6s** | 체이닝 (PRO) | 6 | ~42초 | **최상 (SDR 12.97)** |

### 3.2 오디오 플레이어
- 재생/일시정지, seekable 타임 슬라이더
- 세로 볼륨 슬라이더 (호버 시 표시), 음소거 토글
- HTTP Range Request 지원 (FileResponse)

### 3.3 스펙트로그램
- librosa + matplotlib로 사전 생성 (Mel spectrogram)
- 시간축 타임스탬프 (자동 간격: 2s/5s/10s/15s)
- 크기 토글: S(50px) / M(80px) / L(120px)
- **인터랙티브 플레이헤드**: 재생 위치 흰색 선, 호버 위치 주황색 선
- **스펙트로그램 클릭 seek**: 클릭 위치로 오디오 점프

### 3.4 프롬프트 기반 믹싱
- 한국어 자연어 프롬프트 파싱 ("드럼 키워줘", "30초~40초 피아노 작게")
- 구간/볼륨 GUI 설정 → 프롬프트 자동 생성
- pydub 기반 볼륨 조절/구간 적용
- 믹싱 결과 재생 + 다운로드

### 3.5 다운로드
- 스템별 개별 다운로드 (`파일명_stem.mp3`)
- 전체 ZIP 다운로드 (`파일명_stems.zip`)
- 믹싱 결과 다운로드 (`파일명_mixed.mp3`)

### 3.6 Library
- 스템 + 믹스 결과를 라이브러리에 저장
- 파일 복사 방식 (원본 보존)

### 3.7 프롬프트 히스토리
- 프롬프트 저장/조회/삭제 (`파일명_YYYYMMDD_HHMMSS.txt`)
- 히스토리 패널에서 클릭 로드
- 프롬프트 전체 삭제 버튼

---

## 4. API 엔드포인트 목록

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/system` | 시스템 정보 (모델 목록, CUDA, audio-separator 상태) |
| POST | `/api/upload` | 오디오 파일 업로드 |
| POST | `/api/split/{file_id}` | STEM 분리 시작 |
| GET | `/api/job/{job_id}` | 작업 상태 조회 (로그 포함) |
| GET | `/api/stream/{job_id}/{stem}` | 스템 스트리밍 (FileResponse, seek 지원) |
| GET | `/api/download/{job_id}/{stem}` | 스템 다운로드 |
| GET | `/api/download-all/{job_id}` | 전체 스템 ZIP 다운로드 |
| GET | `/api/spectrogram/{job_id}/{stem}` | 스펙트로그램 이미지 |
| GET | `/api/spectrogram-original/{file_id}` | 원본 스펙트로그램 |
| POST | `/api/mix/{job_id}` | 프롬프트 믹싱 실행 |
| POST | `/api/parse-prompt/{job_id}` | 프롬프트 파싱 미리보기 |
| GET | `/api/stream-mix/{job_id}/{mix_id}` | 믹싱 결과 스트리밍 |
| GET | `/api/download-mix/{job_id}/{mix_id}` | 믹싱 결과 다운로드 |
| GET | `/api/library` | 라이브러리 목록 |
| POST | `/api/library/add` | 라이브러리에 추가 |
| POST | `/api/prompt-history/save` | 프롬프트 히스토리 저장 |
| GET | `/api/prompt-history` | 프롬프트 히스토리 목록 |
| DELETE | `/api/prompt-history/{filename}` | 프롬프트 히스토리 삭제 |
| DELETE | `/api/job/{job_id}` | 작업 삭제 |

---

## 5. 코드 품질 평가

### 5.1 장점
- **모듈화**: 컴포넌트 분리 잘 되어 있음 (AudioPlayer, ResultPanel, MixingPanel 등)
- **엔진 추상화**: `DemucsService`가 Demucs와 체이닝을 `engine` 필드로 투명하게 분기
- **비동기 처리**: `asyncio.to_thread`로 블로킹 AI 작업을 비동기화
- **인터랙티브 UI**: 스펙트로그램 플레이헤드, 호버 타임스탬프, 클릭 seek 등 UX 우수
- **확장 가능한 모델 구조**: `DEMUCS_MODELS` dict에 모델 추가만 하면 자동 노출

### 5.2 개선 필요 사항

| 영역 | 현재 상태 | 권장 개선 |
|---|---|---|
| **상태 관리** | 인메모리 dict (`jobs`) | SQLite 또는 Redis로 영속화 (서버 재시작 시 유실) |
| **파일 관리** | /tmp 기반, 수동 정리 | TTL 기반 자동 정리, 용량 제한 |
| **에러 핸들링** | 기본적인 try/catch | 구조화된 에러 응답, 재시도 로직 |
| **인증/권한** | 없음 | JWT 또는 세션 기반 인증 (ISMS-P 준수) |
| **테스트 코드** | 없음 | pytest 유닛 테스트, API 통합 테스트 |
| **모델 관리** | 요청 시 로드 | 앱 시작 시 프리로드, 모델 캐싱 |
| **프론트 상태** | useState 다수 | useReducer 또는 Zustand 도입 고려 |
| **로깅** | print 문 | Python logging 모듈로 구조화 |

### 5.3 보안 점검 (ISMS-P 기준)

| 항목 | 상태 | 비고 |
|---|---|---|
| 입력 검증 | ⚠️ 부분적 | 파일 확장자 검증 있음, 크기 제한 없음 |
| 파일 업로드 보안 | ⚠️ 부분적 | MIME 검증 없음, Magic number 검증 없음 |
| 시크릿 관리 | ✅ 양호 | 하드코딩된 시크릿 없음 |
| 인증/권한 | ❌ 미구현 | 공개 API 상태 |
| 로그 보안 | ⚠️ 주의 | 파일 경로가 로그에 노출 |
| CORS | ⚠️ 주의 | `allow_origins=["*"]` — 프로덕션 시 제한 필요 |

---

## 6. 의존성 현황

### Backend (Python)

| 패키지 | 용도 | 라이선스 |
|---|---|---|
| fastapi | 웹 프레임워크 | MIT |
| uvicorn | ASGI 서버 | BSD |
| demucs | STEM 분리 | MIT |
| audio-separator | UVR5 엔진 (BS-RoFormer 등) | MIT |
| torch | 딥러닝 프레임워크 | BSD |
| onnxruntime-gpu | ONNX 추론 | MIT |
| librosa | 오디오 분석 | ISC |
| pydub | 오디오 편집 | MIT |
| matplotlib | 스펙트로그램 렌더링 | PSF |
| pydantic | 데이터 검증 | MIT |

### Frontend (Node.js)

| 패키지 | 용도 | 라이선스 |
|---|---|---|
| react / react-dom | UI 프레임워크 | MIT |
| vite | 빌드 도구 | MIT |
| tailwindcss | CSS 프레임워크 | MIT |
| react-dropzone | 파일 업로드 | MIT |
| lucide-react | 아이콘 | ISC |
| axios | HTTP 클라이언트 | MIT |

---

## 7. 성능 벤치마크

**테스트 환경**: Ubuntu Linux, CUDA GPU

| 작업 | 158초 오디오 기준 |
|---|---|
| Demucs htdemucs (4스템) | ~15초 |
| Demucs htdemucs_6s (6스템) | ~20초 |
| BS-RoFormer + Demucs 6s 체이닝 | ~42초 |
| 스펙트로그램 생성 (1개) | ~1~2초 |
| 프롬프트 믹싱 | ~2~5초 |

---

## 8. 결론

LUKUS Music Mixer는 **MVP 수준으로 핵심 기능이 잘 구현**되어 있습니다. BS-RoFormer 체이닝 파이프라인 도입으로 보컬 분리 품질이 크게 향상되었으며, 스펙트로그램 인터랙션과 프롬프트 믹싱은 차별화 포인트입니다.

**프로덕션 전환 시 필수 개선**: 상태 영속화, 인증/권한, 파일 관리 자동화, 테스트 코드 작성.
**품질 향상 다음 단계**: Phase 2 (보컬/드럼 세분화 → 10스템), Phase 3 (Banquet → 12스템).
