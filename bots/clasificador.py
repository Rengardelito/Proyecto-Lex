# bots/clasificador.py
import os
import re
import time
import shutil
from datetime import datetime

from bots.forum_driver import login_forum, buscar_expediente
from bots.driver_manager import (
    get_driver,
    release_driver,
    is_logged_in,
    marcar_ocupado,
    marcar_libre
)
from database.models import db, CausaInfo


def parsear_identidad_expte(texto, tipo_default=""):
    """
    Devuelve:
        tipo, numero_base, anio, numero_visible

    Ejemplos:
        EXP-118897-15  -> EXP, 118897, 15, 118897-15
        C01 45787/99   -> C01, 45787, 99, 45787-99
        118897-15      -> "", 118897, 15, 118897-15
        43532-1        -> "", 43532, 1, 43532-1
    """
    texto = str(texto or "").strip().upper()

    texto = texto.replace("/", "-")
    texto = re.sub(r"\s+", " ", texto)

    tipo = (tipo_default or "").strip().upper()
    numero_base = ""
    anio = ""

    # EXP-118897-15 / C01-45787-99 / I01 43532 1
    m = re.match(r"^([A-Z]{1,4}\d{0,3})[\s\-]+(\d{3,8})[\s\-]+(\d{1,4})$", texto)
    if m:
        tipo = m.group(1)
        numero_base = m.group(2)
        anio = m.group(3)
    else:
        # 118897-15 / 45787 99
        m = re.search(r"(\d{3,8})[\s\-]+(\d{1,4})", texto)
        if m:
            numero_base = m.group(1)
            anio = m.group(2)
        else:
            # solo número
            m = re.search(r"(\d{3,8})", texto)
            if m:
                numero_base = m.group(1)

    numero_visible = f"{numero_base}-{anio}" if anio else numero_base

    return tipo, numero_base, anio, numero_visible


def _limpiar_huerfanos(usuario_id, usuario_nombre, app, socketio):
    with app.app_context():
        registros = CausaInfo.query.filter_by(usuario_id=usuario_id).all()
        ruta_base = os.path.join(os.getcwd(), 'expedientes_clientes', usuario_nombre)
        eliminados = 0

        for registro in registros:
            encontrado = False

            posibles_nombres = set()
            if registro.numero:
                posibles_nombres.add(registro.numero)
            if registro.numero_base and registro.anio:
                posibles_nombres.add(f"{registro.numero_base}-{registro.anio}")
            if registro.tipo and registro.numero_base and registro.anio:
                posibles_nombres.add(f"{registro.tipo}-{registro.numero_base}-{registro.anio}")
                posibles_nombres.add(f"{registro.tipo} {registro.numero_base}-{registro.anio}")

            for root, dirs, files in os.walk(ruta_base):
                if any(nombre in dirs for nombre in posibles_nombres):
                    encontrado = True
                    break

            if not encontrado:
                db.session.delete(registro)
                eliminados += 1
                socketio.emit('bot_log', {
                    'log': [f'🧹 Huérfano eliminado de DB: {registro.numero}']
                })

        db.session.commit()
        socketio.emit('bot_log', {
            'log': [f'🧹 Limpieza lista: {eliminados} registros eliminados.']
        })


def _buscar_causa_existente(usuario_id, tipo, numero_base, anio, numero_visible):
    """
    Busca primero por identidad real:
        tipo + numero_base + anio

    Si no existen campos nuevos cargados, hace fallback por numero visible.
    """
    query = CausaInfo.query.filter(
        CausaInfo.usuario_id == usuario_id,
        CausaInfo.numero_base == numero_base,
        CausaInfo.anio == anio
    )

    if tipo:
        existe = query.filter(CausaInfo.tipo == tipo).first()
        if existe:
            return existe

    existe = query.first()
    if existe:
        return existe

    return CausaInfo.query.filter(
        CausaInfo.usuario_id == usuario_id,
        CausaInfo.numero == numero_visible
    ).first()


