# helpers/forum_scraper.py
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import FORUM_URL_LOGIN, FORUM_URL_CAUSAS

# def login_forum(driver, user, password):
#     """Loguea en el sistema FORUM usando las credenciales del usuario"""
#     try:
#         driver.get(FORUM_URL_LOGIN)
#         wait = WebDriverWait(driver, 15)
        
#         # Esperar y completar usuario
#         user_input = wait.until(EC.presence_of_element_located((By.NAME, "usuario")))
#         user_input.clear()
#         user_input.send_keys(user)
        
#         # Completar contraseña
#         pass_input = driver.find_element(By.NAME, "clave")
#         pass_input.clear()
#         pass_input.send_keys(password)
        
#         # Click en ingresar
#         btn_ingresar = driver.find_element(By.ID, "ingresar")
#         btn_ingresar.click()
        
#         # Verificar si entramos (buscando algún elemento del dashboard)
#         wait.until(EC.presence_of_element_located((By.CLASS_NAME, "dropdown-toggle")))
#         print("[FORUM] Login exitoso")
#         return True
#     except Exception as e:
#         print(f"[FORUM] Error en login: {e}")
#         return False



from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def login_forum(driver, user, password):
    try:
        url_login = "https://forumna.juscorrientes.gov.ar/com.forumna.login"
        print(f"🌐 [FORUM] Abriendo: {url_login}")
        driver.get(url_login)
        
        # ⏱️ ESPERA ACTIVA: Esperamos hasta 20 segundos a que el campo 'usuario' EXISTA
        wait = WebDriverWait(driver, 20)
        
        # Primero esperamos con Selenium para estar seguros que la página cargó el DOM
        print("⏳ Esperando que carguen los campos...")
        campo_user = wait.until(EC.presence_of_element_located((By.NAME, "usuario")))
        
        # Un pequeño respiro extra porque Forum a veces dibuja el campo pero no lo activa
        time.sleep(2)

        # ✍️ INYECCIÓN SEGURA POR ID O NAME
        # Usamos un script más robusto que no tire 'undefined'
        script_js = f"""
            var u = document.getElementsByName('usuario')[0];
            var p = document.getElementsByName('clave')[0];
            if(u && p){{
                u.value = '{user}';
                p.value = '{password}';
                return true;
            }}
            return false;
        """
        
        exito_inyeccion = driver.execute_script(script_js)
        
        if exito_inyeccion:
            print("✍️ Credenciales puestas. Click en ingresar...")
            # Intentamos el click por ID
            driver.execute_script("document.getElementById('ingresar').click();")
        else:
            raise Exception("No se encontraron los campos 'usuario' o 'clave' en el DOM")

        # 🕵️ VERIFICACIÓN FINAL
        # Esperamos ver el dropdown del usuario arriba a la derecha
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "dropdown-toggle")))
        
        print("✅ [FORUM] ¡ADENTRO! Login exitoso.")
        return True

    except Exception as e:
        print(f"❌ [FORUM] Error: {str(e)}")
        driver.save_screenshot("error_dom_forum.png")
        return False
def entrar_expediente_correcto(driver, nro_expte):
    """
    Busca un expediente en la lista de causas y entra.
    nro_expte esperado: 'C01-123456-24' o similar.
    """
    try:
        driver.get(FORUM_URL_CAUSAS)
        wait = WebDriverWait(driver, 10)
        
        # El buscador de Forum suele ser un input de tipo search o texto
        filtro = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='search']")))
        filtro.clear()
        filtro.send_keys(nro_expte)
        time.sleep(1) # Esperar un segundo que filtre la tabla
        
        # Buscar el link que tiene el número de expediente para hacer click
        xpath_expte = f"//a[contains(text(), '{nro_expte}')]"
        link_expte = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_expte)))
        link_expte.click()
        
        print(f"[FORUM] Entramos al expediente: {nro_expte}")
        return True
    except Exception as e:
        print(f"[FORUM] No se pudo entrar al expediente {nro_expte}: {e}")
        return False