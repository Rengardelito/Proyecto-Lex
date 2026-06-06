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
import config


def normalizar_juzgado(nombre):
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
    wait.until(EC.element_to_be_clickable(
        (By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")
    )).click()
    wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//span[contains(text(), 'Capital')]")
    )).click()


def _seleccionar_localidad(driver, wait, localidad):
    wait.until(EC.element_to_be_clickable(
        (By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")
    )).click()
    wait.until(EC.element_to_be_clickable(
        (By.XPATH, f"//span[contains(text(), '{localidad}')]")
    )).click()


def _paginar_siguiente(driver):
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


def _mover_archivo(origen, destino_pdf):
    try:
        if origen.lower().endswith('.rtf'):
            from helpers.rtf_converter import rtf_a_pdf
            print(f"🔄 Convirtiendo RTF a PDF: {os.path.basename(origen)}")

            resultado = rtf_a_pdf(origen, destino_pdf)

            if os.path.exists(origen):
                os.remove(origen)

            if resultado and os.path.exists(destino_pdf):
                return True

            print("❌ Falló la conversión RTF→PDF")
            return False

        shutil.move(origen, destino_pdf)
        return True

    except Exception as e:
        print(f"❌ Error moviendo archivo: {e}")
        return False


def buscar_expediente(driver, nro_solo, tipo_codigo=None, localidad='Capital'):
    try:
        nro_limpio = nro_solo.split('-')[0]

        driver.get(config.FORUM_URL_CAUSAS)
        wait = WebDriverWait(driver, 15)

        if localidad and localidad != 'Capital':
            _seleccionar_localidad(driver, wait, localidad)
        else:
            _seleccionar_capital(driver, wait)

        input_nro = wait.until(EC.element_to_be_clickable((By.ID, "vCAUSANRO")))
        input_nro.clear()
        time.sleep(0.3)
        input_nro.send_keys(nro_limpio)
        time.sleep(0.5)

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
                    nro_fila = celdas[2].text.strip()
                    anio_fila = celdas[3].text.strip()
                    caratula = celdas[4].text.strip()

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


def entrar_a_expediente(driver, nro_expte, tipo_codigo=None, localidad='Capital'):
    from selenium.webdriver.common.action_chains import ActionChains

    def _intentar(driver, nro_expte, tipo_codigo, localidad='Capital'):
        nro_solo = nro_expte.split('-')[0]
        anio = nro_expte.split('-')[1] if '-' in nro_expte else ""
        tipo_normalizado = tipo_codigo.upper().replace(" ", "") if tipo_codigo else None

        driver.get(config.FORUM_URL_CAUSAS)
        wait = WebDriverWait(driver, 15)

        if localidad and localidad != 'Capital':
            _seleccionar_localidad(driver, wait, localidad)
        else:
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

                    tipo_fila = celdas[1].text.strip().upper().replace(" ", "")
                    nro_fila = celdas[2].text.strip()
                    anio_fila = celdas[3].text.strip()

                    if nro_fila != nro_solo:
                        continue

                    if anio and anio_fila != anio:
                        continue

                    if tipo_normalizado and tipo_fila != tipo_normalizado:
                        continue

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

            print(f"🔄 entrar_a_expediente: no encontrado en página {pagina}, paginando...")

            if not _paginar_siguiente(driver):
                break

            pagina += 1

        print(f"❌ No se encontró tipo={tipo_codigo} nro={nro_expte} en {pagina} páginas")
        return False

    for intento in range(2):
        try:
            return _intentar(driver, nro_expte, tipo_codigo, localidad)
        except Exception as e:
            if intento == 0:
                print(f"⚠️ Reintentando {nro_expte}...")
                time.sleep(1)
            else:
                print(f"❌ Error entrando a {nro_expte}: {e}")
                return False


def esperar_tabla_actuaciones(driver, timeout=15):
    wait = WebDriverWait(driver, timeout)
    wait.until(EC.presence_of_element_located((By.XPATH, "//table")))

    for _ in range(20):
        tablas = driver.find_elements(By.XPATH, "//table[contains(@class,'Grid') or .//th]")

        for tabla in tablas:
            try:
                headers = tabla.find_elements(By.XPATH, ".//tr[1]/th")
                textos = [h.text.strip().upper() for h in headers if h.text.strip()]

                tiene_fecha = any("FECHA" in t for t in textos)
                tiene_numero = any("NÚMERO" in t or "NUMERO" in t or t == "NUM" for t in textos)
                tiene_extracto = any("EXTRACTO" in t or "DETALLE" in t for t in textos)
                tiene_documento = any("DOCUMENTO" in t for t in textos)

                if tiene_fecha and tiene_numero and tiene_extracto and tiene_documento:
                    return tabla

            except StaleElementReferenceException:
                continue

        time.sleep(0.5)

    raise TimeoutException("No se encontró la tabla específica de Actuaciones")


def contar_actuaciones_forum(driver):
    try:
        tabla = esperar_tabla_actuaciones(driver, timeout=20)
        filas = tabla.find_elements(By.XPATH, ".//tbody/tr")

        filas_reales = 0

        for fila in filas:
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                texto = " ".join([c.text.strip() for c in celdas])

                if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', texto):
                    filas_reales += 1

            except Exception:
                continue

        total_paginas = 1

        elementos = driver.find_elements(
            By.XPATH,
            "//*[contains(text(), 'Página') and contains(text(), 'de')]"
        )

        for el in elementos:
            texto = el.text.strip()
            match = re.search(r"Página\s+\d+\s+de\s+(\d+)", texto, re.IGNORECASE)

            if match:
                total_paginas = int(match.group(1))
                break

        total_estimado = filas_reales * total_paginas

        print(f"📄 Filas visibles: {filas_reales}")
        print(f"📄 Total páginas Forum: {total_paginas}")
        print(f"✅ TOTAL ESTIMADO FORUM: {total_estimado}")

        return total_estimado

    except Exception as e:
        print(f"⚠️ Error estimando actuaciones: {e}")
        return 0


def descargar_pdfs_nuevos(driver, ruta_local, temp_download_path):
    descargas = 0
    main_window = driver.current_window_handle

    try:
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
        time.sleep(0.5)
    except Exception:
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

    driver.paginas_forum_total = contar_actuaciones_forum(driver)
    print(f"[DEBUG ACTUACIONES] Total real Forum = {driver.paginas_forum_total}")

    tabla = esperar_tabla_actuaciones(driver, timeout=20)
    filas = tabla.find_elements(By.XPATH, ".//tbody/tr")

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

            numero_id = ""

            try:
                if len(celdas) > 4:
                    numero_id = celdas[4].text.strip()
            except Exception:
                pass

            base_nombre = f"{fecha_iso} - {tipo_str}"
            base_nombre = (
                base_nombre
                .replace("/", "_")
                .replace(":", "")
                .replace("\\", "")
                .strip()
            )

            if numero_id:
                nombre_final = f"{base_nombre}_{numero_id}.pdf"
            else:
                nombre_final = f"{base_nombre}.pdf"

            dest_final = os.path.join(ruta_local, nombre_final)

            print(f"📥 Descargando: {nombre_final}")
            archivos_antes = set(os.listdir(temp_download_path))

            try:
                boton = fila.find_element(By.XPATH, ".//a")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", boton)

                archivo_movido = False

                for _ in range(15):
                    time.sleep(1)

                    archivos_despues = set(os.listdir(temp_download_path))
                    nuevos = archivos_despues - archivos_antes

                    archivos_completos = [
                        f for f in nuevos
                        if (f.lower().endswith('.pdf') or f.lower().endswith('.rtf'))
                        and not f.endswith('.crdownload')
                    ]

                    if archivos_completos:
                        origen = os.path.join(temp_download_path, archivos_completos[0])

                        if _mover_archivo(origen, dest_final):
                            print(f"✅ Guardado: {nombre_final}")
                            descargas += 1
                            archivo_movido = True
                            archivos_locales.add(nombre_final.replace('.pdf', '').strip())

                        break

                if not archivo_movido:
                    print(f"⚠️ No llegó el archivo para fila {fila_idx}")

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

    return descargas, getattr(driver, "paginas_forum_total", 0)


def leer_caratula_desde_pagina(driver) -> str:
    try:
        intentos = [
            "//td[contains(text(),'Carátula') or contains(text(),'Caratula')]/following-sibling::td[1]",
            "//*[contains(@id,'CARATULA') or contains(@name,'CARATULA')]",
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

        try:
            elementos = driver.find_elements(By.XPATH, "//*[text()]")

            for i, elem in enumerate(elementos):
                if 'arátula' in elem.text or 'aratula' in elem.text.lower():
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


def sincronizar_pdfs(
    driver,
    ruta_local,
    temp_download_path,
    fecha_desde=None,
    cortar_si_existe=False,
    max_descargas=None
):
    """
    Retorna:
        (descargas_totales, total_forum)
    """
    t0 = t_mod.time()
    descargas_totales = 0
    pagina_actual = 1
    total_forum = 0

    numeros_ya_descargados = set()
    nombres_ya_descargados = set()
    nombres_norm_ya_descargados = set()
    fallidos = []

    def _resultado():
        return descargas_totales, total_forum

    def _normalizar_nombre_pdf(txt):
        txt = (txt or "").lower()
        txt = txt.replace(".pdf", "")
        txt = txt.replace("_", " ")
        txt = re.sub(r"[_\s](\d{6,8})$", "", txt)
        txt = re.sub(r"[^a-z0-9áéíóúñ]+", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt

    def _ya_existe_actuacion(numero_id, nombre_sin_id):
        print(f"[CHECK] ID={numero_id!r} | nombre={nombre_sin_id!r}")
        print(f"[IDS LOCALES] {list(numeros_ya_descargados)[:15]}")

        if numero_id in numeros_ya_descargados:
            return True

        nombre_norm = _normalizar_nombre_pdf(nombre_sin_id)

        for viejo in nombres_norm_ya_descargados:
            if len(nombre_norm) >= 18 and len(viejo) >= 18:
                if nombre_norm in viejo or viejo in nombre_norm:
                    return True

        return False

    if not os.path.exists(ruta_local):
        os.makedirs(ruta_local, exist_ok=True)

    for f in os.listdir(ruta_local):
        if f.lower().endswith(".pdf"):
            match = re.search(r"[_\s](\d{6,8})\.pdf$", f, re.IGNORECASE)

            if not match:
                match = re.search(r"_(\d{6,8})(?:\s*\(\d+\))?\.pdf$", f, re.IGNORECASE)

            if match:
                numeros_ya_descargados.add(match.group(1))

            nombre_sin_ext = f[:-4]
            nombre_limpio = re.sub(r"_\d{6,8}$", "", nombre_sin_ext).strip()

            nombres_ya_descargados.add(nombre_limpio)
            nombres_norm_ya_descargados.add(_normalizar_nombre_pdf(nombre_limpio))

    print(f"IDs ya existentes: {len(numeros_ya_descargados)}")

    def _volver_a_pagina_1():
        try:
            for _ in range(5):
                texto = driver.find_element(By.TAG_NAME, "body").text

                if re.search(r"Página\s+1\s+de\s+\d+", texto, re.IGNORECASE):
                    print("✅ Ya estamos en página 1")
                    return True

                btn_ant = driver.find_element(
                    By.XPATH,
                    "//a[normalize-space()='Ant' or contains(normalize-space(), 'Ant')]"
                )

                clase = (btn_ant.get_attribute("class") or "").lower()

                if "disabled" in clase:
                    print("✅ Botón Ant deshabilitado: página 1")
                    return True

                driver.execute_script("arguments[0].click();", btn_ant)
                time.sleep(1.5)

            return True

        except Exception as e:
            print(f"⚠️ No se pudo volver a página 1: {e}")
            return False

    def _descargar_fila(boton, numero_id, nombre_final, ruta_local, temp_download_path):
        archivos_antes = set(os.listdir(temp_download_path))

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", boton)
        t_mod.sleep(0.3)
        driver.execute_script("arguments[0].click();", boton)

        archivo_descargado = None

        for _ in range(30):
            t_mod.sleep(0.5)

            archivos_despues = set(os.listdir(temp_download_path))
            nuevos = archivos_despues - archivos_antes

            archivos_completos = [
                f for f in nuevos
                if (f.lower().endswith(".pdf") or f.lower().endswith(".rtf"))
                and not f.endswith(".crdownload")
            ]

            if archivos_completos:
                archivo_descargado = archivos_completos[0]
                ruta_temp = os.path.join(temp_download_path, archivo_descargado)

                if os.path.exists(ruta_temp):
                    size1 = os.path.getsize(ruta_temp)
                    t_mod.sleep(1)
                    size2 = os.path.getsize(ruta_temp)

                    if size1 == size2 and size1 > 500:
                        break

                archivo_descargado = None

        if not archivo_descargado:
            return False

        origen = os.path.join(temp_download_path, archivo_descargado)
        destino = os.path.join(ruta_local, nombre_final + ".pdf")

        return _mover_archivo(origen, destino)

    def _buscar_boton_siguiente():
        posibles = driver.find_elements(
            By.XPATH,
            "//a[normalize-space()='Sig' or contains(normalize-space(), 'Sig')]"
        )

        for b in posibles:
            try:
                texto = b.text.strip().lower()
                clase = (b.get_attribute("class") or "").lower()
                aria_disabled = (b.get_attribute("aria-disabled") or "").lower()

                if not texto.startswith("sig"):
                    continue

                if "disabled" in clase or aria_disabled == "true":
                    continue

                if not b.is_displayed() or not b.is_enabled():
                    continue

                return b

            except Exception:
                continue

        return None

    _volver_a_pagina_1()

    while True:
        print(f"\n=== PROCESANDO PÁGINA {pagina_actual} ===")

        try:
            tabla_actuaciones = esperar_tabla_actuaciones(driver, timeout=25)

            if total_forum == 0:
                total_forum = contar_actuaciones_forum(driver)
                print(f"[DEBUG ACTUACIONES] Total Forum = {total_forum}")

            for _ in range(10):
                t_mod.sleep(0.8)

                headers = tabla_actuaciones.find_elements(By.XPATH, ".//tr[1]/th")
                textos_headers = [h.text.strip() for h in headers]

                if headers and any(textos_headers):
                    break

                tabla_actuaciones = esperar_tabla_actuaciones(driver, timeout=10)

            else:
                print(f"⚠️ Headers vacíos en página {pagina_actual}, reintentando...")
                t_mod.sleep(2)

                tabla_actuaciones = esperar_tabla_actuaciones(driver, timeout=10)
                headers = tabla_actuaciones.find_elements(By.XPATH, ".//tr[1]/th")
                textos_headers = [h.text.strip() for h in headers]

                if not any(textos_headers):
                    print("❌ Headers siguen vacíos, cortando")
                    break

        except TimeoutException:
            print("❌ No se detectó tabla de Actuaciones")
            break

        idx_map = {}

        try:
            headers = tabla_actuaciones.find_elements(By.XPATH, ".//tr[1]/th")

            for i, h in enumerate(headers):
                texto = h.text.strip().upper()

                if "FECHA" in texto:
                    idx_map["fecha"] = i
                elif "NUMERO" in texto or "NÚMERO" in texto or texto == "NUM":
                    idx_map["numero"] = i
                elif "EXTRACTO" in texto or "DETALLE" in texto:
                    idx_map["extracto"] = i

            print(f"Headers encontrados: {[h.text for h in headers]}")

            try:
                primera_fila = tabla_actuaciones.find_elements(By.XPATH, ".//tbody/tr[1]/td")
                print(f"Primera fila: {[c.text for c in primera_fila]}")
            except Exception:
                pass

            if "numero" not in idx_map:
                print("❌ No encontré columna 'Número'. Headers:", [h.text for h in headers])
                return _resultado()

            if "fecha" not in idx_map:
                print("❌ No encontré columna 'Fecha'")
                return _resultado()

        except Exception as e:
            print(f"Error detectando headers: {e}")
            return _resultado()

        filas = tabla_actuaciones.find_elements(By.XPATH, ".//tbody/tr")

        if not filas:
            print("No hay filas")
            break

        numeros_pagina_actual = []

        for fila in filas:
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")

                if len(celdas) > idx_map["numero"]:
                    num = celdas[idx_map["numero"]].text.strip()

                    if num.isdigit():
                        numeros_pagina_actual.append(num)

            except Exception:
                pass

        print(f"Filas: {len(filas)} - Números: {numeros_pagina_actual[:3]}...")

        descargas_pagina = 0
        idx_fila = 0

        while idx_fila < len(filas):
            fila = filas[idx_fila]

            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")

                if len(celdas) < 3:
                    idx_fila += 1
                    continue

                numero_id = celdas[idx_map["numero"]].text.strip()

                if not numero_id or not numero_id.isdigit():
                    idx_fila += 1
                    continue

                fecha_str = celdas[idx_map["fecha"]].text.strip()

                if not re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", fecha_str):
                    idx_fila += 1
                    continue

                fecha_dt = datetime.strptime(fecha_str, "%d/%m/%Y")
                fecha_iso = fecha_dt.strftime("%Y-%m-%d")

                tipo_str = ""

                if "extracto" in idx_map and idx_map["extracto"] < len(celdas):
                    tipo_str = celdas[idx_map["extracto"]].text.strip()[:60]

                tipo_str = re.sub(r'[\\/*?:"<>|]', "_", tipo_str)
                nombre_sin_id = f"{fecha_iso} - {tipo_str}".strip()

                if _ya_existe_actuacion(numero_id, nombre_sin_id):
                    if cortar_si_existe:
                        print(f"🏁 Actuación ya existe ({numero_id}) → cortando")
                        return _resultado()

                    print(f"⏩ Actuación ya existe ({numero_id}) → sigo buscando anteriores")
                    idx_fila += 1
                    continue

                if fecha_desde and fecha_dt.date() < fecha_desde:
                    idx_fila += 1
                    continue

                nombre_final = f"{fecha_iso} - {tipo_str}_{numero_id}".strip()

                try:
                    boton = fila.find_element(By.XPATH, ".//a")
                except NoSuchElementException:
                    idx_fila += 1
                    continue

                print(f"[P{pagina_actual}][{idx_fila + 1}] ID:{numero_id} - {tipo_str[:40]}")

                if _descargar_fila(boton, numero_id, nombre_final, ruta_local, temp_download_path):
                    print(f"✅ {nombre_final}.pdf")

                    descargas_pagina += 1
                    descargas_totales += 1

                    numeros_ya_descargados.add(numero_id)
                    nombres_ya_descargados.add(nombre_sin_id)
                    nombres_norm_ya_descargados.add(_normalizar_nombre_pdf(nombre_sin_id))

                    if max_descargas and descargas_totales >= max_descargas:
                        print(f"🏁 Límite alcanzado ({max_descargas})")
                        return _resultado()

                else:
                    print(f"⚠️ Timeout ID:{numero_id} → marcado para reintento")

                    fallidos.append({
                        "numero_id": numero_id,
                        "nombre_final": nombre_final,
                        "fecha_iso": fecha_iso,
                        "tipo_str": tipo_str,
                        "pagina": pagina_actual,
                    })

                idx_fila += 1

            except StaleElementReferenceException:
                print("⚠️ Elemento viejo, recargando tabla y filas...")
                t_mod.sleep(1)

                tabla_actuaciones = esperar_tabla_actuaciones(driver, timeout=15)
                filas = tabla_actuaciones.find_elements(By.XPATH, ".//tbody/tr")
                continue

            except Exception as e:
                print(f"⚠️ Error fila {idx_fila + 1}: {e}")
                idx_fila += 1
                continue

        print(f"Descargados en página {pagina_actual}: {descargas_pagina}")

        try:
            numeros_antes = set(numeros_pagina_actual)
            btn_sig = _buscar_boton_siguiente()

            if not btn_sig:
                print("🏁 No hay botón 'Siguiente'")
                break

            primer_id_antes = numeros_pagina_actual[0] if numeros_pagina_actual else None

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_sig)
            t_mod.sleep(0.4)
            driver.execute_script("arguments[0].click();", btn_sig)

            WebDriverWait(driver, 15).until(
                lambda d: (
                    len(d.find_elements(By.XPATH, "//table[contains(@class,'Grid')]//tbody/tr")) > 0
                )
            )

            t_mod.sleep(2)

            tabla_actuaciones = esperar_tabla_actuaciones(driver, timeout=20)
            filas_nuevas = tabla_actuaciones.find_elements(By.XPATH, ".//tbody/tr")

            numeros_despues = set()

            for f in filas_nuevas:
                try:
                    celdas = f.find_elements(By.TAG_NAME, "td")

                    if len(celdas) > idx_map["numero"]:
                        num = celdas[idx_map["numero"]].text.strip()

                        if num.isdigit():
                            numeros_despues.add(num)

                except Exception:
                    pass

            primer_id_despues = None

            try:
                if filas_nuevas:
                    celdas_primera = filas_nuevas[0].find_elements(By.TAG_NAME, "td")

                    if len(celdas_primera) > idx_map["numero"]:
                        primer_id_despues = celdas_primera[idx_map["numero"]].text.strip()

            except Exception:
                pass

            if primer_id_antes and primer_id_despues and primer_id_antes == primer_id_despues:
                t_mod.sleep(2)

                tabla_actuaciones = esperar_tabla_actuaciones(driver, timeout=20)
                filas_nuevas = tabla_actuaciones.find_elements(By.XPATH, ".//tbody/tr")

                try:
                    celdas_primera = filas_nuevas[0].find_elements(By.TAG_NAME, "td")
                    primer_id_despues = celdas_primera[idx_map["numero"]].text.strip()
                except Exception:
                    pass

            if primer_id_antes and primer_id_despues and primer_id_antes == primer_id_despues:
                print("⚠️ Se hizo click en 'Sig' pero la tabla no cambió. Cortando para evitar loop.")
                break

            pagina_actual += 1

            print(f"➡️ Pasando a página {pagina_actual} - primeros IDs: {list(numeros_despues)[:3]}")

            if (
                numeros_antes
                and numeros_despues
                and len(numeros_antes & numeros_despues) > len(numeros_antes) * 0.5
            ):
                print("⚠️ LOOP detectado. Números repetidos. Cortando.")
                break

        except Exception as e:
            print(f"⚠️ Error paginación: {e}")
            break

    if fallidos:
        print(f"\n🔁 REINTENTOS: {len(fallidos)} archivos pendientes...")

        exitosos_reintento = 0
        aun_fallidos = []

        for item in fallidos:
            numero_id = item["numero_id"]
            nombre_final = item["nombre_final"]
            tipo_str = item["tipo_str"]
            pagina_orig = item["pagina"]

            print(f"  🔁 Reintentando ID:{numero_id} página {pagina_orig}...")

            try:
                if not _ir_a_pagina(driver, pagina_orig):
                    print(f"  ⚠️ No pude volver a página {pagina_orig}")
                    aun_fallidos.append(item)
                    continue

                tabla_actuaciones = esperar_tabla_actuaciones(driver, timeout=15)
                filas = tabla_actuaciones.find_elements(By.XPATH, ".//tbody/tr")

                boton_encontrado = None

                for fila in filas:
                    try:
                        celdas = fila.find_elements(By.TAG_NAME, "td")

                        if len(celdas) <= idx_map["numero"]:
                            continue

                        if celdas[idx_map["numero"]].text.strip() == numero_id:
                            boton_encontrado = fila.find_element(By.XPATH, ".//a")
                            break

                    except Exception:
                        continue

                if boton_encontrado and _descargar_fila(
                    boton_encontrado,
                    numero_id,
                    nombre_final,
                    ruta_local,
                    temp_download_path
                ):
                    print(f"  ✅ Reintento exitoso: {nombre_final}.pdf")

                    exitosos_reintento += 1
                    descargas_totales += 1
                    numeros_ya_descargados.add(numero_id)
                else:
                    print(f"  ❌ Reintento fallido: ID:{numero_id}")
                    aun_fallidos.append(item)

            except Exception as e:
                print(f"  ❌ Error en reintento ID:{numero_id}: {e}")
                aun_fallidos.append(item)

        print(f"🔁 Reintentos: {exitosos_reintento} recuperados, {len(aun_fallidos)} sin resolver")

        if aun_fallidos:
            print(f"\n{'=' * 60}")
            print(f"⚠️ ARCHIVOS QUE REQUIEREN REVISIÓN MANUAL ({len(aun_fallidos)})")
            print(f"{'=' * 60}")

            for item in aun_fallidos:
                print(
                    f"  📄 Fecha: {item['fecha_iso']} | "
                    f"Extracto: {item['tipo_str'][:40]} | "
                    f"ID: {item['numero_id']} | "
                    f"Página: {item['pagina']}"
                )

            print(f"{'=' * 60}")
            print("  → Ingresá manualmente al expediente y verificá estos archivos.")
            print("  → Puede ser que el servidor devuelva el PDF corrupto o vacío.")
            print(f"{'=' * 60}\n")

    print(
        f"\n⏱️ TOTAL: {t_mod.time() - t0:.1f}s - "
        f"Descargados: {descargas_totales} PDFs en {pagina_actual} páginas | "
        f"Forum total: {total_forum}"
    )

    return _resultado()


def _obtener_total_paginas(driver) -> int:
    try:
        elementos = driver.find_elements(
            By.XPATH,
            "//*[contains(text(), 'Página') and contains(text(), 'de')]"
        )

        for el in elementos:
            texto = el.text.strip()
            match = re.search(r'Página\s+\d+\s+de\s+(\d+)', texto)

            if match:
                return int(match.group(1))

    except Exception:
        pass

    return 1


def _ir_a_pagina(driver, numero_pagina: int) -> bool:
    try:
        btn_dropdown = driver.find_element(
            By.XPATH,
            "//*[contains(@class,'rowsperpage')]//button | //*[contains(@class,'rowsperpage')]//*[@data-toggle='dropdown']"
        )

        driver.execute_script("arguments[0].click();", btn_dropdown)
        time.sleep(0.8)

        input_pagina = driver.find_element(By.CSS_SELECTOR, "input[type='number']")
        driver.execute_script("arguments[0].value = '';", input_pagina)
        input_pagina.send_keys(str(numero_pagina))
        time.sleep(0.3)

        btn_submit = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
        driver.execute_script("arguments[0].removeAttribute('disabled');", btn_submit)
        driver.execute_script("arguments[0].click();", btn_submit)

        time.sleep(1.5)
        return True

    except Exception as e:
        print(f"⚠️ No se pudo ir a página {numero_pagina}: {e}")
        return False


def sincronizar_pdfs_inverso(driver, ruta_local, temp_download_path):
    t0 = t_mod.time()
    descargas_totales = 0

    if not os.path.exists(ruta_local):
        os.makedirs(ruta_local, exist_ok=True)

    ids_existentes = set()

    for f in os.listdir(ruta_local):
        if f.endswith('.pdf'):
            match = re.search(r'_(\d{6,8})\.pdf$', f)

            if match:
                ids_existentes.add(match.group(1))

    print(f"📂 IDs ya existentes: {len(ids_existentes)}")

    try:
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
        time.sleep(1)

    except TimeoutException:
        print("❌ No se detectó tabla")
        return 0

    idx_map = {}

    try:
        headers = driver.find_elements(By.XPATH, "//table[contains(@class,'Grid')]//tr[1]/th")

        for i, h in enumerate(headers):
            texto = h.text.strip().upper()

            if 'FECHA' in texto:
                idx_map['fecha'] = i
            elif 'NUMERO' in texto or texto == 'NÚMERO' or texto == 'NUM':
                idx_map['numero'] = i
            elif 'EXTRACTO' in texto or 'DETALLE' in texto:
                idx_map['extracto'] = i

        if 'numero' not in idx_map or 'fecha' not in idx_map:
            print("❌ No se encontraron columnas necesarias")
            return 0

    except Exception as e:
        print(f"❌ Error detectando headers: {e}")
        return 0

    total_paginas = _obtener_total_paginas(driver)
    print(f"📄 Total páginas: {total_paginas}")

    for pagina in range(total_paginas, 0, -1):
        print(f"\n=== PÁGINA {pagina} / {total_paginas} (inverso) ===")

        if not _ir_a_pagina(driver, pagina):
            try:
                btn_ant = driver.find_element(
                    By.XPATH,
                    "//a[contains(text(),'Ant') or contains(@class,'prev')][not(contains(@class,'disabled'))]"
                )
                driver.execute_script("arguments[0].click();", btn_ant)
                time.sleep(1.5)

            except Exception:
                print(f"⚠️ No se pudo navegar a página {pagina}")
                break

        try:
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody/tr")))
            time.sleep(0.8)

        except TimeoutException:
            print(f"⚠️ Timeout esperando tabla en página {pagina}")
            continue

        filas = driver.find_elements(By.XPATH, "//table//tbody/tr")
        print(f"Filas en esta página: {len(filas)}")

        cortar = False

        for fila in reversed(filas):
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")

                if len(celdas) < 3:
                    continue

                numero_id = celdas[idx_map['numero']].text.strip()

                if not numero_id or not numero_id.isdigit():
                    continue

                if numero_id in ids_existentes:
                    print(f"🏁 ID {numero_id} ya existe → historial completo, cortando")
                    cortar = True
                    break

                fecha_str = celdas[idx_map['fecha']].text.strip()

                if not re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', fecha_str):
                    continue

                fecha_dt = datetime.strptime(fecha_str, "%d/%m/%Y")
                fecha_iso = fecha_dt.strftime("%Y-%m-%d")

                tipo_str = ""

                if 'extracto' in idx_map and idx_map['extracto'] < len(celdas):
                    tipo_str = celdas[idx_map['extracto']].text.strip()[:60]

                tipo_str = re.sub(r'[\\/*?:"<>|]', "_", tipo_str)
                nombre_final = f"{fecha_iso} - {tipo_str}_{numero_id}".strip()

                dest = os.path.join(ruta_local, nombre_final + ".pdf")

                if os.path.exists(dest):
                    print(f"⏩ Ya existe por nombre: {nombre_final}")
                    ids_existentes.add(numero_id)
                    cortar = True
                    break

                try:
                    boton = fila.find_element(By.XPATH, ".//a")
                except NoSuchElementException:
                    continue

                archivos_antes = set(os.listdir(temp_download_path))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", boton)
                t_mod.sleep(0.3)
                driver.execute_script("arguments[0].click();", boton)

                print(f"📥 ID:{numero_id} - {tipo_str[:40]}")

                archivo_descargado = None

                for _ in range(30):
                    t_mod.sleep(0.5)

                    archivos_despues = set(os.listdir(temp_download_path))
                    nuevos = archivos_despues - archivos_antes

                    archivos_completos = [
                        f for f in nuevos
                        if (f.lower().endswith('.pdf') or f.lower().endswith('.rtf'))
                        and not f.endswith('.crdownload')
                    ]

                    if archivos_completos:
                        archivo_descargado = archivos_completos[0]
                        ruta_temp = os.path.join(temp_download_path, archivo_descargado)

                        if os.path.exists(ruta_temp):
                            size1 = os.path.getsize(ruta_temp)
                            t_mod.sleep(1)
                            size2 = os.path.getsize(ruta_temp)

                            if size1 == size2 and size1 > 500:
                                break

                        archivo_descargado = None

                if not archivo_descargado:
                    print(f"⚠️ Timeout ID:{numero_id}")
                    continue

                origen = os.path.join(temp_download_path, archivo_descargado)
                destino = os.path.join(ruta_local, nombre_final + ".pdf")

                if _mover_archivo(origen, destino):
                    print(f"✅ {nombre_final}.pdf")
                    descargas_totales += 1
                    ids_existentes.add(numero_id)

            except StaleElementReferenceException:
                print(f"⚠️ Elemento obsoleto en página {pagina}")
                break

            except Exception as e:
                print(f"⚠️ Error en fila: {e}")
                continue

        if cortar:
            break

    print(f"\n⏱️ TOTAL inverso: {t_mod.time() - t0:.1f}s - Descargados: {descargas_totales}")
    return descargas_totales