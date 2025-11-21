# Stage 1: Build the React.js Application
# Taken from : https://docs.docker.com/guides/reactjs/containerize/#overview
ARG NODE_VERSION=22.14.0-alpine
ARG NGINX_VERSION=alpine3.21

FROM node:${NODE_VERSION} AS builder

WORKDIR /app

COPY package.json package-lock.json ./

RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .

RUN npm run build

# Stage 2: Prepare Nginx to Serve Static Files

FROM nginx:${NGINX_VERSION} AS runner

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/build /usr/share/nginx/html

COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]

# Below is now in entrypoint.sh could be moved back here if needed
# CMD ["nginx", "-g", "daemon off;"]
