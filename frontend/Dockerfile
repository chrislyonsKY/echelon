FROM node:20-alpine AS builder

ARG VITE_ESRI_API_KEY=""
ENV VITE_ESRI_API_KEY=$VITE_ESRI_API_KEY

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --prefer-offline

COPY . .
RUN npm run build

# Output stage — copy dist to shared volume
FROM alpine:3.20
WORKDIR /app
COPY --from=builder /app/dist ./build

CMD ["sh", "-c", "cp -r /app/build/* /app/dist/"]
