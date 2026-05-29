# bots/driver_manager.py
import threading
import time
import config

_driver = None
_driver_lock = threading.Lock()
_ping_thread = None
_driver_activo = False
_driver_ocupado = False

def marcar_ocupado():
    global _driver_ocupado
    _driver_ocupado = True

def marcar_libre():
    global _driver_ocupado
    _driver_ocupado = False

def _ping_loop():
    """Ping silencioso cada 4 minutos — solo si el driver no está ocupado."""
    global _driver, _driver_activo, _driver_ocupado
    while _driver_activo:
        time.sleep(240)
        try:
            if _driver and _driver_activo and not _driver_ocupado:
                _driver.execute_script("return document.title;")
                print("[DriverManager] Ping silencioso enviado")
        except Exception as e:
            print(f"[DriverManager] Error en ping: {e}")

def get_driver(temp_download_path=None):
    global _driver, _ping_thread, _driver_activo
    with _driver_lock:
        if _driver is not None:
            try:
                _ = _driver.current_url
                print("[DriverManager] Reutilizando driver existente")
                return _driver
            except Exception:
                print("[DriverManager] Driver muerto, creando uno nuevo")
                _driver = None
                _driver_activo = False

        from selenium import webdriver
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        ruta_temp = temp_download_path or config.TEMP_DOWNLOAD_PATH
        prefs = {
            "download.default_directory": ruta_temp,
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True
        }
        options.add_experimental_option("prefs", prefs)

        _driver = webdriver.Chrome(options=options)
        _driver.implicitly_wait(config.SELENIUM_TIMEOUT)
        _driver_activo = True

        _ping_thread = threading.Thread(target=_ping_loop, daemon=True)
        _ping_thread.start()

        print("[DriverManager] Driver nuevo creado con ping activo")
        return _driver

def release_driver():
    global _driver_ocupado
    _driver_ocupado = False
    print("[DriverManager] Driver liberado (sigue activo en background)")

def close_driver():
    global _driver, _driver_activo
    with _driver_lock:
        _driver_activo = False
        if _driver:
            try:
                _driver.quit()
            except Exception:
                pass
            _driver = None
    print("[DriverManager] Driver cerrado definitivamente")

def is_logged_in():
    global _driver
    if not _driver:
        return False
    try:
        url = _driver.current_url
        return 'forumna.juscorrientes.gov.ar' in url and 'login' not in url.lower()
    except Exception:
        return False