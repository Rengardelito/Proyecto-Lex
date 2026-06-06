"""
helpers/rtf_converter.py
Convierte archivos .rtf a .pdf con múltiples fallbacks:
  1. Microsoft Word (pywin32) — mejor calidad, requiere Word
  2. LibreOffice headless     — buena calidad, requiere LibreOffice
  3. pypandoc + weasyprint    — Python puro, siempre disponible
"""

import os
import sys
import shutil
import tempfile
import subprocess
from pathlib import Path


def rtf_a_pdf(ruta_rtf: str, ruta_pdf: str = None) -> str | None:
    """
    Convierte un archivo .rtf a .pdf.

    ruta_rtf: ruta al archivo .rtf
    ruta_pdf: ruta destino del .pdf (si None, mismo nombre con extensión .pdf)

    Retorna la ruta del .pdf generado, o None si falló todo.
    """
    ruta_rtf = str(ruta_rtf)
    if not os.path.exists(ruta_rtf):
        print(f"❌ rtf_a_pdf: no existe {ruta_rtf}")
        return None

    if ruta_pdf is None:
        ruta_pdf = ruta_rtf.rsplit('.', 1)[0] + '.pdf'

    # Intentar cada método en orden
    metodos = [
        ("Microsoft Word",  _convertir_con_word),
        ("LibreOffice",     _convertir_con_libreoffice),
        ("pypandoc",        _convertir_con_pypandoc),
    ]

    for nombre, fn in metodos:
        try:
            resultado = fn(ruta_rtf, ruta_pdf)
            if resultado and os.path.exists(resultado) and os.path.getsize(resultado) > 500:
                print(f"✅ RTF convertido con {nombre}: {os.path.basename(ruta_pdf)}")
                return resultado
        except Exception as e:
            print(f"⚠️ {nombre} falló: {e}")
            continue

    print(f"❌ No se pudo convertir {os.path.basename(ruta_rtf)} con ningún método")
    return None


# ── Método 1: Microsoft Word vía COM ─────────────────────────
def _convertir_con_word(ruta_rtf: str, ruta_pdf: str) -> str | None:
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    word = None
    doc  = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False

        doc = word.Documents.Open(os.path.abspath(ruta_rtf))
        doc.SaveAs(os.path.abspath(ruta_pdf), FileFormat=17)  # 17 = wdFormatPDF
        return ruta_pdf
    finally:
        if doc:
            try: doc.Close(False)
            except: pass
        if word:
            try: word.Quit()
            except: pass
        pythoncom.CoUninitialize()


# ── Método 2: LibreOffice headless ───────────────────────────
def _convertir_con_libreoffice(ruta_rtf: str, ruta_pdf: str) -> str | None:
    # Buscar LibreOffice en rutas comunes de Windows y Linux
    rutas_lo = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/opt/libreoffice/program/soffice",
        shutil.which("soffice") or "",
        shutil.which("libreoffice") or "",
    ]

    soffice = next((r for r in rutas_lo if r and os.path.exists(r)), None)
    if not soffice:
        raise FileNotFoundError("LibreOffice no encontrado")

    # LibreOffice guarda el PDF en el mismo directorio que el RTF
    directorio_rtf = os.path.dirname(os.path.abspath(ruta_rtf))

    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir",
         directorio_rtf, os.path.abspath(ruta_rtf)],
        capture_output=True, text=True, timeout=30
    )

    # LibreOffice genera el PDF con el mismo nombre base
    pdf_generado = os.path.join(
        directorio_rtf,
        Path(ruta_rtf).stem + ".pdf"
    )

    if os.path.exists(pdf_generado):
        if pdf_generado != ruta_pdf:
            shutil.move(pdf_generado, ruta_pdf)
        return ruta_pdf

    raise RuntimeError(f"LibreOffice no generó el PDF: {result.stderr}")


# ── Método 3: pypandoc (Python puro, siempre disponible) ─────
def _convertir_con_pypandoc(ruta_rtf: str, ruta_pdf: str) -> str | None:
    """
    Convierte RTF → HTML → PDF usando pypandoc + weasyprint.
    No requiere nada externo, todo va dentro del .exe.
    La fidelidad es básica pero garantiza que el contenido sea legible.
    """
    import pypandoc

    # Paso 1: RTF → HTML (pypandoc puede hacer esto sin pandoc externo
    # si se usa el modo Python; si no, necesita pandoc instalado)
    try:
        html = pypandoc.convert_file(ruta_rtf, 'html', format='rtf')
    except Exception:
        # Fallback manual: leer RTF como texto plano y wrappear en HTML
        html = _rtf_a_html_basico(ruta_rtf)

    # Paso 2: HTML → PDF con weasyprint
    try:
        from weasyprint import HTML as WeasyprintHTML
        WeasyprintHTML(string=html).write_pdf(ruta_pdf)
        return ruta_pdf
    except ImportError:
        pass

    # Fallback: usar fpdf2 para generar PDF con el texto extraído
    return _html_a_pdf_con_fpdf(html, ruta_pdf)


def _rtf_a_html_basico(ruta_rtf: str) -> str:
    """Extrae texto plano del RTF y lo convierte a HTML básico."""
    import re
    with open(ruta_rtf, 'r', encoding='latin-1', errors='replace') as f:
        contenido = f.read()

    # Remover bloques RTF comunes
    texto = re.sub(r'\{[^{}]*\}', '', contenido)
    texto = re.sub(r'\\[a-z]+\d*\s?', '', texto)
    texto = re.sub(r'[{}\\]', '', texto)
    texto = texto.replace('\r\n', '\n').replace('\r', '\n')
    texto = re.sub(r'\n{3,}', '\n\n', texto).strip()

    parrafos = ''.join(
        f'<p>{linea.strip()}</p>'
        for linea in texto.split('\n')
        if linea.strip()
    )

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12pt;
         margin: 2cm; line-height: 1.5; }}
  p {{ margin-bottom: 0.5em; text-align: justify; }}
</style>
</head><body>{parrafos}</body></html>"""


def _html_a_pdf_con_fpdf(html: str, ruta_pdf: str) -> str | None:
    """Último recurso: extrae texto del HTML y genera PDF con fpdf2."""
    import re
    from fpdf import FPDF

    texto = re.sub(r'<[^>]+>', ' ', html)
    texto = texto.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ')
    texto = re.sub(r'\s+', ' ', texto).strip()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_font("Helvetica", size=11)
    pdf.set_auto_page_break(auto=True, margin=20)

    # Dividir en párrafos de ~100 caracteres
    palabras = texto.split()
    linea = ""
    for palabra in palabras:
        if len(linea) + len(palabra) + 1 > 95:
            pdf.multi_cell(0, 6, linea.strip())
            linea = palabra + " "
        else:
            linea += palabra + " "
    if linea.strip():
        pdf.multi_cell(0, 6, linea.strip())

    pdf.output(ruta_pdf)
    return ruta_pdf


# ── Función de detección anticipada ──────────────────────────
def metodo_disponible() -> str:
    """Retorna qué método de conversión está disponible."""
    try:
        import win32com.client
        return "word"
    except ImportError:
        pass

    rutas_lo = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice", "/usr/bin/libreoffice",
        shutil.which("soffice") or "",
    ]
    if any(r and os.path.exists(r) for r in rutas_lo):
        return "libreoffice"

    try:
        import pypandoc
        return "pypandoc"
    except ImportError:
        pass

    return "fpdf_basico"  # siempre disponible como último recurso
