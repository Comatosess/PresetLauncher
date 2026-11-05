import base64
import ctypes
import os
import re
import socket
import subprocess
import sys
import json
import threading
import time
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path

import psutil

from PySide6.QtCore import (
    Qt, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QTimer, Property, Signal,
    QFileInfo, QSize, QPoint, QPointF, QRectF, QAbstractNativeEventFilter,
)
from PySide6.QtGui import QIcon, QColor, QPainter, QPen, QFont, QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QLineEdit, QAbstractButton,
    QDoubleSpinBox, QCheckBox, QComboBox, QScrollArea, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QSystemTrayIcon, QMenu, QGraphicsDropShadowEffect, QStyle,
    QDialog, QListWidget, QListWidgetItem, QFileIconProvider, QGraphicsOpacityEffect,
    QGridLayout, QInputDialog,
)

FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent
CONFIG = APP_DIR / "presets.json"
RES = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ICON = RES / "icon.ico"
ICON_CACHE = APP_DIR / "icon_cache"
URL_RE = re.compile(r"https?://[^\s\"']+", re.I)
BROWSERS = {"chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "firefox.exe"}

QSS = """
QWidget { color: #e6e6ee; font-family: "Montserrat", "Segoe UI"; font-size: 12px; font-weight: 500; }
QFrame#root { background: #0c0c10; border: 1px solid #1f1f28; border-radius: 16px; }
QLabel#title { font-size: 15px; font-weight: 700; color: #ffffff; }
QLabel#muted { color: #5e5e6b; font-size: 10px; font-weight: 700; }
QLabel#status { color: #9d86ff; font-size: 11px; font-weight: 600; }
QFrame#editor { background: #101015; border: 1px solid #1c1c25; border-radius: 14px; }
QFrame#row { background: #16161d; border: 1px solid #22222c; border-radius: 10px; }
QFrame#row[lifted="true"] { background: #1c1a2b; border: 1px solid #7c5cff; }
QFrame#argsfield { background: #17171f; border: 1px solid #25252f; border-radius: 8px; }
QFrame#argsfield[open="true"] { border: 1px solid #7c5cff; }
QFrame#argsfield QLineEdit { background: transparent; border: none; }
QFrame#popup { background: #111117; border: 1px solid #2a2a36; border-radius: 12px; }
QDoubleSpinBox { padding-right: 22px; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { subcontrol-origin: border; width: 18px; border: none; background: transparent; }
QDoubleSpinBox::up-button { subcontrol-position: top right; margin: 4px 4px 0 0; }
QDoubleSpinBox::down-button { subcontrol-position: bottom right; margin: 0 4px 4px 0; }
QDoubleSpinBox::up-arrow { width: 0px; height: 0px; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 5px solid #5e5e6b; }
QDoubleSpinBox::down-arrow { width: 0px; height: 0px; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #5e5e6b; }
QDoubleSpinBox::up-arrow:hover { border-bottom-color: #b9a8ff; }
QDoubleSpinBox::down-arrow:hover { border-top-color: #b9a8ff; }
QLineEdit, QDoubleSpinBox, QComboBox {
    background: #17171f; border: 1px solid #25252f; border-radius: 8px; padding: 6px 10px;
    selection-background-color: #7c5cff;
}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #7c5cff; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { width: 0px; height: 0px; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #9a9aa8; margin-right: 8px; }
QComboBox QAbstractItemView { background: #111117; border: 1px solid #25252f; selection-background-color: #7c5cff; outline: none; }
QPushButton { background: #1a1a22; border: 1px solid #272732; border-radius: 9px; padding: 7px 14px; font-weight: 600; }
QPushButton:hover { background: #23232e; border-color: #3a3a4a; }
QPushButton:pressed { background: #15151b; }
QPushButton:disabled { color: #44444f; }
QPushButton#ghost { background: transparent; border: none; color: #7a7a88; padding: 0px; font-size: 14px; }
QPushButton#ghost:hover { color: #ffffff; background: #1c1c26; }
QPushButton#close:hover { color: #ff6b81; background: #2a1820; }
QPushButton#accent { background: #7c5cff; border: none; color: #ffffff; font-weight: 700; padding: 8px 18px; }
QPushButton#accent:hover { background: #9078ff; }
QPushButton#danger:hover { background: #2a1820; border-color: #5a2a36; color: #ff6b81; }
QCheckBox { spacing: 8px; color: #9a9aa8; }
QCheckBox::indicator { width: 15px; height: 15px; border-radius: 4px; border: 1px solid #3a3a48; background: #17171f; }
QCheckBox::indicator:checked { background: #7c5cff; border-color: #7c5cff; }
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 2px; }
QScrollBar::handle:vertical { background: #2a2a36; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #3a3a4a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QMenu { background: #111117; border: 1px solid #25252f; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 18px; border-radius: 6px; }
QMenu::item:selected { background: #7c5cff; color: #ffffff; }
QMenu::separator { height: 1px; background: #25252f; margin: 4px 8px; }
QMessageBox { background: #0c0c10; }
QMessageBox QLabel { color: #e6e6ee; }
"""


def load_config():
    data = {}
    if CONFIG.exists():
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.setdefault("presets", [])
    data.setdefault("autostart_preset", "")
    data.setdefault("start_hidden", False)
    data.setdefault("hide_after_launch", False)
    data.setdefault("folders", [])
    if "categories" not in data:
        data["categories"] = DEFAULT_CATEGORIES
        save_config(data)
    return data


def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def app_icon():
    return QIcon(str(ICON)) if ICON.exists() else QIcon()


SINGLE_PORT = 47821


def notify_running():
    try:
        with socket.create_connection(("127.0.0.1", SINGLE_PORT), timeout=0.4) as s:
            s.sendall(b"show")
        return True
    except OSError:
        return False


def serve_single(win):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", SINGLE_PORT))
        srv.listen(5)
    except OSError:
        return
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        try:
            conn.recv(64)
            win.show_requested.emit()
        except Exception:
            pass
        finally:
            conn.close()


WM_HOTKEY = 0x0312
HOTKEY_ID = 1
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
VK_P = 0x50


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.callback()
        return False, 0


def mix(c1, c2, t):
    a, b = c1.getRgb(), c2.getRgb()
    return QColor(*(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))


ARG_HINTS = {
    "chrome.exe": [
        ("--incognito", "приватная вкладка"),
        ("--new-window", "новое окно"),
        ("--start-maximized", "сразу на весь экран"),
        ("--start-fullscreen", "полноэкранный режим"),
        ("--disable-extensions", "без расширений"),
    ],
    "msedge.exe": [
        ("--inprivate", "приватное окно"),
        ("--new-window", "новое окно"),
        ("--start-maximized", "сразу на весь экран"),
        ("--start-fullscreen", "полноэкранный режим"),
    ],
    "brave.exe": [
        ("--incognito", "приватная вкладка"),
        ("--new-window", "новое окно"),
        ("--start-maximized", "сразу на весь экран"),
    ],
    "firefox.exe": [
        ("-private-window", "приватное окно"),
        ("-new-window", "новое окно"),
    ],
    "discord.exe": [
        ("--start-minimized", "запуск свёрнутым"),
    ],
    "steam.exe": [
        ("-silent", "запуск без окна"),
        ("-bigpicture", "режим Big Picture"),
        ("-console", "открыть консоль"),
    ],
    "telegram.exe": [
        ("-startintray", "запуск в трей"),
    ],
    "obs64.exe": [
        ("--startrecording", "сразу начать запись"),
        ("--startstreaming", "сразу начать стрим"),
        ("--startreplaybuffer", "сразу включить буфер повтора"),
        ("--minimize-to-tray", "сворачивать в трей"),
    ],
}


DEFAULT_CATEGORIES = {
    "Игры": ["osu!.exe", "steam.exe", "epicgameslauncher.exe", "minecraft launcher.exe"],
    "Браузеры": ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"],
    "Мессенджеры": ["discord.exe", "telegram.exe", "whatsapp.exe", "slack.exe", "teams.exe"],
    "Стрим": ["obs64.exe", "obs32.exe", "streamlabs obs.exe"],
    "Музыка": ["aimp.exe", "spotify.exe", "foobar2000.exe"],
    "Работа": ["code.exe", "pycharm64.exe", "winword.exe", "excel.exe", "notion.exe"],
    "Периферия": ["opentabletdriver.ux.wpf.exe"],
}

PS_SCAN = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    "$sh=New-Object -ComObject WScript.Shell;"
    "$dirs=@(\"$env:ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\",\"$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\");"
    "Get-ChildItem -Path $dirs -Recurse -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {"
    "$t=$sh.CreateShortcut($_.FullName).TargetPath; if($t -like '*.exe'){ $_.BaseName + '|' + $t } }"
)

