# -*- coding: utf-8 -*-
"""
Instalador Oficial do Glide Studio para Windows (Versão Nativa 100% Desacoplada de WebView2)
Instala o Glide Studio localmente em %LOCALAPPDATA%\\Programs\\Glide Studio,
migra todas as configurações, projetos e mídias, cria o atalho oficial na Área de Trabalho
e no Menu Iniciar, e registra o desinstalador no Windows.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import winreg
from pathlib import Path

APP_NAME = "Glide Studio"
APP_VERSION = "1.40.0"
DEFAULT_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Programs" / "Glide Studio"


def get_source_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def create_windows_shortcut(target_path: Path, shortcut_path: Path, icon_path: Path | None = None, args: str = "", work_dir: Path | None = None, description: str = "") -> bool:
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir_str = str(work_dir or target_path.parent)
    icon_str = f"$s.IconLocation = '{icon_path},0';" if icon_path and icon_path.exists() else f"$s.IconLocation = '{target_path},0';"
    args_str = f"$s.Arguments = '{args}';" if args else ""
    desc_str = f"$s.Description = '{description}';" if description else ""

    ps_script = f"""
    $w = New-Object -ComObject WScript.Shell;
    $s = $w.CreateShortcut('{str(shortcut_path)}');
    $s.TargetPath = '{str(target_path)}';
    $s.WorkingDirectory = '{work_dir_str}';
    {args_str}
    {icon_str}
    {desc_str}
    $s.Save();
    """
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, check=True)
        return shortcut_path.exists()
    except Exception as exc:
        print(f"Erro ao criar atalho {shortcut_path.name}: {exc}", file=sys.stderr)
        return False


def register_windows_uninstall(install_dir: Path, icon_path: Path) -> None:
    uninstall_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\GlideStudio"
    uninstall_bat = install_dir / "Uninstall.bat"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_key) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Glide Studio")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Glide Studio")
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(icon_path))
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'cmd.exe /c "{str(uninstall_bat)}"')
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except Exception as exc:
        print(f"Aviso ao registrar desinstalador no registro: {exc}", file=sys.stderr)


def create_uninstall_script(install_dir: Path) -> Path:
    desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
    start_menu = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Glide Studio"

    script = f"""@echo off
title Desinstalador Glide Studio
echo ========================================================
echo           DESINSTALADOR GLIDE STUDIO
echo ========================================================
echo.
set /p CONFIRM=Tem certeza de que deseja remover o Glide Studio do computador? (S/N): 
if /i not "%CONFIRM%"=="S" (
    echo Operacao cancelada.
    pause
    exit /b
)

echo.
echo Removendo atalho da Area de Trabalho...
del /f /q "{desktop}\\Glide Studio.lnk" 2>nul
del /f /q "{desktop}\\Glide Studio (Modo Navegador).lnk" 2>nul

echo Removendo atalhos do Menu Iniciar...
rmdir /s /q "{start_menu}" 2>nul

echo Removendo registro do Windows...
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GlideStudio" /f 2>nul

echo.
set /p KEEP_DATA=Deseja MANTER seus projetos salvos e configuracoes? (S/N) [Recomendado: S]: 
if /i "%KEEP_DATA%"=="N" (
    echo Removendo todos os ficheiros do programa e projetos...
    cd ..
    rmdir /s /q "{install_dir}" 2>nul
    echo Glide Studio e todos os dados foram removidos com sucesso.
) else (
    echo Mantendo pasta de dados e projetos em {install_dir}.
    echo Removendo ficheiros executaveis...
    del /f /q "{install_dir}\\Glide Studio.exe" 2>nul
    del /f /q "{install_dir}\\Glide Studio (Modo Navegador).bat" 2>nul
    echo Desinstalacao concluida. Seus projetos continuam preservados.
)

