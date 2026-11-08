# syntax=docker/dockerfile:1

# ---- Stage 1: build the React app ----------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- Stage 2: static files served by unprivileged nginx on :8080 ---------------
FROM nginxinc/nginx-unprivileged:1.27-alpine
# /api is proxied to the Laravel API. API_UPSTREAM is substituted at container start.
ENV API_UPSTREAM=api:8080
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
