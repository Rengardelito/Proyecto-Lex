# bots/sincronizador.py
import os
import re
import time
import shutil
from datetime import datetime
from bots.forum_driver import crear_driver, login_forum, entrar_a_expediente, sincronizar_pdfs
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

    driver = crear_driver(temp_download_path=config.TEMP_DOWNLOAD_PATH)
    t0 = time.time()

    exptes_sincronizados = 0
    pdfs_descargados = 0
    exptes_sin_novedades = 0
    exptes_no_encontrados = 0

    try:
        socketio.emit('bot_status', {'msg': '🔑 Abriendo Forum...', 'progreso': 5})
        socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})

        if not login_forum(driver, forum_user, forum_pass):
            socketio.emit('bot_status', {'msg': '❌ No se pudo hacer login'})
            return

        # ✅ Limpiamos temp_downloads al inicio
        _limpiar_temp(socketio)

        socketio.emit('bot_status', {'msg': '🚀 Sesión iniciada. Buscando expedientes...', 'progreso': 20})

        with app.app_context():
            causas = CausaInfo.query.filter_by(usuario_id=usuario_id).all()
            lista_causas = [
                {
                    "numero": c.numero,
                    "juzgado": c.juzgado,
                    "secretaria": c.secretaria,
                    "caratula": c.demandado
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
        driver.quit()