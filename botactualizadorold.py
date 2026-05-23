# bots/actualizadorold.py
import os
import re
import time
import shutil
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bots.forum_driver import crear_driver, login_forum, entrar_a_expediente, descargar_pdfs_nuevos, buscar_expediente
from database.models import db, CausaInfo, Usuario
import config


def obtener_expedientes_con_movimiento(driver, matricula, socketio):
    wait = WebDriverWait(driver, 20)
    expedientes = []
    vistos = set()

    try:
        socketio.emit('bot_status', {'msg': '🔍 Entrando a Notificaciones...', 'progreso': 15})
        driver.get("https://forumna.juscorrientes.gov.ar/com.forumna.notificaciones")
        time.sleep(5)

        wait.until(EC.element_to_be_clickable(
            (By.ID, "COMBO_ID_LOCALIDADContainer_btnGroupDrop")
        )).click()
        time.sleep(1)
        wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(., 'Capital')]")
        )).click()

        input_mat = wait.until(EC.element_to_be_clickable((By.ID, "vMATRICULA")))
        driver.execute_script("arguments[0].value = arguments[1];", input_mat, str(matricula))
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", input_mat
        )
        time.sleep(1)

        socketio.emit('bot_status', {'msg': f'🔎 Buscando notificaciones...', 'progreso': 20})
        driver.find_element(By.XPATH, "//input[@value='Buscar']").click()
        time.sleep(7)

        headers = driver.find_elements(
            By.XPATH, "//table[contains(@class, 'Grid')]//tr[1]/th"
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

        if 'exptes' not in idx_map or 'juzgado' not in idx_map:
            socketio.emit('bot_error', {'msg': '❌ No se encontraron columnas en notificaciones'})
            return []

        filas = driver.find_elements(
            By.XPATH, "//table[contains(@class, 'Grid')]//tr[td]"
        )
        socketio.emit('bot_status', {'msg': f'📄 {len(filas)} notificaciones encontradas', 'progreso': 25})

        for fila in filas:
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                texto_exptes = celdas[idx_map['exptes']].text.strip()
                texto_juzgado = celdas[idx_map['juzgado']].text.strip()
                texto_sec = celdas[idx_map['secretaria']].text.strip() \
                    if 'secretaria' in idx_map else "SECRETARIA UNICA"

                if not texto_exptes or not texto_juzgado:
                    continue

                juzgado_limpio = re.sub(
                    r'^JUZGADO\s+', '', texto_juzgado, flags=re.IGNORECASE
                ).strip().upper().replace("/", "-")

                partes = texto_exptes.split(" - ")
                for parte in partes:
                    parte = parte.strip()
                    match = re.match(r'^([A-Z]+\d*)\s*(\d{4,6})(?:\s*/\s*(\d+))?$', parte)
                    if match:
                        nro = match.group(2)
                        anio = match.group(3)
                        nro_completo = f"{nro}-{anio}" if anio else nro
                        key = f"{nro_completo}-{juzgado_limpio}"

                        if key not in vistos:
                            expedientes.append({
                                "nro": nro_completo,
                                "juzgado": juzgado_limpio,
                                "secretaria": texto_sec.upper()
                            })
                            vistos.add(key)

            except Exception:
                continue

        return expedientes

    except Exception as e:
        socketio.emit('bot_error', {'msg': f'❌ Error en notificaciones: {str(e)}'})
        return []


def actualizar_estado_desde_tabla(driver, causa_id, app, socketio):
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.XPATH, "//table//tbody")))
        time.sleep(1)

        headers = driver.find_elements(
            By.XPATH, "//table[contains(@class, 'Grid')]//tr[1]/th"
        )
        idx_fecha = None
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
                fecha_str = celdas[idx_fecha].text.strip()
                extracto_str = celdas[idx_extracto].text.strip()

                if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', fecha_str) and extracto_str:
                    with app.app_context():
                        c = CausaInfo.query.get(causa_id)
                        if c:
                            c.estado = extracto_str[:200]
                            c.ultima_notificacion = fecha_str
                            db.session.commit()
                    socketio.emit('bot_status', {
                        'msg': f'📋 Estado: {extracto_str[:60]}'
                    })
                    break
            except Exception:
                continue

    except Exception as e:
        print(f"Error actualizando estado: {e}")


