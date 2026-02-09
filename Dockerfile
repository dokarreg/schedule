FROM python:3.9

# 1. Встановлюємо необхідні утиліти
RUN apt-get update && apt-get install -y wget gnupg ca-certificates --no-install-recommends

# 2. Додаємо ключ Google Chrome (сучасний спосіб без apt-key)
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg

# 3. Додаємо репозиторій, посилаючись на цей ключ
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# 4. Встановлюємо Chrome
RUN apt-get update && apt-get install -y google-chrome-stable --no-install-recommends

# Далі твій код без змін
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