INSTALLED = []
SCANNED = False


def scan_installed():
    global INSTALLED, SCANNED
    encoded = base64.b64encode(PS_SCAN.encode("utf-16le")).decode()
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=120,
        ).stdout
    except Exception:
        out = ""
    seen, items = set(), []
    for line in out.splitlines():
        if "|" not in line:
            continue
        name, path = line.split("|", 1)
        path = path.strip()
        base = os.path.basename(path).lower()
        if path in seen or not os.path.exists(path) or "uninstall" in path.lower() or base.startswith("unins"):
            continue
        seen.add(path)
        items.append({"name": name.strip(), "path": path})
    INSTALLED = items
    SCANNED = True


def build_category_map(cfg):
    m = {}
    for cat, exes in cfg.get("categories", {}).items():
        for exe in exes:
            m[exe.lower()] = cat
    return m


def running_ages():
    ages = {}
    now = time.time()
    for proc in psutil.process_iter(["name", "create_time"]):
        try:
            n = (proc.info["name"] or "").lower()
            if not n:
                continue
            age = now - (proc.info["create_time"] or now)
            ages[n] = max(ages.get(n, 0.0), max(0.0, age))
        except psutil.Error:
            pass
    return ages


def preset_age(apps, ages):
    best = None
    for a in apps:
        n = os.path.basename(a.get("path", "")).lower()
        if n in ages:
            best = ages[n] if best is None else max(best, ages[n])
    return best


def human_age(sec):
    sec = int(sec)
    if sec < 60:
        return f"{sec} с"
    m = sec // 60
    if m < 60:
        return f"{m} мин"
    h = m // 60
    if h < 24:
        return f"{h} ч"
    return f"{h // 24} дн"


def startup_lnk():
    return Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/PresetLauncher.lnk"


STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"


def startup_blocked():
    import winreg
    lnk = startup_lnk()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY) as k:
            try:
                data, _ = winreg.QueryValueEx(k, lnk.name)
            except FileNotFoundError:
                return False
    except Exception:
        return False
    return bool(data) and data[0] != 0x02


def startup_force_enable():
    import winreg
    lnk = startup_lnk()
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, lnk.name, 0, winreg.REG_BINARY, b"\x02" + b"\x00" * 11)
    except Exception:
        pass


def startup_force_disable():
    import winreg
    lnk = startup_lnk()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, lnk.name)
    except Exception:
        pass


def startup_active():
    lnk = startup_lnk()
    return lnk.exists() and not startup_blocked()


def set_startup_lnk(on):
    lnk = startup_lnk()
    try:
        if on:
            cmd = (
                "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
                "$s.TargetPath='%s';$s.WorkingDirectory='%s';$s.IconLocation='%s';$s.Save()"
                % (lnk, sys.executable, APP_DIR, sys.executable)
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, timeout=60,
            )
            startup_force_enable()
        else:
            startup_force_disable()
            if lnk.exists():
                lnk.unlink()
    except Exception:
        pass
    return startup_active()


def file_icon(path, size):
    if path.lower().startswith(("http://", "https://")):
        icon = QApplication.style().standardIcon(QStyle.SP_FileLinkIcon)
    elif os.path.exists(path):
        icon = QFileIconProvider().icon(QFileInfo(path))
    else:
        icon = QApplication.style().standardIcon(QStyle.SP_FileIcon)
    return icon.pixmap(size, size)


def preset_url(p):
    for a in p.get("apps", []):
        path = (a.get("path") or "").strip()
        if path.lower().startswith(("http://", "https://")):
            return path
        if os.path.basename(path).lower() in BROWSERS:
            m = URL_RE.search(a.get("args") or "")
            if m:
                return m.group(0)
    return ""


def fetch_favicon(url):
    host = urllib.parse.urlparse(url).hostname or ""
    if not host:
        return None
    ICON_CACHE.mkdir(exist_ok=True)
    name = re.sub(r"[^\w.-]", "_", host)
    img, none = ICON_CACHE / (name + ".img"), ICON_CACHE / (name + ".none")
    if img.exists():
        pm = QPixmap()
        if pm.loadFromData(img.read_bytes()):
            return pm
    if none.exists():
        return None
    sources = [f"https://www.google.com/s2/favicons?domain={host}&sz=64",
               f"https://{host}/favicon.ico"]
    for src in sources:
        try:
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=4).read()
        except Exception:
            continue
        pm = QPixmap()
        if data and pm.loadFromData(data):
            img.write_bytes(data)
            return pm
    none.touch()
    return None


def preset_pixmap(p, size):
    pm = None
    custom = p.get("icon", "")
    if custom and os.path.exists(custom):
        pm = QPixmap(custom)
    if pm is None or pm.isNull():
        url = preset_url(p)
        pm = fetch_favicon(url) if url else None
    if pm is not None and not pm.isNull():
        return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    first = next((a["path"] for a in p.get("apps", []) if a.get("path")), "")
    return file_icon(first, size)


TILE = 104
PILL_H = 34
GAP = 10
NO_FOLDER = "— без папки —"


def card_at(gpos):
    w = QApplication.widgetAt(gpos)
    while w is not None and not isinstance(w, PresetCard):
        w = w.parentWidget()
    return w


