from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
# bots/forum_driver.py
import time as t_mod
import time
import shutil
import os
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import config
def normalizar_juzgado(nombre):
    """Elimina 'JUZGADO ' del inicio para unificar nombres."""
    import re
    if not nombre:
        return nombre
    return re.sub(r'^JUZGADO\s+', '', nombre.strip(), flags=re.IGNORECASE).upper()

def crear_driver(temp_download_path=None):
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    if temp_download_path:
        prefs = {
            "download.default_directory": temp_download_path,
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True
        }
        options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(config.SELENIUM_TIMEOUT)
    return driver


def login_forum(driver, forum_user, forum_pass):
    try:
        driver.get(config.FORUM_URL_LOGIN)
        wait = WebDriverWait(driver, 20)

        print("⏳ Esperando campos de login...")
        wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME")))
        time.sleep(2)

        wait.until(EC.presence_of_element_located((By.ID, "vSECUSERNAME"))).send_keys(forum_user)
        driver.find_element(By.ID, "vSECUSERPASSWORD").send_keys(forum_pass)
        print("✍️ Credenciales cargadas. Resolvé el captcha y presioná Entrar...")

        wait_larga = WebDriverWait(driver, 180)
        wait_larga.until(EC.url_changes(config.FORUM_URL_LOGIN))

        print("✅ Login exitoso.")
        return True

    except Exception as e:
        print(f"❌ Error en login: {e}")
        return False


def _seleccionar_capital(driver, wait):
    """Selecciona 'Capital' en el combo de localidad. Reutilizable."""
    wait.until(EC.element_to_be_clickable(
        (By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")
    )).click()
    wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//span[contains(text(), 'Capital')]")
    )).click()


def _paginar_siguiente(driver):
    """
    Intenta ir a la página siguiente. 
    Retorna True si paginó, False si era la última página.
    """
    try:
        btn_sig = driver.find_element(
            By.XPATH,
            "//a[contains(text(),'Sig') or contains(@class,'next')][not(contains(@class,'disabled'))]"
        )
        driver.execute_script("arguments[0].click();", btn_sig)
        time.sleep(2)
        return True
    except NoSuchElementException:
        return False


def buscar_expediente(driver, nro_solo, tipo_codigo=None):
    """
    Busca un expediente por número y opcionalmente por tipo/código.
    
    nro_solo:    solo el número (ej: "41481") — sin año, sin código
    tipo_codigo: prefijo tipo (ej: "C01", "I01", "EXP") — opcional pero recomendado
    
    Pagina automáticamente hasta encontrarlo o agotar los resultados.
    Retorna dict con datos del expediente o None si no se encontró.
    """
    try:
        nro_limpio = nro_solo.split('-')[0]

        driver.get(config.FORUM_URL_CAUSAS)
        wait = WebDriverWait(driver, 15)
        _seleccionar_capital(driver, wait)

        input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
        input_nro.clear()
        time.sleep(0.3)
        input_nro.send_keys(nro_limpio)
        time.sleep(0.5)

        # Verificar que el campo tiene el valor antes de buscar
        valor_actual = input_nro.get_attribute('value')
        if not valor_actual or valor_actual.strip() == '':
            input_nro.send_keys(nro_limpio)
            time.sleep(0.5)

        driver.find_element(By.ID, "BTN_SEARCH").click()

        tipo_normalizado = tipo_codigo.upper().replace(" ", "") if tipo_codigo else None
        pagina = 1

        while True:
            wait.until(EC.presence_of_element_located(
                (By.XPATH, "//table[contains(@class,'Grid')]//tbody/tr")
            ))
            time.sleep(0.8)

            filas = driver.find_elements(
                By.XPATH, "//table[contains(@class,'Grid')]//tbody/tr"
            )

            for fila in filas:
                try:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    if len(celdas) < 5:
                        continue

                    organismo = celdas[0].text.strip()
                    tipo_fila = celdas[1].text.strip().upper().replace(" ", "")
                    nro_fila  = celdas[2].text.strip()
                    anio_fila = celdas[3].text.strip()
                    caratula  = celdas[4].text.strip()

                    if nro_fila != nro_limpio:
                        continue

                    if tipo_normalizado and tipo_fila != tipo_normalizado:
                        continue

                    nro_completo = f"{nro_limpio}-{anio_fila}" if anio_fila else nro_limpio
                    return {
                        "nro_completo": nro_completo,
                        "tipo": tipo_fila,
                        "juzgado": normalizar_juzgado(organismo.replace("/", "-")),
                        "caratula": caratula.upper(),
                        "secretaria": "SECRETARIA UNICA"
                    }
                except Exception:
                    continue

            print(f"🔄 buscar_expediente: no encontrado en página {pagina}, paginando...")
            if not _paginar_siguiente(driver):
                break
            pagina += 1

        print(f"⚠️ No se encontró tipo={tipo_codigo} nro={nro_solo} en {pagina} páginas")
        return None

    except Exception as e:
        print(f"⚠️ Error en buscar_expediente: {e}")
        return None

