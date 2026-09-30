FROM node:26-alpine3.23 AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

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
