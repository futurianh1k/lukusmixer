# LUKUS Music Mixer — 개발환경 설정 가이드
> **작성일**: 2026-03-06
> **대상 OS**: Ubuntu 24.04 LTS (Noble Numbat)

---

## 1. 현재 개발 환경 사양

### 시스템
| 항목 | 값 |
|---|---|
| **OS** | Ubuntu 24.04.4 LTS (Noble Numbat) |
| **Kernel** | 6.17.0-14-generic |
| **GPU** | NVIDIA GeForce RTX 3070 (8GB VRAM) |
| **GPU Driver** | 590.48.01 |
| **CUDA** | 12.8 |
| **cuDNN** | 9.1.0.02 |

### 런타임
| 항목 | 값 |
|---|---|
| **Python** | 3.13.11 (Miniconda3 base) |
| **Conda** | 25.11.1 |
| **pip** | 25.3 |
| **Node.js** | 20.20.1 |
| **npm** | 10.8.2 |
| **ffmpeg** | 6.1.1 |

### PyTorch
| 항목 | 값 |
|---|---|
| **PyTorch** | 2.10.0+cu128 |
| **torchaudio** | 2.10.0 |
| **torchvision** | 0.25.0 |
| **CUDA available** | True |
| **ONNX Runtime GPU** | 1.24.3 |

---

## 2. Ubuntu 24.04 시스템 패키지

### 필수 시스템 패키지

```bash
# 기본 빌드 도구
sudo apt update
sudo apt install -y build-essential git curl wget

# 오디오 처리 (pydub, librosa, soundfile 의존)
sudo apt install -y ffmpeg libsndfile1 libsoxr0

# Python 관련
sudo apt install -y python3-dev python3-pip
```

### 현재 설치된 관련 패키지

| 패키지 | 버전 | 용도 |
|---|---|---|
| `ffmpeg` | 7:6.1.1-3ubuntu5 | pydub 오디오 변환 (MP3/WAV 인코딩/디코딩) |
| `libsndfile1` | 1.2.2-1ubuntu5 | soundfile/librosa 오디오 파일 I/O |
| `libsoxr0` | 0.1.3-4build3 | 고품질 리샘플링 |
| `nvidia-driver-590-open` | 590.48.01 | NVIDIA GPU 드라이버 |

---

## 3. NVIDIA GPU + CUDA 설정

### 3.1 GPU 드라이버 설치

```bash
# Ubuntu 24.04 기본 리포지토리에서 설치
sudo apt install -y nvidia-driver-590-open

# 설치 확인
nvidia-smi
```

**출력 예시**:
```
NVIDIA GeForce RTX 3070, 590.48.01, 8192 MiB
```

### 3.2 PyTorch + CUDA 설치

> **중요**: pip의 기본 PyTorch는 CPU 전용입니다. CUDA 버전을 명시적으로 설치해야 합니다.

```bash
# CUDA 12.8용 PyTorch 설치 (현재 사용 중인 명령)
pip install torch==2.10.0 torchaudio==2.10.0 torchvision==0.25.0 \
    --index-url https://download.pytorch.org/whl/cu128
```

**CUDA 버전별 설치 명령**:

| CUDA 버전 | 설치 명령 |
|---|---|
| CUDA 12.8 | `--index-url https://download.pytorch.org/whl/cu128` |
| CUDA 12.4 | `--index-url https://download.pytorch.org/whl/cu124` |
| CUDA 12.1 | `--index-url https://download.pytorch.org/whl/cu121` |
| CPU 전용 | `--index-url https://download.pytorch.org/whl/cpu` |

**CUDA 동작 확인**:
```bash
python3 -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
print(f'GPU: {torch.cuda.get_device_name(0)}')
"
```

### 3.3 ONNX Runtime GPU 설치

audio-separator(BS-RoFormer)가 ONNX Runtime GPU를 사용합니다:

```bash
pip install onnxruntime-gpu==1.24.3
```

---

## 4. Python 환경 설정

### 4.1 Miniconda 설치 (선택, 현재 사용 중)

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
source ~/.bashrc
```

### 4.2 패키지 설치 순서

> **순서가 중요합니다.** PyTorch를 먼저 CUDA 버전으로 설치한 후 나머지를 설치해야 합니다.

```bash
# Step 1: PyTorch + CUDA (반드시 먼저)
pip install torch==2.10.0 torchaudio==2.10.0 torchvision==0.25.0 \
    --index-url https://download.pytorch.org/whl/cu128