def entrar_a_expediente(driver, nro_expte, tipo_codigo=None):
    """
    Entra al expediente haciendo doble click en la fila correcta.
    
    nro_expte:   "41481-99" o "41481"
    tipo_codigo: "C01", "I01", "EXP", etc. — si se pasa, filtra por tipo además de número+año
    
    Pagina automáticamente hasta encontrar la fila correcta.
    Retorna True si logró entrar, False si falló.
    """
    from selenium.webdriver.common.action_chains import ActionChains

    def _intentar(driver, nro_expte, tipo_codigo):
        nro_solo = nro_expte.split('-')[0]
        anio     = nro_expte.split('-')[1] if '-' in nro_expte else ""
        tipo_normalizado = tipo_codigo.upper().replace(" ", "") if tipo_codigo else None

        driver.get(config.FORUM_URL_CAUSAS)
        wait = WebDriverWait(driver, 15)
        _seleccionar_capital(driver, wait)

        input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
        input_nro.clear()
        input_nro.send_keys(nro_solo)
        driver.find_element(By.ID, "BTN_SEARCH").click()

        pagina = 1

        while True:
            wait.until(EC.presence_of_element_located(
                (By.XPATH, "//table[contains(@class,'Grid')]//tbody/tr")
            ))
            time.sleep(0.8)

            filas = driver.find_elements(
                By.XPATH, "//table[contains(@class,'Grid')]//tbody/tr"
            )

            for fila in filas:
                try:
                    celdas = fila.find_elements(By.TAG_NAME, "td")
                    if len(celdas) < 4:
                        continue

                    # Columnas Forum causas: Organismo | Tipo | Número | Año | Carátula
                    tipo_fila = celdas[1].text.strip().upper().replace(" ", "")
                    nro_fila  = celdas[2].text.strip()
                    anio_fila = celdas[3].text.strip()

                    # Filtro por número (obligatorio)
                    if nro_fila != nro_solo:
                        continue

                    # Filtro por año (si lo tenemos)
                    if anio and anio_fila != anio:
                        continue

                    # Filtro por tipo/código (si lo tenemos)
                    if tipo_normalizado and tipo_fila != tipo_normalizado:
                        continue

                   # ✅ Fila correcta — doble click en la celda del número
                    celda_nro = celdas[2]
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", celda_nro)
                    time.sleep(0.3)
                    ActionChains(driver).double_click(celda_nro).perform()
                   

                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//table//tbody/tr"))
                    )
                    return True

                except Exception:
                    continue

            # No encontrado en esta página — intentar siguiente
            print(f"🔄 entrar_a_expediente: no encontrado en página {pagina}, paginando...")
            if not _paginar_siguiente(driver):
                break
            pagina += 1

        print(f"❌ No se encontró tipo={tipo_codigo} nro={nro_expte} en {pagina} páginas")
        return False

    for intento in range(2):
        try:
            return _intentar(driver, nro_expte, tipo_codigo)
        except Exception as e:
            if intento == 0:
                print(f"⚠️ Reintentando {nro_expte}...")
                time.sleep(1)
            else:
                print(f"❌ Error entrando a {nro_expte}: {e}")
                return False


