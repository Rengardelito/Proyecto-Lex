# import shutil
# import pdfkit
# import json
# import os
# from datetime import date # <--- Nuevo para la agenda
# from flask import Flask, render_template, send_file, request, redirect, url_for, session, flash
# from functools import wraps
# from PyPDF2 import PdfMerger
# from flask_sqlalchemy import SQLAlchemy
# from werkzeug.utils import secure_filename
# import pymysql

# pymysql.install_as_MySQLdb()

# app = Flask(__name__)
# app.secret_key = 'tu_llave_secreta_muy_segura'

# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:240588@127.0.0.1:3307/lexview'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# db = SQLAlchemy(app)

# # --- MODELOS ---
# class Usuario(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(50), unique=True, nullable=False)
#     password = db.Column(db.String(50), nullable=False)

# class CausaInfo(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     nombre_carpeta = db.Column(db.String(100), unique=True)
#     estado = db.Column(db.String(100), default="En Trámite")
#     monto = db.Column(db.String(50), default="0.00")
#     notas = db.Column(db.Text, default="")

# # --- NUEVO MODELO PARA LA AGENDA ---
# class Vencimiento(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     fecha = db.Column(db.Date, nullable=False)
#     titulo = db.Column(db.String(200), nullable=False)
#     causa_nombre = db.Column(db.String(100)) 
#     usuario_owner = db.Column(db.String(50)) 

# # --- CONFIG PDF ---
# path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
# config_pdf = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
# BASE_DATOS_PDFS = 'expedientes_clientes'
# OUTPUT_STATIC = 'static/pdf_generados'

# os.makedirs(BASE_DATOS_PDFS, exist_ok=True)
# os.makedirs(OUTPUT_STATIC, exist_ok=True)

# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if 'usuario' not in session: return redirect(url_for('login'))
#         return f(*args, **kwargs)
#     return decorated_function

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         u = Usuario.query.filter_by(username=request.form.get('username')).first()
#         if u and u.password == request.form.get('password'):
#             session['usuario'] = u.username
#             return redirect(url_for('dashboard'))
#         flash('Usuario o contraseña incorrectos')
#     return render_template('login.html')

# @app.route('/logout')
# def logout():
#     session.pop('usuario', None)
#     return redirect(url_for('login'))

# @app.route('/')
# @login_required
# def dashboard():
#     ruta_usuario = os.path.join(BASE_DATOS_PDFS, session['usuario'])
#     os.makedirs(ruta_usuario, exist_ok=True)
    
#     carpetas = [d for d in os.listdir(ruta_usuario) if os.path.isdir(os.path.join(ruta_usuario, d))]
#     expedientes_info = []
    
#     for c in carpetas:
#         info_db = CausaInfo.query.filter_by(nombre_carpeta=c).first()
#         if not info_db:
#             info_db = CausaInfo(nombre_carpeta=c)
#             db.session.add(info_db)
#             db.session.commit()
            
#         ruta_c = os.path.join(ruta_usuario, c)
#         archivos = [f for f in os.listdir(ruta_c) if f.endswith('.pdf') and f != 'caratula_generada.pdf']
        
#         expedientes_info.append({
#             'nombre': c,
#             'archivos': archivos,
#             'estado': info_db.estado,
#             'monto': info_db.monto,
#             'notas': info_db.notas
#         })
    
#     # Traemos los vencimientos del usuario ordenados por fecha
#     agenda = Vencimiento.query.filter_by(usuario_owner=session['usuario']).order_by(Vencimiento.fecha.asc()).all()
    
#     return render_template('dashboard.html', 
#                            expedientes=expedientes_info, 
#                            usuario=session['usuario'],
#                            agenda=agenda,
#                            hoy=date.today())

# @app.route('/agregar_vencimiento', methods=['POST'])
# @login_required
# def agregar_vencimiento():
#     try:
#         nueva_fecha = request.form.get('fecha')
#         nuevo_titulo = request.form.get('titulo')
#         causa = request.form.get('causa_nombre')
        
#         nuevo_vence = Vencimiento(
#             fecha=nueva_fecha, 
#             titulo=nuevo_titulo, 
#             causa_nombre=causa,
#             usuario_owner=session['usuario']
#         )
#         db.session.add(nuevo_vence)
#         db.session.commit()
#         flash("Vencimiento agendado")
#     except Exception as e:
#         flash(f"Error al agendar: {e}")
    
#     return redirect(url_for('dashboard'))

