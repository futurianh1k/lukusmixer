# LUKUS Music Mixer — 코드 리뷰 보고서

> **작성일**: 2026-03-09  
> **대상 버전**: Phase 2 완료 (10스템 분리)  
> **리뷰 범위**: 백엔드(`main.py`, `demucs_service.py`), 프론트엔드(React 6개 컴포넌트), 설정 파일, 문서  
> **프로젝트 위치**: `/mnt/8tb01/cursorworks/LukusMixer/lukus-mixer/`

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | LUKUS Music Mixer (Stem Splitter) |
| **현재 단계** | Phase 2 완료 (10스템 분리) |
| **기술 스택** | FastAPI + React 18 + Vite + Tailwind CSS |
| **AI 엔진** | Demucs v4, BS-RoFormer, MelBand-RoFormer, DrumSep |
| **GPU** | RTX 3070 (CUDA 12.8) |

3컬럼 레이아웃(사이드바 | 업로드+설정+결과 | 믹싱 패널)으로 구성된 풀스택 웹 앱.  
최대 10스템까지 분리하고, 한국어 프롬프트 기반 믹싱을 지원.

### 지원 모델

| 모델 | 엔진 | 스템 수 |
|------|------|---------|
| htdemucs | Demucs | 4 |
| htdemucs_ft | Demucs | 4 (고품질) |
| htdemucs_6s | Demucs | 6 |
| bs_roformer_4s | BS-RoFormer + Demucs 체이닝 | 4 |
| bs_roformer_6s | BS-RoFormer + Demucs 체이닝 | 6 |
| bs_roformer_10s | 4-Pass 체이닝 | 10 |

### 주요 API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/system` | GET | 시스템/모델 정보 |
| `/api/upload` | POST | 오디오 업로드 |
| `/api/split/{file_id}` | POST | STEM 분리 |
| `/api/job/{job_id}` | GET | 작업 상태 |
| `/api/stream/{job_id}/{stem}` | GET | 스템 스트리밍 |
| `/api/download/{job_id}/{stem}` | GET | 스템 다운로드 |
| `/api/download-all/{job_id}` | GET | ZIP 다운로드 |
| `/api/mix/{job_id}` | POST | 프롬프트 믹싱 |
| `/api/spectrogram/{job_id}/{stem}` | GET | 스펙트로그램 |
| `/api/library` | GET | 라이브러리 |
| `/api/prompt-history/save` | POST | 프롬프트 저장 |

---

## 2. 잘 구현된 부분 (강점)

### 2-1. AI 파이프라인 아키텍처

4-Pass 체이닝 파이프라인이 잘 설계되어 있음.

```
원본 오디오
  ├── Pass 1: BS-RoFormer → Vocals / Instrumental
  ├── Pass 2: Demucs 6s → drums, bass, guitar, piano, other
  ├── Pass 3: MelBand-RoFormer → Lead Vocals / Backing Vocals
  └── Pass 4: DrumSep → kick, snare, toms, cymbals
```

각 단계의 `progress_cb`를 통해 진행 상황을 UI에 실시간 전달.

### 2-2. 한국어 프롬프트 파서

`INSTRUMENT_MAP`, `SECTION_MAP`, `VOLUME_ACTION_MAP`을 활용한 룰베이스 파싱이 실용적.
- "전주 드럼 키워줘", "30초~40초 피아노 음소거" 등 자연스러운 한국어 명령 처리 가능
- 10스템 키워드(리드보컬, 킥, 스네어, 심벌즈 등) 지원

### 2-3. 스펙트로그램 인터랙션

`ResultPanel.jsx`의 스펙트로그램 컴포넌트가 상당히 정교함:
- 클릭으로 구간 선택 → 플로팅 볼륨 메뉴 → 프롬프트 자동 삽입
- 더블클릭 확대 모달, 플레이헤드 동기화
- 시작/끝 마커, 호버 타임 표시

### 2-4. 문서화

`docs/` 폴더에 SETUP_GUIDE, ROADMAP, SOFTWARE_REVIEW, DEVELOPMENT_PLAN 존재.  
`History/`에 CHANGELOG가 Phase별로 관리되어 변경 이력 추적 가능.

### 2-5. 10스템 그룹 트리 UI

