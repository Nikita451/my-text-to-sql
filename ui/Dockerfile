# Используем тот же официальный образ Node.js
FROM node:22-slim

WORKDIR /app

# Кэшируем установку зависимостей Node.js
COPY package.json package-lock.json* ./

# Устанавливаем пакеты один раз при сборке образа
RUN npm install

# Копируем исходный код фронтенда
COPY . .
