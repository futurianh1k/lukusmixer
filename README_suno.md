# 🎵 SUNO AI Music Mashup Demo

음악 A + 음악 B를 업로드하여 AI가 새로운 음악 C를 생성하는 데모 애플리케이션입니다.

## 기능

| 기능 | 설명 |
|------|------|
| **매시업** | 두 곡을 업로드하여 AI가 새로운 곡으로 합성 |
| **커버/리믹스** | 한 곡을 업로드하고 스타일을 변경하여 새로운 버전 생성 |
| **실시간 로그** | 각 단계별 진행 상황을 실시간으로 확인 |
| **오디오 재생** | 생성된 음악을 브라우저에서 바로 재생 |

## 설치 및 실행

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 실행
python suno_mashup_demo.py

# 3. 브라우저에서 접속
# → http://localhost:7860
```

## API Key 발급

1. [ttapi.io](https://ttapi.io) 회원가입
2. Dashboard → API Key 복사
3. UI에서 API Key 입력

## 워크플로우

```
🎵 Music A ──┐
             ├── Upload → Mashup → Fetch → 🎧 Music C
🎶 Music B ──┘
```

## 지원 파일 형식

MP3, WAV, OGG, FLAC (최대 8분)

## API Endpoints (TTAPI)

- `POST /suno/v1/upload` — 오디오 업로드 (무료)
- `POST /suno/v1/mashup` — 매시업 생성
- `POST /suno/v1/cover` — 커버/리믹스 생성
- `POST /suno/v1/fetch` — 결과 조회
