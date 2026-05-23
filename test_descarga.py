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

# def ejecutar_test_104604(usuario_sistema, usuario_forum, clave_forum):
#     BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex"
#     temp_download_path = os.path.join(BASE_PATH, "temp_downloads")
#     ruta_destino_final = os.path.join(BASE_PATH, "expedientes_clientes", usuario_sistema, "Juzgado Civil y Comercial N° 1", "104604")

#     os.makedirs(temp_download_path, exist_ok=True)
#     os.makedirs(ruta_destino_final, exist_ok=True)

#     for f in os.listdir(temp_download_path):
#         os.remove(os.path.join(temp_download_path, f))

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

#         driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
#         time.sleep(2)

#         btn_combo = wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")))
#         btn_combo.click()
#         time.sleep(1)
#         driver.find_element(By.XPATH, "//span[contains(text(), 'Capital')]").click()

#         input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
#         input_nro.clear()
#         input_nro.send_keys("104604")
#         driver.find_element(By.ID, "BTN_SEARCH").click()

#         time.sleep(2)
#         celda_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), '104604')]")))
#         ActionChains(driver).double_click(celda_link).perform()

#         print("\n🔎 Esperando grilla de actuaciones...")
#         time.sleep(4)

#         iframes = driver.find_elements(By.TAG_NAME, "iframe")
#         if iframes:
#             driver.switch_to.frame(iframes[0])
#             time.sleep(2)

#         # ID real de fecha según tu captura
#         fecha_referencia = driver.find_element(By.ID, "span_vFECHAFIRMA_0001").text.strip()
#         print(f"📅 La fecha a buscar es: {fecha_referencia}")

#         fila_idx = 1
#         descargas_hechas = 0

#         while True:
#             idx_str = str(fila_idx).zfill(4)
#             id_fecha = f"span_vFECHAFIRMA_{idx_str}"
#             id_boton = f"span_vDOCDOC_{idx_str}" # CORREGIDO: lleva span_ adelante

#             if not driver.find_elements(By.ID, id_fecha):
#                 print(f"✋ No hay más filas. Se procesaron {fila_idx - 1} filas.")
#                 break

#             fecha_actual = driver.find_element(By.ID, id_fecha).text.strip()

#             if fecha_actual == fecha_referencia:
#                 if not driver.find_elements(By.ID, id_boton):
#                     print(f"✋ No existe {id_boton}. Fin de archivos de esta fecha.")
#                     break

#                 try:
#                     nro_act = driver.find_element(By.ID, f"span_vNUMERO_{idx_str}").text.strip()
#                 except:
#                     nro_act = f"fila_{idx_str}"

#                 print(f"📥 Descargando actuación {nro_act} (Fila {idx_str})...")

#                 # TU MISMA LÓGICA EXACTA
#                 btn_pdf = wait.until(EC.element_to_be_clickable((By.ID, id_boton)))
#                 btn_pdf.click()

#                 time.sleep(4)
#                 archivos = os.listdir(temp_download_path)
#                 if archivos:
#                     archivo_reciente = os.path.join(temp_download_path, archivos[0])
#                     nombre_final = f"FECHA_{fecha_referencia.replace('/','-')}_ID_{nro_act}.pdf"
#                     ruta_destino = os.path.join(ruta_destino_final, nombre_final)
#                     shutil.move(archivo_reciente, ruta_destino)
#                     print(f"✅ Guardado en: {ruta_destino}")
#                     descargas_hechas += 1
#                 else:
#                     print(f"⚠️ No apareció archivo para fila {idx_str}")
#                     break
#             else:
#                 print(f"⏭️ Fila {idx_str} es de otra fecha: {fecha_actual}. Corto el loop.")
#                 break

#             fila_idx += 1

#         print(f"\n✨ Test finalizado. Se descargaron {descargas_hechas} archivos del {fecha_referencia}")

#     finally:
#         driver.switch_to.default_content()
#         driver.quit()

# ejecutar_test_104604("nico", "RicardoM", "1942")

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import shutil

