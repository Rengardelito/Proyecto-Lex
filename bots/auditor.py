# bots/auditor.py
import os
import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bots.forum_driver import crear_driver, login_forum, descargar_pdfs_nuevos, sincronizar_pdfs, buscar_expediente
from bots.actualizador import actualizar_estado_desde_tabla, _entrar_a_expediente_actualizador
from database.models import db, CausaInfo, Usuario
import config


def parsear_lista_expedientes(texto):
    expedientes = []
    vistos = set()
    lineas = texto.strip().splitlines()

    LOCALIDADES_VALIDAS = [
        'Capital', 'Alvear', 'Bella Vista', 'Beron de Astrada', 'Caa Cati',
        'Colonia Liebig', 'Concepcion', 'Curuzú Cuatiá', 'Curuzu Cuatia',
        'Empedrado', 'Esquina', 'Gdor. Martinez', 'Gdor. Virasoro', 'Goya',
        'Ita Ibate', 'Itati', 'Ituzaingo', 'La Cruz', 'Loreto', 'Mburucuya',
        'Mercedes', 'Mocoreta', 'Monte Caseros', 'Paso de la Patria',
        'Paso de los Libres', 'Perugorria', 'Saladas', 'San Carlos',
        'San Cosme', 'San Luis del Palmar', 'San Miguel', 'San Roque',
        'Santa Lucia', 'Santa Rosa', 'Santo Tome', 'Sauce', 'Yapeyu'
    ]

    def _normalizar_localidad(texto_loc):
        """Busca la localidad más parecida en la lista válida."""
        texto_loc = texto_loc.strip().title()
        for loc in LOCALIDADES_VALIDAS:
            if loc.upper() == texto_loc.upper():
                return loc
        # Búsqueda parcial
        for loc in LOCALIDADES_VALIDAS:
            if texto_loc.upper() in loc.upper() or loc.upper() in texto_loc.upper():
                return loc
        return 'Capital'  # fallback

    for linea in lineas:
        linea_orig = linea.strip()
        if not linea_orig:
            continue

        # Separar localidad si viene con " - "
        localidad = 'Capital'
        if ' - ' in linea_orig:
            partes_loc = linea_orig.rsplit(' - ', 1)
            localidad_candidata = _normalizar_localidad(partes_loc[1])
            if localidad_candidata != 'Capital' or partes_loc[1].strip().title() == 'Capital':
                localidad = localidad_candidata
                linea_orig = partes_loc[0].strip()

        linea = linea_orig.upper()
        linea = re.sub(r'\s*/\s*', '/', linea)

        match = re.match(r'^([A-Z]+\d*)\s+(\d{4,6})(?:/(\d+))?$', linea)
        if not match:
            match = re.match(r'^(\d{4,6})(?:/(\d+))?$', linea)
            if match:
                nro  = match.group(1)
                anio = match.group(2)
                tipo = ""
            else:
                print(f"⚠️ No se pudo parsear: {linea}")
                continue
        else:
            tipo = match.group(1)
            nro  = match.group(2)
            anio = match.group(3)

        nro_completo = f"{nro}-{anio}" if anio else nro
        key = f"{tipo}-{nro_completo}"

        if key not in vistos:
            expedientes.append({
                "tipo":         tipo,
                "nro":          nro,
                "nro_completo": nro_completo,
                "localidad":    localidad,
            })
            vistos.add(key)

    return expedientes