`StemGroup`/`StemCard` 컴포넌트로 보컬 서브그룹(Lead/Backing)과 드럼 서브그룹(Kick/Snare/Toms/Cymbals)을 접이식 트리로 표현.

---

## 3. 보안 이슈 (Critical) — ✅ P0 수정 완료

### 3-1. CORS 와일드카드

**문제**: `allow_origins`에 `"*"`가 포함되어 모든 도메인에서 접근 가능. `allow_credentials=True`와 동시 사용 시 CORS 보안 무의미.

```python
# 수정 전
allow_origins=["http://localhost:3000", "http://localhost:5173", "*"]

# 수정 후 — 환경변수로 관리, 구체적 도메인만 허용
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()]
allow_methods=["GET", "POST", "DELETE"]
allow_headers=["Content-Type", "Authorization"]
```

**상태**: ✅ 수정 완료

### 3-2. 인증 없음

전체 API에 인증/인가가 없음. 누구나 파일 업로드, 다운로드, 삭제 가능.

**상태**: ⏳ Phase 5 (ROADMAP 5B-1) 예정

### 3-3. 내부 파일 경로 노출

**문제**: 업로드 응답에 서버 내부 경로(`/tmp/lukus_mixer_output/...`)가 노출.

```python
# 수정 전
return { ..., "path": str(file_path) }

# 수정 후 — path 필드 제거
return { "file_id": ..., "filename": ..., "duration": ..., "size": ... }
```

**상태**: ✅ 수정 완료

### 3-4. 파일 업로드 보안 미비

**문제**: 파일 크기 제한 없음, MIME 타입 검증 없음, Magic number 검증 없음.

**수정 내용**:
- 200MB 크기 제한 (1MB 청크 단위 읽기로 메모리 폭발 방지)
- MIME 타입 검증 (`audio/*` 계열만 허용)
- Magic number(파일 헤더) 검증 — MP3(ID3/MPEG sync), WAV(RIFF), FLAC(fLaC), OGG(OggS), M4A(ftyp)
- 확장자와 실제 파일 내용 불일치 시 거부

**상태**: ✅ 수정 완료

### 3-5. 경로 순회 취약점

**문제**: `delete_prompt_history`에서 `filename` 파라미터에 `../../../etc/passwd` 같은 경로 순회 공격 가능.

**수정 내용**:
- `_sanitize_filename()` — 순수 파일명만 추출, 경로 순회 문자 제거
- `_safe_resolve()` — 해석된 경로가 base 디렉토리 범위 내인지 검증
- `split_stems`, `spectrogram-original`, `delete_prompt_history` 엔드포인트에 적용

**상태**: ✅ 수정 완료

---

## 4. 코드 품질 이슈

### 4-1. 예외 처리 부실

**문제**: bare except (`except:`) 다수 사용 — `KeyboardInterrupt`, `SystemExit`도 잡힘.

```python
# 수정 전
except:
    pass

# 수정 후
except Exception as e:
    print(f"⚠️ librosa duration 실패: {e}")
```

**상태**: ✅ 수정 완료 (demucs_service.py 5곳, main.py 2곳)

### 4-2. 임포트 위치 불일치

`main.py`에서 `import re` (라인 458), `import time as _time` (라인 710), `import zipfile` (라인 353)이 파일 중간에 위치. PEP 8 기준으로 모듈 상단에 배치 필요.

**상태**: ⏳ P1 — 리팩토링 시 정리

### 4-3. 로깅 미구현

전체 백엔드가 `print()`로 로깅. `logging` 모듈 도입하여 레벨별 로깅(DEBUG, INFO, WARNING, ERROR) 필요.

**상태**: ⏳ P1 (ROADMAP 5A-5)

### 4-4. 타입 힌트 부재 (프론트엔드)

프론트엔드에서 TypeScript 대신 JSX 사용. 대규모 리팩토링 시 버그 발생 위험.

**상태**: ⏳ P2

### 4-5. 모델 정의 이중화

프론트엔드 `App.jsx`와 백엔드 `demucs_service.py`에 모델 목록이 각각 하드코딩.  
`/api/system` 엔드포인트에서 동적으로 가져오도록 수정하면 동기화 문제 방지 가능.

**상태**: ⏳ P1

### 4-6. 프롬프트 파서 버그 (수정 완료)

