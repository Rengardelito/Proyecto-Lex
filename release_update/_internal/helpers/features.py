# helpers/features.py
"""
Control de funcionalidades por plan en LexView Pro.

Planes:
  trial   → todo limitado (max 5 exptes, 7 días)
  basic   → migración, clasificación, sincronización, actualización
  pro     → basic + auditoría + cédulas/mandamientos
  premium → pro + funciones a medida
  dev     → todo sin límites
"""

from datetime import date
from functools import wraps
from flask import jsonify
from flask_login import current_user


# ── Mapa de features por plan ─────────────────────────────────────────────────

FEATURES = {
    'clasificar':    ['trial', 'basic', 'pro', 'premium', 'dev'],
    'sincronizar':   ['trial', 'basic', 'pro', 'premium', 'dev'],
    'actualizar':    ['trial', 'basic', 'pro', 'premium', 'dev'],
    'migrar':        ['trial', 'basic', 'pro', 'premium', 'dev'],
    'auditoria':     ['pro', 'premium', 'dev'],
    'cedulas':       ['pro', 'premium', 'dev'],
    'resumen_pdf':   ['pro', 'premium', 'dev'],
}

# Límite de expedientes por actualización en modo trial
TRIAL_MAX_EXPTES = 5


# ── Funciones helper ──────────────────────────────────────────────────────────

def get_plan(usuario) -> str:
    """Devuelve el plan del usuario, normalizando valores legacy."""
    plan = getattr(usuario, 'plan', None) or 'basic'
    # Normalizar valor legacy 'piloto' → 'basic'
    if plan == 'piloto':
        return 'basic'
    return plan


def plan_activo(usuario) -> bool:
    """Verifica que la licencia no esté vencida."""
    vence = getattr(usuario, 'licencia_vence', None)
    if vence is None:
        return True  # sin vencimiento → activo
    return vence >= date.today()


def tiene_feature(usuario, feature: str) -> bool:
    """
    Devuelve True si el usuario tiene acceso a la feature.
    También verifica que la licencia no esté vencida.
    """
    if not plan_activo(usuario):
        return False
    plan = get_plan(usuario)
    planes_permitidos = FEATURES.get(feature, [])
    return plan in planes_permitidos


def es_trial(usuario) -> bool:
    return get_plan(usuario) == 'trial'


def max_exptes_trial(usuario) -> int | None:
    """Devuelve el límite de expedientes para trial, o None si no aplica."""
    if es_trial(usuario):
        return TRIAL_MAX_EXPTES
    return None


# ── Decorador para rutas ──────────────────────────────────────────────────────

def requiere_feature(feature: str):
    """
    Decorador para rutas Flask.
    Devuelve 403 si el usuario no tiene acceso a la feature.

    Uso:
        @app.route('/run_auditoria', methods=['POST'])
        @login_required
        @requiere_feature('auditoria')
        def run_auditoria():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not tiene_feature(current_user, feature):
                plan = get_plan(current_user)
                return jsonify({
                    'error': 'plan_insuficiente',
                    'mensaje': f'Tu plan "{plan}" no incluye esta funcionalidad.',
                    'feature': feature
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator