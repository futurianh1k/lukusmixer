# 🎵 KIE.AI Music Studio

KIE.AI Suno API를 사용한 음악 생성 데모입니다.

## 기능

| 기능 | 설명 |
|------|------|
| 🎨 **커버 생성** | 기존 음악의 멜로디를 유지하면서 새로운 스타일로 변환 |
| 🔄 **확장 생성** | 기존 음악을 이어서 확장 |
| 🔀 **매시업** | 두 음악을 조합하여 새로운 음악 생성 |

## 설치

```bash
pip install gradio requests
```

## API Key 발급

1. [kie.ai](https://kie.ai) 회원가입
2. [API Key 관리 페이지](https://kie.ai/api-key)에서 API Key 발급
3. 데모 실행 후 API Key 입력

## 실행

```bash
python kie_mashup_demo.py
```

브라우저에서 `http://localhost:7861` 접속

## 참고 사항

### 파일 업로드 방식

KIE.AI는 **URL 기반 업로드**를 사용합니다. 로컬 파일은 자동으로 [0x0.st](https://0x0.st)에 임시 업로드됩니다.

### 제한 사항

| 기능 | 최대 길이 |
|------|----------|
| 커버 | 2분 |
| 확장 | 8분 |

### 모델 선택

| 모델 | 권장 용도 |
|------|----------|
| V5 | 최고 품질 |
| V4_5PLUS | 고품질 + 안정성 |
| V4 | 빠른 생성 (기본값) |

## API 문서

- [KIE.AI API 문서](https://docs.kie.ai/suno-api/)
- [Upload & Cover](https://docs.kie.ai/suno-api/upload-and-cover-audio/)
- [Upload & Extend](https://docs.kie.ai/suno-api/upload-and-extend-audio/)

## 비교: TTAPI vs KIE.AI

| 항목 | TTAPI (ttapi.io) | KIE.AI |
|------|-----------------|--------|
| 업로드 방식 | 직접 파일 업로드 | URL 기반 |
| 매시업 | 전용 API 있음 | 커버로 대체 |
| 안정성 | ❌ 현재 오류 | ✅ 정상 |

## 라이선스

비공식 API를 사용합니다. 상업적 이용 시 각 서비스의 이용약관을 확인하세요.
