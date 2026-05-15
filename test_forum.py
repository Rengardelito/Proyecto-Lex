from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import shutil

def ejecutar_barrido_automatico(usuario_sistema, usuario_forum, clave_forum):
    # 1. CONFIGURACIÓN DE RUTAS
    BASE_PATH = r"C:\Users\nico_\OneDrive\Escritorio\Proyecto Lex\expedientes_clientes"
    ruta_usuario = os.path.join(BASE_PATH, usuario_sistema)
    nombre_juzgado_carpeta = "Juzgado Civil y Comercial N° 1"
    ruta_juzgado = os.path.join(ruta_usuario, nombre_juzgado_carpeta)
    
    # Carpeta temporal para descargas
    temp_download_path = os.path.join(BASE_PATH, "temp_downloads")
    if not os.path.exists(temp_download_path): os.makedirs(temp_download_path)

    # 2. DETECTAR EXPEDIENTES REALES EN TU DISCO
    # Esto lee las carpetas 260115, 234915, etc.
    if not os.path.exists(ruta_juzgado):
        print(f"❌ No se encontró la carpeta del juzgado en: {ruta_juzgado}")
        return

    expedientes_a_sincronizar = [f for f in os.listdir(ruta_juzgado) if os.path.isdir(os.path.join(ruta_juzgado, f))]
    print(f"📂 Expedientes detectados en tu carpeta: {expedientes_a_sincronizar}")

    # 3. CONFIGURAR NAVEGADOR
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
        # 4. LOGIN ÚNICO
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login") 
        wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys(usuario_forum)
        driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys(clave_forum)
        
        print("\n--- PASO 1: LOGUEATE Y RESOLVÉ EL CAPTCHA ---")
        while "login" in driver.current_url: time.sleep(2)
        print("✅ Sesión iniciada. Empezando barrido...")

        # 5. BUCLE PARA CADA EXPEDIENTE
        for expte in expedientes_a_sincronizar:
            print(f"\n🔍 Procesando expediente: {expte}")
            
            try:
                # Ir a consulta
                driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
                time.sleep(2)

                # Seleccionar Localidad (Capital)
                btn_combo = wait.until(EC.element_to_be_clickable((By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")))
                btn_combo.click()
                time.sleep(1)
                driver.find_element(By.XPATH, "//span[contains(text(), 'Capital')]").click()
                
                # Escribir número y Buscar
                input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
                input_nro.clear()
                input_nro.send_keys(expte)
                driver.find_element(By.ID, "BTN_SEARCH").click()
                
                # Entrar al expediente (Doble clic en el resultado)
                time.sleep(2)
                celda_link = wait.until(EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '{expte}')]")))
                webdriver.ActionChains(driver).double_click(celda_link).perform()
                
                # Descargar el PDF más reciente (el primero de la lista)
                print(f"📥 Descargando actuación para {expte}...")
                btn_pdf = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(@id, 'vDOCDOC_0001')]")))
                btn_pdf.click()
                
                # Esperar descarga y mover archivo
                time.sleep(4) 
                archivos = os.listdir(temp_download_path)
                if archivos:
                    archivo_reciente = os.path.join(temp_download_path, archivos[0])
                    ruta_destino = os.path.join(ruta_juzgado, expte, f"actualizacion_{int(time.time())}.pdf")
                    shutil.move(archivo_reciente, ruta_destino)
                    print(f"✅ Guardado en: {ruta_destino}")
                
            except Exception as e:
                print(f"⚠️ Saltando {expte} por error: {e}")
                continue

        print("\n✨ ¡Barrido completo finalizado!")

    finally:
        driver.quit()

# EJECUCIÓN
ejecutar_barrido_automatico("nico", "RicardoM", "1942")