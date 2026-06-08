# bots/actualizador.py
import os
import re
import time
import shutil
from datetime import date, datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from bots.forum_driver import login_forum, descargar_pdfs_nuevos, buscar_expediente
from bots.driver_manager import get_driver, release_driver, is_logged_in, marcar_ocupado, marcar_libre
from database.models import db, CausaInfo, Usuario
import config


# ══════════════════════════════════════════════════════════════════════════════
# MEJORA 1 — PDF UNIFICADO
# ══════════════════════════════════════════════════════════════════════════════

def _es_proveido(nombre_pdf: str) -> bool:
    """
    Determina si un PDF es un proveído (resolución del juzgado) o un escrito de parte.
    
    Lógica: en Forum, el Extracto de los escritos empieza con la fecha de presentación
    en formato DD/MM/YYYY o DD_MM_YYYY. Los proveídos empiezan con texto descriptivo.
    
    El nombre del archivo tiene formato: "YYYY-MM-DD - EXTRACTO_numero.pdf"
    Entonces miramos lo que viene después del " - " inicial.
    """
    import re
    nombre = os.path.basename(nombre_pdf)
    # Quitar prefijo de fecha del nombre: "2026-05-08 - "
    partes = nombre.split(' - ', 1)
    if len(partes) < 2:
        return True  # si no tiene formato esperado, incluir por las dudas
    extracto = partes[1]
    # Si el extracto empieza con una fecha DD/MM/YYYY o DD_MM_YYYY → escrito de parte
    patron_fecha = r'^\d{1,2}[/_]\d{1,2}[/_]\d{2,4}'
    if re.match(patron_fecha, extracto):
        return False  # es escrito de parte, NO es proveído
    return True  # es proveído


