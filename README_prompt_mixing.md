# 🎛️ Prompt-Based Music Mixing

프롬프트 기반 음악 믹싱 도구

## 파이프라인

```
┌─────────────────────────────────────────────────────────────────┐
│  [Kie.ai API]        [룰베이스]           [로컬 처리]           │
│  ① split_stem    →  ② 프롬프트 파싱  →  ③ 볼륨 조절          │
│  (12트랙 분리)       "전주 드럼 키워줘"     (pydub)             │
│                      → instrument: drums                        │
│                      → section: 0~15s                           │
│                      → action: +6dB                             │
│                                            ④ 트랙 합성          │
│                                            → 최종 출력          │
└─────────────────────────────────────────────────────────────────┘
```

## 기능

### 1. STEM 분리 (KIE.AI API)
- 음악 URL 입력 → 12개 트랙으로 분리
- 분리되는 트랙: vocals, backing_vocals, drums, bass, guitar, keyboard, strings, brass, woodwinds, percussion, synth, fx

### 2. 스펙트로그램 시각화
- 원본 음악의 주파수-시간 분포 표시
- librosa + matplotlib 사용

### 3. 프롬프트 기반 믹싱
- 자연어로 볼륨 조절 명령 입력
- 예: "전주 드럼 키워줘", "30초~40초 피아노 작게"

### 4. 구간 선택 도우미
- GUI에서 악기, 구간, 볼륨을 선택하여 프롬프트에 추가

## 설치

```bash
# 필수 의존성
pip install gradio requests

# 오디오 처리 (권장)
pip install librosa matplotlib pydub numpy

# Ubuntu에서 ffmpeg 설치 (pydub 필요)
sudo apt install ffmpeg
```

## 실행

```bash
python prompt_mixing.py
```

브라우저에서 `http://localhost:7862` 접속

## 프롬프트 문법

### 구간 키워드

| 키워드 | 의미 |
|--------|------|
| 전주, 인트로 | 0~15초 |
| 후주, 아웃트로 | 마지막 30초 |
| 전체, 모두 | 전체 구간 |
| 30초~40초 | 특정 구간 지정 |
| 1분30초~2분 | 분:초 형식 지원 |

### 악기 키워드

| 한글 | 영문 |
|------|------|
| 보컬, 목소리 | vocals |
| 드럼 | drums |
| 베이스 | bass |
| 기타 | guitar |
| 피아노, 키보드 | keyboard |
| 현악기, 스트링 | strings |
| 타악기 | percussion |
| 신디사이저 | synth |

### 볼륨 액션

| 키워드 | 효과 |
|--------|------|
| 키워, 크게, 올려 | +6dB |
| 조금 키워 | +3dB |
| 줄여, 작게 | -6dB |
| 조금 줄여 | -3dB |
| 음소거, 뮤트 | 완전 제거 |

### 프롬프트 예시

```
전주 드럼 키워줘
30초~40초 피아노 작게
1분~1분30초 기타 키워줘
베이스 음소거
후주 현악기 강조
```

## API 비용

| 작업 | 크레딧 |
|------|--------|
| 음원 업로드 (cover) | ~10-30 |
| STEM 분리 (split_stem) | 50 |
| **총합** | ~60-80 크레딧 |

## 기술 스택

- **STEM 분리**: KIE.AI Suno API (`split_stem`)
- **스펙트로그램**: librosa + matplotlib
- **볼륨 조절/믹싱**: pydub
- **UI**: Gradio

## 참고

- [KIE.AI API 문서](https://docs.kie.ai/suno-api/separate-vocals)
- [API Key 발급](https://kie.ai/api-key)