# Step 2: LUKUS Mixer 패키지 전체 설치
pip install -r requirements_lukus_mixer.txt

# Step 3: audio-separator GPU 지원 (Step 2에서 포함되지만 별도 확인)
pip install audio-separator[gpu]==0.41.1
```

### 4.3 설치 검증

```bash
python3 -c "
import torch
import demucs
from audio_separator.separator import Separator
import librosa
import pydub
import fastapi
import matplotlib

print('✅ PyTorch:', torch.__version__, '| CUDA:', torch.cuda.is_available())
print('✅ Demucs:', demucs.__version__)
print('✅ audio-separator: OK')
print('✅ librosa:', librosa.__version__)
print('✅ FastAPI:', fastapi.__version__)
print('✅ 모든 패키지 정상')
"
```

---

## 5. Node.js / Frontend 환경

### 5.1 Node.js 설치

```bash
# nvm으로 설치 (권장)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
```

### 5.2 Frontend 패키지 설치

```bash
cd lukus-mixer/frontend
npm install
```

### 5.3 현재 Frontend 의존성 (`package.json`)

| 패키지 | 버전 | 용도 |
|---|---|---|
| react / react-dom | ^18.2.0 | UI 프레임워크 |
| vite | ^5.0.0 | 빌드 도구 |
| tailwindcss | ^3.4.0 | CSS 프레임워크 |
| react-dropzone | ^14.2.3 | 파일 드래그&드롭 업로드 |
| lucide-react | ^0.300.0 | 아이콘 |
| axios | ^1.6.0 | HTTP 클라이언트 |

---

## 6. 실행 명령

### 백엔드

```bash
cd lukus-mixer/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 개발 모드 (자동 리로드)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 프론트엔드

```bash
cd lukus-mixer/frontend
npm run dev
# → http://localhost:3000
```

### 접속

| 서비스 | URL |
|---|---|
| 프론트엔드 | http://localhost:3000 |
| 백엔드 API | http://localhost:8000 |
| API 문서 (Swagger) | http://localhost:8000/docs |

---

## 7. 프로젝트에서 실행한 설치 명령 기록

아래는 이 프로젝트 개발 과정에서 실제로 실행한 설치 명령들입니다:

```bash
# 1. Demucs 설치
pip install -U demucs

# 2. FastAPI + 웹 서버
pip install fastapi uvicorn[standard] python-multipart pydantic

# 3. 오디오 처리
pip install librosa pydub matplotlib

# 4. audio-separator (BS-RoFormer 체이닝 엔진) — Phase 1에서 추가
pip install audio-separator[gpu]

# 5. Frontend
cd lukus-mixer/frontend && npm install
```

---

## 8. 트러블슈팅

### PyTorch CUDA가 인식되지 않을 때

```bash
# CPU 버전이 설치되었는지 확인
python3 -c "import torch; print(torch.__version__)"
# 출력이 "2.10.0" (cu128 없음)이면 CPU 버전

# 해결: CUDA 버전으로 재설치
pip uninstall torch torchaudio torchvision -y
pip install torch==2.10.0 torchaudio==2.10.0 torchvision==0.25.0 \
    --index-url https://download.pytorch.org/whl/cu128
```

### ffmpeg 누락으로 pydub 오류 발생

```bash
# 증상: pydub.exceptions.CouldntDecodeError
sudo apt install -y ffmpeg
```

### libsndfile 누락으로 soundfile 오류 발생

```bash
# 증상: OSError: sndfile library not found
sudo apt install -y libsndfile1
```

### NVIDIA 드라이버 설치 후 GPU 인식 안 됨

```bash
# 재부팅 필요
sudo reboot

# 드라이버 확인
nvidia-smi
```

### audio-separator 모델 다운로드 경로

모델 가중치는 처음 사용 시 자동 다운로드되며, 기본 저장 경로:
```
~/.cache/audio-separator/
```

| 모델 | 크기 |
|---|---|
| `model_bs_roformer_ep_317_sdr_12.9755.ckpt` | ~639MB |
| `htdemucs_6s` | ~80MB |

---

## 9. Conda 환경 정보

| 환경 | Python | 용도 |
|---|---|---|
| `base` (현재 사용) | 3.13.11 | LUKUS Mixer 개발 |
| `py312` | 3.12.x | 기타 |
| `songgen_env` | - | SongGen 프로젝트 |
