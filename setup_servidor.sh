#!/bin/bash
# =============================================================
# setup_servidor.sh
# Instala y configura el servidor de licencias LexView en el VPS
# Ejecutar como root: bash setup_servidor.sh
# =============================================================

set -e
echo "🚀 Configurando servidor LexView en $(hostname)..."

# --- 1. Dependencias del sistema ---
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv nginx ufw

# --- 2. Crear usuario de aplicación (no root) ---
id -u lexview &>/dev/null || useradd -m -s /bin/bash lexview

# --- 3. Estructura de carpetas ---
mkdir -p /opt/lexview_server
chown lexview:lexview /opt/lexview_server

# --- 4. Copiar la app del servidor ---
cat > /opt/lexview_server/server.py << 'PYEOF'
"""
Servidor de licencias LexView
Endpoint: POST /api/verify  →  {"username": "...", "token": "..."}
"""
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import date
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////opt/lexview_server/licencias.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Licencia(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), unique=True, nullable=False)
    token      = db.Column(db.String(64), nullable=False)
    activa     = db.Column(db.Boolean, default=True)
    vence      = db.Column(db.Date,    nullable=True)   # None = sin vencimiento
    plan       = db.Column(db.String(20), default='piloto')

@app.route('/api/verify', methods=['POST'])
def verify():
    data     = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    token    = data.get('token', '').strip()

    if not username or not token:
        return jsonify({"valid": False, "reason": "datos_incompletos"}), 400

    lic = Licencia.query.filter_by(username=username, token=token).first()

    if not lic:
        return jsonify({"valid": False, "reason": "no_encontrado"})
    if not lic.activa:
        return jsonify({"valid": False, "reason": "inactiva"})
    if lic.vence and lic.vence < date.today():
        return jsonify({"valid": False, "reason": "vencida", "vencio": str(lic.vence)})

    return jsonify({"valid": True, "plan": lic.plan})

@app.route('/api/nueva_licencia', methods=['POST'])
def nueva_licencia():
    """Solo accesible desde localhost (para admin)"""
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({"error": "no autorizado"}), 403

    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    token    = data.get('token', '').strip()
    plan     = data.get('plan', 'piloto')
    vence    = data.get('vence')  # "2026-12-31" o null

    if not username or not token:
        return jsonify({"error": "faltan datos"}), 400

    if Licencia.query.filter_by(username=username).first():
        return jsonify({"error": "ya existe"}), 409

    lic = Licencia(
        username = username,
        token    = token,
        plan     = plan,
        vence    = date.fromisoformat(vence) if vence else None
    )
    db.session.add(lic)
    db.session.commit()
    return jsonify({"ok": True, "username": username})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='127.0.0.1', port=8000)
PYEOF

chown lexview:lexview /opt/lexview_server/server.py

# --- 5. Virtualenv e instalación de dependencias ---
python3 -m venv /opt/lexview_server/venv
/opt/lexview_server/venv/bin/pip install -q flask flask-sqlalchemy gunicorn

# --- 6. Servicio systemd ---
cat > /etc/systemd/system/lexview.service << 'SVCEOF'
[Unit]
Description=LexView License Server
After=network.target

[Service]
User=lexview
WorkingDirectory=/opt/lexview_server
ExecStart=/opt/lexview_server/venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 server:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable lexview
systemctl start lexview

# --- 7. Nginx como proxy reverso ---
cat > /etc/nginx/sites-available/lexview << 'NGXEOF'
server {
    listen 80;
    server_name _;   # cambiá por tu dominio cuando lo tengas

    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
    }

    # Bloquear todo lo demás
    location / {
        return 404;
    }
}
NGXEOF

ln -sf /etc/nginx/sites-available/lexview /etc/nginx/sites-enabled/lexview
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# --- 8. Firewall ---
ufw allow ssh
ufw allow 80/tcp
ufw --force enable

# --- 9. Inicializar DB ---
/opt/lexview_server/venv/bin/python -c "
from server import app, db
with app.app_context():
    db.create_all()
print('DB inicializada.')
"

echo ""
echo "✅ Servidor listo en http://146.190.215.54/api/verify"
echo ""
echo "Para agregar una licencia del piloto:"
echo "  curl -s -X POST http://localhost:8000/api/nueva_licencia \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"username\": \"abogado1\", \"token\": \"TOKEN_SECRETO\", \"plan\": \"piloto\"}'"