def descargar_pdfs_nuevos(driver, ruta_local, temp_download_path):
    descargas = 0
    main_window = driver.current_window_handle

    try:
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
        time.sleep(0.5)
    except:
        print("❌ No se detectó tabla de actuaciones")
        return 0

    idx_map = {}
    try:
        headers = driver.find_elements(By.XPATH, "//table[contains(@class, 'Grid')]//tr[1]/th")
        for i, h in enumerate(headers):
            texto = h.text.strip().upper()
            if 'FECHA' in texto:
                idx_map['fecha'] = i
            elif any(x in texto for x in ['EXTRACTO', 'DETALLE', 'DESCRIPCION']):
                idx_map['extracto'] = i
            elif any(x in texto for x in ['TIPO', 'DOCUMENTO', 'DOC']):
                idx_map['tipo'] = i

        if 'fecha' not in idx_map:
            print("⚠️ No se encontró columna Fecha")
            return 0
    except Exception as e:
        print(f"Error detectando headers: {e}")
        return 0

    filas = driver.find_elements(By.XPATH, "//table//tbody/tr")
    print(f"🔍 {len(filas)} filas en tabla de actuaciones")

    fecha_mas_reciente = None
    for fila in filas:
        try:
            celdas = fila.find_elements(By.TAG_NAME, "td")
            if len(celdas) <= idx_map['fecha']:
                continue
            fecha_str = celdas[idx_map['fecha']].text.strip()
            if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', fecha_str):
                fecha_mas_reciente = fecha_str
                break
        except Exception:
            continue

    if not fecha_mas_reciente:
        print("⚠️ No se encontró ninguna fecha válida en la tabla")
        return 0

    print(f"📅 Fecha más reciente: {fecha_mas_reciente}")

    archivos_locales = set()
    if os.path.exists(ruta_local):
        for f in os.listdir(ruta_local):
            if f.lower().endswith('.pdf'):
                archivos_locales.add(f.replace('.pdf', '').strip())

    fecha_dt = datetime.strptime(fecha_mas_reciente, "%d/%m/%Y")
    fecha_iso = fecha_dt.strftime("%Y-%m-%d")

    fila_idx = 0
    while fila_idx < len(filas):
        fila = filas[fila_idx]
        try:
            celdas = fila.find_elements(By.TAG_NAME, "td")
            if len(celdas) < 3:
                fila_idx += 1
                continue

            fecha_str = celdas[idx_map['fecha']].text.strip()
            if fecha_str != fecha_mas_reciente:
                fila_idx += 1
                continue

            tipo_str = ""
            if 'extracto' in idx_map and idx_map['extracto'] < len(celdas):
                tipo_str = celdas[idx_map['extracto']].text.strip()[:50]
            elif 'tipo' in idx_map and idx_map['tipo'] < len(celdas):
                tipo_str = celdas[idx_map['tipo']].text.strip()[:50]
            elif len(celdas) > 2:
                tipo_str = celdas[2].text.strip()[:50]

            nombre_check = f"{fecha_iso} - {tipo_str}".replace("/", "_").replace(":", "").replace("\\", "").strip()
            if nombre_check in archivos_locales:
                print(f"⏩ Ya existe: {nombre_check}")
                fila_idx += 1
                continue

            nombre_final = f"{fecha_iso} - {tipo_str}.pdf".replace("/", "_").replace(":", "").replace("\\", "")
            dest_final = os.path.join(ruta_local, nombre_final)

            print(f"📥 Descargando: {nombre_final}")
            archivos_antes = set(os.listdir(temp_download_path))

            try:
                boton = fila.find_element(By.XPATH, ".//a")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", boton)

                pdf_movido = False
                for _ in range(15):
                    time.sleep(1)
                    archivos_despues = set(os.listdir(temp_download_path))
                    nuevos = archivos_despues - archivos_antes
                    pdfs_nuevos = [f for f in nuevos if f.endswith('.pdf') and not f.endswith('.crdownload')]
                    if pdfs_nuevos:
                        origen = os.path.join(temp_download_path, pdfs_nuevos[0])
                        shutil.move(origen, dest_final)
                        print(f"✅ Guardado: {nombre_final}")
                        descargas += 1
                        pdf_movido = True
                        archivos_locales.add(nombre_final.replace('.pdf', '').strip())
                        break

                if not pdf_movido:
                    print(f"⚠️ No llegó el PDF para fila {fila_idx}")

                if len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.close()
                    driver.switch_to.window(main_window)

            except Exception as e:
                print(f"⚠️ Error descargando fila {fila_idx}: {e}")
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.close()
                    driver.switch_to.window(main_window)

        except Exception as e:
            print(f"Error en fila {fila_idx}: {e}")

        fila_idx += 1

    return descargas

