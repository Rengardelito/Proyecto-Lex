from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    matricula     = db.Column(db.String(20))

    forum_user    = db.Column(db.String(100))
    forum_pass    = db.Column(db.String(100))

    licencia_activa = db.Column(db.Boolean, default=False)
    licencia_vence  = db.Column(db.Date, nullable=True)
    plan            = db.Column(db.String(20), default='piloto')
    alcance         = db.Column(db.String(20), default='capital')
    hardware_id     = db.Column(db.String(64), nullable=True)

    causas       = db.relationship('CausaInfo', backref='owner', lazy=True)
    vencimientos = db.relationship('Vencimiento', backref='owner', lazy=True)
    notas        = db.relationship('NotaPersonal', backref='owner', lazy=True)

    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class CausaInfo(db.Model):
    __tablename__ = 'causa_info'

    id = db.Column(db.Integer, primary_key=True)

    # Texto visible/compatibilidad. Ej: 118897-15
    numero = db.Column(db.String(100), nullable=False)

    # Identidad real del expediente en Forum:
    # tipo/código + número base + año.
    # Ej: EXP | 118897 | 15
    tipo = db.Column(db.String(20), default="", index=True)
    numero_base = db.Column(db.String(50), nullable=True, index=True)
    anio = db.Column(db.String(10), nullable=True, index=True)
    localidad = db.Column(db.String(100), default="Capital")

    nombre_carpeta      = db.Column(db.String(100))
    demandado           = db.Column(db.String(200), default='SIN CARATULAR')
    juzgado             = db.Column(db.String(200))
    secretaria          = db.Column(db.String(200))
    estado              = db.Column(db.String(100), default="En Trámite")
    ultima_notificacion = db.Column(db.String(50))
    ultimo_estado       = db.Column(db.String(300))
    monto               = db.Column(db.String(50), default="0.00")
    notas               = db.Column(db.Text, default="")
    usuario_id          = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha_creacion      = db.Column(db.DateTime, default=datetime.utcnow)

    # True  -> entra en sincronización
    # False -> ya no se procesa salvo acción explícita
    necesita_sync = db.Column(db.Boolean, default=True)

    # pendiente | parcial | sincronizado | error
    estado_sync = db.Column(db.String(30), default="pendiente")

    # identifica la tanda/lote de importación o clasificación
    lote_importacion = db.Column(db.String(80), nullable=True, index=True)

    ultima_sync = db.Column(db.DateTime, nullable=True)
    error_sync = db.Column(db.Text, nullable=True)

    paginas_forum_total = db.Column(db.Integer, default=0)
    paginas_descargadas_total = db.Column(db.Integer, default=0)

    documentos = db.relationship(
        'Documento',
        backref='causa',
        lazy=True,
        cascade="all, delete-orphan"
    )


class Documento(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    causa_id       = db.Column(db.Integer, db.ForeignKey('causa_info.id'), nullable=False)
    nombre_archivo = db.Column(db.String(300), nullable=False)
    ruta_completa  = db.Column(db.String(500), nullable=False)
    fecha_descarga = db.Column(db.DateTime, default=datetime.utcnow)
    hash_archivo   = db.Column(db.String(64))


class Vencimiento(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    fecha        = db.Column(db.Date, nullable=False)
    titulo       = db.Column(db.String(200), nullable=False)
    causa_nombre = db.Column(db.String(100))
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuario.id'))


class NotaPersonal(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    fecha      = db.Column(db.Date, nullable=False)
    evento     = db.Column(db.String(200), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))