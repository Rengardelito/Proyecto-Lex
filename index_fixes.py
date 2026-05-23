# Este script aplica los 2 fixes al index.html
# Ejecutalo en tu PC con: python index_fixes.py

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# ══════════════════════════════════════════════════════
# FIX 1 — BUSCADOR: re-marcar al cambiar de página
# ══════════════════════════════════════════════════════

# Reemplazar el bloque turned del turn.js para que re-marque
old_turned = '''            when: {
                turned: async function(e, page) {
                    actualizarFooter(page);
                    limpiarSubrayados();
                    await precargarAlrededor(page);
                }
            }'''

new_turned = '''            when: {
                turned: async function(e, page) {
                    actualizarFooter(page);
                    await precargarAlrededor(page);
                    // Re-marcar si hay búsqueda activa
                    if (queryActual) {
                        await new Promise(r => setTimeout(r, 300));
                        await asegurarTextLayer(page);
                        const pageEl = _getPageEl(page);
                        if (pageEl) {
                            const tl = pageEl.querySelector('.textLayer');
                            if (tl && !tl.querySelector('mark')) {
                                $(tl).mark(queryActual, {
                                    separateWordSearch: false,
                                    diacritics: true,
                                    acrossElements: true
                                });
                            }
                        }
                    }
                }
            }'''

if old_turned in content:
    content = content.replace(old_turned, new_turned)
    print("FIX 1a (turned) OK")
else:
    print("FIX 1a NOT FOUND")

# Reemplazar mostrarCoincidencia para que funcione mejor con turn.js
old_mostrar = '''async function mostrarCoincidencia() {
    if (indiceActual < 0 || indiceActual >= coincidencias.length) return;
    const { page } = coincidencias[indiceActual];
    contadorSpan.innerText = `${indiceActual + 1} / ${coincidencias.length}`;
    document.querySelectorAll('.textLayer mark.current').forEach(m => m.classList.remove('current'));
    $('#album').turn('page', page);
    actualizarFooter(page);
    await new Promise(r => setTimeout(r, 500));
    await asegurarTextLayer(page);
    const pageEl = _getPageEl(page);
    if (!pageEl) return;
    const tl = pageEl.querySelector('.textLayer');
    if (!tl) return;
    const yaMarcado = tl.querySelector('mark');
    if (yaMarcado) {
        yaMarcado.classList.add('current');
        return;
    }
    $(tl).mark(queryActual, {
        separateWordSearch: false, diacritics: true, acrossElements: true,
        done: function() {
            const first = tl.querySelector('mark');
            if (first) first.classList.add('current');
        }
    });
}'''

new_mostrar = '''async function mostrarCoincidencia() {
    if (indiceActual < 0 || indiceActual >= coincidencias.length) return;
    const { page } = coincidencias[indiceActual];
    contadorSpan.innerText = `${indiceActual + 1} / ${coincidencias.length}`;

    // Cambiar de página
    $('#album').turn('page', page);
    actualizarFooter(page);

    // Esperar que turn.js termine la animación y el DOM esté listo
    await new Promise(r => setTimeout(r, 600));
    await asegurarTextLayer(page);

    const pageEl = _getPageEl(page);
    if (!pageEl) return;
    const tl = pageEl.querySelector('.textLayer');
    if (!tl) return;

    // Limpiar marks anteriores en TODAS las páginas
    document.querySelectorAll('.textLayer').forEach(t => $(t).unmark());

    // Marcar en la página actual
    await new Promise(resolve => {
        $(tl).mark(queryActual, {
            separateWordSearch: false,
            diacritics: true,
            acrossElements: true,
            done: function() {
                const first = tl.querySelector('mark');
                if (first) {
                    first.classList.add('current');
                    // Scroll al mark
                    const vp = document.getElementById('viewport');
                    const rect = first.getBoundingClientRect();
                    const vpRect = vp.getBoundingClientRect();
                    vp.scrollBy({ top: rect.top - vpRect.top - vp.clientHeight / 2, behavior: 'smooth' });
                }
                resolve();
            }
        });
    });
}'''

if old_mostrar in content:
    content = content.replace(old_mostrar, new_mostrar)
    print("FIX 1b (mostrarCoincidencia) OK")
else:
    print("FIX 1b NOT FOUND")

# ══════════════════════════════════════════════════════
# FIX 2 — CARÁTULA: pasar desde Flask y pre-llenar
# ══════════════════════════════════════════════════════

# En el visor, la ruta de Flask ya tiene info_causa.demandado
# Hay que pasar caratula_texto al template y leerla en JS

# Paso 2a: agregar EXPTE_CARATULA como variable JS
old_expte_vars = '''const EXPTE_NRO       = '{{ expte }}';
const EXPTE_JUZGADO   = '{{ request.view_args.juzgado }}';
const EXPTE_SECRETARIA= '{{ request.view_args.secretaria }}';'''

new_expte_vars = '''const EXPTE_NRO        = '{{ expte }}';
const EXPTE_JUZGADO    = '{{ request.view_args.juzgado }}';
const EXPTE_SECRETARIA = '{{ request.view_args.secretaria }}';
const EXPTE_CARATULA   = '{{ caratula_texto | replace("'", "\\'") }}';'''

if old_expte_vars in content:
    content = content.replace(old_expte_vars, new_expte_vars)
    print("FIX 2a (JS var) OK")
else:
    print("FIX 2a NOT FOUND")

# Paso 2b: pre-llenar f-caratula en cargarFormulario
old_secretaria_fill = '''    document.getElementById('f-juzgado').value    = EXPTE_JUZGADO;
    document.getElementById('f-nro-expte').value  = EXPTE_NRO;
    document.getElementById('f-secretaria').value = EXPTE_SECRETARIA;

    // Carátula: intentar leerla del DOM del visor (ya cargada)
    // (Se pasa como data attribute en la URL del visor si es necesario)'''

new_secretaria_fill = '''    document.getElementById('f-juzgado').value    = EXPTE_JUZGADO;
    document.getElementById('f-nro-expte').value  = EXPTE_NRO;
    document.getElementById('f-secretaria').value = EXPTE_SECRETARIA;
    document.getElementById('f-caratula').value   = EXPTE_CARATULA;'''

if old_secretaria_fill in content:
    content = content.replace(old_secretaria_fill, new_secretaria_fill)
    print("FIX 2b (caratula fill) OK")
else:
    print("FIX 2b NOT FOUND")

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nListo. Reiniciá el servidor para ver los cambios.")
