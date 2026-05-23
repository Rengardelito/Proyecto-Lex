# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.common.action_chains import ActionChains
# from webdriver_manager.chrome import ChromeDriverManager
# import time
# import os
# import shutil
# import re

# def descargar_ciclo_vida_cronologico(driver, wait, expte, ruta_destino_final, delay_entre_descargas=3):
#     """
#     Descarga TODAS las actuaciones del expediente en orden cronológico:
#     De la más vieja a la más nueva, para que queden ordenadas en la carpeta.
#     """
#     print(f"\n📚 Descargando CICLO DE VIDA CRONOLÓGICO de {expte}...")

#     temp_download_path = os.path.join(os.path.dirname(ruta_destino_final), "..", "..", "temp_downloads")
#     temp_download_path = os.path.abspath(temp_download_path)

#     for f in os.listdir(temp_download_path):
#         os.remove(os.path.join(temp_download_path, f))

#     # Entrar al expediente
#     input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
#     input_nro.clear()
#     input_nro.send_keys(expte)
#     driver.find_element(By.ID, "BTN_SEARCH").click()

#     time.sleep(2)
#     celda_link = wait.until(EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '{expte}')]")))
#     ActionChains(driver).double_click(celda_link).perform()

#     print("🔎 Esperando grilla de actuaciones...")
#     time.sleep(4)

#     iframes = driver.find_elements(By.TAG_NAME, "iframe")
#     if iframes:
#         driver.switch_to.frame(iframes[0])
#         time.sleep(2)

#     # PASO 1: Detectar paginación e ir a la última página
#     try:
#         # Busco el paginador
#         paginador = driver.find_element(By.CSS_SELECTOR, "ul.pagination")
#         botones_pagina = paginador.find_elements(By.TAG_NAME, "a")

#         # Saco todos los números de página
#         numeros_pag = []
#         for btn in botones_pagina:
#             txt = btn.text.strip()
#             if txt.isdigit():
#                 numeros_pag.append(int(txt))

#         if numeros_pag:
#             ultima_pagina = max(numeros_pag)
#             print(f"📄 Detectadas {ultima_pagina} páginas. Yendo a la última...")
#             # Click en el botón de la última página
#             btn_ultima = paginador.find_element(By.XPATH, f".//a[text()='{ultima_pagina}']")
#             driver.execute_script("arguments[0].click();", btn_ultima)
#             time.sleep(3) # Esperar que cargue la página
#         else:
#             print("📄 Solo hay 1 página.")
#             ultima_pagina = 1
#     except:
#         print("📄 No se detectó paginador. Asumo 1 sola página.")
#         ultima_pagina = 1

#     descargas_hechas = 0
#     archivos_ya_existentes = set()
#     if os.path.exists(ruta_destino_final):
#         archivos_ya_existentes = set(os.listdir(ruta_destino_final))

#     pagina_actual = ultima_pagina

#     # PASO 2: Loop de páginas de atrás para adelante
#     while pagina_actual >= 1:
#         print(f"\n📖 Procesando página {pagina_actual}...")

#         # PASO 3: Detectar cuántas filas hay en esta página y procesar de ABAJO hacia ARRIBA
#         filas = driver.find_elements(By.XPATH, "//span[contains(@id, 'span_vFECHAFIRMA_')]")
#         indices = []
#         for f in filas:
#             id_completo = f.get_attribute("id") # span_vFECHAFIRMA_0015
#             match = re.search(r'_(\d+)$', id_completo)
#             if match:
#                 indices.append(int(match.group(1)))

#         # Ordeno de mayor a menor para ir de abajo hacia arriba en la tabla
#         indices.sort(reverse=True)
#         print(f" Encontradas {len(indices)} filas. Índices: {indices[:3]}...{indices[-3:]}")

#         for idx_int in indices:
#             idx_str = str(idx_int).zfill(4)
#             id_fecha = f"span_vFECHAFIRMA_{idx_str}"
#             id_boton = f"span_vDOCDOC_{idx_str}"

#             fecha_actual = driver.find_element(By.ID, id_fecha).text.strip()

