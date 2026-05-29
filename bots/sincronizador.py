# bots/sincronizador.py
import os
import re
import time
import shutil
from datetime import datetime
from bots.forum_driver import login_forum, entrar_a_expediente, sincronizar_pdfs
from bots.driver_manager import get_driver, release_driver, is_logged_in, marcar_ocupado, marcar_libre
from database.models import db, CausaInfo
import config

def _limpiar_temp(socketio):
    """Limpia la carpeta temp_downloads al inicio de cada sincronización."""
    ruta_temp = config.TEMP_DOWNLOAD_PATH
    if not os.path.exists(ruta_temp):
        return
    eliminados = 0
    for nombre in os.listdir(ruta_temp):
        ruta_archivo = os.path.join(ruta_temp, nombre)
        try:
            if os.path.isfile(ruta_archivo):
                os.remove(ruta_archivo)
                eliminados += 1
        except Exception as e:
            print(f"⚠️ No se pudo borrar {nombre}: {e}")
    if eliminados > 0:
        socketio.emit('bot_status', {'msg': f'🧹 Temp limpiada: {eliminados} archivos eliminados'})

def _mover_migrados(ruta, socketio):
    """
    Mueve los archivos sin formato YYYY-MM-DD a una subcarpeta MIGRADOS/
    para que no interfieran con los descargados de Forum.
    """
    if not os.path.exists(ruta):
        return

    patron_fecha = re.compile(r'^\d{4}-\d{2}-\d{2}')
    ruta_migrados = os.path.join(ruta, 'MIGRADOS')
    movidos = 0

    for nombre in os.listdir(ruta):
        ruta_archivo = os.path.join(ruta, nombre)

        if not os.path.isfile(ruta_archivo):
            continue
        if patron_fecha.match(nombre):
            continue

        os.makedirs(ruta_migrados, exist_ok=True)
        ruta_destino = os.path.join(ruta_migrados, nombre)

        if not os.path.exists(ruta_destino):
            shutil.move(ruta_archivo, ruta_destino)
            movidos += 1
            socketio.emit('bot_status', {'msg': f'📦 Archivado: {nombre}'})

    if movidos > 0:
        socketio.emit('bot_status', {'msg': f'📦 {movidos} archivos migrados movidos a MIGRADOS/'})

def ejecutar_sincronizacion(usuario_id, usuario_nombre, socketio, app, max_exptes=None):
    # Obtener credenciales del usuario desde la DB
    with app.app_context():
        from database.models import Usuario
        usuario = db.session.get(Usuario, usuario_id)
        forum_user = usuario.forum_user
        forum_pass = usuario.forum_pass

    driver = get_driver(temp_download_path=config.TEMP_DOWNLOAD_PATH)
    marcar_ocupado()

    t0 = time.time()

    exptes_sincronizados = 0
    pdfs_descargados = 0
    exptes_sin_novedades = 0
    exptes_no_encontrados = 0

    try:
        if not is_logged_in():
            socketio.emit('bot_status', {'msg': '🔑 Abriendo Forum...', 'progreso': 5})
            socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})
            if not login_forum(driver, forum_user, forum_pass):
                socketio.emit('bot_status', {'msg': '❌ No se pudo hacer login'})
                return
        else:
            # ✅ Limpiamos temp_downloads al inicio
            _limpiar_temp(socketio)
            socketio.emit('bot_status', {'msg': '✅ Sesión activa, reutilizando...', 'progreso': 10})
        

        

       

        with app.app_context():
            causas = CausaInfo.query.filter_by(usuario_id=usuario_id).all()
            lista_causas = [
                {
                    "numero":     c.numero,
                    "tipo":       c.tipo or "",       # ← agregar esto
                    "juzgado":    c.juzgado    or "SIN JUZGADO",
                    "secretaria": c.secretaria or "SIN SECRETARIA",
                }
                for c in causas
            ]

         # ✅ LÍMITE TRIAL
        if max_exptes and len(lista_causas) > max_exptes:
            socketio.emit('bot_status', {
                'msg': f'⚠️ MODO TRIAL: procesando {max_exptes} de {len(lista_causas)} expedientes',
                'progreso': 22
            })
            lista_causas = lista_causas[:max_exptes]    

        total = len(lista_causas)
        socketio.emit('bot_status', {'msg': f'📁 {total} expedientes encontrados', 'progreso': 25})

        for idx, causa in enumerate(lista_causas):
            nro = causa["numero"]
            progreso = int(((idx + 1) / total) * 70) + 25

            socketio.emit('bot_status', {
                'msg': f'🔎 Sincronizando {nro} ({idx+1}/{total})',
                'progreso': progreso
            })

            ruta = os.path.join(
                "expedientes_clientes",
                usuario_nombre,
                causa["juzgado"] or "SIN JUZGADO",
                causa["secretaria"] or "SIN SECRETARIA",
                nro
            )
            os.makedirs(ruta, exist_ok=True)

            _mover_migrados(ruta, socketio)

            socketio.emit('bot_status', {'msg': f'📂 {nro}: descargando historial completo de Forum'})

            if entrar_a_expediente(driver, nro):
                nuevos = sincronizar_pdfs(driver, ruta, config.TEMP_DOWNLOAD_PATH, fecha_desde=None)
                pdfs_descargados += nuevos
                if nuevos > 0:
                    exptes_sincronizados += 1
                    socketio.emit('bot_status', {'msg': f'✅ {nro}: {nuevos} PDFs nuevos', 'progreso': progreso})
                else:
                    exptes_sin_novedades += 1
                    socketio.emit('bot_status', {'msg': f'📭 {nro}: Sin novedades', 'progreso': progreso})
            else:
                exptes_no_encontrados += 1
                socketio.emit('bot_status', {'msg': f'⚠️ No se encontró {nro} en Forum', 'progreso': progreso})

        tiempo_total = int(time.time() - t0)
        mins = tiempo_total // 60
        segs = tiempo_total % 60
        tiempo_str = f"{mins}m {segs}s" if mins > 0 else f"{segs}s"

        socketio.emit('bot_status', {'msg': '🏁 Sincronización finalizada', 'progreso': 100})
        socketio.emit('bot_status', {'msg': '━' * 40})
        socketio.emit('bot_status', {'msg': '📊 RESUMEN SINCRONIZACIÓN'})
        socketio.emit('bot_status', {'msg': f'✅ Expedientes con PDFs nuevos: {exptes_sincronizados}'})
        socketio.emit('bot_status', {'msg': f'📄 Total PDFs descargados: {pdfs_descargados}'})
        socketio.emit('bot_status', {'msg': f'📭 Sin novedades: {exptes_sin_novedades}'})
        if exptes_no_encontrados > 0:
            socketio.emit('bot_status', {'msg': f'⚠️ No encontrados en Forum: {exptes_no_encontrados}'})
        socketio.emit('bot_status', {'msg': f'⏱️ Tiempo total: {tiempo_str}'})
        socketio.emit('bot_status', {'msg': '━' * 40})
        socketio.emit('bot_finished', {})

    except Exception as e:
        import traceback
        traceback.print_exc()
        socketio.emit('bot_status', {'msg': f'❌ Error crítico: {str(e)}'})
    finally:
        marcar_libre()
        release_driver()

