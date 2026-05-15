# python fix_toolbar.py

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# FIX 1: Boton rojo X (cerrar)
# Buscar el boton rojo y ponerle X
old_red = re.search(r'<button[^>]*red icon[^>]*onclick="window\.close\(\)"[^>]*>.*?</button>', content, re.DOTALL)
if old_red:
    content = content.replace(old_red.group(0), '<button class="tb-btn red icon" onclick="window.close()" title="Cerrar">&#10005;</button>')
    print("Fix boton X OK")
else:
    # intentar con href
    content = re.sub(
        r'<[ab][^>]*red icon[^>]*>.*?</[ab]>',
        '<button class="tb-btn red icon" onclick="window.close()" title="Cerrar">&#10005;</button>',
        content, count=1, flags=re.DOTALL
    )
    print("Fix boton X (alternativo) OK")

# FIX 2: Boton girar - restaurar icono
content = content.replace(
    'onclick="rotarContenido()" title="Rotar 90°">',
    'onclick="rotarContenido()" title="Rotar 90&#176;">&#8635;'
)
# Limpiar el contenido vacio del boton si quedó asi
content = re.sub(
    r'(onclick="rotarContenido\(\)"[^>]*>)\s*(</button>)',
    r'\1&#8635;\2',
    content
)
print("Fix girar OK")

# FIX 3: Foja centrado - mover el wrap al centro
# Sacar margin-left:auto y agregar posicion centrada
content = content.replace(
    '<div class="tb-foja-wrap" style="margin-left:auto;">',
    '<div class="tb-foja-wrap" style="position:absolute; left:50%; transform:translateX(-50%);">'
)
# Si no tenia margin-left:auto todavia
content = content.replace(
    '<div class="tb-foja-wrap">',
    '<div class="tb-foja-wrap" style="position:absolute; left:50%; transform:translateX(-50%);">'
)
print("Fix foja centrado OK")

# FIX 4: Asegurarse que el toolbar tiene position:relative para que funcione el absolute
content = content.replace(
    '#toolbar {\n            width: 100%;\n            background: #141414;\n            border-bottom: 1px solid #2a2a2a;\n            padding: 0 16px;\n            height: 54px;\n            display: flex;\n            align-items: center;\n            gap: 6px;\n            flex-shrink: 0;\n            z-index: 1000;\n        }',
    '#toolbar {\n            width: 100%;\n            background: #141414;\n            border-bottom: 1px solid #2a2a2a;\n            padding: 0 16px;\n            height: 54px;\n            display: flex;\n            align-items: center;\n            gap: 6px;\n            flex-shrink: 0;\n            z-index: 1000;\n            position: relative;\n        }'
)
print("Fix toolbar position OK")

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nListo. Reinicia el servidor.")
