# bots/auditor.py
import os
import re
import time
from datetime import datetime

from bots.forum_driver import login_forum, sincronizar_pdfs, buscar_expediente
from bots.driver_manager import (
    get_driver,
    release_driver,
    is_logged_in,
    marcar_ocupado,
    marcar_libre
)
from bots.actualizador import actualizar_estado_desde_tabla, _entrar_a_expediente_actualizador
from database.models import db, CausaInfo, Usuario
import config


def _contar_pdfs_locales(ruta):
    total = 0
    if not os.path.exists(ruta):
        return 0

    for root, dirs, files in os.walk(ruta):
        for f in files:
            if f.lower().endswith(".pdf"):
                total += 1

    return total


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
        texto_loc = texto_loc.strip().title()

        for loc in LOCALIDADES_VALIDAS:
            if loc.upper() == texto_loc.upper():
                return loc

        for loc in LOCALIDADES_VALIDAS:
            if texto_loc.upper() in loc.upper() or loc.upper() in texto_loc.upper():
                return loc

        return 'Capital'

    for linea in lineas:
        linea_orig = linea.strip()

        if not linea_orig:
            continue

        localidad = 'Capital'

        if ' - ' in linea_orig:
            partes_loc = linea_orig.rsplit(' - ', 1)
            localidad_candidata = _normalizar_localidad(partes_loc[1])

            if localidad_candidata != 'Capital' or partes_loc[1].strip().title() == 'Capital':
                localidad = localidad_candidata
                linea_orig = partes_loc[0].strip()

        linea = linea_orig.upper().strip()
        linea = linea.replace("/", "-")
        linea = re.sub(r"\s+", " ", linea)

        tipo = ""
        nro = ""
        anio = ""

        # EXP-118897-15 / C01-43532-1 / EXP 118897 15
        m = re.match(r"^([A-Z]{1,4}\d{0,3})[\s\-]+(\d{3,8})[\s\-]+(\d{1,4})$", linea)

        if m:
            tipo = m.group(1)
            nro = m.group(2)
            anio = m.group(3)
        else:
            # 118897-15
            m = re.match(r"^(\d{3,8})[\s\-]+(\d{1,4})$", linea)

            if m:
                nro = m.group(1)
                anio = m.group(2)
            else:
                # EXP 118897
                m = re.match(r"^([A-Z]{1,4}\d{0,3})\s+(\d{3,8})$", linea)

                if m:
                    tipo = m.group(1)
                    nro = m.group(2)
                else:
                    # Solo número
                    m = re.match(r"^(\d{3,8})$", linea)

                    if m:
                        nro = m.group(1)
                    else:
                        print(f"⚠️ No se pudo parsear: {linea}")
                        continue

        nro_completo = f"{nro}-{anio}" if anio else nro
        key = f"{tipo}-{nro}-{anio}-{localidad}"

        if key not in vistos:
            expedientes.append({
                "tipo": tipo,
                "nro": nro,
                "anio": anio,
                "nro_completo": nro_completo,
                "localidad": localidad,
            })
            vistos.add(key)

    return expedientes


def _buscar_causa(usuario_id, tipo, nro, anio, nro_completo):
    causa = None

    query = CausaInfo.query.filter(
        CausaInfo.usuario_id == usuario_id,
        CausaInfo.numero_base == nro,
        CausaInfo.anio == anio
    )

    if tipo:
        causa = query.filter(CausaInfo.tipo == tipo).first()

    if not causa:
        causa = query.first()

    if not causa:
        causa = CausaInfo.query.filter(
            CausaInfo.usuario_id == usuario_id,
            CausaInfo.numero == nro_completo
        ).first()

    if not causa:
        causa = CausaInfo.query.filter(
            CausaInfo.usuario_id == usuario_id,
            CausaInfo.numero.contains(nro)
        ).first()

    return causa