def generar_pdf_resumen(pdfs_del_dia: list[dict], fecha_str: str | None, socketio):
    """
    Combina todos los PDFs descargados en el día en un único archivo con:
      - Página de índice al inicio
      - Página separadora antes de cada expediente
      - PDFs originales a continuación
    Usa solo PyMuPDF (fitz) — sin FPDF — para evitar problemas de encoding Unicode.
    """
    try:
        import fitz
        import tempfile
        from datetime import date, datetime

        if not pdfs_del_dia:
            return
        # Filtrar entradas con PDFs y dentro de cada una, solo los proveídos
        pdfs_del_dia_filtrado = []
        for entry in pdfs_del_dia:
            if not entry.get("paths"):
                continue
            solo_proveidos = [p for p in entry["paths"] if _es_proveido(p)]
            if solo_proveidos:
                entry_copia = dict(entry)
                entry_copia["paths"] = solo_proveidos
                pdfs_del_dia_filtrado.append(entry_copia)
        pdfs_del_dia = pdfs_del_dia_filtrado

        if not pdfs_del_dia:
            socketio.emit('bot_status', {'msg': '📋 Sin proveidos nuevos para unificar'})
            return

        socketio.emit('bot_status', {'msg': '📎 Generando PDF resumen diario...'})

        fecha_label   = fecha_str if fecha_str else date.today().strftime("%Y-%m-%d")
        fecha_display = datetime.strptime(fecha_label, "%Y-%m-%d").strftime("%d/%m/%Y")
        nombre_archivo = f"resumen_{fecha_label.replace('-', '')}.pdf"
        ruta_salida    = os.path.join(config.RESUMEN_DIARIO_PATH, nombre_archivo)

        total_pdfs = sum(len(e.get("paths", [])) for e in pdfs_del_dia)

        # ── Helper: crear página con fitz ────────────────────────────────────
        def _nueva_pagina(doc, ancho=595, alto=842):
            """Agrega una página A4 en blanco y devuelve (page, writer_rect)."""
            page = doc.new_page(width=ancho, height=alto)
            return page

        def _texto(page, x, y, texto, size=11, bold=False, color=(0, 0, 0)):
            flags = fitz.TEXT_FONT_BOLD if bold else 0
            fontname = "helv"
            page.insert_text(
                fitz.Point(x, y), texto,
                fontname=fontname, fontsize=size, color=color
            )

        def _rect_fill(page, x0, y0, x1, y1, color):
            page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=color, fill=color)

        AZUL  = (0.18, 0.33, 0.55)
        GRIS  = (0.5,  0.5,  0.5)
        NEGRO = (0.1,  0.1,  0.1)
        BLANCO = (1.0, 1.0, 1.0)

        merger = fitz.open()

        # ── 1. Página de índice ───────────────────────────────────────────────
        pag = _nueva_pagina(merger)

        # Encabezado azul
        _rect_fill(pag, 0, 0, 595, 60, AZUL)
        pag.insert_text(fitz.Point(30, 38),
            "RESUMEN DIARIO DE NOTIFICACIONES",
            fontname="helv", fontsize=18, color=BLANCO)
        pag.insert_text(fitz.Point(30, 55),
            f"Fecha: {fecha_display}",
            fontname="helv", fontsize=10, color=BLANCO)

        # Tabla de índice
        y = 90
        # Cabecera tabla
        _rect_fill(pag, 30, y, 565, y+18, AZUL)
        pag.insert_text(fitz.Point(34,  y+13), "#",         fontname="helv", fontsize=9, color=BLANCO)
        pag.insert_text(fitz.Point(55,  y+13), "Expediente",fontname="helv", fontsize=9, color=BLANCO)
        pag.insert_text(fitz.Point(170, y+13), "Caratula",  fontname="helv", fontsize=9, color=BLANCO)
        pag.insert_text(fitz.Point(500, y+13), "PDFs",      fontname="helv", fontsize=9, color=BLANCO)
        y += 20

        for i, entry in enumerate(pdfs_del_dia):
            bg = (0.94, 0.96, 1.0) if i % 2 == 0 else BLANCO
            _rect_fill(pag, 30, y, 565, y+16, bg)
            nro_txt  = f"{entry.get('tipo','')} {entry.get('nro','')}"
            car_txt  = entry.get("caratula", "")[:50]
            cant_txt = str(len(entry.get("paths", [])))
            pag.insert_text(fitz.Point(34,  y+11), str(i+1),   fontname="helv", fontsize=8, color=NEGRO)
            pag.insert_text(fitz.Point(55,  y+11), nro_txt,    fontname="helv", fontsize=8, color=NEGRO)
            pag.insert_text(fitz.Point(170, y+11), car_txt,    fontname="helv", fontsize=8, color=NEGRO)
            pag.insert_text(fitz.Point(500, y+11), cant_txt,   fontname="helv", fontsize=8, color=NEGRO)
            y += 17
            if y > 780:  # evitar overflow de página
                break

        # Total
        y += 10
        pag.insert_text(fitz.Point(30, y),
            f"Total: {len(pdfs_del_dia)} expediente(s) - {total_pdfs} PDF(s)",
            fontname="helv", fontsize=10, color=AZUL)

        # ── 2. Por cada expediente: separador + PDFs ──────────────────────────
        for entry in pdfs_del_dia:
            # Página separadora
            sep = _nueva_pagina(merger)

            # Franja azul superior
            _rect_fill(sep, 0, 0, 595, 70, AZUL)
            nro_titulo = f"EXPEDIENTE {entry.get('tipo','')} N {entry.get('nro','')}"
            sep.insert_text(fitz.Point(30, 42),
                nro_titulo, fontname="helv", fontsize=16, color=BLANCO)

            y = 95
            sep.insert_text(fitz.Point(30, y), "Caratula:",
                fontname="helv", fontsize=11, color=NEGRO)
            y += 18
            caratula_txt = entry.get("caratula", "")
            # Partir caratula en lineas de 80 chars
            palabras = caratula_txt.split()
            linea = ""
            for palabra in palabras:
                if len(linea) + len(palabra) + 1 > 80:
                    sep.insert_text(fitz.Point(30, y), linea,
                        fontname="helv", fontsize=10, color=GRIS)
                    y += 15
                    linea = palabra
                else:
                    linea = (linea + " " + palabra).strip()
            if linea:
                sep.insert_text(fitz.Point(30, y), linea,
                    fontname="helv", fontsize=10, color=GRIS)
                y += 20

            sep.insert_text(fitz.Point(30, y), "Juzgado:",
                fontname="helv", fontsize=11, color=NEGRO)
            sep.insert_text(fitz.Point(110, y), entry.get("juzgado", ""),
                fontname="helv", fontsize=10, color=GRIS)
            y += 20

            sep.insert_text(fitz.Point(30, y), f"Fecha notif.: {fecha_display}",
                fontname="helv", fontsize=10, color=NEGRO)
            y += 25

            sep.insert_text(fitz.Point(30, y),
                f"Archivos incluidos ({len(entry['paths'])}):",
                fontname="helv", fontsize=10, color=NEGRO)
            y += 18

            for path in entry["paths"]:
                sep.insert_text(fitz.Point(40, y), f"- {os.path.basename(path)}",
                    fontname="helv", fontsize=9, color=GRIS)
                y += 14
                if y > 800:
                    break

            # Insertar los PDFs del expediente
            for pdf_path in entry["paths"]:
                try:
                    merger.insert_pdf(fitz.open(pdf_path))
                except Exception as e:
                    print(f"⚠️ No se pudo incluir {pdf_path}: {e}")

        merger.save(ruta_salida)
        merger.close()

        socketio.emit('bot_status', {
            'msg': f'📎 PDF resumen guardado: RESUMEN_DIARIO/{nombre_archivo}'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        socketio.emit('bot_status', {'msg': f'⚠️ No se pudo generar PDF resumen: {str(e)}'})

def obtener_expedientes_con_movimiento(driver, matricula, socketio, fecha=None, alcance='capital'):

    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    import traceback
    import time
    import re
    from datetime import datetime

    wait = WebDriverWait(driver, 20)
    wait_corto = WebDriverWait(driver, 3)

    expedientes = []
    vistos = set()

    LOCALIDADES_PROVINCIAL = [
        'Capital', 'Alvear', 'Bella Vista', 'Beron de Astrada', 'Caa Cati',
        'Colonia Liebig', 'Concepcion', 'Curuzú Cuatiá', 'Empedrado', 'Esquina',
        'Gdor. Martinez', 'Gdor. Virasoro', 'Goya', 'Ita Ibate', 'Itati',
        'Ituzaingo', 'La Cruz', 'Loreto', 'Mburucuya', 'Mercedes', 'Mocoreta',
        'Monte Caseros', 'Paso de la Patria', 'Paso de los Libres', 'Perugorria',
        'Saladas', 'San Carlos', 'San Cosme', 'San Luis del Palmar', 'San Miguel',
        'San Roque', 'Santa Lucia', 'Santa Rosa', 'Santo Tome', 'Sauce', 'Yapeyu'
    ]

    localidades = (
        LOCALIDADES_PROVINCIAL
        if alcance == 'provincial'
        else ['Capital']
    )

    try:

        # =========================
        # ABRIR UNA SOLA VEZ
        # =========================
        driver.get(
            "https://forumna.juscorrientes.gov.ar/com.forumna.notificaciones"
        )

        wait.until(
            EC.presence_of_element_located(
                (By.ID, "vMATRICULA")
            )
        )

        for idx_loc, localidad in enumerate(localidades):

            t_ciclo = time.time()

            socketio.emit('bot_status', {
                'msg': (
                    f'🔍 Buscando en {localidad} '
                    f'({idx_loc+1}/{len(localidades)})...'
                ),
                'progreso': 15 + int(
                    (idx_loc / len(localidades)) * 10
                )
            })

            try:

                # =========================
                # SELECCIONAR LOCALIDAD
                # =========================
                combo = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.ID,
                            "COMBO_ID_LOCALIDADContainer_btnGroupDrop"
                        )
                    )
                )

                combo.click()

                opcion = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            f"//a[contains(., '{localidad}')]"
                        )
                    )
                )

                opcion.click()

                # =========================
                # MATRÍCULA
                # =========================
                input_mat = wait.until(
                    EC.presence_of_element_located(
                        (By.ID, "vMATRICULA")
                    )
                )

                input_mat.click()
                input_mat.send_keys(Keys.CONTROL + "a")
                input_mat.send_keys(Keys.DELETE)

                driver.execute_script(
                    "arguments[0].value = arguments[1];",
                    input_mat,
                    str(matricula)
                )

                driver.execute_script("""
                    arguments[0].dispatchEvent(
                        new Event('change', { bubbles: true })
                    );
                """, input_mat)

                # =========================
                # FECHA
                # =========================
                if fecha:

                    try:

                        fecha_dt = datetime.strptime(
                            fecha,
                            "%Y-%m-%d"
                        )

                        fecha_forum = fecha_dt.strftime(
                            "%d/%m/%Y"
                        )

                        campo_fecha = driver.find_element(
                            By.ID,
                            "vFECHADATE"
                        )

                        campo_fecha.click()

                        campo_fecha.send_keys(
                            Keys.CONTROL + "a"
                        )

                        campo_fecha.send_keys(Keys.DELETE)

                        campo_fecha.send_keys(fecha_forum)

                        campo_fecha.send_keys(Keys.ESCAPE)

                    except Exception as e:

                        print(
                            f"⚠ No se pudo setear fecha "
                            f"en {localidad}: {e}"
                        )

                # =========================
                # GUARDAR GRID VIEJO
                # =========================
                try:
                    grid_viejo = driver.find_element(
                        By.XPATH,
                        "//table[contains(@class, 'Grid')]"
                    )
                except:
                    grid_viejo = None

                # =========================
                # CLICK BUSCAR
                # =========================
                btn = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//input[@value='Buscar']"
                        )
                    )
                )

                btn.click()

                # =========================
                # ESPERAR QUE MUERA GRID VIEJO
                # =========================
                if grid_viejo:

                    try:
                        wait.until(
                            EC.staleness_of(grid_viejo)
                        )

                    except TimeoutException:
                        pass

                # =========================
                # ESPERAR RESPUESTA NUEVA
                # =========================
                try:

                    wait_corto.until(
                        EC.any_of(

                            EC.presence_of_element_located(
                                (
                                    By.XPATH,
                                    "//*[contains(text(),'Cantidad')]"
                                )
                            ),

                            EC.presence_of_element_located(
                                (
                                    By.XPATH,
                                    "//table[contains(@class, 'Grid')]//tr[td]"
                                )
                            )
                        )
                    )

                except TimeoutException:

                    print(
                        f"⏱ {localidad}: "
                        f"{time.time()-t_ciclo:.1f}s "
                        f"→ timeout"
                    )

                    continue

                # =========================
                # HTML ACTUAL
                # =========================
                source = driver.page_source

                # =========================
                # SIN RESULTADOS
                # =========================
                if (
                    "Cantidad: 0" in source
                    or "No se encontraron registros" in source
                ):

                    print(
                        f"⏱ {localidad}: "
                        f"{time.time()-t_ciclo:.1f}s "
                        f"→ sin notificaciones"
                    )

                    continue

                # =========================
                # FILAS
                # =========================
                filas = driver.find_elements(
                    By.XPATH,
                    "//table[contains(@class, 'Grid')]//tr[td]"
                )

                if not filas:

                    print(
                        f"⏱ {localidad}: "
                        f"{time.time()-t_ciclo:.1f}s "
                        f"→ sin filas"
                    )

                    continue

                # =========================
                # HEADERS
                # =========================
                headers = driver.find_elements(
                    By.XPATH,
                    "//table[contains(@class, 'Grid')]//tr[1]/th"
                )

                idx_map = {}

                for i, h in enumerate(headers):

                    texto = h.text.strip().upper()

                    if 'EXPEDIENTES' in texto:
                        idx_map['exptes'] = i

                    elif 'ORGANISMO' in texto:
                        idx_map['juzgado'] = i

                    elif 'SECRETAR' in texto:
                        idx_map['secretaria'] = i

                if (
                    'exptes' not in idx_map
                    or 'juzgado' not in idx_map
                ):

                    print(
                        f"⏱ {localidad}: "
                        f"{time.time()-t_ciclo:.1f}s "
                        f"→ columnas inválidas"
                    )

                    continue

                socketio.emit('bot_status', {
                    'msg': (
                        f'📄 {localidad}: '
                        f'{len(filas)} notificaciones encontradas'
                    )
                })

                # =========================
                # PARSEAR FILAS
                # =========================
                for fila in filas:

                    try:

                        celdas = fila.find_elements(
                            By.TAG_NAME,
                            "td"
                        )

                        texto_exptes = celdas[
                            idx_map['exptes']
                        ].text.strip()

                        texto_juzgado = celdas[
                            idx_map['juzgado']
                        ].text.strip()

                        texto_sec = (
                            celdas[
                                idx_map['secretaria']
                            ].text.strip()
                            if 'secretaria' in idx_map
                            else "SECRETARIA UNICA"
                        )

                        if (
                            not texto_exptes
                            or not texto_juzgado
                        ):
                            continue

                        juzgado_limpio = re.sub(
                            r'^JUZGADO\s+',
                            '',
                            texto_juzgado,
                            flags=re.IGNORECASE
                        ).strip().upper().replace("/", "-")

                        partes = texto_exptes.split(" - ")

                        for parte in partes:

                            parte = parte.strip()

                            match = re.match(
                                r'^([A-Z]+\d*)\s*(\d{4,6})(?:\s*/\s*(\d+))?$',
                                parte
                            )

                            if match:

                                tipo_code = match.group(1)
                                nro = match.group(2)
                                anio = match.group(3)

                                nro_completo = (
                                    f"{nro}-{anio}"
                                    if anio
                                    else nro
                                )

                                key = (
                                    f"{tipo_code}-"
                                    f"{nro_completo}-"
                                    f"{juzgado_limpio}"
                                )

                                if key not in vistos:

                                    expedientes.append({
                                        "tipo": tipo_code,
                                        "nro": nro_completo,
                                        "juzgado": juzgado_limpio,
                                        "secretaria": texto_sec.upper(),
                                        "localidad": localidad,
                                        "fecha_lista": (
                                            fecha if fecha else ""
                                        )
                                    })

                                    vistos.add(key)

                    except Exception:
                        continue

                print(
                    f"⏱ {localidad}: "
                    f"{time.time()-t_ciclo:.1f}s → "
                    f"{len(filas)} notificaciones"
                )

            except Exception as e:

                print(f"❌ Error en {localidad}: {e}")

                continue

        socketio.emit('bot_status', {
            'msg': (
                f'✅ Total: '
                f'{len(expedientes)} expedientes con movimiento'
            )
        })

        return expedientes

    except Exception as e:

        traceback.print_exc()

        socketio.emit('bot_error', {
            'msg': (
                f'❌ Error en notificaciones: {str(e)}'
            )
        })

        return []
