# ═══════════════════════════════════════════════════
# LUKUS Music Mixer — Backend (GPU)
# ═══════════════════════════════════════════════════
# 빌드:
#   docker compose build backend
# 실행:
#   docker compose up backend
#
# 참고:
#   - NVIDIA Container Toolkit 필요
#   - PyTorch CUDA 이미지 기반
#   - Banquet 체크포인트는 볼륨 마운트 또는 수동 다운로드 필요:
#     https://zenodo.org/records/13694558

FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치 (캐시 활용을 위해 requirements.txt 먼저)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir audio-separator[gpu] onnxruntime-gpu

# hear21passt (Banquet 의존성) - GitHub에서 직접 설치
RUN pip install --no-cache-dir git+https://github.com/kkoutini/passt_hear21.git

# 소스코드 복사
COPY backend/ .

# query_bandit 서브모듈이 있는 경우 복사 (체크포인트 제외)
# 체크포인트는 볼륨 마운트로 제공해야 함

# 환경변수 설정
ENV LOG_LEVEL=INFO \
    LUKUS_DATA_DIR=/data \
    FILE_TTL_HOURS=24 \
    CLEANUP_INTERVAL_MINUTES=30 \
    MAX_CONCURRENT_SPLITS=1 \
    MAX_UPLOAD_SIZE=209715200 \
    BANQUET_BATCH_SIZE=1 \
    ALLOWED_ORIGINS=http://localhost:3000,http://localhost:80

# 데이터 및 모델 캐시 볼륨
VOLUME ["/data", "/root/.cache"]

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