**문제**: 짧은 키워드("키워")가 긴 키워드("조금 키워")보다 먼저 매칭되어 "조금 키워"(3dB)가 "키워"(6dB)로 인식됨.

**수정**: 악기명 매칭과 볼륨 액션 매핑 모두 긴 키워드 우선 매칭으로 변경.

```python
# 수정 후 — 긴 키워드 우선
for action, db in sorted(VOLUME_ACTION_MAP.items(), key=lambda x: len(x[0]), reverse=True):
```

**상태**: ✅ 수정 완료

---

## 5. 아키텍처 이슈

### 5-1. 인메모리 상태 관리

```python
jobs: Dict[str, dict] = {}  # 서버 재시작 시 모든 데이터 소실
```

SQLite/Redis 도입 필요.

**상태**: ⏳ P1 (ROADMAP 5A-1)

### 5-2. 임시 파일 정리 없음

`/tmp/lukus_mixer_output/`에 출력 파일 누적. TTL 기반 자동 정리 없음 → 디스크 사용량 계속 증가.

**상태**: ⏳ P1 (ROADMAP 5A-2)

### 5-3. 동시성 처리 부재

`BackgroundTasks`로 비동기 처리하지만, 동시 GPU 작업 시 VRAM 부족 가능.  
작업 큐(Celery, RQ)와 동시 실행 제한 필요.

**상태**: ⏳ P2

### 5-4. 성능 이슈 — 오디오 길이 계산

```python
# 수정 전 — 전체 오디오를 메모리에 로드
y, sr = librosa.load(audio_path, sr=None)
return len(y) / sr

# 수정 후 — 메타데이터만 읽기
return librosa.get_duration(path=audio_path)
```

**상태**: ✅ 수정 완료

---

## 6. UX/프론트엔드 이슈

### 6-1. FileUpload X 버튼 미연결

```jsx
// onClick 핸들러 없음 — 클릭해도 아무 동작 안 함
<button className="text-dark-500 hover:text-red-400 transition-colors">
  <X className="w-5 h-5" />
</button>
```

**상태**: ⏳ P1

### 6-2. `alert()` 사용

파일 업로드 실패, 분리 실패, 라이브러리 추가 등에서 네이티브 `alert()` 사용.  
Toast 알림 라이브러리(react-hot-toast 등) 교체 권장.

**상태**: ⏳ P2

### 6-3. Error Boundary 없음

React Error Boundary 없어서 렌더링 에러 시 전체 앱 크래시.

**상태**: ⏳ P2

### 6-4. 사이드바 메뉴 비활성

"AI Text to Music", "AI Music Generator" 등 메뉴가 클릭 가능하지만 아무 동작 없음.  
disabled 상태 시각 표시 또는 "Coming soon" 표시 필요.

**상태**: ⏳ P2

### 6-5. 반응형 미지원

고정 width(`w-[400px]`, `w-[380px]`, `w-[220px]`) 사용.  
모바일/태블릿 레이아웃 깨짐.

**상태**: ⏳ P2

---

## 7. 테스트 코드 — ✅ 신규 작성 완료

리뷰 시점에 테스트 코드가 전혀 없었으며, P0 수정과 함께 테스트 스위트를 신규 작성.

| 테스트 파일 | 테스트 수 | 대상 |
|------------|-----------|------|
| `tests/test_prompt_parser.py` | 28개 | 악기 매핑, 구간 인식, 볼륨 액션, 10스템, 복수 라인 |
| `tests/test_security.py` | 28개 | 파일명 검증, 경로 순회 방지, Magic number, 확장자, 크기 제한 |
| `tests/test_mixing.py` | 8개 | 스템 믹싱, 볼륨 조절, 구간 처리, 음소거, 에러 처리 |
| **합계** | **64개** | **전부 통과** ✅ |

실행 방법:

```bash
cd backend
python -m pytest tests/ -v
```

---

## 8. 우선순위별 개선 권장사항

