# LUKUS Music Mixer — 개발 계획서 v2
## "LALAL.AI 수준 12-stem 분리" 로드맵

> **작성일**: 2026-03-06
> **참고 문서**: `lalal따라하기.pdf` (다단계 체이닝 파이프라인 리서치)
> **현재 상태**: Demucs 6-stem + 프롬프트 믹싱 프로토타입 완성

---

## 1. 현재 시스템 (As-Is)

| 항목 | 현재 상태 |
|---|---|
| **분리 엔진** | Demucs v4 단일 모델 (`htdemucs`, `htdemucs_ft`, `htdemucs_6s`) |
| **최대 스템** | 6개 (vocals, drums, bass, guitar, piano, other) |
| **프론트엔드** | React + Tailwind (3컬럼 레이아웃, 스펙트로그램, 플레이헤드) |
| **믹싱** | 프롬프트 기반 볼륨 조절 (pydub) |
| **백엔드** | FastAPI, 인메모리 job 관리 |
| **저장** | 임시 파일 기반 (/tmp), Library 기본 구현 |

### 한계
- Demucs 6-stem이 한계 → Strings, Brass, Woodwinds, Synth 분리 불가
- 보컬 분리 품질이 LALAL.AI 대비 낮음 (BS-RoFormer SDR 12.97 vs Demucs ~10)
- 드럼 세부 분리 불가 (Kick/Snare/HiHat/Toms)
- Lead/Backing Vocals 분리 불가

---

## 2. 목표 시스템 (To-Be)

### 최대 12-stem 분리 파이프라인

```
원본 음악
│
├─ Pass 1: BS-RoFormer (보컬/반주 분리 — 현존 최고 SDR 12.97)
│   ├── Vocals
│   └── Instrumental ──────────────────────┐
│                                          │
├─ Pass 2: Demucs htdemucs_6s (반주 → 6스템)
│   ├── Drums                              │
│   ├── Bass                               │
│   ├── Guitar                             │
│   ├── Piano/Keyboard                     │
│   └── Other ─────────────────────────────┤
│                                          │
├─ Pass 3: MelBand-RoFormer (보컬 세분화)  │
│   ├── Lead Vocals                        │
│   └── Backing Vocals                     │
│                                          │
├─ Pass 4: DrumSep (드럼 세분화)           │
│   ├── Kick                               │
│   ├── Snare                              │
│   ├── Toms                               │
│   └── Cymbals/HiHat                      │
│                                          │
└─ Pass 5: Banquet 쿼리 기반 (롱테일 악기) │
    ├── Strings (바이올린 쿼리)             │
    ├── Brass (트럼펫 쿼리)                │
    ├── Woodwinds (플룻 쿼리)              │
    ├── Synthesizer (신스 쿼리)            │
    └── FX/Other                           │
```

### Suno 12-stem 대비 커버리지

| # | Suno 스템 | 오픈소스 커버 모델 | Pass |
|---|---|---|---|
| 1 | Vocals | BS-RoFormer (SDR 12.97) | 1 |
| 2 | Backing Vocals | MelBand-RoFormer Karaoke | 3 |
| 3 | Drums | Demucs 6s | 2 |
| 4 | Bass | Demucs 6s | 2 |
| 5 | Guitar | Demucs 6s | 2 |
| 6 | Keyboard | Demucs 6s (piano) | 2 |
| 7 | Strings | Banquet 쿼리 | 5 |
| 8 | Brass | Banquet 쿼리 | 5 |
| 9 | Woodwinds | Banquet 쿼리 | 5 |
| 10 | Percussion | DrumSep (Drums → 재분리) | 4 |
| 11 | Synthesizer | Banquet 쿼리 | 5 |
| 12 | FX/Other | 잔여 신호 | 2 |

---

## 3. 단계별 개발 계획

### Phase 1: 코어 엔진 교체 (1~2주)
> **목표**: python-audio-separator 기반으로 엔진 교체, BS-RoFormer 보컬 분리 도입

| 태스크 | 설명 | 우선순위 |
|---|---|---|
| 1-1 | `pip install audio-separator[gpu]` 설치 및 환경 검증 | P0 |
| 1-2 | `StemSeparatorService` 클래스 신규 구현 (기존 `DemucsService` 래핑) | P0 |
| 1-3 | Pass 1 구현: BS-RoFormer 보컬/반주 분리 | P0 |
| 1-4 | Pass 2 구현: Demucs 6s 반주→스템 분리 (기존 로직 활용) | P0 |
| 1-5 | 분리 모드 선택 UI: "빠른 분리(6스템)" / "고급 분리(12스템)" | P1 |
| 1-6 | 테스트: 기존 Demucs 단독 vs 새 파이프라인 A/B 비교 | P0 |

