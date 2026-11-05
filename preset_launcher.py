import copy
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

import pystray
from PIL import Image, ImageDraw

try:
    import winreg
except ImportError:
    winreg = None

APP_NAME = "PresetLauncher"
BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "presets.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NONE_LABEL = "— ничего —"

BG = "#16171d"
CARD = "#23252e"
CARD_HOVER = "#2e3140"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#9077ff"
TEXT = "#eceff4"
MUTED = "#8b90a0"
DANGER = "#e5534b"
DANGER_HOVER = "#f06a63"
FONT = ("Segoe UI", 10)
FONT_BIG = ("Segoe UI Semibold", 11)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"autostart_preset": "", "presets": []}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def run_preset(preset):
    for app in preset.get("apps", []):
        path = app.get("path", "")
        if os.path.exists(path):
            subprocess.Popen(f'"{path}" {app.get("args", "")}', cwd=os.path.dirname(path))
        time.sleep(float(app.get("delay", 0)))


def autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --autostart'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pythonw}" "{os.path.abspath(__file__)}" --autostart'


def is_autostart_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def apply_theme(root):
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=TEXT, font=FONT, bordercolor=BG,
                    lightcolor=BG, darkcolor=BG)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 18))
    style.configure("TButton", background=CARD, foreground=TEXT, borderwidth=0,
                    focusthickness=0, padding=(14, 9))
    style.map("TButton", background=[("active", CARD_HOVER)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", font=FONT_BIG)
    style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])
    style.configure("Danger.TButton", background=DANGER, foreground="#ffffff")
    style.map("Danger.TButton", background=[("active", DANGER_HOVER)])
    style.configure("TCheckbutton", background=BG, foreground=TEXT)
    style.map("TCheckbutton", background=[("active", BG)], indicatorcolor=[("selected", ACCENT)])
    style.configure("TEntry", fieldbackground=CARD, foreground=TEXT, insertcolor=TEXT,
                    borderwidth=0, padding=7)
    style.configure("TCombobox", fieldbackground=CARD, foreground=TEXT, background=CARD,
                    arrowcolor=TEXT, borderwidth=0, padding=7)
    style.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)


def make_listbox(parent, **kw):
    return tk.Listbox(parent, bg=CARD, fg=TEXT, selectbackground=ACCENT, selectforeground="#ffffff",
                      highlightthickness=0, borderwidth=0, relief="flat", activestyle="none",
                      font=FONT_BIG, **kw)