# @app.route('/actualizar_ficha/<nro_expediente>', methods=['POST'])
# @login_required
# def actualizar_ficha(nro_expediente):
#     info = CausaInfo.query.filter_by(nombre_carpeta=nro_expediente).first()
#     if info:
#         info.estado = request.form.get('estado')
#         info.monto = request.form.get('monto')
#         info.notas = request.form.get('notas')
#         db.session.commit()
#         flash(f'Ficha de {nro_expediente} actualizada')
#     return redirect(url_for('dashboard'))

# @app.route('/visor/<nro_expediente>')
# @login_required
# def abrir_visor(nro_expediente):
#     ruta_carpeta_expte = os.path.join(BASE_DATOS_PDFS, session['usuario'], nro_expediente)
#     ruta_json = os.path.join(ruta_carpeta_expte, 'datos_caratula.json')

#     if not os.path.exists(ruta_json):
#         datos_basicos = {
#             "nro_expediente": nro_expediente, "juzgado": "No asignado",
#             "secretaria": "-", "titulo_causa": nro_expediente, "materia": "-"
#         }
#         with open(ruta_json, 'w', encoding='utf-8') as f:
#             json.dump(datos_basicos, f)

#     try:
#         with open(ruta_json, 'r', encoding='utf-8') as f:
#             datos = json.load(f)

#         html_caratula = render_template('caratula_modelo.html', **datos)
#         ruta_caratula_pdf = os.path.join(ruta_carpeta_expte, 'caratula_generada.pdf')
#         pdfkit.from_string(html_caratula, ruta_caratula_pdf, configuration=config_pdf)

#         nombre_archivo_final = f"{session['usuario']}_{nro_expediente}.pdf".lower().replace(" ", "_")
#         ruta_destino = os.path.join(OUTPUT_STATIC, nombre_archivo_final)

#         archivos = sorted([f for f in os.listdir(ruta_carpeta_expte) if f.endswith('.pdf') and f != 'caratula_generada.pdf'],
#                           key=lambda x: os.path.getmtime(os.path.join(ruta_carpeta_expte, x)))

#         merger = PdfMerger()
#         merger.append(ruta_caratula_pdf)
#         for f in archivos:
#             merger.append(os.path.join(ruta_carpeta_expte, f))
        
#         merger.write(ruta_destino)
#         merger.close()

#         return render_template('index.html', archivo_pdf=nombre_archivo_final)

#     except Exception as e:
#         print(f"Error en Visor: {e}")
#         return f"Error al generar PDF: {e}", 500

# @app.route('/obtener_pdf/<nombre_pdf>')
# @login_required
# def obtener_pdf(nombre_pdf):
#     ruta = os.path.join(OUTPUT_STATIC, nombre_pdf)
#     if os.path.exists(ruta):
#         return send_file(ruta, mimetype='application/pdf')
#     return "Archivo no encontrado", 404

# @app.route('/guardar_caratula/<nro_expediente>', methods=['POST'])
# @login_required
# def guardar_caratula(nro_expediente):
#     datos = {
#         "nro_expediente": request.form.get('nro_expediente_form'),
#         "juzgado": request.form.get('juzgado'),
#         "secretaria": request.form.get('secretaria'),
#         "titulo_causa": request.form.get('titulo_causa'),
#         "materia": request.form.get('materia')
#     }
#     ruta_c = os.path.join(BASE_DATOS_PDFS, session['usuario'], nro_expediente)
#     with open(os.path.join(ruta_c, 'datos_caratula.json'), 'w', encoding='utf-8') as f:
#         json.dump(datos, f)
#     return redirect(url_for('abrir_visor', nro_expediente=nro_expediente))

# @app.route('/crear_causa', methods=['POST'])
# @login_required
# def crear_causa():
#     nom = "".join(x for x in request.form.get('nombre_causa') if (x.isalnum() or x in "._- "))
#     if nom:
#         os.makedirs(os.path.join(BASE_DATOS_PDFS, session['usuario'], nom), exist_ok=True)
#     return redirect(url_for('dashboard'))

# @app.route('/subir_archivo/<nro_expediente>', methods=['POST'])
# @login_required
# def subir_archivo(nro_expediente):
#     f = request.files.get('archivo_pdf')
#     if f and f.filename.endswith('.pdf'):
#         f.save(os.path.join(BASE_DATOS_PDFS, session['usuario'], nro_expediente, secure_filename(f.filename)))
#     return redirect(url_for('dashboard'))

