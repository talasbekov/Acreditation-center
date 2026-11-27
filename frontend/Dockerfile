# Development server. Dockerfile.release builds the TLS-served static application.
FROM node:22-alpine@sha256:1314fb30ec37592d5845e5a160d522c0e680972aa534549940b8d73bde88481a

WORKDIR /app

# Сначала только манифесты — слой install кэшируется, пока не менялись зависимости.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

EXPOSE 5173

# --host 0.0.0.0 — чтобы dev-сервер был доступен с хоста (не только из контейнера).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
