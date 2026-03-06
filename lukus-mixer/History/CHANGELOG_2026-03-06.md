# LUKUS Music Mixer — 수정 내역
## 2026-03-06 (초기 개발 ~ Phase 1 완료)

---

### 1. 프로젝트 초기 구축

**요청**: Loudly Stem Splitter 스타일의 음악 STEM 분리 풀스택 웹앱 구축
**구현**:
- FastAPI 백엔드 + React 프론트엔드 풀스택 구조 생성
- Demucs v4 기반 STEM 분리 엔진 통합
- 3컬럼 레이아웃 (사이드바 20% / 결과 40% / 믹싱 40%)
- 타이틀: "LUKUS Music Mixing", 배경색: 주황색 테마

**수정 파일**:
- `backend/main.py` — FastAPI 서버, API 엔드포인트
- `backend/demucs_service.py` — Demucs 서비스 클래스
- `frontend/src/App.jsx` — 메인 앱 컴포넌트
- `frontend/src/components/*.jsx` — UI 컴포넌트들
- `frontend/src/index.css` — 글로벌 스타일

---

### 2. 스템 필터링 & 모델 선택

**요청**: Select Stems에서 선택한 스템만 결과 패널에 표시
**구현**: `ResultPanel`에 `selectedStems` prop 전달, 선택된 스템만 필터링

---

### 3. 오디오 플레이어 고도화

**요청**: 볼륨 on/off + 세로 슬라이더, 시간축 이동 가능한 타임 슬라이더
**구현**:
- `AudioPlayer.jsx` — 세로 볼륨 슬라이더 (호버 시 표시), seekable `<input type="range">` 타임 슬라이더
- 볼륨: 0~100% 표시, 음소거 토글
- HTTP Range Request 지원을 위해 `StreamingResponse` → `FileResponse` 변경

**수정 파일**: `AudioPlayer.jsx`, `backend/main.py`

---

### 4. 스펙트로그램 표시

**요청**: 분리된 스템마다 스펙트로그램 표시
**구현**:
- `generate_spectrogram_image()` — librosa + matplotlib로 PNG 생성
- 최적화: sr=8000, n_mels=64, fmax=4000, dpi=72
- 분리 과정에서 스펙트로그램 사전 생성 (on-demand 아닌 pre-generation)
- 크기 토글: S/M/L (50px/80px/120px)
- `object-fit: fill` 적용으로 스케일링 보정

**수정 파일**: `ResultPanel.jsx`, `backend/main.py`

---

### 5. 스펙트로그램 타임라인 추가

**요청**: 스펙트로그램에 시간축(타임스탬프) 표시, 글꼴 크기/밝기 개선
**구현**:
- X축 틱 표시: 오디오 길이에 따라 자동 간격 (2s/5s/10s/15s)
- 글꼴: 6px → 9px, 색상: `#64748b` → `#e2e8f0` (밝은 흰색)
- Minor tick 추가 (주요 틱의 절반 간격)

**수정 파일**: `backend/main.py` (`generate_spectrogram_image`)

---

### 6. 스펙트로그램 플레이헤드 (인터랙티브)

**요청**: 슬라이더 이동 시 스펙트로그램에 타임스탬프 표시
**구현**:
- `Spectrogram` 컴포넌트에 `currentTime`, `duration`, `onSeek` props 추가
- 재생 위치: 흰색 세로선 + 상단 타임스탬프 오버레이
- 호버 위치: 주황색 세로선 + 하단 타임스탬프
- 스펙트로그램 클릭 시 해당 시간으로 seek
- `AudioPlayer`에 `onTimeUpdate`, `externalAudioRef` 콜백 추가

**수정 파일**: `ResultPanel.jsx`, `AudioPlayer.jsx`

---

### 7. 프롬프트 기반 믹싱

**요청**: `demucs_local_mixing.py`의 프롬프트 믹싱을 웹앱으로 포팅
**구현**:
- `MixingPanel.jsx` — 오른쪽 패널 신규 컴포넌트
  - 악기 스템 버튼, 구간/볼륨 설정 UI
  - 프롬프트 자유 입력 + 미리보기 + 실행
- `backend/main.py`:
  - `parse_mixing_prompt()` — 한국어 프롬프트 파싱
  - `execute_mix()` — pydub로 볼륨 조절/믹싱 실행
  - `/api/mix/{job_id}`, `/api/parse-prompt/{job_id}` 엔드포인트
