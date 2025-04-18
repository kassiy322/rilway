FROM python:3.12-slim

# Устанавливаем системные зависимости для Playwright и glibc
RUN apt-get update && apt-get install -y \
    libc6 \
    libstdc++6 \
    curl \
    wget \
    unzip \
    xvfb \
    libnss3 \
    libxss1 \
    libasound2 \
    fonts-liberation \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Устанавливаем Playwright и необходимые браузеры
RUN pip install playwright
RUN playwright install --with-deps chromium

# Копируем исходный код
COPY . .

# Запуск приложения
CMD ["python", "main.py"]