def actualizar_estado_desde_tabla(driver, causa_id, app, socketio, fecha_notif=None):
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
        time.sleep(1)

        headers = driver.find_elements(
            By.XPATH, "//table[contains(@class, 'Grid')]//tr[1]/th"
        )
        idx_fecha    = None
        idx_extracto = None
        for i, h in enumerate(headers):
            texto = h.text.strip().upper()
            if 'FECHA' in texto:
                idx_fecha = i
            elif any(x in texto for x in ['EXTRACTO', 'DETALLE', 'DESCRIPCION']):
                idx_extracto = i

        if idx_fecha is None or idx_extracto is None:
            return

        filas = driver.find_elements(By.XPATH, "//table//tbody/tr")
        for fila in filas:
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) <= max(idx_fecha, idx_extracto):
                    continue
                fecha_str    = celdas[idx_fecha].text.strip()
                extracto_str = celdas[idx_extracto].text.strip()

                if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', fecha_str) and extracto_str:
                    with app.app_context():
                        c = CausaInfo.query.get(causa_id)
                        if c:
                            c.estado = extracto_str[:200]
                            if fecha_notif:
                                try:
                                    dt = datetime.strptime(fecha_notif, "%Y-%m-%d")
                                    c.ultima_notificacion = dt.strftime("%d/%m/%Y")
                                except Exception:
                                    c.ultima_notificacion = fecha_notif
                            else:
                                c.ultima_notificacion = fecha_str
                            db.session.commit()
                    socketio.emit('bot_status', {'msg': f'📋 Estado: {extracto_str[:60]}'})
                    break
            except Exception:
                continue

    except Exception as e:
        print(f"Error actualizando estado: {e}")


