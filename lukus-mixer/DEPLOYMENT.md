# LUKUS Music Mixer — 배포 가이드

## 요구사항

### 하드웨어
- **GPU**: NVIDIA GPU (VRAM 8GB 이상 권장)
- **RAM**: 16GB 이상
- **Storage**: 50GB 이상 (모델 캐시 포함)

### 소프트웨어
- Docker 24.0+
- Docker Compose 2.20+
- NVIDIA Container Toolkit

---

## 빠른 시작

### 1. NVIDIA Container Toolkit 설치 (Ubuntu)

```bash
# 저장소 추가
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# 설치
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# 확인
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

### 2. Banquet 체크포인트 다운로드

```bash
mkdir -p checkpoints
cd checkpoints

# Zenodo에서 다운로드 (약 500MB)
# https://zenodo.org/records/13694558
wget https://zenodo.org/records/13694558/files/ev-pre-aug.ckpt

cd ..
```

### 3. 환경설정

```bash
# 환경변수 파일 생성
cp .env.example .env

# 필요시 수정 (포트, GPU 설정 등)
vim .env
```

### 4. 빌드 및 실행

```bash
# 이미지 빌드 (최초 1회, 약 10-15분 소요)
docker compose build

# 서비스 시작
docker compose up -d

# 로그 확인
docker compose logs -f
```

### 5. 접속

- **Frontend**: http://localhost (또는 설정한 포트)
- **Backend API**: http://localhost:8000

---

## 상세 설정

### GPU 메모리 최적화 (8GB VRAM)

```bash
# .env 파일 설정
MAX_CONCURRENT_SPLITS=1  # 동시 작업 1개
BANQUET_BATCH_SIZE=1     # Banquet 배치 크기 1
```

### 파일 보관 정책

```bash
# .env 파일 설정
FILE_TTL_HOURS=24           # 24시간 후 자동 삭제
CLEANUP_INTERVAL_MINUTES=30  # 30분마다 정리
```

### 업로드 용량 제한

```bash
# .env 파일 설정
MAX_UPLOAD_SIZE=209715200  # 200MB
```

### CORS 설정 (운영 환경)

```bash
# .env 파일 설정
ALLOWED_ORIGINS=https://yourdomain.com
```

---

## 운영 명령어

### 서비스 관리

```bash
# 시작
docker compose up -d

# 중지
docker compose down

# 재시작
docker compose restart

# 상태 확인
docker compose ps
```

### 로그 확인

```bash
# 전체 로그
docker compose logs -f

# 백엔드 로그만
docker compose logs -f backend

# 최근 100줄
docker compose logs --tail 100 backend
```

### 업데이트

```bash
# 코드 업데이트 후
git pull

# 이미지 재빌드
docker compose build --no-cache

# 서비스 재시작
docker compose down && docker compose up -d
```

### 볼륨 관리

```bash
# 볼륨 목록
docker volume ls | grep lukus

# 데이터 백업 (선택)
docker run --rm -v lukus-mixer-data:/data -v $(pwd):/backup alpine \
  tar cvf /backup/lukus-data-backup.tar /data

# 볼륨 삭제 (주의: 모든 데이터 삭제됨)
docker compose down -v
```

---

## 문제 해결

### GPU를 인식하지 못하는 경우

```bash
# NVIDIA 드라이버 확인
nvidia-smi

# Container Toolkit 재설치
sudo apt-get install --reinstall nvidia-container-toolkit
sudo systemctl restart docker
```

### OOM (Out of Memory) 오류

```bash
# .env 수정
BANQUET_BATCH_SIZE=1
MAX_CONCURRENT_SPLITS=1

# 서비스 재시작
docker compose restart backend
```

### 빌드 실패

```bash
# 캐시 삭제 후 재빌드
docker compose build --no-cache

# 또는 전체 정리 후 재시작
docker system prune -f
docker compose build
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

## 프로덕션 배포 체크리스트

- [ ] NVIDIA Container Toolkit 설치 확인
- [ ] Banquet 체크포인트 다운로드 완료
- [ ] `.env` 파일 설정 완료
- [ ] `ALLOWED_ORIGINS` 도메인 설정
- [ ] 방화벽 포트 개방 (80, 443)
- [ ] SSL/TLS 인증서 설정 (리버스 프록시 권장)
- [ ] 로그 로테이션 설정
- [ ] 백업 정책 수립