class PresetCard(QFrame):
    clicked = Signal()
    double_clicked = Signal()
    context = Signal(QPoint)
    released_at = Signal(QPoint)

    def __init__(self, title, sub, pixmap=None, active=False, drag=None, target=None, plus=False, small=False):
        super().__init__()
        self.title = title
        self.sub = sub
        self.pixmap = pixmap
        self.plus = plus
        self.small = small
        self.active = active
        self.drag_payload = drag
        self.target = target
        self._hover = False
        self._drop_hover = False
        self._dragging = False
        self._hot = None
        self._ghost = None
        self._ghost_anim = None
        self._src_fx = None
        self._offset = QPoint()
        self._press = QPoint()
        self._dbl = False
        if small:
            self.setFixedSize(TILE, PILL_H)
        else:
            self.setFixedSize(TILE, TILE)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.globalPosition().toPoint()
            self._dragging = False
            self._dbl = False

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.LeftButton) or not self.drag_payload:
            return
        gpos = e.globalPosition().toPoint()
        if not self._dragging:
            if (gpos - self._press).manhattanLength() < QApplication.startDragDistance():
                return
            self._begin_drag(gpos)
        self._ghost.move(self.window().mapFromGlobal(gpos - self._offset))
        over = card_at(gpos)
        if over is self or (over is not None and over.target is None):
            over = None
        if over is not self._hot:
            if self._hot is not None:
                self._hot._drop_hover = False
                self._hot.update()
            self._hot = over
            if over is not None:
                over._drop_hover = True
                over.update()

    def _begin_drag(self, gpos):
        self._dragging = True
        self._offset = self._press - self.mapToGlobal(QPoint(0, 0))
        ghost = QLabel(self.window())
        ghost.setAttribute(Qt.WA_TransparentForMouseEvents)
        ghost.setFixedSize(self.size())
        ghost.setPixmap(self.grab())
        fx = QGraphicsOpacityEffect(ghost)
        fx.setOpacity(0.0)
        ghost.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity", ghost)
        anim.setDuration(160)
        anim.setStartValue(0.0)
        anim.setEndValue(0.9)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._ghost_anim = anim
        self._ghost = ghost
        ghost.move(self.window().mapFromGlobal(gpos - self._offset))
        ghost.show()
        ghost.raise_()
        self._src_fx = QGraphicsOpacityEffect(self)
        self._src_fx.setOpacity(0.35)
        self.setGraphicsEffect(self._src_fx)
        self.setCursor(Qt.ClosedHandCursor)

    def _end_drag(self):
        self._dragging = False
        if self._hot is not None:
            self._hot._drop_hover = False
            self._hot.update()
            self._hot = None
        if self._ghost is not None:
            self._ghost.deleteLater()
            self._ghost = None
        self.setGraphicsEffect(None)
        self._src_fx = None
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        if self._dragging:
            self._end_drag()
            self.released_at.emit(e.globalPosition().toPoint())
        elif self.rect().contains(e.position().toPoint()):
            if self._dbl:
                self.double_clicked.emit()
            else:
                self.clicked.emit()
        self._dbl = False

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dbl = True

    def contextMenuEvent(self, e):
        self.context.emit(e.globalPos())

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        base = QColor("#1a1a26") if self.active else QColor("#121217")
        if self._drop_hover:
            border, width = QColor("#b9a8ff"), 2
        elif self.active:
            border, width = QColor("#7c5cff"), 1.4
        else:
            border, width = QColor("#22222c"), 1
        p.setPen(QPen(border, width))
        p.setBrush(mix(base, QColor("#1f1f2a"), 1.0 if self._hover else 0.0))
        p.drawRoundedRect(r, 14, 14)
        p.setPen(Qt.NoPen)
        if self.plus:
            p.setPen(QPen(QColor("#b9a8ff") if self._hover else QColor("#8b8b9a"), 2.2, Qt.SolidLine, Qt.RoundCap))
            c = r.center()
            p.drawLine(QPointF(c.x() - 10, c.y()), QPointF(c.x() + 10, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - 10), QPointF(c.x(), c.y() + 10))
            p.end()
            return
        if self.small:
            pill = QRectF(self.rect()).adjusted(3, 3, -3, -3)
            p.setPen(QPen(QColor("#7c5cff") if self.active else QColor("#22222c"), 1.4 if self.active else 1))
            p.setBrush(mix(QColor("#121217"), QColor("#1f1f2a"), 1.0 if self._hover else 0.0))
            p.drawRoundedRect(pill, 10, 10)
            if self._drop_hover:
                p.setPen(QPen(QColor("#b9a8ff"), 2))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(pill, 10, 10)
            p.setPen(QPen(QColor("#b9a8ff") if self._hover else QColor("#8b8b9a"), 2, Qt.SolidLine, Qt.RoundCap))
            if self.plus:
                c = pill.center()
                p.drawLine(QPointF(c.x() - 7, c.y()), QPointF(c.x() + 7, c.y()))
                p.drawLine(QPointF(c.x(), c.y() - 7), QPointF(c.x(), c.y() + 7))
            else:
                f = p.font()
                f.setPointSize(8)
                f.setBold(True)
                p.setFont(f)
                p.setPen(QColor("#f2f2f7"))
                title = p.fontMetrics().elidedText(self.title, Qt.ElideRight, int(pill.width() - 10))
                p.drawText(pill, Qt.AlignCenter, title)
            p.end()
            return
        if self.pixmap:
            p.drawPixmap(int(r.center().x() - self.pixmap.width() / 2), int(r.top() + 14), self.pixmap)
            title_rect = QRectF(r.left() + 6, r.bottom() - 30, r.width() - 12, 22)
        else:
            title_rect = QRectF(r.left() + 6, r.center().y() - 11, r.width() - 12, 22)
        f = p.font()
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#f2f2f7"))
        title = p.fontMetrics().elidedText(self.title, Qt.ElideRight, int(r.width() - 12))
        p.drawText(title_rect, Qt.AlignCenter, title)
        p.end()


ACCENT = QColor("#7c5cff")
DANGER = QColor("#ff5c7a")


def repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def with_alpha(c, a):
    c = QColor(c)
    c.setAlpha(max(0, min(255, int(a))))
    return c


