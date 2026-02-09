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
    padding, header_h = 40, 100
    total_w = max(img1.width, img2.width) + (padding * 2)
    total_h = header_h + img1.height + padding + header_h + img2.height + padding
    
    new_img = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(new_img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except:
        font = ImageFont.load_default()

    # Малюємо заголовки
    for i, txt in enumerate(["1 ТИЖДЕНЬ", "2 ТИЖДЕНЬ"]):
        y = 20 if i == 0 else header_h + img1.height + padding + 20
        img = img1 if i == 0 else img2
        bbox = draw.textbbox((0, 0), txt, font=font)
        draw.text(((total_w - (bbox[2]-bbox[0])) // 2, y), txt, fill=(0, 51, 153), font=font)
        new_img.paste(img, ((total_w - img.width) // 2, y + 80))
    return new_img

@app.post("/generate-schedule")
def generate_schedule(data: LoginData):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,2500")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 25)

    try:
        # ЖОДНИХ print(data.username) ТУТ НЕМАЄ
        driver.get("https://cabinet.nau.edu.ua/login")
        wait.until(EC.presence_of_element_located((By.ID, "loginform-username"))).send_keys(data.username)
        driver.find_element(By.ID, "password-input").send_keys(data.password + Keys.ENTER)

        time.sleep(3)
        if "login" in driver.current_url:
             raise Exception("Authentication Failed") # Універсальна помилка

        driver.get("https://cabinet.nau.edu.ua/student/schedule")
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "schedule-grid")))

        # Чистка інтерфейсу
        driver.execute_script("""
            var sidebar = document.querySelector('.menu-aside'); if(sidebar) sidebar.remove();
            var navbar = document.querySelector('nav.navbar'); if(navbar) navbar.style.display = 'none';
            var footer = document.querySelector('footer'); if(footer) footer.style.display = 'none';
            var container = document.querySelector('.container');
            if(container) { container.style.maxWidth = '100%'; container.style.width = '100%'; container.style.margin = '0'; }
            
            var style = document.createElement('style');
            style.innerHTML = '.schedule-grid { grid-template-columns: 80px repeat(5, 1fr) !important; display: grid !important; width: 100% !important; }';
            document.head.appendChild(style);

            document.querySelectorAll('.grid-header-row, .grid-row').forEach(row => {
                if (row.children.length >= 7) { row.children[row.children.length-1].style.display = 'none'; } // Неділя
                if (row.children.length >= 8) { row.children[row.children.length-2].style.display = 'none'; } // Субота
            });
        """)
        time.sleep(2)

        # Тиждень 1
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., '1 тиждень')]"))).click()
        time.sleep(2)
        img1 = Image.open(io.BytesIO(driver.find_element(By.CSS_SELECTOR, "#w0-tab0 .schedule-grid").screenshot_as_png))

        # Тиждень 2
        driver.find_element(By.XPATH, "//a[contains(., '2 тиждень')]").click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#w0-tab1.active")))
        time.sleep(2)
        img2 = Image.open(io.BytesIO(driver.find_element(By.CSS_SELECTOR, "#w0-tab1 .schedule-grid").screenshot_as_png))

        final_img = create_vertical_image(img1, img2)
        img_byte_arr = io.BytesIO()
        final_img.save(img_byte_arr, format='PNG')
        
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")

    except Exception:
        # Повертаємо загальну помилку без деталей про логін
        raise HTTPException(status_code=400, detail="Error processing schedule")
    finally:
        driver.quit()
