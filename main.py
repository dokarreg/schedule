from fastapi import FastAPI, Response, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image, ImageDraw, ImageFont
import io
import time

app = FastAPI()

class LoginData(BaseModel):
    username: str
    password: str

def create_vertical_image(img1, img2):
    """Склеює розклад вертикально: Тиждень 1 зверху, Тиждень 2 знизу"""
    padding = 40
    header_h = 100
    total_w = max(img1.width, img2.width) + (padding * 2)
    # Висота: заголовок1 + картинка1 + заголовок2 + картинка2 + відступи
    total_h = header_h + img1.height + (padding * 2) + header_h + img2.height + padding
    
    new_img = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(new_img)
    
    try:
        # Стандартний шлях до шрифтів у Docker (Debian)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except:
        font = ImageFont.load_default()

    # --- Секція 1 тижня ---
    txt1 = "1 TIZHDEN"
    bbox1 = draw.textbbox((0, 0), txt1, font=font)
    draw.text(((total_w - (bbox1[2]-bbox1[0])) // 2, 20), txt1, fill=(0, 51, 153), font=font)
    new_img.paste(img1, ((total_w - img1.width) // 2, header_h))

    # --- Секція 2 тижня ---
    y_start_2 = header_h + img1.height + (padding * 2)
    txt2 = "2 TIZHDEN"
    bbox2 = draw.textbbox((0, 0), txt2, font=font)
    draw.text(((total_w - (bbox2[2]-bbox2[0])) // 2, y_start_2), txt2, fill=(0, 51, 153), font=font)
    new_img.paste(img2, ((total_w - img2.width) // 2, y_start_2 + header_h))
    
    return new_img

@app.post("/generate-schedule")
def generate_schedule(data: LoginData):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,2500") # Достатньо для 5 днів

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 25)

    try:
        # 1. Авторизація (Без логів даних користувача)
        driver.get("https://cabinet.nau.edu.ua/login")
        wait.until(EC.presence_of_element_located((By.ID, "loginform-username"))).send_keys(data.username)
        driver.find_element(By.ID, "password-input").send_keys(data.password + Keys.ENTER)

        time.sleep(4)
        if "login" in driver.current_url:
             raise Exception("Auth Error")

        # 2. Перехід до розкладу
        driver.get("https://cabinet.nau.edu.ua/student/schedule")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "schedule-grid")))

        # 3. JS-скрипт: Видалення вихідних, меню та налаштування колонок
        driver.execute_script("""
            // Видаляємо сміття
            var sidebar = document.querySelector('.menu-aside'); if(sidebar) sidebar.remove();
            var navbar = document.querySelector('nav.navbar'); if(navbar) navbar.style.display = 'none';
            var footer = document.querySelector('footer'); if(footer) footer.style.display = 'none';
            
            // Розтягуємо контейнер
            var container = document.querySelector('.container');
            if(container) { container.style.maxWidth = '100%'; container.style.width = '100%'; container.style.margin = '0'; }

            // Налаштовуємо сітку: Час(80px) + 5 робочих днів
            var style = document.createElement('style');
            style.innerHTML = '.schedule-grid { grid-template-columns: 80px repeat(5, 1fr) !important; display: grid !important; width: 100% !important; } .schedule-wrapper { overflow: visible !important; }';
            document.head.appendChild(style);

            // Приховуємо суботу (індекс 5 робочих + 1 час = 6) та неділю
            document.querySelectorAll('.grid-header-row, .grid-row').forEach(row => {
                var cells = row.children;
                if (cells.length >= 7) { cells[6].style.display = 'none'; } // Неділя (7-й елемент)
                if (cells.length >= 8) { cells[7].style.display = 'none'; } // Якщо є 8-й
                if (cells.length >= 6) { cells[5].parentElement.className.contains('grid-header-row') ? cells[5].style.display = 'none' : null; }
                
                // Специфічне приховування для рядків контенту
                if (row.classList.contains('grid-row')) {
                    if(cells[6]) cells[6].style.display = 'none'; // Субота
                    if(cells[7]) cells[7].style.display = 'none'; // Неділя
                } else {
                    if(cells[5]) cells[5].style.display = 'none'; // Субота в хедері
                    if(cells[6]) cells[6].style.display = 'none'; // Неділя в хедері
                }
            });
        """)
        time.sleep(2)

        # 4. Знімок 1 тижня
        tab1 = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., '1 тиждень')]")))
        tab1.click()
        time.sleep(2)
        png1 = driver.find_element(By.CSS_SELECTOR, "#w0-tab0 .schedule-grid").screenshot_as_png
        img1 = Image.open(io.BytesIO(png1))

        # 5. Знімок 2 тижня
        tab2 = driver.find_element(By.XPATH, "//a[contains(., '2 тиждень')]")
        tab2.click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#w0-tab1.active")))
        time.sleep(2)
        
        # Додаткова перевірка приховування для 2 тижня
        driver.execute_script("""
            document.querySelectorAll('#w0-tab1 .grid-row').forEach(row => {
                if (row.children.length >= 7) row.children[6].style.display = 'none';
                if (row.children.length >= 8) row.children[7].style.display = 'none';
            });
        """)
        
        png2 = driver.find_element(By.CSS_SELECTOR, "#w0-tab1 .schedule-grid").screenshot_as_png
        img2 = Image.open(io.BytesIO(png2))

        # 6. Склейка та повернення результату
        final_img = create_vertical_image(img1, img2)
        img_io = io.BytesIO()
        final_img.save(img_io, format='PNG', quality=100)
        img_io.seek(0)
        
        return Response(content=img_io.getvalue(), media_type="image/png")

    except Exception:
        raise HTTPException(status_code=500, detail="Server error during processing")
    finally:
        driver.quit()
