# import time
# import os
# import shutil
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.common.action_chains import ActionChains
# from webdriver_manager.chrome import ChromeDriverManager

# def ejecutar_test_barrido_fecha(usuario_sistema, usuario_forum, clave_forum):
#     # 1. RUTAS (Asegurate que existan)
#     BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex\expedientes_clientes"
#     ruta_juzgado = os.path.join(BASE_PATH, usuario_sistema, "Juzgado Civil y Comercial N° 1")
#     temp_path = os.path.join(BASE_PATH, "temp_downloads")
#     if not os.path.exists(temp_path): os.makedirs(temp_path)

#     # Caso de prueba estrella: el incidente /2
#     exptes = [{"nro": "47215", "tipo": "I01", "sub": "/2"}]

#     options = webdriver.ChromeOptions()
#     prefs = {"download.default_directory": temp_path, "download.prompt_for_download": False}
#     options.add_experimental_option("prefs", prefs)
#     driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
#     wait = WebDriverWait(driver, 20)

#     try:
#         driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
#         print("\n--- LOGUEATE Y RESOLVÉ EL CAPTCHA ---")
#         while "login" in driver.current_url: time.sleep(2)

#         for item in exptes:
#             nro, tipo, sub = item["nro"], item["tipo"], item["sub"]
#             print(f"\n🚀 APUNTANDO A: {tipo} {nro}{sub}")
            
#             driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
#             time.sleep(2)

#             # Filtros (Capital)
#             wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop"))).click()
#             driver.find_element(By.XPATH, "//span[contains(text(), 'Capital')]").click()
            
#             # Buscar Nro
#             input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
#             input_nro.clear()
#             input_nro.send_keys(nro)
#             driver.find_element(By.ID, "BTN_SEARCH").click()
#             time.sleep(4)

#             # Puntería Láser para entrar al incidente correcto
#             sub_clean = sub.replace("/", "")
#             xpath_fila = f"//tr[td[2][contains(.,'{tipo}')] and td[4][contains(.,'{sub_clean}')]]//span[contains(text(),'{nro}')]"
#             celda = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_fila)))
#             ActionChains(driver).double_click(celda).perform()

#            # --- CORAZÓN DEL BARRIDO REFORZADO ---
#             print("⌛ Esperando que carguen las actuaciones...")
#             try:
#                 # Esperamos a que aparezca al menos una celda de fecha
#                 elemento_tabla = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id, 'vCAUSA_ACT_FECHA_')]")))
#                 driver.execute_script("arguments[0].scrollIntoView();", elemento_tabla)
#                 time.sleep(2) # Pausa de cortesía para que Genexus termine de dibujar
#             except Exception as e:
#                 print("❌ La tabla no cargó a tiempo. Reintentando con scroll...")
#                 driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#                 time.sleep(3)

#             # 1. Leemos la fecha de la primera fila (usando un selector más flexible)
#             try:
#                 # Intentamos obtener el texto de la primera fecha
#                 celda_fecha_0001 = driver.find_element(By.XPATH, "//*[contains(@id, 'vCAUSA_ACT_FECHA_0001')]")
#                 fecha_tope = celda_fecha_0001.text.strip()
                
#                 if not fecha_tope: # Si el texto está vacío, probamos con el atributo innerText
#                     fecha_tope = driver.execute_script("return arguments[0].innerText;", celda_fecha_0001).strip()
                
#                 print(f"📅 Detectada fecha más reciente: {fecha_tope}")
#             except:
#                 print("❌ No se pudo leer la fecha de la primera fila. ¿El expediente está vacío?")
#                 continue

#             fila_idx = 1
#             # ... resto del bucle while True ...
#             while True:
#                 suffix = str(fila_idx).zfill(4)
#                 try:
#                     # 2. Leemos fecha de la fila actual
#                     fecha_fila = driver.find_element(By.ID, f"span_vCAUSA_ACT_FECHA_{suffix}").text.strip()
                    
#                     if fecha_fila == fecha_tope:
#                         nro_act = driver.find_element(By.ID, f"span_vCAUSA_ACT_NUMERO_{suffix}").text.strip()
#                         print(f"📥 Descargando actuación {nro_act} (Fila {suffix})")
                        
#                         # Limpiar temp antes de clickear
#                         for f in os.listdir(temp_path): os.remove(os.path.join(temp_path, f))

#                         # Clic PDF
#                         btn_pdf = driver.find_element(By.ID, f"vDOCDOC_{suffix}")
#                         driver.execute_script("arguments[0].click();", btn_pdf)
                        
#                         # Esperar que aparezca el archivo en temp
#                         for _ in range(15):
#                             time.sleep(1)
#                             archivos = [f for f in os.listdir(temp_path) if not f.endswith('.tmp')]
#                             if archivos:
#                                 # Mover a la carpeta del expediente
#                                 folder_exp = os.path.join(ruta_juzgado, f"{nro}_{tipo}_{sub_clean}")
#                                 if not os.path.exists(folder_exp): os.makedirs(folder_exp)
                                
#                                 destino = os.path.join(folder_exp, f"{fecha_tope.replace('/','-')}_ID_{nro_act}.pdf")
#                                 shutil.move(os.path.join(temp_path, archivos[0]), destino)
#                                 print(f"✅ Sincronizado: {destino}")
#                                 break
                        
#                         fila_idx += 1 # Seguimos a la siguiente fila
#                     else:
#                         print(f"✋ Llegamos a una fecha vieja ({fecha_fila}). Fin del barrido.")
#                         break
#                 except:
#                     print("🏁 No hay más actuaciones en esta página.")
#                     break

#     finally:
#         driver.quit()
#         print("\n✨ Test finalizado.")