#             # Si no tiene PDF, salto
#             if not driver.find_elements(By.ID, id_boton):
#                 print(f" ⏭️ Fila {idx_str} ({fecha_actual}) sin PDF. Salto.")
#                 continue

#             try:
#                 nro_act = driver.find_element(By.ID, f"span_vNUMERO_{idx_str}").text.strip()
#             except:
#                 nro_act = f"fila_{idx_str}"

#             nombre_final = f"FECHA_{fecha_actual.replace('/','-')}_ID_{nro_act}.pdf"

#             if nombre_final in archivos_ya_existentes:
#                 print(f" ⏭️ Ya existe: {nombre_final}")
#                 continue

#             print(f" 📥 Descargando {fecha_actual} - Act {nro_act}...")

#             btn_pdf = wait.until(EC.element_to_be_clickable((By.ID, id_boton)))
#             driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_pdf)
#             time.sleep(0.5)
#             btn_pdf.click()

#             time.sleep(4)
#             archivos = os.listdir(temp_download_path)
#             if archivos:
#                 archivo_reciente = os.path.join(temp_download_path, archivos[0])
#                 ruta_destino = os.path.join(ruta_destino_final, nombre_final)
#                 shutil.move(archivo_reciente, ruta_destino)
#                 print(f" ✅ Guardado: {nombre_final}")
#                 descargas_hechas += 1
#             else:
#                 print(f" ⚠️ No apareció archivo para fila {idx_str}")

#             time.sleep(delay_entre_descargas)

#         # PASO 4: Ir a la página anterior si no es la 1
#         if pagina_actual > 1:
#             try:
#                 btn_ant = driver.find_element(By.XPATH, "//ul[contains(@class,'pagination')]//a[text()='Ant']")
#                 driver.execute_script("arguments[0].click();", btn_ant)
#                 pagina_actual -= 1
#                 time.sleep(3) # Esperar carga de página
#             except:
#                 print("⚠️ No pude clickear 'Ant'. Corto acá.")
#                 break
#         else:
#             break

#     driver.switch_to.default_content()
#     print(f"\n✨ Ciclo de vida finalizado. Se descargaron {descargas_hechas} archivos nuevos en orden cronológico.")
#     return descargas_hechas

# def ejecutar_barrido_cronologico(usuario_sistema, usuario_forum, clave_forum, lista_exptes):
#     """
#     Botón "DESCARGAR TODO" pero en orden cronológico correcto.
#     """
#     BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex"
#     temp_download_path = os.path.join(BASE_PATH, "temp_downloads")
#     os.makedirs(temp_download_path, exist_ok=True)

#     options = webdriver.ChromeOptions()
#     prefs = {
#         "download.default_directory": temp_download_path,
#         "download.prompt_for_download": False,
#         "plugins.always_open_pdf_externally": True
#     }
#     options.add_experimental_option("prefs", prefs)
#     driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
#     wait = WebDriverWait(driver, 15)

#     try:
#         driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
#         wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys(usuario_forum)
#         driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys(clave_forum)
#         print("\n--- LOGUEATE Y RESOLVÉ EL CAPTCHA ---")
#         while "login" in driver.current_url: time.sleep(2)
#         print("✅ Sesión iniciada.")

#         for expte in lista_exptes:
#             ruta_destino_final = os.path.join(BASE_PATH, "expedientes_clientes", usuario_sistema, "Juzgado Civil y Comercial N° 1", expte)
#             os.makedirs(ruta_destino_final, exist_ok=True)

#             driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
#             time.sleep(2)

#             btn_combo = wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")))
#             btn_combo.click()
#             time.sleep(1)
#             driver.find_element(By.XPATH, "//span[contains(text(), 'Capital')]").click()

#             descargar_ciclo_vida_cronologico(driver, wait, expte, ruta_destino_final, delay_entre_descargas=3)

#             print(f"\n⏸️ Pausa de 5 seg antes del próximo expediente...")
#             time.sleep(5)

#     finally:
#         driver.quit()

# # EJECUCIÓN
# ejecutar_barrido_cronologico("nico", "RicardoM", "1942", ["104604"])

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import shutil
import re

