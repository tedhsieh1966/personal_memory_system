# installer.py — PMS GUI installer / uninstaller
import os
import sys
import shutil
import ctypes
import platform
import subprocess
import tempfile
import urllib.request
import winreg
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import win32com.client

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from app_info import *

INSTALL_DIR   = Path(os.getenv("APPDATA")) / APP
OLLAMA_MODELS = ["qwen2.5:7b", "nomic-embed-text"]
NSSM_URL             = "https://nssm.cc/release/nssm-2.24.zip"
NSSM_ZIP_NAME        = "nssm-2.24"
OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"


def _init_translator():
    """Load LanguageTranslator from the xlsx bundled alongside this script."""
    try:
        from py_libraries.LanguageOp import LanguageTranslator, get_current_input_language
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        else:
            base = os.path.join(current_dir, "pms", "editor")
        xlsx = os.path.join(base, "languages.xlsx")
        translator = LanguageTranslator(xlsx)
        sys_lang = get_current_input_language().get("language_name", "")
        available = translator.get_languages()
        translator.set_current_language(sys_lang if sys_lang in available else available[0])
        return translator.translate
    except Exception:
        return lambda k: k  # fallback: return the key itself


tr = _init_translator()


class PMS_Installer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{BRIEF} {VERSION} — {tr('installer.window_title')}")
        self.root.geometry("572x480")
        self.root.resizable(False, False)

        try:
            self.root.iconbitmap(sys._MEIPASS + "\\favicon.ico")
        except Exception:
            pass

        self.is_installed = self._check_installed()
        self._build_ui()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _check_installed(self):
        return INSTALL_DIR.exists() and (INSTALL_DIR / APP_SERVER_EXE).exists()

    def _is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False

    def _source_dir(self):
        return Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent / "dist"

    def _set_status(self, text, value=None):
        self.status_lbl.config(text=text)
        if value is not None:
            self.progress["value"] = value
        self.root.update_idletasks()

    def _refresh_ui(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.is_installed = self._check_installed()
        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        tk.Label(self.root, text=BRIEF, font=("Arial", 16, "bold")).pack(pady=(20, 4))
        tk.Label(self.root, text=DESCRIPTION).pack()
        tk.Label(self.root, text=f"Version {VERSION}", fg="gray").pack(pady=(2, 10))

        color = "green" if self.is_installed else "red"
        text  = f"{APP_CAPS} {tr('installer.installed_at')} {INSTALL_DIR}" if self.is_installed else f"{APP_CAPS} {tr('installer.not_installed')}"
        tk.Label(self.root, text=text, fg=color, font=("Arial", 9, "bold")).pack()

        # options
        opts = tk.LabelFrame(self.root, text=tr("installer.options"), padx=10, pady=8)
        opts.pack(fill="x", padx=20, pady=10)

        self.shortcut_var = tk.BooleanVar(value=True)
        self.launch_var   = tk.BooleanVar(value=True)
        self.ollama_var   = tk.BooleanVar(value=True)

        tk.Checkbutton(opts, text=tr("installer.create_shortcut"),
                       variable=self.shortcut_var).pack(anchor="w")
        tk.Checkbutton(opts, text=f"{tr('installer.setup_ollama')} ({', '.join(OLLAMA_MODELS)})",
                       variable=self.ollama_var).pack(anchor="w")
        tk.Checkbutton(opts, text=tr("installer.launch_after"),
                       variable=self.launch_var).pack(anchor="w")

        # progress
        pf = tk.Frame(self.root)
        pf.pack(fill="x", padx=20, pady=6)
        self.progress = ttk.Progressbar(pf, orient="horizontal", length=532, mode="determinate")
        self.progress.pack()
        self.status_lbl = tk.Label(pf, text="", fg="gray", font=("Arial", 8))
        self.status_lbl.pack(pady=(4, 0))

        # buttons
        bf = tk.Frame(self.root)
        bf.pack(pady=12)

        if self.is_installed:
            tk.Button(bf, text=tr("installer.btn_uninstall"), width=12, bg="red", fg="white",
                      command=self._uninstall).pack(side="left", padx=5)
            tk.Button(bf, text=tr("installer.btn_reinstall"), width=12,
                      command=self._install).pack(side="left", padx=5)
        else:
            tk.Button(bf, text=tr("installer.btn_install"), width=12,
                      command=self._install).pack(side="left", padx=5)

        tk.Button(bf, text=tr("installer.btn_exit"), width=12, command=self.root.destroy).pack(side="right", padx=5)

    # ── Network helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _download(url: str, dst_path: str, timeout: float = 30.0) -> None:
        """Download `url` to `dst_path` with a connect+read timeout. Raises on failure.
        Replaces urllib.request.urlretrieve, which has no timeout parameter and can
        block the Tkinter UI thread indefinitely on a slow or unreachable host."""
        req = urllib.request.Request(url, headers={"User-Agent": "PMS-Installer"})
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dst_path, "wb") as f:
            shutil.copyfileobj(resp, f)

    # ── NSSM ─────────────────────────────────────────────────────────────────

    def _find_or_install_nssm(self) -> str | None:
        # 1. Already installed at INSTALL_DIR (kept across runs once placed)
        local = INSTALL_DIR / "nssm.exe"
        if local.exists():
            return str(local)
        # 2. Bundled with this installer — copy it across, no network needed
        bundled = self._source_dir() / "nssm.exe"
        if bundled.exists():
            shutil.copy2(bundled, local)
            return str(local)
        # 3. On PATH (developer machine etc.)
        nssm = shutil.which("nssm")
        if nssm:
            return nssm
        # 4. Last resort: fetch from nssm.cc (with timeout)
        self._set_status(tr("installer.downloading_nssm"))
        try:
            arch = "win64" if platform.machine() in ("AMD64", "x86_64") else "win32"
            with tempfile.TemporaryDirectory() as tmp:
                zip_path = os.path.join(tmp, "nssm.zip")
                self._download(NSSM_URL, zip_path, timeout=30.0)
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extract(f"{NSSM_ZIP_NAME}/{arch}/nssm.exe", tmp)
                shutil.copy2(
                    os.path.join(tmp, NSSM_ZIP_NAME, arch, "nssm.exe"),
                    str(local),
                )
            return str(local)
        except Exception as e:
            self._set_status(f"{tr('installer.nssm_failed')}: {e}")
            return None

    # ── Ollama ────────────────────────────────────────────────────────────────

    def _find_or_install_ollama(self) -> str | None:
        # 1. Already on PATH
        ollama = shutil.which("ollama")
        if ollama:
            return ollama
        # 2. Known default install location
        known = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe"
        if known.exists():
            return str(known)
        # 3. Prompt user
        if not messagebox.askyesno(
            tr("installer.msg_ollama_title"),
            tr("installer.msg_ollama_body"),
        ):
            return None
        # 4. Download and run silent installer
        self._set_status(tr("installer.downloading_ollama"))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                setup_path = os.path.join(tmp, "OllamaSetup.exe")
                self._download(OLLAMA_INSTALLER_URL, setup_path, timeout=120.0)
                self._set_status(tr("installer.installing_ollama"))
                subprocess.run(
                    [setup_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                    check=True,
                )
            if known.exists():
                return str(known)
            return shutil.which("ollama")
        except Exception as e:
            self._set_status(f"{tr('installer.ollama_failed')}: {e}")
            messagebox.showwarning(tr("installer.msg_ollama_fail_title"), str(e))
            return None

    def _model_is_pulled(self, ollama: str, model: str) -> bool:
        result = subprocess.run([ollama, "list"], capture_output=True, text=True)
        return model.split(":")[0] in result.stdout

    # ── install ───────────────────────────────────────────────────────────────

    def _install(self):
        if not self._is_admin():
            messagebox.showerror(tr("installer.msg_admin_title"), tr("installer.msg_admin_body"))
            return
        try:
            src = self._source_dir()

            # 0. stop any prior PMS services so their nssm.exe / pms_*.exe handles are released
            self._set_status(tr("installer.stopping_svc"), 2)
            self._stop_existing_services()

            # 1. prepare directory — preserve existing config.yaml
            self._set_status(tr("installer.preparing_dir"), 5)
            if INSTALL_DIR.exists():
                for item in INSTALL_DIR.iterdir():
                    if item.name == "config.yaml":
                        continue
                    shutil.rmtree(item) if item.is_dir() else item.unlink()
            else:
                INSTALL_DIR.mkdir(parents=True)

            # 2. copy executables
            self._set_status(tr("installer.copying_files"), 20)
            for fname in [APP_SERVER_EXE, APP_EDITOR_EXE, APP_MANAGER_EXE]:
                s = src / fname
                if s.exists():
                    shutil.copy2(s, INSTALL_DIR / fname)
                else:
                    raise FileNotFoundError(f"{fname} not found in installer package.")

            config_dst = INSTALL_DIR / "config.yaml"
            if not config_dst.exists():
                config_src = src / "config.yaml"
                if config_src.exists():
                    shutil.copy2(config_src, config_dst)

            # 2.5 add INSTALL_DIR to the user's PATH so pms_manager / pms_server
            #     can be invoked from any shell. Idempotent on reinstall.
            self._set_status(tr("installer.adding_path"), 30)
            self._add_to_user_path(str(INSTALL_DIR))

            # 3. install Windows service
            self._set_status(tr("installer.installing_svc"), 40)
            svc_ok = self._install_service()
            if not svc_ok:
                messagebox.showwarning(tr("installer.msg_svc_title"), tr("installer.msg_svc_body"))

            # 4. pull Ollama models
            if self.ollama_var.get():
                self._pull_ollama_models()

            # 5. desktop shortcut
            if self.shortcut_var.get():
                self._set_status(tr("installer.creating_shortcut"), 90)
                self._create_shortcut()

            self._set_status(tr("installer.complete"), 100)
            messagebox.showinfo(
                tr("installer.msg_complete_title"),
                f"{BRIEF} has been installed to:\n{INSTALL_DIR}\n\n"
                + (f"{tr('installer.svc_running')}\n\n" if svc_ok
                   else f"{tr('installer.svc_not_installed')}\n\n")
                + tr("installer.path_notice"),
            )

            if self.launch_var.get():
                os.startfile(str(INSTALL_DIR / APP_EDITOR_EXE))

            self.root.after(0, self._refresh_ui)

        except Exception as e:
            messagebox.showerror(tr("installer.msg_install_error"), str(e))
            self._set_status(tr("installer.failed"), 0)

    _LEGACY_SERVICE_NAME = "pms_api"  # pre-rename service name; uninstall on upgrade

    def _stop_existing_services(self):
        """Stop and unregister any prior PMS services (current + legacy names) using
        built-in Windows tools, so their executables are unlocked before we replace files.
        Uses net/sc rather than NSSM because NSSM may not be available yet on first install."""
        for svc in (APP_SERVER, self._LEGACY_SERVICE_NAME):
            subprocess.run(["net", "stop",   svc], capture_output=True)
            subprocess.run(["sc",  "delete", svc], capture_output=True)

    # ── User PATH ────────────────────────────────────────────────────────────
    #
    # The install dir lives at %APPDATA%\pms, which is per-user, so the entry
    # belongs in the user PATH (HKCU\Environment\Path) — not system PATH.
    # We preserve the original value type (REG_SZ vs REG_EXPAND_SZ) and
    # broadcast WM_SETTINGCHANGE so new shells pick it up without a logoff.

    @staticmethod
    def _read_user_path() -> tuple[str, int]:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as key:
            try:
                value, kind = winreg.QueryValueEx(key, "Path")
                return value, kind
            except FileNotFoundError:
                return "", winreg.REG_EXPAND_SZ

    @staticmethod
    def _write_user_path(value: str, kind: int) -> None:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "Path", 0, kind, value)
        # Notify running shells / explorer that the environment changed.
        HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
            SMTO_ABORTIFHUNG, 5000, ctypes.byref(ctypes.c_ulong()),
        )

    def _add_to_user_path(self, directory: str) -> bool:
        """Append `directory` to user PATH if not already present. Returns True if added."""
        try:
            value, kind = self._read_user_path()
            entries = [p for p in value.split(";") if p]
            target = os.path.normcase(os.path.normpath(directory))
            if any(os.path.normcase(os.path.normpath(p)) == target for p in entries):
                return False
            entries.append(directory)
            self._write_user_path(";".join(entries), kind)
            return True
        except Exception:
            return False

    def _remove_from_user_path(self, directory: str) -> None:
        try:
            value, kind = self._read_user_path()
            target = os.path.normcase(os.path.normpath(directory))
            entries = [p for p in value.split(";")
                       if p and os.path.normcase(os.path.normpath(p)) != target]
            self._write_user_path(";".join(entries), kind)
        except Exception:
            pass

    def _install_service(self):
        nssm = self._find_or_install_nssm()
        if not nssm:
            return False
        server_exe = str(INSTALL_DIR / APP_SERVER_EXE)
        svc = APP_SERVER
        try:
            subprocess.run([nssm, "install", svc, server_exe],        check=True, capture_output=True)
            subprocess.run([nssm, "set", svc, "AppDirectory",  str(INSTALL_DIR)],           check=True, capture_output=True)
            subprocess.run([nssm, "set", svc, "Description",   BRIEF],                      check=True, capture_output=True)
            subprocess.run([nssm, "set", svc, "Start",         "SERVICE_AUTO_START"],        check=True, capture_output=True)
            subprocess.run([nssm, "set", svc, "AppStdout",     str(INSTALL_DIR/"pms_server.log")],     check=True, capture_output=True)
            subprocess.run([nssm, "set", svc, "AppStderr",     str(INSTALL_DIR/"pms_server_err.log")], check=True, capture_output=True)
            subprocess.run(["net", "start",  svc],                    check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _pull_ollama_models(self):
        ollama = self._find_or_install_ollama()
        if not ollama:
            self._set_status(tr("installer.skipping_ollama"), 85)
            return
        total = len(OLLAMA_MODELS)
        for i, model in enumerate(OLLAMA_MODELS):
            pct = 55 + int(30 * i / total)
            if self._model_is_pulled(ollama, model):
                self._set_status(f"{model} {tr('installer.already_present')}", pct)
                continue
            self._set_status(f"{tr('installer.pulling_model')} {model}…", pct)
            subprocess.run([ollama, "pull", model])

    def _create_shortcut(self):
        desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
        sc_path = desktop / APP_DESKTOP_LINK
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortCut(str(sc_path))
        sc.TargetPath = str(INSTALL_DIR / APP_EDITOR_EXE)
        sc.WorkingDirectory = str(INSTALL_DIR)
        sc.Save()

    # ── uninstall ─────────────────────────────────────────────────────────────

    def _uninstall(self):
        if not self._is_admin():
            messagebox.showerror(tr("installer.msg_admin_title"), tr("installer.msg_admin_body"))
            return
        if not messagebox.askyesno(
            tr("installer.msg_uninstall_confirm_title"),
            tr("installer.msg_uninstall_confirm_body").format(app=BRIEF),
        ):
            return
        try:
            self._set_status(tr("installer.uninstalling_svc"), 20)
            self._remove_service()

            self._set_status(tr("installer.removing_path"), 40)
            self._remove_from_user_path(str(INSTALL_DIR))

            self._set_status(tr("installer.removing_shortcut"), 50)
            sc = Path(os.environ["USERPROFILE"]) / "Desktop" / APP_DESKTOP_LINK
            if sc.exists():
                sc.unlink()

            self._set_status(tr("installer.removing_files"), 70)
            if INSTALL_DIR.exists():
                for item in INSTALL_DIR.iterdir():
                    if item.name == "config.yaml":
                        continue
                    shutil.rmtree(item) if item.is_dir() else item.unlink()

            self._set_status(tr("installer.done"), 100)
            messagebox.showinfo(
                tr("installer.msg_uninstalled_title"),
                f"{BRIEF} {tr('installer.msg_uninstalled_body')}\n{INSTALL_DIR}",
            )
            self.root.after(0, self._refresh_ui)

        except Exception as e:
            messagebox.showerror(tr("installer.msg_uninstall_error"), str(e))

    def _remove_service(self):
        nssm = shutil.which("nssm") or str(INSTALL_DIR / "nssm.exe")
        if not Path(nssm).exists():
            return
        for svc in (APP_SERVER, self._LEGACY_SERVICE_NAME):
            subprocess.run(["net",  "stop",   svc],            capture_output=True)
            subprocess.run([nssm,   "remove", svc, "confirm"], capture_output=True)

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    PMS_Installer().run()
