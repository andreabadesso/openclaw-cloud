FROM node:20-alpine

WORKDIR /app

COPY apps/token-proxy/package.json apps/token-proxy/package-lock.json* ./
RUN npm ci --production

COPY apps/token-proxy/src/ src/

ENV PORT=8080
EXPOSE 8080

CMD ["node", "src/server.js"]