def ejecutar_clasificacion(usuario_id, usuario_nombre, socketio, app):
    with app.app_context():
        from database.models import Usuario
        usuario = db.session.get(Usuario, usuario_id)
        forum_user = usuario.forum_user
        forum_pass = usuario.forum_pass

    driver = get_driver(temp_download_path=None)
    marcar_ocupado()
    t0 = time.time()

    clasificados = 0
    no_encontrados = 0
    errores = 0

    lote_actual = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        socketio.emit('bot_status', {'msg': '🔑 Obteniendo driver...', 'progreso': 5})

        if not is_logged_in():
            socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})
            if not login_forum(driver, forum_user, forum_pass):
                socketio.emit('bot_error', {'msg': '❌ No se pudo hacer login en Forum'})
                return
        else:
            socketio.emit('bot_status', {'msg': '✅ Sesión activa, reutilizando...', 'progreso': 10})

        ruta_base = os.path.join(os.getcwd(), 'expedientes_clientes', usuario_nombre)
        ruta_importados = os.path.join(ruta_base, 'IMPORTADOS')

        if not os.path.exists(ruta_importados):
            socketio.emit('bot_error', {'msg': '❌ No se encontró la carpeta IMPORTADOS'})
            return

        socketio.emit('bot_status', {'msg': '🧹 Sincronizando DB con carpetas...', 'progreso': 3})
        _limpiar_huerfanos(usuario_id, usuario_nombre, app, socketio)

        carpetas = [
            d for d in os.listdir(ruta_importados)
            if os.path.isdir(os.path.join(ruta_importados, d))
        ]

        total = len(carpetas)

        socketio.emit('bot_log', {'log': [f'📁 {total} carpetas para clasificar.']})
        socketio.emit('bot_log', {'log': [f'🏷️ Lote de clasificación actual: {lote_actual}']})

        for idx, nombre_folder in enumerate(carpetas):
            juz_final = "POR CLASIFICAR"
            sec_final = "REVISAR"
            demandado_final = "CARATULA NO ENCONTRADA"

            parte_nro = nombre_folder.split(' _ ')[0] if ' _ ' in nombre_folder else nombre_folder

            tipo_inicial, numero_base_inicial, anio_inicial, numero_visible_inicial = parsear_identidad_expte(parte_nro)

            if not numero_base_inicial:
                socketio.emit('bot_log', {
                    'log': [f'⚠️ Saltado: {nombre_folder} (sin número válido)']
                })
                errores += 1
                continue

            progreso = int(((idx + 1) / total) * 85) + 10

            socketio.emit('bot_status', {
                'msg': f'⚖️ Clasificando: {numero_visible_inicial} ({idx + 1}/{total})',
                'progreso': progreso
            })

            with app.app_context():
                causa_previa = CausaInfo.query.filter(
                    CausaInfo.usuario_id == usuario_id,
                    CausaInfo.nombre_carpeta == nombre_folder
                ).first()

                if not causa_previa:
                    causa_previa = CausaInfo.query.filter(
                        CausaInfo.usuario_id == usuario_id,
                        CausaInfo.numero_base == numero_base_inicial,
                        CausaInfo.anio == anio_inicial
                    ).first()

                localidad_busqueda = (
                    causa_previa.localidad
                    if causa_previa and causa_previa.localidad
                    else "Capital"
                )

                tipo_busqueda = (
                    causa_previa.tipo
                    if causa_previa and causa_previa.tipo
                    else tipo_inicial
                )

            socketio.emit('bot_log', {
                'log': [f'🌎 Buscando {tipo_busqueda or ""} {numero_visible_inicial} en {localidad_busqueda}']
            })

            datos = buscar_expediente(
                driver,
                numero_base_inicial,
                tipo_codigo=tipo_busqueda if tipo_busqueda else None,
                localidad=localidad_busqueda
            )
            if datos:
                juz_final = datos.get('juzgado') or juz_final
                sec_final = datos.get('secretaria') or sec_final
                demandado_final = datos.get('caratula') or demandado_final

                tipo_final = (datos.get('tipo') or tipo_inicial or "").strip().upper()

                nro_forum = datos.get('nro_completo') or numero_visible_inicial
                _, numero_base_final, anio_final, numero_visible_final = parsear_identidad_expte(
                    nro_forum,
                    tipo_default=tipo_final
                )

                if not numero_base_final:
                    numero_base_final = numero_base_inicial
                if not anio_final:
                    anio_final = anio_inicial

                numero_visible_final = (
                    f"{numero_base_final}-{anio_final}"
                    if anio_final
                    else numero_base_final
                )

                socketio.emit('bot_log', {
                    'log': [f'✅ {tipo_final} {numero_visible_final} → {juz_final}']
                })

                clasificados += 1

            else:
                tipo_final = tipo_inicial
                numero_base_final = numero_base_inicial
                anio_final = anio_inicial
                numero_visible_final = numero_visible_inicial

                socketio.emit('bot_log', {
                    'log': [f'❌ No encontrado en Forum: {tipo_final} {numero_visible_final}']
                })
                no_encontrados += 1

            ruta_destino = os.path.join(ruta_base, juz_final, sec_final, numero_visible_final)
            os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)

            try:
                ruta_origen = os.path.join(ruta_importados, nombre_folder)

                if not os.path.exists(ruta_destino):
                    shutil.move(ruta_origen, ruta_destino)
                else:
                    socketio.emit('bot_log', {
                        'log': [f'⚠️ Ya existía destino, fusionando y limpiando IMPORTADOS: {numero_visible_final}']
                    })

                    for item in os.listdir(ruta_origen):
                        origen_item = os.path.join(ruta_origen, item)
                        destino_item = os.path.join(ruta_destino, item)

                        if os.path.isdir(origen_item):
                            if not os.path.exists(destino_item):
                                shutil.move(origen_item, destino_item)
                        else:
                            if not os.path.exists(destino_item):
                                shutil.move(origen_item, destino_item)

                    shutil.rmtree(ruta_origen, ignore_errors=True)

            except Exception as e:
                socketio.emit('bot_log', {
                    'log': [f'💥 Error moviendo {numero_visible_final}: {str(e)}']
                })
                errores += 1
                continue

            try:
                with app.app_context():
                    existe = _buscar_causa_existente(
                        usuario_id,
                        tipo_final,
                        numero_base_final,
                        anio_final,
                        numero_visible_final
                    )

                    if not existe:
                        nueva = CausaInfo(
                            numero=numero_visible_final,
                            tipo=tipo_final,
                            numero_base=numero_base_final,
                            anio=anio_final,
                            localidad=localidad_busqueda,
                            nombre_carpeta=nombre_folder,

                            juzgado=juz_final,
                            secretaria=sec_final,
                            demandado=demandado_final,
                            estado="En Trámite",
                            usuario_id=usuario_id,

                            necesita_sync=True,
                            estado_sync="pendiente",
                            lote_importacion=lote_actual
                        )

                        db.session.add(nueva)
                        db.session.commit()

                        socketio.emit('bot_log', {
                            'log': [
                                f'🆕 DB: {tipo_final} {numero_visible_final} '
                                f'agregado al lote {lote_actual}'
                            ]
                        })

                    else:
                        cambio = False

                        if tipo_final and existe.tipo != tipo_final:
                            existe.tipo = tipo_final
                            cambio = True

                        if numero_base_final and existe.numero_base != numero_base_final:
                            existe.numero_base = numero_base_final
                            cambio = True

                        if anio_final and existe.anio != anio_final:
                            existe.anio = anio_final
                            cambio = True

                        if existe.numero != numero_visible_final:
                            existe.numero = numero_visible_final
                            cambio = True

                        existe.juzgado = juz_final
                        existe.secretaria = sec_final
                        existe.demandado = demandado_final
                        existe.localidad = localidad_busqueda
                        existe.nombre_carpeta = nombre_folder
                        cambio = True

                        # CLAVE:
                        # Si el expediente viene de IMPORTADOS y sigue pendiente,
                        # pertenece a esta clasificación/camada actual.
                        if existe.necesita_sync and existe.estado_sync in ["pendiente", "parcial"]:
                            existe.lote_importacion = lote_actual
                            cambio = True

                        if cambio:
                            db.session.commit()

                        socketio.emit('bot_log', {
                            'log': [
                                f'ℹ️ DB actualizada: {tipo_final} {numero_visible_final} '
                                f'→ lote {existe.lote_importacion}'
                            ]
                        })

            except Exception as e:
                db.session.rollback()
                socketio.emit('bot_log', {
                    'log': [f'💥 Error en DB para {tipo_final} {numero_visible_final}: {str(e)}']
                })
                errores += 1

        tiempo_total = int(time.time() - t0)
        mins = tiempo_total // 60
        segs = tiempo_total % 60
        tiempo_str = f"{mins}m {segs}s" if mins > 0 else f"{segs}s"

        socketio.emit('bot_status', {'msg': '✅ Clasificación finalizada', 'progreso': 100})
        socketio.emit('bot_log', {'log': ['━' * 40]})
        socketio.emit('bot_log', {'log': ['📊 RESUMEN CLASIFICACIÓN']})
        socketio.emit('bot_log', {'log': [f'✅ Clasificados correctamente: {clasificados}']})
        socketio.emit('bot_log', {'log': [f'❌ No encontrados en Forum: {no_encontrados}']})
        socketio.emit('bot_log', {'log': [f'💥 Errores: {errores}']})
        socketio.emit('bot_log', {'log': [f'🏷️ Lote generado: {lote_actual}']})
        socketio.emit('bot_log', {'log': [f'⏱️ Tiempo total: {tiempo_str}']})

        socketio.emit('clasificacion_completa', {
            'total': clasificados,
            'lote': lote_actual,
            'mensaje': 'Clasificación finalizada'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        socketio.emit('bot_error', {'msg': f'❌ Error crítico: {str(e)}'})

    finally:
        marcar_libre()
        release_driver()