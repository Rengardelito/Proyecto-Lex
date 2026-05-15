import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def test_navegador_exptes():
    # 1. Configuración del Driver
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 15)
    
    # LISTA DE PRUEBA (Copiamos algunos de los que detectó el radar)
    lista_a_procesar = ['104604', '106353', '107303'] 

    try:
        # 2. Login Manual
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.login")
        print("Logueate y esperá a estar en el Inicio...")
        while "login" in driver.current_url:
            time.sleep(2)

        # 3. Bucle de Navegación
        for expte in lista_a_procesar:
            print(f"\n🔎 Procesando Expediente: {expte}")
            
            # Vamos directo a la URL de causas
            driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.causass")
            time.sleep(5)

            try:
                # A. Seleccionar Localidad (Capital) 
                print("Configurando Localidad...")
                btn_combo_loc = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@id, 'LOCALIDAD')]//button")))
                driver.execute_script("arguments[0].click();", btn_combo_loc)
                time.sleep(2)
                
                opcion_capital = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Capital')]")))
                opcion_capital.click()
                print("✅ Localidad: Capital seleccionada.")
                
                time.sleep(2)

                # B. Poner el Número de Expediente (ID CORRECTO: vCAUSANRO)
                print(f"Ingresando expediente {expte}...")
                input_nro = wait.until(EC.visibility_of_element_located((By.ID, "vCAUSANRO")))
                input_nro.clear()
                
                # Escribimos con pausa para que el sistema procese el número
                for n in expte:
                    input_nro.send_keys(n)
                    time.sleep(0.1)
                
                print(f"✅ Número {expte} ingresado.")

                # C. Clic en Buscar
                btn_buscar = wait.until(EC.element_to_be_clickable((By.NAME, "BTN_SEARCH")))
                btn_buscar.click()
                print("⌛ Buscando resultados...")
                time.sleep(5)

                # D. Entrar al expediente
                btn_entrar = wait.until(EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '{expte}')]")))
                btn_entrar.click()
                
                print(f"🚀 ¡ESTAMOS ADENTRO del expediente {expte}!")
                time.sleep(5) 

            except Exception as e_interno:
                print(f"❌ Error procesando el número {expte}: {e_interno}")

    except Exception as e:
        print(f"❌ Error general en el navegador: {e}")
    
    finally:
        print("\n--- Tarea finalizada ---")
        input("Presioná Enter para cerrar el navegador...")
        driver.quit()

if __name__ == "__main__":
    test_navegador_exptes()