class IconButton(QAbstractButton):
    def __init__(self, kind, size=30, danger=False, frame=True):
        super().__init__()
        self.kind = kind
        self.danger = danger
        self.frame = frame
        self._hover = 0.0
        self._rot = 0.0
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.anim = QPropertyAnimation(self, b"hover", self)
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.rot_anim = QPropertyAnimation(self, b"rot", self)
        self.rot_anim.setDuration(260)
        self.rot_anim.setEasingCurve(QEasingCurve.OutBack)

    def getHover(self):
        return self._hover

    def setHover(self, v):
        self._hover = v
        self.update()

    hover = Property(float, getHover, setHover)

    def getRot(self):
        return self._rot

    def setRot(self, v):
        self._rot = v
        self.update()

    rot = Property(float, getRot, setRot)

    def rotate_to(self, angle):
        self.rot_anim.stop()
        self.rot_anim.setStartValue(self._rot)
        self.rot_anim.setEndValue(float(angle))
        self.rot_anim.start()

    def _animate(self, v):
        self.anim.stop()
        self.anim.setStartValue(self._hover)
        self.anim.setEndValue(v)
        self.anim.start()

    def enterEvent(self, e):
        self._animate(1.0)

    def leaveEvent(self, e):
        self._animate(0.0)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self._hover if self.isEnabled() else 0.0
        accent = DANGER if self.danger else ACCENT
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.frame:
            p.setPen(QPen(mix(QColor("#272732"), accent, h * 0.8), 1))
            p.setBrush(mix(QColor("#1a1a22"), mix(QColor("#1a1a22"), accent, 0.25), h))
            p.drawRoundedRect(r, 9, 9)
        elif h > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(with_alpha(accent, 45 * h))
            p.drawRoundedRect(r, 8, 8)
        hot = QColor("#ff8197") if self.danger else QColor("#ffffff")
        col = mix(QColor("#8a8a98"), hot, h) if self.isEnabled() else QColor("#44444f")
        p.translate(self.width() / 2, self.height() / 2)
        if self.isDown():
            p.scale(0.85, 0.85)
        p.setPen(QPen(col, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        u = 4.5
        k = self.kind
        if k == "close":
            p.rotate(90 * h)
            p.drawLine(QPointF(-u, -u), QPointF(u, u))
            p.drawLine(QPointF(-u, u), QPointF(u, -u))
        elif k == "min":
            p.drawLine(QPointF(-u, 0), QPointF(u, 0))
        elif k in ("up", "down"):
            d = -1 if k == "up" else 1
            p.translate(0, 1.5 * h * d)
            p.drawPolyline([QPointF(-u, -u / 2 * d), QPointF(0, u / 2 * d), QPointF(u, -u / 2 * d)])
        elif k == "chevron":
            p.rotate(self._rot)
            p.drawPolyline([QPointF(-4, -2), QPointF(0, 2), QPointF(4, -2)])
        elif k == "copy":
            p.drawRoundedRect(QRectF(-2.5, -6, 7.5, 8.5), 2, 2)
            p.drawRoundedRect(QRectF(-5.5, -2.5, 7.5, 8.5), 2, 2)
        elif k == "folder":
            p.translate(0, -1.2 * h)
            p.drawPolyline([
                QPointF(-6, -4), QPointF(-2, -4), QPointF(-0.5, -2.5), QPointF(6, -2.5),
                QPointF(6, 4.5), QPointF(-6, 4.5), QPointF(-6, -4),
            ])
        p.end()


class Grip(QWidget):
    def __init__(self, row):
        super().__init__()
        self.row = row
        self._hover = 0.0
        self.setFixedSize(16, 28)
        self.setCursor(Qt.OpenHandCursor)
        self.anim = QPropertyAnimation(self, b"hover", self)
        self.anim.setDuration(200)

    def getHover(self):
        return self._hover

    def setHover(self, v):
        self._hover = v
        self.update()

    hover = Property(float, getHover, setHover)

    def _animate(self, v):
        self.anim.stop()
        self.anim.setStartValue(self._hover)
        self.anim.setEndValue(v)
        self.anim.start()

    def enterEvent(self, e):
        self._animate(1.0)

    def leaveEvent(self, e):
        self._animate(0.0)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.row.host:
            self.setCursor(Qt.ClosedHandCursor)
            self.row.host.begin_drag(self.row, e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self.row.host:
            self.row.host.drag_to(e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):
        self.setCursor(Qt.OpenHandCursor)
        if self.row.host:
            self.row.host.end_drag()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(mix(QColor("#4a4a58"), QColor("#b9a8ff"), self._hover))
        cx, cy = self.width() / 2, self.height() / 2
        for dx in (-3, 3):
            for dy in (-6, 0, 6):
                p.drawEllipse(QPointF(cx + dx, cy + dy), 1.6, 1.6)
        p.end()


class AppList(QWidget):
    GAP = 8

    def __init__(self):
        super().__init__()
        self.rows = []
        self.drag_row = None
        self.drag_off = 0
        self.scroll = None
        self.on_reorder = None
        self._order0 = []

    def _layout_ys(self, order):
        ys, y = [], 0
        for r in order:
            ys.append(y)
            y += r.sizeHint().height() + self.GAP
        return ys, max(0, y - self.GAP)

    def slide(self, row, target):
        anim = getattr(row, "slide_anim", None)
        if anim is None:
            anim = row.slide_anim = QPropertyAnimation(row, b"pos", row)
            anim.setDuration(240)
            anim.setEasingCurve(QEasingCurve.OutCubic)
        if anim.state() == QPropertyAnimation.Running and anim.endValue() == target:
            return
        anim.stop()
        if row.pos() == target:
            return
        anim.setStartValue(row.pos())
        anim.setEndValue(target)
        anim.start()

    def relayout(self, animate=True):
        ys, total = self._layout_ys(self.rows)
        self.setMinimumHeight(total)
        w = self.width() - 6
        for r, y in zip(self.rows, ys):
            r.target_y = y
            r.resize(w, r.sizeHint().height())
            if r is self.drag_row:
                continue
            target = QPoint(0, y)
            if animate and getattr(r, "placed", False):
                self.slide(r, target)
            else:
                r.move(target)
                r.placed = True

    def resizeEvent(self, e):
        for r in self.rows:
            r.resize(self.width() - 6, r.height())

    def add(self, row):
        row.host = self
        row.setParent(self)
        self.rows.append(row)
        row.show()
        self.relayout()
        fx = QGraphicsOpacityEffect(row)
        row.setGraphicsEffect(fx)
        a = QPropertyAnimation(fx, b"opacity", row)
        a.setDuration(260)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.finished.connect(lambda: row.setGraphicsEffect(None))
        a.start()

    def insert_after(self, row, new):
        self.rows.remove(new)
        self.rows.insert(self.rows.index(row) + 1, new)
        self.relayout()

    def remove(self, row):
        if row not in self.rows:
            return
        self.rows.remove(row)
        row.host = None
        row.lower()
        row.setEnabled(False)
        fx = QGraphicsOpacityEffect(row)
        row.setGraphicsEffect(fx)
        group = QParallelAnimationGroup(row)
        fade = QPropertyAnimation(fx, b"opacity")
        fade.setDuration(180)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        shift = QPropertyAnimation(row, b"pos")
        shift.setDuration(180)
        shift.setEndValue(row.pos() + QPoint(40, 0))
        group.addAnimation(fade)
        group.addAnimation(shift)
        group.finished.connect(row.deleteLater)
        group.start()
        self.relayout()

    def clear(self):
        for r in self.rows:
            r.host = None
            r.setParent(None)
            r.deleteLater()
        self.rows = []
        self.drag_row = None
        self.setMinimumHeight(0)

    def shift(self, row, delta):
        i = self.rows.index(row)
        j = i + delta
        if not 0 <= j < len(self.rows):
            return
        self.rows[i], self.rows[j] = self.rows[j], self.rows[i]
        self.relayout()

    def begin_drag(self, row, gpos):
        self.drag_row = row
        self._order0 = list(self.rows)
        anim = getattr(row, "slide_anim", None)
        if anim:
            anim.stop()
        self.drag_off = gpos.y() - row.mapToGlobal(QPoint(0, 0)).y()
        row.raise_()
        row.set_lifted(True)

    def drag_to(self, gpos):
        row = self.drag_row
        if row is None:
            return
        y = self.mapFromGlobal(gpos).y() - self.drag_off
        y = max(0, min(y, self.height() - row.height()))
        row.move(0, y)
        center = y + row.height() / 2
        rest = [r for r in self.rows if r is not row]
        idx = sum(1 for r in rest if r.target_y + r.height() / 2 < center)
        order = rest[:idx] + [row] + rest[idx:]
        if order != self.rows:
            self.rows = order
            self.relayout()
        if self.scroll:
            self.scroll.ensureVisible(0, int(center), 0, row.height() // 2 + 10)

    def end_drag(self):
        row = self.drag_row
        if row is None:
            return
        self.drag_row = None
        row.set_lifted(False)
        self.relayout()
        if self.on_reorder and self.rows != self._order0:
            self.on_reorder()


class ArgItem(QAbstractButton):
    def __init__(self, desc, arg, checked):
        super().__init__()
        self.desc = desc
        self.arg = arg
        self.setCheckable(True)
        self.setChecked(checked)
        self._hover = 0.0
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.anim = QPropertyAnimation(self, b"hover", self)
        self.anim.setDuration(160)
        self.toggled.connect(lambda *_: self.update())

    def getHover(self):
        return self._hover

    def setHover(self, v):
        self._hover = v
        self.update()

    hover = Property(float, getHover, setHover)

    def _animate(self, v):
        self.anim.stop()
        self.anim.setStartValue(self._hover)
        self.anim.setEndValue(v)
        self.anim.start()

    def enterEvent(self, e):
        self._animate(1.0)

    def leaveEvent(self, e):
        self._animate(0.0)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(Qt.NoPen)
        p.setBrush(with_alpha(ACCENT, 20 + 40 * self._hover if self.isChecked() else 40 * self._hover))
        p.drawRoundedRect(r, 9, 9)
        box = QRectF(r.left() + 10, r.center().y() - 8, 16, 16)
        if self.isChecked():
            p.setBrush(ACCENT)
            p.drawRoundedRect(box, 5, 5)
            p.setPen(QPen(QColor("#ffffff"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            c = box.center()
            p.drawPolyline([QPointF(c.x() - 3.5, c.y()), QPointF(c.x() - 1, c.y() + 2.8), QPointF(c.x() + 4, c.y() - 3)])
        else:
            p.setPen(QPen(mix(QColor("#3a3a48"), ACCENT, self._hover), 1.4))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box, 5, 5)
        f = QFont(self.font())
        f.setPixelSize(12)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor("#f2f2f7"))
        text_r = r.adjusted(36, 0, -10, 0)
        p.drawText(text_r, Qt.AlignLeft | Qt.AlignVCenter, self.desc)
        f.setPixelSize(10)
        f.setWeight(QFont.Medium)
        p.setFont(f)
        tw = p.fontMetrics().horizontalAdvance(self.arg) + 14
        pill = QRectF(r.right() - tw - 8, r.center().y() - 10, tw, 20)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#1e1a33"))
        p.drawRoundedRect(pill, 10, 10)
        p.setPen(QColor("#b9a8ff"))
        p.drawText(pill, Qt.AlignCenter, self.arg)
        p.end()


class ArgsPopup(QWidget):
    picked = Signal(str)
    closed = Signal()
    PAD = 14

    def __init__(self, parent, hints, current):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._progress = 0.0
        self.base = QPoint()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.PAD, self.PAD - 6, self.PAD, self.PAD + 6)
        box = QFrame()
        box.setObjectName("popup")
        shadow = QGraphicsDropShadowEffect(box)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 170))
        box.setGraphicsEffect(shadow)
        outer.addWidget(box)
        v = QVBoxLayout(box)
        v.setContentsMargins(6, 8, 6, 6)
        v.setSpacing(2)
        head = QLabel("ГОТОВЫЕ АРГУМЕНТЫ")
        head.setObjectName("muted")
        head.setContentsMargins(10, 0, 0, 4)
        v.addWidget(head)
        if not hints:
            empty = QLabel("Для этой проги готовых нет —\nвпиши свои руками в поле")
            empty.setStyleSheet("color: #7a7a88; padding: 8px 10px 10px 10px;")
            v.addWidget(empty)
        for arg, desc in hints:
            item = ArgItem(desc, arg, arg in current)
            item.clicked.connect(lambda checked=False, a=arg: self.picked.emit(a))
            v.addWidget(item)
        self.anim = QPropertyAnimation(self, b"progress", self)
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

    def getProgress(self):
        return self._progress

    def setProgress(self, v):
        self._progress = v
        self.setWindowOpacity(v)
        self.move(self.base + QPoint(0, int(-10 * (1 - v))))

    progress = Property(float, getProgress, setProgress)

    def show_below(self, anchor):
        w = max(anchor.width(), 330) + self.PAD * 2
        self.resize(w, self.sizeHint().height())
        pos = anchor.mapToGlobal(QPoint(anchor.width() - w + self.PAD, anchor.height() + 4 - self.PAD + 6))
        screen = anchor.screen().availableGeometry()
        if pos.y() + self.height() > screen.bottom():
            pos.setY(anchor.mapToGlobal(QPoint(0, 0)).y() - self.height() + self.PAD - 4)
        pos.setX(max(screen.left(), pos.x()))
        self.base = pos
        self.setProgress(0.0)
        self.show()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def hideEvent(self, e):
        self.closed.emit()
        super().hideEvent(e)


class ArgsField(QFrame):
    def __init__(self, text=""):
        super().__init__()
        self.setObjectName("argsfield")
        self.setProperty("open", False)
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 4, 0)
        lay.setSpacing(2)
        self.edit = QLineEdit(text)
        self.edit.setPlaceholderText("аргументы")
        self.edit.setStyleSheet("padding: 6px 0px;")
        self.btn = IconButton("chevron", 26, frame=False)
        self.btn.clicked.connect(self.toggle)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.btn)
        self.hints = []
        self.popup = None
        self._closed_at = 0.0

    def text(self):
        return self.edit.text()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.toggle()

    def toggle(self):
        if self.popup is not None:
            self.popup.close()
            return
        if time.monotonic() - self._closed_at < 0.25:
            return
        self.popup = ArgsPopup(self, self.hints, self.edit.text().split())
        self.popup.picked.connect(self.toggle_arg)
        self.popup.closed.connect(self._on_closed)
        self.popup.show_below(self)
        self.set_open(True)

    def _on_closed(self):
        self.popup = None
        self._closed_at = time.monotonic()
        self.set_open(False)

    def set_open(self, on):
        self.setProperty("open", on)
        repolish(self)
        self.btn.rotate_to(180 if on else 0)

    def toggle_arg(self, arg):
        parts = self.edit.text().split()
        if arg in parts:
            parts.remove(arg)
        else:
            parts.append(arg)
        self.edit.setText(" ".join(parts))


