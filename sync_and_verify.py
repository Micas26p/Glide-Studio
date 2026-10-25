# -*- coding: utf-8 -*-
import os
import sys
import shutil
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
INSTALL_DIR = Path(LOCALAPPDATA) / "Programs" / "Glide Studio"
DIST_DIR = ROOT / "dist"

def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest().upper()

def main():
    print("=== SYNCHRONIZING TARGETS ===")
    exe_root = ROOT / "Glide Studio.exe"
    if not exe_root.exists():
        print(f"ERRO: {exe_root} nao existe!", file=sys.stderr)
        sys.exit(1)

    # 1. Dist copy
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    exe_dist = DIST_DIR / "Glide Studio.exe"
    print(f"Copiando para {exe_dist}...")
    shutil.copy2(exe_root, exe_dist)

    # 2. LocalAppData copy
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    exe_install = INSTALL_DIR / "Glide Studio.exe"
    print(f"Copiando para {exe_install}...")
    shutil.copy2(exe_root, exe_install)

    # 3. Synchronize asset directories
    folders = ["frontend", "assets", "tools", "model_packs", "reference_styles"]
    for folder_name in folders:
        src = ROOT / folder_name
        dst = INSTALL_DIR / folder_name
        if src.exists():
            print(f"Sincronizando pasta {folder_name} -> {dst}...")
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            print(f"Aviso: pasta {folder_name} nao encontrada na raiz.")

    print("\n=== VERIFICANDO SHA-256 HASHES ===")
    hash_root = sha256_file(exe_root)
    hash_dist = sha256_file(exe_dist)
    hash_install = sha256_file(exe_install)

    print(f"Root:      {exe_root}\n           SHA256: {hash_root}")
    print(f"Dist:      {exe_dist}\n           SHA256: {hash_dist}")
    print(f"Installed: {exe_install}\n           SHA256: {hash_install}")

    if hash_root == hash_dist == hash_install:
        print("\n[SUCESSO] Todos os 3 executaveis possuem hashes SHA-256 IDENTICOS!")
    else:
        print("\n[ERRO] Discrepancia detectada nos hashes SHA-256!", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