| 우선순위 | 항목 | 분류 | 상태 |
|----------|------|------|------|
| **P0** | CORS 와일드카드 제거 | 보안 | ✅ 완료 |
| **P0** | 파일 업로드 보안 강화 (크기 제한, MIME, Magic number) | 보안 | ✅ 완료 |
| **P0** | 경로 순회 방지 | 보안 | ✅ 완료 |
| **P0** | 내부 경로 노출 제거 | 보안 | ✅ 완료 |
| **P0** | bare except → 구체적 예외 처리 | 코드 품질 | ✅ 완료 |
| **P0** | 테스트 코드 작성 (64개) | 테스트 | ✅ 완료 |
| **P0** | 프롬프트 파서 키워드 매칭 버그 수정 | 버그 | ✅ 완료 |
| P1 | `logging` 모듈 도입 | 코드 품질 | ✅ 완료 |
| P1 | `get_audio_duration` 성능 개선 | 성능 | ✅ 완료 |
| P1 | Job 상태 영속화 (SQLite) | 아키텍처 | ✅ 완료 |
| P1 | 임시 파일 TTL 자동 정리 | 아키텍처 | ✅ 완료 |
| P1 | GPU 동시 작업 제한 (큐 시스템) | 아키텍처 | ✅ 완료 |
| P1 | 모델 목록 서버에서 동적 로드 | 코드 품질 | ✅ 완료 |
| P1 | FileUpload X 버튼 연결 | UX | ✅ 완료 |
| P2 | Toast 알림 도입 | UX | ✅ 완료 |
| P2 | Error Boundary 추가 | UX | ✅ 완료 |
| P2 | TypeScript 마이그레이션 | 코드 품질 | ✅ 기반 구축 |
| P2 | Docker 컨테이너화 | 인프라 | ✅ 완료 |
| P2 | WebSocket 실시간 로그 | UX | ✅ 완료 |
| P2 | 반응형 디자인 | UX | ✅ 완료 |

---

## 9. Phase 3: Banquet 14스템 (2026-03-09)

| 태스크 | 분류 | 상태 |
|--------|------|------|
| query-bandit 리포 클론 및 환경 구축 | 인프라 | ✅ 완료 |
| Banquet 추론 파이프라인 래핑 (banquet_service.py) | 백엔드 | ✅ 완료 |
| 레퍼런스 쿼리 오디오 수집 (합성 4종) | 데이터 | ✅ 완료 |
| Pass 5 구현: Other → Banquet → 4개 악기 | 백엔드 | ✅ 완료 |
| 14스템 모델 옵션 (banquet_14s) 등록 | 백엔드 | ✅ 완료 |
| 프론트엔드 UI (Banquet 그룹, STEM_CONFIG 확장) | 프론트 | ✅ 완료 |
| 프롬프트 파서 키워드 확장 (14개 한글 키워드) | 백엔드 | ✅ 완료 |
| Banquet 테스트 26개 추가 (총 105개) | 테스트 | ✅ 완료 |
| 사용자 커스텀 쿼리 업로드 기능 | UX | ⏳ 추후 |

---

## 10. 총평

Phase 3까지의 **AI 파이프라인 완성도가 높음**.  
5-Pass 체이닝(BS-RoFormer → Demucs → MelBand → DrumSep → Banquet)으로
단일 오디오에서 14개 악기 스템을 분리하는 체계를 구축.

Banquet 쿼리 기반 접근법으로 **사전 정의되지 않은 악기도 분리 가능**한
유연한 아키텍처를 달성. 합성 쿼리 오디오를 실제 녹음으로 교체하면 품질이 향상될 여지가 있음.

테스트 코드 105개로 회귀 방지 체계가 견고하며, ROADMAP/CHANGELOG 문서도 잘 관리되고 있음.

---

## 참고 출처

| 리소스 | URL |
|--------|-----|
| python-audio-separator | https://github.com/nomadkaraoke/python-audio-separator (MIT) |
| BS-RoFormer | https://github.com/lucidrains/BS-RoFormer (MIT) |
| Demucs v4 | https://github.com/facebookresearch/demucs (MIT) |
| MelBand-RoFormer Karaoke | aufr33 & viperx (python-audio-separator 내장) |
| MDX23C DrumSep | aufr33 & jarredou |
| **Banquet (query-bandit)** | **https://github.com/kwatcharasupat/query-bandit (MIT, ISMIR 2024)** |
| **PaSST** | **https://github.com/kkoutini/PaSST (Apache-2.0)** |
| **모델 가중치 (ev-pre-aug.ckpt)** | **https://zenodo.org/records/13694558** |
| 파일 시그니처 참고 | https://en.wikipedia.org/wiki/List_of_file_signatures |