class PathEdit(QLineEdit):
    def __init__(self, text=""):
        super().__init__()
        self._full = ""
        self.textChanged.connect(self._sync)
        self.setText(text)

    def _is_link(self):
        return self._full.lower().startswith(("http://", "https://"))

    def _show(self):
        shown = self._full if (self.hasFocus() or not self._full or self._is_link()) else os.path.basename(self._full)
        QLineEdit.setText(self, shown)
        self.setToolTip(self._full)

    def _sync(self, *_):
        if self.hasFocus():
            self._full = QLineEdit.text(self)

    def text(self):
        return self._full

    def setText(self, t):
        self._full = t or ""
        self._show()

    def focusInEvent(self, e):
        QLineEdit.setText(self, self._full)
        super().focusInEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self._show()


class AppRow(QFrame):
    removed = Signal(object)
    moved = Signal(object, int)
    duplicated = Signal(object)

    def __init__(self, data=None):
        super().__init__()
        data = data or {}
        self.host = None
        self.target_y = 0
        self.setObjectName("row")
        self.setProperty("lifted", False)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 8, 10, 8)
        lay.setSpacing(8)

        self.path = PathEdit(data.get("path", ""))
        self.path.setPlaceholderText("Путь к программе или https://ссылка")
        self.dot = QLabel("●")
        self.dot.setFixedWidth(12)
        self.dot.setStyleSheet("color: transparent; font-size: 9px;")
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(22, 22)
        self.path.textChanged.connect(self.update_icon)
        self.update_icon()
        browse = IconButton("folder", 32)
        browse.setToolTip("Выбрать файл")
        browse.clicked.connect(self.pick)

        self.args = ArgsField(data.get("args", ""))
        self.args.setFixedWidth(230)
        self.path.textChanged.connect(lambda *_: self.fill_args())
        self.fill_args()

        self.delay = QDoubleSpinBox()
        self.delay.setRange(0, 600)
        self.delay.setDecimals(1)
        self.delay.setSuffix(" с")
        self.delay.setValue(float(data.get("delay", 0) or 0))
        self.delay.setFixedWidth(90)
        self.delay.setAlignment(Qt.AlignCenter)
        self.delay.setToolTip("Задержка перед следующим")
        self.mode = QPushButton()
        self.mode.setCheckable(True)
        self.mode.setChecked(data.get("mode") == "close")
        self.mode.setFixedWidth(96)
        self.mode.setToolTip("Открыть программу или закрыть её в этот момент очереди")
        self.mode.toggled.connect(self.update_mode)
        self.kill = QCheckBox("закрыть")
        self.kill.setChecked(bool(data.get("kill")))
        self.kill.setToolTip("Закрывать эту программу кнопкой «Закрыть всё»")
        self.update_mode()

        rm = IconButton("close", 32, danger=True)
        rm.setToolTip("Убрать")
        rm.clicked.connect(lambda: self.removed.emit(self))
        dup = IconButton("copy", 32)
        dup.setToolTip("Сделать строку «закрыть» с этой же программой (через 20 с)")
        dup.clicked.connect(lambda: self.duplicated.emit(self))
        up = IconButton("up", 32)
        up.setToolTip("Выше")
        up.clicked.connect(lambda: self.moved.emit(self, -1))
        down = IconButton("down", 32)
        down.setToolTip("Ниже")
        down.clicked.connect(lambda: self.moved.emit(self, 1))

        lay.addWidget(Grip(self))
        lay.addWidget(self.dot)
        lay.addWidget(self.icon_lbl)
        lay.addWidget(self.path, 1)
        lay.addWidget(browse)
        lay.addWidget(self.mode)
        lay.addWidget(self.args)
        lay.addWidget(self.delay)
        lay.addWidget(self.kill)
        lay.addWidget(dup)
        lay.addWidget(up)
        lay.addWidget(down)
        lay.addWidget(rm)

    def set_lifted(self, on):
        self.setProperty("lifted", on)
        repolish(self)
        if on:
            fx = QGraphicsDropShadowEffect(self)
            fx.setOffset(0, 10)
            fx.setColor(QColor(124, 92, 255, 90))
            fx.setBlurRadius(0)
            self.setGraphicsEffect(fx)
            self.lift_anim = QPropertyAnimation(fx, b"blurRadius", self)
            self.lift_anim.setDuration(200)
            self.lift_anim.setStartValue(0.0)
            self.lift_anim.setEndValue(32.0)
            self.lift_anim.start()
        else:
            self.setGraphicsEffect(None)

    def update_icon(self):
        self.icon_lbl.setPixmap(file_icon(self.path.text().strip(), 20))

    def set_running(self, on):
        self.dot.setStyleSheet(f"color: {'#3ddc84' if on else 'transparent'}; font-size: 9px;")

    def update_mode(self, *_):
        closing = self.mode.isChecked()
        self.mode.setText("✕ закрыть" if closing else "▶ открыть")
        self.args.setEnabled(not closing)
        self.kill.setEnabled(not closing)

    def fill_args(self):
        name = os.path.basename(self.path.text().strip()).lower()
        self.args.hints = ARG_HINTS.get(name, [])

    def pick(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбери программу", "", "Программы (*.exe *.bat *.cmd *.lnk);;Все файлы (*)"
        )
        if path:
            self.path.setText(path)

    def to_dict(self):
        return {
            "path": self.path.text().strip(),
            "args": self.args.text().strip(),
            "delay": self.delay.value(),
            "kill": self.kill.isChecked(),
            "mode": "close" if self.mode.isChecked() else "open",
        }


class FinderDialog(QDialog):
    def __init__(self, parent, cmap):
        super().__init__(parent)
        self.cmap = cmap
        self.selected = []
        self.setWindowTitle("Найти программу")
        self.setWindowIcon(app_icon())
        self.resize(560, 460)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Название программы или категория")
        self.search.textChanged.connect(self.populate)
        v.addWidget(self.search)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.setIconSize(QSize(24, 24))
        self.list.itemDoubleClicked.connect(lambda *_: self.accept_selection())
        v.addWidget(self.list, 1)
        self.info = QLabel("")
        self.info.setObjectName("muted")
        v.addWidget(self.info)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        add = QPushButton("Добавить")
        add.setObjectName("accent")
        add.clicked.connect(self.accept_selection)
        row.addWidget(cancel)
        row.addWidget(add)
        v.addLayout(row)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        if not SCANNED:
            self.timer.start(400)
        self.populate()

    def tick(self):
        if SCANNED:
            self.timer.stop()
        self.populate()

    def populate(self):
        query = self.search.text().strip().lower()
        rows = []
        for item in INSTALLED:
            cat = self.cmap.get(os.path.basename(item["path"]).lower(), "")
            if query and query not in item["name"].lower() and query not in cat.lower():
                continue
            rows.append((cat == "", cat, item["name"].lower(), item, cat))
        rows.sort(key=lambda r: r[:3])
        self.list.clear()
        for _, _, _, item, cat in rows:
            text = f"{item['name']}   ·   {cat}" if cat else item["name"]
            li = QListWidgetItem(QIcon(file_icon(item["path"], 24)), text)
            li.setData(Qt.UserRole, item["path"])
            li.setToolTip(item["path"])
            self.list.addItem(li)
        self.info.setText(f"Найдено: {len(rows)}" if SCANNED else "Ищу установленные программы...")

    def accept_selection(self):
        self.selected = [{"path": i.data(Qt.UserRole)} for i in self.list.selectedItems()]
        if self.selected:
            self.accept()