pause
"""
    uninstall_bat = install_dir / "Uninstall.bat"
    uninstall_bat.write_text(script, encoding="utf-8")
    return uninstall_bat


def perform_installation(
    source_dir: Path,
    dest_dir: Path,
    desktop_shortcut: bool = True,
    start_menu: bool = True,
    migrate_data: bool = True,
    progress_callback = None,
) -> bool:
    def update(pct: int, msg: str):
        if progress_callback:
            progress_callback(pct, msg)
        else:
            print(f"[{pct:3d}%] {msg}")

    update(5, "Criando diretório de instalação...")
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 1. Localizar o executável compilado mais recente
    candidates = [source_dir / "Glide Studio.exe", source_dir / "dist" / "Glide Studio.exe"]
    existing_candidates = [cand for cand in candidates if cand.exists()]
    if not existing_candidates:
        raise FileNotFoundError(f"Não foi possível encontrar Glide Studio.exe em {source_dir} nem em {source_dir / 'dist'}")
    exe_source = max(existing_candidates, key=lambda cand: cand.stat().st_mtime)

    update(15, "Instalando aplicativo principal (Glide Studio.exe)...")
    shutil.copy2(exe_source, dest_dir / "Glide Studio.exe")

    # 2. Copiar assets e ferramentas essenciais (FFmpeg, Whisper, modelos, etc.)
    update(30, "Instalando recursos do sistema (FFmpeg, modelos de IA, assets)...")
    for folder_name in ["tools", "model_packs", "assets", "frontend", "reference_styles"]:
        s_folder = source_dir / folder_name
        d_folder = dest_dir / folder_name
        if s_folder.exists() and s_folder.is_dir():
            if d_folder.exists():
                shutil.rmtree(d_folder, ignore_errors=True)
            shutil.copytree(s_folder, d_folder)

    # 3. Migrar dados e projetos existentes com segurança
    if migrate_data:
        update(50, "Migrando e preservando projetos, históricos e mídias...")
        data_files = [
            "queue_projects.json",
            "music_history.json",
            "render_performance.json",
            "visual_clean_cache.json",
            "app_settings.json",
            "glide_studio.db",
            "glide_intelligence.sqlite3",
        ]
        for fname in data_files:
            s_file = source_dir / fname
            d_file = dest_dir / fname
            if s_file.exists():
                shutil.copy2(s_file, d_file)

        data_folders = [
            "project_media",
            "DROPZONE",
            "OUTPUT",
            "exports",
            "queue_backups",
        ]
        for fol_name in data_folders:
            s_f = source_dir / fol_name
            d_f = dest_dir / fol_name
            if s_f.exists() and s_f.is_dir():
                d_f.mkdir(parents=True, exist_ok=True)
                for item in s_f.iterdir():
                    dest_item = d_f / item.name
                    if not dest_item.exists():
                        if item.is_dir():
                            shutil.copytree(item, dest_item)
                        else:
                            shutil.copy2(item, dest_item)

    # 4. Limpeza de artefatos legados ou obsoletos
    update(70, "Limpando artefatos antigos e garantindo pasta organizada...")
    old_files_to_remove = [
        dest_dir / "Glide Studio (Modo Navegador).bat",
        dest_dir / "Glide Studio.old.exe",
    ]
    for old_f in old_files_to_remove:
        if old_f.exists():
            old_f.unlink(missing_ok=True)

    old_wv = dest_dir / "webview_profile"
    if old_wv.exists():
        shutil.rmtree(old_wv, ignore_errors=True)

    # 5. Criar script de desinstalação
    update(80, "Gerando script de desinstalação oficial...")
    create_uninstall_script(dest_dir)

    # 6. Registrar no Windows
    update(85, "Registrando aplicação no Painel do Windows...")
    icon_path = dest_dir / "assets" / "glide_studio.ico"
    register_windows_uninstall(dest_dir, icon_path)

    # 7. Criar Atalho Único na Área de Trabalho e Menu Iniciar
    update(92, "Criando atalho na Área de Trabalho e Menu Iniciar...")
    desktop_dir = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
    start_menu_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Glide Studio"

    # Remove qualquer atalho antigo do Modo Navegador
    (desktop_dir / "Glide Studio (Modo Navegador).lnk").unlink(missing_ok=True)
    (start_menu_dir / "Glide Studio (Modo Navegador).lnk").unlink(missing_ok=True)

    installed_exe = dest_dir / "Glide Studio.exe"

    if desktop_shortcut:
        create_windows_shortcut(
            target_path=installed_exe,
            shortcut_path=desktop_dir / "Glide Studio.lnk",
            icon_path=icon_path,
            description="Glide Studio - Editor e Renderizador de Vídeo Local",
            work_dir=dest_dir,
        )

    if start_menu:
        create_windows_shortcut(
            target_path=installed_exe,
            shortcut_path=start_menu_dir / "Glide Studio.lnk",
            icon_path=icon_path,
            description="Glide Studio - Editor e Renderizador de Vídeo Local",
            work_dir=dest_dir,
        )

    try:
        ps_notify = '''
        $code = @"
        [System.Runtime.InteropServices.DllImport("shell32.dll")]
        public static extern void SHChangeNotify(int wEventId, int uFlags, IntPtr dwItem1, IntPtr dwItem2);
"@
        $type = Add-Type -MemberDefinition $code -Name ShellNotify -Namespace Win32 -PassThru -ErrorAction SilentlyContinue
        if ($type) { $type::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero) }
        '''
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_notify], capture_output=True, text=True)
    except Exception:
        pass

    update(100, "Instalação concluída com sucesso!")
    return True


def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    source_dir = get_source_dir()

    root = tk.Tk()
    root.title(f"{APP_NAME} - Instalador Oficial")
    root.geometry("620x480")
    root.resizable(False, False)
    root.configure(bg="#0d1117")

    ico = source_dir / "assets" / "glide_studio.ico"
    if ico.exists():
        try:
            root.iconbitmap(str(ico))
        except Exception:
            pass

    # Cabeçalho
    header_frame = tk.Frame(root, bg="#161b22", height=80)
    header_frame.pack(fill="x")
    header_frame.pack_propagate(False)

    title_lbl = tk.Label(header_frame, text=f"Instalador do {APP_NAME} v{APP_VERSION}", font=("Segoe UI", 16, "bold"), fg="#58a6ff", bg="#161b22")
    title_lbl.pack(anchor="w", padx=24, pady=(16, 2))
    sub_lbl = tk.Label(header_frame, text="Versão nativa local sem dependência de WebView2", font=("Segoe UI", 9), fg="#8b949e", bg="#161b22")
    sub_lbl.pack(anchor="w", padx=24)

    # Conteúdo Principal
    content_frame = tk.Frame(root, bg="#0d1117", padx=24, pady=16)
    content_frame.pack(fill="both", expand=True)

    # Destino
    dest_lbl = tk.Label(content_frame, text="Pasta de Instalação no Windows:", font=("Segoe UI", 10, "bold"), fg="#f0f6fc", bg="#0d1117")
    dest_lbl.pack(anchor="w", pady=(0, 4))

    dest_box = tk.Frame(content_frame, bg="#0d1117")
    dest_box.pack(fill="x", pady=(0, 16))

    dest_var = tk.StringVar(value=str(DEFAULT_INSTALL_DIR))
    dest_entry = tk.Entry(dest_box, textvariable=dest_var, font=("Segoe UI", 9), bg="#21262d", fg="#f0f6fc", insertbackground="#fff", relief="flat", highlightthickness=1, highlightcolor="#58a6ff")
    dest_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

    def browse_dest():
        chosen = filedialog.askdirectory(initialdir=dest_var.get())
        if chosen:
            dest_var.set(chosen)

    browse_btn = tk.Button(dest_box, text="Procurar...", font=("Segoe UI", 9), bg="#30363d", fg="#f0f6fc", relief="flat", padx=12, command=browse_dest)
    browse_btn.pack(side="right")

    # Opções
    opts_lbl = tk.Label(content_frame, text="Opções da Instalação:", font=("Segoe UI", 10, "bold"), fg="#f0f6fc", bg="#0d1117")
    opts_lbl.pack(anchor="w", pady=(0, 6))

    chk_desktop_var = tk.BooleanVar(value=True)
    chk_start_var = tk.BooleanVar(value=True)
    chk_migrate_var = tk.BooleanVar(value=True)

    chk_style = {"bg": "#0d1117", "fg": "#f0f6fc", "activebackground": "#0d1117", "activeforeground": "#58a6ff", "selectcolor": "#21262d", "font": ("Segoe UI", 9)}

    tk.Checkbutton(content_frame, text="Criar atalho na Área de Trabalho (Glide Studio)", variable=chk_desktop_var, **chk_style).pack(anchor="w", pady=2)
    tk.Checkbutton(content_frame, text="Adicionar ao Menu Iniciar do Windows", variable=chk_start_var, **chk_style).pack(anchor="w", pady=2)
    tk.Checkbutton(content_frame, text="Migrar e preservar todos os projetos, históricos e mídias existentes", variable=chk_migrate_var, **chk_style).pack(anchor="w", pady=2)

    # Info de arquitetura
    info_box = tk.Label(content_frame, text="Execução Nativa: O aplicativo roda em janela nativa dedicada (Zero WebView2, sem vazamento de memória).", font=("Segoe UI", 8), fg="#7ee787", bg="#0d1117", wraplength=570, justify="left")
    info_box.pack(anchor="w", pady=(8, 0))

    # Barra de Progresso
    status_var = tk.StringVar(value="Pronto para iniciar a instalação.")
    status_lbl = tk.Label(content_frame, textvariable=status_var, font=("Segoe UI", 9), fg="#8b949e", bg="#0d1117")
    status_lbl.pack(anchor="w", pady=(14, 4))

    progress = ttk.Progressbar(content_frame, orient="horizontal", mode="determinate")
    progress.pack(fill="x", pady=(0, 16))

    # Botões
    btn_box = tk.Frame(root, bg="#161b22", height=60, padx=24)
    btn_box.pack(fill="x", side="bottom")

    def start_install():
        btn_install.config(state="disabled")
        dest_path = Path(dest_var.get().strip())

        def callback(pct, msg):
            progress["value"] = pct
            status_var.set(msg)
            root.update_idletasks()

        try:
            perform_installation(
                source_dir=source_dir,
                dest_dir=dest_path,
                desktop_shortcut=chk_desktop_var.get(),
                start_menu=chk_start_var.get(),
                migrate_data=chk_migrate_var.get(),
                progress_callback=callback,
            )
            ans = messagebox.askyesno(
                "Instalação Concluída",
                f"O {APP_NAME} foi instalado com sucesso em:\n{dest_path}\n\nDeseja abrir o {APP_NAME} agora?"
            )
            if ans:
                installed_exe = dest_path / "Glide Studio.exe"
                if installed_exe.exists():
                    subprocess.Popen([str(installed_exe)], cwd=str(dest_path))
            root.destroy()
        except Exception as exc:
            messagebox.showerror("Erro na Instalação", f"Ocorreu um erro ao instalar:\n{exc}")
            btn_install.config(state="normal")

    btn_cancel = tk.Button(btn_box, text="Cancelar", font=("Segoe UI", 9), bg="#21262d", fg="#f0f6fc", relief="flat", padx=16, pady=6, command=root.destroy)
    btn_cancel.pack(side="left", pady=12)

    btn_install = tk.Button(btn_box, text="Instalar Glide Studio", font=("Segoe UI", 10, "bold"), bg="#238636", fg="#ffffff", activebackground="#2ea043", relief="flat", padx=20, pady=6, command=start_install)
    btn_install.pack(side="right", pady=12)

    root.mainloop()


def main():
    if "--silent" in sys.argv or "--cli" in sys.argv:
        source_dir = get_source_dir()
        dest_dir = DEFAULT_INSTALL_DIR
        for arg in sys.argv:
            if arg.startswith("--dir="):
                dest_dir = Path(arg.split("=", 1)[1].strip('"'))
        print(f"Iniciando instalacao silenciosa de {APP_NAME} em {dest_dir}...")
        perform_installation(source_dir, dest_dir)
        print("Instalacao concluida.")
    else:
        run_gui()


if __name__ == "__main__":
    main()
