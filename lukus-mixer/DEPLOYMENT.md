# LUKUS Music Mixer — 배포 가이드

## 목차
1. [요구사항](#요구사항)
2. [빠른 시작](#빠른-시작)
3. [상세 설정](#상세-설정)
4. [운영 가이드](#운영-가이드)
5. [프로덕션 배포](#프로덕션-배포)
6. [문제 해결](#문제-해결)

---

## 요구사항

### 하드웨어

| 항목 | 최소 | 권장 |
|------|------|------|
| **GPU** | NVIDIA 8GB VRAM | NVIDIA 12GB+ VRAM |
| **RAM** | 16GB | 32GB |
| **Storage** | 50GB SSD | 100GB+ NVMe |
| **CPU** | 4 cores | 8+ cores |

### 소프트웨어

| 소프트웨어 | 버전 | 설치 확인 |
|-----------|------|----------|
| Docker | 24.0+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| NVIDIA Driver | 535+ | `nvidia-smi` |
| NVIDIA Container Toolkit | 최신 | `docker run --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi` |

---

## 빠른 시작

### Step 1: NVIDIA Container Toolkit 설치

**Ubuntu 20.04 / 22.04:**

```bash
# GPG 키 및 저장소 추가
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 설치
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 확인
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

**Windows (WSL2):**

```powershell
# Windows에서 WSL2 + NVIDIA GPU 드라이버 설치 후
# WSL2 Ubuntu에서 위 명령어 실행
```

### Step 2: 프로젝트 클론

```bash
git clone https://github.com/futurianh1k/lukusmixer.git
cd lukusmixer/lukus-mixer
```

### Step 3: Banquet 체크포인트 다운로드

```bash
# checkpoints 폴더 생성
mkdir -p checkpoints

# Zenodo에서 다운로드 (~500MB)
wget -O checkpoints/ev-pre-aug.ckpt \
  "https://zenodo.org/records/13694558/files/ev-pre-aug.ckpt?download=1"

# 다운로드 확인
ls -lh checkpoints/
# ev-pre-aug.ckpt  약 500MB
```

> **참고**: 14스템 분리(Banquet) 기능을 사용하지 않으면 이 단계를 건너뛸 수 있습니다.

### Step 4: 환경변수 설정

```bash
# 환경변수 파일 복사
cp .env.example .env

# 필요에 따라 수정
nano .env
```

**주요 설정:**

```bash
# 포트 (기본값 권장)
BACKEND_PORT=8000
FRONTEND_PORT=80

# GPU 설정 (8GB VRAM 기준)
MAX_CONCURRENT_SPLITS=1
BANQUET_BATCH_SIZE=1

# 파일 관리
FILE_TTL_HOURS=24
MAX_UPLOAD_SIZE=209715200  # 200MB
```

### Step 5: 빌드 및 실행

```bash
# 이미지 빌드 (최초 1회, 10-15분 소요)
docker compose build

# 서비스 시작 (백그라운드)
docker compose up -d

# 로그 확인
docker compose logs -f

# 헬스체크 확인 (~60초 대기)
docker compose ps
```

### Step 6: 접속 확인

| 서비스 | URL | 설명 |
|--------|-----|------|
| **Frontend** | http://localhost | 웹 UI |
| **Backend API** | http://localhost:8000 | REST API |
| **API 문서** | http://localhost:8000/docs | Swagger UI |

---

## 상세 설정

### GPU 메모리 최적화

**8GB VRAM (RTX 3070/4070 등):**

```bash
# .env
MAX_CONCURRENT_SPLITS=1
BANQUET_BATCH_SIZE=1
```

**12GB+ VRAM (RTX 3080/4080/A5000 등):**

```bash
# .env
MAX_CONCURRENT_SPLITS=2
BANQUET_BATCH_SIZE=2
```

**24GB+ VRAM (RTX 4090/A6000 등):**

```bash
# .env
MAX_CONCURRENT_SPLITS=3
BANQUET_BATCH_SIZE=3
```

### 파일 보관 정책

```bash
# .env
FILE_TTL_HOURS=24              # 24시간 후 자동 삭제
CLEANUP_INTERVAL_MINUTES=30    # 30분마다 정리 실행
```

### 업로드 용량 제한

```bash
# .env
MAX_UPLOAD_SIZE=209715200      # 200MB (기본)
MAX_UPLOAD_SIZE=524288000      # 500MB
MAX_UPLOAD_SIZE=1073741824     # 1GB
```

### 커스텀 쿼리 설정

```bash
# .env (기본값)
MAX_QUERY_SIZE=20971520        # 20MB
MAX_QUERY_DURATION=30          # 30초
```

---

## 운영 가이드

### 서비스 관리

```bash
# 시작
docker compose up -d

# 중지
docker compose down

# 재시작
docker compose restart

# 백엔드만 재시작
docker compose restart backend

# 상태 확인
docker compose ps

# 리소스 사용량
docker stats
```

### 로그 관리

```bash
# 전체 로그 (실시간)
docker compose logs -f

# 백엔드 로그만
docker compose logs -f backend

# 최근 500줄
docker compose logs --tail 500 backend

# 시간대별 로그
docker compose logs --since "2024-01-01T00:00:00" backend
```

### 업데이트

```bash
# 1. 코드 업데이트
git pull

# 2. 이미지 재빌드
docker compose build --no-cache

# 3. 서비스 재시작
docker compose down && docker compose up -d
```

### 볼륨 관리

```bash
# 볼륨 목록
docker volume ls | grep lukus

# 볼륨 상세 정보
docker volume inspect lukus-mixer-data

# 데이터 백업
docker run --rm \
  -v lukus-mixer-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar cvf /backup/lukus-data-$(date +%Y%m%d).tar /data

# 볼륨 삭제 (주의: 모든 데이터 삭제)
docker compose down -v
```

### 모델 캐시 관리

```bash
# 모델 캐시 용량 확인
docker exec lukus-backend du -sh /root/.cache

# 캐시 정리 (필요시)
docker exec lukus-backend rm -rf /root/.cache/torch/hub/*
```

---

## 프로덕션 배포

### 체크리스트

- [ ] NVIDIA Container Toolkit 설치 완료
- [ ] Banquet 체크포인트 다운로드 완료
- [ ] `.env` 파일 설정 완료
- [ ] 방화벽 포트 개방 (80, 443)
- [ ] SSL/TLS 인증서 준비
- [ ] 도메인 설정 완료
- [ ] 리버스 프록시 설정 (Nginx/Traefik)
- [ ] 로그 로테이션 설정
- [ ] 모니터링 설정
- [ ] 백업 정책 수립

### CORS 설정

```bash
# .env - 프로덕션 도메인 설정
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Nginx 리버스 프록시 (예시)

```nginx
# /etc/nginx/sites-available/lukus-mixer

upstream lukus_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://lukus_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # 대용량 업로드
        client_max_body_size 200M;
        proxy_read_timeout 300s;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://lukus_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

### Docker Compose 프로덕션 오버라이드

```yaml
# docker-compose.prod.yml
services:
  backend:
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "5"

  frontend:
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"
```

```bash
# 프로덕션 실행
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### systemd 서비스 등록 (선택)

```ini
# /etc/systemd/system/lukus-mixer.service
[Unit]
Description=LUKUS Music Mixer
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/lukus-mixer
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable lukus-mixer
sudo systemctl start lukus-mixer
```

---

## 문제 해결

### GPU 인식 안됨

```bash
# 1. NVIDIA 드라이버 확인
nvidia-smi

# 2. Docker 내 GPU 확인
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi

# 3. Container Toolkit 재설치
sudo apt-get install --reinstall nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### OOM (Out of Memory) 오류

```bash
# 1. GPU 메모리 상태 확인
nvidia-smi

# 2. 배치 크기 줄이기
# .env 수정
BANQUET_BATCH_SIZE=1
MAX_CONCURRENT_SPLITS=1

# 3. 서비스 재시작
docker compose restart backend
```

### 빌드 실패

```bash
# 1. 캐시 삭제 후 재빌드
docker compose build --no-cache

# 2. Docker 시스템 정리
docker system prune -f
docker builder prune -f

# 3. 재빌드
docker compose build
```

### 포트 충돌

```bash
# 1. 사용 중인 포트 확인
sudo lsof -i :80
sudo lsof -i :8000

# 2. .env에서 포트 변경
FRONTEND_PORT=8080
BACKEND_PORT=8001

# 3. 서비스 재시작
docker compose down && docker compose up -d
```

### WebSocket 연결 실패

```bash
# 1. 프록시 설정 확인 (Nginx)
# WebSocket 업그레이드 헤더 필요

# 2. 방화벽 확인
sudo ufw allow 8000/tcp

# 3. 컨테이너 로그 확인
docker compose logs backend | grep -i websocket
```

### Banquet 모델 로드 실패

```bash
# 1. 체크포인트 파일 확인
ls -lh checkpoints/ev-pre-aug.ckpt
# 약 500MB여야 함

# 2. 볼륨 마운트 확인
docker exec lukus-backend ls -la /app/query_bandit/checkpoints/

# 3. 로그 확인
docker compose logs backend | grep -i banquet
```

---

## 지원

- **이슈 리포트**: GitHub Issues
- **문서**: https://github.com/futurianh1k/lukusmixer
