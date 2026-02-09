# Використовуємо офіційний Python образ (slim версія для меншого розміру)
FROM python:3.9-slim

# Встановлюємо змінні оточення
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Встановлюємо системні залежності для Chrome та Selenium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Встановлюємо Google Chrome Stable
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Встановлюємо робочу директорію
WORKDIR /app

# Копіюємо файл залежностей та встановлюємо їх
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код програм
# УВАГА: Ми перейменовуємо файл на main.py для зручності запуску
COPY "main (7).py" main.py

# Створюємо користувача non-root для безпеки (опціонально, але бажано для Render)
RUN useradd -m myuser
USER myuser

# Запускаємо сервер
# Render автоматично передає порт через змінну PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
