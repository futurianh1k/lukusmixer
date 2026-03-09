# Phase 2 변경 내역 — 보컬 세분화 + 드럼 세분화 (6→10 스템)

**날짜**: 2026-03-09  
**브랜치**: master  
**작업자**: AI Assistant

---

## 목표

기존 6스템 분리(Vocals, Drums, Bass, Guitar, Piano, Other)를 10스템으로 확장:
- **보컬 세분화**: Vocals → Lead Vocals + Backing Vocals
- **드럼 세분화**: Drums → Kick + Snare + Toms + Cymbals (HiHat+Ride+Crash 합산)

---

## 사용 모델 (Phase 2에서 새로 추가)

| 모델 | 용도 | SDR | 출처 |
|------|------|-----|------|
| `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt` | 보컬 → Lead/Backing | 10.19 | aufr33 & viperx (python-audio-separator) |
| `MDX23C-DrumSep-aufr33-jarredou.ckpt` | 드럼 → 6서브스템 | 10.80 | aufr33 & jarredou (python-audio-separator) |

---

## 4-Pass 파이프라인 구조

```
원본 오디오
  │
  ├── Pass 1: BS-RoFormer (SDR 12.97)
  │     ├── Vocals (WAV)
  │     └── Instrumental (WAV)
  │
  ├── Pass 2: Demucs htdemucs_6s
  │     Instrumental → drums, bass, guitar, piano, other
  │
  ├── Pass 3: MelBand-RoFormer Karaoke
  │     Vocals → Lead Vocals + Backing Vocals
  │
  └── Pass 4: MDX23C DrumSep
        Drums → kick, snare, toms, hh, ride, crash
                                    └── cymbals (합산)
```

**총 처리 시간**: ~95초 (RTX 3070, 2분 38초 오디오 기준)

---

## 수정 파일

### 1. `backend/demucs_service.py`

**요청**: 10스템 분리 파이프라인 구현  
**변경 내용**:
- `DEMUCS_MODELS`에 `bs_roformer_10s` 모델 정의 추가 (engine: `chained_10s`)
- `STEM_LABELS`에 10스템 전체 라벨/색상 정의 추가 (lead_vocals, backing_vocals, kick, snare, toms, cymbals)
- `STEM_HIERARCHY` 딕셔너리 추가 — 하위 스템의 부모 그룹 정보 (UI 트리 구조용)
- 상수 추가: `MELBAND_KARAOKE_MODEL`, `DRUMSEP_MODEL`
- `separate()` 메서드에 `chained_10s` 엔진 분기 추가
- `_separate_chained_10s()` 메서드 신규 구현 — 4-Pass 파이프라인
- `_merge_audio_files()` 헬퍼 메서드 추가 — DrumSep hh+ride+crash → cymbals 합산

### 2. `frontend/src/App.jsx`

**요청**: 10스템 모델을 UI 모델 선택에 추가  
**변경 내용**:
- `MODELS` 배열에 `bs_roformer_10s` 항목 추가
- 모델 선택 버튼에 `chained_10s` 엔진용 "MAX" 뱃지 추가 (빨간색 강조)
- `isPro`/`is10s` 조건으로 UI 색상 분기

### 3. `frontend/src/components/ResultPanel.jsx`

**요청**: 10스템 하위 그룹 트리 구조 표시  
**변경 내용**:
- `STEM_COLORS`, `STEM_LABELS`, `STEM_KR`에 10스템 전체 항목 추가
- `STEM_GROUPS`, `GROUP_LABELS` 상수 추가 — 하위 스템 그룹핑 정보
- `StemCard` 컴포넌트 추출 — 개별 스템 카드 (들여쓰기 옵션 포함)
- `StemGroup` 컴포넌트 추가 — 접이식 그룹 헤더 + 하위 스템 목록
- `collapsedGroups` 상태 + `toggleGroup` 핸들러 추가
- 스템 렌더링 로직: 그룹 존재 시 트리 구조로, 없으면 기존 평면 구조

### 4. `frontend/src/components/MixingPanel.jsx`

**요청**: 새 스템 키워드 지원  
**변경 내용**:
- `STEM_CONFIG`에 10스템 전체 항목 추가 (lead_vocals, backing_vocals, kick, snare, toms, cymbals)

### 5. `backend/main.py`

**요청**: 프롬프트 파서에 새 키워드 추가  
**변경 내용**:
- `INSTRUMENT_MAP`에 키워드 추가:
  - 리드보컬, 리드, 메인보컬 → lead_vocals
  - 백킹보컬, 코러스, 하모니, 백보컬 → backing_vocals
  - 킥, 킥드럼, 베이스드럼 → kick
  - 스네어, 스네어드럼 → snare
  - 탐, 탐탐, 톰 → toms
  - 심벌즈, 심벌, 하이햇, 라이드, 크래시 → cymbals
- `VOLUME_ACTION_MAP`에 추가: 최대로 크게(+12dB), 매우 크게(+9dB), 매우 작게(-9dB), 최소(-12dB)

---

## 테스트 결과

| 항목 | 결과 |
|------|------|
| 프론트엔드 빌드 | ✅ 성공 |
| 백엔드 임포트 | ✅ 성공 |
| Linter 검사 | ✅ 에러 없음 |
| MelBand-RoFormer 단독 테스트 | ✅ 성공 (12초) |
| MDX23C DrumSep 단독 테스트 | ✅ 성공 (28초, 6스템 출력) |
| 10스템 통합 테스트 | ✅ 성공 (95초, 10스템 모두 생성) |

### 10스템 출력 확인

| 스템 | 크기 | 상태 |
|------|------|------|
| lead_vocals | 6.1 MB | ✅ |
| backing_vocals | 6.1 MB | ✅ |
| kick | 6.1 MB | ✅ |
| snare | 6.1 MB | ✅ |
| toms | 6.1 MB | ✅ |
| cymbals | 6.1 MB | ✅ |
| bass | 6.1 MB | ✅ |
| guitar | 6.1 MB | ✅ |
| piano | 6.1 MB | ✅ |
| other | 6.1 MB | ✅ |

---

## 참고 출처

- python-audio-separator: https://github.com/nomadkaraoke/python-audio-separator (MIT)
- MelBand-RoFormer Karaoke by aufr33 & viperx
- MDX23C DrumSep by aufr33 & jarredou: https://github.com/jarredou/models
- BS-RoFormer: https://github.com/lucidrains/BS-RoFormer
- Demucs v4: https://github.com/facebookresearch/demucs (MIT)
