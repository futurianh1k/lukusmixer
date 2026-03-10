# LUKUS Music Mixer — 향후 개발 계획 (Roadmap)
> **작성일**: 2026-03-06
> **현재 버전**: v1.0 (Phase 1 완료)
> **목표**: LALAL.AI / Suno AI 수준의 12-stem 분리 + 프로덕션 서비스

---

## 전체 로드맵 개요

```
                          현재 위치
                              ▼
Phase 1 ████████████████████████ 완료 — BS-RoFormer 체이닝 (6스템)
Phase 2 ░░░░░░░░░░░░░░░░░░░░░░ 예정 — 보컬/드럼 세분화 (10스템)
Phase 3 ░░░░░░░░░░░░░░░░░░░░░░ 예정 — Banquet 롱테일 악기 (12스템)
Phase 4 ░░░░░░░░░░░░░░░░░░░░░░ 예정 — 앙상블 품질 최적화
Phase 5 ░░░░░░░░░░░░░░░░░░░░░░ 예정 — 프로덕션 & UX 고도화
```

---

## Phase 2: 보컬 세분화 + 드럼 세분화 (예상 1주)

### 목표
현재 6스템 → **10스템**으로 확장

### 추가되는 스템

| # | 신규 스템 | 원본 소스 | 사용 모델 |
|---|---|---|---|
| 1 | **Lead Vocals** | Vocals에서 분리 | MelBand-RoFormer |
| 2 | **Backing Vocals** | Vocals에서 분리 | MelBand-RoFormer |
| 3 | **Kick** | Drums에서 분리 | DrumSep (UVR5) |
| 4 | **Snare** | Drums에서 분리 | DrumSep (UVR5) |
| 5 | **Toms** | Drums에서 분리 | DrumSep (UVR5) |
| 6 | **Cymbals/HiHat** | Drums에서 분리 | DrumSep (UVR5) |

### 태스크

| ID | 태스크 | 우선순위 | 예상 |
|---|---|---|---|
| 2-1 | MelBand-RoFormer 모델 테스트 (`mel_band_roformer_karaoke_aufr33_viperx.ckpt`) | P0 | 2h |
| 2-2 | Pass 3 구현: Vocals → Lead/Backing 분리 | P0 | 4h |
| 2-3 | DrumSep 모델 확인 및 테스트 | P0 | 2h |
| 2-4 | Pass 4 구현: Drums → Kick/Snare/Toms/Cymbals | P0 | 4h |
| 2-5 | `demucs_service.py`에 새 모델 옵션 추가 (`bs_roformer_10s`) | P0 | 2h |
| 2-6 | UI: 하위 스템 접기/펼치기 트리 구조 | P1 | 4h |
| 2-7 | 프롬프트 파서 확장: "킥", "스네어", "코러스" 등 새 키워드 | P1 | 2h |
| 2-8 | 통합 테스트 | P0 | 2h |

### 참고 출처
- MelBand-RoFormer: audio-separator 내장 모델
- DrumSep: UVR5 커뮤니티 모델

---

## Phase 3: 롱테일 악기 — Banquet 쿼리 기반 (예상 2주)

### 목표
10스템 → **14스템** (+ Strings, Brass, Woodwinds, Synth + Other 잔여)

### 추가되는 스템

| # | 신규 스템 | 원본 소스 | 방식 |
|---|---|---|---|
| 1 | **Strings** | Other에서 추출 | Banquet (바이올린 쿼리) |
| 2 | **Brass** | Other에서 추출 | Banquet (트럼펫 쿼리) |
| 3 | **Woodwinds** | Other에서 추출 | Banquet (플룻 쿼리) |
| 4 | **Synthesizer** | Other에서 추출 | Banquet (신스 쿼리) |

### 태스크

| ID | 태스크 | 우선순위 | 상태 |
|---|---|---|---|
| 3-1 | `query-bandit` 리포 클론 및 환경 구축 | P0 | ✅ 완료 |
| 3-2 | Banquet 추론 파이프라인 래핑 (`banquet_service.py`) | P0 | ✅ 완료 |
| 3-3 | 레퍼런스 쿼리 오디오 수집 (합성 4종) | P0 | ✅ 완료 |
| 3-4 | Pass 5 구현: Other → Banquet → 롱테일 악기 | P0 | ✅ 완료 |
| 3-5 | 14스템 모델 옵션 등록 + 프롬프트 키워드 확장 | P0 | ✅ 완료 |
| 3-6 | 프론트엔드 UI 14스템 대응 (Banquet 그룹 색상) | P1 | ✅ 완료 |
| 3-7 | 통합 테스트 26개 추가 (총 105개) | P0 | ✅ 완료 |
| 3-8 | 사용자 커스텀 쿼리 업로드 기능 | P2 | ⏳ 추후 |

### 참고 출처
- Banquet: https://github.com/kwatcharasupat/query-bandit (24.9M params, MIT)
- 모델 가중치: https://zenodo.org/records/13694558
- 필요 GPU: RTX 3060 이상 (batch_size=3 기준 ~8GB VRAM)

---

