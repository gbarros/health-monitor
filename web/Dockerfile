FROM oven/bun:1.3 AS build

WORKDIR /app
COPY web/package.json web/bun.lock ./
RUN bun install --frozen-lockfile
COPY web/index.html web/tsconfig.json web/vite.config.ts ./
COPY web/src ./src
RUN bun run build

FROM nginx:1.27-alpine

COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
