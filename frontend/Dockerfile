FROM node:26-alpine3.23 AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL
ARG VITE_LOGODEV_TOKEN

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_LOGODEV_TOKEN=$VITE_LOGODEV_TOKEN

RUN npm run build

FROM caddy:2.11.4-alpine

COPY --from=build /app/dist /srv/frontend

COPY <<EOF /etc/caddy/Caddyfile
:80 {
    root * /srv/frontend
    file_server
    try_files {path} /index.html
}
EOF