def ejecutar_auditoria(usuario_id, usuario_nombre, socketio, app, lista_texto, cantidad):
    expedientes = parsear_lista_expedientes(lista_texto)

    if not expedientes:
        socketio.emit('bot_status', {
            'msg': '❌ No se encontraron expedientes válidos en la lista',
            'progreso': 100
        })
        socketio.emit('bot_finished', {})
        return

    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)
        forum_user = usuario.forum_user
        forum_pass = usuario.forum_pass

    driver = get_driver(temp_download_path=config.TEMP_DOWNLOAD_PATH)
    marcar_ocupado()
    t0 = time.time()

    total = len(expedientes)
    procesados = 0
    pdfs_descargados = 0
    no_encontrados = 0

    txt_cantidad = "TODAS" if cantidad is None else str(cantidad)

    try:
        socketio.emit('bot_status', {
            'msg': f'🔎 AUDITORÍA — {total} expedientes — Descarga: {txt_cantidad}',
            'progreso': 5
        })

        if not is_logged_in():
            socketio.emit('bot_status', {
                'msg': '⚠️ Resolvé el Captcha e iniciá sesión',
                'progreso': 10
            })

            if not login_forum(driver, forum_user, forum_pass):
                socketio.emit('bot_error', {'msg': '❌ No se pudo hacer login'})
                return
        else:
            socketio.emit('bot_status', {
                'msg': '✅ Sesión activa, reutilizando...',
                'progreso': 15
            })

        socketio.emit('bot_status', {
            'msg': '✅ Iniciando auditoría...',
            'progreso': 15
        })

        for idx, exp in enumerate(expedientes):
            nro_completo = exp["nro_completo"]
            nro_solo = exp["nro"]
            anio = exp.get("anio", "")
            tipo_code = exp["tipo"]
            localidad = exp.get("localidad", "Capital")

            progreso = int(((idx + 1) / total) * 80) + 15
            label = f"{tipo_code} {nro_completo}" if tipo_code else nro_completo

            socketio.emit('bot_status', {
                'msg': f'📋 Procesando {label} ({idx + 1}/{total}) — {localidad}',
                'progreso': progreso
            })

            with app.app_context():
                causa = _buscar_causa(
                    usuario_id,
                    tipo_code,
                    nro_solo,
                    anio,
                    nro_completo
                )

            if not causa:
                socketio.emit('bot_status', {
                    'msg': f'🔍 {label} no está en DB, buscando en Forum...'
                })

                datos = buscar_expediente(
                    driver,
                    nro_solo,
                    tipo_codigo=tipo_code or None,
                    localidad=localidad
                )

                if not datos:
                    socketio.emit('bot_status', {
                        'msg': f'⚠️ {label}: no encontrado en Forum, saltando...'
                    })
                    no_encontrados += 1
                    continue

                juzgado = datos.get('juzgado') or 'SIN JUZGADO'
                secretaria = datos.get('secretaria') or 'SECRETARIA UNICA'
                caratula = datos.get('caratula') or 'SIN CARATULAR'

                tipo_final = (datos.get('tipo') or tipo_code or "").strip().upper()
                nro_forum = datos.get('nro_completo') or nro_completo

                # Normalizamos por si Forum devuelve EXP-118897-15
                texto_forum = str(nro_forum).replace("/", "-").upper()
                m = re.match(
                    r"^([A-Z]{1,4}\d{0,3})[\s\-]+(\d{3,8})[\s\-]+(\d{1,4})$",
                    texto_forum
                )

                if m:
                    tipo_final = tipo_final or m.group(1)
                    nro_solo = m.group(2)
                    anio = m.group(3)
                    nro_completo = f"{nro_solo}-{anio}"

                ruta = os.path.join(
                    "expedientes_clientes",
                    usuario_nombre,
                    juzgado,
                    secretaria,
                    nro_completo
                )
                os.makedirs(ruta, exist_ok=True)

                with app.app_context():
                    nueva = CausaInfo(
                        numero=nro_completo,
                        tipo=tipo_final,
                        numero_base=nro_solo,
                        anio=anio,
                        juzgado=juzgado,
                        secretaria=secretaria,
                        demandado=caratula,
                        estado="En Trámite",
                        usuario_id=usuario_id,
                        necesita_sync=True,
                        estado_sync="pendiente"
                    )

                    db.session.add(nueva)
                    db.session.commit()
                    causa_id = nueva.id

                socketio.emit('bot_status', {
                    'msg': f'🆕 {label}: creado en DB — {caratula[:50]}'
                })

            else:
                causa_id = causa.id
                juzgado = causa.juzgado or "SIN JUZGADO"
                secretaria = causa.secretaria or "SECRETARIA UNICA"

                if causa.tipo:
                    tipo_code = causa.tipo

                if causa.numero_base:
                    nro_solo = causa.numero_base

                if causa.anio:
                    anio = causa.anio
                    nro_completo = f"{nro_solo}-{anio}"

                ruta = os.path.join(
                    "expedientes_clientes",
                    usuario_nombre,
                    juzgado,
                    secretaria,
                    causa.numero
                )
                os.makedirs(ruta, exist_ok=True)

            if not _entrar_a_expediente_actualizador(
                driver,
                nro_completo,
                tipo_codigo=tipo_code or None,
                localidad=localidad
            ):
                socketio.emit('bot_status', {
                    'msg': f'⚠️ {label}: no se pudo entrar, saltando...'
                })
                no_encontrados += 1
                continue

            actualizar_estado_desde_tabla(driver, causa_id, app, socketio)

            nuevos, total_forum = sincronizar_pdfs(
                driver,
                ruta,
                config.TEMP_DOWNLOAD_PATH,
                fecha_desde=None,
                cortar_si_existe=False,
                max_descargas=cantidad
            )

            total_local = _contar_pdfs_locales(ruta)

            with app.app_context():
                causa_db = db.session.get(CausaInfo, causa_id)

                if causa_db:
                    causa_db.paginas_forum_total = total_forum or 0
                    causa_db.paginas_descargadas_total = total_local
                    causa_db.ultima_sync = datetime.utcnow()

                    if cantidad is None:
                        causa_db.estado_sync = "sincronizado"
                        causa_db.necesita_sync = False
                        causa_db.error_sync = None

                    elif total_forum > 0 and total_local >= total_forum:
                        causa_db.estado_sync = "sincronizado"
                        causa_db.necesita_sync = False
                        causa_db.error_sync = None

                    else:
                        causa_db.estado_sync = "parcial"
                        causa_db.necesita_sync = True
                        causa_db.error_sync = "Auditoría parcial; falta completar historial"

                    db.session.commit()

            socketio.emit('bot_status', {
                'msg': f'📚 {label}: {nuevos} PDFs descargados | Forum: {total_forum} | Local: {total_local}',
                'progreso': progreso
            })

            pdfs_descargados += nuevos
            procesados += 1

            try:
                driver.switch_to.default_content()
            except Exception:
                pass

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
        socketio.emit('bot_status', {
            'msg': f'❌ Error crítico: {str(e)}'
        })

    finally:
        marcar_libre()
        release_driver()