def limpiar_temp(temp_download_path):
    """Vacía la carpeta temporal de forma segura"""
    if os.path.exists(temp_download_path):
        for f in os.listdir(temp_download_path):
            ruta = os.path.join(temp_download_path, f)
            try:
                if os.path.isfile(ruta):
                    os.remove(ruta)
            except:
                pass

def esperar_descarga_o_pestana(driver, temp_download_path, timeout=20):
    """
    Espera a que aparezca un PDF en temp_download_path O que se abra una pestaña nueva.
    Devuelve la ruta del archivo si lo bajó, o None si hay que manejar pestaña.
    """
    ventana_original = driver.current_window_handle
    for _ in range(timeout):
        time.sleep(1)
        # Caso 1: Se descargó directo
        archivos = [a for a in os.listdir(temp_download_path) if a.endswith('.pdf') and not a.endswith('.crdownload')]
        if archivos:
            return os.path.join(temp_download_path, archivos[0])

        # Caso 2: Se abrió pestaña nueva con el PDF
        if len(driver.window_handles) > 1:
            return None # Señal de que hay que manejar pestaña

    return None

def descargar_desde_pestana_pdf(driver, ventana_original, ruta_destino_final, nombre_final):
    """
    Si el PDF se abrió en pestaña nueva, guarda el contenido.
    """
    try:
        # Cambio a la pestaña nueva
        for ventana in driver.window_handles:
            if ventana!= ventana_original:
                driver.switch_to.window(ventana)
                break

        time.sleep(2)
        # En Forum el PDF suele estar en un <embed> o <iframe>
        pdf_url = driver.current_url
        if ".pdf" in pdf_url.lower():
            # Truco: uso el print de Chrome para guardar como PDF
            driver.execute_script("window.print();")
            time.sleep(3) # Le doy tiempo al diálogo de impresión
            # Como no podemos interactuar con el diálogo nativo, cerramos y avisamos
            print(f" ⚠️ PDF abierto en pestaña: {pdf_url}")
            print(f" ⚠️ Descargalo manualmente como: {nombre_final}")
            driver.close()
            driver.switch_to.window(ventana_original)
            return False
        else:
            driver.close()
            driver.switch_to.window(ventana_original)
            return False
    except Exception as e:
        print(f" ⚠️ Error manejando pestaña PDF: {e}")
        if len(driver.window_handles) > 1:
            driver.close()
        driver.switch_to.window(ventana_original)
        return False