class PresetDialog(tk.Toplevel):
    def __init__(self, master, preset=None):
        super().__init__(master, bg=BG)
        self.title("Пресет")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        self.preset = copy.deepcopy(preset) if preset else {"name": "", "apps": []}

        top = ttk.Frame(self, padding=(20, 20, 20, 10))
        top.pack(fill="x")
        ttk.Label(top, text="Название").pack(anchor="w")
        self.name_var = tk.StringVar(value=self.preset["name"])
        ttk.Entry(top, textvariable=self.name_var).pack(fill="x", pady=(4, 0))

        mid = ttk.Frame(self, padding=(20, 6))
        mid.pack(fill="both", expand=True)
        self.listbox = make_listbox(mid, width=46, height=10)
        self.listbox.pack(side="left", fill="both", expand=True)

        side = ttk.Frame(mid, padding=(12, 0, 0, 0))
        side.pack(side="right", fill="y")
        for text, cmd in [
            ("➕ Добавить .exe", self.add_app),
            ("⌨ Аргументы", self.edit_args),
            ("⏱ Задержка", self.edit_delay),
            ("🗑 Удалить", self.remove_app),
            ("▲ Вверх", lambda: self.move(-1)),
            ("▼ Вниз", lambda: self.move(1)),
        ]:
            ttk.Button(side, text=text, command=cmd, width=16).pack(pady=3)

        bottom = ttk.Frame(self, padding=20)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Сохранить", style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(bottom, text="Отмена", command=self.destroy).pack(side="right", padx=8)

        self.refresh()
        self.grab_set()
        self.wait_window()

    def refresh(self):
        self.listbox.delete(0, "end")
        for a in self.preset["apps"]:
            self.listbox.insert("end", f'{os.path.basename(a["path"])}   {a["args"]}   ⏱ {a["delay"]} с')

    def current(self):
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def add_app(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Программы", "*.exe"), ("Все файлы", "*.*")])
        if path:
            self.preset["apps"].append({"path": path, "args": "", "delay": 0})
            self.refresh()

    def edit_args(self):
        i = self.current()
        if i is None:
            return
        app = self.preset["apps"][i]
        val = simpledialog.askstring("Аргументы", "Аргументы командной строки:", initialvalue=app["args"], parent=self)
        if val is not None:
            app["args"] = val.strip()
            self.refresh()

    def edit_delay(self):
        i = self.current()
        if i is None:
            return
        app = self.preset["apps"][i]
        val = simpledialog.askfloat("Задержка", "Пауза после запуска (сек):", initialvalue=app["delay"], minvalue=0, parent=self)
        if val is not None:
            app["delay"] = val
            self.refresh()

    def remove_app(self):
        i = self.current()
        if i is not None:
            del self.preset["apps"][i]
            self.refresh()

    def move(self, d):
        i = self.current()
        if i is None:
            return
        j = i + d
        if 0 <= j < len(self.preset["apps"]):
            apps = self.preset["apps"]
            apps[i], apps[j] = apps[j], apps[i]
            self.refresh()
            self.listbox.selection_set(j)

    def save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Ошибка", "Введи название пресета", parent=self)
            return
        if name == NONE_LABEL:
            messagebox.showwarning("Ошибка", "Это имя зарезервировано", parent=self)
            return
        if not self.preset["apps"]:
            messagebox.showwarning("Ошибка", "Добавь хотя бы одну программу", parent=self)
            return
        self.preset["name"] = name
        self.result = self.preset
        self.destroy()


class ManagerWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app, bg=BG)
        self.app = app
        self.title("Управление пресетами")
        self.geometry("560x480")
        self.transient(app)

        ttk.Label(self, text="Пресеты", style="Title.TLabel").pack(anchor="w", padx=24, pady=(20, 10))

        mid = ttk.Frame(self, padding=(24, 0))
        mid.pack(fill="both", expand=True)
        self.listbox = make_listbox(mid, width=30, height=10)
        self.listbox.pack(side="left", fill="both", expand=True)

        side = ttk.Frame(mid, padding=(12, 0, 0, 0))
        side.pack(side="right", fill="y")
        ttk.Button(side, text="➕ Новый", command=self.add, width=16).pack(pady=3)
        ttk.Button(side, text="✏ Изменить", command=self.edit, width=16).pack(pady=3)
        ttk.Button(side, text="🗑 Удалить", style="Danger.TButton", command=self.delete, width=16).pack(pady=3)

        bottom = ttk.Frame(self, padding=24)
        bottom.pack(fill="x")
        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        ttk.Checkbutton(bottom, text="Запускать с Windows", variable=self.autostart_var,
                        command=self.toggle_autostart).pack(anchor="w")
        ttk.Label(bottom, text="Пресет при входе в Windows", style="Muted.TLabel").pack(anchor="w", pady=(12, 4))
        self.auto_box = ttk.Combobox(bottom, state="readonly")
        self.auto_box.pack(fill="x")
        self.auto_box.bind("<<ComboboxSelected>>", self.set_auto_preset)

        self.refresh()

    def refresh(self):
        self.listbox.delete(0, "end")
        for p in self.app.cfg["presets"]:
            self.listbox.insert("end", p["name"])
        self.auto_box["values"] = [NONE_LABEL] + self.app.preset_names()
        self.auto_box.set(self.app.cfg.get("autostart_preset") or NONE_LABEL)

    def current(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("Пресеты", "Выбери пресет в списке", parent=self)
            return None
        return sel[0]

    def add(self):
        dlg = PresetDialog(self)
        if dlg.result:
            self.app.cfg["presets"].append(dlg.result)
            self.app.save()
            self.refresh()

    def edit(self):
        idx = self.current()
        if idx is None:
            return
        cfg = self.app.cfg
        old = cfg["presets"][idx]
        dlg = PresetDialog(self, old)
        if dlg.result:
            if cfg.get("autostart_preset") == old["name"]:
                cfg["autostart_preset"] = dlg.result["name"]
            cfg["presets"][idx] = dlg.result
            self.app.save()
            self.refresh()

    def delete(self):
        idx = self.current()
        if idx is None:
            return
        cfg = self.app.cfg
        name = cfg["presets"][idx]["name"]
        if messagebox.askyesno("Удалить", f"Удалить пресет «{name}»?", parent=self):
            del cfg["presets"][idx]
            if cfg.get("autostart_preset") == name:
                cfg["autostart_preset"] = ""
            self.app.save()
            self.refresh()

    def set_auto_preset(self, _=None):
        val = self.auto_box.get()
        self.app.cfg["autostart_preset"] = "" if val == NONE_LABEL else val
        self.app.save()

    def toggle_autostart(self):
        try:
            set_autostart(self.autostart_var.get())
        except OSError as e:
            messagebox.showerror("Ошибка", str(e), parent=self)
            self.autostart_var.set(is_autostart_enabled())


def make_tray_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=ACCENT)
    d.polygon([(24, 18), (24, 46), (48, 32)], fill="#ffffff")
    return img


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Preset Launcher")
        self.geometry("400x520")
        self.resizable(False, False)
        apply_theme(self)
        self.cfg = load_config()
        self.manager = None
        self.events = queue.Queue()
        self.protocol("WM_DELETE_WINDOW", self.hide)

        self.tray = pystray.Icon(APP_NAME, make_tray_image(), "Preset Launcher", pystray.Menu(
            pystray.MenuItem("Открыть", lambda icon, item: self.events.put("show"), default=True),
            pystray.MenuItem("Выход", lambda icon, item: self.events.put("quit")),
        ))
        threading.Thread(target=self.tray.run, daemon=True).start()
        self.after(100, self.poll_events)

        ttk.Label(self, text="Preset Launcher", style="Title.TLabel").pack(pady=(28, 2))
        ttk.Label(self, text="Выбери, что запустить", style="Muted.TLabel").pack(pady=(0, 18))

        self.buttons = ttk.Frame(self)
        self.buttons.pack(fill="both", expand=True, padx=30)

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=30, pady=22)
        ttk.Button(footer, text="⚙  Управление пресетами", command=self.open_manager).pack(fill="x")

        self.render_buttons()

    def preset_names(self):
        return [p["name"] for p in self.cfg["presets"]]

    def render_buttons(self):
        for w in self.buttons.winfo_children():
            w.destroy()
        ttk.Button(self.buttons, text="⏹  Ничего (none)", command=self.hide).pack(fill="x", pady=4)
        autostart = self.cfg.get("autostart_preset")
        for p in self.cfg["presets"]:
            label = f"▶  {p['name']}" + ("   ⭐ автозапуск" if p["name"] == autostart else "")
            ttk.Button(self.buttons, text=label, command=lambda p=p: self.launch(p)).pack(fill="x", pady=4)

    def save(self):
        save_config(self.cfg)
        self.render_buttons()
        if self.manager and self.manager.winfo_exists():
            self.manager.refresh()

    def open_manager(self):
        if self.manager and self.manager.winfo_exists():
            self.manager.lift()
            return
        self.manager = ManagerWindow(self)

    def launch(self, preset):
        missing = [a["path"] for a in preset["apps"] if not os.path.exists(a["path"])]
        if missing:
            messagebox.showerror("Не найдено", "Не найдены файлы:\n" + "\n".join(missing))
            return
        threading.Thread(target=run_preset, args=(preset,), daemon=True).start()
        self.hide()

    def hide(self):
        self.withdraw()

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event == "show":
                    self.show()
                elif event == "quit":
                    self.tray.stop()
                    self.destroy()
                    return
        except queue.Empty:
            pass
        self.after(100, self.poll_events)


if __name__ == "__main__":
    if "--autostart" in sys.argv:
        cfg = load_config()
        preset = next((p for p in cfg["presets"] if p["name"] == cfg.get("autostart_preset")), None)
        if preset:
            run_preset(preset)
    else:
        App().mainloop()