def ejecutar_test_104604(usuario_sistema, usuario_forum, clave_forum):
    # --- CONFIGURACIÓN DE RUTAS (Tu estructura original) ---
    BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex"
    temp_download_path = os.path.join(BASE_PATH, "temp_downloads")
    
    # Definimos el número de expediente fijo para esta prueba
    expte_nro = "104604"
    
    # Ruta dinámica: si el expediente no existe, el código lo crea
    ruta_destino_final = os.path.join(
        BASE_PATH, 
        "expedientes_clientes", 
        usuario_sistema, 
        "Juzgado Civil y Comercial N° 1", 
        expte_nro
    )

    # Creamos las carpetas si no existen
    os.makedirs(temp_download_path, exist_ok=True)
    os.makedirs(ruta_destino_final, exist_ok=True)

    # Limpiamos temporales antes de arrancar
    for f in os.listdir(temp_download_path):
        os.remove(os.path.join(temp_download_path, f))

    # --- CONFIGURAR NAVEGADOR ---
    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": temp_download_path,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True
    }
    options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 15)

    try:
        # --- LOGIN ---
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
        wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys(usuario_forum)
        driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys(clave_forum)

        print("\n--- LOGUEATE Y RESOLVÉ EL CAPTCHA ---")
        while "login" in driver.current_url: time.sleep(2)
        print("✅ Sesión iniciada.")

        # --- BÚSQUEDA ---
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
        time.sleep(2)

        btn_combo = wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")))
        btn_combo.click()
        time.sleep(1)
        driver.find_element(By.XPATH, "//span[contains(text(), 'Capital')]").click()

        input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
        input_nro.clear()
        input_nro.send_keys(expte_nro)
        driver.find_element(By.ID, "BTN_SEARCH").click()

        time.sleep(2)
        celda_link = wait.until(EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '{expte_nro}')]")))
        ActionChains(driver).double_click(celda_link).perform()

        print("\n🔎 Esperando grilla de actuaciones...")
        time.sleep(4)

        # MANEJO DE IFRAMES (La clave que lo hizo funcionar)
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            driver.switch_to.frame(iframes[0])
            time.sleep(2)

        # ID real de fecha según tu hallazgo
        fecha_referencia = driver.find_element(By.ID, "span_vFECHAFIRMA_0001").text.strip()
        print(f"📅 La fecha a buscar es: {fecha_referencia}")

        fila_idx = 1
        descargas_hechas = 0

        while True:
            idx_str = str(fila_idx).zfill(4)
            id_fecha = f"span_vFECHAFIRMA_{idx_str}"
            id_boton = f"span_vDOCDOC_{idx_str}" 

            if not driver.find_elements(By.ID, id_fecha):
                print(f"✋ No hay más filas. Se procesaron {fila_idx - 1} filas.")
                break

            fecha_actual = driver.find_element(By.ID, id_fecha).text.strip()

            if fecha_actual == fecha_referencia:
                if not driver.find_elements(By.ID, id_boton):
                    print(f"✋ No existe el botón en la fila {idx_str}. Fin de archivos de esta fecha.")
                    break

                try:
                    # Intentamos sacar el número de actuación para el nombre del archivo
                    nro_act = driver.find_element(By.ID, f"span_vNUMERO_{idx_str}").text.strip()
                except:
                    nro_act = f"fila_{idx_str}"

                print(f"📥 Descargando actuación {nro_act} (Fila {idx_str})...")

                # Limpieza rápida del temporal antes de cada clic
                for f in os.listdir(temp_download_path):
                    os.remove(os.path.join(temp_download_path, f))

                # CLIC EN EL PDF
                btn_pdf = wait.until(EC.element_to_be_clickable((By.ID, id_boton)))
                btn_pdf.click()

                # Espera técnica de descarga
                time.sleep(5) 
                
                archivos = os.listdir(temp_download_path)
                if archivos:
                    # Filtramos archivos temporales de Chrome
                    archivos_reales = [a for a in archivos if not a.endswith('.tmp') and not a.endswith('.crdownload')]
                    if archivos_reales:
                        archivo_reciente = os.path.join(temp_download_path, archivos_reales[0])
                        # Nombre con fecha limpia e ID de actuación
                        nombre_final = f"FECHA_{fecha_referencia.replace('/','-')}_ID_{nro_act}.pdf"
                        ruta_destino = os.path.join(ruta_destino_final, nombre_final)
                        
                        # Movemos el archivo a su carpeta definitiva
                        shutil.move(archivo_reciente, ruta_destino)
                        print(f"✅ Sincronizado: {nombre_final}")
                        descargas_hechas += 1
                else:
                    print(f"⚠️ El archivo no apareció a tiempo para la fila {idx_str}")
            else:
                print(f"⏭️ Fila {idx_str} es de otra fecha ({fecha_actual}). Corto el loop.")
                break

            fila_idx += 1

        print(f"\n✨ Sincronización completa. Total bajado: {descargas_hechas} archivos.")

    finally:
        # Volvemos al contenido principal y cerramos
        driver.switch_to.default_content()
        driver.quit()

# EJECUCIÓN
ejecutar_test_104604("nico", "RicardoM", "1942")