def descargar_ciclo_vida_cronologico(driver, wait, expte, ruta_destino_final, delay_entre_descargas=3):
    """
    Descarga TODAS las actuaciones del expediente en orden cronológico:
    De la más vieja a la más nueva, para que queden ordenadas en la carpeta.
    """
    print(f"\n📚 Descargando CICLO DE VIDA CRONOLÓGICO de {expte}...")

    temp_download_path = os.path.join(os.path.dirname(ruta_destino_final), "..", "..", "temp_downloads")
    temp_download_path = os.path.abspath(temp_download_path)
    os.makedirs(temp_download_path, exist_ok=True)
    os.makedirs(ruta_destino_final, exist_ok=True)
    limpiar_temp(temp_download_path)

    # Entrar al expediente
    input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
    input_nro.clear()
    input_nro.send_keys(expte)
    driver.find_element(By.ID, "BTN_SEARCH").click()

    time.sleep(2)
    celda_link = wait.until(EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '{expte}')]")))
    ActionChains(driver).double_click(celda_link).perform()

    print("🔎 Esperando grilla de actuaciones...")
    time.sleep(4)

    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    if iframes:
        driver.switch_to.frame(iframes[0])
        time.sleep(2)

    # PASO 1: Ir a la última página
    ultima_pagina = 1
    try:
        def get_pagina_actual():
            try:
                paginador = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.pagination")))
                activo = paginador.find_element(By.CSS_SELECTOR, "li.active a")
                return int(activo.text.strip())
            except:
                return 1

        paginador = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.pagination")))

        try:
            btn_ult = paginador.find_element(By.XPATH, ".//a[contains(text(), 'Últ') or contains(text(), '>>') or contains(text(), '»')]")
            driver.execute_script("arguments[0].click();", btn_ult)
            time.sleep(3)
            ultima_pagina = get_pagina_actual()
            print(f"📄 Click en 'Últ'. Ahora estoy en página {ultima_pagina}")
        except:
            print("📄 No hay botón 'Últ'. Buscando número más alto...")
            while True:
                paginador = driver.find_element(By.CSS_SELECTOR, "ul.pagination")
                botones = paginador.find_elements(By.XPATH, ".//a[string(number(text()))!= 'NaN']")
                numeros = [int(b.text) for b in botones if b.text.isdigit()]
                if not numeros: break

                pagina_actual_detectada = get_pagina_actual()
                max_visible = max(numeros)

                if pagina_actual_detectada == max_visible:
                    ultima_pagina = pagina_actual_detectada
                    break
                else:
                    btn_max = paginador.find_element(By.XPATH, f".//a[text()='{max_visible}']")
                    driver.execute_script("arguments[0].click();", btn_max)
                    time.sleep(3)

            ultima_pagina = get_pagina_actual()
            print(f"✅ Confirmado: Última página real es la {ultima_pagina}")

    except Exception as e:
        print(f"📄 No se detectó paginador: {e}. Asumo 1 sola página.")
        ultima_pagina = 1

    descargas_hechas = 0
    archivos_ya_existentes = set(os.listdir(ruta_destino_final)) if os.path.exists(ruta_destino_final) else set()
    print(f"📁 Ya existen {len(archivos_ya_existentes)} archivos en destino.")

    pagina_actual = ultima_pagina
    ventana_principal = driver.current_window_handle

    # PASO 2: Loop de páginas de atrás para adelante
    while pagina_actual >= 1:
        print(f"\n📖 Procesando página {pagina_actual}...")

        wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(@id, 'span_vFECHAFIRMA_')]")))
        filas = driver.find_elements(By.XPATH, "//span[contains(@id, 'span_vFECHAFIRMA_')]")

        indices = []
        for f in filas:
            id_completo = f.get_attribute("id")
            match = re.search(r'_(\d+)$', id_completo)
            if match:
                indices.append(int(match.group(1)))

        indices.sort(reverse=True)
        print(f" Encontradas {len(indices)} filas.")

        for idx_int in indices:
            idx_str = str(idx_int).zfill(4)
            id_fecha = f"span_vFECHAFIRMA_{idx_str}"
            id_boton = f"span_vDOCDOC_{idx_str}"

            try:
                fecha_actual = driver.find_element(By.ID, id_fecha).text.strip()
                if not driver.find_elements(By.ID, id_boton):
                    continue
                try:
                    nro_act = driver.find_element(By.ID, f"span_vNUMERO_{idx_str}").text.strip()
                except:
                    nro_act = f"fila_{idx_str}"
            except:
                print(f" ⚠️ Fila {idx_str} desapareció. Salto.")
                continue

            nombre_final = f"FECHA_{fecha_actual.replace('/','-')}_ID_{nro_act}.pdf"

            if nombre_final in archivos_ya_existentes:
                print(f" ⏭️ SKIP: Ya existe {nombre_final}")
                continue

            print(f" 📥 Intentando descargar {fecha_actual} - Act {nro_act}...")

            limpiar_temp(temp_download_path)
            btn_pdf = wait.until(EC.element_to_be_clickable((By.ID, id_boton)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_pdf)
            time.sleep(0.3)

            # Guardo handles antes del click
            handles_antes = set(driver.window_handles)
            driver.execute_script("arguments[0].click();", btn_pdf)

            # CAMBIO: Manejo descarga directa O pestaña nueva
            archivo_descargado = esperar_descarga_o_pestana(driver, temp_download_path, timeout=20)

            if archivo_descargado:
                ruta_destino = os.path.join(ruta_destino_final, nombre_final)
                if not os.path.exists(ruta_destino):
                    shutil.move(archivo_descargado, ruta_destino)
                    print(f" ✅ Guardado: {nombre_final}")
                    descargas_hechas += 1
                    archivos_ya_existentes.add(nombre_final)
                else:
                    os.remove(archivo_descargado)
            else:
                # No se descargó directo, veo si abrió pestaña
                if len(driver.window_handles) > len(handles_antes):
                    print(f" ⚠️ Se abrió en pestaña nueva. Forum no permite descarga directa.")
                    descargar_desde_pestana_pdf(driver, ventana_principal, ruta_destino_final, nombre_final)
                else:
                    print(f" ⚠️ Timeout: No se descargó PDF para fila {idx_str}")

            time.sleep(delay_entre_descargas)

        # PASO 4: Ir a la página anterior - VERSIÓN CON 4 SELECTORES
        if pagina_actual > 1:
            try:
                paginador = driver.find_element(By.CSS_SELECTOR, "ul.pagination")
                # CAMBIO: Pruebo 4 formas de encontrar el botón anterior
                selectores_ant = [
                    ".//a[contains(text(),'Ant')]",
                    ".//a[contains(text(),'‹')]",
                    ".//a[contains(text(),'<')]",
                    ".//li[contains(@class,'prev')]/a"
                ]
                btn_ant = None
                for sel in selectores_ant:
                    try:
                        btn_ant = paginador.find_element(By.XPATH, sel)
                        break
                    except:
                        continue

                if not btn_ant:
                    raise Exception("No encontré botón 'Anterior' con ningún selector")

                driver.execute_script("arguments[0].click();", btn_ant)
                wait.until(lambda d: get_pagina_actual() == pagina_actual - 1)
                pagina_actual -= 1
                print(f"➡️ Navegando a página {pagina_actual}")
                time.sleep(2)

            except Exception as e:
                print(f"⚠️ No pude ir a la página anterior: {repr(e)}. Corto el loop.")
                break
        else:
            print("🏁 Llegamos a la página 1. Fin.")
            break

    driver.switch_to.default_content()
    print(f"\n✨ Ciclo de vida finalizado. Se descargaron {descargas_hechas} archivos nuevos en orden cronológico.")
    return descargas_hechas

def ejecutar_barrido_cronologico(usuario_sistema, usuario_forum, clave_forum, lista_exptes):
    """
    Botón "DESCARGAR TODO" pero en orden cronológico correcto.
    """
    BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex"
    temp_download_path = os.path.join(BASE_PATH, "temp_downloads")
    os.makedirs(temp_download_path, exist_ok=True)

    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": temp_download_path,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "profile.default_content_settings.popups": 0,
        "profile.content_settings.exceptions.automatic_downloads.*.setting": 1
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("detach", True)
    # CAMBIO: Esto hace que Chrome no abra el visor de PDF
    options.add_argument("--disable-features=DownloadBubble,DownloadBubbleV2")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    # CAMBIO: Habilito descargas en headless/iframes via CDP
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": temp_download_path
    })

    wait = WebDriverWait(driver, 15)

    try:
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
        wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys(usuario_forum)
        driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys(clave_forum)
        print("\n--- LOGUEATE Y RESOLVÉ EL CAPTCHA ---")
        while "login" in driver.current_url: time.sleep(2)
        print("✅ Sesión iniciada.")

        for expte in lista_exptes:
            ruta_destino_final = os.path.join(BASE_PATH, "expedientes_clientes", usuario_sistema, "Juzgado Civil y Comercial N° 1", expte)
            os.makedirs(ruta_destino_final, exist_ok=True)

            driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
            time.sleep(2)

            btn_combo = wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")))
            btn_combo.click()
            time.sleep(1)
            driver.find_element(By.XPATH, "//span[contains(text(), 'Capital')]").click()

            descargar_ciclo_vida_cronologico(driver, wait, expte, ruta_destino_final, delay_entre_descargas=3)

            print(f"\n⏸️ Pausa de 5 seg antes del próximo expediente...")
            time.sleep(5)

    finally:
        driver.quit()

# EJECUCIÓN
ejecutar_barrido_cronologico("nico", "RicardoM", "1942", ["104604"])