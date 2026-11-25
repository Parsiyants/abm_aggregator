# ─── Этап 1: сборка Vue-приложения ─────────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

# Сначала только манифесты — слой с зависимостями кэшируется
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Значения по умолчанию можно переопределить при сборке:
#   docker build --build-arg VITE_API_URL=/api/v1 -t frontend .
ARG VITE_API_URL=/api/v1
ARG VITE_WS_URL=
ENV VITE_API_URL=${VITE_API_URL} \
    VITE_WS_URL=${VITE_WS_URL}

RUN npm run build

# ─── Этап 2: раздача статики через nginx ───────────────────────────────────
FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3005

CMD ["nginx", "-g", "daemon off;"]

