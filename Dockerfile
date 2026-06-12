# Используем тот же официальный образ Python
FROM python:3.13-slim-bookworm

# Устанавливаем рабочую директорию
WORKDIR /app

# Сначала копируем ТОЛЬКО файл с зависимостями
# Это критически важно для кэширования Docker
COPY requirements.txt .

# Устанавливаем пакеты один раз на этапе сборки образа
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код проекта
COPY . .