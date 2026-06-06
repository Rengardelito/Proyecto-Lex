# bots/recuperador.py
import time
from database.models import db, CausaInfo, Usuario
from bots.forum_driver import login_forum, buscar_expediente
from bots.driver_manager import get_driver, release_driver, is_logged_in, marcar_ocupado, marcar_libre
import config

LOCALIDADES_PROVINCIAL = [
    'Capital', 'Alvear', 'Bella Vista', 'Beron de Astrada', 'Caa Cati',
    'Colonia Liebig', 'Concepcion', 'Curuzú Cuatiá', 'Empedrado', 'Esquina',
    'Gdor. Martinez', 'Gdor. Virasoro', 'Goya', 'Ita Ibate', 'Itati',
    'Ituzaingo', 'La Cruz', 'Loreto', 'Mburucuya', 'Mercedes', 'Mocoreta',
    'Monte Caseros', 'Paso de la Patria', 'Paso de los Libres', 'Perugorria',
    'Saladas', 'San Carlos', 'San Cosme', 'San Luis del Palmar', 'San Miguel',
    'San Roque', 'Santa Lucia', 'Santa Rosa', 'Santo Tome', 'Sauce', 'Yapeyu'
]

def _localidad_en_nombre(juzgado):
    juzgado_upper = juzgado.upper()
    for loc in LOCALIDADES_PROVINCIAL:
        if loc.upper() in juzgado_upper:
            return loc
    return None

def ejecutar_recuperar_caratulas(usuario_id, usuario_nombre, localidades_mapa, socketio, app):
    with app.app_context():
        usuario    = db.session.get(Usuario, usuario_id)
        forum_user = usuario.forum_user
        forum_pass = usuario.forum_pass

    driver = get_driver(temp_download_path=config.TEMP_DOWNLOAD_PATH)
    marcar_ocupado()
    t0 = time.time()
    actualizados   = 0
    no_encontrados = 0

    try:
        if not is_logged_in():
            socketio.emit('bot_status', {'msg': '⚠️ Resolvé el captcha e iniciá sesión'})
            if not login_forum(driver, forum_user, forum_pass):
                socketio.emit('bot_status', {'msg': '❌ No se pudo hacer login'})
                return
        else:
            socketio.emit('bot_status', {'msg': '✅ Sesión activa, reutilizando...'})

        socketio.emit('bot_status', {'msg': '✅ Buscando carátulas...'})

        with app.app_context():
            causas = CausaInfo.query.filter(
                CausaInfo.usuario_id == usuario_id,
                CausaInfo.demandado == 'SIN CARATULAR'
            ).all()
            lista = [{'id': c.id, 'numero': c.numero, 'tipo': c.tipo or '',
                      'juzgado': c.juzgado or ''} for c in causas]

        total = len(lista)
        socketio.emit('bot_status', {'msg': f'📋 {total} expedientes sin carátula'})

        for idx, causa in enumerate(lista):
            nro      = causa['numero']
            nro_solo = nro.split('-')[0]
            tipo     = causa['tipo']
            juzgado  = causa['juzgado']
            progreso = int(((idx + 1) / total) * 100)

            localidad = localidades_mapa.get(juzgado)
            if not localidad:
                localidad = _localidad_en_nombre(juzgado) or 'Capital'

            socketio.emit('bot_status', {
                'msg': f'🔍 ({idx+1}/{total}) {nro} — {localidad}'
            })

            datos = buscar_expediente(driver, nro_solo,
                                      tipo_codigo=tipo or None,
                                      localidad=localidad)

            if datos and datos.get('caratula') and datos['caratula'] != 'SIN CARATULAR':
                with app.app_context():
                    c = db.session.get(CausaInfo, causa['id'])
                    if c:
                        c.demandado = datos['caratula']
                        db.session.commit()
                actualizados += 1
                socketio.emit('bot_status', {
                    'msg': f'✅ {nro}: {datos["caratula"][:50]}'
                })
            else:
                no_encontrados += 1
                socketio.emit('bot_status', {
                    'msg': f'⚠️ {nro}: no encontrado en {localidad}'
                })

        tiempo = int(time.time() - t0)
        mins = tiempo // 60
        segs = tiempo % 60
        socketio.emit('bot_status', {'msg': '━' * 40})
        socketio.emit('bot_status', {'msg': '📊 RESUMEN RECUPERAR CARÁTULAS'})
        socketio.emit('bot_status', {'msg': f'✅ Actualizados: {actualizados}'})
        socketio.emit('bot_status', {'msg': f'⚠️ No encontrados: {no_encontrados}'})
        socketio.emit('bot_status', {'msg': f'⏱️ Tiempo: {mins}m {segs}s'})
        socketio.emit('bot_status', {'msg': '━' * 40})
        socketio.emit('bot_finished', {})

    except Exception as e:
        import traceback
        traceback.print_exc()
        socketio.emit('bot_status', {'msg': f'❌ Error: {str(e)}'})
    finally:
        marcar_libre()
        release_driver()