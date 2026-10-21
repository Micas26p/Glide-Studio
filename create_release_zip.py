# -*- coding: utf-8 -*-
"""
Gera o pacote oficial compactado (Glide_Studio_Instalador_Completo.zip)
contendo todos os ficheiros essenciais para levar o Glide Studio para qualquer PC
via Pen-drive, Google Drive ou GitHub Releases sem precisar de Python nem de agentes.
"""

import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_ZIP = ROOT / "Glide_Studio_Instalador_Completo.zip"

INCLUDE_FILES = [
    "Glide Studio.exe",
    "INSTALAR_GLIDE_STUDIO.bat",
    "instalar.bat",
    "installer.py",
]

INCLUDE_DIRS = [
    "assets",
    "frontend",
    "model_packs",
    "reference_styles",
    "tools",
]

README_CONTENT = """===============================================================================
                       GLIDE STUDIO - INSTALADOR OFICIAL
===============================================================================

Este pacote contem a versao oficial do Glide Studio 100% pronta para uso local.
Nao e necessario instalar Python, nem bibliotecas, nem configurar variaveis de ambiente.

COMO INSTALAR NESTE COMPUTADOR:
1. Extraia todo o conteudo deste arquivo ZIP para uma pasta no seu computador.
2. De um clique duplo no arquivo:
      INSTALAR_GLIDE_STUDIO.bat
3. O instalador ira configurar automaticamente o Glide Studio no seu Windows e
   colocar o icone oficial na sua Area de Trabalho e no Menu Iniciar.
4. Abra o Glide Studio pelo atalho da Area de Trabalho e aproveite!

REQUISITOS RECOMENDADOS:
- Windows 10 ou Windows 11 (64 bits)
- 8 GB ou mais de memoria RAM
- Placa de video NVIDIA (RTX / GTX) recomendada para codificacao ultra-rapida por hardware
"""

def make_zip():
    print(f"Criando pacote: {OUTPUT_ZIP.name}...")
    (ROOT / "COMO_INSTALAR.txt").write_text(README_CONTENT, encoding="utf-8")
    
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(ROOT / "COMO_INSTALAR.txt", "COMO_INSTALAR.txt")
        
        for fname in INCLUDE_FILES:
            fpath = ROOT / fname
            if fpath.exists():
                print(f"  + Adicionando arquivo: {fname}")
                zf.write(fpath, fname)
            else:
                print(f"  ! Aviso: Arquivo {fname} nao encontrado.")
                
        for dname in INCLUDE_DIRS:
            dpath = ROOT / dname
            if dpath.exists() and dpath.is_dir():
                print(f"  + Adicionando pasta: {dname}/...")
                for item in dpath.rglob("*"):
                    if item.is_file():
                        # Evitar ficheiros temporários
                        if item.suffix in [".tmp", ".log"] or "__pycache__" in item.parts:
                            continue
                        rel_path = item.relative_to(ROOT)
                        zf.write(item, str(rel_path))
                        
    size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"\n[SUCESSO] Pacote gerado com sucesso!")
    print(f"Arquivo: {OUTPUT_ZIP}")
    print(f"Tamanho total: {size_mb:.1f} MB")

if __name__ == "__main__":
    make_zip()
