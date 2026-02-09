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
    padding = 40
    header_height = 100
    bg_color = (255, 255, 255)
    text_color = (0, 51, 153)
    
    total_width = max(img1.width, img2.width) + (padding * 2)
    total_height = header_height + img1.height + padding + header_height + img2.height + padding
    
    new_img = Image.new("RGB", (total_width, total_height), bg_color)
    draw = ImageDraw.Draw(new_img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except:
        font = ImageFont.load_default()

    text1 = "1 ТИЖДЕНЬ"
    bbox1 = draw.textbbox((0, 0), text1, font=font)
    draw.text(((total_width - (bbox1[2]-bbox1[0])) // 2, 20), text1, fill=text_color, font=font)
    
    img1_x = (total_width - img1.width) // 2
    new_img.paste(img1, (img1_x, header_height))

    y_offset = header_height + img1.height + padding
    text2 = "2 ТИЖДЕНЬ"
    bbox2 = draw.textbbox((0, 0), text2, font=font)
    draw.text(((total_width - (bbox2[2]-bbox2[0])) // 2, y_offset + 20), text2, fill=text_color, font=font)
    
    img2_x = (total_width - img2.width) // 2
    new_img.paste(img2, (img2_x, y_offset + header_height))
    
    return new_img

@app.post("/generate-schedule")
def generate_schedule(data: LoginData):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox") # Важливо для Docker
    options.add_argument("--disable-dev-shm-usage") # Важливо для Docker
    options.add_argument("--window-size=1920,2500")
    options.add_argument("--hide-scrollbars")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 25)

    try:
        driver.get("https://cabinet.nau.edu.ua/login")
        wait.until(EC.presence_of_element_located((By.ID, "loginform-username"))).send_keys(data.username)
        driver.find_element(By.ID, "password-input").send_keys(data.password + Keys.ENTER)

        time.sleep(3)
        # Перевірка на невдалий логін (якщо URL не змінився або є помилка)
        if "login" in driver.current_url and "student" not in driver.current_url:
             raise Exception("Невірний логін або пароль")

        driver.get("https://cabinet.nau.edu.ua/student/schedule")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "schedule-grid")))

        driver.execute_script("""
            var sidebar = document.querySelector('.menu-aside');
            if(sidebar) sidebar.remove();
            var navbar = document.querySelector('nav.navbar');
            if(navbar) navbar.style.display = 'none';
            var footer = document.querySelector('footer');
            if(footer) footer.style.display = 'none';

            var container = document.querySelector('.container');
            if(container) {
                container.style.maxWidth = '100%';
                container.style.width = '100%';
                container.style.padding = '10px';
                container.style.margin = '0';
            }

            var style = document.createElement('style');
            style.innerHTML = '.schedule-grid { grid-template-columns: 80px repeat(5, 1fr) !important; display: grid !important; width: 100% !important; } .schedule-wrapper { overflow: visible !important; }';
            document.head.appendChild(style);

            document.querySelectorAll('.grid-header-row').forEach(headerRow => {
                var headers = headerRow.children;
                if (headers.length >= 7) {
                    headers[5].style.display = 'none';
                    headers[6].style.display = 'none';
                }
            });

            document.querySelectorAll('.grid-row').forEach(row => {
                var cells = row.children;
                if (cells.length >= 8) {
                    cells[6].style.display = 'none';
                    cells[7].style.display = 'none';
                }
            });

            document.body.style.zoom = '100%'; 
        """)
        time.sleep(2)

        # 1 ТИЖДЕНЬ
        tab1_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., '1 тиждень')]")))
        tab1_btn.click()
        time.sleep(2)
        # Скріншот в пам'ять
        png1 = driver.find_element(By.CSS_SELECTOR, "#w0-tab0 .schedule-grid").screenshot_as_png
        img1 = Image.open(io.BytesIO(png1))

        # 2 ТИЖДЕНЬ
        tab2_btn = driver.find_element(By.XPATH, "//a[contains(., '2 тиждень')]")
        tab2_btn.click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#w0-tab1.active")))
        time.sleep(2)
        png2 = driver.find_element(By.CSS_SELECTOR, "#w0-tab1 .schedule-grid").screenshot_as_png
        img2 = Image.open(io.BytesIO(png2))

        final_img = create_vertical_image(img1, img2)
        
        # Зберігаємо результат в буфер байтів
        img_byte_arr = io.BytesIO()
        final_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")

    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        driver.quit()
