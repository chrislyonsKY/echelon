FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Output stage — copy dist to shared volume
FROM alpine:3.20
WORKDIR /app
COPY --from=builder /app/dist ./build

CMD ["sh", "-c", "cp -r /app/build/* /app/dist/"]
