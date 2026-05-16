"""
build_release.py — Empaqueta los archivos de código en un zip para el release de GitHub.

Uso:
    python build_release.py 1.2.0

Genera:
    dist/lexview-update-1.2.0.zip
    dist/lexview-update-1.2.0.zip.sha256

Luego subís el zip a GitHub Releases con el tag v1.2.0
y actualizás CURRENT_VERSION en el server.py del VPS.
"""

import sys
import hashlib
import zipfile
from pathlib import Path

# Archivos y carpetas que van en el zip de actualización
UPDATABLE_FILES = ["app.py", "config.py"]
UPDATABLE_DIRS  = ["bots", "helpers", "templates", "static"]

# Extensiones a excluir del zip
EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".DS_Store"}
EXCLUDE_DIRS       = {"__pycache__", ".git", ".pytest_cache"}


def build_zip(version: str, project_root: Path) -> Path:
    dist_dir = project_root / "dist"
    dist_dir.mkdir(exist_ok=True)

    zip_name = f"lexview-update-{version}.zip"
    zip_path = dist_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:

        # Archivos sueltos
        for filename in UPDATABLE_FILES:
            src = project_root / filename
            if src.exists():
                zf.write(src, f"update/{filename}")
                print(f"  + {filename}")
            else:
                print(f"  ⚠ No encontrado: {filename}")

        # Carpetas
        for dir_name in UPDATABLE_DIRS:
            src_dir = project_root / dir_name
            if not src_dir.exists():
                print(f"  ⚠ Carpeta no encontrada: {dir_name}/")
                continue

            for file_path in src_dir.rglob("*"):
                # Filtrar exclusiones
                if file_path.suffix in EXCLUDE_EXTENSIONS:
                    continue
                if any(part in EXCLUDE_DIRS for part in file_path.parts):
                    continue
                if file_path.is_dir():
                    continue

                rel = file_path.relative_to(project_root)
                zf.write(file_path, f"update/{rel}")
                print(f"  + {rel}")

        # Incluir version.txt dentro del zip
        version_content = version.encode("utf-8")
        zf.writestr("update/version.txt", version_content)
        print(f"  + version.txt ({version})")

    print(f"\nZip generado: {zip_path} ({zip_path.stat().st_size // 1024} KB)")
    return zip_path


def compute_sha256(zip_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def write_sha256_file(zip_path: Path, digest: str):
    sha_path = zip_path.with_suffix(".zip.sha256")
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    print(f"SHA256: {digest}")
    print(f"Archivo: {sha_path}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python build_release.py <version>")
        print("Ejemplo: python build_release.py 1.2.0")
        sys.exit(1)

    version = sys.argv[1].lstrip("v")
    project_root = Path(__file__).parent

    print(f"\n{'='*50}")
    print(f"  LexView Pro — Build Release v{version}")
    print(f"{'='*50}\n")
    print("Empaquetando archivos...")

    zip_path = build_zip(version, project_root)
    digest   = compute_sha256(zip_path)
    write_sha256_file(zip_path, digest)

    print(f"\n{'='*50}")
    print("  Próximos pasos:")
    print(f"{'='*50}")
    print(f"1. git tag v{version} && git push origin v{version}")
    print(f"2. Subir {zip_path.name} a GitHub Releases (tag v{version})")
    print(f"3. En el VPS, editar /opt/lexview_server/server.py:")
    print(f'   CURRENT_VERSION = "{version}"')
    print(f"4. sudo systemctl restart lexview (o equivalente)")
    print(f"\n  SHA256 para el endpoint del VPS (opcional):")
    print(f"  {digest}")


if __name__ == "__main__":
    main()
