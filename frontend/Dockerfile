# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files and install dependencies
COPY package.json ./
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

# Serve stage
FROM node:18-alpine

WORKDIR /app

# Install serve and curl (for health check)
RUN apk add --no-cache curl && \
    npm install -g serve@14.2.1

# Copy built files
COPY --from=builder /app/build ./build

EXPOSE 3000

# Health check with proper startup period
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/ || exit 1

# Start server with host binding
CMD ["serve", "-s", "build", "--listen", "3000", "--single"]