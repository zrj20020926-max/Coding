FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN npm ci --registry="$NPM_REGISTRY" --fetch-retries=5 \
    --fetch-retry-mintimeout=2000 --fetch-retry-maxtimeout=60000
COPY . .
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
