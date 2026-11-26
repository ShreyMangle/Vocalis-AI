# =============================================================================
# Stage 1: Build Frontend Assets
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package descriptors first for Docker layer caching
COPY package*.json ./
RUN npm install

# Copy source code and build production bundle
COPY . .
RUN npm run build

# =============================================================================
# Stage 2: Production Nginx Server
# =============================================================================
FROM nginx:alpine AS runtime

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled SPA dist from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration with reverse proxy & WebSocket upgrade
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
