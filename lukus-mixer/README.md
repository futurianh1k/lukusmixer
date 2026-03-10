# LUKUS Music Mixer

AI 기반 음악 STEM 분리 웹 애플리케이션

## 주요 기능

- **다중 모델 지원**: 4/6/10/14 스템 분리
  - Demucs: 4스템 (Vocals, Drums, Bass, Other)
  - BS-RoFormer + Demucs 체이닝: 6/10 스템 고품질
  - Banquet: 14스템 (현악기, 금관악기, 목관악기, 신디사이저 등)
- **커스텀 쿼리 분리**: 사용자가 원하는 악기 소리를 업로드하여 분리
- **프롬프트 믹싱**: 자연어로 볼륨 조절 ("보컬 키워줘", "드럼 줄여")
- **실시간 진행률**: WebSocket 기반 실시간 상태 업데이트
- **스펙트로그램 시각화**: 각 스템별 스펙트로그램 표시

## 시스템 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| GPU | NVIDIA 8GB VRAM | NVIDIA 12GB+ VRAM |
| RAM | 16GB | 32GB |
| Storage | 50GB | 100GB |
| OS | Ubuntu 20.04+ / Windows WSL2 | Ubuntu 22.04 |

---

## 빠른 시작 (Docker)

### 1. 사전 준비

```bash
# NVIDIA Container Toolkit 설치 (Ubuntu)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# 확인
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

### 2. Banquet 체크포인트 다운로드

```bash
mkdir -p checkpoints
wget -O checkpoints/ev-pre-aug.ckpt \
  https://zenodo.org/records/13694558/files/ev-pre-aug.ckpt
```

### 3. 환경설정

```bash
cp .env.example .env
# 필요시 포트, GPU 설정 등 수정
```

### 4. 빌드 및 실행

```bash
# 이미지 빌드 (최초 1회, ~15분)
docker compose build

# 서비스 시작
docker compose up -d

# 로그 확인
docker compose logs -f
```

### 5. 접속

| 서비스 | URL |
|--------|-----|
| **Frontend** | http://localhost |
| **Backend API** | http://localhost:8000 |
| **API 문서** | http://localhost:8000/docs |

---

## 서비스 관리

```bash
# 시작
docker compose up -d

# 중지
docker compose down

# 재시작
docker compose restart

# 상태 확인
docker compose ps

# 로그 (실시간)
docker compose logs -f backend

# 업데이트
git pull && docker compose build --no-cache && docker compose up -d
```

---

## 환경변수 (.env)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `BACKEND_PORT` | 8000 | 백엔드 포트 |
| `FRONTEND_PORT` | 80 | 프론트엔드 포트 |
| `LOG_LEVEL` | INFO | 로그 레벨 |
| `FILE_TTL_HOURS` | 24 | 파일 보관 시간 |
| `MAX_CONCURRENT_SPLITS` | 1 | 동시 GPU 작업 수 |
| `MAX_UPLOAD_SIZE` | 209715200 | 최대 업로드 크기 (200MB) |
| `BANQUET_BATCH_SIZE` | 1 | Banquet 배치 크기 |
| `ALLOWED_ORIGINS` | localhost | CORS 허용 도메인 |

---

## 프로젝트 구조

```
lukus-mixer/
├── docker/
│   ├── backend.Dockerfile
│   └── frontend.Dockerfile
├── backend/
│   ├── main.py              # FastAPI 엔드포인트
│   ├── demucs_service.py    # 스템 분리 서비스
│   ├── banquet_service.py   # Banquet 쿼리 기반 분리
│   ├── job_store.py         # SQLite 작업 저장소
│   └── tests/               # 테스트 코드
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUpload.tsx
│   │   │   ├── StemSelector.jsx
│   │   │   ├── ResultPanel.tsx
│   │   │   ├── MixingPanel.tsx
│   │   │   └── CustomQueryManager.tsx
│   │   └── App.jsx
│   └── package.json
├── checkpoints/             # Banquet 체크포인트 (수동 다운로드)
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API 엔드포인트

### 파일 업로드 및 분리

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/upload` | 오디오 파일 업로드 |
| POST | `/api/split/{file_id}` | STEM 분리 시작 |
| GET | `/api/job/{job_id}` | 작업 상태 조회 |
| WS | `/ws/job/{job_id}` | 실시간 상태 스트리밍 |

### 결과 다운로드

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/stream/{job_id}/{stem}` | 스템 스트리밍 |
| GET | `/api/download/{job_id}/{stem}` | 스템 다운로드 |
| GET | `/api/download-all/{job_id}` | 전체 ZIP 다운로드 |

### 커스텀 쿼리

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/custom-queries/upload` | 쿼리 오디오 업로드 |
| GET | `/api/custom-queries` | 쿼리 목록 |
| DELETE | `/api/custom-queries/{id}` | 쿼리 삭제 |
| GET | `/api/custom-queries/{id}/stream` | 쿼리 미리듣기 |

### 믹싱

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/mix/{job_id}` | 프롬프트 믹싱 실행 |
| POST | `/api/parse-prompt/{job_id}` | 프롬프트 미리보기 |

---

## 개발 환경 (로컬)

Docker 없이 로컬에서 개발하려면:

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 문제 해결

### GPU 인식 안됨

```bash
# NVIDIA 드라이버 확인
nvidia-smi

# Container Toolkit 재설치
sudo apt-get install --reinstall nvidia-container-toolkit
sudo systemctl restart docker
```

### OOM (메모리 부족)

```bash
# .env 수정
MAX_CONCURRENT_SPLITS=1
BANQUET_BATCH_SIZE=1

docker compose restart backend
```

### 포트 충돌

```bash
# 사용 중인 포트 확인
sudo lsof -i :80
sudo lsof -i :8000

# .env에서 포트 변경
FRONTEND_PORT=8080
BACKEND_PORT=8001
```

---

## 기술 스택

### Backend
- FastAPI, Python 3.10+
- Demucs, BS-RoFormer, Banquet (AI 모델)
- PyTorch CUDA
- SQLite (작업 저장)

### Frontend
- React 18, TypeScript
- Tailwind CSS
- react-dropzone, axios

---

## 라이선스

MIT License

## 참고

- [Demucs](https://github.com/adefossez/demucs) — Meta AI
- [BS-RoFormer](https://github.com/lucidrains/BS-RoFormer) — 고품질 보컬 분리
- [Banquet](https://github.com/kwatcharasupat/query-bandit) — 쿼리 기반 분리 (ISMIR 2024)
