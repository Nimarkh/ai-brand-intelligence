# Frontend image targets:
#   development — Angular dev server (used by docker-compose.yml)
#   production  — static nginx SPA (used by docker-compose.prod.yml)

# ---- shared deps ----
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- development (ng serve) ----
FROM deps AS development
WORKDIR /app
COPY . .
EXPOSE 4200
# Compose service name. Host `npm start` does not use this image.
ENV API_PROXY_TARGET=http://backend:8000
CMD ["npm", "start", "--", "--host", "0.0.0.0", "--port", "4200"]

# ---- production build ----
FROM deps AS build
WORKDIR /app
COPY . .
RUN npm run build

# ---- production runtime ----
FROM nginxinc/nginx-unprivileged:1.27-alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
