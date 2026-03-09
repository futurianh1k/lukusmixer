# CHANGELOG — 2026-03-09 P2 보완 구현

> **작업 유형**: UX 개선 + 인프라 + 코드 품질 (P2)
> **이전 작업**: P0 보안 + P1 아키텍처 완료 후 진행

---

## 변경 요약

### 1. Toast 알림 도입 (P2-1)
- **파일**: `frontend/src/App.jsx`, `frontend/src/components/MixingPanel.jsx`
- **패키지**: `react-hot-toast` 추가
- **내용**:
  - 모든 `alert()` 호출을 `toast.success()` / `toast.error()`로 교체 (총 8곳)
  - 다크 테마 스타일 Toast (`#1e293b` 배경, `#334155` 테두리)
  - 성공 알림 4초, 에러 알림 6초 자동 사라짐
  - 비차단식 — 토스트가 떠도 UI 조작 가능
- **참고**: react-hot-toast — https://react-hot-toast.com/

### 2. Error Boundary 추가 (P2-2)
- **파일**: `frontend/src/components/ErrorBoundary.jsx` (신규)
- **내용**:
  - React Class Component 기반 Error Boundary
  - `ResultPanel`과 `MixingPanel`을 각각 감싸서 개별 크래시 격리
  - 폴백 UI: 경고 아이콘 + "다시 시도" 버튼
  - `name` prop으로 에러 발생 위치 표시

### 3. Docker 컨테이너화 (P2-3)
- **파일**: `docker-compose.yml`, `docker/backend.Dockerfile`, `docker/frontend.Dockerfile`, `docker/nginx.conf`, `.dockerignore` (모두 신규)
- **내용**:
  - **백엔드**: `pytorch/pytorch:2.5.1-cuda12.4` 기반, ffmpeg + libsndfile 포함
  - **프론트엔드**: Node.js 멀티스테이지 빌드 → nginx:1.27-alpine 서빙
  - **nginx**: `/api/` → 백엔드 프록시, `/ws/` → WebSocket 프록시, SPA fallback
  - `docker compose up -d` 한 줄로 전체 서비스 시작
  - GPU 지원 (NVIDIA Container Toolkit), 볼륨 분리 (data, models)
  - 헬스체크 포함
- **참고**: NVIDIA Container Toolkit — https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/

### 4. WebSocket 실시간 로그 (P2-4)
- **백엔드**: `backend/main.py`
  - `@app.websocket("/ws/job/{job_id}")` 엔드포인트 추가
  - `_ws_subscribers` 딕셔너리로 연결 관리
  - `_update_job()` 호출 시 `_notify_ws()`로 구독자에게 즉시 push
  - 연결 시 현재 상태 즉시 전송
- **프론트엔드**: `frontend/src/hooks/useJobWebSocket.js` (신규)
  - WebSocket 연결 → 실시간 상태 수신
  - 재연결 3회 시도 후 HTTP 폴링으로 자동 폴백
  - `App.jsx`에서 기존 `setInterval` 폴링 완전 제거
- **Vite**: `vite.config.js`에 `/ws` 프록시 추가
- **참고**: FastAPI WebSocket — https://fastapi.tiangolo.com/advanced/websockets/

### 5. TypeScript 기반 구축 (P2-5)
- **파일**: `frontend/tsconfig.json`, `frontend/src/types/api.ts` (모두 신규)
- **내용**:
  - `tsconfig.json`: `allowJs: true`로 점진적 마이그레이션 가능
  - `api.ts`: 백엔드 Pydantic 모델과 1:1 대응하는 TypeScript 인터페이스
    - `ModelInfo`, `SystemInfo`, `UploadResponse`, `StemResult`, `JobStatus`
    - `MixCommand`, `MixResponse`, `UploadedFile`, `ExpandedMix`, `WsJobUpdate`
  - TypeScript, `@types/node` devDependencies 추가
- **마이그레이션 가이드**: `.jsx` 파일을 하나씩 `.tsx`로 변환하면서 `api.ts` 타입 import

### 6. 반응형 디자인 (P2-6)
- **파일**: `frontend/src/App.jsx`
- **내용**:
  - **lg (1024px) 이상**: 기존 3컬럼 레이아웃 유지
  - **lg 미만**: 설정/결과/믹싱 탭 전환 방식
  - 탭 바: 하단 주황색 인디케이터로 현재 탭 표시
  - 사이드바: `hidden lg:block`으로 모바일에서 숨김
  - 패널 콘텐츠를 변수로 추출하여 데스크톱/모바일 양쪽에서 재사용

---

## 검증 결과

### 백엔드 테스트
```
79 passed in 3.55s (0 warnings)
```

### 프론트엔드 빌드
```
✓ 1468 modules transformed
✓ built in 1.90s
dist/assets/index-BYf7_aYu.js   315.28 kB │ gzip: 100.57 kB
```

---

## 신규 파일 목록

| 파일 | 유형 | 설명 |
|------|------|------|
| `frontend/src/components/ErrorBoundary.jsx` | 프론트 | Error Boundary 컴포넌트 |
| `frontend/src/hooks/useJobWebSocket.js` | 프론트 | WebSocket 훅 (폴링 폴백 포함) |
| `frontend/src/types/api.ts` | 프론트 | API 타입 정의 |
| `frontend/tsconfig.json` | 설정 | TypeScript 설정 |
| `docker-compose.yml` | 인프라 | Docker Compose 정의 |
| `docker/backend.Dockerfile` | 인프라 | 백엔드 GPU 이미지 |
| `docker/frontend.Dockerfile` | 인프라 | 프론트 멀티스테이지 빌드 |
| `docker/nginx.conf` | 인프라 | nginx 리버스 프록시 |
| `.dockerignore` | 설정 | Docker 빌드 제외 목록 |

---

## 참고 출처
- react-hot-toast: https://react-hot-toast.com/
- React Error Boundary: https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary
- FastAPI WebSocket: https://fastapi.tiangolo.com/advanced/websockets/
- Docker Compose: https://docs.docker.com/compose/
- NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/
- Vite Static Deploy: https://vitejs.dev/guide/static-deploy.html
