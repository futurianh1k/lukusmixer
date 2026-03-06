# 🎛️ LUKUS Music Mixer

Loudly Stem Splitter 스타일의 음악 STEM 분리 웹 애플리케이션

![UI Preview](https://www.loudly.com/music/stem-splitter)

## 📁 프로젝트 구조

```
lukus-mixer/
├── backend/                 # FastAPI 백엔드
│   ├── main.py             # API 엔드포인트
│   ├── demucs_service.py   # Demucs 분리 로직
│   └── requirements.txt
├── frontend/               # React 프론트엔드
│   ├── src/
│   │   ├── components/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── FileUpload.jsx
│   │   │   ├── StemSelector.jsx
│   │   │   ├── AudioPlayer.jsx
│   │   │   └── ResultPanel.jsx
│   │   ├── App.jsx
│   │   └── index.css
│   └── package.json
└── README.md
```

## 🚀 빠른 시작

### 1. 백엔드 실행

```bash
cd backend

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 프론트엔드 실행

```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

### 3. 접속

- **프론트엔드**: http://localhost:3000
- **백엔드 API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs

## 🎵 기능

### STEM 분리
- **htdemucs**: 4 스템 (Vocals, Drums, Bass, Other) - 빠른 속도
- **htdemucs_ft**: 4 스템 - 최고 품질 (4배 느림)
- **htdemucs_6s**: 6 스템 (+ Guitar, Piano)

### 지원 포맷
- 입력: MP3, WAV, FLAC, OGG, M4A
- 출력: MP3 (320kbps)

## 🔌 API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/system` | 시스템 정보 |
| POST | `/api/upload` | 파일 업로드 |
| POST | `/api/split/{file_id}` | STEM 분리 시작 |
| GET | `/api/job/{job_id}` | 작업 상태 조회 |
| GET | `/api/download/{job_id}/{stem}` | 스템 다운로드 |
| GET | `/api/stream/{job_id}/{stem}` | 스템 스트리밍 |

## 🖥️ 시스템 요구사항

### 백엔드
- Python 3.10+
- CUDA (GPU) 권장 (CPU도 가능)
- RAM: 8GB+ (GPU: 4GB+ VRAM)

### 프론트엔드
- Node.js 18+
- npm 또는 yarn

## 📦 주요 의존성

### Backend
- FastAPI - 웹 프레임워크
- Demucs - STEM 분리 엔진
- PyTorch - 딥러닝 프레임워크
- Librosa - 오디오 처리

### Frontend
- React 18 - UI 프레임워크
- Tailwind CSS - 스타일링
- react-dropzone - 파일 업로드
- WaveSurfer.js - 오디오 파형 (예정)
- Lucide React - 아이콘

## 🎨 UI 특징

- **다크 테마**: Loudly 스타일의 모던한 다크 UI
- **실시간 진행률**: 작업 상태 실시간 표시
- **오디오 플레이어**: 각 스템별 재생 및 다운로드
- **드래그 앤 드롭**: 직관적인 파일 업로드

## 📝 TODO

- [ ] WaveSurfer.js 파형 시각화
- [ ] ZIP 일괄 다운로드
- [ ] 믹싱 기능 추가
- [ ] 사용자 인증
- [ ] 작업 히스토리
- [ ] WebSocket 실시간 업데이트

## 📄 라이선스

MIT License

## 🙏 참고

- [Demucs](https://github.com/adefossez/demucs) - Facebook Research
- [Loudly Stem Splitter](https://www.loudly.com/music/stem-splitter) - UI 디자인 참고
