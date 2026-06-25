# Frontend dev-сервер (Vite + React). Для прода нужен отдельный multi-stage
# (npm run build → отдача статики nginx/whitenoise); этот образ — для разработки
# с hot-reload (исходники прокидываются bind-mount'ом из compose).
FROM node:22-alpine

WORKDIR /app

# Сначала только манифесты — слой install кэшируется, пока не менялись зависимости.
# npm install (не ci): lock-файл сгенерён на другой ОС и не содержит alpine/linux
# optional-deps (@emnapi/*, нативные биндинги Vite/oxlint) — ci падал бы на рассинхроне.
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 5173

# --host 0.0.0.0 — чтобы dev-сервер был доступен с хоста (не только из контейнера).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
