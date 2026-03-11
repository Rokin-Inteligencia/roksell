FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Build (variáveis de build podem ser passadas via build-arg se necessário)
RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]
