# bot_clasificador.py - USA CONSULTA DE EXPEDIENTES
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import re

BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex"

def bot_clasificador(usuario_sistema, usuario_forum, clave_forum, progress_callback=None, stop_event=None):
    def emit_event(event, data):
        if progress_callback:
            progress_callback.emit(event, data)
            progress_callback.sleep(0.1)
        print(data.get('msg', ''))

    def check_stop():
        return stop_event and stop_event.is_set()

    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        emit_event('bot_status', {'msg': '✅ Chrome abierto', 'progreso': 5})
    except Exception as e:
        emit_event('bot_error', {'msg': f'No se pudo abrir Chrome: {str(e)}'})
        return

    wait = WebDriverWait(driver, 20)

    try:
        # 1. LOGIN
        emit_event('bot_status', {'msg': '🔑 Iniciando sesión en Forum...', 'progreso': 10})
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")

        wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys(usuario_forum)
        driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys(clave_forum)

        # Múltiples selectores del botón
        login_exitoso = False
        selectores_boton = [
            (By.ID, "btnLogin"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//button[contains(text(), 'Ingresar')]"),
            (By.XPATH, "//input[@value='Ingresar']")
        ]

        for metodo, selector in selectores_boton:
            try:
                driver.find_element(metodo, selector).click()
                login_exitoso = True
                break
            except:
                continue

        if not login_exitoso:
            driver.find_element(By.TAG_NAME, "form").submit()

        time.sleep(3)
        intentos = 0
        while "login" in driver.current_url.lower() and intentos < 10:
            time.sleep(2)
            intentos += 1

        emit_event('bot_status', {'msg': '✅ Sesión iniciada', 'progreso': 15})

        # 2. LEER CARPETA IMPORTADOS
        ruta_importados = os.path.join(BASE_PATH, "expedientes_clientes", usuario_sistema, "IMPORTADOS")

        if not os.path.exists(ruta_importados):
            emit_event('bot_status', {'msg': '❌ No existe carpeta IMPORTADOS', 'progreso': 100})
            return

        carpetas = [f for f in os.listdir(ruta_importados) if os.path.isdir(os.path.join(ruta_importados, f))]

        if not carpetas:
            emit_event('bot_status', {'msg': '✅ No hay expedientes para clasificar', 'progreso': 100})
            return

        emit_event('bot_status', {'msg': f'📂 {len(carpetas)} expedientes para clasificar', 'progreso': 20})

        # 3. CLASIFICAR USANDO "CONSULTA DE EXPEDIENTES"
        clasificados = 0
        errores = 0
        log_items = []

        for idx, nombre_carpeta in enumerate(carpetas):
            if check_stop():
                emit_event('bot_status', {'msg': '🛑 Clasificación detenida'})
                break

            progreso = 20 + int((idx / len(carpetas)) * 70)

            # IGNORAR LOS SIN_NUMERO
            if nombre_carpeta.startswith("SIN_NUMERO"):
                print(f"[CLASIFICADOR] Saltando {nombre_carpeta} - sin número")
                emit_event('bot_status', {
                    'msg': f'Saltando {nombre_carpeta[:30]} - sin número',
                    'progreso': progreso,
                    'contador': f'{idx+1}/{len(carpetas)}'
                })
                continue

            # Extraer número: "278674-25 _ NOMBRE"
            match = re.match(r'^([A-Z0-9-]+)\s+_', nombre_carpeta)
            if not match:
                log_items.insert(0, f'⚠️ {nombre_carpeta[:30]} - Sin número')
                emit_event('bot_log', {'log': log_items[:3]})
                errores += 1
                continue

            nro_completo = match.group(1)

            emit_event('bot_status', {
                'msg': f'🔍 [{idx+1}/{len(carpetas)}] Buscando {nro_completo}...',
                'progreso': progreso,
                'contador': f'{idx+1}/{len(carpetas)}',
                'current_exp': nro_completo[:30]
            })

            # BUSCAR EN CONSULTA DE EXPEDIENTES
            juzgado = buscar_juzgado_en_consulta(driver, wait, nro_completo, emit_event)

            if not juzgado:
                log_items.insert(0, f'❌ {nro_completo} - No se encontró juzgado')
                emit_event('bot_log', {'log': log_items[:3]})
                errores += 1
                continue

            # MOVER A: Juzgado Civil Y Comercial N° 1/EN_ESPERA/nombre_carpeta
            ruta_origen = os.path.join(ruta_importados, nombre_carpeta)

            ruta_destino_base = os.path.join(
                BASE_PATH,
                "expedientes_clientes",
                usuario_sistema,
                juzgado,
                "EN_ESPERA"
            )
            os.makedirs(ruta_destino_base, exist_ok=True)
            ruta_destino = os.path.join(ruta_destino_base, nombre_carpeta)

            try:
                shutil.move(ruta_origen, ruta_destino)
                clasificados += 1
                log_items.insert(0, f'✅ {nro_completo} → {juzgado}/EN_ESPERA')
                emit_event('bot_log', {'log': log_items[:3]})
            except Exception as e:
                log_items.insert(0, f'❌ Error moviendo: {str(e)[:30]}')
                emit_event('bot_log', {'log': log_items[:3]})
                errores += 1

        emit_event('bot_finished', {
            'total': len(carpetas),
            'clasificados': clasificados,
            'errores': errores,
            'tiempo': 'Completado'
        })
        emit_event('bot_status', {
            'msg': f'✅ Clasificación finalizada: {clasificados} movidos, {errores} errores',
            'progreso': 100
        })

    except Exception as e:
        emit_event('bot_error', {'msg': f'Error crítico: {str(e)}'})
    finally:
        try:
            driver.quit()
        except:
            pass

def buscar_juzgado_en_consulta(driver, wait, nro_completo, emit_event):
    """
    Busca el expte en 'Consulta de Expedientes' y devuelve el juzgado de la columna 'Organismo Radicación'
    """
    try:
        # Parsear número
        partes = nro_completo.split("-")

        if partes[0].startswith(('C', 'I')): # C01-45330-09
            nro = partes[1]
            anio = partes[2]
        else: # 278674-25
            nro = partes[0]
            anio = partes[1]

        # IR A CONSULTA DE EXPEDIENTES
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
        time.sleep(2)

        # Localidad Capital
        try:
            wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop"))).click()
            time.sleep(0.5)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Capital')]"))).click()
        except:
            pass

        # COMPLETAR NÚMERO Y AÑO
        wait.until(EC.presence_of_element_located((By.ID, "vCAUSANRO"))).clear()
        driver.find_element(By.ID, "vCAUSANRO").send_keys(nro)

        try:
            driver.find_element(By.ID, "vCAUSAANIO").clear()
            driver.find_element(By.ID, "vCAUSAANIO").send_keys(anio)
        except:
            pass

        # BUSCAR
        driver.find_element(By.ID, "BTN_SEARCH").click()
        time.sleep(3)

        # LEER COLUMNA "ORGANISMO RADICACIÓN"
        try:
            # Esperar que aparezca la tabla
            wait.until(EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'Grid')]")))

            # Buscar la primera fila de datos - columna "Organismo Radicación"
            juzgado_element = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//table[contains(@class, 'Grid')]//tr[td][1]/td[1]")
            ))

            juzgado_texto = juzgado_element.text.strip()

            # Limpiar: "JUZGADO CIVIL Y COMERCIAL NRO.11" → "Juzgado Civil Y Comercial N° 11"
            juzgado = re.sub(r'^JUZGADO\s+', '', juzgado_texto, flags=re.IGNORECASE).strip()
            juzgado = f"Juzgado {juzgado}"
            juzgado = juzgado.replace('NRO.', 'N°').replace('Nº', 'N°')

            emit_event('bot_log', {'log': [f'✅ Encontrado: {juzgado}']})
            return juzgado

        except Exception as e:
            emit_event('bot_log', {'log': [f'❌ No apareció en tabla: {str(e)[:40]}']})
            return None

    except Exception as e:
        emit_event('bot_log', {'log': [f'❌ Error buscando {nro_completo}: {str(e)[:40]}']})
        return None

if __name__ == "__main__":
    bot_clasificador("nico", "RicardoM", "1942")