# # ¡DALE PLAY!
# ejecutar_test_barrido_fecha("nico", "RicardoM", "1942")

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

def ejecutar_sincronizacion_total(usuario_sistema, usuario_forum, clave_forum):
    # --- 1. CONFIGURACIÓN DE RUTAS ---
    BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex"
    temp_download_path = os.path.join(BASE_PATH, "temp_downloads")
    ruta_juzgado = os.path.join(BASE_PATH, "expedientes_clientes", usuario_sistema, "Juzgado Civil y Comercial N° 1")

    os.makedirs(temp_download_path, exist_ok=True)

    # Detectamos qué expedientes tenés en la carpeta (ej: "47215_I01_2")
    if not os.path.exists(ruta_juzgado):
        print(f"❌ No se encontró la ruta: {ruta_juzgado}")
        return

    carpetas_exp = [f for f in os.listdir(ruta_juzgado) if os.path.isdir(os.path.join(ruta_juzgado, f))]
    print(f"📂 Carpetas detectadas para sincronizar: {carpetas_exp}")

    # --- 2. CONFIGURAR NAVEGADOR ---
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
        # --- 3. LOGIN ---
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
        wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys(usuario_forum)
        driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys(clave_forum)

        print("\n--- LOGUEATE Y RESOLVÉ EL CAPTCHA ---")
        while "login" in driver.current_url: time.sleep(2)
        print("✅ Sesión iniciada.")

        # --- 4. BUCLE DE EXPEDIENTES ---
        for carpeta in carpetas_exp:
            try:
                # Separamos el nombre (Ej: 47215_I01_2 -> nro=47215, tipo=I01, sub=2)
                partes = carpeta.split("_")
                if len(partes) < 3: continue
                nro_exp, tipo_exp, sub_exp = partes[0], partes[1], partes[2]

                print(f"\n🚀 APUNTANDO LÁSER A: {nro_exp} | Tipo: {tipo_exp} | Inc: {sub_exp}")
                
                driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
                time.sleep(2)

                # Localidad Capital
                btn_combo = wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")))
                btn_combo.click()
                time.sleep(1)
                driver.find_element(By.XPATH, "//span[contains(text(), 'Capital')]").click()

                # Buscar Nro
                input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
                input_nro.clear()
                input_nro.send_keys(nro_exp)
                driver.find_element(By.ID, "BTN_SEARCH").click()
                time.sleep(3)

                # --- EL RAYO LÁSER (Puntería Quirúrgica) ---
                # Buscamos la fila que coincida con el Tipo (Col 2) y el Incidente (Col 4)
                xpath_laser = f"//tr[td[2][contains(.,'{tipo_exp}')] and td[4][contains(.,'{sub_exp}')]]//span[contains(text(),'{nro_exp}')]"
                celda_objetivo = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_laser)))
                ActionChains(driver).double_click(celda_objetivo).perform()

                print("⌛ Esperando grilla interna...")
                time.sleep(4)

                # Cambio a Iframe (Tu clave del éxito)
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                if iframes:
                    driver.switch_to.frame(iframes[0])
                    time.sleep(2)

                # --- LÓGICA DE FECHAS REPETIDAS ---
                fecha_referencia = driver.find_element(By.ID, "span_vFECHAFIRMA_0001").text.strip()
                print(f"📅 Fecha tope: {fecha_referencia}. Iniciando barrido...")

                fila_idx = 1
                while True:
                    idx_str = str(fila_idx).zfill(4)
                    id_fecha = f"span_vFECHAFIRMA_{idx_str}"
                    id_boton = f"span_vDOCDOC_{idx_str}"

                    # Si no existe la fila, salimos del expediente
                    if not driver.find_elements(By.ID, id_fecha): break

                    fecha_actual = driver.find_element(By.ID, id_fecha).text.strip()

                    # Si la fecha coincide, descargamos
                    if fecha_actual == fecha_referencia:
                        if not driver.find_elements(By.ID, id_boton): break

                        try:
                            nro_act = driver.find_element(By.ID, f"span_vNUMERO_{idx_str}").text.strip()
                        except:
                            nro_act = f"fila_{idx_str}"

                        print(f"📥 Descargando {nro_act}...")

                        # Limpiar temp
                        for f in os.listdir(temp_download_path): os.remove(os.path.join(temp_download_path, f))

                        # Clic PDF
                        driver.find_element(By.ID, id_boton).click()
                        time.sleep(5)

                        # Mover archivo
                        archivos = [a for a in os.listdir(temp_download_path) if not a.endswith('.tmp') and not a.endswith('.crdownload')]
                        if archivos:
                            ruta_destino_folder = os.path.join(ruta_juzgado, carpeta)
                            nombre_final = f"FECHA_{fecha_referencia.replace('/','-')}_ID_{nro_act}.pdf"
                            shutil.move(os.path.join(temp_download_path, archivos[0]), os.path.join(ruta_destino_folder, nombre_final))
                            print(f"✅ Sincronizado: {nombre_final}")
                        
                        fila_idx += 1
                    else:
                        print(f"⏭️ Fecha distinta ({fecha_actual}). Fin de novedades.")
                        break

                # Salir del iframe para el siguiente expediente
                driver.switch_to.default_content()

            except Exception as e:
                print(f"⚠️ Error en {carpeta}: {e}")
                driver.switch_to.default_content() # Por si falló dentro del iframe
                continue

        print("\n✨ LexView Pro terminó la sincronización de toda tu carpeta.")

    finally:
        driver.quit()

# --- EJECUCIÓN ---
ejecutar_sincronizacion_total("nico", "RicardoM", "1942")