- 믹싱 진행률 표시, "AI 믹싱 실행 중..." 문구

**수정 파일**: `MixingPanel.jsx` (신규), `App.jsx`, `backend/main.py`

---

### 8. 다운로드 기능 정비

**요청**: 스템별 다운로드 (파일명_stem.mp3), Download All ZIP, 믹싱 결과 다운로드
**구현**:
- 스템 다운로드: `원본파일명_stemName.mp3` 형식, Content-Disposition 헤더
- `/api/download-all/{job_id}` — 전체 스템 ZIP 다운로드
- `/api/download-mix/{job_id}/{mix_id}` — 믹싱 결과 다운로드

**수정 파일**: `backend/main.py`, `App.jsx`, `ResultPanel.jsx`, `MixingPanel.jsx`

---

### 9. Library 기능

**요청**: 결과물을 라이브러리에 추가
**구현**:
- `/api/library/add` — 스템+믹스 파일을 library/ 폴더에 복사 저장
- `/api/library` — 목록 조회
- ResultPanel, MixingPanel에 "Library 추가" 버튼

**수정 파일**: `backend/main.py`, `App.jsx`, `ResultPanel.jsx`, `MixingPanel.jsx`

---

### 10. 프롬프트 히스토리

**요청**: 프롬프트 전체 삭제 버튼, 히스토리 저장/조회 (파일명_%datetime% 형식)
**구현**:
- 전체 삭제 (Trash2 아이콘), 저장 (Save 아이콘), 히스토리 패널 (History 아이콘)
- `/api/prompt-history/save` — `파일명_YYYYMMDD_HHMMSS.txt` 파일 저장
- `/api/prompt-history` — 목록 조회 (최신순)
- `/api/prompt-history/{filename}` — 개별 삭제
- 히스토리 항목 클릭 시 프롬프트 입력란에 로드

**수정 파일**: `MixingPanel.jsx`, `backend/main.py`

---

### 11. .gitignore 갱신

**요청**: 프로젝트에서 git에 넣지 말아야 할 파일 정리
**구현**: 카테고리별 제외 항목 정리
- Python (`__pycache__`, `*.pyc`), Node.js (`node_modules/`), 오디오 (`*.mp3`, `*.wav`), 임시/로그, IDE, ML 모델, 보안 파일

**수정 파일**: `.gitignore`

---

### 12. Phase 1: BS-RoFormer 체이닝 엔진 도입

**요청**: `lalal따라하기.pdf` 기반 개발 계획 수립 및 Phase 1 구현
**구현**:
- `audio-separator[gpu]` v0.41.1 설치 (BS-RoFormer 모델 639MB)
- `demucs_service.py` 대폭 확장:
  - `engine` 필드로 `demucs` / `chained` 자동 분기
  - `_separate_chained()`: Pass 1 BS-RoFormer(SDR 12.97) → Pass 2 Demucs 6s
  - WAV → MP3 자동 변환, progress 콜백 지원
- 새 모델 2개 추가:
  - `bs_roformer_4s` — 4 스템 (고급 보컬): BS-RoFormer + Demucs ft
  - `bs_roformer_6s` — 6 스템 (고급 보컬): BS-RoFormer + Demucs 6s
- 프론트엔드: 모델 선택 UI를 카드 버튼 스타일로 변경, PRO 뱃지 표시
- 성능: 158초 오디오 기준 약 42초 (Pass1 26s + Pass2 9s)

**수정 파일**: `demucs_service.py`, `backend/main.py`, `App.jsx`

**참고 출처**:
- python-audio-separator: https://github.com/nomadkaraoke/python-audio-separator (MIT)
- BS-RoFormer: https://github.com/lucidrains/BS-RoFormer
- Demucs v4: https://github.com/facebookresearch/demucs (MIT)

---

### 파일별 최종 코드 규모

| 파일 | 라인 수 |
|---|---|
| `backend/main.py` | 937 |
| `backend/demucs_service.py` | 340 |
| `frontend/src/App.jsx` | 287 |
| `frontend/src/components/MixingPanel.jsx` | 536 |
| `frontend/src/components/ResultPanel.jsx` | 346 |
| `frontend/src/components/AudioPlayer.jsx` | 206 |
| `frontend/src/index.css` | 190 |
| 기타 컴포넌트 | 265 |
| **합계** | **~3,107** |
