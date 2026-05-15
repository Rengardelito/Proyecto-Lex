# helpers/bot_base.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from config import SELENIUM_TIMEOUT

class BotBase:
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.driver = None

    def iniciar_driver(self):
        chrome_options = Options()
        # chrome_options.add_argument("--headless") # Descomentar para no ver la ventana
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Ajustá la ruta del chromedriver si es necesario
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(SELENIUM_TIMEOUT)

    def emit_event(self, event_name, msg, progreso=None):
        if self.socketio:
            data = {'msg': msg}
            if progreso is not None:
                data['progreso'] = progreso
            self.socketio.emit(event_name, data)
        print(f"[{event_name.upper()}] {msg}")

    def cerrar(self):
        if self.driver:
            self.driver.quit()