# Ejecutar desde la carpeta raiz del proyecto:
# python fix_buscador.py

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazar todo el bloque del buscador
old_buscador = '''// ── BUSCADOR ──────────────────────────────────────────────────────────
let coincidencias = [], indiceActual = -1, queryActual = '';
const searchInput  = document.getElementById('keyword-search');
const contadorSpan = document.getElementById('search-counter');

async function buscarTodo(query) {
    if (!query || !currentPdf) return;
    coincidencias = []; indiceActual = -1; queryActual = query;
    limpiarSubrayados();
    contadorSpan.innerText = 'Buscando...';
    for (let i = 1; i <= totalPages; i++) {
        const page = await currentPdf.getPage(i);
        const tc   = await page.getTextContent();
        const txt  = tc.items.map(it => it.str).join(' ').toLowerCase();
        if (txt.includes(query.toLowerCase())) coincidencias.push({ page: i });
    }
    if (!coincidencias.length) { contadorSpan.innerText = '0 resultados'; return; }
    indiceActual = 0;
    await mostrarCoincidencia();
}

async function mostrarCoincidencia() {
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
}

async function navegarBuscador(dir) {
    if (!coincidencias.length) return;
    indiceActual = (indiceActual + dir + coincidencias.length) % coincidencias.length;
    await mostrarCoincidencia();
}

function limpiarSubrayados() {
    document.querySelectorAll('.textLayer').forEach(tl => $(tl).unmark());
}

searchInput.addEventListener('keydown', async function(e) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const query = this.value.trim();
    if (!query) return;
    if (!coincidencias.length || this.dataset.lastQuery !== query) {
        this.dataset.lastQuery = query;
        await buscarTodo(query);
    } else {
        await navegarBuscador(e.shiftKey ? -1 : 1);
    }
});

searchInput.addEventListener('input', function() {
    if (!this.value.trim()) {
        coincidencias = []; indiceActual = -1; queryActual = '';
        contadorSpan.innerText = ''; limpiarSubrayados();
    }
});'''

new_buscador = '''// ── BUSCADOR SIMPLE ───────────────────────────────────────────────────
// Busca en qué fojas aparece la palabra y navega entre ellas.
// Sin resaltado visual — solo navegación de fojas.
let fojasCoinc = [], idxCoinc = -1;
const searchInput  = document.getElementById('keyword-search');
const contadorSpan = document.getElementById('search-counter');

async function buscarTodo(query) {
    if (!query || !currentPdf) return;
    fojasCoinc = []; idxCoinc = -1;
    contadorSpan.innerText = 'Buscando...';

    for (let i = 1; i <= totalPages; i++) {
        const page = await currentPdf.getPage(i);
        const tc   = await page.getTextContent();
        const txt  = tc.items.map(it => it.str).join(' ').toLowerCase();
        if (txt.includes(query.toLowerCase())) fojasCoinc.push(i);
    }

    if (!fojasCoinc.length) {
        contadorSpan.innerText = '0 resultados';
        return;
    }

    idxCoinc = 0;
    irAFoja(fojasCoinc[0]);
    contadorSpan.innerText = '1 / ' + fojasCoinc.length + ' fojas';
}

function navegarBuscador(dir) {
    if (!fojasCoinc.length) return;
    idxCoinc = (idxCoinc + dir + fojasCoinc.length) % fojasCoinc.length;
    irAFoja(fojasCoinc[idxCoinc]);
    contadorSpan.innerText = (idxCoinc + 1) + ' / ' + fojasCoinc.length + ' fojas';
}

function irAFoja(foja) {
    $('#album').turn('page', foja);
    actualizarFooter(foja);
}

function limpiarSubrayados() {}  // no-op, mantenido por compatibilidad

searchInput.addEventListener('keydown', async function(e) {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const query = this.value.trim();
    if (!query) return;
    // Si ya hay resultados para la misma query → navegar al siguiente
    if (fojasCoinc.length && this.dataset.lastQuery === query) {
        navegarBuscador(1);
    } else {
        this.dataset.lastQuery = query;
        await buscarTodo(query);
    }
});

searchInput.addEventListener('input', function() {
    if (!this.value.trim()) {
        fojasCoinc = []; idxCoinc = -1;
        contadorSpan.innerText = '';
    }
});'''

if old_buscador in content:
    content = content.replace(old_buscador, new_buscador)
    print("Buscador reemplazado OK")
else:
    print("NOT FOUND — buscando version alternativa...")
    # Buscar por fragmento clave
    if 'async function buscarTodo(query)' in content:
        print("La funcion existe pero el bloque completo no coincide exactamente")
        print("Aplicando fix manual...")
        # Reemplazar solo la funcion mostrarCoincidencia y navegarBuscador
        print("Revisar manualmente")
    else:
        print("No se encontro el buscador")

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Listo.")
