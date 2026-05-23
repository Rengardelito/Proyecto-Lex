import os
import uuid as _uuid
from flask import Flask, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime as dt
from werkzeug.utils import secure_filename
import shutil

CURRENT_VERSION = "1.0.0"
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////opt/lexview_server/licencias.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.secret_key = 'lexview_admin_2026'

class Licencia(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    mac         = db.Column(db.String(17), unique=False, nullable=True)
    hardware_id = db.Column(db.String(64), unique=False, nullable=True)
    nombre      = db.Column(db.String(100))
    activa      = db.Column(db.Boolean, default=True)
    vence       = db.Column(db.Date, nullable=True)
    plan        = db.Column(db.String(20), default='piloto')

DOCUMENTAL_PATH = '/opt/lexview_server/documental'
os.makedirs(DOCUMENTAL_PATH, exist_ok=True)

ADMIN_PASSWORD = "lexview_admin_2026"

# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/verify', methods=['POST'])
def verify():
    data        = request.get_json(silent=True) or {}
    mac         = data.get('mac', '').strip().upper() or None
    hardware_id = data.get('hardware_id', '').strip() or None
    lic = None
    if hardware_id:
        lic = Licencia.query.filter_by(hardware_id=hardware_id).first()
    if not lic and mac:
        lic = Licencia.query.filter_by(mac=mac).first()
    if not lic:
        return jsonify({"valid": False, "reason": "no_autorizado"})
    if not lic.activa:
        return jsonify({"valid": False, "reason": "inactiva"})
    if lic.vence and lic.vence < date.today():
        return jsonify({"valid": False, "reason": "vencida"})
    return jsonify({"valid": True, "plan": lic.plan, "vence": str(lic.vence) if lic.vence else None})

@app.route('/api/nueva_licencia', methods=['POST'])
def nueva_licencia():
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({"error": "no autorizado"}), 403
    data        = request.get_json(silent=True) or {}
    mac         = data.get('mac', '').strip().upper() or None
    hardware_id = data.get('hardware_id', '').strip() or None
    nombre      = data.get('nombre', '').strip()
    plan        = data.get('plan', 'piloto')
    vence       = data.get('vence')
    if not hardware_id and not mac:
        return jsonify({"error": "falta hardware_id o mac"}), 400
    if hardware_id and Licencia.query.filter_by(hardware_id=hardware_id).first():
        return jsonify({"error": "dispositivo ya registrado"}), 409
    if mac and Licencia.query.filter_by(mac=mac).first():
        return jsonify({"error": "mac ya registrada"}), 409
    lic = Licencia(mac=mac, hardware_id=hardware_id, nombre=nombre, plan=plan,
                   vence=date.fromisoformat(vence) if vence else None)
    db.session.add(lic)
    db.session.commit()
    return jsonify({"ok": True, "hardware_id": hardware_id, "mac": mac, "nombre": nombre})

@app.route('/api/listar', methods=['GET'])
def listar():
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({"error": "no autorizado"}), 403
    lics = Licencia.query.all()
    return jsonify([{"mac": l.mac, "hardware_id": l.hardware_id, "nombre": l.nombre,
                     "activa": l.activa, "plan": l.plan,
                     "vence": str(l.vence) if l.vence else None} for l in lics])

@app.route("/api/version", methods=["GET"])
def get_version():
    hw_id = request.args.get("hw_id", "").strip()
    if not hw_id:
        return jsonify({"error": "hw_id requerido"}), 400
    lic = Licencia.query.filter_by(hardware_id=hw_id, activa=True).first()
    if not lic:
        return jsonify({"error": "Licencia invalida"}), 403
    if lic.vence and lic.vence < date.today():
        return jsonify({"error": "Licencia vencida"}), 403
    github_release_url = (
        f"https://github.com/Rengardelito/Proyecto-Lex/releases/download/"
        f"v{CURRENT_VERSION}/lexview-update-{CURRENT_VERSION}.zip"
    )
    changelog_path = f"/opt/lexview_server/changelogs/{CURRENT_VERSION}.txt"
    changelog = ""
    if os.path.exists(changelog_path):
        with open(changelog_path, "r", encoding="utf-8") as f:
            changelog = f.read()
    return jsonify({
        "version": CURRENT_VERSION,
        "download_url": github_release_url,
        "changelog": changelog,
        "min_version": "0.9.0",
    })

# ── DOCUMENTAL ────────────────────────────────────────────────────────────────

def _generar_index_html(carpeta, guardados):
    items = ""
    for nombre in guardados:
        display = nombre.replace('_', ' ').replace('.pdf', '')
        try:
            kb = os.path.getsize(os.path.join(carpeta, nombre)) // 1024
            size = f"{kb} KB" if kb < 1024 else f"{kb//1024} MB"
        except Exception:
            size = ""
        items += f'<a class="fi" href="{nombre}" download="{nombre}"><div class="ic">&#x1F4C4;</div><div class="fo"><div class="fn">{display}</div><div class="fs">{size}</div></div><span class="db">&#x2B07; Descargar</span></a>'
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>LexView Pro - Documental</title><style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f4f8;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:40px 16px}}.card{{background:white;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.10);width:100%;max-width:520px;overflow:hidden}}.hdr{{background:#1a3a7a;color:white;padding:24px 28px 20px}}.hdr h1{{font-size:1.1rem;font-weight:700;margin-bottom:4px}}.hdr p{{font-size:.82rem;opacity:.75}}.badge{{display:inline-block;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);border-radius:20px;padding:3px 12px;font-size:.7rem;font-weight:700;letter-spacing:1px;margin-top:10px}}.bdy{{padding:24px 28px}}.lbl{{font-size:.68rem;font-weight:700;color:#1a3a7a;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}}.fi{{display:flex;align-items:center;gap:12px;background:#f8faff;border:1px solid #e0e8f0;border-radius:8px;padding:12px 14px;margin-bottom:10px;text-decoration:none;color:inherit;transition:border-color .15s,background .15s}}.fi:hover{{border-color:#1a3a7a;background:#eef3ff}}.ic{{font-size:1.6rem;flex-shrink:0}}.fo{{flex:1}}.fn{{font-size:.82rem;font-weight:600;color:#1a2a4a;word-break:break-word}}.fs{{font-size:.68rem;color:#888;margin-top:2px}}.db{{background:#1a3a7a;color:white;border:none;border-radius:6px;padding:6px 14px;font-size:.72rem;font-weight:700;white-space:nowrap;text-decoration:none}}.av{{background:#fff8e1;border:1px solid #ffe082;border-radius:8px;padding:10px 14px;font-size:.75rem;color:#7a6000;margin-bottom:16px;line-height:1.5}}.ftr{{text-align:center;padding:16px 28px;border-top:1px solid #f0f0f0;font-size:.68rem;color:#aaa}}</style></head><body><div class="card"><div class="hdr"><h1>&#x2696; LexView Pro</h1><p>Copias para Traslado &mdash; Documentaci&oacute;n Judicial</p><span class="badge">ACCESO P&Uacute;BLICO</span></div><div class="bdy"><div class="av">&#x1F4CB; Los siguientes documentos forman parte de una notificaci&oacute;n judicial. Pod&eacute;s descargarlos haciendo click en cada uno.</div><div class="lbl">Archivos disponibles</div>{items}</div><div class="ftr">Generado por LexView Pro &middot; Poder Judicial de Corrientes</div></div></body></html>"""
    with open(os.path.join(carpeta, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)

@app.route('/api/documental/subir', methods=['POST'])
def subir_documental():
    hw_id = request.headers.get('X-Hardware-ID', '').strip()
    if not hw_id:
        return jsonify({'error': 'Sin identificacion'}), 401
    lic = Licencia.query.filter_by(hardware_id=hw_id, activa=True).first()
    if not lic:
        mac = request.headers.get('X-MAC', '').strip().upper()
        if mac:
            lic = Licencia.query.filter_by(mac=mac, activa=True).first()
    if not lic:
        return jsonify({'error': 'Dispositivo no autorizado'}), 403

    archivos = request.files.getlist('pdfs')
    if not archivos:
        return jsonify({'error': 'No se enviaron archivos'}), 400

    token = request.form.get('token', '').strip()
    if not token or len(token) < 8:
        token = _uuid.uuid4().hex[:16]

    carpeta = os.path.join(DOCUMENTAL_PATH, token)
    os.makedirs(carpeta, exist_ok=True)

    # Guardar metadata del hw_id para saber quién subió
    meta_path = os.path.join(carpeta, '.meta')
    if not os.path.exists(meta_path):
        with open(meta_path, 'w') as f:
            f.write(f"{hw_id}\n{lic.nombre}\n{dt.now().isoformat()}")

    guardados = []
    for archivo in archivos:
        if not archivo.filename.lower().endswith('.pdf'):
            continue
        nombre_seguro = secure_filename(archivo.filename)
        archivo.save(os.path.join(carpeta, nombre_seguro))
        guardados.append(nombre_seguro)

    if not guardados:
        return jsonify({'error': 'No se guardaron archivos'}), 500

    _generar_index_html(carpeta, guardados)
    return jsonify({'ok': True, 'token': token, 'url': f"https://lexviewpro.com.ar/documental/{token}/", 'archivos': guardados})

@app.route('/documental/<token>/<nombre_archivo>')
def descargar_documental(token, nombre_archivo):
    from flask import send_from_directory
    carpeta = os.path.join(DOCUMENTAL_PATH, token)
    return send_from_directory(carpeta, nombre_archivo, as_attachment=True)

@app.route('/documental/<token>/')
@app.route('/documental/<token>')
def ver_documental(token):
    carpeta = os.path.join(DOCUMENTAL_PATH, token)
    ruta_index = os.path.join(carpeta, 'index.html')
    if not os.path.exists(ruta_index):
        return "No encontrado", 404
    with open(ruta_index, 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/api/documental/eliminar/<token>', methods=['DELETE'])
def eliminar_documental(token):
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({'error': 'No autorizado'}), 403
    carpeta = os.path.join(DOCUMENTAL_PATH, token)
    if os.path.exists(carpeta):
        shutil.rmtree(carpeta)
        return jsonify({'ok': True, 'eliminado': token})
    return jsonify({'error': 'Token no encontrado'}), 404

# ── ADMIN ─────────────────────────────────────────────────────────────────────

@app.route('/admin')
def admin_login_page():
    return '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>LexView Admin</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0e1a;font-family:'Segoe UI',sans-serif;display:flex;justify-content:center;align-items:center;height:100vh}
.card{background:#111827;border:1px solid #1e2d45;border-radius:12px;padding:40px;width:360px;text-align:center}
.logo{font-size:1.4rem;font-weight:800;color:#3b82f6;letter-spacing:2px;margin-bottom:6px}
.sub{font-size:0.75rem;color:#4b5563;margin-bottom:30px}
input{width:100%;background:#1e2d45;border:1px solid #2d3f5a;color:#e2e8f0;border-radius:8px;padding:12px 16px;font-size:0.9rem;outline:none;margin-bottom:14px}
input:focus{border-color:#3b82f6}
button{width:100%;background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:12px;font-size:0.9rem;font-weight:700;cursor:pointer}
button:hover{background:#2563eb}
</style>
</head>
<body>
<div class="card">
  <div class="logo">LEXVIEW PRO</div>
  <div class="sub">Panel de Administracion</div>
  <form method="POST" action="/admin/login">
    <input type="password" name="password" placeholder="Contrasena de acceso" autofocus>
    <button type="submit">Ingresar</button>
  </form>
</div>
</body>
</html>'''

@app.route('/admin/login', methods=['POST'])
def admin_login():
    pwd = request.form.get('password', '')
    if pwd == ADMIN_PASSWORD:
        session['admin'] = True
        return redirect('/admin/panel')
    return redirect('/admin')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin')

def _nav(activa):
    links = [('Licencias', '/admin/panel'), ('Documental', '/admin/documental')]
    items = ''
    for label, href in links:
        color = '#3b82f6' if activa == label else '#9ca3af'
        weight = '700' if activa == label else '400'
        items += f'<a href="{href}" style="color:{color};font-weight:{weight};text-decoration:none;font-size:0.82rem">{label}</a>'
    return f'''<nav style="background:#111827;border-bottom:1px solid #1e2d45;padding:0 32px;height:56px;display:flex;align-items:center;justify-content:space-between">
  <div><div style="font-size:1rem;font-weight:800;color:#3b82f6;letter-spacing:2px">LEXVIEW PRO</div><div style="font-size:0.72rem;color:#4b5563">Panel de Administracion</div></div>
  <div style="display:flex;gap:24px;align-items:center">{items}<a href="/admin/logout" style="color:#ef4444;text-decoration:none;font-size:0.8rem">Cerrar sesion</a></div>
</nav>'''

@app.route('/admin/panel')
def admin_panel():
    if not session.get('admin'):
        return redirect('/admin')

    lics = Licencia.query.order_by(Licencia.id.desc()).all()
    hoy  = date.today()

    total   = len(lics)
    activas = sum(1 for l in lics if l.activa and (not l.vence or l.vence >= hoy))
    vencidas = sum(1 for l in lics if l.vence and l.vence < hoy)
    por_plan = {}
    for l in lics:
        por_plan[l.plan] = por_plan.get(l.plan, 0) + 1

    colores_plan = {
        'trial': '#f59e0b', 'basic': '#6b7280', 'pro': '#3b82f6',
        'premium': '#8b5cf6', 'dev': '#10b981', 'piloto': '#6b7280'
    }

    filas = ''
    for l in lics:
        vencido     = l.vence and l.vence < hoy
        activo_real = l.activa and not vencido
        estado_badge = (
            '<span style="background:#10b981;color:#000;padding:2px 10px;border-radius:20px;font-size:0.68rem;font-weight:700;">ACTIVA</span>'
            if activo_real else
            f'<span style="background:#ef4444;color:#fff;padding:2px 10px;border-radius:20px;font-size:0.68rem;font-weight:700;">{"VENCIDA" if vencido else "INACTIVA"}</span>'
        )
        plan_color = colores_plan.get(l.plan or 'basic', '#6b7280')
        plan_badge = f'<span style="background:{plan_color};color:{"#000" if l.plan in ["trial","dev"] else "#fff"};padding:2px 10px;border-radius:20px;font-size:0.68rem;font-weight:700;">{(l.plan or "basic").upper()}</span>'
        hw_short   = ((l.hardware_id or l.mac or '')[:16] + '...') if (l.hardware_id or l.mac) else '—'
        vence_str  = str(l.vence) if l.vence else '—'
        filas += f'''<tr>
            <td style="padding:12px 16px;color:#e2e8f0;font-weight:600">{l.nombre or "—"}</td>
            <td style="padding:12px 16px">{plan_badge}</td>
            <td style="padding:12px 16px">{estado_badge}</td>
            <td style="padding:12px 16px;color:#9ca3af;font-family:monospace;font-size:0.75rem">{hw_short}</td>
            <td style="padding:12px 16px;color:#9ca3af;font-size:0.8rem">{vence_str}</td>
            <td style="padding:12px 16px">
                <form method="POST" action="/admin/cambiar_plan" style="display:inline">
                    <input type="hidden" name="id" value="{l.id}">
                    <select name="plan" onchange="this.form.submit()" style="background:#1e2d45;border:1px solid #2d3f5a;color:#e2e8f0;border-radius:6px;padding:4px 8px;font-size:0.75rem;cursor:pointer">
                        {"".join(f'<option value="{p}" {"selected" if l.plan==p else ""}>{p.upper()}</option>' for p in ["trial","basic","pro","premium","dev"])}
                    </select>
                </form>
                <form method="POST" action="/admin/toggle_activa" style="display:inline;margin-left:6px">
                    <input type="hidden" name="id" value="{l.id}">
                    <button type="submit" style="background:{"#ef4444" if activo_real else "#10b981"};color:#fff;border:none;border-radius:6px;padding:4px 10px;font-size:0.72rem;cursor:pointer">{"Desactivar" if activo_real else "Activar"}</button>
                </form>
            </td>
        </tr>'''

    stats_html = ''.join(
        f'<div style="background:#1e2d45;border-radius:8px;padding:16px 24px;text-align:center"><div style="font-size:1.8rem;font-weight:800;color:{colores_plan.get(p,"#6b7280")}">{c}</div><div style="font-size:0.72rem;color:#9ca3af;margin-top:4px">{p.upper()}</div></div>'
        for p, c in por_plan.items()
    )

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LexView Admin Panel</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0e1a;font-family:'Segoe UI',sans-serif;color:#e2e8f0;min-height:100vh}}
.container{{max-width:1200px;margin:0 auto;padding:32px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:16px;margin-bottom:32px}}
.stat-card{{background:#111827;border:1px solid #1e2d45;border-radius:10px;padding:20px;text-align:center}}
.stat-num{{font-size:2rem;font-weight:800;color:#3b82f6}}
.stat-num.green{{color:#10b981}} .stat-num.red{{color:#ef4444}}
.stat-label{{font-size:0.72rem;color:#6b7280;margin-top:4px}}
.section-title{{font-size:0.75rem;font-weight:700;color:#6b7280;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px}}
.card{{background:#111827;border:1px solid #1e2d45;border-radius:10px;overflow:hidden;margin-bottom:32px}}
table{{width:100%;border-collapse:collapse}}
th{{background:#0f172a;padding:10px 16px;text-align:left;font-size:0.68rem;color:#6b7280;letter-spacing:1px;text-transform:uppercase}}
tr{{border-bottom:1px solid #1e2d45}} tr:hover td{{background:#1a2435}}
.form-card{{background:#111827;border:1px solid #1e2d45;border-radius:10px;padding:24px;margin-bottom:32px}}
.form-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
label{{font-size:0.72rem;color:#9ca3af;display:block;margin-bottom:6px}}
input[type=text],input[type=date],select.form-select{{width:100%;background:#1e2d45;border:1px solid #2d3f5a;color:#e2e8f0;border-radius:8px;padding:10px 14px;font-size:0.85rem;outline:none}}
.btn-primary{{background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:12px 24px;font-size:0.85rem;font-weight:700;cursor:pointer;margin-top:8px}}
</style>
</head>
<body>
{_nav("Licencias")}
<div class="container">
  <div class="stats">
    <div class="stat-card"><div class="stat-num">{total}</div><div class="stat-label">TOTAL</div></div>
    <div class="stat-card"><div class="stat-num green">{activas}</div><div class="stat-label">ACTIVAS</div></div>
    <div class="stat-card"><div class="stat-num red">{vencidas}</div><div class="stat-label">VENCIDAS</div></div>
    {stats_html}
  </div>
  <div class="section-title">Agregar nueva licencia</div>
  <div class="form-card">
    <form method="POST" action="/admin/nueva">
      <div class="form-grid">
        <div><label>Nombre del abogado</label><input type="text" name="nombre" placeholder="Dr. Juan Perez" required></div>
        <div><label>Hardware ID (del dispositivo)</label><input type="text" name="hardware_id" placeholder="abc123..." required></div>
        <div><label>Plan</label>
          <select name="plan" class="form-select">
            <option value="trial">TRIAL</option><option value="basic" selected>BASIC</option>
            <option value="pro">PRO</option><option value="premium">PREMIUM</option><option value="dev">DEV</option>
          </select>
        </div>
        <div><label>Vencimiento (opcional)</label><input type="date" name="vence"></div>
      </div>
      <button type="submit" class="btn-primary">+ Registrar licencia</button>
    </form>
  </div>
  <div class="section-title">Licencias registradas</div>
  <div class="card">
    <table>
      <thead><tr><th>Nombre</th><th>Plan</th><th>Estado</th><th>Hardware ID</th><th>Vencimiento</th><th>Acciones</th></tr></thead>
      <tbody>{filas}</tbody>
    </table>
  </div>
</div>
</body>
</html>'''

@app.route('/admin/nueva', methods=['POST'])
def admin_nueva():
    if not session.get('admin'):
        return redirect('/admin')
    nombre      = request.form.get('nombre', '').strip()
    hardware_id = request.form.get('hardware_id', '').strip()
    plan        = request.form.get('plan', 'basic')
    vence_str   = request.form.get('vence', '').strip()
    if nombre and hardware_id:
        lic = Licencia(nombre=nombre, hardware_id=hardware_id, plan=plan, activa=True,
                       vence=date.fromisoformat(vence_str) if vence_str else None)
        db.session.add(lic)
        db.session.commit()
    return redirect('/admin/panel')

@app.route('/admin/cambiar_plan', methods=['POST'])
def admin_cambiar_plan():
    if not session.get('admin'):
        return redirect('/admin')
    lic = db.session.get(Licencia, int(request.form.get('id')))
    if lic:
        lic.plan = request.form.get('plan')
        db.session.commit()
    return redirect('/admin/panel')

@app.route('/admin/toggle_activa', methods=['POST'])
def admin_toggle_activa():
    if not session.get('admin'):
        return redirect('/admin')
    lic = db.session.get(Licencia, int(request.form.get('id')))
    if lic:
        lic.activa = not lic.activa
        db.session.commit()
    return redirect('/admin/panel')

# ── ADMIN DOCUMENTAL ──────────────────────────────────────────────────────────

@app.route('/admin/documental')
def admin_documental():
    if not session.get('admin'):
        return redirect('/admin')

    lics = Licencia.query.all()

    tokens_info = []
    if os.path.exists(DOCUMENTAL_PATH):
        for token in sorted(os.listdir(DOCUMENTAL_PATH)):
            carpeta = os.path.join(DOCUMENTAL_PATH, token)
            if not os.path.isdir(carpeta):
                continue

            archivos = [f for f in os.listdir(carpeta) if f.endswith('.pdf')]

            # Leer metadata si existe
            nombre_licencia = '—'
            fecha = '—'
            meta_path = os.path.join(carpeta, '.meta')
            if os.path.exists(meta_path):
                try:
                    lines = open(meta_path).read().strip().splitlines()
                    hw_meta   = lines[0] if len(lines) > 0 else ''
                    nombre_licencia = lines[1] if len(lines) > 1 else hw_meta[:12]
                    fecha_iso = lines[2] if len(lines) > 2 else ''
                    if fecha_iso:
                        fecha = dt.fromisoformat(fecha_iso).strftime('%d/%m/%Y %H:%M')
                except Exception:
                    pass
            else:
                # Fallback: fecha de modificación de carpeta
                try:
                    ts    = os.path.getmtime(carpeta)
                    fecha = dt.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M')
                except Exception:
                    pass

            total_bytes = sum(
                os.path.getsize(os.path.join(carpeta, f))
                for f in archivos
                if os.path.exists(os.path.join(carpeta, f))
            )
            size_str = f"{total_bytes // 1024} KB" if total_bytes < 1024*1024 else f"{total_bytes / (1024*1024):.1f} MB"

            tokens_info.append({
                'token':    token,
                'licencia': nombre_licencia,
                'archivos': archivos,
                'cantidad': len(archivos),
                'fecha':    fecha,
                'size':     size_str,
                'url':      f"https://lexviewpro.com.ar/documental/{token}/",
            })

    tokens_info.reverse()

    total_tokens   = len(tokens_info)
    total_archivos = sum(t['cantidad'] for t in tokens_info)

    filas = ''
    for t in tokens_info:
        archivos_html = ''.join(
            f'<div style="font-size:0.7rem;color:#9ca3af;padding:1px 0;">📄 {a}</div>'
            for a in t['archivos']
        ) or '<div style="font-size:0.7rem;color:#4b5563;">sin archivos</div>'

        filas += f'''<tr>
            <td style="padding:12px 16px;color:#60a5fa;font-weight:700;font-size:0.82rem">{t["licencia"]}</td>
            <td style="padding:12px 16px;color:#9ca3af;font-size:0.78rem">{t["fecha"]}</td>
            <td style="padding:12px 16px;text-align:center">
                <span style="background:#1e3a5f;color:#60a5fa;border-radius:20px;padding:3px 12px;font-size:0.75rem;font-weight:700">{t["cantidad"]}</span>
            </td>
            <td style="padding:12px 16px;color:#9ca3af;font-size:0.78rem">{t["size"]}</td>
            <td style="padding:12px 16px">{archivos_html}</td>
            <td style="padding:12px 16px;white-space:nowrap">
                <a href="{t["url"]}" target="_blank"
                   style="background:#1e3a5f;color:#60a5fa;border-radius:6px;padding:5px 12px;font-size:0.72rem;text-decoration:none;margin-right:6px;display:inline-block">
                   🔗 Ver
                </a>
                <form method="POST" action="/admin/documental/eliminar/{t["token"]}" style="display:inline"
                      onsubmit="return confirm('Eliminar este token y sus archivos?')">
                    <button type="submit"
                        style="background:#7f1d1d;color:#fca5a5;border:none;border-radius:6px;padding:5px 12px;font-size:0.72rem;cursor:pointer">
                        🗑 Eliminar
                    </button>
                </form>
            </td>
        </tr>'''

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LexView Admin — Documental</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0e1a;font-family:'Segoe UI',sans-serif;color:#e2e8f0;min-height:100vh}}
.container{{max-width:1300px;margin:0 auto;padding:32px}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:32px}}
.stat-card{{background:#111827;border:1px solid #1e2d45;border-radius:10px;padding:20px;text-align:center}}
.stat-num{{font-size:2rem;font-weight:800;color:#3b82f6}}
.stat-label{{font-size:0.72rem;color:#6b7280;margin-top:4px}}
.section-title{{font-size:0.75rem;font-weight:700;color:#6b7280;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px}}
.card{{background:#111827;border:1px solid #1e2d45;border-radius:10px;overflow:hidden}}
table{{width:100%;border-collapse:collapse}}
th{{background:#0f172a;padding:10px 16px;text-align:left;font-size:0.68rem;color:#6b7280;letter-spacing:1px;text-transform:uppercase}}
tr{{border-bottom:1px solid #1e2d45}} tr:hover td{{background:#1a2435}}
</style>
</head>
<body>
{_nav("Documental")}
<div class="container">
  <div class="stats">
    <div class="stat-card"><div class="stat-num">{total_tokens}</div><div class="stat-label">CEDULAS GENERADAS</div></div>
    <div class="stat-card"><div class="stat-num" style="color:#10b981">{total_archivos}</div><div class="stat-label">ARCHIVOS TOTALES</div></div>
    <div class="stat-card"><div class="stat-num" style="color:#8b5cf6">{len(lics)}</div><div class="stat-label">LICENCIAS</div></div>
  </div>
  <div class="section-title">Documentales subidos</div>
  <div class="card">
    <table>
      <thead><tr>
        <th>Abogado</th><th>Fecha</th><th>Archivos</th><th>Tamaño</th><th>Contenido</th><th>Acciones</th>
      </tr></thead>
      <tbody>{filas if filas else '<tr><td colspan="6" style="text-align:center;padding:40px;color:#4b5563;">No hay documentales subidos</td></tr>'}</tbody>
    </table>
  </div>
</div>
</body>
</html>'''

@app.route('/admin/documental/eliminar/<token>', methods=['POST'])
def admin_eliminar_documental(token):
    if not session.get('admin'):
        return redirect('/admin')
    carpeta = os.path.join(DOCUMENTAL_PATH, token)
    if os.path.exists(carpeta):
        shutil.rmtree(carpeta)
    return redirect('/admin/documental')

# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='127.0.0.1', port=8000)
