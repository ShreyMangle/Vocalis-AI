FROM node:20-alpine

WORKDIR /app

# Copy package files first (layer caching — same as backend Dockerfile)
COPY package*.json ./
RUN npm install

# Copy source (mounted as volume in dev, so this is mainly for production builds)
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
