import re
from database.models import CausaInfo, db
import time
import shutil
import os
import threading
import json
from datetime import date, datetime
from pathlib import Path
from collections import defaultdict
from config import LICENSE_SERVER_URL
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory, make_response
from flask_socketio import SocketIO
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from fpdf import FPDF
import fitz

import config
from config import BASE_PATH, BASE_DATOS_PDFS, OUTPUT_STATIC, CARPETA_HOTFOLDER
from database.models import db, Usuario, CausaInfo, Vencimiento, NotaPersonal
from helpers.expte_parser import extraer_nro_expte_de_emergencia
from helpers.migrador_old import ejecutar_migracion_legado
from helpers.features import requiere_feature, tiene_feature, get_plan, max_exptes_trial

app = Flask(__name__)

app.secret_key = 'lexview_secret_key_2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{config.DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    if Usuario.query.count() == 0:
        return redirect(url_for('setup'))
    return redirect(url_for('login'))


# ============================================================
# SETUP
# ============================================================
@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if Usuario.query.count() > 0:
        return redirect(url_for('login'))

    if request.method == 'POST':
        username   = request.form.get('username', '').strip()
        password   = request.form.get('password', '')
        password2  = request.form.get('password2', '')
        matricula  = request.form.get('matricula', '').strip()
        forum_user = request.form.get('forum_user', '').strip()
        forum_pass = request.form.get('forum_pass', '')

        if not username or not password or not forum_user or not forum_pass:
            flash('Completá todos los campos obligatorios', 'error')
            return render_template('setup.html')

        if ' ' in username or any(c in username for c in 'áéíóúÁÉÍÓÚñÑ'):
            flash('El usuario no puede tener espacios ni tildes', 'error')
            return render_template('setup.html')

        if password != password2:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('setup.html')

        if len(password) < 4:
            flash('La contraseña debe tener al menos 4 caracteres', 'error')
            return render_template('setup.html')

        import requests as req
        from config import get_hardware_id
        hw_id = get_hardware_id()

        try:
            r = req.post(
                'https://lexviewpro.com.ar/api/verify',
                json={'hardware_id': hw_id},
                timeout=5
            )
            data = r.json()
            if not data.get('valid'):
                flash('Dispositivo no autorizado. Contactá al desarrollador.', 'error')
                return render_template('setup.html')
            # Guardar plan del servidor
            plan_servidor = data.get('plan', 'basic')
        except Exception:
            flash(
                '⚠️ No se pudo verificar la licencia online. '
                'Podés continuar, pero necesitarás conexión a internet '
                'para validar el dispositivo.',
                'warning'
            )
            plan_servidor = 'basic'

        nuevo = Usuario(
            username        = username,
            matricula       = matricula or None,
            forum_user      = forum_user,
            forum_pass      = forum_pass,
            hardware_id     = hw_id,
            licencia_activa = True,
            plan            = plan_servidor
        )
        nuevo.set_password(password)
        db.session.add(nuevo)
        db.session.commit()

        os.makedirs(os.path.join('expedientes_clientes', username), exist_ok=True)
        login_user(nuevo)
        flash(f'¡Bienvenido {username}! Tu cuenta fue creada.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('setup.html')


# ============================================================
# LOGIN
# ============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('username', '').strip()
        pass_input = request.form.get('password', '')
        user = Usuario.query.filter_by(username=user_input).first()
        if user and user.check_password(pass_input):
            # Sincronizar plan desde el servidor al hacer login
            try:
                import requests as req
                from config import get_hardware_id
                hw_id = get_hardware_id()
                r = req.post(
                    'https://lexviewpro.com.ar/api/verify',
                    json={'hardware_id': hw_id},
                    timeout=4
                )
                data = r.json()
                if data.get('valid'):
                    plan_nuevo = data.get('plan', user.plan)
                    vence_str  = data.get('vence')
                    if plan_nuevo != user.plan:
                        user.plan = plan_nuevo
                    if vence_str and vence_str != 'sin_vencimiento':
                        from datetime import date as _date
                        user.licencia_vence = _date.fromisoformat(vence_str)
                    db.session.commit()
            except Exception:
                pass  # Sin internet → usar plan guardado localmente

            login_user(user)
            flash(f'Bienvenido {user.username}', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    response = make_response(redirect(url_for('login')))
    response.set_cookie('session', '', expires=0)
    return response


# ============================================================
# CONFIGURAR FORUM
# ============================================================
@app.route('/configurar_forum', methods=['GET', 'POST'])
@login_required
def configurar_forum():
    if request.method == 'POST':
        current_user.forum_user = request.form.get('forum_user', '').strip()
        current_user.forum_pass = request.form.get('forum_pass', '')
        current_user.matricula  = request.form.get('matricula', '').strip()
        db.session.commit()
        flash('Credenciales de Forum guardadas', 'success')
        return redirect(url_for('dashboard'))
    return render_template('configurar_forum.html', usuario=current_user)


@app.route('/seleccionar_carpeta', methods=['POST'])
@login_required
def seleccionar_carpeta():
    carpeta = request.form.get('ruta', '').strip()
    if carpeta and os.path.isdir(carpeta):
        return jsonify({"success": True, "ruta": carpeta})
    return jsonify({"success": False, "message": "Ruta inválida o no encontrada"})


# ============================================================
# IMPORTAR
# ============================================================
@app.route('/importar_legado', methods=['POST'])
@login_required
def importar_legado():
    ruta_origen = CARPETA_HOTFOLDER
    u_name = current_user.username
    if not os.listdir(ruta_origen):
        return jsonify({"success": False, "message": "La carpeta 'IMPORTAR_AQUI' está vacía."}), 400
    try:
        def hilo():
            from bots.migrador import ejecutar_migracion
            ejecutar_migracion(ruta_origen, u_name, socketio)
        t = threading.Thread(target=hilo)
        t.daemon = True
        t.start()
        return jsonify({"success": True, "message": "Iniciando migración..."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/importar_desde_lista', methods=['POST'])
@login_required
def importar_desde_lista():
    lista_raw = request.form.get('lista', '').strip()
    u_name = current_user.username
    if not lista_raw:
        return jsonify({"success": False, "message": "La lista está vacía."}), 400
    lineas = [l.strip() for l in lista_raw.splitlines() if l.strip()]
    if not lineas:
        return jsonify({"success": False, "message": "No se encontraron expedientes válidos."}), 400
    try:
        def hilo():
            ruta_importados = os.path.join('expedientes_clientes', u_name, 'IMPORTADOS')
            os.makedirs(ruta_importados, exist_ok=True)
            creados = 0
            for linea in lineas:
                linea = linea.strip()
                if not linea:
                    continue
                nombre = re.sub(r'\s+', '_', linea).replace('/', '-')
                ruta_expte = os.path.join(ruta_importados, nombre)
                if not os.path.exists(ruta_expte):
                    os.makedirs(ruta_expte)
                    creados += 1
                    socketio.emit('bot_status', {'msg': f'✅ Carpeta creada: {nombre}'})
                else:
                    socketio.emit('bot_status', {'msg': f'⏩ Ya existe: {nombre}'})
            socketio.emit('bot_status', {'msg': f'🏁 {creados} carpetas creadas en IMPORTADOS'})
            socketio.emit('bot_finished', {})
        t = threading.Thread(target=hilo, daemon=True)
        t.start()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================================
# DASHBOARD
# ============================================================
@app.route('/')
@login_required
def dashboard():
    usuario = current_user.username
    hoy = date.today()
    causas_db = CausaInfo.query.filter_by(usuario_id=current_user.id).all()
    base_path = Path(os.path.join(BASE_DATOS_PDFS, usuario))
    estructura_carpetas = []

    if base_path.exists():
        for juzgado_path in sorted(base_path.iterdir(), key=lambda x: [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', x.name)]):
            if not juzgado_path.is_dir():
                continue
            nombre_dir = juzgado_path.name
            secretarias = []
            total_en_juzgado = 0

            if nombre_dir == "IMPORTADOS":
                exptes_sueltos = []
                for e in juzgado_path.iterdir():
                    if e.is_dir():
                        archivos_en_disco = [f for f in os.listdir(e) if f.lower().endswith('.pdf')]
                        exptes_sueltos.append({'numero': e.name, 'info': None, 'archivos_disco': sorted(archivos_en_disco)})
                if exptes_sueltos:
                    secretarias.append({'nombre': 'MIGRACIONES RECIENTES', 'expedientes': exptes_sueltos})
                    total_en_juzgado = len(exptes_sueltos)
            else:
                for sec_path in sorted(juzgado_path.iterdir()):
                    if not sec_path.is_dir():
                        continue
                    exptes = []
                    for e in sec_path.iterdir():
                        if e.is_dir():
                            nro = e.name
                            archivos_en_disco = [f for f in os.listdir(e) if f.lower().endswith('.pdf')]
                            archivos_sin_caratula = [f for f in archivos_en_disco if f != 'caratula_pro.pdf']
                            ultimo_archivo = sorted(archivos_sin_caratula, reverse=True)[0] if archivos_sin_caratula else None
                            estado_archivo = None
                            if ultimo_archivo:
                                partes = ultimo_archivo.replace('.pdf', '').split(' - ', 1)
                                estado_archivo = partes[1].strip() if len(partes) > 1 else ultimo_archivo.replace('.pdf', '')
                            info_db = next((c for c in causas_db if c.numero == nro), None)
                            exptes.append({'numero': nro, 'info': info_db, 'archivos_disco': sorted(archivos_en_disco), 'estado_archivo': estado_archivo})
                    if exptes:
                        secretarias.append({'nombre': sec_path.name, 'expedientes': exptes})
                        total_en_juzgado += len(exptes)

            if secretarias:
                estructura_carpetas.append({'nombre_juzgado': nombre_dir, 'secretarias': secretarias, 'total_exptes': total_en_juzgado})

    notas_db = NotaPersonal.query.filter(
        NotaPersonal.usuario_id == current_user.id,
        NotaPersonal.fecha >= hoy
    ).order_by(NotaPersonal.fecha).all()

    vencimientos_db = Vencimiento.query.filter(
        Vencimiento.usuario_id == current_user.id,
        Vencimiento.fecha >= hoy
    ).order_by(Vencimiento.fecha).all()

    notas_json = {}
    for n in notas_db:
        f = n.fecha.isoformat()
        notas_json.setdefault(f, []).append({'tipo': 'agenda', 'texto': n.evento})
    for v in vencimientos_db:
        f = v.fecha.isoformat()
        notas_json.setdefault(f, []).append({'tipo': 'vencimiento', 'texto': v.titulo})

    return render_template('dashboard.html',
                           usuario=usuario,
                           causas=causas_db,
                           estructura=estructura_carpetas,
                           notas_db=notas_db,
                           vencimientos_db=vencimientos_db,
                           notas_json=notas_json,
                           plan=get_plan(current_user))


# ============================================================
# NOTAS Y VENCIMIENTOS
# ============================================================
@app.route('/agregar_evento', methods=['POST'])
@login_required
def agregar_evento():
    fecha_str = request.form.get('fecha')
    evento = request.form.get('evento', '').strip()
    if fecha_str and evento:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        existe = NotaPersonal.query.filter_by(usuario_id=current_user.id, fecha=fecha, evento=evento).first()
        if not existe:
            db.session.add(NotaPersonal(usuario_id=current_user.id, fecha=fecha, evento=evento))
            db.session.commit()
            flash('Evento agendado', 'success')
    return redirect(url_for('dashboard'))


@app.route('/eliminar_nota/<int:id>')
@login_required
def eliminar_nota(id):
    nota = db.session.get(NotaPersonal, id)
    if nota and nota.usuario_id == current_user.id:
        db.session.delete(nota)
        db.session.commit()
        flash('Evento eliminado', 'success')
    return redirect(url_for('dashboard'))


@app.route('/eliminar_vencimiento/<int:id>')
@login_required
def eliminar_vencimiento(id):
    venc = db.session.get(Vencimiento, id)
    if venc and venc.usuario_id == current_user.id:
        db.session.delete(venc)
        db.session.commit()
        flash('Vencimiento eliminado', 'success')
    return redirect(url_for('dashboard'))


@app.route('/agregar_vencimiento_ajax', methods=['POST'])
@login_required
def agregar_vencimiento_ajax():
    nro_expte = request.form.get('nro_expte')
    fecha_str = request.form.get('fecha')
    titulo    = request.form.get('titulo')
    try:
        nueva_fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
        nuevo_vence = Vencimiento(titulo=f"Exp. {nro_expte}: {titulo}", fecha=nueva_fecha, usuario_id=current_user.id)
        db.session.add(nuevo_vence)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ============================================================
# BOTS — protegidos por plan
# ============================================================
@app.route('/run_clasificador', methods=['POST'])
@login_required
@requiere_feature('clasificar')
def run_clasificador():
    u_id, u_name = current_user.id, current_user.username
    def hilo():
        from bots.clasificador import ejecutar_clasificacion
        ejecutar_clasificacion(u_id, u_name, socketio, app)
    threading.Thread(target=hilo, daemon=True).start()
    return jsonify({"success": True})


@app.route('/run_actualizador', methods=['POST'])
@login_required
@requiere_feature('actualizar')
def run_actualizador():
    u_id      = current_user.id
    u_name    = current_user.username
    fecha_str = request.form.get('fecha')
    max_exptes = max_exptes_trial(current_user)
    def hilo():
        from bots.actualizador import ejecutar_actualizacion
        ejecutar_actualizacion(u_id, u_name, socketio, app, fecha_str=fecha_str, max_exptes=max_exptes)
    threading.Thread(target=hilo, daemon=True).start()
    return jsonify({"success": True})


@app.route('/run_sincronizador', methods=['POST'])
@login_required
@requiere_feature('sincronizar')
def run_sincronizador():
    u_id, u_name = current_user.id, current_user.username
    def hilo():
        from bots.sincronizador import ejecutar_sincronizacion
        ejecutar_sincronizacion(u_id, u_name, socketio, app)
    threading.Thread(target=hilo, daemon=True).start()
    return jsonify({"success": True})


@app.route('/run_auditoria', methods=['POST'])
@login_required
@requiere_feature('auditoria')
def run_auditoria():
    u_id   = current_user.id
    u_name = current_user.username
    lista  = request.form.get('lista', '')
    modo   = request.form.get('modo', 'ultimo')
    if not lista.strip():
        return jsonify({"success": False, "message": "Lista vacía"})
    def hilo():
        from bots.auditor import ejecutar_auditoria
        ejecutar_auditoria(u_id, u_name, socketio, app, lista, modo)
    threading.Thread(target=hilo, daemon=True).start()
    return jsonify({"success": True})


# ============================================================
# VISOR
# ============================================================
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]


@app.route('/visor/<juzgado>/<secretaria>/<expte>')
@login_required
def visor(juzgado, secretaria, expte):
    ruta_carpeta = os.path.join(BASE_DATOS_PDFS, current_user.username, juzgado, secretaria, expte)
    ruta_pdf_caratula = os.path.join(ruta_carpeta, 'caratula_pro.pdf')
    safe_n = expte.replace("/", "_").replace(" ", "_")
    nombre_f = f"{current_user.username}_{safe_n}.pdf".lower()
    ruta_destino_final = os.path.join(OUTPUT_STATIC, nombre_f)
    os.makedirs(OUTPUT_STATIC, exist_ok=True)
    info_causa = CausaInfo.query.filter_by(numero=expte, usuario_id=current_user.id).first()
    caratula_texto = info_causa.demandado if info_causa else "SIN CARATULAR"

    try:
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_line_width(1);  pdf.rect(10, 10, 190, 277)
        pdf.set_line_width(0.2); pdf.rect(12, 12, 186, 273)
        pdf.set_font("helvetica", "B", 60)
        with pdf.rotation(90, x=25, y=180):
            pdf.text(25, 180, expte)
        pdf.set_y(30)
        pdf.set_font("helvetica", "B", 22)
        pdf.cell(0, 10, "REPÚBLICA ARGENTINA", align="C", ln=True)
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 5, "PODER JUDICIAL DE LA PROVINCIA DE CORRIENTES", align="C", ln=True)
        pdf.set_line_width(0.8)
        pdf.line(60, 52, 150, 52); pdf.line(60, 53.5, 150, 53.5)
        pdf.set_y(75)
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(0, 8, "EXPEDIENTE NÚMERO", align="C", ln=True)
        pdf.set_font("helvetica", "B", 55)
        pdf.cell(0, 25, expte, align="C", ln=True)
        pdf.set_y(120)
        pdf.set_font("helvetica", "B", 18)
        pdf.multi_cell(w=180, h=10, txt=juzgado.upper(), align="C")
        pdf.set_font("helvetica", "", 14)
        pdf.multi_cell(w=180, h=8, txt=f"Secretaría: {secretaria.upper()}", align="C")
        pdf.set_y(175); pdf.set_line_width(0.5)
        pdf.line(40, 175, 170, 175)
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 10, "CARÁTULA / PARTES", align="C", ln=True)
        pdf.set_y(188); pdf.set_font("helvetica", "B", 18)
        pdf.multi_cell(w=160, h=10, txt=caratula_texto.upper(), align="C")
        y_fin = pdf.get_y() + 5; pdf.line(40, y_fin, 170, y_fin)
        pdf.set_y(245); pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 8, "MATERIA", align="C", ln=True)
        pdf.set_font("helvetica", "BU", 16)
        pdf.cell(0, 10, "CIVIL Y COMERCIAL", align="C", ln=True)
        pdf.set_y(272); pdf.set_font("helvetica", "I", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 10, f"Generado por LexView Pro - {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C", ln=True)
        pdf.output(ruta_pdf_caratula)
    except Exception as e:
        print(f"❌ Error carátula: {e}")

    if os.path.exists(ruta_carpeta):
        archivos_raw = [f for f in os.listdir(ruta_carpeta) if f.lower().endswith('.pdf') and f != 'caratula_pro.pdf']
        archivos = sorted(archivos_raw, key=natural_sort_key)
        doc_final = fitz.open()
        if os.path.exists(ruta_pdf_caratula):
            with fitz.open(ruta_pdf_caratula) as c:
                doc_final.insert_pdf(c)
        for f_nombre in archivos:
            r_full = os.path.join(ruta_carpeta, f_nombre)
            if os.path.getsize(r_full) > 100:
                with fitz.open(r_full) as d:
                    doc_final.insert_pdf(d)
        doc_final.save(ruta_destino_final, garbage=4, deflate=True)
        doc_final.close()

    return render_template('index.html', archivo_pdf=nombre_f, expte=expte, caratula_texto=caratula_texto)


@app.route('/obtener_pdf/<nombre_pdf>')
@login_required
def obtener_pdf(nombre_pdf):
    return send_from_directory(OUTPUT_STATIC, nombre_pdf)


@app.route('/guardar_nota', methods=['POST'])
@login_required
def guardar_nota():
    causa_id = request.form.get('causa_id')
    nota = request.form.get('nota', '')
    try:
        causa = db.session.get(CausaInfo, int(causa_id))
        if causa and causa.usuario_id == current_user.id:
            causa.notas = nota
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'No autorizado'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/subir_pdf', methods=['POST'])
@login_required
def subir_pdf():
    nro_expte  = request.form.get('nro_expte')
    juzgado    = request.form.get('juzgado')
    secretaria = request.form.get('secretaria')
    archivos   = request.files.getlist('pdfs')
    ruta = os.path.join(BASE_DATOS_PDFS, current_user.username, juzgado, secretaria, nro_expte)
    os.makedirs(ruta, exist_ok=True)
    guardados = 0
    for archivo in archivos:
        if archivo.filename.endswith('.pdf'):
            archivo.save(os.path.join(ruta, archivo.filename))
            guardados += 1
    return jsonify({'success': True, 'cantidad': guardados})


# ============================================================
# CÉDULAS Y MANDAMIENTOS — protegidas por plan
# ============================================================
@app.route('/cedulas/proveidos/<juzgado>/<secretaria>/<expte>')
@login_required
@requiere_feature('cedulas')
def listar_proveidos_expte(juzgado, secretaria, expte):
    from helpers.cedulas import listar_proveidos
    ruta_carpeta = os.path.join(BASE_DATOS_PDFS, current_user.username, juzgado, secretaria, expte)
    proveidos = listar_proveidos(ruta_carpeta)
    return jsonify({"proveidos": proveidos})


@app.route('/cedulas/texto_proveido')
@login_required
@requiere_feature('cedulas')
def texto_proveido():
    from helpers.cedulas import extraer_texto_proveido
    juzgado    = request.args.get('juzgado', '')
    secretaria = request.args.get('secretaria', '')
    expte      = request.args.get('expte', '')
    nombre     = request.args.get('nombre', '')
    ruta = os.path.join(BASE_DATOS_PDFS, current_user.username, juzgado, secretaria, expte, nombre)
    if not os.path.exists(ruta):
        return jsonify({"error": "Archivo no encontrado"}), 404
    texto = extraer_texto_proveido(ruta)
    return jsonify({"texto": texto})


@app.route('/cedulas/generar', methods=['POST'])
@login_required
@requiere_feature('cedulas')
def generar_cedula_route():
    from helpers.cedulas import generar_cedula
    tipo = request.form.get('tipo', 'cedula_local')
    datos = {
        "juzgado":              request.form.get('juzgado', ''),
        "nro_expte":            request.form.get('nro_expte', ''),
        "caratula":             request.form.get('caratula', ''),
        "juez":                 request.form.get('juez', ''),
        "secretaria":           request.form.get('secretaria', ''),
        "domicilio_juzgado":    request.form.get('domicilio_juzgado', ''),
        "correo_juzgado":       request.form.get('correo_juzgado', ''),
        "tel_juzgado":          request.form.get('tel_juzgado', ''),
        "dependencia_dest":     request.form.get('dependencia_dest', ''),
        "personas_autorizadas": request.form.get('personas_autorizadas', ''),
        "objeto_notificacion":  request.form.get('objeto_notificacion', ''),
        "destinatario":         request.form.get('destinatario', ''),
        "domicilio":            request.form.get('domicilio', ''),
        "caracter_domicilio":   request.form.get('caracter_domicilio', ''),
        "localidad":            request.form.get('localidad', ''),
        "texto_providencia":    request.form.get('texto_providencia', ''),
        "copias_traslado":      request.form.get('copias_traslado', ''),
        "url_drive":            request.form.get('url_drive', ''),
        "fecha_dia":            request.form.get('fecha_dia', ''),
        "fecha_mes":            request.form.get('fecha_mes', ''),
        "fecha_anio":           request.form.get('fecha_anio', ''),
    }
    nro_safe = datos['nro_expte'].replace('/', '-').replace(' ', '_')
    tipo_label = {
        'cedula_local':      'Cedula_Local',
        'cedula_ley':        'Cedula_Ley22172',
        'mandamiento_local': 'Mandamiento_Local',
        'mandamiento_ley':   'Mandamiento_Ley22172',
    }.get(tipo, 'Documento')
    nombre_archivo = f"{tipo_label}_{nro_safe}.docx"
    ruta_temp = os.path.join(config.TEMP_DOWNLOAD_PATH, nombre_archivo)
    generar_cedula(datos, tipo, ruta_temp)
    return send_from_directory(config.TEMP_DOWNLOAD_PATH, nombre_archivo,
                               as_attachment=True, download_name=nombre_archivo)


# ============================================================
# DOCUMENTAL
# ============================================================
@app.route('/documental/subir', methods=['POST'])
@login_required
def subir_documental_vps():
    import requests as req
    import traceback
    from config import get_hardware_id
    try:
        data       = request.get_json(force=True) or {}
        juzgado    = data.get('juzgado', '')
        secretaria = data.get('secretaria', '')
        expte      = data.get('expte', '')
        archivos   = data.get('archivos', [])
        if not archivos:
            return jsonify({'error': 'No se seleccionaron archivos'}), 400
        ruta_carpeta = os.path.join(BASE_DATOS_PDFS, current_user.username, juzgado, secretaria, expte)
        rutas_validas = []
        for nombre in archivos:
            ruta = os.path.join(ruta_carpeta, nombre)
            if os.path.exists(ruta) and nombre.lower().endswith('.pdf'):
                rutas_validas.append((nombre, ruta))
        if not rutas_validas:
            return jsonify({'error': 'No se encontraron los archivos'}), 404
        hw_id = get_hardware_id()
        files = [('pdfs', (nombre, open(ruta, 'rb'), 'application/pdf')) for nombre, ruta in rutas_validas]
        r = req.post('https://lexviewpro.com.ar/api/documental/subir',
                     files=files, headers={'X-Hardware-ID': hw_id}, timeout=30)
        for _, (_, f, _) in files:
            f.close()
        if r.status_code != 200:
            return jsonify({'error': f'Error VPS: {r.text}'}), 500
        resultado = r.json()
        return jsonify({'ok': True, 'url': resultado['url'], 'token': resultado['token']})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/documental/listar/<juzgado>/<secretaria>/<expte>')
@login_required
def listar_pdfs_expte(juzgado, secretaria, expte):
    ruta_carpeta = os.path.join(BASE_DATOS_PDFS, current_user.username, juzgado, secretaria, expte)
    if not os.path.isdir(ruta_carpeta):
        return jsonify({'archivos': []})
    patron_fecha_escrito = re.compile(r'^\d{1,2}[/_]\d{1,2}[/_]\d{2,4}')
    archivos = []
    for nombre in sorted(os.listdir(ruta_carpeta), reverse=True):
        if not nombre.lower().endswith('.pdf') or nombre == 'caratula_pro.pdf':
            continue
        partes = nombre.replace('.pdf', '').split(' - ', 1)
        if len(partes) < 2:
            continue
        fecha_str = partes[0].strip()
        extracto  = partes[1].strip()
        es_escrito = patron_fecha_escrito.match(extracto)
        try:
            fecha_display = datetime.strptime(fecha_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            fecha_display = fecha_str
        archivos.append({'nombre': nombre, 'fecha': fecha_display,
                         'extracto': extracto[:80], 'es_escrito': bool(es_escrito)})
    return jsonify({'archivos': archivos})


# ============================================================
# API
# ============================================================
@app.route('/api/device_id')
def api_device_id():
    from config import get_hardware_id
    try:
        hw_id = get_hardware_id()
        return jsonify({'hardware_id': hw_id})
    except Exception as e:
        return jsonify({'hardware_id': None, 'error': str(e)})


@app.route('/api/mi_plan')
@login_required
def mi_plan():
    from helpers.features import FEATURES
    plan = get_plan(current_user)
    vence = current_user.licencia_vence
    features_disponibles = [f for f, planes in FEATURES.items() if plan in planes]
    return jsonify({
        'plan':     plan,
        'vence':    str(vence) if vence else None,
        'features': features_disponibles
    })


# ============================================================
# ARRANQUE
# ============================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)