## Phase 4: 앙상블 품질 최적화 (예상 1주)

### 목표
MVSEP 방식의 다중 모델 앙상블로 분리 품질 극대화

### 태스크

| ID | 태스크 | 우선순위 |
|---|---|---|
| 4-1 | MVSEP 앙상블 전략 연구 및 코드 분석 | P1 |
| 4-2 | 보컬 앙상블: BS-RoFormer + MelBand-RoFormer + SCNet XL | P2 |
| 4-3 | 반주 앙상블: Demucs4_ft + Demucs4_ht + Demucs4_6s | P2 |
| 4-4 | SDR 벤치마크 자동화 (MUSDB18 테스트셋) | P2 |
| 4-5 | GPU 메모리 최적화 (모델 순차 로드/해제) | P1 |

### 참고 출처
- MVSEP: https://github.com/ZFTurbo/MVSEP-MDX23-music-separation-model

---

## Phase 5: 프로덕션 & UX 고도화 (예상 2주)

### 5A. 인프라 안정화

| ID | 태스크 | 우선순위 |
|---|---|---|
| 5A-1 | Job 상태 영속화: SQLite 또는 Redis | P0 |
| 5A-2 | 파일 관리: TTL 자동 정리, 용량 제한 | P0 |
| 5A-3 | Docker 컨테이너화 + docker-compose | P1 |
| 5A-4 | 에러 핸들링 구조화, 재시도 로직 | P1 |
| 5A-5 | Python logging 모듈 도입 (print → logger) | P1 |

### 5B. 보안 (ISMS-P 준수)

| ID | 태스크 | 우선순위 |
|---|---|---|
| 5B-1 | 사용자 인증 (JWT 또는 세션) | P0 |
| 5B-2 | CORS 제한 (allow_origins 구체화) | P0 |
| 5B-3 | 파일 업로드 보안: MIME + Magic number 검증, 크기 제한 | P0 |
| 5B-4 | Admin 기능: 별도 URL prefix + role 체크 + Audit Log | P1 |
| 5B-5 | 시크릿 관리: .env + Secret Manager | P1 |

### 5C. UX 개선

| ID | 태스크 | 우선순위 |
|---|---|---|
| 5C-1 | Pass별 세분화 프로그레스 (Pass 1/5, 2/5...) | P1 |
| 5C-2 | Library 고도화: 검색, 태그, 정렬, 삭제, 미리듣기 | P1 |
| 5C-3 | 믹싱 이펙트 확장: EQ, 리버브, 패닝, 컴프레서 | P2 |
| 5C-4 | 배치 처리: 여러 파일 동시 분리 큐 | P2 |
| 5C-5 | WebSocket 실시간 로그 스트리밍 | P2 |
| 5C-6 | 반응형 디자인 (모바일 대응) | P2 |

### 5D. 테스트

| ID | 태스크 | 우선순위 |
|---|---|---|
| 5D-1 | pytest 유닛 테스트: DemucsService, 프롬프트 파서, 믹싱 로직 | P0 |
| 5D-2 | API 통합 테스트: 업로드 → 분리 → 다운로드 E2E | P0 |
| 5D-3 | 프론트엔드 컴포넌트 테스트 (React Testing Library) | P2 |

---

## 타임라인 요약

```
Week 1    ▓▓▓▓▓▓▓▓░░  Phase 2: 보컬/드럼 세분화 (10스템)
Week 2-3  ▓▓▓▓▓▓▓▓▓░  Phase 3: Banquet 롱테일 악기 (12스템)
Week 4    ▓▓▓▓▓░░░░░  Phase 4: 앙상블 최적화
Week 5-6  ▓▓▓▓▓▓▓▓▓▓  Phase 5: 프로덕션 & UX & 보안
```

**총 예상 기간**: 약 5~6주 (Phase 1 이후 기준)

---

## 스템 확장 로드맵

```
v1.0 (현재)    : Vocals, Drums, Bass, Guitar, Piano, Other          → 6스템
v2.0 (Phase 2) : + Lead/Backing Vocals, Kick/Snare/Toms/Cymbals     → 10스템
v3.0 (Phase 3) : + Strings, Brass, Woodwinds, Synth                 → 12스템
v4.0 (Phase 4) : 앙상블 최적화로 각 스템 품질 향상                   → 12스템 (고품질)
v5.0 (Phase 5) : 프로덕션 서비스 + 인증 + Docker                    → 서비스 출시
```

---

## 참고 출처 종합

| 리소스 | URL | 라이선스 |
|---|---|---|
| python-audio-separator | https://github.com/nomadkaraoke/python-audio-separator | MIT |
| BS-RoFormer | https://github.com/lucidrains/BS-RoFormer | MIT |
| Demucs v4 | https://github.com/facebookresearch/demucs | MIT |
| Banquet | https://github.com/kwatcharasupat/query-bandit | 연구용 |
| MVSEP 앙상블 | https://github.com/ZFTurbo/MVSEP-MDX23-music-separation-model | MIT |
| lalal따라하기.pdf | 프로젝트 내부 리서치 문서 | — |