def leer_caratula_desde_pagina(driver) -> str:
    """
    Lee la carátula del expediente desde la página actual de Forum
    (la que muestra Nro. Expediente, Carátula, Fecha Ingreso, Ubicación Actual).
    
    Se llama DESPUÉS de entrar al expediente con entrar_a_expediente() o
    _entrar_a_expediente_actualizador(), sin necesidad de hacer una búsqueda extra.
    
    Retorna la carátula en mayúsculas, o "SIN CARATULAR" si no la encuentra.
    """
    try:
        # Forum muestra los datos del expediente en una tabla con celdas "label: valor"
        # La carátula está en una celda que sigue a un th/td con texto "Carátula"
        intentos = [
            # Intento 1: celda que sigue a un elemento con texto "Carátula"
            "//td[contains(text(),'Carátula') or contains(text(),'Caratula')]"
            "/following-sibling::td[1]",
            # Intento 2: span o div con clase que contenga caratula
            "//*[contains(@id,'CARATULA') or contains(@name,'CARATULA')]",
            # Intento 3: buscar en la fila de info del expediente
            "//tr[td[contains(.,'Carátula') or contains(.,'Caratula')]]/td[2]",
        ]

        for xpath in intentos:
            try:
                elem = driver.find_element(By.XPATH, xpath)
                texto = elem.text.strip()
                if texto and len(texto) > 3:
                    return texto.upper()
            except Exception:
                continue

        # Fallback: buscar el texto "Carátula" y tomar el siguiente texto visible
        try:
            elementos = driver.find_elements(By.XPATH, "//*[text()]")
            for i, elem in enumerate(elementos):
                if 'arátula' in elem.text or 'aratula' in elem.text.lower():
                    # El siguiente elemento con texto es el valor
                    for j in range(i + 1, min(i + 5, len(elementos))):
                        siguiente = elementos[j].text.strip()
                        if siguiente and len(siguiente) > 5 and 'arátula' not in siguiente:
                            return siguiente.upper()
        except Exception:
            pass

        return "SIN CARATULAR"

    except Exception as e:
        print(f"⚠️ No se pudo leer carátula: {e}")
        return "SIN CARATULAR"
