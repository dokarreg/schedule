from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import re

app = FastAPI()

class LoginData(BaseModel):
    username: str
    password: str

# Допоміжна функція для очищення тексту
def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def parse_schedule_html(html_content, week_label):
    soup = BeautifulSoup(html_content, 'html.parser')
    schedule_data = []

    # Знаходимо грід розкладу
    # Орієнтуємось на класи, які були в JS скрипті: .schedule-grid
    grid = soup.find(class_="schedule-grid")
    if not grid:
        return []

    # Знаходимо заголовки днів (дати)
    # Припускаємо, що це .grid-header-row або перший рядок
    header_row = grid.find(class_="grid-header-row")
    if not header_row:
        # Fallback: можливо заголовки просто перші елементи
        pass 

    # Отримуємо дати для кожного стовпчика (крім першого - там час)
    day_columns = []
    if header_row:
        cols = header_row.find_all("div", recursive=False) # Діти рядка
        # Перший стовпчик - пустий або "Час", пропускаємо
        for i, col in enumerate(cols[1:], 1): # Починаємо з 1
            text = clean_text(col.get_text())
            # Текст типу "Понеділок 23.10"
            day_columns.append(text)
    
    # Якщо дат немає, створимо заглушки
    if not day_columns:
        day_columns = [f"День {i}" for i in range(1, 6)]

    # Ініціалізуємо структуру для кожного дня
    days_map = {}
    for day_name in day_columns:
        days_map[day_name] = {
            "day_name": day_name,
            "date": week_label, # Можна витягнути з day_name пізніше
            "lessons": []
        }

    # Парсимо рядки з парами
    rows = grid.find_all(class_="grid-row")
    for row in rows:
        cells = row.find_all("div", recursive=False)
        if not cells:
            continue

        # Перша клітинка - номер пари і час
        time_cell = cells[0]
        time_text = clean_text(time_cell.get_text()) # "1 08:00 - 09:35"
        
        # Парсимо номер і час
        lesson_number = 0
        lesson_time = time_text
        match = re.search(r'(\d+)\s*(.*)', time_text)
        if match:
            lesson_number = int(match.group(1))
            lesson_time = match.group(2)

        # Решта клітинок - предмети для кожного дня
        # cells[1] -> Понеділок, cells[2] -> Вівторок...
        for i, cell in enumerate(cells[1:]):
            if i >= len(day_columns): break # Захист від виходу за межі
            
            day_name = day_columns[i]
            
            # Якщо клітинка пуста - пари немає
            if not cell.get_text(strip=True):
                continue
            
            # Витягуємо дані з клітинки
            # Приклад структури в клітинці:
            # <div class="subject">Math</div>
            # <div class="teacher">Ivanov</div>
            # <div class="room">101</div>
            
            subject = clean_text(cell.find(class_="discipline").get_text()) if cell.find(class_="discipline") else clean_text(cell.get_text())
            teacher = clean_text(cell.find(class_="teacher").get_text()) if cell.find(class_="teacher") else ""
            room = clean_text(cell.find(class_="auditory").get_text()) if cell.find(class_="auditory") else ""
            lesson_type = clean_text(cell.find(class_="type").get_text()) if cell.find(class_="type") else ""
            
            # Посилання (Zoom/Google Meet)
            link = None
            a_tag = cell.find("a", href=True)
            if a_tag:
                link = a_tag['href']

            lesson = {
                "number": lesson_number,
                "time": lesson_time,
                "subject": subject,
                "teacher": teacher,
                "type": lesson_type,
                "room": room,
                "link": link
            }
            
            days_map[day_name]["lessons"].append(lesson)

    return list(days_map.values())

@app.post("/api/schedule/json")
def get_schedule_json(data: LoginData):
    options = webdriver.ChromeOptions()
    # Оптимізація для Free Tier (Render/Heroku - 512MB RAM)
    options.add_argument("--headless=new") # Новий безголовий режим (менше пам'яті)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--blink-settings=imagesEnabled=false") # Не завантажувати картинки (швидше!)
    options.page_load_strategy = 'eager' # Не чекати повного завантаження ресурсів
    
    # Тільки якщо дуже мало пам'яті (може бути менш стабільним)
    # options.add_argument("--single-process") 

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15) # Трохи збільшимо на всяк випадок

    try:
        # Логін
        driver.get("https://cabinet.nau.edu.ua/login")
        wait.until(EC.presence_of_element_located((By.ID, "loginform-username"))).send_keys(data.username)
        driver.find_element(By.ID, "password-input").send_keys(data.password + Keys.ENTER)

        time.sleep(2) # Чекаємо редірект
        if "login" in driver.current_url:
            raise HTTPException(status_code=401, detail="Authentication Failed")

        driver.get("https://cabinet.nau.edu.ua/student/schedule")
        
        # Чекаємо таблицю
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "schedule-grid")))

        all_schedule = []

        # -- Тиждень 1 --
        # Натискаємо кнопку, якщо треба, але зазвичай 1 тиждень відкритий
        # wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., '1 тиждень')]"))).click()
        # time.sleep(1)
        
        # Парсимо HTML активної вкладки
        html_tab0 = driver.find_element(By.CSS_SELECTOR, "#w0-tab0").get_attribute('innerHTML')
        all_schedule.extend(parse_schedule_html(html_tab0, "1 тиждень"))

        # -- Тиждень 2 --
        # Перемикаємось на 2 тиждень
        try:
            tab2_btn = driver.find_element(By.XPATH, "//a[contains(., '2 тиждень')]")
            driver.execute_script("arguments[0].click();", tab2_btn) # Клік через JS надійніший
            time.sleep(1) # Чекаємо підвантаження
            
            # Чекаємо поки вкладка стане активною (не обов'язково, але бажано)
            html_tab1 = driver.find_element(By.CSS_SELECTOR, "#w0-tab1").get_attribute('innerHTML')
            all_schedule.extend(parse_schedule_html(html_tab1, "2 тиждень"))
        except Exception as e:
            print(f"Skipping week 2: {e}")

        return all_schedule

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        driver.quit()

