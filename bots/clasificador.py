# bots/clasificador.py

import os
import re
import time
import shutil
from bots.forum_driver import crear_driver, login_forum, buscar_expediente
from database.models import db, CausaInfo


def _limpiar_huerfanos(usuario_id, usuario_nombre, app, socketio):
    """Elimina de la DB los registros que no tienen carpeta física."""
    with app.app_context():
        registros = CausaInfo.query.filter_by(usuario_id=usuario_id).all()
        ruta_base = os.path.join(os.getcwd(), 'expedientes_clientes', usuario_nombre)
        eliminados = 0

        for registro in registros:
            encontrado = False
            for root, dirs, files in os.walk(ruta_base):
                if registro.numero in dirs:
                    encontrado = True
                    break
            if not encontrado:
                db.session.delete(registro)
                eliminados += 1
                socketio.emit('bot_log', {'log': [f'🧹 Huérfano eliminado de DB: {registro.numero}']})

        db.session.commit()
        socketio.emit('bot_log', {'log': [f'🧹 Limpieza lista: {eliminados} registros eliminados.']})


def ejecutar_clasificacion(usuario_id, usuario_nombre, socketio, app):
    # Obtener credenciales del usuario desde la DB
    with app.app_context():
        from database.models import Usuario
        usuario = db.session.get(Usuario, usuario_id)
        forum_user = usuario.forum_user
        forum_pass = usuario.forum_pass
    driver = crear_driver()
    t0 = time.time()

    # Contadores
    clasificados = 0
    no_encontrados = 0
    errores = 0

    try:
        socketio.emit('bot_status', {'msg': '🔑 Abriendo Forum...', 'progreso': 5})
        socketio.emit('bot_status', {'msg': '⚠️ Resolvé el Captcha e iniciá sesión', 'progreso': 10})

        if not login_forum(driver, forum_user, forum_pass):
            socketio.emit('bot_error', {'msg': '❌ No se pudo hacer login en Forum'})
            return

        ruta_base = os.path.join(os.getcwd(), 'expedientes_clientes', usuario_nombre)
        ruta_importados = os.path.join(ruta_base, 'IMPORTADOS')

        if not os.path.exists(ruta_importados):
            socketio.emit('bot_error', {'msg': '❌ No se encontró la carpeta IMPORTADOS'})
            return

        socketio.emit('bot_status', {'msg': '🧹 Sincronizando DB con carpetas...', 'progreso': 3})
        _limpiar_huerfanos(usuario_id, usuario_nombre, app, socketio)

        carpetas = [d for d in os.listdir(ruta_importados) if os.path.isdir(os.path.join(ruta_importados, d))]
        total = len(carpetas)
        socketio.emit('bot_log', {'log': [f'📁 {total} carpetas para clasificar.']})

        for idx, nombre_folder in enumerate(carpetas):
            juz_final = "POR CLASIFICAR"
            sec_final = "REVISAR"
            demandado_final = "CARATULA NO ENCONTRADA"

            parte_nro = nombre_folder.split(' _ ')[0] if ' _ ' in nombre_folder else nombre_folder

            match = re.search(r'\b(\d{5,6})\b', parte_nro)
            if not match:
                socketio.emit('bot_log', {'log': [f'⚠️ Saltado: {nombre_folder} (sin número válido)']})
                errores += 1
                continue

            nro_solo = match.group(1)

            progreso = int(((idx + 1) / total) * 85) + 10
            socketio.emit('bot_status', {
                'msg': f'⚖️ Clasificando: {nro_solo} ({idx+1}/{total})',
                'progreso': progreso
            })

            datos = buscar_expediente(driver, nro_solo)
            if datos:
                juz_final = datos['juzgado']
                sec_final = datos['secretaria']
                demandado_final = datos['caratula']
                nro_completo = datos.get('nro_completo', nro_solo)
                socketio.emit('bot_log', {'log': [f'✅ {nro_completo} → {juz_final}']})
                clasificados += 1
            else:
                nro_completo = nro_solo
                socketio.emit('bot_log', {'log': [f'❌ No encontrado en Forum: {nro_solo}']})
                no_encontrados += 1

            ruta_destino = os.path.join(ruta_base, juz_final, sec_final, nro_completo)
            os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)

            try:
                ruta_origen = os.path.join(ruta_importados, nombre_folder)
                if not os.path.exists(ruta_destino):
                    shutil.move(ruta_origen, ruta_destino)
            except Exception as e:
                socketio.emit('bot_log', {'log': [f'💥 Error moviendo {nro_solo}: {str(e)}']})
                errores += 1
                continue

            try:
                with app.app_context():
                    existe = CausaInfo.query.filter_by(
                        numero=nro_completo, usuario_id=usuario_id
                    ).first()
                    if not existe:
                        nueva = CausaInfo(
                            numero=nro_completo,
                            juzgado=juz_final,
                            secretaria=sec_final,
                            demandado=demandado_final,
                            estado="En Trámite",
                            usuario_id=usuario_id
                        )
                        db.session.add(nueva)
                        db.session.commit()
            except Exception as e:
                socketio.emit('bot_log', {'log': [f'💥 Error en DB para {nro_solo}: {str(e)}']})
                errores += 1

        # ✅ RESUMEN FINAL
        tiempo_total = int(time.time() - t0)
        mins = tiempo_total // 60
        segs = tiempo_total % 60
        tiempo_str = f"{mins}m {segs}s" if mins > 0 else f"{segs}s"

        socketio.emit('bot_status', {'msg': '✅ Clasificación finalizada', 'progreso': 100})
        socketio.emit('bot_log', {'log': ['━' * 40]})
        socketio.emit('bot_log', {'log': [f'📊 RESUMEN CLASIFICACIÓN']})
        socketio.emit('bot_log', {'log': [f'✅ Clasificados correctamente: {clasificados}']})
        socketio.emit('bot_log', {'log': [f'❌ No encontrados en Forum: {no_encontrados}']})
        if errores > 0:
            socketio.emit('bot_log', {'log': [f'⚠️ Errores: {errores}']})
        socketio.emit('bot_log', {'log': [f'⏱️ Tiempo total: {tiempo_str}']})
        socketio.emit('bot_log', {'log': ['━' * 40]})
        socketio.emit('bot_finished', {})

    except Exception as e:
        import traceback
        traceback.print_exc()
        socketio.emit('bot_error', {'msg': f'❌ Error crítico: {str(e)}'})
    finally:
        driver.quit()