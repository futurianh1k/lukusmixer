# Phase 3: Banquet 쿼리 기반 14스템 분리

**날짜**: 2026-03-09  
**작성자**: AI Assistant  

---

## 개요

10스템 파이프라인에 Banquet (query-bandit) 모델을 통합하여 "Other" 스템에서
4개의 추가 악기(현악기, 금관악기, 목관악기, 신디사이저)를 분리하는 14스템 엔진을 구현했다.

## 참고 출처

- **Banquet**: https://github.com/kwatcharasupat/query-bandit (MIT License)
  - Watcharasupat & Lerch, "A Stem-Agnostic Single-Decoder System for Music Source Separation Beyond Four Stems", ISMIR 2024
  - arXiv: https://arxiv.org/abs/2406.18747
- **PaSST**: https://github.com/kkoutini/PaSST (Apache-2.0)
- **모델 가중치**: https://zenodo.org/records/13694558 (ev-pre-aug.ckpt, 270MB)

## 변경 사항

### 1. 백엔드

#### 신규 파일
| 파일 | 설명 |
|------|------|
| `backend/banquet_service.py` | Banquet 모델 래핑 서비스 (싱글톤 지연 로딩) |
| `backend/generate_query_audio.py` | 레퍼런스 쿼리 오디오 합성 스크립트 |
| `backend/banquet_queries/` | 4개 레퍼런스 쿼리 WAV (각 10초) |
| `backend/query_bandit/` | query-bandit 리포 클론 + 체크포인트 |
| `backend/tests/test_banquet.py` | 26개 Banquet 관련 테스트 |

#### 수정 파일
| 파일 | 변경 내용 |
|------|-----------|
| `backend/demucs_service.py` | `banquet_14s` 모델 등록, Pass 5 엔진(`_separate_chained_banquet`), STEM_LABELS/STEM_HIERARCHY에 4개 신규 스템 추가 |
| `backend/main.py` | INSTRUMENT_MAP에 14개 한글 키워드 추가, _SPEC_COLORS 확장, SystemInfo에 `banquet_available` 필드, /api/system에서 Banquet 미사용 시 모델 숨김 |

### 2. 프론트엔드

| 파일 | 변경 내용 |
|------|-----------|
| `frontend/src/components/ResultPanel.jsx` | STEM_COLORS, STEM_LABELS, STEM_KR, STEM_GROUPS에 banquet 그룹 추가, StemGroup에 violet 색상 |
| `frontend/src/components/MixingPanel.jsx` | STEM_CONFIG에 4개 신규 스템 + 색상 맵 확장, 인식 키워드 안내 문구 업데이트 |
| `frontend/src/components/StemSelector.jsx` | STEM_CONFIG에 14스템 전체 등록 |
| `frontend/src/types/api.ts` | `chained_banquet` 엔진 타입, `banquet_available` 필드 추가 |

### 3. 14스템 파이프라인 구조

```
원본 오디오
  │
  ├── Pass 1: BS-RoFormer → Vocals / Instrumental
  │
  ├── Pass 2: Demucs 6s → Instrumental → drums, bass, guitar, piano, other
  │
  ├── Pass 3: MelBand-RoFormer → Vocals → Lead Vocals / Backing Vocals
  │
  ├── Pass 4: DrumSep → Drums → kick, snare, toms, cymbals
  │
  └── Pass 5: Banquet → Other → strings, brass, woodwinds, synthesizer
```

### 4. 새 스템 목록 (14개)

| # | 스템 | 한글 | 그룹 | 추출 방식 |
|---|------|------|------|-----------|
| 1 | lead_vocals | 리드 보컬 | vocals | MelBand-RoFormer |
| 2 | backing_vocals | 백킹 보컬 | vocals | MelBand-RoFormer |
| 3 | kick | 킥 | drums | DrumSep |
| 4 | snare | 스네어 | drums | DrumSep |
| 5 | toms | 탐 | drums | DrumSep |
| 6 | cymbals | 심벌즈 | drums | DrumSep |
| 7 | bass | 베이스 | — | Demucs 6s |
| 8 | guitar | 기타 | — | Demucs 6s |
| 9 | piano | 피아노 | — | Demucs 6s |
| 10 | **strings** | **현악기** | banquet | **Banquet (바이올린 쿼리)** |
| 11 | **brass** | **금관악기** | banquet | **Banquet (트럼펫 쿼리)** |
| 12 | **woodwinds** | **목관악기** | banquet | **Banquet (플루트 쿼리)** |
| 13 | **synthesizer** | **신디사이저** | banquet | **Banquet (신스 쿼리)** |
| 14 | other | 기타 악기 | — | 잔여 Other |

### 5. 프롬프트 파서 키워드 (신규)

| 한글 키워드 | 매핑 스템 |
|-------------|-----------|
| 현악기, 스트링, 바이올린, 비올라, 첼로 | strings |
| 금관악기, 브라스, 트럼펫, 트롬본, 호른, 튜바 | brass |
| 목관악기, 우드윈드, 플루트, 플룻, 클라리넷, 오보에, 바순, 색소폰 | woodwinds |
| 신디사이저, 신스, 싱스, 패드, 신디 | synthesizer |

## 테스트 결과

- 전체 테스트: **105개 통과** (기존 79 + 신규 26)
- 프론트엔드 빌드: **성공**

## 향후 개선 사항

- 합성 쿼리 오디오를 실제 악기 녹음(CC0)으로 교체하면 분리 품질 향상
- 사용자 커스텀 쿼리 업로드 기능 (ROADMAP 3-5, P2)
- RTX 3070 메모리 최적화 (현재 batch_size=3)
