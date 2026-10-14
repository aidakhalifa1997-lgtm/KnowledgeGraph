# syntax=docker/dockerfile:1.7
# Image du frontend : compilation Vite puis service statique par nginx (utilisateur non privilégié),
# qui relaie aussi /api vers le backend.
ARG NODE_IMAGE=node:22-bookworm-slim
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.27-alpine

FROM ${NODE_IMAGE} AS build
WORKDIR /src
COPY package.json package-lock.json ./
# Certificat éventuel d'un proxy d'entreprise : utilisé seulement pendant `npm ci`.
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -s /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM ${NGINX_IMAGE} AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=3s --retries=3 CMD wget -q --spider http://127.0.0.1:8080/healthz || exit 1
