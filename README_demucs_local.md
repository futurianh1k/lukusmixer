# 🎛️ Demucs Local Music Mixing

로컬 Demucs 기반 음악 믹싱 도구 (API 비용 없음!)

## 장점

| 항목 | KIE.AI API 버전 | Demucs 로컬 버전 |
|------|----------------|-----------------|
| 비용 | 50~80 크레딧/곡 | **무료** |
| 입력 | URL만 | **파일 업로드 + URL** |
| 스템 수 | 12개 | 4~6개 |
| 속도 | 빠름 (서버) | CPU: 느림, GPU: 빠름 |
| 오프라인 | 불가 | **가능** |

## 파이프라인

```
┌─────────────────────────────────────────────────────────────────┐
│  [로컬 Demucs]       [룰베이스]           [로컬 처리]           │
│  ① STEM 분리     →  ② 프롬프트 파싱  →  ③ 볼륨 조절          │
│  (4~6 트랙)          "전주 드럼 키워줘"     (pydub)             │
│  - vocals            → instrument: drums                        │
│  - drums             → section: 0~15s                           │
│  - bass              → action: +6dB                             │
│  - other                                                        │
│  (+ guitar, piano)                    ④ 트랙 합성              │
│                                       → 최종 출력               │
└─────────────────────────────────────────────────────────────────┘
```

## 설치

```bash
# 필수
pip install gradio demucs pydub

# 권장 (스펙트로그램)
pip install librosa matplotlib numpy

# Ubuntu ffmpeg (pydub 필요)
sudo apt install ffmpeg
```

### GPU 가속 (권장)

```bash
# CUDA 버전에 맞는 PyTorch 설치
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## 실행

```bash
python demucs_local_mixing.py
```

브라우저에서 `http://localhost:7863` 접속

## Demucs 모델

| 모델 | 출력 스템 | 특징 |
|------|----------|------|
| `htdemucs` (기본) | vocals, drums, bass, other | 빠른 속도 |
| `htdemucs_6s` | + guitar, piano | 6 스템 분리 |
| `htdemucs_ft` | vocals, drums, bass, other | 최고 품질 (4배 느림) |

## 프롬프트 문법

### 구간 키워드

| 키워드 | 의미 |
|--------|------|
| 전주, 인트로 | 0~15초 |
| 후주, 아웃트로 | 마지막 30초 |
| 전체 | 전체 구간 |
| 30초~40초 | 특정 구간 지정 |

### 악기 키워드

| 한글 | 영문 |
|------|------|
| 보컬, 목소리 | vocals |
| 드럼 | drums |
| 베이스 | bass |
| 기타 | guitar (6s 모델) |
| 피아노 | piano (6s 모델) |
| 나머지, 기타악기 | other |

### 볼륨 액션

| 키워드 | 효과 |
|--------|------|
| 키워, 크게 | +6dB |
| 조금 키워 | +3dB |
| 줄여, 작게 | -6dB |
| 음소거 | 완전 제거 |

### 예시

```
전주 드럼 키워줘
30초~40초 피아노 작게
기타 음소거
후주 보컬 강조
```

## 시스템 요구사항

### CPU 모드
- **시간**: 곡 길이의 약 1.5배
- **RAM**: 최소 4GB

### GPU 모드 (권장)
- **시간**: 실시간보다 빠름
- **VRAM**: 최소 3GB (권장 7GB)
- **CUDA**: 지원되는 NVIDIA GPU

## 참고

- [Demucs GitHub](https://github.com/adefossez/demucs)
- [Hybrid Transformer Demucs 논문](https://arxiv.org/abs/2211.08553)