# @app.route('/eliminar_archivo/<nro_expediente>/<nombre_archivo>')
# @login_required
# def eliminar_archivo(nro_expediente, nombre_archivo):
#     ruta = os.path.join(BASE_DATOS_PDFS, session['usuario'], nro_expediente, nombre_archivo)
#     if os.path.exists(ruta): os.remove(ruta)
#     return redirect(url_for('dashboard'))

# @app.route('/eliminar_causa/<nro_expediente>')
# @login_required
# def eliminar_causa(nro_expediente):
#     ruta = os.path.join(BASE_DATOS_PDFS, session['usuario'], nro_expediente)
#     if os.path.exists(ruta): shutil.rmtree(ruta)
#     return redirect(url_for('dashboard'))

# if __name__ == '__main__':
#     with app.app_context():
#         db.create_all()
#         if not Usuario.query.filter_by(username='nico').first():
#             db.session.add(Usuario(username='nico', password='123'))
#             db.session.commit()
#     app.run(debug=True)

import shutil
import pdfkit
import json
import os
from datetime import date, datetime
from flask import Flask, render_template, send_file, request, redirect, url_for, session, flash, send_from_directory
from functools import wraps
from PyPDF2 import PdfMerger
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'tu_llave_secreta_muy_segura'

# --- CONFIGURACIÓN DE BASE DE DATOS ---
database_url = os.environ.get('DATABASE_URL')

# Corrección para que Render y SQLAlchemy se entiendan con PostgreSQL
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///lexview.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# INICIALIZAR LA BASE DE DATOS (Esto arregla tus 9 errores)
db = SQLAlchemy(app)

# --- MODELOS ---
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)

class CausaInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_carpeta = db.Column(db.String(100), unique=True)
    estado = db.Column(db.String(100), default="En Trámite")
    monto = db.Column(db.String(50), default="0.00")
    notas = db.Column(db.Text, default="")

class Vencimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    titulo = db.Column(db.String(200), nullable=False)
    causa_nombre = db.Column(db.String(100)) 
    usuario_owner = db.Column(db.String(50)) 

# --- CONFIG PDF ---
if os.name == 'nt': 
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
else: 
    path_wkhtmltopdf = '/usr/bin/wkhtmltopdf'

# Intentamos configurar pdfkit, pero si falla en Render no bloquea toda la app
try:
    config_pdf = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
except:
    config_pdf = None

BASE_DATOS_PDFS = 'expedientes_clientes'
OUTPUT_STATIC = 'static/pdf_generados'

os.makedirs(BASE_DATOS_PDFS, exist_ok=True)
os.makedirs(OUTPUT_STATIC, exist_ok=True)

# --- RUTAS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = Usuario.query.filter_by(username=request.form.get('username')).first()
        if u and u.password == request.form.get('password'):
            session['usuario'] = u.username
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    ruta_usuario = os.path.join(BASE_DATOS_PDFS, session['usuario'])
    os.makedirs(ruta_usuario, exist_ok=True)
    carpetas = [d for d in os.listdir(ruta_usuario) if os.path.isdir(os.path.join(ruta_usuario, d))]
    expedientes_info = []
    for c in carpetas:
        info_db = CausaInfo.query.filter_by(nombre_carpeta=c).first()
        if not info_db:
            info_db = CausaInfo(nombre_carpeta=c)
            db.session.add(info_db); db.session.commit()
        ruta_c = os.path.join(ruta_usuario, c)
        archivos = [f for f in os.listdir(ruta_c) if f.endswith('.pdf') and f != 'caratula_generada.pdf']
        expedientes_info.append({'nombre': c, 'archivos': archivos, 'estado': info_db.estado, 'monto': info_db.monto, 'notas': info_db.notas})
    
    agenda = Vencimiento.query.filter_by(usuario_owner=session['usuario']).order_by(Vencimiento.fecha.asc()).all()
    return render_template('dashboard.html', expedientes=expedientes_info, usuario=session['usuario'], agenda=agenda, hoy=date.today())

@app.route('/agregar_vencimiento', methods=['POST'])
@login_required
def agregar_vencimiento():
    fecha_str = request.form.get('fecha')
    nueva_fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    nuevo_vence = Vencimiento(fecha=nueva_fecha, titulo=request.form.get('titulo'), causa_nombre=request.form.get('causa_nombre'), usuario_owner=session['usuario'])
    db.session.add(nuevo_vence); db.session.commit()
    flash("Vencimiento agendado")
    return redirect(url_for('dashboard'))