def _entrar_a_expediente_actualizador(driver, nro_expte, tipo_codigo=None, localidad='Capital'):
    nro_solo = nro_expte.split('-')[0]
    anio     = nro_expte.split('-')[1] if '-' in nro_expte else ""
    tipo_normalizado = tipo_codigo.upper().replace(" ", "") if tipo_codigo else None

    driver.get(config.FORUM_URL_CAUSAS)
    wait = WebDriverWait(driver, 25)

    try:
        wait.until(EC.presence_of_element_located(
            (By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")
        ))
        time.sleep(0.5)
        wait.until(EC.element_to_be_clickable(
            (By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")
        )).click()
    except Exception:
        print("⚠️ Timeout en combo localidad, recargando...")
        driver.get(config.FORUM_URL_CAUSAS)
        time.sleep(3)
        wait.until(EC.element_to_be_clickable(
            (By.ID, "COMBO_CAUSA_LOCALIDADIDContainer_btnGroupDrop")
        )).click()

    wait.until(EC.element_to_be_clickable(
    (By.XPATH, f"//span[contains(text(), '{localidad}')]")
    )).click()
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
                nro_fila  = celdas[2].text.strip()
                anio_fila = celdas[3].text.strip()
                 # ── DEBUG ──────────────────────────────────────────────
                print(f"[DEBUG FILA] tipo={tipo_fila!r} nro={nro_fila!r} anio={anio_fila!r} | buscando tipo={tipo_normalizado!r} nro={nro_solo!r} anio={anio!r}")
                # ───────────────────────────────────────────────────────

                if nro_fila != nro_solo:
                    continue
                if anio and anio_fila != anio:
                    continue
                if tipo_normalizado and tipo_fila != tipo_normalizado:
                    continue

                celda_nro = celdas[2]
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", celda_nro
                )
                time.sleep(0.3)
                ActionChains(driver).double_click(celda_nro).perform()

                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//table//tbody/tr"))
                )
                return True

            except Exception:
                continue

        print(f"🔄 entrar_actualizador: no encontrado en página {pagina}, paginando...")
        try:
            btn_sig = driver.find_element(
                By.XPATH,
                "//a[contains(text(),'Sig') or contains(@class,'next')][not(contains(@class,'disabled'))]"
            )
            driver.execute_script("arguments[0].click();", btn_sig)
            time.sleep(2)
            pagina += 1
        except Exception:
            break

    print(f"❌ No se encontró tipo={tipo_codigo} nro={nro_expte} en {pagina} páginas")
    return False
def detectar_total_paginas_forum(driver):

    try:

        import re
        from selenium.webdriver.common.by import By

        print("[DEBUG PAGINAS] Entró a detectar_total_paginas_forum")

        body = driver.find_element(By.TAG_NAME, "body")

        texto = body.text

        print("[DEBUG PAGINAS] TEXTO ENCONTRADO:")
        print(texto[:3000])

        # ============================================================
        # CASO 1 — Página X de Y
        # ============================================================

        match = re.search(
            r"p[aá]gina\s+\d+\s+de\s+(\d+)",
            texto,
            re.IGNORECASE
        )

        if match:

            total = int(match.group(1))

            print(f"[DEBUG PAGINAS] MATCH TEXTO → {total}")

            return total

        # ============================================================
        # CASO 2 — botones
        # ============================================================

        elementos = driver.find_elements(
            By.XPATH,
            "//a|//button|//span"
        )

        nums = []

        for e in elementos:

            try:

                t = e.text.strip()

                if t.isdigit():
                    nums.append(int(t))

            except:
                pass

        print(f"[DEBUG PAGINAS] BOTONES → {nums}")

        if nums:
            return max(nums)

        print("[DEBUG PAGINAS] NO ENCONTRÓ PAGINACIÓN")

        return 1

    except Exception as e:

        print(f"[DEBUG PAGINAS ERROR] {e}")

        return 1

