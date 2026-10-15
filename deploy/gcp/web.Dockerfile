# DeploySmith frontend for Google Cloud Run: a static Vite build served by nginx.
# Build from the repository root; the API URL is baked in at build time:
#   docker build -f deploy/gcp/web.Dockerfile --build-arg VITE_API_URL=https://... -t deploysmith-web .

FROM node:22-alpine AS build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend ./
ARG VITE_API_URL
RUN test -n "$VITE_API_URL" || (echo "VITE_API_URL build arg is required" && exit 1)
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
# The official image renders /etc/nginx/templates/*.template with envsubst at start,
# so nginx listens on Cloud Run's $PORT.
ENV PORT=8080
COPY deploy/gcp/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /src/frontend/dist /usr/share/nginx/html
EXPOSE 8080