@app.route('/visor/<nro_expediente>')
@login_required
def abrir_visor(nro_expediente):
    ruta_carpeta_expte = os.path.join(BASE_DATOS_PDFS, session['usuario'], nro_expediente)
    ruta_json = os.path.join(ruta_carpeta_expte, 'datos_caratula.json')
    if not os.path.exists(ruta_json):
        datos = {"nro_expediente": nro_expediente, "juzgado": "No asignado", "secretaria": "-", "titulo_causa": nro_expediente, "materia": "-"}
        with open(ruta_json, 'w', encoding='utf-8') as f: json.dump(datos, f)
    
    with open(ruta_json, 'r', encoding='utf-8') as f: datos = json.load(f)
    html_caratula = render_template('caratula_modelo.html', **datos)
    ruta_caratula_pdf = os.path.join(ruta_carpeta_expte, 'caratula_generada.pdf')
    
    if config_pdf:
        pdfkit.from_string(html_caratula, ruta_caratula_pdf, configuration=config_pdf)

    nombre_archivo_final = f"{session['usuario']}_{nro_expediente}.pdf".lower().replace(" ", "_")
    ruta_destino = os.path.join(OUTPUT_STATIC, nombre_archivo_final)
    archivos = sorted([f for f in os.listdir(ruta_carpeta_expte) if f.endswith('.pdf') and f != 'caratula_generada.pdf'], key=lambda x: os.path.getmtime(os.path.join(ruta_carpeta_expte, x)))

    merger = PdfMerger()
    if os.path.exists(ruta_caratula_pdf):
        merger.append(ruta_caratula_pdf)
    for f in archivos: merger.append(os.path.join(ruta_carpeta_expte, f))
    merger.write(ruta_destino); merger.close()
    return render_template('index.html', archivo_pdf=nombre_archivo_final)

@app.route('/obtener_pdf/<path:nombre_pdf>')
@login_required
def obtener_pdf(nombre_pdf):
    return send_from_directory(OUTPUT_STATIC, nombre_pdf)

@app.route('/crear_causa', methods=['POST'])
@login_required
def crear_causa():
    nom = "".join(x for x in request.form.get('nombre_causa') if (x.isalnum() or x in "._- "))
    if nom: os.makedirs(os.path.join(BASE_DATOS_PDFS, session['usuario'], nom), exist_ok=True)
    return redirect(url_for('dashboard'))

@app.route('/subir_archivo/<nro_expediente>', methods=['POST'])
@login_required
def subir_archivo(nro_expediente):
    f = request.files.get('archivo_pdf')
    if f and f.filename.endswith('.pdf'):
        f.save(os.path.join(BASE_DATOS_PDFS, session['usuario'], nro_expediente, secure_filename(f.filename)))
    return redirect(url_for('dashboard'))

@app.route('/eliminar_archivo/<nro_expediente>/<nombre_archivo>')
@login_required
def eliminar_archivo(nro_expediente, nombre_archivo):
    ruta = os.path.join(BASE_DATOS_PDFS, session['usuario'], nro_expediente, nombre_archivo)
    if os.path.exists(ruta): os.remove(ruta)
    return redirect(url_for('dashboard'))

@app.route('/eliminar_causa/<nro_expediente>')
@login_required
def eliminar_causa(nro_expediente):
    ruta = os.path.join(BASE_DATOS_PDFS, session['usuario'], nro_expediente)
    if os.path.exists(ruta): shutil.rmtree(ruta)
    return redirect(url_for('dashboard'))

@app.route('/actualizar_ficha/<nro_expediente>', methods=['POST'])
@login_required
def actualizar_ficha(nro_expediente):
    info = CausaInfo.query.filter_by(nombre_carpeta=nro_expediente).first()
    if info:
        info.estado = request.form.get('estado'); info.monto = request.form.get('monto'); info.notas = request.form.get('notas')
        db.session.commit()
    return redirect(url_for('dashboard'))

# --- CREACIÓN DE TABLAS Y USUARIO INICIAL ---
with app.app_context():
    db.create_all()
    # Si la base de datos de Postgres está vacía, crea tu usuario automáticamente
    if not Usuario.query.filter_by(username='nico').first():
        nuevo_usuario = Usuario(username='nico', password='123')
        db.session.add(nuevo_usuario)
        db.session.commit()
        print("Usuario 'nico' creado exitosamente.")

if __name__ == '__main__':
    app.run(debug=True)