class MainWindow(QMainWindow):
    show_requested = Signal()

    def __init__(self):
        super().__init__()
        self.show_requested.connect(self.show_window)
        self.cfg = load_config()
        self.cfg["presets"].sort(key=lambda x: 0 if x.get("pinned") else 1)
        self.current = 0 if self.cfg["presets"] else -1
        self.queue = []
        self.skipped = []
        self.quitting = False
        self._drag = None
        self._dragging = None

        self.setWindowTitle("PresetLauncher")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(1000, 600)

        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade.setDuration(220)
        self.fade.setEasingCurve(QEasingCurve.OutCubic)
        self.fade.finished.connect(self._fade_done)

        self.folder = None
        self.card_map = {}
        self.build_ui()
        self.refresh_cards()
        self.load_editor()
        self.update_combo()
        self.run_timer = QTimer(self)
        self.run_timer.timeout.connect(self.refresh_running)
        self.run_timer.start(2000)
        self.refresh_running()

        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setContextMenu(QMenu())
        self.tray.activated.connect(self._tray_activated)
        self.rebuild_tray()
        self.tray.show()

        self.hotkey_ok = bool(ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_P))
        self.hotkey_filter = HotkeyFilter(self.show_window)
        QApplication.instance().installNativeEventFilter(self.hotkey_filter)

        first_run = not self.cfg.get("first_run_done", False)
        if first_run:
            self.cfg["first_run_done"] = True
            save_config(self.cfg)

        if self.cfg["start_hidden"] and not first_run:
            self.tray.showMessage("PresetLauncher", "Свернулся в трей. Клик по иконке — открыть", app_icon(), 2000)
        else:
            self.show_window()

        auto = self.cfg.get("autostart_preset", "")
        names = [p["name"] for p in self.cfg["presets"]]
        if auto in names:
            QTimer.singleShot(1500, lambda: self.launch(names.index(auto)))

    def _ghost(self, text, slot, name="ghost"):
        b = QPushButton(text)
        b.setObjectName(name)
        b.setFixedSize(30, 28)
        b.clicked.connect(slot)
        return b

    def _muted(self, text):
        l = QLabel(text)
        l.setObjectName("muted")
        return l

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 16, 16, 16)

        root = QFrame()
        root.setObjectName("root")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 180))
        root.setGraphicsEffect(shadow)
        outer.addWidget(root)

        v = QVBoxLayout(root)
        v.setContentsMargins(20, 14, 20, 14)
        v.setSpacing(14)

        head = QHBoxLayout()
        title = QLabel("P R E S E T S")
        title.setObjectName("title")
        head.addWidget(title)
        head.addStretch()
        min_btn = IconButton("min", 30, frame=False)
        min_btn.clicked.connect(self.showMinimized)
        close_btn = IconButton("close", 30, danger=True, frame=False)
        close_btn.clicked.connect(self.hide_window)
        head.addWidget(min_btn)
        head.addWidget(close_btn)
        v.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(self._muted("ПАПКИ И ПРЕСЕТЫ"))
        self.tiles_host = QWidget()
        self.tiles = QGridLayout(self.tiles_host)
        self.tiles.setContentsMargins(0, 0, 0, 0)
        self.tiles.setSpacing(GAP)
        self.tiles.setAlignment(Qt.AlignTop)
        self.tiles.setContentsMargins(0, 0, 0, 0)
        for col in range(3):
            self.tiles.setColumnMinimumWidth(col, TILE)
        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setWidget(self.tiles_host)
        cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cards_scroll.setFixedWidth(3 * TILE + 2 * GAP + 26)
        left.addWidget(cards_scroll, 1)
        add_preset = QPushButton("+ Новый пресет")
        add_preset.clicked.connect(self.add_preset)
        left.addWidget(add_preset)
        body.addLayout(left)

        self.editor = QFrame()
        self.editor.setObjectName("editor")
        ev = QVBoxLayout(self.editor)
        ev.setContentsMargins(20, 18, 20, 18)
        ev.setSpacing(10)
        ev.addWidget(self._muted("НАЗВАНИЕ"))
        self.name_edit = QLineEdit()
        ev.addWidget(self.name_edit)
        ev.addWidget(self._muted("ПАПКА"))
        self.folder_combo = QComboBox()
        ev.addWidget(self.folder_combo)
        ev.addWidget(self._muted("ПРИЛОЖЕНИЯ ПО ПОРЯДКУ  ·  можно перетащить .exe в окно"))

        apps_scroll = QScrollArea()
        apps_scroll.setWidgetResizable(True)
        apps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.apps_list = AppList()
        self.apps_list.scroll = apps_scroll
        apps_scroll.setWidget(self.apps_list)
        ev.addWidget(apps_scroll, 1)

        btns = QHBoxLayout()
        find_btn = QPushButton("Найти программу")
        find_btn.clicked.connect(self.open_finder)
        close_btn = QPushButton("Закрыть всё")
        close_btn.setObjectName("danger")
        close_btn.clicked.connect(self.close_preset)
        add_app = QPushButton("+ Приложение")
        add_app.clicked.connect(lambda: self.add_app_row())
        del_preset = QPushButton("Удалить пресет")
        del_preset.setObjectName("danger")
        del_preset.clicked.connect(self.delete_preset)
        dup_preset = QPushButton("Дублировать")
        dup_preset.setToolTip("Сделать копию пресета")
        dup_preset.clicked.connect(self.duplicate_preset)
        later = QPushButton("Позже")
        later.setToolTip("Запустить с задержкой")
        later_menu = QMenu(later)
        for label, secs in (("10 секунд", 10), ("30 секунд", 30), ("1 минута", 60), ("5 минут", 300)):
            later_menu.addAction(label).triggered.connect(lambda checked=False, s=secs: self.launch_later(s))
        later.setMenu(later_menu)
        save = QPushButton("Сохранить")
        save.clicked.connect(self.save_current)
        launch = QPushButton("▶  ЗАПУСК")
        launch.setObjectName("accent")
        launch.clicked.connect(lambda: self.launch(self.current))
        btns.addWidget(add_app)
        btns.addWidget(find_btn)
        btns.addWidget(close_btn)
        btns.addWidget(dup_preset)
        btns.addWidget(del_preset)
        btns.addStretch()
        btns.addWidget(save)
        btns.addWidget(later)
        btns.addWidget(launch)
        ev.addLayout(btns)
        body.addWidget(self.editor, 1)
        v.addLayout(body, 1)

        foot = QHBoxLayout()
        self.hidden_chk = QCheckBox("Стартовать в трей")
        self.hidden_chk.setChecked(bool(self.cfg["start_hidden"]))
        self.hidden_chk.toggled.connect(self.toggle_hidden)
        self.hide_chk = QCheckBox("Скрыть после запуска")
        self.hide_chk.setChecked(bool(self.cfg.get("hide_after_launch", False)))
        self.hide_chk.toggled.connect(self.toggle_hide_after)
        self.win_chk = QCheckBox("Автостарт Windows")
        self.win_chk.setChecked(startup_active())
        self.win_chk.toggled.connect(self.toggle_windows_startup)
        self.status = QLabel("")
        self.status.setObjectName("status")
        self.auto_combo = QComboBox()
        self.auto_combo.setMinimumWidth(160)
        self.auto_combo.currentIndexChanged.connect(self.set_autostart)
        quit_btn = QPushButton("Выйти")
        quit_btn.clicked.connect(self.quit_app)
        foot.addWidget(self.hidden_chk)
        foot.addWidget(self.hide_chk)
        foot.addWidget(self.win_chk)
        foot.addStretch()
        foot.addWidget(self.status)
        foot.addSpacing(12)
        foot.addWidget(self._muted("АВТОЗАПУСК"))
        foot.addWidget(self.auto_combo)
        foot.addWidget(quit_btn)
        v.addLayout(foot)

    def open_finder(self):
        dlg = FinderDialog(self, build_category_map(self.cfg))
        if dlg.exec():
            for item in dlg.selected:
                self.add_app_row({"path": item["path"], "args": "", "delay": 0})

    def close_preset(self):
        if not 0 <= self.current < len(self.cfg["presets"]):
            return
        self.save_current()
        apps = self.cfg["presets"][self.current].get("apps", [])
        targets = [a for a in apps if a.get("kill")] or apps
        names = {os.path.basename(a["path"]).lower() for a in targets if a["path"].lower().endswith(".exe")}
        running = names & set(running_ages())
        if not running:
            self.flash("Ничего из пресета не открыто")
            return
        reply = QMessageBox.question(
            self, "Закрыть", "Закрыть: " + ", ".join(sorted(running)) + "?"
        )
        if reply != QMessageBox.Yes:
            return
        closed = 0
        for proc in psutil.process_iter(["name"]):
            try:
                if (proc.info["name"] or "").lower() in running:
                    proc.terminate()
                    closed += 1
            except psutil.Error:
                pass
        self.flash(f"Закрыто: {closed}")
        QTimer.singleShot(800, self.refresh_running)

    def refresh_running(self):
        ages = running_ages()
        for r in self.app_rows:
            r.set_running(os.path.basename(r.path.text().strip()).lower() in ages)


    @property
    def app_rows(self):
        return self.apps_list.rows

    def add_app_row(self, data=None):
        row = AppRow(data)
        row.removed.connect(self.apps_list.remove)
        row.moved.connect(self.apps_list.shift)
        row.duplicated.connect(self.dup_app_row)
        self.apps_list.add(row)
        return row

    def dup_app_row(self, row):
        data = row.to_dict()
        if not data["path"]:
            return
        data.update({"mode": "close", "delay": 20.0, "kill": False})
        new = self.add_app_row(data)
        self.apps_list.insert_after(row, new)

    def load_editor(self):
        self.apps_list.clear()
        valid = 0 <= self.current < len(self.cfg["presets"])
        self.editor.setEnabled(valid)
        if not valid:
            self.name_edit.clear()
            return
        p = self.cfg["presets"][self.current]
        self.name_edit.setText(p["name"])
        for a in p.get("apps", []):
            self.add_app_row(a)
        self.sync_folder_combo()

    def visible_indexes(self):
        return [i for i, p in enumerate(self.cfg["presets"])
                if self.folder is None or p.get("folder", "") == self.folder]

    def refresh_cards(self):
        while self.tiles.count():
            w = self.tiles.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.card_map = {}
        cols = 3
        self.tiles.addWidget(self._muted("ПАПКИ"), 0, 0, 1, cols)
        folder_tiles = [(None, "Все", f"{len(self.cfg['presets'])} шт")]
        for name in self.cfg["folders"]:
            n = sum(1 for p in self.cfg["presets"] if p.get("folder", "") == name)
            folder_tiles.append((name, name, f"{n} шт"))
        for k, (name, title, sub) in enumerate(folder_tiles):
            c = PresetCard(title, sub, active=self.folder == name,
                           target=("folder", name) if name is not None else None, small=True)
            c.clicked.connect(lambda n=name: self.select_folder(n))
            if name is not None:
                c.context.connect(lambda pos, n=name: self.folder_menu(pos, n))
            self.tiles.addWidget(c, 1 + k // cols, k % cols)
        k = len(folder_tiles)
        add = PresetCard("", "", plus=True, small=True)
        add.clicked.connect(self.add_folder)
        self.tiles.addWidget(add, 1 + k // cols, k % cols)
        row = 1 + (k + cols) // cols
        self.tiles.addWidget(self._muted("ПРЕСЕТЫ"), row, 0, 1, cols)
        row += 1
        for k, i in enumerate(self.visible_indexes()):
            p = self.cfg["presets"][i]
            c = PresetCard(p["name"], "",
                           pixmap=preset_pixmap(p, 48), active=i == self.current,
                           drag=f"preset:{i}", target=("preset", i))
            c.clicked.connect(lambda i=i: self.select(i))
            c.double_clicked.connect(lambda i=i: self.launch(i))
            c.context.connect(lambda pos, i=i: self.preset_menu(pos, i))
            c.released_at.connect(lambda gpos, i=i: self.preset_released(i, gpos))
            self.card_map[i] = c
            self.tiles.addWidget(c, row + k // cols, k % cols)
        self.refresh_running()

    def preset_released(self, src, gpos):
        over = card_at(gpos)
        if over is None or over.target is None:
            return
        self.drop_on(f"preset:{src}", over.target)

    def drop_on(self, payload, target):
        src = int(payload.split(":", 1)[1])
        presets = self.cfg["presets"]
        if not 0 <= src < len(presets):
            return
        kind, val = target
        if kind == "folder":
            presets[src]["folder"] = val
        else:
            if val == src:
                return
            cur = presets[self.current] if 0 <= self.current < len(presets) else None
            item = presets.pop(src)
            presets.insert(val, item)
            if cur is not None:
                self.current = next(i for i, x in enumerate(presets) if x is cur)
        QTimer.singleShot(0, self.commit)

    def select_folder(self, name):
        self.folder = name
        self.refresh_cards()

    def add_folder(self):
        name, ok = QInputDialog.getText(self, "Новая папка", "Название папки:")
        name = name.strip()
        if ok and name and name not in self.cfg["folders"]:
            self.cfg["folders"].append(name)
            self.commit()

    def folder_menu(self, pos, name):
        m = QMenu(self)
        m.addAction("Переименовать").triggered.connect(lambda: self.rename_folder(name))
        m.addAction("Удалить").triggered.connect(lambda: self.delete_folder(name))
        m.exec(pos)

    def rename_folder(self, old):
        new, ok = QInputDialog.getText(self, "Переименовать", "Новое название:", text=old)
        new = new.strip()
        if not ok or not new or new == old or new in self.cfg["folders"]:
            return
        self.cfg["folders"][self.cfg["folders"].index(old)] = new
        for p in self.cfg["presets"]:
            if p.get("folder", "") == old:
                p["folder"] = new
        if self.folder == old:
            self.folder = new
        self.commit()

    def delete_folder(self, name):
        reply = QMessageBox.question(self, "Удалить папку", f"Удалить папку «{name}»? Пресеты останутся.")
        if reply != QMessageBox.Yes:
            return
        self.cfg["folders"].remove(name)
        for p in self.cfg["presets"]:
            if p.get("folder", "") == name:
                p["folder"] = ""
        if self.folder == name:
            self.folder = None
        self.commit()

    def preset_menu(self, pos, i):
        p = self.cfg["presets"][i]
        m = QMenu(self)
        m.addAction("▶ Запустить").triggered.connect(lambda: self.launch(i))
        m.addAction("Открепить" if p.get("pinned") else "Закрепить").triggered.connect(lambda: self.toggle_pin(i))
        m.addAction("Сменить иконку").triggered.connect(lambda: self.pick_icon(i))
        if p.get("icon"):
            m.addAction("Сбросить иконку").triggered.connect(lambda: self.set_icon(i, ""))
        sub = m.addMenu("В папку")
        sub.addAction(NO_FOLDER).triggered.connect(lambda: self.move_to_folder(i, ""))
        for name in self.cfg["folders"]:
            sub.addAction(name).triggered.connect(lambda checked=False, n=name: self.move_to_folder(i, n))
        m.exec(pos)

    def pick_icon(self, i):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбери иконку", "", "Картинки (*.png *.jpg *.jpeg *.ico *.bmp *.webp);;Все файлы (*)"
        )
        if path:
            self.set_icon(i, path)

    def set_icon(self, i, path):
        self.cfg["presets"][i]["icon"] = path
        self.commit()

    def move_to_folder(self, i, name):
        self.cfg["presets"][i]["folder"] = name
        self.commit()

    def update_folder_combo(self):
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        self.folder_combo.addItem(NO_FOLDER)
        self.folder_combo.addItems(self.cfg["folders"])
        self.folder_combo.blockSignals(False)

    def sync_folder_combo(self):
        self.update_folder_combo()
        if 0 <= self.current < len(self.cfg["presets"]):
            self.folder_combo.setCurrentText(self.cfg["presets"][self.current].get("folder") or NO_FOLDER)

    def toggle_pin(self, idx):
        if not 0 <= idx < len(self.cfg["presets"]):
            return
        p = self.cfg["presets"][idx]
        p["pinned"] = not bool(p.get("pinned"))
        cur = self.cfg["presets"][self.current] if 0 <= self.current < len(self.cfg["presets"]) else None
        self.cfg["presets"].sort(key=lambda x: 0 if x.get("pinned") else 1)
        if cur is not None:
            self.current = next(i for i, x in enumerate(self.cfg["presets"]) if x is cur)
        save_config(self.cfg)
        self.refresh_cards()
        self.rebuild_tray()
        self.update_combo()

    def duplicate_preset(self):
        if not 0 <= self.current < len(self.cfg["presets"]):
            return
        self.save_current()
        src = json.loads(json.dumps(self.cfg["presets"][self.current], ensure_ascii=False))
        src["name"] = src["name"] + " (копия)"
        src["pinned"] = False
        src["launches"] = 0
        self.cfg["presets"].insert(self.current + 1, src)
        self.current += 1
        self.load_editor()
        self.commit()
        self.flash("Дублировано ✓")

    def launch_later(self, secs):
        if not 0 <= self.current < len(self.cfg["presets"]):
            return
        p = self.cfg["presets"][self.current]
        self.save_current()
        self.flash(f"Запуск через {secs} с")
        QTimer.singleShot(int(secs * 1000), lambda: self._launch_obj(p))

    def _launch_obj(self, p):
        idx = next((i for i, x in enumerate(self.cfg["presets"]) if x is p), None)
        if idx is not None:
            self.launch(idx)

    def toggle_hide_after(self, checked):
        self.cfg["hide_after_launch"] = checked
        save_config(self.cfg)

    def toggle_windows_startup(self, checked):
        ok = set_startup_lnk(checked)
        self.win_chk.blockSignals(True)
        self.win_chk.setChecked(ok)
        self.win_chk.blockSignals(False)
        self.flash("Автостарт Windows: вкл" if ok else "Автостарт Windows: выкл")

    def commit(self):
        save_config(self.cfg)
        self.refresh_cards()
        self.rebuild_tray()
        self.update_combo()
        self.sync_folder_combo()

    def select(self, idx):
        if idx == self.current:
            return
        self.save_current()
        self.current = idx
        self.load_editor()
        self.refresh_cards()

    def save_current(self):
        if not 0 <= self.current < len(self.cfg["presets"]):
            return
        p = self.cfg["presets"][self.current]
        old = p["name"]
        p["name"] = self.name_edit.text().strip() or "Без названия"
        folder = self.folder_combo.currentText()
        p["folder"] = "" if folder == NO_FOLDER else folder
        p["apps"] = [d for d in (r.to_dict() for r in self.app_rows) if d["path"]]
        if self.cfg.get("autostart_preset") == old:
            self.cfg["autostart_preset"] = p["name"]
        self.commit()
        self.flash("Сохранено ✓")

    def add_preset(self):
        self.save_current()
        n = len(self.cfg["presets"]) + 1
        self.cfg["presets"].append({"name": f"Пресет {n}", "apps": [], "folder": self.folder or ""})
        self.current = len(self.cfg["presets"]) - 1
        self.load_editor()
        self.commit()
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def delete_preset(self):
        if not 0 <= self.current < len(self.cfg["presets"]):
            return
        name = self.cfg["presets"][self.current]["name"]
        reply = QMessageBox.question(self, "Удалить", f"Удалить пресет «{name}»?")
        if reply != QMessageBox.Yes:
            return
        del self.cfg["presets"][self.current]
        if self.cfg.get("autostart_preset") == name:
            self.cfg["autostart_preset"] = ""
        self.current = min(self.current, len(self.cfg["presets"]) - 1)
        self.load_editor()
        self.commit()

    def update_combo(self):
        names = [p["name"] for p in self.cfg["presets"]]
        auto = self.cfg.get("autostart_preset", "")
        self.auto_combo.blockSignals(True)
        self.auto_combo.clear()
        self.auto_combo.addItem("— нет —")
        self.auto_combo.addItems(names)
        self.auto_combo.setCurrentIndex(names.index(auto) + 1 if auto in names else 0)
        self.auto_combo.blockSignals(False)

    def set_autostart(self, i):
        self.cfg["autostart_preset"] = self.auto_combo.currentText() if i > 0 else ""
        save_config(self.cfg)

    def toggle_hidden(self, checked):
        self.cfg["start_hidden"] = checked
        save_config(self.cfg)

    def launch(self, idx):
        if not 0 <= idx < len(self.cfg["presets"]):
            return
        if idx == self.current:
            self.save_current()
        p = self.cfg["presets"][idx]
        p["launches"] = int(p.get("launches", 0)) + 1
        p["last_launch"] = int(time.time())
        self.queue = list(p.get("apps", []))
        self.skipped = []
        self.flash(f"Запуск: {p['name']}")
        save_config(self.cfg)
        self.refresh_cards()
        self.launch_next()

    def launch_next(self):
        if not self.queue:
            self.finish_launch()
            return
        app = self.queue.pop(0)
        path = app.get("path", "").strip()
        args = app.get("args", "")
        name = os.path.basename(path).lower()
        if app.get("mode") == "close":
            QTimer.singleShot(int(float(app.get("delay", 0) or 0) * 1000), lambda: self.close_app(name))
            return
        skip = name.endswith((".exe", ".bat", ".cmd")) and name in running_ages() and not (
            name in BROWSERS and URL_RE.search(args))
        if skip:
            self.skipped.append(os.path.basename(path))
        else:
            try:
                if name.endswith((".exe", ".bat", ".cmd")):
                    cmd = f'"{path}" {args}'.strip()
                    subprocess.Popen(cmd, cwd=os.path.dirname(path) or None)
                else:
                    os.startfile(path)
            except Exception as e:
                self.flash(f"Ошибка: {e}")
        if self.queue:
            QTimer.singleShot(int(float(app.get("delay", 0) or 0) * 1000), self.launch_next)
        else:
            self.finish_launch()

    def close_app(self, name):
        if name in running_ages():
            for proc in psutil.process_iter(["name"]):
                try:
                    if (proc.info["name"] or "").lower() == name:
                        proc.terminate()
                except psutil.Error:
                    pass
            self.flash(f"Закрыл: {name}")
        else:
            self.flash(f"Уже закрыто: {name}")
        self.refresh_running()
        self.launch_next()

    def finish_launch(self):
        if self.skipped:
            self.flash("Уже открыто, пропустил: " + ", ".join(self.skipped))
        self.refresh_running()
        if self.cfg.get("hide_after_launch"):
            QTimer.singleShot(600, self.hide_window)

    def flash(self, text):
        self.status.setText(text)
        QTimer.singleShot(2500, self.status.clear)
        if not self.isVisible():
            self.tray.showMessage("PresetLauncher", text, app_icon(), 1500)

    def rebuild_tray(self):
        menu = self.tray.contextMenu()
        menu.clear()
        menu.addAction("Показать").triggered.connect(self.show_window)
        menu.addSeparator()
        for i, p in enumerate(self.cfg["presets"]):
            menu.addAction(f"▶  {p['name']}").triggered.connect(lambda checked=False, i=i: self.launch(i))
        menu.addSeparator()
        menu.addAction("Выйти").triggered.connect(self.quit_app)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible():
                self.hide_window()
            else:
                self.show_window()

    def show_window(self):
        self.fade.stop()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.fade.start()

    def hide_window(self):
        self.fade.stop()
        self.fade.setStartValue(self.windowOpacity())
        self.fade.setEndValue(0.0)
        self.fade.start()

    def _fade_done(self):
        if self.windowOpacity() < 0.01:
            self.hide()
            self.setWindowOpacity(1.0)

    def quit_app(self):
        self.quitting = True
        self.tray.hide()
        if self.hotkey_ok:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        QApplication.quit()

    def closeEvent(self, e):
        if self.quitting:
            e.accept()
            return
        e.ignore()
        self.hide_window()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if self.current < 0:
            self.add_preset()
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.add_app_row({"path": path, "args": "", "delay": 0})


def main():
    if notify_running():
        return
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    for ttf in (RES / "fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(ttf))
    app.setStyleSheet(QSS)
    app.setWindowIcon(app_icon())

    threading.Thread(target=scan_installed, daemon=True).start()
    win = MainWindow()
    threading.Thread(target=serve_single, args=(win,), daemon=True).start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