def ejecutar_completar_historial(usuario_id, usuario_nombre, socketio, app, max_exptes=None, lista_exptes=None):
    """
    Completa el historial de expedientes yendo de adelante para atrás.
    Se detiene por expediente cuando encuentra archivos que ya tiene.
    Ideal para abogados que solo tienen la última actuación descargada.
    Si lista_exptes viene del actualizador, usa esa lista en lugar de toda la DB.
    """
    
    from database.models import db, CausaInfo

    with app.app_context():
        from database.models import Usuario
        usuario = db.session.get(Usuario, usuario_id)
        forum_user = usuario.forum_user
        forum_pass = usuario.forum_pass

    driver = get_driver(temp_download_path=config.TEMP_DOWNLOAD_PATH)
    t0 = time.time()

    exptes_procesados     = 0
    pdfs_descargados      = 0
    exptes_sin_nuevos     = 0
    exptes_no_encontrados = 0

    try:
        socketio.emit('bot_status', {'msg': '🔑 Abriendo Forum...', 'progreso': 5})
        socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})

        if not is_logged_in():
            socketio.emit('bot_status', {'msg': '🔑 Abriendo Forum...', 'progreso': 5})
            socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})
            if not login_forum(driver, forum_user, forum_pass):
                socketio.emit('bot_status', {'msg': '❌ No se pudo hacer login'})
                return
        else:
            socketio.emit('bot_status', {'msg': '✅ Sesión activa, reutilizando...', 'progreso': 10})

        # ── Armar lista de causas ─────────────────────────────────────────────
        if lista_exptes:
            # Viene del actualizador — normalizar claves y completar con DB
            lista_causas = []
            with app.app_context():
                for e in lista_exptes:
                    nro = e.get("nro") or e.get("numero", "")
                    tipo = e.get("tipo", "")
                    juzgado = e.get("juzgado", "") or ""
                    secretaria = e.get("secretaria", "") or ""

                    # Si no tiene secretaria o es SIN SECRETARIA, buscar en DB
                    if not secretaria or "SIN" in secretaria.upper():
                        db_causa = CausaInfo.query.filter(
                            CausaInfo.numero == nro,
                            CausaInfo.usuario_id == usuario_id
                        ).first()
                        if db_causa:
                            juzgado = db_causa.juzgado or juzgado
                            secretaria = db_causa.secretaria or secretaria

                    lista_causas.append({
                        "numero":     nro,
                        "tipo":       tipo,
                        "juzgado":    juzgado or "SIN JUZGADO",
                        "secretaria": secretaria or "SIN SECRETARIA",
                        "localidad":  e.get("localidad", "Capital"),
                    })
        else:
            # Sin lista: usar toda la DB
            with app.app_context():
                causas = CausaInfo.query.filter_by(usuario_id=usuario_id).all()
                lista_causas = [
                    {
                        "numero":     c.numero,
                        "tipo":       c.tipo or "",
                        "juzgado":    c.juzgado    or "SIN JUZGADO",
                        "secretaria": c.secretaria or "SIN SECRETARIA",
                    }
                    for c in causas
                ]

        if max_exptes and len(lista_causas) > max_exptes:
            socketio.emit('bot_status', {
                'msg': f'⚠️ MODO TRIAL: procesando {max_exptes} de {len(lista_causas)} expedientes',
                'progreso': 22
            })
            lista_causas = lista_causas[:max_exptes]

        total = len(lista_causas)
        socketio.emit('bot_status', {'msg': f'📁 {total} expedientes a completar', 'progreso': 25})

        for idx, causa in enumerate(lista_causas):
            nro      = causa["numero"]
            tipo     = causa.get("tipo", "")
            progreso = int(((idx + 1) / total) * 70) + 25

            socketio.emit('bot_status', {
                'msg': f'📂 Completando historial {nro} ({idx+1}/{total})',
                'progreso': progreso
            })

            # Buscar en DB la ruta correcta
            with app.app_context():
                db_causa = CausaInfo.query.filter(
                    CausaInfo.numero == nro,
                    CausaInfo.usuario_id == usuario_id
                ).first()
                print(f"  → DB lookup {nro}: {'ENCONTRADO' if db_causa else 'NO ENCONTRADO'} | juzgado={db_causa.juzgado if db_causa else 'N/A'}")
                if db_causa:
                    juzgado    = db_causa.juzgado or causa["juzgado"]
                    secretaria = db_causa.secretaria or causa["secretaria"]
                else:
                    juzgado    = causa["juzgado"]
                    secretaria = causa["secretaria"]

            ruta = os.path.join(
                "expedientes_clientes",
                usuario_nombre,
                juzgado,
                secretaria,
                nro
            )
            os.makedirs(ruta, exist_ok=True)

            localidad_expte = causa.get("localidad", "Capital")
            print(f"  → {nro}: localidad={localidad_expte}, causa keys={list(causa.keys())}")
            if entrar_a_expediente(driver, nro, tipo_codigo=tipo if tipo else None, localidad=localidad_expte):
                nuevos = sincronizar_pdfs(
                    driver, ruta, config.TEMP_DOWNLOAD_PATH,
                    cortar_si_existe=True
                )
                pdfs_descargados += nuevos
                if nuevos > 0:
                    exptes_procesados += 1
                    socketio.emit('bot_status', {
                        'msg': f'✅ {nro}: {nuevos} PDFs descargados',
                        'progreso': progreso
                    })
                else:
                    exptes_sin_nuevos += 1
                    socketio.emit('bot_status', {
                        'msg': f'📭 {nro}: ya estaba completo',
                        'progreso': progreso
                    })
            else:
                exptes_no_encontrados += 1
                socketio.emit('bot_status', {
                    'msg': f'⚠️ No se encontró {nro} en Forum',
                    'progreso': progreso
                })

        tiempo_total = int(time.time() - t0)
        mins = tiempo_total // 60
        segs = tiempo_total % 60
        tiempo_str = f"{mins}m {segs}s" if mins > 0 else f"{segs}s"

        socketio.emit('bot_status', {'msg': '🏁 Historial completado', 'progreso': 100})
        socketio.emit('bot_status', {'msg': '━' * 40})
        socketio.emit('bot_status', {'msg': '📊 RESUMEN COMPLETAR HISTORIAL'})
        socketio.emit('bot_status', {'msg': f'✅ Expedientes con PDFs nuevos: {exptes_procesados}'})
        socketio.emit('bot_status', {'msg': f'📄 Total PDFs descargados: {pdfs_descargados}'})
        socketio.emit('bot_status', {'msg': f'📭 Ya completos: {exptes_sin_nuevos}'})
        if exptes_no_encontrados > 0:
            socketio.emit('bot_status', {'msg': f'⚠️ No encontrados: {exptes_no_encontrados}'})
        socketio.emit('bot_status', {'msg': f'⏱️ Tiempo total: {tiempo_str}'})
        socketio.emit('bot_status', {'msg': '━' * 40})
        socketio.emit('bot_finished', {})

    except Exception as e:
        import traceback
        traceback.print_exc()
        socketio.emit('bot_status', {'msg': f'❌ Error crítico: {str(e)}'})
    finally:
        release_driver()