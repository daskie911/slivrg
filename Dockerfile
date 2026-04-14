FROM python:3.11-slim

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Создаём необходимые папки
RUN mkdir -p data logs

# Запускаем бота
CMD ["python", "main.py"]