def ejecutar_actualizacion(usuario_id, usuario_nombre, socketio, app, fecha_str=None, max_exptes=None, matricula_override=None):
    """
    Actualiza expedientes desde Notificaciones Automáticas.

    Fixes incluidos:
    - Guarda SIEMPRE la localidad real detectada por ACTUALIZAR.
    - Cuando el expediente ya existe en DB, corrige localidad/juzgado/secretaría/tipo.
    - Cuando crea un expediente nuevo, guarda localidad/numero_base/anio.
    - El modal de parciales usa solo expedientes tocados en esta corrida.
    - descargar_pdfs_nuevos puede devolver int o tupla sin romper.
    """

    def _resultado_descarga_seguro(resultado, driver):
        if isinstance(resultado, tuple):
            nuevos, total_forum = resultado
        else:
            nuevos = resultado or 0
            total_forum = getattr(driver, "paginas_forum_total", 0) or 0
        return nuevos or 0, total_forum or 0

    try:
        socketio.emit('bot_status', {'msg': '🔧 Iniciando...'})
        print("[DEBUG] ejecutar_actualizacion arrancó")
        print(f"[DEBUG] fecha recibida: {fecha_str!r}")

        with app.app_context():
            usuario = db.session.get(Usuario, usuario_id)
            if not usuario:
                socketio.emit('bot_status', {'msg': '❌ Usuario no encontrado'})
                return

            forum_user = usuario.forum_user
            forum_pass = usuario.forum_pass
            matricula = matricula_override if matricula_override else (usuario.matricula if usuario.matricula else "")
            alcance = usuario.alcance or 'capital'

        socketio.emit('bot_status', {'msg': '🌐 Obteniendo Chrome...'})
        driver = get_driver(temp_download_path=config.TEMP_DOWNLOAD_PATH)
        marcar_ocupado()
        socketio.emit('bot_status', {'msg': '✅ Chrome listo'})

    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"[DEBUG ERROR] {e}\n{err}")
        socketio.emit('bot_status', {'msg': f'❌ Error: {str(e)}'})
        socketio.emit('bot_status', {'msg': err[:500]})
        return

    t0 = time.time()

    exptes_actualizados = 0
    exptes_nuevos = 0
    pdfs_descargados = 0
    exptes_sin_pdfs = 0

    acumulador_pdfs: list[dict] = []

    try:
        if not is_logged_in():
            socketio.emit('bot_status', {'msg': '🔑 Abriendo Forum...', 'progreso': 5})
            socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})

            if not login_forum(driver, forum_user, forum_pass):
                socketio.emit('bot_status', {'msg': '❌ No se pudo hacer login'})
                return
        else:
            socketio.emit('bot_status', {'msg': '✅ Sesión activa, reutilizando...', 'progreso': 10})

        expedientes = obtener_expedientes_con_movimiento(
            driver,
            matricula,
            socketio,
            fecha=fecha_str,
            alcance=alcance
        )

        if not expedientes:
            label = f"del {fecha_str}" if fecha_str else "de hoy"
            socketio.emit('bot_status', {'msg': f'📭 Sin notificaciones {label}', 'progreso': 100})
            socketio.emit('bot_finished', {})
            return

        if max_exptes and len(expedientes) > max_exptes:
            socketio.emit('bot_status', {
                'msg': f'⚠️ MODO TRIAL: procesando {max_exptes} de {len(expedientes)} expedientes',
                'progreso': 30
            })
            expedientes = expedientes[:max_exptes]

        total = len(expedientes)
        socketio.emit('bot_status', {'msg': f'📋 {total} expedientes con movimiento', 'progreso': 30})

        for idx, exp in enumerate(expedientes):
            nro = exp["nro"]
            nro_solo = nro.split('-')[0]
            anio = nro.split('-')[1] if '-' in nro else ""
            tipo_code = (exp.get("tipo") or "").strip()
            juzgado_forum = exp.get("juzgado") or "SIN JUZGADO"
            secretaria_forum = exp.get("secretaria") or "SECRETARIA UNICA"
            localidad_forum = exp.get("localidad") or "Capital"
            progreso = int(((idx + 1) / total) * 65) + 30

            print(
                f"[DEBUG EXP] tipo={tipo_code!r} nro={nro!r} nro_solo={nro_solo!r} "
                f"localidad={localidad_forum!r} juzgado={juzgado_forum!r}"
            )

            socketio.emit('bot_status', {
                'msg': f'📥 Actualizando {tipo_code} {nro} ({idx + 1}/{total})',
                'progreso': progreso
            })

            entrada_resumen = {
                "nro": nro,
                "tipo": tipo_code,
                "caratula": "",
                "juzgado": juzgado_forum,
                "secretaria": secretaria_forum,
                "paths": [],
                "localidad": localidad_forum,
            }

            causa_id = None
            causa_juzgado = None
            causa_secretaria = ""
            causa_caratula = ""
            causa_encontrada = False

            # ============================================================
            # BUSCAR / CORREGIR DB EXISTENTE
            # ============================================================
            with app.app_context():
                causa = CausaInfo.query.filter(
                    CausaInfo.numero == nro,
                    CausaInfo.usuario_id == usuario_id
                ).first()

                if not causa and tipo_code:
                    causa = CausaInfo.query.filter(
                        CausaInfo.numero.contains(nro_solo),
                        CausaInfo.tipo == "",
                        CausaInfo.usuario_id == usuario_id
                    ).first()

                if causa:
                    causa_encontrada = True

                    # CLAVE: ACTUALIZAR sabe la localidad real por la lista de notificaciones.
                    # Si DB decía Capital y el movimiento vino de Goya/Monte/etc, corregimos DB acá.
                    causa.localidad = localidad_forum
                    causa.juzgado = juzgado_forum or causa.juzgado
                    causa.secretaria = secretaria_forum or causa.secretaria
                    if tipo_code:
                        causa.tipo = tipo_code

                    if not getattr(causa, "numero_base", None):
                        causa.numero_base = nro_solo
                    if not getattr(causa, "anio", None):
                        causa.anio = anio

                    db.session.commit()

                    causa_id = causa.id
                    causa_juzgado = causa.juzgado
                    causa_secretaria = causa.secretaria or ""
                    causa_caratula = causa.demandado or ""

                    print(
                        f"[DEBUG DB FIX] {nro}: localidad={causa.localidad!r}, "
                        f"juzgado={causa.juzgado!r}, tipo={causa.tipo!r}"
                    )

            # ============================================================
            # CASO 1: NO EXISTE EN DB
            # ============================================================
            if not causa_encontrada:
                socketio.emit('bot_status', {
                    'msg': f'🆕 {tipo_code} {nro} no estaba en DB, creando...',
                    'progreso': progreso
                })

                exptes_nuevos += 1
                nueva_id = None
                caratula_real = "SIN CARATULAR"

                datos_busqueda = buscar_expediente(
                    driver,
                    nro_solo,
                    tipo_codigo=tipo_code if tipo_code else None,
                    localidad=localidad_forum
                )

                if datos_busqueda:
                    if datos_busqueda.get('caratula'):
                        caratula_real = datos_busqueda['caratula']
                    if datos_busqueda.get('juzgado'):
                        juzgado_forum = datos_busqueda['juzgado']
                    if datos_busqueda.get('secretaria'):
                        secretaria_forum = datos_busqueda['secretaria']

                entrada_resumen["caratula"] = caratula_real
                entrada_resumen["juzgado"] = juzgado_forum
                entrada_resumen["secretaria"] = secretaria_forum
                entrada_resumen["localidad"] = localidad_forum

                ruta = os.path.join(
                    "expedientes_clientes",
                    usuario_nombre,
                    juzgado_forum,
                    secretaria_forum,
                    nro
                )
                os.makedirs(ruta, exist_ok=True)

                if _entrar_a_expediente_actualizador(
                    driver,
                    nro,
                    tipo_codigo=tipo_code if tipo_code else None,
                    localidad=localidad_forum
                ):
                    print("[DEBUG] ENTRÓ AL CASO 1")

                    total_paginas = detectar_total_paginas_forum(driver)
                    print(f"[DEBUG] TOTAL PAGINAS = {total_paginas}")

                    socketio.emit('bot_status', {
                        'msg': f'📚 {tipo_code} {nro}: {total_paginas} páginas en Forum'
                    })

                    with app.app_context():
                        nueva = CausaInfo(
                            numero=nro,
                            tipo=tipo_code,
                            numero_base=nro_solo,
                            anio=anio,
                            localidad=localidad_forum,
                            juzgado=juzgado_forum,
                            secretaria=secretaria_forum,
                            demandado=caratula_real,
                            estado="En Trámite",
                            usuario_id=usuario_id,
                            necesita_sync=True,
                            estado_sync="parcial",
                            ultima_sync=datetime.utcnow(),
                            error_sync=None,
                            paginas_forum_total=total_paginas,
                            paginas_descargadas_total=0
                        )

                        db.session.add(nueva)
                        db.session.commit()
                        nueva_id = nueva.id

                    actualizar_estado_desde_tabla(
                        driver,
                        nueva_id,
                        app,
                        socketio,
                        fecha_notif=fecha_str
                    )

                    pdfs_antes = set(_listar_pdfs(ruta))

                    resultado_descarga = descargar_pdfs_nuevos(
                        driver,
                        ruta,
                        config.TEMP_DOWNLOAD_PATH
                    )
                    nuevos, total_paginas = _resultado_descarga_seguro(resultado_descarga, driver)

                    pdfs_despues = set(_listar_pdfs(ruta))
                    pdfs_nuevos_paths = list(pdfs_despues - pdfs_antes)

                    pdfs_descargados += nuevos
                    entrada_resumen["paths"] = pdfs_nuevos_paths

                    with app.app_context():
                        c = db.session.get(CausaInfo, nueva_id)

                        if c:
                            total_local = len(_listar_pdfs(ruta))

                            print(f"[DEBUG TOTAL NUEVO] Forum={total_paginas}")

                            c.localidad = localidad_forum
                            c.juzgado = juzgado_forum or c.juzgado
                            c.secretaria = secretaria_forum or c.secretaria
                            c.tipo = tipo_code or c.tipo
                            c.numero_base = nro_solo
                            c.anio = anio

                            c.paginas_forum_total = total_paginas
                            c.paginas_descargadas_total = total_local

                            if total_paginas > 0 and total_local >= total_paginas:
                                c.estado_sync = "sincronizado"
                                c.necesita_sync = False
                                c.error_sync = None
                            else:
                                c.estado_sync = "parcial"
                                c.necesita_sync = True
                                c.error_sync = "Actualizado parcialmente; falta sincronización completa"

                            c.ultima_sync = datetime.utcnow()
                            db.session.commit()

                    exptes_actualizados += 1

                    if nuevos > 0:
                        socketio.emit('bot_status', {
                            'msg': f'✅ {tipo_code} {nro}: {nuevos} PDFs nuevos',
                            'progreso': progreso
                        })
                    else:
                        exptes_sin_pdfs += 1
                        socketio.emit('bot_status', {
                            'msg': f'📭 {tipo_code} {nro}: Sin PDFs nuevos',
                            'progreso': progreso
                        })

                    try:
                        driver.switch_to.default_content()
                    except Exception:
                        pass

                else:
                    with app.app_context():
                        nueva = CausaInfo(
                            numero=nro,
                            tipo=tipo_code,
                            numero_base=nro_solo,
                            anio=anio,
                            localidad=localidad_forum,
                            juzgado=juzgado_forum,
                            secretaria=secretaria_forum,
                            demandado=caratula_real,
                            estado="En Trámite",
                            usuario_id=usuario_id,
                            necesita_sync=True,
                            estado_sync="error",
                            ultima_sync=datetime.utcnow(),
                            error_sync="No se pudo entrar al expediente",
                            paginas_forum_total=0,
                            paginas_descargadas_total=0
                        )

                        db.session.add(nueva)
                        db.session.commit()

                    socketio.emit('bot_status', {
                        'msg': f'⚠️ No se pudo entrar a {tipo_code} {nro}',
                        'progreso': progreso
                    })

                acumulador_pdfs.append(entrada_resumen)
                continue

            # ============================================================
            # CASO 2: EXISTE EN DB
            # ============================================================
            entrada_resumen["caratula"] = causa_caratula

            with app.app_context():
                c = db.session.get(CausaInfo, causa_id)

                if c:
                    # CLAVE: mantener DB coherente apenas ACTUALIZAR detecta la localidad.
                    c.localidad = localidad_forum
                    c.juzgado = juzgado_forum or c.juzgado
                    c.secretaria = secretaria_forum or c.secretaria
                    if tipo_code:
                        c.tipo = tipo_code
                    if not getattr(c, "numero_base", None):
                        c.numero_base = nro_solo
                    if not getattr(c, "anio", None):
                        c.anio = anio
                    db.session.commit()

                if c and c.demandado in (None, "", "SIN CARATULAR", "CARATULA NO ENCONTRADA"):
                    datos = buscar_expediente(
                        driver,
                        nro_solo,
                        tipo_codigo=tipo_code if tipo_code else None,
                        localidad=localidad_forum
                    )

                    if datos and datos.get('caratula'):
                        c.demandado = datos['caratula']
                        db.session.commit()
                        entrada_resumen["caratula"] = datos['caratula']
                        socketio.emit('bot_log', {'msg': f'📝 Carátula actualizada: {nro}'})

            ruta_vieja = os.path.join(
                "expedientes_clientes",
                usuario_nombre,
                causa_juzgado or juzgado_forum,
                causa_secretaria,
                nro
            )

            ruta_nueva = os.path.join(
                "expedientes_clientes",
                usuario_nombre,
                juzgado_forum,
                secretaria_forum,
                nro
            )

            if causa_secretaria and causa_secretaria.upper() != secretaria_forum.upper() and os.path.exists(ruta_vieja):
                try:
                    os.makedirs(os.path.dirname(ruta_nueva), exist_ok=True)
                    shutil.move(ruta_vieja, ruta_nueva)

                    socketio.emit('bot_status', {
                        'msg': f'📦 {nro}: {causa_secretaria} → {secretaria_forum}'
                    })

                    with app.app_context():
                        c = db.session.get(CausaInfo, causa_id)
                        if c:
                            c.secretaria = secretaria_forum
                            c.juzgado = juzgado_forum
                            c.localidad = localidad_forum
                            db.session.commit()

                except Exception as e:
                    socketio.emit('bot_status', {'msg': f'⚠️ Error moviendo: {str(e)}'})

            ruta_final = ruta_nueva if os.path.exists(ruta_nueva) else ruta_vieja
            os.makedirs(ruta_final, exist_ok=True)

            if _entrar_a_expediente_actualizador(
                driver,
                nro,
                tipo_codigo=tipo_code if tipo_code else None,
                localidad=localidad_forum
            ):
                total_paginas = detectar_total_paginas_forum(driver)
                print(f"[DEBUG PAGINAS] {tipo_code} {nro} → {total_paginas}")

                socketio.emit('bot_status', {
                    'msg': f'📚 {tipo_code} {nro}: {total_paginas} páginas en Forum'
                })

                actualizar_estado_desde_tabla(
                    driver,
                    causa_id,
                    app,
                    socketio,
                    fecha_notif=fecha_str
                )

                pdfs_antes = set(_listar_pdfs(ruta_final))

                resultado_descarga = descargar_pdfs_nuevos(
                    driver,
                    ruta_final,
                    config.TEMP_DOWNLOAD_PATH
                )
                nuevos, total_paginas = _resultado_descarga_seguro(resultado_descarga, driver)

                pdfs_despues = set(_listar_pdfs(ruta_final))
                pdfs_nuevos_paths = list(pdfs_despues - pdfs_antes)

                pdfs_descargados += nuevos
                entrada_resumen["paths"] = pdfs_nuevos_paths

                with app.app_context():
                    c = db.session.get(CausaInfo, causa_id)

                    if c:
                        total_local = len(_listar_pdfs(ruta_final))

                        print(f"[DEBUG TOTAL EXISTENTE] Forum={total_paginas}")

                        c.localidad = localidad_forum
                        c.juzgado = juzgado_forum or c.juzgado
                        c.secretaria = secretaria_forum or c.secretaria
                        c.tipo = tipo_code or c.tipo
                        c.numero_base = c.numero_base or nro_solo
                        c.anio = c.anio or anio

                        c.paginas_forum_total = total_paginas
                        c.paginas_descargadas_total = total_local

                        if total_paginas > 0 and total_local >= total_paginas:
                            c.estado_sync = "sincronizado"
                            c.necesita_sync = False
                            c.error_sync = None
                        else:
                            c.estado_sync = "parcial"
                            c.necesita_sync = True
                            c.error_sync = "Actualizado parcialmente; falta sincronización completa"

                        c.ultima_sync = datetime.utcnow()
                        db.session.commit()

                exptes_actualizados += 1

                if nuevos > 0:
                    socketio.emit('bot_status', {
                        'msg': f'✅ {tipo_code} {nro}: {nuevos} PDFs nuevos',
                        'progreso': progreso
                    })
                else:
                    exptes_sin_pdfs += 1
                    socketio.emit('bot_status', {
                        'msg': f'📭 {tipo_code} {nro}: Sin PDFs nuevos',
                        'progreso': progreso
                    })

                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass

            else:
                with app.app_context():
                    c = db.session.get(CausaInfo, causa_id)

                    if c:
                        # Aunque no logre entrar, la localidad real vino de Notificaciones.
                        c.localidad = localidad_forum
                        c.juzgado = juzgado_forum or c.juzgado
                        c.secretaria = secretaria_forum or c.secretaria
                        c.tipo = tipo_code or c.tipo
                        c.estado_sync = "error"
                        c.error_sync = "No se pudo entrar al expediente"
                        c.ultima_sync = datetime.utcnow()
                        db.session.commit()

                socketio.emit('bot_status', {
                    'msg': f'⚠️ No se pudo entrar a {tipo_code} {nro}',
                    'progreso': progreso
                })

            acumulador_pdfs.append(entrada_resumen)

        # ============================================================
        # FIN LOOP
        # ============================================================
        generar_pdf_resumen(acumulador_pdfs, fecha_str, socketio)

        tiempo_total = int(time.time() - t0)
        mins = tiempo_total // 60
        segs = tiempo_total % 60
        tiempo_str = f"{mins}m {segs}s" if mins > 0 else f"{segs}s"

        socketio.emit('bot_status', {'msg': '🏁 Actualización finalizada', 'progreso': 100})
        socketio.emit('bot_status', {'msg': '━' * 40})
        socketio.emit('bot_status', {'msg': '📊 RESUMEN ACTUALIZACIÓN'})
        socketio.emit('bot_status', {'msg': f'🔔 Expedientes con movimiento: {total}'})
        socketio.emit('bot_status', {'msg': f'✅ Actualizados: {exptes_actualizados}'})

        if exptes_nuevos > 0:
            socketio.emit('bot_status', {'msg': f'🆕 Nuevos creados: {exptes_nuevos}'})

        socketio.emit('bot_status', {'msg': f'📄 PDFs descargados: {pdfs_descargados}'})
        socketio.emit('bot_status', {'msg': f'📭 Sin PDFs nuevos: {exptes_sin_pdfs}'})
        socketio.emit('bot_status', {'msg': f'⏱️ Tiempo total: {tiempo_str}'})
        socketio.emit('bot_status', {'msg': '━' * 40})

        # ============================================================
        # EXPEDIENTES PARCIALES SOLO DE ESTA ACTUALIZACIÓN
        # ============================================================
        expedientes_parciales = []

        # Índice de lo que ACTUALIZAR realmente procesó en esta corrida.
        # Esta es la fuente correcta de localidad, no la DB.
        actualizados_por_numero = {}

        for e in acumulador_pdfs:
            nro_e = str(e.get("nro") or e.get("numero") or "").strip()
            if not nro_e:
                continue

            actualizados_por_numero[nro_e] = {
                "nro": nro_e,
                "tipo": e.get("tipo", ""),
                "juzgado": e.get("juzgado", ""),
                "secretaria": e.get("secretaria", ""),
                "localidad": e.get("localidad", ""),
            }

        print("=" * 80)
        print("ACTUALIZADOS_POR_NUMERO / FUENTE PARA MODAL")
        for k, v in actualizados_por_numero.items():
            print(k, v)
        print("=" * 80)

        with app.app_context():

            causas_parciales = CausaInfo.query.filter(
                CausaInfo.usuario_id == usuario_id,
                CausaInfo.estado_sync == "parcial"
            ).all()

            for c in causas_parciales:
                nro_c = str(c.numero or "").strip()

                # CLAVE: si no estuvo en esta actualización, NO va al modal.
                if nro_c not in actualizados_por_numero:
                    continue

                fuente = actualizados_por_numero[nro_c]

                localidad_modal = fuente.get("localidad") or c.localidad or "Capital"
                tipo_modal = fuente.get("tipo") or c.tipo or ""
                juzgado_modal = fuente.get("juzgado") or c.juzgado or ""
                secretaria_modal = fuente.get("secretaria") or c.secretaria or ""

                print(
                    f"[MODAL PARCIAL] {nro_c} | "
                    f"loc_fuente={fuente.get('localidad')!r} | "
                    f"loc_db={c.localidad!r} | "
                    f"loc_modal={localidad_modal!r}"
                )

                faltan = max(
                    (c.paginas_forum_total or 0) -
                    (c.paginas_descargadas_total or 0),
                    0
                )

                expedientes_parciales.append({
                    "nro": nro_c,
                    "numero": nro_c,
                    "forum_total": c.paginas_forum_total or 0,
                    "descargadas": c.paginas_descargadas_total or 0,
                    "faltan": faltan,
                    "juzgado": juzgado_modal,
                    "secretaria": secretaria_modal,
                    "tipo": tipo_modal,
                    "localidad": localidad_modal,
                })

        print("=" * 80)
        print("EXPEDIENTES_PARCIALES QUE VAN AL MODAL")
        for e in expedientes_parciales:
            print(e)
        print("=" * 80)

        socketio.emit('actualizacion_completa', {
            'total': total,
            'pdfs': pdfs_descargados,

            'expedientes': [
                {
                    'nro': e.get('nro', e.get('numero', '')),
                    'tipo': e.get('tipo', ''),
                    'juzgado': e.get('juzgado', ''),
                    'secretaria': e.get('secretaria', ''),
                    'localidad': e.get('localidad', 'Capital')
                }
                for e in acumulador_pdfs
            ],

            'expedientes_parciales': expedientes_parciales,
            'tiempo': tiempo_str
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        socketio.emit('bot_status', {'msg': f'❌ Error crítico: {str(e)}'})

    finally:
        marcar_libre()
        release_driver()


# ── Helper interno ───────────────────────────────────────────────────────────

def _listar_pdfs(carpeta: str) -> list[str]:
    """Devuelve lista de rutas absolutas de todos los PDFs en una carpeta."""
    if not os.path.isdir(carpeta):
        return []
    return [
        os.path.join(carpeta, f)
        for f in os.listdir(carpeta)
        if f.lower().endswith(".pdf")
    ]