def ejecutar_auditoria(usuario_id, usuario_nombre, socketio, app, lista_texto, modo):
    """
    modo: 'ultimo'  → descargar_pdfs_nuevos  (igual que ACTUALIZAR)
          'completo' → sincronizar_pdfs       (igual que SINCRONIZAR)
    """
    expedientes = parsear_lista_expedientes(lista_texto)

    if not expedientes:
        socketio.emit('bot_status', {'msg': '❌ No se encontraron expedientes válidos en la lista', 'progreso': 100})
        socketio.emit('bot_finished', {})
        return

    with app.app_context():
        usuario    = db.session.get(Usuario, usuario_id)
        forum_user = usuario.forum_user
        forum_pass = usuario.forum_pass

    driver = crear_driver(temp_download_path=config.TEMP_DOWNLOAD_PATH)
    t0 = time.time()

    total            = len(expedientes)
    procesados       = 0
    pdfs_descargados = 0
    no_encontrados   = 0

    modo_label = "último movimiento" if modo == 'ultimo' else "ciclo de vida completo"

    try:
        socketio.emit('bot_status', {'msg': f'🔎 AUDITORÍA — {total} expedientes — Modo: {modo_label}', 'progreso': 5})
        socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})

        if not login_forum(driver, forum_user, forum_pass):
            socketio.emit('bot_error', {'msg': '❌ No se pudo hacer login'})
            return

        socketio.emit('bot_status', {'msg': '✅ Login exitoso. Iniciando auditoría...', 'progreso': 15})

        for idx, exp in enumerate(expedientes):
            nro_completo = exp["nro_completo"]
            nro_solo     = exp["nro"]
            tipo_code    = exp["tipo"]
            progreso     = int(((idx + 1) / total) * 80) + 15

            label = f"{tipo_code} {nro_completo}" if tipo_code else nro_completo
            socketio.emit('bot_status', {
                'msg': f'📋 Procesando {label} ({idx+1}/{total})',
                'progreso': progreso
            })

            # ── Buscar datos del expediente (carátula, juzgado) ──
            with app.app_context():
                causa = None
                if tipo_code:
                    causa = CausaInfo.query.filter(
                        CausaInfo.numero.contains(nro_solo),
                        CausaInfo.tipo == tipo_code,
                        CausaInfo.usuario_id == usuario_id
                    ).first()
                if not causa:
                    causa = CausaInfo.query.filter(
                        CausaInfo.numero.contains(nro_solo),
                        CausaInfo.usuario_id == usuario_id
                    ).first()

            # Si no está en DB, buscar en Forum para obtener datos
            localidad = exp.get("localidad", "Capital")
            if not causa:
                socketio.emit('bot_status', {'msg': f'🔍 {label} no está en DB, buscando en Forum...'})
                localidad = exp.get("localidad", "Capital")
                datos = buscar_expediente(driver, nro_solo, tipo_codigo=tipo_code or None, localidad=localidad)
                if not datos:
                    socketio.emit('bot_status', {'msg': f'⚠️ {label}: no encontrado en Forum, saltando...'})
                    no_encontrados += 1
                    continue

                juzgado   = datos['juzgado']
                secretaria = datos.get('secretaria', 'SECRETARIA UNICA')
                caratula  = datos['caratula']

                ruta = os.path.join(
                    "expedientes_clientes", usuario_nombre,
                    juzgado, secretaria, nro_completo
                )
                os.makedirs(ruta, exist_ok=True)

                with app.app_context():
                    nueva = CausaInfo(
                        numero=nro_completo,
                        tipo=tipo_code,
                        juzgado=juzgado,
                        secretaria=secretaria,
                        demandado=caratula,
                        estado="En Trámite",
                        usuario_id=usuario_id
                    )
                    db.session.add(nueva)
                    db.session.commit()
                    causa_id = nueva.id

                socketio.emit('bot_status', {'msg': f'🆕 {label}: creado en DB — {caratula[:50]}'})

            else:
                causa_id  = causa.id
                juzgado   = causa.juzgado
                secretaria = causa.secretaria or "SECRETARIA UNICA"
                ruta = os.path.join(
                    "expedientes_clientes", usuario_nombre,
                    juzgado, secretaria, causa.numero
                )
                os.makedirs(ruta, exist_ok=True)

            # ── Entrar al expediente ──
            if not _entrar_a_expediente_actualizador(driver, nro_completo, tipo_codigo=tipo_code or None, localidad=localidad):
                socketio.emit('bot_status', {'msg': f'⚠️ {label}: no se pudo entrar, saltando...'})
                no_encontrados += 1
                continue

            # ── Actualizar estado ──
            actualizar_estado_desde_tabla(driver, causa_id, app, socketio)

            # ── Descargar según modo ──
            if modo == 'completo':
                nuevos = sincronizar_pdfs(driver, ruta, config.TEMP_DOWNLOAD_PATH)
                socketio.emit('bot_status', {
                    'msg': f'📚 {label}: {nuevos} PDFs descargados (ciclo completo)',
                    'progreso': progreso
                })
            else:
                nuevos = descargar_pdfs_nuevos(driver, ruta, config.TEMP_DOWNLOAD_PATH)
                socketio.emit('bot_status', {
                    'msg': f'📄 {label}: {nuevos} PDFs nuevos descargados',
                    'progreso': progreso
                })

            pdfs_descargados += nuevos
            procesados += 1
            driver.switch_to.default_content()

        # ── Resumen ──
        tiempo_total = int(time.time() - t0)
        mins = tiempo_total // 60
        segs = tiempo_total % 60
        tiempo_str = f"{mins}m {segs}s" if mins > 0 else f"{segs}s"

        socketio.emit('bot_status', {'msg': '🏁 Auditoría finalizada', 'progreso': 100})
        socketio.emit('bot_status', {'msg': '━' * 40})
        socketio.emit('bot_status', {'msg': '📊 RESUMEN AUDITORÍA'})
        socketio.emit('bot_status', {'msg': f'📋 Total en lista: {total}'})
        socketio.emit('bot_status', {'msg': f'✅ Procesados: {procesados}'})
        socketio.emit('bot_status', {'msg': f'❌ No encontrados: {no_encontrados}'})
        socketio.emit('bot_status', {'msg': f'📄 PDFs descargados: {pdfs_descargados}'})
        socketio.emit('bot_status', {'msg': f'⏱️ Tiempo total: {tiempo_str}'})
        socketio.emit('bot_status', {'msg': '━' * 40})
        socketio.emit('bot_finished', {})

    except Exception as e:
        import traceback
        traceback.print_exc()
        socketio.emit('bot_status', {'msg': f'❌ Error crítico: {str(e)}'})
    finally:
        driver.quit()