**참고 출처**:
- python-audio-separator: https://github.com/nomadkaraoke/python-audio-separator (MIT)
- BS-RoFormer: https://github.com/lucidrains/BS-RoFormer

### Phase 2: 보컬 세분화 + 드럼 세분화 (1주)
> **목표**: Lead/Backing 보컬 분리, 드럼 → Kick/Snare/Toms/Cymbals 분리

| 태스크 | 설명 | 우선순위 |
|---|---|---|
| 2-1 | Pass 3 구현: MelBand-RoFormer Lead/Backing Vocals 분리 | P0 |
| 2-2 | Pass 4 구현: DrumSep (UVR5 모델) Kick/Snare/Toms/Cymbals | P1 |
| 2-3 | UI: 드럼 세부 스템 접기/펼치기 (트리 구조) | P1 |
| 2-4 | 품질 검증 및 파라미터 튜닝 | P0 |

**참고 출처**:
- MelBand-RoFormer: audio-separator 내장 모델 `mel_band_roformer_karaoke_aufr33_viperx.ckpt`
- DrumSep: UVR5 커뮤니티 모델

### Phase 3: 롱테일 악기 — Banquet 쿼리 기반 (2주)
> **목표**: Strings, Brass, Woodwinds, Synth 등 롱테일 악기 분리

| 태스크 | 설명 | 우선순위 |
|---|---|---|
| 3-1 | Banquet 모델 설치 (`query-bandit` 리포) 및 추론 파이프라인 구현 | P0 |
| 3-2 | 레퍼런스 쿼리 오디오 샘플 수집 (바이올린, 트럼펫, 플룻, 신스 등) | P0 |
| 3-3 | Pass 5 구현: Other 스템 → Banquet 쿼리 → 롱테일 악기 추출 | P0 |
| 3-4 | 사용자 커스텀 쿼리 업로드 기능 (자기가 원하는 악기 샘플 제공) | P2 |
| 3-5 | UI: 쿼리 기반 분리 결과 표시 + "악기 추가 분리" 인터랙션 | P1 |

**참고 출처**:
- Banquet: https://github.com/kwatcharasupat/query-bandit (24.9M params)
- 논문: Query-Based Music Source Separation (ResearchGate)

### Phase 4: 앙상블 & 품질 최적화 (1주)
> **목표**: MVSEP 방식 앙상블로 분리 품질 극대화

| 태스크 | 설명 | 우선순위 |
|---|---|---|
| 4-1 | MVSEP 앙상블 전략 연구 및 적용 (여러 모델 가중 평균) | P1 |
| 4-2 | 보컬: BS-RoFormer + MelBand-RoFormer + SCNet XL 앙상블 | P2 |
| 4-3 | 반주: Demucs4_ft + Demucs4_ht + Demucs4_6s 다중 모델 조합 | P2 |
| 4-4 | SDR 벤치마크 자동화 (MUSDB18 테스트셋) | P2 |

**참고 출처**:
- MVSEP 앙상블: https://github.com/ZFTurbo/MVSEP-MDX23-music-separation-model
- S3sound 멀티스템 가이드

### Phase 5: 프로덕션 & UX 고도화 (2주)
> **목표**: 서비스 수준 안정화, UX 개선

| 태스크 | 설명 | 우선순위 |
|---|---|---|
| 5-1 | Job 상태 영속화 (SQLite/Redis) — 서버 재시작 시 보존 | P0 |
| 5-2 | 파일 관리: 자동 정리 (TTL 기반), 용량 제한 | P0 |
| 5-3 | 프로그레스 세분화: Pass별 진행률 표시 | P1 |
| 5-4 | Library 고도화: 검색, 태그, 정렬, 삭제 | P1 |
| 5-5 | 믹싱 고도화: EQ, 리버브, 패닝 등 이펙트 추가 | P2 |
| 5-6 | 배치 처리: 여러 파일 동시 분리 큐 | P2 |
| 5-7 | Docker 컨테이너화 및 배포 가이드 | P1 |
| 5-8 | 사용자 인증/권한 (ISMS-P 보안 코딩 가이드 준수) | P1 |

---

