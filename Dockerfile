FROM python:3.12-slim

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
    libu2f-udev \
    libvulkan1 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

RUN pip install playwright
RUN playwright install --with-deps chromium

COPY . .

CMD ["python", "main.py"]