def ejecutar_actualizacion(usuario_id, usuario_nombre, socketio, app):
    driver = crear_driver(temp_download_path=config.TEMP_DOWNLOAD_PATH)
    t0 = time.time()

    # Contadores
    exptes_actualizados = 0
    exptes_nuevos = 0
    pdfs_descargados = 0
    exptes_sin_pdfs = 0

    try:
        socketio.emit('bot_status', {'msg': '🔑 Abriendo Forum...', 'progreso': 5})
        socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})

        if not login_forum(driver):
            socketio.emit('bot_error', {'msg': '❌ No se pudo hacer login'})
            return

        with app.app_context():
            usuario = Usuario.query.get(usuario_id)
            matricula = usuario.matricula if usuario and usuario.matricula else config.MATRICULA

        expedientes = obtener_expedientes_con_movimiento(driver, matricula, socketio)

        if not expedientes:
            socketio.emit('bot_status', {'msg': '📭 Sin notificaciones nuevas hoy', 'progreso': 100})
            socketio.emit('bot_finished', {})
            return

        total = len(expedientes)
        socketio.emit('bot_status', {'msg': f'📋 {total} expedientes con movimiento', 'progreso': 30})

        for idx, exp in enumerate(expedientes):
            nro = exp["nro"]
            nro_solo = nro.split('-')[0]
            juzgado_forum = exp["juzgado"]
            secretaria_forum = exp["secretaria"]
            progreso = int(((idx + 1) / total) * 65) + 30

            socketio.emit('bot_status', {
                'msg': f'📥 Actualizando {nro} ({idx+1}/{total})',
                'progreso': progreso
            })

            with app.app_context():
                causa = CausaInfo.query.filter(
                    CausaInfo.numero.contains(nro_solo),
                    CausaInfo.usuario_id == usuario_id
                ).first()

            # --- CASO 1: No está en la DB ---
            if not causa:
                socketio.emit('bot_status', {
                    'msg': f'🆕 {nro} no estaba en DB, creando...', 'progreso': progreso
                })
                ruta = os.path.join(
                    "expedientes_clientes", usuario_nombre,
                    juzgado_forum, secretaria_forum, nro
                )
                os.makedirs(ruta, exist_ok=True)

                datos = buscar_expediente(driver, nro_solo)
                caratula_real = datos['caratula'] if datos else "SIN CARATULAR"

                with app.app_context():
                    nueva = CausaInfo(
                        numero=nro,
                        juzgado=juzgado_forum,
                        secretaria=secretaria_forum,
                        demandado=caratula_real,
                        estado="En Trámite",
                        usuario_id=usuario_id
                    )
                    db.session.add(nueva)
                    db.session.commit()
                    nueva_id = nueva.id

                exptes_nuevos += 1

                if entrar_a_expediente(driver, nro):
                    actualizar_estado_desde_tabla(driver, nueva_id, app, socketio)
                    nuevos = descargar_pdfs_nuevos(driver, ruta, config.TEMP_DOWNLOAD_PATH)
                    pdfs_descargados += nuevos
                    driver.switch_to.default_content()

                continue

            # --- CASO 2: Está en la DB ---
            causa_id = causa.id
            causa_juzgado = causa.juzgado
            causa_secretaria = causa.secretaria or ""
            causa_numero = causa.numero

            # Rescatar carátula si falta
            with app.app_context():
                c = CausaInfo.query.get(causa_id)
                if c and c.demandado in (None, "", "SIN CARATULAR", "CARATULA NO ENCONTRADA"):
                    datos = buscar_expediente(driver, nro_solo)
                    if datos and datos.get('caratula'):
                        c.demandado = datos['caratula']
                        db.session.commit()
                        socketio.emit('bot_log', {'msg': f'📝 Carátula actualizada: {nro}'})

            ruta_vieja = os.path.join(
                "expedientes_clientes", usuario_nombre,
                causa_juzgado or juzgado_forum,
                causa_secretaria,
                causa_numero
            )
            ruta_nueva = os.path.join(
                "expedientes_clientes", usuario_nombre,
                juzgado_forum,
                secretaria_forum,
                causa_numero
            )

            if causa_secretaria.upper() != secretaria_forum.upper() and os.path.exists(ruta_vieja):
                try:
                    os.makedirs(os.path.dirname(ruta_nueva), exist_ok=True)
                    shutil.move(ruta_vieja, ruta_nueva)
                    socketio.emit('bot_status', {
                        'msg': f'📦 {nro}: {causa_secretaria} → {secretaria_forum}'
                    })
                    with app.app_context():
                        c = CausaInfo.query.get(causa_id)
                        if c:
                            c.secretaria = secretaria_forum
                            c.juzgado = juzgado_forum
                            db.session.commit()
                except Exception as e:
                    socketio.emit('bot_status', {'msg': f'⚠️ Error moviendo: {str(e)}'})

            ruta_final = ruta_nueva if os.path.exists(ruta_nueva) else ruta_vieja
            os.makedirs(ruta_final, exist_ok=True)

            if entrar_a_expediente(driver, causa_numero):
                actualizar_estado_desde_tabla(driver, causa_id, app, socketio)
                nuevos = descargar_pdfs_nuevos(driver, ruta_final, config.TEMP_DOWNLOAD_PATH)
                pdfs_descargados += nuevos
                exptes_actualizados += 1
                if nuevos > 0:
                    socketio.emit('bot_status', {
                        'msg': f'✅ {nro}: {nuevos} PDFs nuevos', 'progreso': progreso
                    })
                else:
                    exptes_sin_pdfs += 1
                    socketio.emit('bot_status', {
                        'msg': f'📭 {nro}: Sin PDFs nuevos', 'progreso': progreso
                    })
                driver.switch_to.default_content()
            else:
                socketio.emit('bot_status', {
                    'msg': f'⚠️ No se pudo entrar a {nro}', 'progreso': progreso
                })

        # ✅ RESUMEN FINAL
        tiempo_total = int(time.time() - t0)
        mins = tiempo_total // 60
        segs = tiempo_total % 60
        tiempo_str = f"{mins}m {segs}s" if mins > 0 else f"{segs}s"

        socketio.emit('bot_status', {'msg': '🏁 Actualización finalizada', 'progreso': 100})
        socketio.emit('bot_log', {'log': ['━' * 40]})
        socketio.emit('bot_log', {'log': [f'📊 RESUMEN ACTUALIZACIÓN']})
        socketio.emit('bot_log', {'log': [f'🔔 Expedientes con movimiento: {total}']})
        socketio.emit('bot_log', {'log': [f'✅ Actualizados: {exptes_actualizados}']})
        if exptes_nuevos > 0:
            socketio.emit('bot_log', {'log': [f'🆕 Nuevos creados: {exptes_nuevos}']})
        socketio.emit('bot_log', {'log': [f'📄 PDFs descargados: {pdfs_descargados}']})
        socketio.emit('bot_log', {'log': [f'📭 Sin PDFs nuevos: {exptes_sin_pdfs}']})
        socketio.emit('bot_log', {'log': [f'⏱️ Tiempo total: {tiempo_str}']})
        socketio.emit('bot_log', {'log': ['━' * 40]})
        socketio.emit('bot_finished', {})

    except Exception as e:
        import traceback
        traceback.print_exc()
        socketio.emit('bot_error', {'msg': f'❌ Error crítico: {str(e)}'})
    finally:
        driver.quit()