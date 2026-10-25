FROM node:22-alpine AS build
WORKDIR /site
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY deployment/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /site/dist/ /srv/
