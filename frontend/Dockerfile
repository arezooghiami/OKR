# OKR web: builds the React app, then nginx serves it and forwards /api to the API container.
ARG NODE_IMAGE=node:24-slim
ARG NGINX_IMAGE=nginx:alpine

FROM ${NODE_IMAGE} AS build
ARG NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --registry "$NPM_REGISTRY"
COPY . .
RUN npm run build

FROM ${NGINX_IMAGE}
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