## 4. 기술 스택 변경 사항

| 구분 | 현재 (As-Is) | 변경 후 (To-Be) |
|---|---|---|
| **분리 엔진** | `demucs` (단일) | `audio-separator` (메인) + `demucs` + `banquet` |
| **보컬 분리** | Demucs 내장 | BS-RoFormer (SDR 12.97) |
| **보컬 세분화** | 없음 | MelBand-RoFormer (Lead/Backing) |
| **드럼 세분화** | 없음 | DrumSep (Kick/Snare/Toms/Cymbals) |
| **롱테일 악기** | 없음 | Banquet 쿼리 기반 |
| **Job 저장** | 인메모리 dict | SQLite + 파일시스템 |
| **GPU 요구** | CUDA (선택) | CUDA (필수, RTX 3060+) |

---

## 5. 필요 리소스

### 하드웨어
- **GPU**: RTX 3060 이상 (VRAM 8GB+), 현재 서버 CUDA 확인 완료
- **디스크**: 모델 가중치 약 5~10GB, 임시 오디오 파일용 여유 공간

### 모델 가중치 (자동 다운로드)
| 모델 | 크기 (approx) | 용도 |
|---|---|---|
| `model_bs_roformer_ep_317_sdr_12.9755.ckpt` | ~500MB | 보컬/반주 분리 |
| `htdemucs_6s` | ~80MB | 6스템 분리 |
| `mel_band_roformer_karaoke_aufr33_viperx.ckpt` | ~400MB | Lead/Backing 보컬 |
| DrumSep 모델 | ~200MB | 드럼 세분화 |
| `ev-pre-aug.ckpt` (Banquet) | ~100MB | 쿼리 기반 추출 |

### Python 패키지 추가
```
audio-separator[gpu]   # UVR5 엔진 (BS-RoFormer, MelBand 등 포함)
# banquet은 git clone 후 로컬 설치
```

---

## 6. 리스크 및 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| 다단계 파이프라인 처리 시간 증가 | 사용자 대기 시간 ↑ | Pass별 프로그레스 표시, 비동기 처리, 분리 모드 선택 (빠른/고급) |
| GPU 메모리 부족 (여러 모델 로드) | OOM 크래시 | 모델 순차 로드/해제, `torch.cuda.empty_cache()` |
| Banquet 쿼리 품질 불안정 | 롱테일 악기 분리 품질 ↓ | 고품질 레퍼런스 샘플 확보, 사용자 피드백 루프 |
| DrumSep 모델 가용성 | UVR5 커뮤니티 모델 의존 | 대안: Demucs drums를 그대로 사용 (기본 폴백) |
| 모델 라이선스 충돌 | 상용화 제약 | MIT 라이선스 모델 우선 사용, 연구용 모델은 명시 |

---

## 7. 마일스톤 타임라인

```
Week 1-2  ▓▓▓▓▓▓▓▓░░  Phase 1: 코어 엔진 교체 (audio-separator + BS-RoFormer)
Week 3    ▓▓▓▓░░░░░░  Phase 2: 보컬/드럼 세분화
Week 4-5  ▓▓▓▓▓▓▓▓░░  Phase 3: Banquet 롱테일 악기
Week 6    ▓▓▓▓░░░░░░  Phase 4: 앙상블 최적화
Week 7-8  ▓▓▓▓▓▓▓▓░░  Phase 5: 프로덕션 & UX 고도화
```

**총 예상 기간: 6~8주**

---

## 8. 즉시 실행 가능한 첫 단계

Phase 1-1부터 시작하려면:

```bash
# 1. audio-separator 설치
pip install audio-separator[gpu]

# 2. BS-RoFormer 모델 테스트
python -c "
from audio_separator.separator import Separator
sep = Separator(output_dir='./test_stems')
sep.load_model('model_bs_roformer_ep_317_sdr_12.9755.ckpt')
stems = sep.separate('input.mp3')
print(stems)
"
```

---

> **참고 출처 종합**:
> - python-audio-separator: https://github.com/nomadkaraoke/python-audio-separator (MIT)
> - BS-RoFormer: https://github.com/lucidrains/BS-RoFormer
> - Banquet: https://github.com/kwatcharasupat/query-bandit
> - MVSEP: https://github.com/ZFTurbo/MVSEP-MDX23-music-separation-model
> - Demucs v4: https://github.com/facebookresearch/demucs (MIT)
> - LALAL따라하기.pdf 리서치 문서
