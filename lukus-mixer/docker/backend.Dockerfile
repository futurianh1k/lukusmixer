# ═══════════════════════════════════════════════════
# LUKUS Music Mixer — Backend (GPU)
# ═══════════════════════════════════════════════════
# 빌드:
#   docker compose build backend
# 실행:
#   docker compose up backend
#
# 참고:
#   - NVIDIA Container Toolkit 필요: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/
#   - PyTorch CUDA 이미지 기반: https://hub.docker.com/r/pytorch/pytorch

FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir audio-separator[gpu] onnxruntime-gpu

COPY backend/ .

ENV LOG_LEVEL=INFO \
    LUKUS_DATA_DIR=/data \
    FILE_TTL_HOURS=24 \
    MAX_CONCURRENT_SPLITS=1 \
    ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

VOLUME ["/data"]

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