def sincronizar_pdfs(driver, ruta_local, temp_download_path, fecha_desde=None):
    """
    v4.1: Usa columna 'Número' como ID único.
    Evita duplicados y detecta loop de paginación comparando números.
    """
    t0 = t_mod.time()
    descargas_totales = 0
    pagina_actual = 1
    numeros_ya_descargados = set()

    if not os.path.exists(ruta_local):
        os.makedirs(ruta_local, exist_ok=True)

    for f in os.listdir(ruta_local):
        if f.endswith('.pdf'):
            match = re.search(r'_(\d{7,8})\.pdf$', f)
            if match:
                numeros_ya_descargados.add(match.group(1))

    print(f"IDs ya existentes: {len(numeros_ya_descargados)}")

    while True:
        print(f"\n=== PROCESANDO PÁGINA {pagina_actual} ===")
        try:
                wait = WebDriverWait(driver, 15)
                # Esperar tabla Y que los headers no estén vacíos
                wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
                
                # Esperar hasta que al menos un th tenga texto
                for _ in range(10):
                    time.sleep(0.8)
                    ths = driver.find_elements(By.XPATH, "//table[contains(@class,'Grid')]//tr[1]/th")
                    if ths and any(h.text.strip() for h in ths):
                        break
                else:
                    print(f"⚠️ Headers vacíos en página {pagina_actual}, reintentando...")
                    time.sleep(2)
                    ths = driver.find_elements(By.XPATH, "//table[contains(@class,'Grid')]//tr[1]/th")
                    if not any(h.text.strip() for h in ths):
                        print("❌ Headers siguen vacíos, cortando")
                        break

        except TimeoutException:
         print("❌ No se detectó tabla")
         break

        idx_map = {}
        try:
            headers = driver.find_elements(By.XPATH, "//table[contains(@class, 'Grid')]//tr[1]/th")
            for i, h in enumerate(headers):
                texto = h.text.strip().upper()
                if 'FECHA' in texto:
                    idx_map['fecha'] = i
                elif 'NUMERO' in texto or texto == 'NÚMERO' or texto == 'NUM':
                    idx_map['numero'] = i
                elif 'EXTRACTO' in texto or 'DETALLE' in texto:
                    idx_map['extracto'] = i

            if 'numero' not in idx_map:
                print("❌ No encontré columna 'Número'. Headers:", [h.text for h in headers])
                return descargas_totales
            if 'fecha' not in idx_map:
                print("❌ No encontré columna 'Fecha'")
                return descargas_totales

        except Exception as e:
            print(f"Error detectando headers: {e}")
            return descargas_totales

        filas = driver.find_elements(By.XPATH, "//table//tbody/tr")
        if not filas:
            print("No hay filas")
            break

        numeros_pagina_actual = []
        for fila in filas:
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) > idx_map['numero']:
                    num = celdas[idx_map['numero']].text.strip()
                    if num.isdigit():
                        numeros_pagina_actual.append(num)
            except:
                pass

        print(f"Filas: {len(filas)} - Números: {numeros_pagina_actual[:3]}...")

        descargas_pagina = 0

        for idx_fila, fila in enumerate(filas):
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) < 3:
                    continue

                numero_id = celdas[idx_map['numero']].text.strip()
                if not numero_id or not numero_id.isdigit():
                    continue

                if numero_id in numeros_ya_descargados:
                    continue

                fecha_str = celdas[idx_map['fecha']].text.strip()
                if not re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', fecha_str):
                    continue

                fecha_dt = datetime.strptime(fecha_str, "%d/%m/%Y")
                fecha_iso = fecha_dt.strftime("%Y-%m-%d")

                if fecha_desde and fecha_dt.date() < fecha_desde:
                    continue

                tipo_str = ""
                if 'extracto' in idx_map and idx_map['extracto'] < len(celdas):
                    tipo_str = celdas[idx_map['extracto']].text.strip()[:60]

                tipo_str = re.sub(r'[\\/*?:"<>|]', "_", tipo_str)
                nombre_final = f"{fecha_iso} - {tipo_str}_{numero_id}".strip()

                try:
                    boton = fila.find_element(By.XPATH, ".//a")
                except NoSuchElementException:
                    continue

                archivos_antes = set(os.listdir(temp_download_path))

                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton)
                t_mod.sleep(0.3)
                driver.execute_script("arguments[0].click();", boton)
                print(f"[P{pagina_actual}][{idx_fila+1}] ID:{numero_id} - {tipo_str[:40]}")

                pdf_descargado = None
                for _ in range(30):
                    t_mod.sleep(0.5)
                    archivos_despues = set(os.listdir(temp_download_path))
                    nuevos = archivos_despues - archivos_antes
                    pdfs_completos = [f for f in nuevos if f.endswith('.pdf') and not f.endswith('.crdownload')]

                    if pdfs_completos:
                        pdf_descargado = pdfs_completos[0]
                        ruta_temp = os.path.join(temp_download_path, pdf_descargado)
                        if os.path.exists(ruta_temp):
                            size1 = os.path.getsize(ruta_temp)
                            t_mod.sleep(1)
                            size2 = os.path.getsize(ruta_temp)
                            if size1 == size2 and size1 > 1024:
                                break
                        pdf_descargado = None

                if not pdf_descargado:
                    print(f"⚠️ Timeout ID:{numero_id}")
                    continue

                origen = os.path.join(temp_download_path, pdf_descargado)
                destino = os.path.join(ruta_local, nombre_final + ".pdf")

                shutil.move(origen, destino)
                print(f"✅ {nombre_final}.pdf")
                descargas_pagina += 1
                descargas_totales += 1
                numeros_ya_descargados.add(numero_id)

            except StaleElementReferenceException:
                print(f"⚠️ Elemento viejo, reintentando página...")
                break
            except Exception as e:
                print(f"⚠️ Error fila {idx_fila+1}: {e}")
                continue

        print(f"Descargados en página {pagina_actual}: {descargas_pagina}")

        try:
            btn_sig = driver.find_element(
                By.XPATH,
                "//a[contains(text(), 'Sig') or contains(@class, 'next')][not(contains(@class, 'disabled'))]"
            )
            if btn_sig.is_enabled():
                numeros_antes = set(numeros_pagina_actual)
                driver.execute_script("arguments[0].click();", btn_sig)
                pagina_actual += 1
                time.sleep(2.5)

                filas_nuevas = driver.find_elements(By.XPATH, "//table//tbody/tr")
                numeros_despues = set()
                for f in filas_nuevas:
                    try:
                        celdas = f.find_elements(By.TAG_NAME, "td")
                        num = celdas[idx_map['numero']].text.strip()
                        if num.isdigit():
                            numeros_despues.add(num)
                    except:
                        pass

                if numeros_antes and numeros_despues and len(numeros_antes & numeros_despues) > len(numeros_antes) * 0.5:
                    print(f"⚠️ LOOP detectado. Números repetidos. Cortando.")
                    break
            else:
                print("🏁 Última página")
                break

        except NoSuchElementException:
            print("🏁 No hay botón 'Siguiente'")
            break
        except Exception as e:
            print(f"⚠️ Error paginación: {e}")
            break

    print(f"\n⏱️ TOTAL: {t_mod.time()-t0:.1f}s - Descargados: {descargas_totales} PDFs en {pagina_actual} páginas")
    return descargas_totales