# Ejecutar desde la carpeta raiz del proyecto:
# python fix_visor_visual.py

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# FIX 1: Limpiar ?? corrompidos
content = re.sub(r'\?\?\s*', '', content)
print("Fix 1 (emojis ??) OK")

# FIX 2: Contador de paginas blanco
content = content.replace(
    '#page-counter { font-size: 0.72rem; color: #555; white-space: nowrap; }',
    '#page-counter { font-size: 0.72rem; color: #ffffff; font-weight: 600; white-space: nowrap; }'
)
print("Fix 2 (contador blanco) OK")

# FIX 3: Boton X cierra la pestana
content = content.replace(
    'href="javascript:history.back()"',
    'onclick="window.close()" href="#"'
)
print("Fix 3 (cerrar pestana) OK")

# FIX 4: Foja mas visible - sacar spacer y agregar margen al foja-wrap
content = content.replace(
    '<div class="tb-spacer"></div>',
    ''
)
content = content.replace(
    '<div class="tb-foja-wrap">',
    '<div class="tb-foja-wrap" style="margin-left:auto;">'
)
print("Fix 4 (foja visible) OK")

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nListo. Reinicia el servidor.")
