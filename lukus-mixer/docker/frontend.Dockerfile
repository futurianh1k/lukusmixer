# ═══════════════════════════════════════════════════
# LUKUS Music Mixer — Frontend (빌드 + nginx 서빙)
# ═══════════════════════════════════════════════════
# 멀티스테이지: Node.js 빌드 → nginx 서빙
# 참고: https://vitejs.dev/guide/static-deploy.html

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# Stage 2: Serve
FROM nginx:1.27-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
