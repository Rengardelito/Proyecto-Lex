import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def test_recolector_solo():
    # 1. Configuración del Driver
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 15)
    
    matricula_test = "3232"

    try:
        # 2. Login Manual
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
        print("Esperando que te loguees manualmente...")
        
        while "login" in driver.current_url:
            time.sleep(2)

        # 3. Navegar directo a la URL de Notificaciones
        print("Navegando a la pestaña de Notificaciones...")
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.notificaciones")
        time.sleep(5)

        # 4. Configurar Filtros
        print("Configurando filtros...")
        
        # A. Seleccionar Localidad (Capital)
        btn_combo_loc = wait.until(EC.element_to_be_clickable((By.ID, "COMBO_ID_LOCALIDADContainer_btnGroupDrop")))
        btn_combo_loc.click()
        time.sleep(1)
        opcion_capital = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Capital')]")))
        opcion_capital.click()
        print("✅ Localidad: Capital seleccionada.")
        
        # B. Llenar Matrícula
        input_mat = wait.until(EC.element_to_be_clickable((By.ID, "vMATRICULA")))
        input_mat.click()
        input_mat.clear()
        for caracter in matricula_test:
            input_mat.send_keys(caracter)
            time.sleep(0.1)
        print(f"✅ Matrícula {matricula_test} ingresada.")
        
        # C. Clic en Buscar
        btn_buscar = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@value='Buscar']")))
        btn_buscar.click()
        print("⌛ Buscando resultados...")
        time.sleep(7) 

        # 5. EXTRACCIÓN "ASPIRADORA"
        print("Iniciando aspiradora de datos...")
        
        # Intentamos capturar el texto de la tabla o del cuerpo de la página
        try:
            # Buscamos la tabla de resultados
            tabla = driver.find_elements(By.XPATH, "//table[contains(@class, 'Grid')]")
            if tabla:
                texto_fuente = tabla[0].text
                print("Extrayendo datos de la tabla...")
            else:
                texto_fuente = driver.find_element(By.TAG_NAME, "body").text
                print("Tabla no detectada, extrayendo del cuerpo de la página...")

            # El imán de números (Busca de 5 a 6 dígitos)
            patron_nros = r'\b\d{5,6}\b'
            encontrados = re.findall(patron_nros, texto_fuente)
            
            # Limpieza: quitamos duplicados, años y la matrícula del test
            excluir = ['2025', '2026', '3232', '2024']
            lista_final = sorted(list(set([n for n in encontrados if n not in excluir])))

            print("\n" + "="*50)
            print(f"🎯 RESULTADO DEL RADAR LEXVIEW:")
            if lista_final:
                print(f"✅ ¡ÉXITO! Detectados {len(lista_final)} expedientes.")
                print(f"Lista: {lista_final}")
            else:
                print("⚠️ No se detectaron números. Revisá si la tabla tiene datos.")
            print("="*50 + "\n")

        except Exception as e_inner:
            print(f"❌ Error en la extracción: {e_inner}")

    except Exception as e:
        print(f"❌ Error general en el proceso: {e}")
    
    finally:
        input("Presioná Enter para cerrar el navegador...")
        driver.quit()

if __name__ == "__main__":
    test_recolector_solo()