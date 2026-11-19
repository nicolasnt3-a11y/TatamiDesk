#!/usr/bin/env python3
"""
Tatami Desk - range les raccourcis du bureau dans des zones a onglets.
Auteur : Vincent Chapeau - Licence MIT.

- Glisse un raccourci / fichier / dossier du bureau dans une zone : il quitte le
  bureau et s'affiche dans l'onglet actif (stocke dans %APPDATA%\\TatamiDesk\\items).
- Survole un onglet en glissant une icone : l'onglet s'ouvre. Lache sur l'onglet : rangé dedans.
- Double-clic icone : lance. Clic droit : options.
- Barre d'onglets : clic = changer d'onglet, glisser = deplacer la zone,
  double-clic = replier, "+" = nouvel onglet. Bords : redimensionner.
- Icone de notification : clic = afficher/masquer, clic droit = reglages.
"""
import sys
import os
import json
import uuid
import shutil
import subprocess
import ctypes
import math
import struct
import time
import psutil

from PySide6.QtCore import (QFileSystemWatcher, Qt, QPoint, QPointF, QRect, QRectF, QTimer, QUrl, QMimeData,
                            QFileInfo, QStandardPaths, QEvent)
from PySide6.QtGui import (QBrush, QLinearGradient, QImage, QAbstractFileIconProvider, QGuiApplication, QPainter, QColor, QPainterPath, QDrag, QIcon, QPixmap, QFont,
                           QPen, QFontMetrics)
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QStackedWidget, QRadioButton, QButtonGroup,
                               QGroupBox, QDialog, QFormLayout, QSlider, QCheckBox, QComboBox, QFontComboBox,
                               QPushButton, QColorDialog, QLabel, QHBoxLayout,
                               QApplication, QWidget, QVBoxLayout, QLineEdit, QScrollArea,
                               QFileIconProvider, QMenu, QSystemTrayIcon, QMessageBox, QFrame)

IS_WIN = sys.platform == "win32"
APP_NAME = "Tatami Desk"
APP_ID = "TatamiDesk"          # dossier de donnees, registre, exe
OLD_ID = "Mini" + "Fen" + "ces"      # nom de la version de developpement (migration)
APP_VERSION = "1.0"
_MUTEX = None
MIME = "application/x-tatamidesk-item"

DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_ID)
STORE_DIR = os.path.join(DATA_DIR, "items")
CONFIG = os.path.join(DATA_DIR, "config.json")

ACCENTS = [("Blanc", "#E5E7EB"), ("Bleu", "#4C8BF5"), ("Turquoise", "#14B8A6"),
           ("Vert", "#22C55E"), ("Jaune", "#EAB308"), ("Orange", "#F97316"),
           ("Rouge", "#EF4444"), ("Rose", "#EC4899"), ("Violet", "#8B5CF6")]

# Themes : tout est peint par l'app, changer de theme ne coute rien en ressources.
THEMES = {
    "sombre": dict(label="Sombre (défaut)", bg=(12, 13, 18), a_blur=105, a_blur_h=135, a_solid=170, a_solid_h=200,
                   band=(0, 0, 0), band_a=55, band_accent=False, border=(255, 255, 255), border_a=20, border_h=34,
                   border_accent=False, glow=False, radius=8, text=(240, 240, 240), shadow=True, inactive=140,
                   tab="pill", tile_hover=(255, 255, 255, 28), sep_a=22, blur_ok=True),
    "classique": dict(label="Classique (façon Zones)", bg=(0, 0, 0), a_blur=110, a_blur_h=140, a_solid=160,
                      a_solid_h=185, band=(0, 0, 0), band_a=0, band_accent=False, border=(255, 255, 255), border_a=0,
                      border_h=18, border_accent=False, glow=False, radius=2, text=(235, 235, 235), shadow=True,
                      inactive=150, tab="box", tile_hover=(255, 255, 255, 30), sep_a=0, blur_ok=True),
    "verre": dict(label="Verre clair", bg=(245, 247, 250), a_blur=95, a_blur_h=125, a_solid=200, a_solid_h=225,
                  band=(255, 255, 255), band_a=70, band_accent=False, border=(255, 255, 255), border_a=120,
                  border_h=170, border_accent=False, glow=False, radius=12, text=(22, 24, 30), shadow=False,
                  inactive=150, tab="pill", tile_hover=(0, 0, 0, 22), sep_a=0, blur_ok=True),
    "minimal": dict(label="Minimal (invisible au repos)", bg=(10, 10, 14), a_blur=6, a_blur_h=150, a_solid=6,
                    a_solid_h=150, band=(0, 0, 0), band_a=0, band_accent=False, border=(255, 255, 255), border_a=0,
                    border_h=25, border_accent=False, glow=False, radius=8, text=(245, 245, 245), shadow=True,
                    inactive=120, tab="underline", tile_hover=(255, 255, 255, 30), sep_a=0, blur_ok=False),
    "neon": dict(label="Néon", bg=(8, 8, 14), a_blur=150, a_blur_h=175, a_solid=200, a_solid_h=220,
                 band=(0, 0, 0), band_a=0, band_accent=True, border=(0, 0, 0), border_a=170, border_h=230,
                 border_accent=True, glow=True, radius=10, text=(240, 240, 255), shadow=True, inactive=130,
                 tab="accent", tile_hover=(255, 255, 255, 24), sep_a=0, blur_ok=True),
    "graphite": dict(label="Graphite (opaque, sobre)", bg=(32, 34, 40), a_blur=245, a_blur_h=250, a_solid=245,
                     a_solid_h=250, band=(0, 0, 0), band_a=0, band_accent=True, border=(255, 255, 255), border_a=14,
                     border_h=24, border_accent=False, glow=False, radius=4, text=(230, 232, 236), shadow=False,
                     inactive=140, tab="underline", tile_hover=(255, 255, 255, 18), sep_a=0, blur_ok=False),
}
THEMES["zen"] = dict(
    label="Zen (papier washi)", bg=(236, 228, 212), a_blur=205, a_blur_h=225, a_solid=235, a_solid_h=245,
    band=(0, 0, 0), band_a=0, band_accent=False, border=(90, 70, 50), border_a=55, border_h=85,
    border_accent=False, glow=False, radius=3, text=(44, 34, 28), shadow=False, inactive=135,
    tab="dot", tile_hover=(120, 90, 60, 28), sep_a=0, blur_ok=True,
    font="Yu Mincho", upper=False, shape="round", deco="shoji", accent="#B7282E")
THEMES["zen_nuit"] = dict(
    label="Zen nuit (encre sumi)", bg=(26, 23, 21), a_blur=175, a_blur_h=200, a_solid=225, a_solid_h=238,
    band=(0, 0, 0), band_a=0, band_accent=False, border=(210, 190, 160), border_a=28, border_h=50,
    border_accent=False, glow=False, radius=3, text=(234, 226, 212), shadow=False, inactive=130,
    tab="dot", tile_hover=(234, 226, 212, 22), sep_a=0, blur_ok=True,
    font="Yu Mincho", upper=False, shape="round", deco="shoji", accent="#D2553F")
THEMES["futur"] = dict(
    label="Futuriste (HUD)", bg=(4, 10, 22), a_blur=150, a_blur_h=180, a_solid=215, a_solid_h=232,
    band=(0, 0, 0), band_a=0, band_accent=False, border=(0, 0, 0), border_a=120, border_h=210,
    border_accent=True, glow=True, radius=12, text=(205, 238, 255), shadow=False, inactive=115,
    tab="hud", tile_hover=(0, 229, 255, 26), sep_a=0, blur_ok=True,
    font="Bahnschrift", upper=True, shape="chamfer", deco="hud", accent="#00E5FF")

THEME_DEFAULTS = dict(font="Segoe UI", upper=False, shape="round", deco="none", accent=None)
for _t in THEMES.values():
    for _k, _v in THEME_DEFAULTS.items():
        _t.setdefault(_k, _v)

THEMES["sunset"] = dict(
    label="Néon Sunset (Miami 80s)", bg=(30, 8, 48), gradient=[(26, 6, 46), (110, 20, 78)],
    a_blur=190, a_blur_h=215, a_solid=225, a_solid_h=240,
    band=(0, 0, 0), band_a=0, band_accent=False, border=(0, 0, 0), border_a=200, border_h=255,
    border_accent=True, border_gradient=["#FF3EA5", "#FFB13B"], glow=True, radius=10,
    text=(255, 238, 250), shadow=True, inactive=150, tab="underline", tile_hover=(255, 62, 165, 40),
    sep_a=0, blur_ok=True, font="Bahnschrift", upper=True, shape="round", deco="sunset", accent="#FF3EA5")
THEMES["cyber"] = dict(
    label="Cyber (jaune et noir)", bg=(10, 10, 12), a_blur=215, a_blur_h=235, a_solid=235, a_solid_h=248,
    band=(0, 0, 0), band_a=0, band_accent=False, border=(0, 0, 0), border_a=190, border_h=255,
    border_accent=True, glow=False, radius=14, text=(238, 238, 238), shadow=False, inactive=120,
    tab="hud", tile_hover=(252, 238, 10, 30), sep_a=0, blur_ok=False,
    font="Bahnschrift", upper=True, shape="chamfer", deco="scanlines", accent="#FCEE0A")
THEMES["palmiers"] = dict(
    label="Palmiers au crépuscule", bg=(40, 10, 60), gradient=[(34, 8, 62), (196, 58, 96)],
    a_blur=225, a_blur_h=240, a_solid=238, a_solid_h=248,
    band=(0, 0, 0), band_a=70, band_accent=False, border=(0, 0, 0), border_a=190, border_h=255,
    border_accent=True, border_gradient=["#FF4FA3", "#FFA53B"], glow=True, radius=10,
    text=(255, 244, 236), shadow=True, inactive=160, tab="underline", tile_hover=(255, 165, 59, 45),
    sep_a=0, blur_ok=False, font="Bahnschrift", upper=True, shape="round", deco="palms", accent="#FFA53B")
THEMES["teel"] = dict(
    label="Rouge & anthracite (Teel)", bg=(40, 42, 46), gradient=[(46, 48, 53), (30, 31, 35)],
    a_blur=225, a_blur_h=238, a_solid=238, a_solid_h=248,
    band=(0, 0, 0), band_a=60, band_accent=False, border=(255, 255, 255), border_a=18, border_h=34,
    border_accent=False, glow=False, radius=4, text=(242, 242, 244), shadow=False, inactive=135,
    tab="underline", tile_hover=(215, 25, 32, 34), sep_a=0, blur_ok=False,
    font="Segoe UI", upper=False, shape="round", deco="stripe", accent="#D71920")
for _t in (THEMES["sunset"], THEMES["cyber"], THEMES["teel"], THEMES["palmiers"]):
    for _k, _v in THEME_DEFAULTS.items():
        _t.setdefault(_k, _v)

THEME_ORDER = ["sombre", "classique", "verre", "minimal", "neon", "graphite", "zen", "zen_nuit", "futur",
               "sunset", "palmiers", "cyber", "teel"]
TAB_STYLES = [("pill", "Pastille"), ("box", "Cadre sombre"), ("underline", "Soulignement"),
              ("accent", "Texte coloré"), ("dot", "Point (zen)"), ("hud", "Crochets (HUD)")]
DECOS = [("none", "Aucune"), ("shoji", "Shoji (lignes de paravent)"), ("hud", "HUD (coins techniques)"),
         ("sunset", "Soleil et grille néon"), ("scanlines", "Lignes d'écran (cyber)"),
         ("stripe", "Liseré d'accent (pro)"), ("palms", "Palmiers et coucher de soleil")]


def palm_path(bx, by, height, lean):
    """Silhouette de palmier : tronc courbe qui s'affine + couronne de palmes tombantes."""
    path = QPainterPath()
    tx, ty = bx + lean * height * 0.35, by - height          # sommet du tronc
    w0, w1 = max(3.0, height * 0.055), max(1.5, height * 0.022)
    cx1, cy1 = bx + lean * height * 0.05, by - height * 0.55  # courbure
    trunk = QPainterPath()
    trunk.moveTo(bx - w0, by)
    trunk.quadTo(cx1 - w0 * 0.8, cy1, tx - w1, ty)
    trunk.lineTo(tx + w1, ty)
    trunk.quadTo(cx1 + w0 * 0.8, cy1, bx + w0, by)
    trunk.closeSubpath()
    path.addPath(trunk)
    L = height * 0.48
    for deg, droop in ((195, 0.55), (215, 0.35), (240, 0.12), (268, 0.0), (295, 0.1),
                       (322, 0.32), (345, 0.55), (165, 0.6), (15, 0.6)):
        a = math.radians(deg)
        dx, dy = math.cos(a), math.sin(a)
        ex = tx + dx * L
        ey = ty + dy * L * 0.55 + droop * L
        mx = tx + dx * L * 0.55
        my = ty + dy * L * 0.30 - L * 0.22
        nx, ny = -dy, dx
        wl = L * 0.17
        leaf = QPainterPath()
        leaf.moveTo(tx, ty)
        leaf.quadTo(mx - nx * wl, my - ny * wl, ex, ey)
        leaf.quadTo(mx + nx * wl * 0.4, my + ny * wl * 0.4 + wl, tx, ty)
        leaf.closeSubpath()
        path.addPath(leaf)
    return path


def theme_font(T, size=9, bold=False):
    f = QFont(T.get("font") or "Segoe UI", size)
    if bold:
        f.setWeight(QFont.DemiBold)
    if T.get("upper"):
        f.setLetterSpacing(QFont.PercentageSpacing, 108)
    return f


def zone_path(rect, T):
    path = QPainterPath()
    rad = T["radius"]
    if T.get("shape") == "chamfer":
        c = max(2.0, float(rad))
        x0, y0, x1, y1 = rect.left(), rect.top(), rect.right(), rect.bottom()
        path.moveTo(x0 + c, y0)
        path.lineTo(x1 - c, y0)
        path.lineTo(x1, y0 + c)
        path.lineTo(x1, y1 - c)
        path.lineTo(x1 - c, y1)
        path.lineTo(x0 + c, y1)
        path.lineTo(x0, y1 - c)
        path.lineTo(x0, y0 + c)
        path.closeSubpath()
    else:
        path.addRoundedRect(rect, rad, rad)
    return path

# Elements speciaux de Windows (pas de fichier sur le disque)
SPECIALS = {
    "recycle": ("Corbeille", "shell:RecycleBinFolder"),
    "computer": ("Ce PC", "shell:MyComputerFolder"),
    "documents": ("Documents", "shell:Personal"),
    "downloads": ("Téléchargements", "shell:Downloads"),
    "profile": ("Dossier personnel", "shell:Profile"),
    "network": ("Réseau", "shell:NetworkPlacesFolder"),
    "control": ("Panneau de configuration", "shell:ControlPanelFolder"),
    "settings": ("Paramètres Windows", "ms-settings:"),
}
# icones "systeme" du bureau (on ne peut pas les deplacer, seulement les masquer du bureau)
SPECIAL_CLSID = {
    "recycle": "{645FF040-5081-101B-9F08-00AA002F954E}",
    "computer": "{20D04FE0-3AEA-1069-A2D8-08002B30309D}",
    "network": "{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}",
    "control": "{5399E694-6CE5-4D6C-8FCE-1D8870FDCBA0}",
    "profile": "{59031A47-3F72-44A7-89C5-5595FE6B30EE}",
}


RULE_KINDS = [("folder", "Dossiers"), ("doc", "Documents (pdf, word, excel, txt...)"),
              ("image", "Images"), ("media", "Musique et vidéo"), ("archive", "Archives (zip, 7z, iso...)"),
              ("shortcut", "Raccourcis de programmes"), ("url", "Liens web"), ("name", "Nom contient…")]
TYPE_EXT = {
    "doc": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".txt", ".odt", ".ods", ".odp",
            ".csv", ".rtf", ".md", ".json", ".xml", ".log"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".svg", ".tif", ".tiff", ".ico", ".raw"},
    "media": {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    "archive": {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".iso", ".img", ".cab"},
    "shortcut": {".lnk", ".appref-ms", ".exe", ".msi", ".bat", ".cmd", ".ps1"},
    "url": {".url", ".website"},
}
IGNORE_EXT = {".tmp", ".crdownload", ".part", ".partial", ".download", ".opdownload"}


def rule_matches(rule, path):
    name = os.path.basename(path.rstrip("\\/"))
    low = name.lower()
    kind = rule.get("kind")
    isdir = os.path.isdir(path)
    if kind == "folder":
        return isdir
    if kind == "name":
        pat = (rule.get("pattern") or "").lower().strip()
        return bool(pat) and pat in low
    if isdir:
        return False
    return os.path.splitext(low)[1] in TYPE_EXT.get(kind, ())


def rgba(t, a=None):
    return QColor(t[0], t[1], t[2], t[3] if a is None and len(t) > 3 else (255 if a is None else a))


# largeur, hauteur, taille d'icone
SIZES = {"small": (70, 74, 32), "medium": (82, 86, 40), "large": (100, 100, 48)}
SIZE_LABELS = [("small", "Petites"), ("medium", "Moyennes"), ("large", "Grandes")]

EDGE = 5             # zone de redimensionnement / marge
TITLE_H = 36         # hauteur de la barre d'onglets (marge haute incluse)
GAP, PAD = 2, 8
SNAP_DIST = 14      # distance d'aimantation (px)
ZONE_GAP = 8       # espace entre deux zones collees / avec le bord d'ecran
RADIUS = 8
MIN_W, MIN_H = 180, TITLE_H + 70

MENU_CSS = """
QMenu { background:#1C1E25; color:#E5E7EB; border:1px solid #33374A; padding:5px; }
QMenu::item { padding:6px 26px 6px 26px; border-radius:5px; }
QMenu::item:selected { background:#2E3342; }
QMenu::item:disabled { color:#5B6170; }
QMenu::separator { height:1px; background:#33374A; margin:5px 8px; }
QMenu::icon { padding-left:6px; }
"""

SCROLL_CSS = """
QScrollArea { background:transparent; border:none; }
QScrollArea > QWidget > QWidget { background:transparent; }
QScrollBar:vertical { background:transparent; width:7px; margin:3px 1px; }
QScrollBar::handle:vertical { background:rgba(255,255,255,45); border-radius:3px; min-height:24px; }
QScrollBar::handle:vertical:hover { background:rgba(255,255,255,90); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
"""


# --------------------------------------------------------------------------- utilitaires

def desktop_dirs():
    dirs = []
    d = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
    if d:
        dirs.append(d)
    pub = os.environ.get("PUBLIC")
    if pub:
        dirs.append(os.path.join(pub, "Desktop"))
    return [os.path.normcase(os.path.abspath(x)) for x in dirs]


def user_desktop():
    return QStandardPaths.writableLocation(QStandardPaths.DesktopLocation) or os.path.expanduser("~")


def is_on_desktop(path):
    return os.path.normcase(os.path.dirname(os.path.abspath(path))) in desktop_dirs()


def is_in_store(path):
    return os.path.normcase(os.path.abspath(path)).startswith(
        os.path.normcase(os.path.abspath(STORE_DIR)) + os.sep)


def unique_path(folder, name):
    base, ext = os.path.splitext(name)
    cand = os.path.join(folder, name)
    i = 2
    while os.path.exists(cand):
        cand = os.path.join(folder, f"{base} ({i}){ext}")
        i += 1
    return cand


def display_name(path):
    name = os.path.basename(path.rstrip("\\/")) or path
    root, ext = os.path.splitext(name)
    if ext.lower() in (".lnk", ".url", ".appref-ms"):
        root = root.replace(" - Raccourci", "").replace(" - Shortcut", "")
        return root
    return name


def same_path(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def screen_id(s):
    sid = " ".join(x for x in (s.manufacturer(), s.model(), s.serialNumber()) if x).strip()
    return sid or s.name()


def screens_sig():
    parts = []
    for s in QGuiApplication.screens():
        g = s.geometry()
        parts.append(f"{screen_id(s)}@{g.x()},{g.y()},{g.width()}x{g.height()}")
    return "|".join(sorted(parts))


_icon_provider = None
_icon_cache = {}


def icon_for(path):
    global _icon_provider
    key = os.path.normcase(path)
    ic = _icon_cache.get(key)
    if ic is None:
        if _icon_provider is None:
            _icon_provider = QFileIconProvider()
        ic = _icon_provider.icon(QFileInfo(path))
        _icon_cache[key] = ic
    return ic


def _win_icon_to_qicon(hicon, size=48):
    """Convertit une HICON Windows en QIcon (via un bitmap 32 bits)."""
    from ctypes import wintypes
    gdi, u = ctypes.windll.gdi32, ctypes.windll.user32

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]
    bih = BIH(ctypes.sizeof(BIH), size, -size, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    gdi.CreateDIBSection.restype = ctypes.c_void_p
    gdi.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                     ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint]
    gdi.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi.DeleteDC.argtypes = [ctypes.c_void_p]
    u.DrawIconEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
                             ctypes.c_int, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    dc = gdi.CreateCompatibleDC(None)
    bmp = gdi.CreateDIBSection(dc, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0)
    old = gdi.SelectObject(dc, bmp)
    ctypes.memset(bits, 0, size * size * 4)
    u.DrawIconEx(dc, 0, 0, ctypes.c_void_p(hicon), size, size, 0, None, 3)   # DI_NORMAL
    raw = ctypes.string_at(bits, size * size * 4)
    gdi.SelectObject(dc, old)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(dc)
    img = QImage(raw, size, size, QImage.Format_ARGB32_Premultiplied).copy()
    return QIcon(QPixmap.fromImage(img))


def win_shell_icon(parsing_name):
    """Vraie icone Windows d'un objet du shell (ex. '::{CLSID}' pour la Corbeille), en 48 px."""
    if not IS_WIN:
        return None
    try:
        from ctypes import wintypes
        sh = ctypes.windll.shell32
        pidl = ctypes.c_void_p()
        sh.SHParseDisplayName.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
                                          ctypes.c_ulong, ctypes.c_void_p]
        if sh.SHParseDisplayName(parsing_name, None, ctypes.byref(pidl), 0, None) != 0:
            return None

        class SHFILEINFOW(ctypes.Structure):
            _fields_ = [("hIcon", ctypes.c_void_p), ("iIcon", ctypes.c_int), ("dwAttributes", wintypes.DWORD),
                        ("szDisplayName", ctypes.c_wchar * 260), ("szTypeName", ctypes.c_wchar * 80)]
        sfi = SHFILEINFOW()
        sh.SHGetFileInfoW.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
        sh.SHGetFileInfoW(pidl, 0, ctypes.byref(sfi), ctypes.sizeof(sfi), 0x4000 | 0x8)  # SYSICONINDEX|PIDL
        ctypes.windll.ole32.CoTaskMemFree(pidl)

        class GUID(ctypes.Structure):
            _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD),
                        ("d4", ctypes.c_ubyte * 8)]
        iid = GUID(0x46EB5926, 0x582E, 0x4017, (ctypes.c_ubyte * 8)(0x9F, 0xDF, 0xE8, 0x99, 0x8D, 0xAA, 0x09, 0x50))
        himl = ctypes.c_void_p()
        sh.SHGetImageList.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        if sh.SHGetImageList(2, ctypes.byref(iid), ctypes.byref(himl)) != 0:   # SHIL_EXTRALARGE (48 px)
            return None
        cc = ctypes.windll.comctl32
        cc.ImageList_GetIcon.restype = ctypes.c_void_p
        cc.ImageList_GetIcon.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint]
        hicon = cc.ImageList_GetIcon(himl, sfi.iIcon, 1)    # ILD_TRANSPARENT
        if not hicon:
            return None
        ic = _win_icon_to_qicon(hicon, 48)
        ctypes.windll.user32.DestroyIcon(ctypes.c_void_p(hicon))
        return ic
    except Exception:
        return None


def win_shell_names_from_drop(md):
    """Lit le format 'Shell IDList Array' d'un glisser-deposer et rend les noms d'analyse (ex. '::{CLSID}')."""
    if not IS_WIN:
        return []
    fmt = next((f for f in md.formats() if "Shell IDList" in f), None)
    if not fmt:
        return []
    try:
        b = bytes(md.data(fmt))
        cidl = struct.unpack_from("<I", b, 0)[0]
        offs = struct.unpack_from(f"<{cidl + 1}I", b, 4)
        sh = ctypes.windll.shell32
        sh.ILCombine.restype = ctypes.c_void_p
        sh.ILCombine.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        sh.SHGetNameFromIDList.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_wchar_p)]
        sh.ILFree.argtypes = [ctypes.c_void_p]
        parent = ctypes.create_string_buffer(b[offs[0]:])
        names = []
        for o in offs[1:]:
            child = ctypes.create_string_buffer(b[o:])
            full = sh.ILCombine(ctypes.cast(parent, ctypes.c_void_p), ctypes.cast(child, ctypes.c_void_p))
            out = ctypes.c_wchar_p()
            # SIGDN_DESKTOPABSOLUTEPARSING
            if full and sh.SHGetNameFromIDList(full, ctypes.c_int(0x80028000 - (1 << 32)), ctypes.byref(out)) == 0:
                names.append(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)
            if full:
                sh.ILFree(full)
        return names
    except Exception:
        return []


def special_from_name(name):
    up = (name or "").upper()
    for key, clsid in SPECIAL_CLSID.items():
        if clsid in up:
            return key
    return None


def win_set_desktop_ns_icon(clsid, visible):
    """Affiche / masque une icone systeme du bureau (meme reglage que 'Parametres des icones du bureau')."""
    if not IS_WIN:
        return
    import winreg
    for sub in ("NewStartPanel", "ClassicStartMenu"):
        key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\HideDesktopIcons" + "\\" + sub
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, clsid, 0, winreg.REG_DWORD, 0 if visible else 1)
        except OSError:
            pass
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x1000, None, None)   # rafraichit le bureau
    except Exception:
        pass


def special_icon(key):
    if key in SPECIAL_CLSID:
        ic = win_shell_icon("::" + SPECIAL_CLSID[key])
        if ic is not None:
            return ic
    global _icon_provider
    if _icon_provider is None:
        _icon_provider = QFileIconProvider()
    T = QAbstractFileIconProvider.IconType
    if key == "recycle":
        return _icon_provider.icon(T.Trashcan)
    if key == "computer":
        return _icon_provider.icon(T.Computer)
    if key == "network":
        return _icon_provider.icon(T.Network)
    if key in ("documents", "downloads", "profile"):
        loc = {"documents": QStandardPaths.DocumentsLocation, "downloads": QStandardPaths.DownloadLocation,
               "profile": QStandardPaths.HomeLocation}[key]
        path = QStandardPaths.writableLocation(loc)
        if path:
            return icon_for(path)
    return _icon_provider.icon(T.Desktop)


TATAMI_MATS = [(8, 8, 32, 15), (42, 8, 14, 32), (24, 41, 32, 15), (8, 25, 14, 31)]
TATAMI_CENTER = (24, 25, 16, 14)


def make_app_icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(30, 32, 40))
    p.drawRoundedRect(QRectF(2, 2, 60, 60), 12, 12)
    # disposition de tatamis "en moulinet" autour d'un demi-tatami central
    p.setBrush(QColor(205, 191, 142))
    for x, y, w, h in TATAMI_MATS:
        p.drawRoundedRect(QRectF(x, y, w, h), 2, 2)
    p.setBrush(QColor(200, 53, 43))
    p.drawRoundedRect(QRectF(*TATAMI_CENTER), 2, 2)
    p.end()
    return QIcon(pix)


def color_icon(col):
    pix = QPixmap(14, 14)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(col))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, 12, 12)
    p.end()
    return QIcon(pix)


# --------------------------------------------------------------------------- Windows

def _hwnd(widget):
    return ctypes.c_void_p(int(widget.winId()))


def win_push_bottom(widget):
    """Place la zone tout en bas de la pile (juste au-dessus du bureau)."""
    if not IS_WIN:
        return
    try:
        # HWND_BOTTOM=1, SWP_NOSIZE|SWP_NOMOVE|SWP_NOACTIVATE
        ctypes.windll.user32.SetWindowPos(_hwnd(widget), ctypes.c_void_p(1), 0, 0, 0, 0, 0x0013)
    except Exception:
        pass


def win_attach_desktop(widget):
    """Rattache la zone au bureau (Progman) pour qu'elle survive a Win+D."""
    if not IS_WIN:
        return
    try:
        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        progman = user32.FindWindowW("Progman", None)
        if progman:
            setwl = user32.SetWindowLongPtrW
            setwl.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            setwl.restype = ctypes.c_void_p
            setwl(_hwnd(widget), -8, ctypes.c_void_p(progman))  # GWLP_HWNDPARENT
    except Exception:
        pass


class _AccentPolicy(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class _WinCompAttrData(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t)]


def win_blur(widget, on):
    """Flou d'arriere-plan gere par Windows (DWM) : aucun calcul cote application."""
    if not IS_WIN:
        return
    try:
        accent = _AccentPolicy(3 if on else 0, 0, 0, 0)   # 3 = ACCENT_ENABLE_BLURBEHIND
        data = _WinCompAttrData(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p),
                                ctypes.sizeof(accent))  # 19 = WCA_ACCENT_POLICY
        ctypes.windll.user32.SetWindowCompositionAttribute(_hwnd(widget), ctypes.byref(data))
    except Exception:
        pass
    try:
        pref = ctypes.c_int(2)  # DWMWCP_ROUND (Windows 11)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(_hwnd(widget), 33, ctypes.byref(pref), 4)
    except Exception:
        pass


# --- Quick-hide : double-clic sur le bureau vide -> masque icones et/ou zones

def _win_class(hwnd):
    buf = ctypes.create_unicode_buffer(64)
    ctypes.windll.user32.GetClassNameW(ctypes.c_void_p(hwnd), buf, 64)
    return buf.value


def desktop_listview():
    """Fenetre qui contient les icones du bureau (SysListView32 dans SHELLDLL_DefView)."""
    if not IS_WIN:
        return None
    u = ctypes.windll.user32
    u.FindWindowW.restype = ctypes.c_void_p
    u.FindWindowExW.restype = ctypes.c_void_p
    u.FindWindowExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
    defview = None
    progman = u.FindWindowW("Progman", None)
    if progman:
        defview = u.FindWindowExW(progman, None, "SHELLDLL_DefView", None)
    w = None
    while not defview:
        w = u.FindWindowExW(None, w, "WorkerW", None)
        if not w:
            break
        defview = u.FindWindowExW(w, None, "SHELLDLL_DefView", None)
    if not defview:
        return None
    return u.FindWindowExW(defview, None, "SysListView32", None)


class DesktopDoubleClick:
    """Hook souris bas niveau : ne fait que comparer deux clics, aucun calcul en continu."""

    def __init__(self, on_double):
        self.on_double = on_double
        self.hook = None
        self.last_t = 0
        self.last_pt = (0, 0)
        if not IS_WIN:
            return
        from ctypes import wintypes
        self.wintypes = wintypes

        class MSLL(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long), ("mouseData", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD), ("extra", ctypes.c_void_p)]
        self.MSLL = MSLL
        proto = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        u = ctypes.windll.user32
        u.SetWindowsHookExW.argtypes = [ctypes.c_int, proto, ctypes.c_void_p, wintypes.DWORD]
        u.SetWindowsHookExW.restype = ctypes.c_void_p
        u.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        u.CallNextHookEx.restype = ctypes.c_ssize_t
        u.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        self.dbl_ms = u.GetDoubleClickTime()
        self.dx = u.GetSystemMetrics(36)   # SM_CXDOUBLECLK
        self.dy = u.GetSystemMetrics(37)
        self._proc = proto(self._callback)   # garder une reference

    def start(self):
        if IS_WIN and not self.hook:
            self.hook = ctypes.windll.user32.SetWindowsHookExW(14, self._proc, None, 0)  # WH_MOUSE_LL

    def stop(self):
        if IS_WIN and self.hook:
            ctypes.windll.user32.UnhookWindowsHookEx(self.hook)
            self.hook = None

    def _callback(self, code, wparam, lparam):
        if code == 0 and wparam == 0x0201:     # WM_LBUTTONDOWN
            info = ctypes.cast(lparam, ctypes.POINTER(self.MSLL)).contents
            t, x, y = info.time, info.x, info.y
            if (t - self.last_t) <= self.dbl_ms and abs(x - self.last_pt[0]) <= self.dx \
                    and abs(y - self.last_pt[1]) <= self.dy:
                self.last_t = 0
                QTimer.singleShot(90, lambda: self._check(x, y))
            else:
                self.last_t, self.last_pt = t, (x, y)
        return ctypes.windll.user32.CallNextHookEx(None, code, wparam, lparam)

    def _check(self, x, y):
        u = ctypes.windll.user32
        u.WindowFromPoint.restype = ctypes.c_void_p
        u.WindowFromPoint.argtypes = [self.wintypes.POINT]
        u.GetParent.restype = ctypes.c_void_p
        u.GetParent.argtypes = [ctypes.c_void_p]
        hwnd = u.WindowFromPoint(self.wintypes.POINT(x, y))
        if not hwnd:
            return
        cls = _win_class(hwnd)
        if cls == "SysListView32":
            parent = u.GetParent(hwnd)
            if not parent or _win_class(parent) != "SHELLDLL_DefView":
                return
            # double-clic sur une icone = elle est selectionnee -> on ne masque pas
            if u.SendMessageW(ctypes.c_void_p(hwnd), 0x1032, 0, 0) != 0:   # LVM_GETSELECTEDCOUNT
                return
        elif cls not in ("SHELLDLL_DefView", "WorkerW", "Progman"):
            return
        self.on_double()


def set_desktop_icons_visible(on):
    lv = desktop_listview()
    if lv:
        ctypes.windll.user32.ShowWindow(ctypes.c_void_p(lv), 5 if on else 0)


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def migrate_old_install():
    """Reprend la configuration de la version de developpement (ancien nom) si elle existe."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    old_dir = os.path.join(base, OLD_ID)
    if not os.path.isdir(old_dir) or os.path.exists(DATA_DIR):
        return
    try:
        shutil.move(old_dir, DATA_DIR)
    except OSError:
        return
    # les chemins des elements ranges pointent vers l'ancien dossier : on les corrige
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        old_n = os.path.normcase(os.path.abspath(old_dir))

        def fix(path):
            if os.path.normcase(os.path.abspath(path)).startswith(old_n + os.sep):
                return os.path.join(DATA_DIR, os.path.abspath(path)[len(old_n) + 1:])
            return path
        for z in cfg.get("f" + "ences", []) + cfg.get("zones", []):
            for t in z.get("tabs", []):
                for it in t.get("items", []):
                    if not it.get("special"):
                        it["path"] = fix(it["path"])
        if "f" + "ences" in cfg:
            cfg["zones"] = cfg.pop("f" + "ences")
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    if IS_WIN:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as k:
                try:
                    winreg.QueryValueEx(k, OLD_ID)
                    winreg.DeleteValue(k, OLD_ID)
                    winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, startup_command())
                except OSError:
                    pass
        except OSError:
            pass
        old_lnk = os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs", OLD_ID + ".lnk")
        try:
            os.remove(old_lnk)
        except OSError:
            pass


def startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = sys.executable
    pw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pw):
        exe = pw
    return f'"{exe}" "{os.path.abspath(sys.argv[0])}"'


def get_startup():
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_ID)
            return True
    except OSError:
        return False


def set_startup(on):
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(k, APP_ID)
            except OSError:
                pass


# --------------------------------------------------------------------------- menu qui reste ouvert

class StickyMenu(QMenu):
    """Sous-menu de choix (theme, taille, couleur) : cliquer applique sans fermer le menu."""

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setStyleSheet(MENU_CSS)

    def mouseReleaseEvent(self, e):
        a = self.actionAt(e.position().toPoint())
        if a is not None and a.isEnabled() and a.property("sticky"):
            a.trigger()
            return
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        a = self.activeAction()
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and a is not None and a.property("sticky"):
            a.trigger()
            return
        super().keyPressEvent(e)


def sticky_submenu(parent_menu, title):
    sm = StickyMenu(title, parent_menu)
    parent_menu.addMenu(sm)
    return sm


def make_sticky(action):
    action.setProperty("sticky", True)
    return action


# --------------------------------------------------------------------------- icone

class Tile(QWidget):
    def __init__(self, zone, item):
        super().__init__(zone.grid)
        self.zone = zone
        self.item = item
        self.path = item["path"]
        self.special = item.get("special")
        if self.special:
            self.exists = True
            self.icon = special_icon(self.special)
            self.text = SPECIALS.get(self.special, ("?", ""))[0]
        else:
            self.exists = os.path.exists(self.path)
            self.icon = icon_for(self.path)
            self.text = display_name(self.path)
        self.hover = False
        self.press_pos = None
        self._elided = None
        self._font = None
        self._flags = Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap
        tw, th, _ = zone.app.tile
        self.setFixedSize(tw, th)
        self.setToolTip(self.text if self.special else
                        (self.path if self.exists else f"Introuvable : {self.path}"))

    def elided(self, fm, width, height=1000):
        if self._elided is not None:
            return self._elided
        if any(fm.horizontalAdvance(w) > width for w in self.text.split()):
            self._flags = Qt.AlignHCenter | Qt.AlignTop | Qt.TextWrapAnywhere
        maxh = min(fm.lineSpacing() * 2 + 4, height + 3)
        box = QRect(0, 0, width, 1000)
        t = self.text
        if fm.boundingRect(box, self._flags, t).height() > maxh:
            while len(t) > 1 and fm.boundingRect(box, self._flags, t + "…").height() > maxh:
                t = t[:-1]
            t = t.rstrip() + "…"
        self._elided = t
        return t

    def paintEvent(self, e):
        _, _, isz = self.zone.app.tile
        T = self.zone.app.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.hover:
            hv = T["tile_hover"]
            p.setPen(QPen(rgba(hv, min(255, hv[3] + 14)), 1))
            p.setBrush(rgba(hv))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5), 7, 7)
        if not self.exists:
            p.setOpacity(0.35)
        top = 6
        self.icon.paint(p, QRect((self.width() - isz) // 2, top, isz, isz))
        tr = QRect(3, top + isz + 4, self.width() - 6, self.height() - (top + isz + 4))
        if self._font is None:
            # certaines polices (ex. Yu Mincho) ont un grand interligne : on reduit pour garder 2 lignes
            f = theme_font(T)
            size = f.pointSizeF()
            while QFontMetrics(f).lineSpacing() * 2 > tr.height() + 1 and size > 7:
                size -= 0.5
                f.setPointSizeF(size)
            self._font = f
        p.setFont(self._font)
        txt = self.elided(p.fontMetrics(), tr.width(), tr.height())
        if T["shadow"]:
            p.setPen(QColor(0, 0, 0, 200))
            p.drawText(tr.translated(0, 1), self._flags, txt)
        p.setPen(rgba(T["text"]))
        p.drawText(tr, self._flags, txt)

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.press_pos = e.position().toPoint()

    def mouseReleaseEvent(self, e):
        self.press_pos = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.zone.app.launch(self.path)

    def mouseMoveEvent(self, e):
        if self.press_pos is None or not (e.buttons() & Qt.LeftButton):
            return
        if (e.position().toPoint() - self.press_pos).manhattanLength() < QApplication.startDragDistance():
            return
        self.press_pos = None
        self.start_drag()

    def start_drag(self):
        app = self.zone.app
        md = QMimeData()
        if not self.special:
            md.setUrls([QUrl.fromLocalFile(self.path)])
        md.setData(MIME, json.dumps({"path": self.path}).encode("utf-8"))
        self.hover = False
        drag = QDrag(self.zone)
        drag.setMimeData(md)
        drag.setPixmap(self.grab())
        drag.setHotSpot(QPoint(self.width() // 2, self.height() // 2))
        app.pending = None
        app.drag_tile = self
        drag.exec(Qt.CopyAction | Qt.MoveAction | Qt.LinkAction, Qt.MoveAction)
        app.drag_tile = None
        if app.pending:
            app.run_pending()
        elif not self.special and not os.path.exists(self.path):
            # deplace ailleurs par l'Explorateur (ex: reglisse sur le bureau)
            app.ignore_names.add(os.path.basename(self.path.rstrip("\\/")).lower())
            app.remove_item(self.path, restore=False)
        if self not in self.zone.grid.tiles:
            self.deleteLater()

    def contextMenuEvent(self, e):
        app = self.zone.app
        path = self.path
        m = app.menu(self)
        m.addAction("Ouvrir", lambda: app.launch(path))
        if self.special == "recycle":
            m.addAction("Vider la corbeille", app.empty_recycle_bin)
        elif not self.special:
            m.addAction("Ouvrir l'emplacement", lambda: app.reveal(path))
        tabs = self.zone.data["tabs"]
        if len(tabs) > 1:
            mv = m.addMenu("Déplacer vers l'onglet")
            mv.setStyleSheet(MENU_CSS)
            for i, t in enumerate(tabs):
                if i != self.zone.active():
                    mv.addAction(t["name"], lambda _=False, ti=i: app.move_item(path, self.zone.fid, ti, None))
        m.addSeparator()
        if self.item.get("origin") or self.item.get("hid_desktop"):
            m.addAction("Remettre sur le bureau", lambda: app.remove_item(path, restore=True))
        elif self.special:
            m.addAction("Retirer de la zone", lambda: app.remove_item(path, restore=False))
        else:
            m.addAction("Retirer de la zone", lambda: app.remove_item(path, restore=False))
        m.exec(e.globalPos())
        e.accept()


# --------------------------------------------------------------------------- grille

class Grid(QWidget):
    def __init__(self, zone):
        super().__init__()
        self.zone = zone
        self.tiles = []
        self.indicator = None

    def set_tiles(self, tiles):
        drag_tile = self.zone.app.drag_tile
        for t in self.tiles:
            t.hide()
            if t is not drag_tile:      # la tuile en cours de glisser est supprimee apres le drag
                t.deleteLater()
        self.tiles = tiles
        for t in tiles:
            t.setParent(self)
            t.show()
        self.relayout()

    def step(self):
        tw, th, _ = self.zone.app.tile
        return tw + GAP, th + GAP

    def cols(self):
        sx, _ = self.step()
        return max(1, (self.width() - 2 * PAD + GAP) // sx)

    def relayout(self):
        c = self.cols()
        sx, sy = self.step()
        for i, t in enumerate(self.tiles):
            r, k = divmod(i, c)
            t.move(PAD + k * sx, PAD + r * sy)
        rows = (len(self.tiles) + c - 1) // c
        self.setMinimumHeight(PAD * 2 + rows * sy)
        self.update()

    def resizeEvent(self, e):
        self.relayout()

    def index_at(self, pos):
        c = self.cols()
        n = len(self.tiles)
        sx, sy = self.step()
        col = max(0, min(c, int(round((pos.x() - PAD) / sx))))
        row = max(0, int((pos.y() - PAD) // sy))
        return max(0, min(n, row * c + col))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.tiles and not self.zone.merge_hint:
            p.setPen(rgba(self.zone.app.theme["text"], 110))
            p.drawText(self.visibleRegion().boundingRect(), Qt.AlignCenter | Qt.TextWordWrap,
                       "Glisse tes raccourcis ici")
        if self.indicator is not None:
            c = self.cols()
            sx, sy = self.step()
            idx, n = self.indicator, len(self.tiles)
            if idx == n and n > 0 and idx % c == 0:
                r, k = (idx - 1) // c, c
            else:
                r, k = divmod(idx, c)
            x = PAD + k * sx - GAP / 2 - 1.5
            y = PAD + r * sy + 6
            p.setPen(Qt.NoPen)
            p.setBrush(self.zone.app.accent_for(self.zone))
            p.drawRoundedRect(QRectF(x, y, 3, sy - GAP - 12), 1.5, 1.5)


# --------------------------------------------------------------------------- barre d'onglets

class TabBar(QWidget):
    PLUS_W = 26

    def __init__(self, zone):
        super().__init__(zone)
        self.zone = zone
        self.setFixedHeight(TITLE_H - EDGE)
        self.setMouseTracking(True)
        self.bar_hover = False
        self.hover_idx = None
        self.hover_plus = False
        self.press = None
        self.drag_off = None
        self.moving = False
        self.edit_idx = None
        self.edit = QLineEdit(self)
        self.edit.setAlignment(Qt.AlignCenter)
        self.edit.setStyleSheet("QLineEdit{color:#F1F5F9; background:rgba(0,0,0,110);"
                                "border:1px solid rgba(255,255,255,70); border-radius:5px; padding:0 6px;}")
        self.edit.hide()
        self.edit.editingFinished.connect(self.finish_edit)

    def tabs(self):
        return self.zone.data["tabs"]

    def tab_rects(self):
        n = len(self.tabs())
        if n <= 1:
            return [QRectF(0, 0, self.width(), self.height())]
        tw = (self.width() - self.PLUS_W) / n
        return [QRectF(i * tw, 0, tw, self.height()) for i in range(n)]

    def plus_rect(self):
        return QRectF(self.width() - self.PLUS_W, 0, self.PLUS_W, self.height())

    def plus_visible(self):
        return self.bar_hover and not self.zone.app.locked

    def index_at(self, pos):
        pf = QPointF(pos)
        if len(self.tabs()) > 1 and self.plus_rect().contains(pf):
            return None
        for i, r in enumerate(self.tab_rects()):
            if r.contains(pf):
                return i
        return None

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tabs = self.tabs()
        n = len(tabs)
        act = self.zone.active()
        T = self.zone.app.theme
        accent = self.zone.app.accent_for(self.zone)
        base = theme_font(T)
        bold = theme_font(T, bold=True)
        tc = T["text"]
        style = T["tab"]
        rects = self.tab_rects()
        if n > 1:
            # separateurs entre onglets + fond leger au survol
            p.setPen(QPen(rgba(tc, 45), 1))
            for i in range(1, n):
                x = round(rects[i].left()) + 0.5
                p.drawLine(QPointF(x, rects[i].top() + 9), QPointF(x, rects[i].bottom() - 7))
            if self.hover_idx is not None and self.hover_idx != act and self.hover_idx < n:
                p.setPen(Qt.NoPen)
                p.setBrush(rgba(tc, 14))
                p.drawRoundedRect(rects[self.hover_idx].adjusted(3, 4, -3, -3), 5, 5)
        for i, (r, t) in enumerate(zip(rects, tabs)):
            if i == self.edit_idx:
                continue
            is_act = (i == act)
            if n > 1 and is_act:
                p.setPen(Qt.NoPen)
                if style == "pill":
                    p.setBrush(rgba(tc, 24))
                    p.drawRoundedRect(r.adjusted(3, 4, -3, -3), 6, 6)
                    p.setBrush(accent)
                    p.drawRoundedRect(QRectF(r.center().x() - 14, r.bottom() - 4, 28, 2.5), 1.2, 1.2)
                elif style == "box":
                    p.setBrush(QColor(0, 0, 0, 110))
                    p.drawRect(r.adjusted(2, 2, -2, 0))
                elif style == "underline":
                    p.setBrush(accent)
                    p.drawRoundedRect(QRectF(r.left() + 10, r.bottom() - 3, r.width() - 20, 2), 1, 1)
                elif style == "dot":
                    p.setBrush(accent)
                    p.drawEllipse(QPointF(r.center().x(), r.bottom() - 4), 2.6, 2.6)
                elif style == "hud":
                    p.setPen(QPen(accent, 1.2))
                    p.setBrush(Qt.NoBrush)
                    q = r.adjusted(5, 5, -5, -4)
                    k = 6
                    for (x, y, dx, dy) in ((q.left(), q.top(), 1, 1), (q.right(), q.top(), -1, 1),
                                           (q.left(), q.bottom(), 1, -1), (q.right(), q.bottom(), -1, -1)):
                        p.drawLine(QPointF(x, y), QPointF(x + dx * k, y))
                        p.drawLine(QPointF(x, y), QPointF(x, y + dy * k))
            if n == 1 or is_act:
                p.setFont(bold)
                p.setPen(accent if (style in ("accent", "hud") and n > 1) else rgba(tc))
            else:
                p.setFont(base)
                p.setPen(rgba(tc, min(255, T["inactive"] + 75) if i == self.hover_idx else T["inactive"]))
            name = t["name"].upper() if T.get("upper") else t["name"]
            txt = QFontMetrics(p.font()).elidedText(name, Qt.ElideRight, int(r.width()) - 12)
            p.drawText(r, Qt.AlignCenter, txt)
        if self.plus_visible():
            pr = self.plus_rect()
            if self.hover_plus:
                p.setPen(Qt.NoPen)
                p.setBrush(rgba(tc, 30))
                p.drawRoundedRect(pr.adjusted(3, 6, -3, -5), 5, 5)
            p.setPen(QPen(rgba(tc, 220 if self.hover_plus else 120), 1.6))
            c = pr.center()
            p.drawLine(QPointF(c.x() - 5, c.y()), QPointF(c.x() + 5, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - 5), QPointF(c.x(), c.y() + 5))

    # -- souris
    def enterEvent(self, e):
        self.bar_hover = True
        self.update()

    def leaveEvent(self, e):
        self.bar_hover = False
        self.hover_idx = None
        self.hover_plus = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.press = e.globalPosition().toPoint()
            self.drag_off = self.press - self.zone.pos()
            self.moving = False

    def mouseMoveEvent(self, e):
        if self.press is not None and (e.buttons() & Qt.LeftButton):
            gp = e.globalPosition().toPoint()
            if (not self.moving and not self.zone.app.locked
                    and (gp - self.press).manhattanLength() >= QApplication.startDragDistance()):
                self.moving = True
            if self.moving:
                p = gp - self.drag_off
                if self.zone.app.snap_on and not (QApplication.keyboardModifiers() & Qt.ShiftModifier):
                    p = self.zone.app.snap_move(self.zone, p)
                self.zone.move(p)
                self.zone.app.update_merge_target(self.zone, gp)
            return
        pos = e.position().toPoint()
        hp = self.plus_visible() and self.plus_rect().contains(QPointF(pos))
        hi = None if hp else self.index_at(pos)
        if hp != self.hover_plus or hi != self.hover_idx:
            self.hover_plus, self.hover_idx = hp, hi
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self.press is None:
            return
        was_moving = self.moving
        self.press = None
        self.moving = False
        if was_moving:
            app = self.zone.app
            if app.merge_target is not None:
                app.merge_zones(self.zone, app.merge_target)
                return
            app.save_soon()
            win_push_bottom(self.zone)
            return
        pos = e.position().toPoint()
        if self.plus_visible() and self.plus_rect().contains(QPointF(pos)):
            self.zone.add_tab()
            return
        i = self.index_at(pos)
        if i is not None and i != self.zone.active():
            self.zone.set_active(i)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton and not (self.plus_visible() and self.plus_rect().contains(e.position())):
            self.zone.toggle_collapse()

    def contextMenuEvent(self, e):
        self.zone.show_menu(e.globalPos(), self.index_at(e.pos()))
        e.accept()

    # -- renommage
    def start_edit(self, i):
        if i is None or i >= len(self.tabs()):
            return
        r = self.tab_rects()[i].toRect().adjusted(6, 4, -6, -3)
        self.edit_idx = i
        self.edit.setGeometry(r)
        self.edit.setText(self.tabs()[i]["name"])
        self.edit.show()
        self.zone.activateWindow()
        self.edit.setFocus()
        self.edit.selectAll()
        self.update()

    def finish_edit(self):
        if self.edit_idx is None:
            return
        i, self.edit_idx = self.edit_idx, None
        self.edit.hide()
        if i < len(self.tabs()):
            self.tabs()[i]["name"] = self.edit.text().strip() or "Onglet"
        self.update()
        self.zone.app.save_soon()

    def resizeEvent(self, e):
        if self.edit_idx is not None:
            self.edit.setGeometry(self.tab_rects()[self.edit_idx].toRect().adjusted(6, 4, -6, -3))


# --------------------------------------------------------------------------- zone

class PerfWidget(QWidget):
    """Widget natif de monitoring des performances PC (CPU, RAM, Réseau, Disque)."""
    def __init__(self, zone):
        super().__init__(zone)
        self.zone = zone
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.ArrowCursor)
        self.cpu = 0.0
        self.ram_pct = 0.0
        self.ram_used = 0.0
        self.ram_total = 0.0
        self.disk_pct = 0.0
        self.disk_used = 0.0
        self.disk_total = 0.0
        self.net_up = 0.0
        self.net_down = 0.0
        self._last_net = psutil.net_io_counters()
        self._last_t = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._sample)
        if QApplication.instance():
            QApplication.instance().aboutToQuit.connect(self.timer.stop)

    def set_active(self, on):
        if on:
            if not self.timer.isActive():
                psutil.cpu_percent(interval=None)
                self._last_net = psutil.net_io_counters()
                self._last_t = time.monotonic()
                self._sample()
                self.timer.start()
        else:
            self.timer.stop()

    def _sample(self):
        if not self.isVisible():
            return
        self.cpu = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        self.ram_pct = vm.percent
        self.ram_used = vm.used / (1024 ** 3)
        self.ram_total = vm.total / (1024 ** 3)
        try:
            du = psutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
            self.disk_pct = du.percent
            self.disk_used = du.used / (1024 ** 3)
            self.disk_total = du.total / (1024 ** 3)
        except Exception:
            pass
        now = time.monotonic()
        net = psutil.net_io_counters()
        dt = max(0.1, now - self._last_t)
        self.net_up = max(0.0, (net.bytes_sent - self._last_net.bytes_sent) / dt)
        self.net_down = max(0.0, (net.bytes_recv - self._last_net.bytes_recv) / dt)
        self._last_net = net
        self._last_t = now
        self.update()

    @staticmethod
    def _fmt_rate(bps):
        if bps < 1024:
            return f"{bps:.0f} B/s"
        if bps < 1024 ** 2:
            return f"{bps / 1024:.1f} KB/s"
        return f"{bps / (1024 ** 2):.2f} MB/s"

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        T = self.zone.app.theme
        accent = QColor(self.zone.app.accent_for(self.zone))
        txt_col = rgba(T["text"])
        sub_col = rgba(T["text"], 170)
        track_col = rgba(T["text"], 35)

        w = self.width()
        pad = 12
        bar_w = max(40, w - pad * 2)

        f_lbl = QFont(self.zone.app.font_name, 9, QFont.DemiBold)
        f_val = QFont(self.zone.app.font_name, 9)

        rows = [
            ("CPU", f"{self.cpu:.0f}%", self.cpu / 100.0),
            ("RAM", f"{self.ram_used:.1f} / {self.ram_total:.0f} Go ({self.ram_pct:.0f}%)", self.ram_pct / 100.0),
            ("Disque C:", f"{self.disk_used:.0f} / {self.disk_total:.0f} Go ({self.disk_pct:.0f}%)", self.disk_pct / 100.0),
        ]

        y = 10
        for label, val, ratio in rows:
            p.setFont(f_lbl)
            p.setPen(txt_col)
            p.drawText(QRect(pad, y, bar_w // 2, 16), Qt.AlignLeft | Qt.AlignVCenter, label)
            p.setFont(f_val)
            p.setPen(sub_col)
            p.drawText(QRect(pad, y, bar_w, 16), Qt.AlignRight | Qt.AlignVCenter, val)
            y += 18

            # barre de progression
            p.setPen(Qt.NoPen)
            p.setBrush(track_col)
            p.drawRoundedRect(QRectF(pad, y, bar_w, 6), 3, 3)
            fill_col = QColor("#E05252") if ratio > 0.85 else (QColor("#E6A23C") if ratio > 0.65 else accent)
            p.setBrush(fill_col)
            fw = max(0.0, min(1.0, ratio)) * bar_w
            if fw > 0:
                p.drawRoundedRect(QRectF(pad, y, fw, 6), 3, 3)
            y += 14

        # Réseau (Upload / Download)
        y += 2
        p.setFont(f_lbl)
        p.setPen(txt_col)
        p.drawText(QRect(pad, y, 70, 18), Qt.AlignLeft | Qt.AlignVCenter, "Réseau")
        p.setFont(f_val)
        p.setPen(sub_col)
        net_str = f"↓ {self._fmt_rate(self.net_down)}   ↑ {self._fmt_rate(self.net_up)}"
        p.drawText(QRect(pad + 60, y, bar_w - 60, 18), Qt.AlignRight | Qt.AlignVCenter, net_str)


class Zone(QWidget):
    def __init__(self, app, data):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint)
        self.app = app
        self.data = data
        self.fid = data["id"]
        self.hovered = False
        self.rs_flags = 0
        self.rs_start = None
        self.rs_geom = None
        self.hover_tab = None
        self.merge_hint = False
        self.switch_timer = QTimer(self)
        self.switch_timer.setSingleShot(True)
        self.switch_timer.setInterval(450)
        self.switch_timer.timeout.connect(self._spring_switch)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(MIN_W, TITLE_H)

        self.lay = QVBoxLayout(self)
        self.lay.setSpacing(0)
        self.tabbar = TabBar(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(SCROLL_CSS)
        self.scroll.viewport().setAutoFillBackground(False)
        self.grid = Grid(self)
        self.scroll.setWidget(self.grid)
        self.perf = PerfWidget(self)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.scroll)
        self.stack.addWidget(self.perf)
        self.lay.addWidget(self.tabbar)
        self.lay.addWidget(self.stack, 1)
        # curseur normal partout sauf sur les bords (sinon le curseur de redimensionnement "colle")
        self.tabbar.setCursor(Qt.ArrowCursor)
        self.scroll.setCursor(Qt.ArrowCursor)
        self.scroll.viewport().setCursor(Qt.ArrowCursor)

        collapsed = data.get("collapsed", False)
        self.stack.setVisible(not collapsed)
        self.lay.setContentsMargins(EDGE, EDGE, EDGE, 0 if collapsed else EDGE)
        self.setGeometry(data.get("x", 60), data.get("y", 60), data.get("w", 520),
                         TITLE_H if collapsed else data.get("h", 260))

    # -- onglets
    def active(self):
        n = len(self.data["tabs"])
        a = self.data.get("active", 0)
        return max(0, min(n - 1, a))

    def items(self):
        return self.data["tabs"][self.active()]["items"]

    def set_active(self, i):
        self.data["active"] = i
        self.refresh()
        self.app.save_soon()

    def add_tab(self):
        self.data["tabs"].append({"name": "Nouvel onglet", "items": []})
        self.set_active(len(self.data["tabs"]) - 1)
        QTimer.singleShot(30, lambda: self.tabbar.start_edit(len(self.data["tabs"]) - 1))

    def move_tab(self, i, d):
        tabs = self.data["tabs"]
        j = i + d
        if 0 <= j < len(tabs):
            act = self.active()
            tabs[i], tabs[j] = tabs[j], tabs[i]
            if act == i:
                self.data["active"] = j
            elif act == j:
                self.data["active"] = i
            self.refresh()
            self.app.save_soon()

    def delete_tab(self, i):
        tabs = self.data["tabs"]
        if len(tabs) <= 1:
            self.app.delete_zone(self.fid)
            return
        t = tabs[i]
        if t["items"]:
            r = QMessageBox.question(None, APP_NAME,
                                     f"Supprimer l'onglet « {t['name']} » ?\n"
                                     "Ses éléments seront remis sur le bureau.")
            if r != QMessageBox.Yes:
                return
        for it in t["items"]:
            self.app.restore_file(it)
        tabs.pop(i)
        if self.active() >= i and self.data.get("active", 0) > 0:
            self.data["active"] = self.data.get("active", 0) - 1
        self.refresh()
        self.app.save()

    def detach_tab(self, i):
        tabs = self.data["tabs"]
        if len(tabs) <= 1:
            return
        t = tabs.pop(i)
        if self.data.get("active", 0) >= len(tabs):
            self.data["active"] = len(tabs) - 1
        self.refresh()
        g = self.geometry()
        d = {"id": uuid.uuid4().hex, "x": g.x() + 40, "y": g.y() + 40, "w": g.width(),
             "h": self.data.get("h", 260), "color": self.data.get("color", "#4C8BF5"),
             "collapsed": False, "tabs": [t], "active": 0}
        self.app.create_zone(d)
        self.app.save()

    def _spring_switch(self):
        if self.hover_tab is not None and self.hover_tab != self.active():
            self.set_active(self.hover_tab)

    # -- contenu
    def refresh(self):
        self.tabbar.update()
        tab = self.data["tabs"][self.active()]
        is_perf = tab.get("type") == "perf"
        self.stack.setCurrentIndex(1 if is_perf else 0)
        self.perf.set_active(is_perf and not self.data.get("collapsed", False))
        if not is_perf:
            self.grid.set_tiles([Tile(self, it) for it in self.items()])
        self.update()

    def ensure_visible(self):
        geo = self.frameGeometry()
        for s in QApplication.screens():
            if s.availableGeometry().intersects(geo):
                return
        pg = QApplication.primaryScreen().availableGeometry()
        self.move(pg.left() + 40, pg.top() + 40)

    def set_color(self, col):
        self.data["color"] = col
        self.update()
        self.tabbar.update()
        self.grid.update()
        self.app.save_soon()

    def toggle_collapse(self):
        c = not self.data.get("collapsed", False)
        if c:
            self.data["h"] = self.height()
        self.data["collapsed"] = c
        self.stack.setVisible(not c)
        tab = self.data["tabs"][self.active()]
        self.perf.set_active(tab.get("type") == "perf" and not c)
        self.lay.setContentsMargins(EDGE, EDGE, EDGE, 0 if c else EDGE)
        self.resize(self.width(), TITLE_H if c else max(MIN_H, self.data.get("h", 260)))
        self.update()
        self.app.save_soon()

    # -- peinture
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        T = self.app.theme
        rad = T["radius"]
        accent = self.app.accent_for(self)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if T["glow"]:
            r = r.adjusted(2, 2, -2, -2)
        path = zone_path(r, T)
        if self.app.blur_active():
            alpha = T["a_blur_h"] if self.hovered else T["a_blur"]
        else:
            alpha = T["a_solid_h"] if self.hovered else T["a_solid"]
        grad = T.get("gradient")
        if grad:
            lg = QLinearGradient(0, 0, 0, self.height())
            lg.setColorAt(0, rgba(grad[0], alpha))
            lg.setColorAt(1, rgba(grad[1], alpha))
            p.fillPath(path, lg)
        else:
            p.fillPath(path, rgba(T["bg"], alpha))
        band_a = T["band_a"]
        if T["band_accent"]:
            band = QColor(accent)
            band.setAlpha(60 if self.hovered else 40)
        else:
            band = rgba(T["band"], band_a)
        if band.alpha():
            p.save()
            p.setClipPath(path)
            p.fillRect(QRectF(0, 0, self.width(), TITLE_H), band)
            p.restore()
        deco = T.get("deco", "none")
        collapsed = self.data.get("collapsed")
        if deco == "shoji":
            # paravent japonais : fine double ligne sous le titre + trame tres legere
            p.save()
            p.setClipPath(path)
            lc = rgba(T["text"], 16)
            p.setPen(QPen(lc, 1))
            if not collapsed:
                step = 64
                x = step
                while x < self.width():
                    p.drawLine(QPointF(x + 0.5, TITLE_H + 6), QPointF(x + 0.5, self.height() - 6))
                    x += step
                y = TITLE_H + step
                while y < self.height():
                    p.drawLine(QPointF(6, y + 0.5), QPointF(self.width() - 6, y + 0.5))
                    y += step
                p.setPen(QPen(rgba(T["text"], 60), 1))
                p.drawLine(QPointF(14, TITLE_H - 1.5), QPointF(self.width() - 14, TITLE_H - 1.5))
                p.drawLine(QPointF(14, TITLE_H + 1.5), QPointF(self.width() - 14, TITLE_H + 1.5))
            p.restore()
        elif deco == "sunset" and not collapsed:
            p.save()
            p.setClipPath(path)
            w, h = self.width(), self.height()
            y0 = TITLE_H + (h - TITLE_H) * 0.58
            # soleil a rayures
            rs = max(24.0, (h - TITLE_H) * 0.30)
            sg = QLinearGradient(0, y0 - rs, 0, y0)
            sg.setColorAt(0, QColor(255, 177, 59, 80))
            sg.setColorAt(1, QColor(255, 62, 165, 80))
            sun = QPainterPath()
            sun.addEllipse(QPointF(w * 0.72, y0), rs, rs)
            cut = QPainterPath()
            cut.addRect(QRectF(0, TITLE_H, w, y0 - TITLE_H))
            sun = sun.intersected(cut)
            for i in range(4):
                band = QPainterPath()
                yy = y0 - (i + 1) * rs * 0.16
                band.addRect(QRectF(0, yy, w, 2 + i))
                sun = sun.subtracted(band)
            p.fillPath(sun, sg)
            # grille en perspective
            gc = QColor(255, 62, 165, 55)
            p.setPen(QPen(gc, 1))
            p.drawLine(QPointF(0, y0), QPointF(w, y0))
            for i in range(1, 7):
                yy = y0 + (h - y0) * (i / 6.0) ** 1.7
                p.drawLine(QPointF(0, yy), QPointF(w, yy))
            cx = w / 2
            for k in range(-9, 10):
                p.drawLine(QPointF(cx + k * w / 30, y0), QPointF(cx + k * w / 7, h))
            p.restore()
        elif deco == "palms" and not collapsed:
            p.save()
            p.setClipPath(path)
            w, h = self.width(), self.height()
            y0 = TITLE_H + (h - TITLE_H) * 0.66
            # grand soleil couchant a rayures
            rs = max(30.0, (h - TITLE_H) * 0.42)
            sg = QLinearGradient(0, y0 - rs, 0, y0)
            sg.setColorAt(0, QColor(255, 214, 102, 150))
            sg.setColorAt(1, QColor(255, 79, 120, 150))
            sun = QPainterPath()
            sun.addEllipse(QPointF(w * 0.5, y0), rs, rs)
            cut = QPainterPath()
            cut.addRect(QRectF(0, TITLE_H, w, y0 - TITLE_H))
            sun = sun.intersected(cut)
            for i in range(5):
                band = QPainterPath()
                yy = y0 - (i + 1) * rs * 0.13
                band.addRect(QRectF(0, yy, w, 1.5 + i * 0.9))
                sun = sun.subtracted(band)
            p.fillPath(sun, sg)
            # mer : reflets sous l'horizon
            p.fillRect(QRectF(0, y0, w, h - y0), QColor(20, 6, 40, 120))
            for i in range(7):
                yy = y0 + 4 + i * (h - y0) / 8.0
                half = rs * (0.9 - i * 0.1)
                if half <= 4:
                    break
                p.fillRect(QRectF(w * 0.5 - half, yy, half * 2, 1.6), QColor(255, 140, 90, 95 - i * 10))
            # palmiers en silhouette
            sil = QColor(22, 4, 34, 235)
            hh = h - TITLE_H
            for bx, frac, lean in ((w * 0.06, 0.86, 0.35), (w * 0.17, 0.70, 0.15),
                                   (w * 0.90, 0.88, -0.30), (w * 0.98, 0.60, -0.1)):
                p.fillPath(palm_path(bx, h + 2, hh * frac, lean), sil)
            p.restore()
        elif deco == "stripe":
            p.save()
            p.setClipPath(path)
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            # trait d'accent sous la barre d'onglets + barre verticale a gauche
            if not collapsed:
                p.drawRect(QRectF(0, TITLE_H - 1, self.width(), 2))
                p.drawRect(QRectF(0, TITLE_H + 1, 3, self.height() - TITLE_H))
            else:
                p.drawRect(QRectF(0, 0, 3, self.height()))
            # petites diagonales en haut a droite
            c2 = QColor(accent)
            c2.setAlpha(150)
            p.setBrush(c2)
            for i in range(3):
                x = self.width() - 18 - i * 9
                d = QPainterPath()
                d.moveTo(x, 0)
                d.lineTo(x + 5, 0)
                d.lineTo(x - 1, 6)
                d.lineTo(x - 6, 6)
                d.closeSubpath()
                p.drawPath(d)
            p.restore()
        elif deco == "scanlines":
            p.save()
            p.setClipPath(path)
            p.setPen(QPen(QColor(255, 255, 255, 9), 1))
            y = TITLE_H + 2
            while y < self.height():
                p.drawLine(QPointF(0, y + 0.5), QPointF(self.width(), y + 0.5))
                y += 3
            # coin jaune + petite etiquette
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            tri = QPainterPath()
            tri.moveTo(self.width() - 2, self.height() - 26)
            tri.lineTo(self.width() - 2, self.height() - 2)
            tri.lineTo(self.width() - 26, self.height() - 2)
            tri.closeSubpath()
            p.drawPath(tri)
            if not collapsed:
                p.drawRect(QRectF(10, self.height() - 9, 46, 3))
                p.drawRect(QRectF(60, self.height() - 9, 8, 3))
            p.restore()
        elif deco == "hud" and not collapsed:
            hc = QColor(accent)
            hc.setAlpha(90)
            p.setPen(QPen(hc, 1))
            p.drawLine(QPointF(rad + 6, TITLE_H + 0.5), QPointF(self.width() - rad - 6, TITLE_H + 0.5))
            hc.setAlpha(170)
            p.setPen(QPen(hc, 1.5))
            # petites graduations
            for i in range(6):
                x = self.width() - rad - 10 - i * 5
                p.drawLine(QPointF(x, self.height() - 6), QPointF(x, self.height() - 10))
            p.drawLine(QPointF(rad + 8, self.height() - 7), QPointF(rad + 40, self.height() - 7))
        if T["sep_a"] and not self.data.get("collapsed"):
            p.setPen(QPen(rgba(T["text"], T["sep_a"]), 1))
            p.drawLine(QPointF(EDGE, TITLE_H + 0.5), QPointF(self.width() - EDGE, TITLE_H + 0.5))
        ba = T["border_h"] if self.hovered else T["border_a"]
        p.setBrush(Qt.NoBrush)
        if T["glow"]:
            g = QColor(accent)
            g.setAlpha(50 if self.hovered else 30)
            p.setPen(QPen(g, 4))
            p.drawPath(path)
        if ba:
            bg_ = T.get("border_gradient")
            if bg_:
                lg = QLinearGradient(0, 0, self.width(), self.height())
                c0, c1 = QColor(bg_[0]), QColor(bg_[1])
                c0.setAlpha(ba)
                c1.setAlpha(ba)
                lg.setColorAt(0, c0)
                lg.setColorAt(1, c1)
                p.setPen(QPen(QBrush(lg), 1.6))
            else:
                bc = QColor(accent) if T["border_accent"] else rgba(T["border"])
                bc.setAlpha(ba)
                p.setPen(QPen(bc, 1.2 if T["border_accent"] else 1))
            p.drawPath(path)
        if self.merge_hint:
            fill = QColor(accent)
            fill.setAlpha(45)
            p.fillPath(path, fill)
            p.setPen(QPen(accent, 2))
            p.drawPath(zone_path(QRectF(self.rect()).adjusted(1, 1, -1, -1), T))
            p.setPen(rgba(T["text"]))
            body = QRectF(0, TITLE_H, self.width(), max(30, self.height() - TITLE_H))
            p.drawText(body, Qt.AlignCenter, "Lâcher pour fusionner en onglets")

    def enterEvent(self, e):
        self.hovered = True
        for t in self.grid.tiles:
            if t.special == "recycle":
                ic = win_shell_icon("::" + SPECIAL_CLSID["recycle"])   # icone vide / pleine a jour
                if ic is not None:
                    t.icon = ic
                    t.update()
        self.update()

    def leaveEvent(self, e):
        self.hovered = False
        if not self.rs_flags:
            self.unsetCursor()
        self.update()

    # -- redimensionnement par les bords
    def hit(self, pos):
        if self.app.locked:
            return 0
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        f = 0
        if x <= EDGE:
            f |= 1
        elif x >= w - EDGE:
            f |= 2
        if not self.data.get("collapsed"):
            if y <= EDGE:
                f |= 4
            elif y >= h - EDGE:
                f |= 8
        return f

    @staticmethod
    def cursor_for(f):
        if f in (5, 10):
            return Qt.SizeFDiagCursor
        if f in (6, 9):
            return Qt.SizeBDiagCursor
        if f in (1, 2):
            return Qt.SizeHorCursor
        if f in (4, 8):
            return Qt.SizeVerCursor
        return None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            f = self.hit(e.position().toPoint())
            if f:
                self.rs_flags = f
                self.rs_start = e.globalPosition().toPoint()
                self.rs_geom = QRect(self.geometry())

    def mouseMoveEvent(self, e):
        if self.rs_flags and (e.buttons() & Qt.LeftButton):
            d = e.globalPosition().toPoint() - self.rs_start
            g = QRect(self.rs_geom)
            f = self.rs_flags
            if f & 1:
                g.setLeft(min(g.left() + d.x(), g.right() - MIN_W))
            if f & 2:
                g.setRight(max(g.right() + d.x(), g.left() + MIN_W))
            if f & 4:
                g.setTop(min(g.top() + d.y(), g.bottom() - MIN_H))
            if f & 8:
                g.setBottom(max(g.bottom() + d.y(), g.top() + MIN_H))
            if self.app.snap_on and not (QApplication.keyboardModifiers() & Qt.ShiftModifier):
                g = self.app.snap_resize(self, g, f)
            self.setGeometry(g)
            return
        cur = self.cursor_for(self.hit(e.position().toPoint()))
        if cur is None:
            self.unsetCursor()
        else:
            self.setCursor(cur)

    def mouseReleaseEvent(self, e):
        if self.rs_flags:
            self.rs_flags = 0
            self.app.save_soon()
            win_push_bottom(self)

    def moveEvent(self, e):
        self.app.record_geom(self)

    def resizeEvent(self, e):
        self.app.record_geom(self)

    def showEvent(self, e):
        def init():
            win_attach_desktop(self)
            win_blur(self, self.app.blur_active())
            win_push_bottom(self)
        QTimer.singleShot(0, init)

    def changeEvent(self, e):
        if e.type() == QEvent.ActivationChange and self.isActiveWindow():
            QTimer.singleShot(50, lambda: win_push_bottom(self))
        super().changeEvent(e)

    # -- menu
    def contextMenuEvent(self, e):
        self.show_menu(e.globalPos(), None)

    def show_menu(self, gp, tab):
        a = self.app
        tabs = self.data["tabs"]
        t = self.active() if tab is None else tab
        m = a.menu(self)
        m.addAction("Paramètres…", a.open_settings)
        m.addSeparator()
        m.addAction("Nouvel onglet", self.add_tab)
        m.addAction(f"Renommer « {tabs[t]['name']} »", lambda: self.tabbar.start_edit(t))
        if len(tabs) > 1:
            left = m.addAction("Déplacer l'onglet à gauche", lambda: self.move_tab(t, -1))
            left.setEnabled(t > 0)
            right = m.addAction("Déplacer l'onglet à droite", lambda: self.move_tab(t, 1))
            right.setEnabled(t < len(tabs) - 1)
            m.addAction("Détacher en nouvelle zone", lambda: self.detach_tab(t))
            m.addAction("Supprimer l'onglet", lambda: self.delete_tab(t))
        m.addSeparator()
        sp = a.special_menu(m, self.fid, self.active())
        sp.setTitle("Ajouter un élément Windows")
        m.addMenu(sp)
        m.addAction("Trier par nom", lambda: a.sort_tab(self.fid))
        cm = sticky_submenu(m, "Couleur d'accent")
        for name, col in ACCENTS:
            act = make_sticky(cm.addAction(color_icon(col), name))
            act.triggered.connect(lambda _=False, c=col: self.set_color(c))
        m.addAction("Déplier" if self.data.get("collapsed") else "Replier", self.toggle_collapse)
        m.addSeparator()
        screens = QGuiApplication.screens()
        if len(screens) > 1:
            sm = m.addMenu("Envoyer vers l'écran")
            sm.setStyleSheet(MENU_CSS)
            cur = QGuiApplication.screenAt(self.geometry().center())
            for i, s in enumerate(screens):
                g = s.geometry()
                act = sm.addAction(f"{i + 1}. {s.model() or s.name()}  ({g.width()}×{g.height()})")
                act.setEnabled(s is not cur)
                act.triggered.connect(lambda _=False, sc=s: a.send_to_screen(self, sc))
        others = [o for o in a.zones.values() if o is not self]
        if others:
            ms = m.addMenu("Même taille que")
            ms.setStyleSheet(MENU_CSS)
            for o in others:
                name = " / ".join(t["name"] for t in o.data["tabs"][:3])
                ms.addAction(name, lambda oo=o: a.match_size(self, oo, True, True))
                ms.addAction(f"    largeur seulement", lambda oo=o: a.match_size(self, oo, True, False))
                ms.addAction(f"    hauteur seulement", lambda oo=o: a.match_size(self, oo, False, True))
        m.addAction("Nouvelle zone", lambda: a.new_zone(gp))
        m.addAction("Nouvelle zone Performances", lambda: a.new_zone(gp, edit=False, name="Performances", tab_type="perf"))
        lock = m.addAction("Verrouiller les zones")
        lock.setCheckable(True)
        lock.setChecked(a.locked)
        lock.toggled.connect(a.set_locked)
        m.addAction("Supprimer cette zone", lambda: a.delete_zone(self.fid))
        m.exec(gp)

    # -- glisser-deposer
    def _action(self, md):
        return Qt.MoveAction if md.hasFormat(MIME) else Qt.CopyAction

    def _tab_under(self, pos):
        if self.tabbar.geometry().contains(pos):
            return self.tabbar.index_at(self.tabbar.mapFrom(self, pos))
        return None

    @staticmethod
    def _is_shell_obj(md):
        return any("Shell IDList" in f for f in md.formats())

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasFormat(MIME) or self._is_shell_obj(md):
            e.setDropAction(self._action(e.mimeData()))
            e.accept()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        pos = e.position().toPoint()
        if self.data.get("collapsed"):
            self.toggle_collapse()
        ti = self._tab_under(pos)
        if self.tabbar.geometry().contains(pos):
            self.grid.indicator = None
            if ti != self.hover_tab:
                self.hover_tab = ti
                if ti is not None and ti != self.active():
                    self.switch_timer.start()
                else:
                    self.switch_timer.stop()
            self.tabbar.hover_idx = ti
            self.tabbar.update()
        else:
            self.hover_tab = None
            self.switch_timer.stop()
            self.grid.indicator = self.grid.index_at(self.grid.mapFrom(self, pos))
        self.grid.update()
        e.setDropAction(self._action(e.mimeData()))
        e.accept()

    def _clear_drag_state(self):
        self.switch_timer.stop()
        self.hover_tab = None
        self.grid.indicator = None
        self.tabbar.hover_idx = None
        self.grid.update()
        self.tabbar.update()

    def dragLeaveEvent(self, e):
        self._clear_drag_state()

    def dropEvent(self, e):
        pos = e.position().toPoint()
        ti = self._tab_under(pos)
        on_bar = self.tabbar.geometry().contains(pos)
        if on_bar:
            tab = ti if ti is not None else self.active()
            idx = None                                   # a la fin de l'onglet
        else:
            tab = self.active()
            idx = self.grid.index_at(self.grid.mapFrom(self, pos))
        self._clear_drag_state()
        md = e.mimeData()
        if md.hasFormat(MIME):
            info = json.loads(bytes(md.data(MIME)).decode("utf-8"))
            e.setDropAction(Qt.MoveAction)
            e.accept()
            # traite apres la fin du drag (la tuile source est encore utilisee)
            self.app.pending = ("move", info["path"], self.fid, tab, idx)
            return
        paths = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
        if not paths and self._is_shell_obj(md):
            e.setDropAction(Qt.CopyAction)
            e.accept()
            keys = [k for k in (special_from_name(n) for n in win_shell_names_from_drop(md)) if k]
            if keys:
                fid = self.fid
                QTimer.singleShot(0, lambda: [self.app.add_special(fid, tab, k, idx, from_desktop=True)
                                              for k in keys])
                return
            # objet non reconnu : on propose la liste
            gp = self.mapToGlobal(pos)
            fid = self.fid
            QTimer.singleShot(0, lambda: self.app.special_menu(None, fid, tab, idx).exec(gp))
            return
        # CopyAction : l'Explorateur ne touche a rien, c'est nous qui deplacons le fichier
        e.setDropAction(Qt.CopyAction)
        e.accept()
        fid = self.fid
        QTimer.singleShot(0, lambda: self.app.add_external(fid, tab, paths, idx))


# --------------------------------------------------------------------------- application

DIALOG_CSS = """
QDialog { background:#1C1E25; }
QLabel { color:#D6D9E0; }
QCheckBox { color:#D6D9E0; }
QComboBox, QFontComboBox { background:#262A34; color:#E5E7EB; border:1px solid #3A3F4E;
    border-radius:5px; padding:3px 8px; min-height:20px; }
QComboBox QAbstractItemView { background:#262A34; color:#E5E7EB; selection-background-color:#3A4152; }
QPushButton { background:#2B303C; color:#E5E7EB; border:1px solid #3A3F4E; border-radius:6px; padding:5px 12px; }
QPushButton:hover { background:#353B4A; }
QSlider::groove:horizontal { height:4px; background:#3A3F4E; border-radius:2px; }
QSlider::handle:horizontal { background:#4C8BF5; width:14px; margin:-6px 0; border-radius:7px; }
QSlider::sub-page:horizontal { background:#4C8BF5; border-radius:2px; }
"""


class ColorButton(QPushButton):
    def __init__(self, on_pick):
        super().__init__()
        self.on_pick = on_pick
        self.color = QColor("#ffffff")
        self.setFixedWidth(70)
        self.clicked.connect(self.pick)

    def set_color(self, c):
        self.color = QColor(c)
        self.setStyleSheet(f"QPushButton{{background:{self.color.name()}; border:1px solid #555; border-radius:6px;}}")

    def pick(self):
        c = QColorDialog.getColor(self.color, self, "Choisir une couleur")
        if c.isValid():
            self.set_color(c)
            self.on_pick(c)


class ThemeDialog(QDialog):
    """Reglages du theme actif : chaque changement s'applique en direct."""

    def __init__(self, app):
        super().__init__(None)
        self.app = app
        self.setWindowTitle("Personnaliser le thème")
        self.setStyleSheet(DIALOG_CSS)
        self.setMinimumWidth(380)
        self.loading = False
        lay = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setStyleSheet("font-size:15px; font-weight:600; color:#FFFFFF;")
        lay.addWidget(self.title)
        self.theme_pick = QComboBox()
        for k in THEME_ORDER:
            self.theme_pick.addItem(THEMES[k]["label"], k)
        self.theme_pick.currentIndexChanged.connect(
            lambda i: (not self.loading) and self.app.set_theme(self.theme_pick.itemData(i)))
        lay.addWidget(self.theme_pick)
        lay.addSpacing(4)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(9)

        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 255)
        self.opacity.valueChanged.connect(self.on_opacity)
        form.addRow("Opacité du fond", self.opacity)
        self.bg = ColorButton(lambda c: self.set("bg", [c.red(), c.green(), c.blue()]))
        form.addRow("Couleur du fond", self.bg)
        self.text = ColorButton(lambda c: self.set("text", [c.red(), c.green(), c.blue()]))
        form.addRow("Couleur du texte", self.text)
        self.shadow = QCheckBox("Ombre sous le texte")
        self.shadow.toggled.connect(lambda v: self.set("shadow", v))
        form.addRow("", self.shadow)

        acc_row = QHBoxLayout()
        self.acc_on = QCheckBox("Imposer")
        self.acc_on.toggled.connect(self.on_accent_toggle)
        self.acc = ColorButton(lambda c: self.set("accent", c.name()))
        acc_row.addWidget(self.acc_on)
        acc_row.addWidget(self.acc)
        acc_row.addStretch(1)
        accw = QWidget()
        accw.setLayout(acc_row)
        acc_row.setContentsMargins(0, 0, 0, 0)
        form.addRow("Couleur d'accent", accw)

        self.radius = QSlider(Qt.Horizontal)
        self.radius.setRange(0, 20)
        self.radius.valueChanged.connect(lambda v: self.set("radius", v))
        form.addRow("Arrondi des coins", self.radius)
        self.shape = QComboBox()
        self.shape.addItem("Coins arrondis", "round")
        self.shape.addItem("Coins coupés (futuriste)", "chamfer")
        self.shape.currentIndexChanged.connect(lambda i: self.set("shape", self.shape.itemData(i)))
        form.addRow("Forme", self.shape)
        self.border = QSlider(Qt.Horizontal)
        self.border.setRange(0, 255)
        self.border.valueChanged.connect(self.on_border)
        form.addRow("Bordure", self.border)
        self.glow = QCheckBox("Halo lumineux autour du cadre")
        self.glow.toggled.connect(lambda v: self.set("glow", v))
        form.addRow("", self.glow)

        self.tab = QComboBox()
        for k, label in TAB_STYLES:
            self.tab.addItem(label, k)
        self.tab.currentIndexChanged.connect(lambda i: self.set("tab", self.tab.itemData(i)))
        form.addRow("Style des onglets", self.tab)
        self.font = QFontComboBox()
        self.font.currentFontChanged.connect(lambda f: self.set("font", f.family()))
        form.addRow("Police", self.font)
        self.upper = QCheckBox("Onglets en majuscules")
        self.upper.toggled.connect(lambda v: self.set("upper", v))
        form.addRow("", self.upper)
        self.deco = QComboBox()
        for k, label in DECOS:
            self.deco.addItem(label, k)
        self.deco.currentIndexChanged.connect(lambda i: self.set("deco", self.deco.itemData(i)))
        form.addRow("Décoration", self.deco)
        lay.addLayout(form)

        btns = QHBoxLayout()
        reset = QPushButton("Réinitialiser ce thème")
        reset.clicked.connect(self.on_reset)
        close = QPushButton("Fermer")
        close.clicked.connect(self.close)
        btns.addWidget(reset)
        btns.addStretch(1)
        btns.addWidget(close)
        lay.addSpacing(6)
        lay.addLayout(btns)

    def set(self, field, value):
        if not self.loading:
            self.app.set_override(field, value)

    def on_opacity(self, v):
        if self.loading:
            return
        self.set("a_blur", v)
        self.set("a_blur_h", min(255, v + 30))
        self.set("a_solid", min(255, v + 60))
        self.set("a_solid_h", min(255, v + 85))

    def on_border(self, v):
        if self.loading:
            return
        self.set("border_a", v)
        self.set("border_h", min(255, v + 40))

    def on_accent_toggle(self, on):
        self.acc.setEnabled(on)
        self.set("accent", self.acc.color.name() if on else None)

    def on_reset(self):
        self.app.reset_theme()
        self.load()

    @staticmethod
    def _select(combo, data):
        i = combo.findData(data)
        combo.setCurrentIndex(max(0, i))

    def load(self):
        self.loading = True
        T = self.app.theme
        self.title.setText("Thème")
        self._select(self.theme_pick, self.app.theme_key)
        self.opacity.setValue(T["a_blur"])
        self.bg.set_color(rgba(T["bg"], 255))
        self.text.set_color(rgba(T["text"], 255))
        self.shadow.setChecked(bool(T["shadow"]))
        acc = T.get("accent")
        self.acc_on.setChecked(bool(acc))
        self.acc.set_color(acc or "#4C8BF5")
        self.acc.setEnabled(bool(acc))
        self.radius.setValue(int(T["radius"]))
        self._select(self.shape, T.get("shape", "round"))
        self.border.setValue(int(T["border_a"]))
        self.glow.setChecked(bool(T["glow"]))
        self._select(self.tab, T["tab"])
        self.font.setCurrentFont(QFont(T.get("font") or "Segoe UI"))
        self.upper.setChecked(bool(T.get("upper")))
        self._select(self.deco, T.get("deco", "none"))
        self.loading = False


SETTINGS_CSS = DIALOG_CSS + """
QListWidget#nav { background:#17191F; border:none; color:#D6D9E0; padding:8px 6px; outline:0; }
QListWidget#nav::item { padding:9px 12px; border-radius:6px; margin:1px 0; }
QListWidget#nav::item:selected { background:#2A2F3B; color:#FFFFFF; }
QListWidget#nav::item:hover:!selected { background:#20232B; }
QListWidget#rules { background:#20232B; color:#E5E7EB; border:1px solid #33374A; border-radius:6px; }
QListWidget#rules::item { padding:5px 8px; }
QListWidget#rules::item:selected { background:#33405A; }
QGroupBox { color:#FFFFFF; font-weight:600; border:1px solid #2E3240; border-radius:8px;
    margin-top:14px; padding:12px 12px 10px 12px; background:#20232B; }
QGroupBox::title { subcontrol-origin: margin; left:10px; padding:0 4px; }
QRadioButton { color:#D6D9E0; }
QLineEdit { background:#262A34; color:#E5E7EB; border:1px solid #3A3F4E; border-radius:5px; padding:4px 6px; }
QLabel#h1 { font-size:20px; font-weight:600; color:#FFFFFF; }
QLabel#hint { color:#8A90A0; }
"""


class SettingsDialog(QDialog):
    PAGES = ["Général", "Apparence", "Bureau", "Rangement auto", "Disposition", "À propos"]

    def __init__(self, app):
        super().__init__(None)
        self.app = app
        self.loading = False
        self.setWindowTitle(f"{APP_NAME} - Paramètres")
        self.setStyleSheet(SETTINGS_CSS)
        self.resize(760, 560)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(180)
        for name in self.PAGES:
            QListWidgetItem(name, self.nav)
        self.stack = QStackedWidget()
        root.addWidget(self.nav)
        root.addWidget(self.stack, 1)
        for build in (self.page_general, self.page_look, self.page_desktop, self.page_rules,
                      self.page_layout, self.page_about):
            self.stack.addWidget(build())
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

    # -- helpers
    def _page(self, title, subtitle=""):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(26, 20, 26, 20)
        lay.setSpacing(8)
        h = QLabel(title)
        h.setObjectName("h1")
        lay.addWidget(h)
        if subtitle:
            sl = QLabel(subtitle)
            sl.setObjectName("hint")
            sl.setWordWrap(True)
            lay.addWidget(sl)
        return w, lay

    def _group(self, lay, title):
        g = QGroupBox(title)
        gl = QVBoxLayout(g)
        gl.setSpacing(8)
        lay.addWidget(g)
        return gl

    def _check(self, layout, text, slot):
        c = QCheckBox(text)
        c.toggled.connect(lambda v: (not self.loading) and slot(v))
        layout.addWidget(c)
        return c

    # -- pages
    def page_general(self):
        w, lay = self._page("Général", "Comportement de base de l'application.")
        g = self._group(lay, "Démarrage")
        self.c_start = self._check(g, "Lancer au démarrage de Windows", self.app.toggle_startup)
        self.c_start.setEnabled(IS_WIN)
        b = QPushButton("Installer (raccourci dans le menu Démarrer)")
        b.clicked.connect(self.app.install)
        b.setEnabled(IS_WIN)
        g.addWidget(b)
        g2 = self._group(lay, "Zones")
        self.c_move = self._check(g2, "Retirer les fichiers du bureau quand je les range dans une zone",
                                  self.app.set_move)
        self.c_lock = self._check(g2, "Verrouiller les zones (empêche de les déplacer ou redimensionner)",
                                  self.app.set_locked)
        row = QHBoxLayout()
        nb = QPushButton("Nouvelle zone")
        nb.clicked.connect(lambda: self.app.new_zone())
        ob = QPushButton("Ouvrir le dossier de stockage")
        ob.clicked.connect(lambda: self.app.launch(STORE_DIR))
        row.addWidget(nb)
        row.addWidget(ob)
        row.addStretch(1)
        g2.addLayout(row)
        lay.addStretch(1)
        return w

    def page_look(self):
        w, lay = self._page("Apparence", "Thème, taille des icônes et effets.")
        g = self._group(lay, "Thème")
        self.theme_combo = QComboBox()
        for k in THEME_ORDER:
            self.theme_combo.addItem(THEMES[k]["label"], k)
        self.theme_combo.currentIndexChanged.connect(
            lambda i: (not self.loading) and self.app.set_theme(self.theme_combo.itemData(i)))
        g.addWidget(self.theme_combo)
        cb = QPushButton("Personnaliser ce thème…")
        cb.clicked.connect(self.app.open_theme_dialog)
        g.addWidget(cb)
        g2 = self._group(lay, "Icônes")
        self.size_combo = QComboBox()
        for k, label in SIZE_LABELS:
            self.size_combo.addItem(label, k)
        self.size_combo.currentIndexChanged.connect(
            lambda i: (not self.loading) and self.app.set_size(self.size_combo.itemData(i)))
        g2.addWidget(self.size_combo)
        g3 = self._group(lay, "Effets")
        self.c_blur = self._check(g3, "Effet de flou Windows derrière les zones", self.app.set_blur)
        hint = QLabel("Le flou est calculé par Windows lui-même : il ne ralentit pas l'application.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        g3.addWidget(hint)
        lay.addStretch(1)
        return w

    def page_desktop(self):
        w, lay = self._page("Bureau", "Double-clic sur un endroit vide du bureau pour tout masquer, "
                                      "re-double-clic pour tout réafficher.")
        g = self._group(lay, "Double-clic sur le bureau")
        self.qh_group = QButtonGroup(self)
        self.qh_radios = {}
        for key, label in (("both", "Masquer les icônes du bureau et les zones"),
                           ("zones", "Masquer seulement les zones"),
                           ("icons", "Masquer seulement les icônes du bureau"),
                           ("off", "Ne rien faire")):
            r = QRadioButton(label)
            self.qh_group.addButton(r)
            self.qh_radios[key] = r
            r.toggled.connect(lambda on, k=key: on and (not self.loading) and self.app.set_qh_mode(k))
            g.addWidget(r)
        hint = QLabel("Les icônes ne sont cachées que temporairement : elles réapparaissent "
                      "quand tu quittes l'application et à chaque démarrage.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        g.addWidget(hint)
        lay.addStretch(1)
        return w

    def page_rules(self):
        w, lay = self._page("Rangement automatique",
                            "Range les éléments du bureau dans tes zones selon des règles. "
                            "Les règles sont testées dans l'ordre, la première qui correspond gagne.")
        g = self._group(lay, "Règles")
        self.rules_list = QListWidget()
        self.rules_list.setObjectName("rules")
        self.rules_list.setMinimumHeight(130)
        g.addWidget(self.rules_list)
        row = QHBoxLayout()
        self.r_kind = QComboBox()
        for k, label in RULE_KINDS:
            self.r_kind.addItem(label, k)
        self.r_pattern = QLineEdit()
        self.r_pattern.setPlaceholderText("texte du nom")
        self.r_pattern.setFixedWidth(120)
        self.r_kind.currentIndexChanged.connect(
            lambda i: self.r_pattern.setVisible(self.r_kind.itemData(i) == "name"))
        self.r_pattern.setVisible(False)
        arrow = QLabel("→")
        self.r_dest = QComboBox()
        self.r_dest.setMinimumWidth(170)
        add = QPushButton("Ajouter")
        add.clicked.connect(self.add_rule)
        row.addWidget(self.r_kind)
        row.addWidget(self.r_pattern)
        row.addWidget(arrow)
        row.addWidget(self.r_dest, 1)
        row.addWidget(add)
        g.addLayout(row)
        row2 = QHBoxLayout()
        up = QPushButton("Monter")
        up.clicked.connect(lambda: self.move_rule(-1))
        down = QPushButton("Descendre")
        down.clicked.connect(lambda: self.move_rule(1))
        rm = QPushButton("Supprimer la règle")
        rm.clicked.connect(self.remove_rule)
        row2.addWidget(up)
        row2.addWidget(down)
        row2.addStretch(1)
        row2.addWidget(rm)
        g.addLayout(row2)

        g2 = self._group(lay, "Le reste")
        drow = QHBoxLayout()
        drow.addWidget(QLabel("Éléments sans règle :"))
        self.default_combo = QComboBox()
        self.default_combo.currentIndexChanged.connect(self.on_default)
        drow.addWidget(self.default_combo, 1)
        g2.addLayout(drow)

        g3 = self._group(lay, "Quand ranger ?")
        self.c_auto = self._check(g3, "Ranger automatiquement les nouveaux éléments qui arrivent sur le bureau",
                                  self.app.set_auto_sort)
        hint = QLabel("Surveillance gérée par Windows (aucune vérification en boucle). "
                      "Un élément que tu remets toi-même sur le bureau n'est pas re-rangé.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        g3.addWidget(hint)
        now = QPushButton("Ranger le bureau maintenant")
        now.clicked.connect(self.sort_now)
        g3.addWidget(now)
        lay.addStretch(1)
        return w

    def page_layout(self):
        w, lay = self._page("Disposition", "Aimantation, espacement et sauvegardes de la disposition.")
        g = self._group(lay, "Aimantation")
        self.c_snap = self._check(g, "Aimanter les zones entre elles et aux bords de l'écran",
                                  lambda v: self.app.set_snap(on=v))
        form = QFormLayout()
        self.s_dist = QSlider(Qt.Horizontal)
        self.s_dist.setRange(4, 30)
        self.l_dist = QLabel()
        self.s_dist.valueChanged.connect(self.on_dist)
        rd = QHBoxLayout()
        rd.addWidget(self.s_dist, 1)
        rd.addWidget(self.l_dist)
        form.addRow("Force de l'aimant", rd)
        self.s_gap = QSlider(Qt.Horizontal)
        self.s_gap.setRange(0, 24)
        self.l_gap = QLabel()
        self.s_gap.valueChanged.connect(self.on_gap)
        rg = QHBoxLayout()
        rg.addWidget(self.s_gap, 1)
        rg.addWidget(self.l_gap)
        form.addRow("Espace entre zones", rg)
        g.addLayout(form)
        hint = QLabel("Astuce : garde Maj enfoncée pendant un déplacement pour couper l'aimant.")
        hint.setObjectName("hint")
        g.addWidget(hint)

        g2 = self._group(lay, "Sauvegardes")
        hint2 = QLabel("Une copie de la disposition est faite chaque jour (15 derniers jours gardés). "
                       "Les positions sont aussi mémorisées pour chaque configuration d'écrans.")
        hint2.setObjectName("hint")
        hint2.setWordWrap(True)
        g2.addWidget(hint2)
        br = QHBoxLayout()
        self.backup_combo = QComboBox()
        rb = QPushButton("Restaurer")
        rb.clicked.connect(self.restore)
        br.addWidget(self.backup_combo, 1)
        br.addWidget(rb)
        g2.addLayout(br)
        lay.addStretch(1)
        return w

    def page_about(self):
        w, lay = self._page(APP_NAME, f"Version {APP_VERSION}")
        g = self._group(lay, "Données")
        lab = QLabel(f"Configuration et éléments rangés :\n{DATA_DIR}")
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        g.addWidget(lab)
        ob = QPushButton("Ouvrir le dossier")
        ob.clicked.connect(lambda: self.app.launch(DATA_DIR))
        g.addWidget(ob)
        lay.addStretch(1)
        return w

    # -- actions
    def _fill_dest(self, combo, with_none):
        combo.blockSignals(True)
        combo.clear()
        if with_none:
            combo.addItem("Laisser sur le bureau", None)
        for label, fid, tab in self.app.dest_list():
            combo.addItem(label, {"fid": fid, "tab": tab})
        combo.blockSignals(False)

    def refresh_rules(self):
        self.rules_list.clear()
        kinds = dict(RULE_KINDS)
        for r in self.app.rules:
            what = kinds.get(r["kind"], r["kind"])
            if r["kind"] == "name":
                what = f"Nom contient « {r.get('pattern', '')} »"
            QListWidgetItem(f"{what}   →   {self.app.dest_label(r.get('fid'), r.get('tab'))}", self.rules_list)

    def add_rule(self):
        dest = self.r_dest.currentData()
        if not dest:
            return
        kind = self.r_kind.currentData()
        pat = self.r_pattern.text().strip()
        if kind == "name" and not pat:
            self.r_pattern.setFocus()
            return
        self.app.rules.append({"kind": kind, "pattern": pat, "fid": dest["fid"], "tab": dest["tab"]})
        self.r_pattern.clear()
        self.refresh_rules()
        self.app.save_soon()

    def remove_rule(self):
        i = self.rules_list.currentRow()
        if 0 <= i < len(self.app.rules):
            self.app.rules.pop(i)
            self.refresh_rules()
            self.app.save_soon()

    def move_rule(self, d):
        i = self.rules_list.currentRow()
        j = i + d
        rules = self.app.rules
        if 0 <= i < len(rules) and 0 <= j < len(rules):
            rules[i], rules[j] = rules[j], rules[i]
            self.refresh_rules()
            self.rules_list.setCurrentRow(j)
            self.app.save_soon()

    def on_default(self, i):
        if not self.loading:
            self.app.default_dest = self.default_combo.itemData(i)
            self.app.save_soon()

    def sort_now(self):
        if not self.app.rules and not self.app.default_dest:
            QMessageBox.information(self, APP_NAME, "Ajoute d'abord au moins une règle.")
            return
        n = self.app.sort_desktop()
        self.app.known = set(self.app.desktop_entries())
        QMessageBox.information(self, APP_NAME, f"{n} élément(s) rangé(s)." if n else "Rien à ranger.")

    def on_dist(self, v):
        self.l_dist.setText(f"{v} px")
        if not self.loading:
            self.app.set_snap(dist=v)

    def on_gap(self, v):
        self.l_gap.setText(f"{v} px")
        if not self.loading:
            self.app.set_snap(gap=v)

    def restore(self):
        name = self.backup_combo.currentData()
        if name:
            self.app.restore_backup(name)

    def load(self):
        self.loading = True
        a = self.app
        self.c_start.setChecked(get_startup())
        self.c_move.setChecked(a.move_files)
        self.c_lock.setChecked(a.locked)
        ThemeDialog._select(self.theme_combo, a.theme_key)
        ThemeDialog._select(self.size_combo, a.size_key)
        self.c_blur.setChecked(a.blur)
        self.qh_radios[a.qh_mode].setChecked(True)
        self._fill_dest(self.r_dest, False)
        self._fill_dest(self.default_combo, True)
        idx = 0
        if a.default_dest:
            for i in range(self.default_combo.count()):
                dd = self.default_combo.itemData(i)
                if dd and dd["fid"] == a.default_dest.get("fid") and dd["tab"] == a.default_dest.get("tab"):
                    idx = i
        self.default_combo.setCurrentIndex(idx)
        self.refresh_rules()
        self.c_auto.setChecked(a.auto_sort)
        self.c_snap.setChecked(a.snap_on)
        self.s_dist.setValue(SNAP_DIST)
        self.l_dist.setText(f"{SNAP_DIST} px")
        self.s_gap.setValue(ZONE_GAP)
        self.l_gap.setText(f"{ZONE_GAP} px")
        self.backup_combo.clear()
        for b in a.backups():
            d = b[7:15]
            self.backup_combo.addItem(f"{d[6:8]}/{d[4:6]}/{d[0:4]}", b)
        self.loading = False


class TatamiApp:
    def __init__(self, qapp):
        self.qapp = qapp
        self.zones = {}
        self.pending = None
        self.drag_tile = None
        self.merge_target = None
        migrate_old_install()
        os.makedirs(STORE_DIR, exist_ok=True)
        cfg = self.load()
        self.locked = cfg.get("locked", False)
        self.move_files = cfg.get("move_files", True)
        self.blur = cfg.get("blur", True)
        self.theme_key = cfg.get("theme", "sombre") if cfg.get("theme") in THEMES else "sombre"
        self.theme_over = cfg.get("theme_overrides", {}) or {}
        self.theme = self.merged_theme(self.theme_key)
        self.theme_dialog = None
        self.backup_config()
        self.size_key = cfg.get("tile_size", "medium") if cfg.get("tile_size") in SIZES else "medium"
        self.tile = SIZES[self.size_key]
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(self.save)
        self.restoring = False
        self.screens_dirty = False
        self.sig = screens_sig()
        self.screen_timer = QTimer()
        self.screen_timer.setSingleShot(True)
        self.screen_timer.setInterval(1200)
        self.screen_timer.timeout.connect(self.on_screens_changed)
        qapp.screenAdded.connect(self._screen_added)
        qapp.screenRemoved.connect(self._screens_event)
        qapp.primaryScreenChanged.connect(self._screens_event)
        for s in QGuiApplication.screens():
            s.geometryChanged.connect(self._screens_event)
        # Quick-hide : "both" | "zones" | "icons" | "off"
        self.qh_mode = cfg.get("quick_hide", "both")
        if self.qh_mode not in ("both", "zones", "icons", "off"):
            self.qh_mode = "both"
        self.qh_hidden = False
        global SNAP_DIST, ZONE_GAP
        self.snap_on = cfg.get("snap_on", True)
        SNAP_DIST = int(cfg.get("snap_dist", SNAP_DIST))
        ZONE_GAP = int(cfg.get("zone_gap", cfg.get("f" + "ence_gap", ZONE_GAP)))
        self.rules = cfg.get("rules", []) or []
        self.default_dest = cfg.get("default_dest")
        self.auto_sort = cfg.get("auto_sort", False)
        self.ignore_names = set()
        self.known = set()
        self.settings_dialog = None
        self.size_actions = []
        self.qh_actions = []
        self.watcher = QFileSystemWatcher()
        self.watch_timer = QTimer()
        self.watch_timer.setSingleShot(True)
        self.watch_timer.setInterval(1500)
        self.watch_timer.timeout.connect(self._on_desktop_changed)
        self.watcher.directoryChanged.connect(lambda _p: self.watch_timer.start())
        if IS_WIN:
            set_desktop_icons_visible(True)    # toujours reafficher les icones au demarrage
        self.dbl = DesktopDoubleClick(self.quick_hide_toggle)
        if self.qh_mode != "off":
            self.dbl.start()
        self.make_tray()
        for d in cfg.get("zones", cfg.get("f" + "ences", [])):
            self.create_zone(self.migrate(d))
        if not self.zones:
            self.new_zone(edit=False, name="Raccourcis")
        if self.auto_sort:
            self.start_watch()

    @staticmethod
    def migrate(d):
        d.setdefault("id", uuid.uuid4().hex)
        if "tabs" not in d:
            d["tabs"] = [{"name": d.pop("title", "Raccourcis"), "items": d.pop("items", [])}]
        if not d["tabs"]:
            d["tabs"] = [{"name": "Raccourcis", "items": []}]
        d.setdefault("active", 0)
        return d

    # -- persistance
    def load(self):
        try:
            with open(CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception:
            try:
                shutil.copy2(CONFIG, CONFIG + ".corrompu")
            except Exception:
                pass
            return {}

    def backup_config(self):
        """Une copie de la config par jour, on garde les 15 dernieres."""
        try:
            if not os.path.exists(CONFIG):
                return
            import datetime
            bdir = os.path.join(DATA_DIR, "backups")
            os.makedirs(bdir, exist_ok=True)
            dst = os.path.join(bdir, f"config-{datetime.date.today():%Y%m%d}.json")
            if not os.path.exists(dst):
                shutil.copy2(CONFIG, dst)
            files = sorted(x for x in os.listdir(bdir) if x.startswith("config-"))
            for old in files[:-15]:
                os.remove(os.path.join(bdir, old))
        except Exception:
            pass

    def save_soon(self):
        self.save_timer.start()

    def save(self):
        if getattr(self, "no_save", False):
            return
        cfg = {"locked": self.locked, "move_files": self.move_files, "blur": self.blur, "theme": self.theme_key, "theme_overrides": self.theme_over, "quick_hide": self.qh_mode, "snap_on": self.snap_on,
               "snap_dist": SNAP_DIST, "zone_gap": ZONE_GAP, "rules": self.rules,
               "default_dest": self.default_dest, "auto_sort": self.auto_sort,
               "tile_size": self.size_key, "zones": [f.data for f in self.zones.values()]}
        tmp = CONFIG + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, CONFIG)
        except Exception:
            pass

    # -- zones
    def create_zone(self, d):
        self.restoring = True
        f = Zone(self, d)
        self.restoring = False
        self.zones[d["id"]] = f
        self.place_zone(f)
        f.refresh()
        f.show()
        return f

    # -- ecrans : une position memorisee par configuration d'ecrans
    def _screen_added(self, s):
        s.geometryChanged.connect(self._screens_event)
        self._screens_event()

    def _screens_event(self, *args):
        self.screens_dirty = True        # on ignore les deplacements faits par Windows
        self.screen_timer.start()

    def on_screens_changed(self):
        self.screens_dirty = False
        self.sig = screens_sig()
        for f in self.zones.values():
            self.place_zone(f)
            win_push_bottom(f)
        self.save_soon()

    def record_geom(self, f):
        if self.restoring or self.screens_dirty:
            return
        d = f.data
        g = f.geometry()
        d["x"], d["y"], d["w"] = g.x(), g.y(), g.width()
        if not d.get("collapsed"):
            d["h"] = g.height()
        h = d.get("h", g.height())
        d.setdefault("pos", {})[self.sig] = [g.x(), g.y(), g.width(), h]
        s = QGuiApplication.screenAt(g.center()) or QGuiApplication.primaryScreen()
        ag = s.availableGeometry()
        d["screen"] = screen_id(s)
        d["rel"] = [(g.x() - ag.x()) / ag.width(), (g.y() - ag.y()) / ag.height(),
                    g.width() / ag.width(), h / ag.height()]
        self.save_soon()

    @staticmethod
    def rect_from_rel(ag, rel):
        rx, ry, rw, rh = rel
        return QRect(ag.x() + round(rx * ag.width()), ag.y() + round(ry * ag.height()),
                     max(MIN_W, round(rw * ag.width())), max(MIN_H, round(rh * ag.height())))

    @staticmethod
    def fit(rect):
        screens = QGuiApplication.screens()
        best, area = None, 0
        for s in screens:
            inter = s.availableGeometry().intersected(rect)
            a = inter.width() * inter.height()
            if a > area:
                best, area = s, a
        if best is None:
            best = QGuiApplication.primaryScreen()
            ag = best.availableGeometry()
            rect = QRect(ag.x() + 40, ag.y() + 40, rect.width(), rect.height())
        ag = best.availableGeometry()
        w, h = min(rect.width(), ag.width()), min(rect.height(), ag.height())
        x = max(ag.left(), min(rect.x(), ag.right() - w + 1))
        y = max(ag.top(), min(rect.y(), ag.bottom() - h + 1))
        return QRect(x, y, w, h)

    def place_zone(self, f):
        d = f.data
        pos = d.get("pos", {}).get(self.sig)
        if pos:
            rect = QRect(*pos)
        else:
            scr = next((s for s in QGuiApplication.screens() if screen_id(s) == d.get("screen")), None)
            if scr and d.get("rel"):
                rect = self.rect_from_rel(scr.availableGeometry(), d["rel"])
            else:
                rect = QRect(d.get("x", 60), d.get("y", 60), d.get("w", 520), d.get("h", 260))
        rect = self.fit(rect)
        self.restoring = True
        f.setGeometry(rect.x(), rect.y(), rect.width(), TITLE_H if d.get("collapsed") else rect.height())
        self.restoring = False
        d["h"] = rect.height()
        if f.isVisible():
            self.record_geom(f)

    # -- aimantation
    def _neighbours(self, f):
        res = []
        for o in self.zones.values():
            if o is f or not o.isVisible():
                continue
            g = o.geometry()
            res.append((g.left(), g.left() + g.width(), g.top(), g.top() + g.height(), o))
        return res

    @staticmethod
    def _best(value, cands):
        best, dist = value, SNAP_DIST + 1
        for c in cands:
            d = abs(c - value)
            if d < dist:
                best, dist = c, d
        return best

    @staticmethod
    def _nearest(value, cands):
        ds = [c - value for c in cands if abs(c - value) <= SNAP_DIST]
        return min(ds, key=abs) if ds else None

    def _screen_ag(self, rect):
        s = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        return s.availableGeometry()

    def snap_move(self, f, p):
        w, h = f.width(), f.height()
        L, T = p.x(), p.y()
        R, B = L + w, T + h
        ag = self._screen_ag(QRect(L, T, w, h))
        lx = [ag.left() + ZONE_GAP, ag.left()]
        rx = [ag.left() + ag.width() - ZONE_GAP, ag.left() + ag.width()]
        ty = [ag.top() + ZONE_GAP, ag.top()]
        by = [ag.top() + ag.height() - ZONE_GAP, ag.top() + ag.height()]
        for oL, oR, oT, oB, _ in self._neighbours(f):
            near_v = T < oB + 150 and B > oT - 150      # proches verticalement
            near_h = L < oR + 150 and R > oL - 150
            if near_v:
                lx += [oL, oR + ZONE_GAP]
                rx += [oR, oL - ZONE_GAP]
            if near_h:
                ty += [oT, oB + ZONE_GAP]
                by += [oB, oT - ZONE_GAP]
        return QPoint(L + self._delta(L, lx, R, rx), T + self._delta(T, ty, B, by))

    def _delta(self, a, ca, b, cb):
        """Plus petit deplacement qui colle le bord a ou le bord b a une ligne d'aimantation."""
        opts = [d for d in (self._nearest(a, ca), self._nearest(b, cb)) if d is not None]
        return min(opts, key=abs) if opts else 0

    def _col_widths(self):
        sx = self.tile[0] + GAP
        return [2 * EDGE + 2 * PAD - GAP + n * sx for n in range(1, 25)]

    def _row_heights(self):
        sy = self.tile[1] + GAP
        return [TITLE_H + EDGE + 2 * PAD + n * sy for n in range(1, 20)]

    def snap_resize(self, f, g, flags):
        L, T = g.left(), g.top()
        R, B = L + g.width(), T + g.height()
        ag = self._screen_ag(g)
        nb = self._neighbours(f)
        widths = self._col_widths() + [oR - oL for oL, oR, _, _, _ in nb]
        heights = self._row_heights() + [oB - oT for _, _, oT, oB, _ in nb]
        if flags & 1:
            c = [ag.left() + ZONE_GAP, ag.left()] + [R - w for w in widths]
            for oL, oR, _, _, _ in nb:
                c += [oL, oR + ZONE_GAP]
            L = min(self._best(L, c), R - MIN_W)
        if flags & 2:
            c = [ag.left() + ag.width() - ZONE_GAP, ag.left() + ag.width()] + [L + w for w in widths]
            for oL, oR, _, _, _ in nb:
                c += [oR, oL - ZONE_GAP]
            R = max(self._best(R, c), L + MIN_W)
        if flags & 4:
            c = [ag.top() + ZONE_GAP, ag.top()] + [B - h for h in heights]
            for _, _, oT, oB, _ in nb:
                c += [oT, oB + ZONE_GAP]
            T = min(self._best(T, c), B - MIN_H)
        if flags & 8:
            c = [ag.top() + ag.height() - ZONE_GAP, ag.top() + ag.height()] + [T + h for h in heights]
            for _, _, oT, oB, _ in nb:
                c += [oB, oT - ZONE_GAP]
            B = max(self._best(B, c), T + MIN_H)
        return QRect(L, T, R - L, B - T)

    def match_size(self, f, other, width, height):
        g = f.geometry()
        w = other.width() if width else g.width()
        h = other.data.get("h", other.height()) if height else f.data.get("h", g.height())
        rect = self.fit(QRect(g.x(), g.y(), w, h))
        f.data["h"] = rect.height()
        f.setGeometry(rect.x(), rect.y(), rect.width(),
                      TITLE_H if f.data.get("collapsed") else rect.height())
        win_push_bottom(f)

    def send_to_screen(self, f, screen):
        g = f.geometry()
        cur = QGuiApplication.screenAt(g.center()) or QGuiApplication.primaryScreen()
        ag = cur.availableGeometry()
        h = f.data.get("h", g.height())
        rel = [(g.x() - ag.x()) / ag.width(), (g.y() - ag.y()) / ag.height(),
               g.width() / ag.width(), h / ag.height()]
        rect = self.fit(self.rect_from_rel(screen.availableGeometry(), rel))
        f.data["h"] = rect.height()
        f.setGeometry(rect.x(), rect.y(), rect.width(),
                      TITLE_H if f.data.get("collapsed") else rect.height())
        win_push_bottom(f)

    def new_zone(self, pos=None, edit=True, name="Nouvelle zone", tab_type=None):
        n = len(self.zones)
        if isinstance(pos, QPoint):
            x, y = pos.x() + 20, pos.y() + 20
        else:
            g = QApplication.primaryScreen().availableGeometry()
            x, y = g.left() + 40 + 30 * (n % 10), g.top() + 40 + 30 * (n % 10)
        tab = {"name": name, "items": []}
        if tab_type:
            tab["type"] = tab_type
        w, h = (320, 190) if tab_type == "perf" else (520, 260)
        d = {"id": uuid.uuid4().hex, "x": x, "y": y, "w": w, "h": h,
             "color": ACCENTS[(n + 1) % len(ACCENTS)][1], "collapsed": False,
             "tabs": [tab], "active": 0}
        f = self.create_zone(d)
        self.save_soon()
        if edit:
            QTimer.singleShot(60, lambda: f.tabbar.start_edit(0))

    def delete_zone(self, fid):
        f = self.zones.get(fid)
        if not f:
            return
        all_items = [it for t in f.data["tabs"] for it in t["items"]]
        if all_items:
            r = QMessageBox.question(None, APP_NAME,
                                     f"Supprimer la zone « {f.data['tabs'][0]['name']} » et ses onglets ?\n"
                                     "Les éléments qu'elle contient seront remis sur le bureau.")
            if r != QMessageBox.Yes:
                return
        for it in all_items:
            self.restore_file(it)
        del self.zones[fid]
        f.hide()
        f.deleteLater()
        self.save()

    def update_merge_target(self, src, gp):
        tgt = None
        for f in self.zones.values():
            if f is src or not f.isVisible():
                continue
            g = f.geometry()
            if g.contains(gp) and gp.y() <= g.y() + TITLE_H + 6:
                tgt = f
                break
        if tgt is not self.merge_target:
            if self.merge_target is not None:
                self.merge_target.merge_hint = False
                self.merge_target.update()
                self.merge_target.grid.update()
            self.merge_target = tgt
            if tgt is not None:
                tgt.merge_hint = True
                tgt.update()
                tgt.grid.update()

    def merge_zones(self, src, tgt):
        tgt.merge_hint = False
        self.merge_target = None
        n = len(tgt.data["tabs"])
        tgt.data["tabs"].extend(src.data["tabs"])
        tgt.data["active"] = n
        self.zones.pop(src.fid, None)
        src.hide()
        src.deleteLater()
        if tgt.data.get("collapsed"):
            tgt.toggle_collapse()
        tgt.refresh()
        win_push_bottom(tgt)
        self.save()

    def sort_tab(self, fid):
        f = self.zones[fid]
        f.items().sort(key=lambda it: display_name(it["path"]).lower())
        f.refresh()
        self.save_soon()

    def set_locked(self, on):
        self.locked = bool(on)
        for f in self.zones.values():
            f.tabbar.update()
        self.save_soon()

    def set_move(self, on):
        self.move_files = bool(on)
        self.save_soon()

    def blur_active(self):
        return self.blur and self.theme["blur_ok"]

    def set_blur(self, on):
        self.blur = bool(on)
        self._apply_look()

    def merged_theme(self, key):
        t = dict(THEMES[key])
        over = self.theme_over.get(key, {})
        t.update(over)
        if "bg" in over:
            t.pop("gradient", None)          # couleur de fond choisie a la main : pas de degrade
        if "accent" in over:
            t.pop("border_gradient", None)
        return t

    def accent_for(self, zone):
        acc = self.theme.get("accent")
        return QColor(acc) if acc else QColor(zone.data.get("color", "#4C8BF5"))

    def set_theme(self, key):
        self.theme_key = key
        self.theme = self.merged_theme(key)
        for k, a in self.theme_actions:
            a.setChecked(k == key)
        self._apply_look()
        if self.theme_dialog and self.theme_dialog.isVisible():
            self.theme_dialog.load()

    def set_override(self, field, value):
        self.theme_over.setdefault(self.theme_key, {})[field] = value
        self.theme = self.merged_theme(self.theme_key)
        self._apply_look()

    def reset_theme(self):
        self.theme_over.pop(self.theme_key, None)
        self.theme = self.merged_theme(self.theme_key)
        self._apply_look()

    def open_theme_dialog(self):
        if self.theme_dialog is None:
            self.theme_dialog = ThemeDialog(self)
        self.theme_dialog.load()
        self.theme_dialog.show()
        self.theme_dialog.raise_()
        self.theme_dialog.activateWindow()

    def _apply_look(self):
        for f in self.zones.values():
            win_blur(f, self.blur_active())
            f.refresh()
            f.update()
        self.save_soon()

    def empty_recycle_bin(self):
        if not IS_WIN:
            return
        try:
            # Windows affiche lui-meme la confirmation
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0)
        except Exception:
            pass

    def add_special(self, fid, tab, key, idx=None, from_desktop=False):
        f = self.zones.get(fid)
        if not f or key not in SPECIALS:
            return
        path = "special:" + key
        if self.find_item(path)[0]:
            self.move_item(path, fid, tab, idx)
            return
        item = {"path": path, "special": key}
        if from_desktop and self.move_files and key in SPECIAL_CLSID:
            win_set_desktop_ns_icon(SPECIAL_CLSID[key], visible=False)   # l'original quitte le bureau
            item["hid_desktop"] = True
        self._insert(f, tab, item, idx)
        f.refresh()
        self.save()

    def special_menu(self, parent, fid, tab, idx=None):
        m = self.menu(parent)
        for key, (label, _) in SPECIALS.items():
            m.addAction(special_icon(key), label,
                        lambda k=key: self.add_special(fid, tab, k, idx))
        return m

    def set_size(self, key):
        self.size_key = key
        self.tile = SIZES[key]
        for f in self.zones.values():
            f.refresh()
        self.save_soon()

    # -- elements
    def find_item(self, path):
        for f in self.zones.values():
            for ti, t in enumerate(f.data["tabs"]):
                for it in t["items"]:
                    if same_path(it["path"], path):
                        return f, ti, it
        return None, None, None

    def _insert(self, zone, tab, item, idx):
        lst = zone.data["tabs"][tab]["items"]
        if idx is None or idx > len(lst):
            idx = len(lst)
        lst.insert(idx, item)
        return idx + 1

    def add_external(self, fid, tab, paths, idx):
        dst = self.zones.get(fid)
        if not dst or tab >= len(dst.data["tabs"]):
            return
        failed = []
        touched = {fid}
        for p in paths:
            if not os.path.exists(p):
                continue
            src, _, existing = self.find_item(p)
            if existing:
                for t in src.data["tabs"]:
                    if existing in t["items"]:
                        t["items"].remove(existing)
                touched.add(src.fid)
                item = existing
            elif self.move_files and is_on_desktop(p):
                try:
                    dest = unique_path(STORE_DIR, os.path.basename(p.rstrip("\\/")))
                    shutil.move(p, dest)
                    item = {"path": dest, "origin": os.path.dirname(os.path.abspath(p))}
                except OSError:
                    item = {"path": p}
                    failed.append(display_name(p))
            else:
                item = {"path": p}
            idx = self._insert(dst, tab, item, idx)
        for t in touched:
            if t in self.zones:
                self.zones[t].refresh()
        self.save()
        if failed:
            self.notify("Certains éléments n'ont pas pu être retirés du bureau "
                        "(droits administrateur ?). Ils ont été ajoutés en lien : " + ", ".join(failed))

    def restore_file(self, it):
        if it.get("hid_desktop") and it.get("special") in SPECIAL_CLSID:
            win_set_desktop_ns_icon(SPECIAL_CLSID[it["special"]], visible=True)
            return
        if not it.get("origin") or not os.path.exists(it["path"]) or not is_in_store(it["path"]):
            return
        name = os.path.basename(it["path"].rstrip("\\/"))
        for folder in (it["origin"], user_desktop()):
            try:
                if os.path.isdir(folder):
                    dest = unique_path(folder, name)
                    self.ignore_names.add(os.path.basename(dest).lower())
                    shutil.move(it["path"], dest)
                    return
            except OSError:
                continue

    def remove_item(self, path, restore):
        f, ti, it = self.find_item(path)
        if not f:
            return
        if restore:
            self.restore_file(it)
        f.data["tabs"][ti]["items"].remove(it)
        f.refresh()
        self.save()

    def move_item(self, path, dfid, dtab, idx):
        src, stab, item = self.find_item(path)
        dst = self.zones.get(dfid)
        if not src or not dst or dtab >= len(dst.data["tabs"]):
            return
        lst = src.data["tabs"][stab]["items"]
        old = lst.index(item)
        lst.remove(item)
        if src is dst and stab == dtab and idx is not None and idx > old:
            idx -= 1
        self._insert(dst, dtab, item, idx)
        src.refresh()
        if dst is not src:
            dst.refresh()
        self.save()

    def run_pending(self):
        op, self.pending = self.pending, None
        if op and op[0] == "move":
            _, path, dfid, dtab, idx = op
            self.move_item(path, dfid, dtab, idx)

    def launch(self, path):
        if path.startswith("special:"):
            key = path.split(":", 1)[1]
            target = SPECIALS.get(key, ("", ""))[1]
            if key in SPECIAL_CLSID:
                target = "shell:::" + SPECIAL_CLSID[key]
            try:
                if target.startswith("ms-settings"):
                    os.startfile(target)
                else:
                    subprocess.Popen(["explorer.exe", target])
            except OSError as ex:
                QMessageBox.warning(None, APP_NAME, f"Impossible d'ouvrir :\n{ex}")
            return
        if not os.path.exists(path):
            QMessageBox.warning(None, APP_NAME, f"Élément introuvable :\n{path}")
            return
        try:
            if IS_WIN:
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as ex:
            QMessageBox.warning(None, APP_NAME, f"Impossible d'ouvrir :\n{path}\n\n{ex}")

    def reveal(self, path):
        if IS_WIN:
            subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])

    # -- interface
    def menu(self, parent):
        m = QMenu(parent)
        m.setStyleSheet(MENU_CSS)
        return m

    def notify(self, msg):
        if self.tray and self.tray.isVisible():
            self.tray.showMessage(APP_NAME, msg, QSystemTrayIcon.Information, 6000)

    def show_all(self):
        for f in self.zones.values():
            f.show()
            self.place_zone(f)
            win_push_bottom(f)

    def quick_hide_toggle(self):
        self.qh_hidden = not self.qh_hidden
        mode = self.qh_mode
        if mode in ("both", "icons"):
            set_desktop_icons_visible(not self.qh_hidden)
        if mode in ("both", "zones"):
            if self.qh_hidden:
                for f in self.zones.values():
                    f.hide()
            else:
                self.show_all()

    def set_qh_mode(self, mode):
        if self.qh_hidden:
            self.quick_hide_toggle()     # tout reafficher avant de changer
        self.qh_mode = mode
        for k, a in self.qh_actions:
            a.setChecked(k == mode)
        if mode == "off":
            self.dbl.stop()
        else:
            self.dbl.start()
        self.save_soon()

    def toggle_all(self):
        if any(f.isVisible() for f in self.zones.values()):
            for f in self.zones.values():
                f.hide()
        else:
            self.show_all()

    def install(self):
        """Copie le programme dans %APPDATA%\\TatamiDesk\\app et cree un raccourci menu Demarrer (pythonw, sans console)."""
        try:
            app_dir = os.path.join(DATA_DIR, "app")
            os.makedirs(app_dir, exist_ok=True)
            frozen = getattr(sys, "frozen", False)
            if frozen:      # version .exe : on copie l'exe lui-meme
                here = os.path.abspath(sys.executable)
                target = os.path.join(app_dir, "TatamiDesk.exe")
            else:
                here = os.path.abspath(sys.argv[0])
                target = os.path.join(app_dir, "tatamidesk.pyw")
            if not same_path(here, target):
                shutil.copy2(here, target)
            pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if not os.path.exists(pyw):
                pyw = sys.executable
            programs = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
            lnk = os.path.join(programs, "Tatami Desk.lnk")
            q = lambda x: x.replace("'", "''")
            ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(lnk)}');" +
                  (f"$s.TargetPath='{q(target)}';" if frozen else
                   f"$s.TargetPath='{q(pyw)}';$s.Arguments='\"{q(target)}\"';") +
                  f"$s.WorkingDirectory='{q(app_dir)}';$s.Description='Tatami Desk';$s.Save()")
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           check=True, creationflags=0x08000000)
            if get_startup():
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ,
                                      f'"{target}"' if frozen else f'"{pyw}" "{target}"')
            QMessageBox.information(None, APP_NAME,
                                    "Tatami Desk est installé.\n\n"
                                    "Tu le trouves maintenant dans le menu Démarrer (tape « Tatami »).\n"
                                    "Le fichier dans Téléchargements peut être supprimé.")
        except Exception as ex:
            QMessageBox.warning(None, APP_NAME, f"Installation impossible :\n{ex}")

    # -- parametres
    def open_settings(self, page=0):
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.load()
        if isinstance(page, int):
            self.settings_dialog.nav.setCurrentRow(page)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def set_snap(self, on=None, dist=None, gap=None):
        global SNAP_DIST, ZONE_GAP
        if on is not None:
            self.snap_on = bool(on)
        if dist is not None:
            SNAP_DIST = int(dist)
        if gap is not None:
            ZONE_GAP = int(gap)
        self.save_soon()

    def backups(self):
        bdir = os.path.join(DATA_DIR, "backups")
        try:
            return sorted((x for x in os.listdir(bdir) if x.startswith("config-")), reverse=True)
        except OSError:
            return []

    def restore_backup(self, name):
        src = os.path.join(DATA_DIR, "backups", name)
        r = QMessageBox.question(None, APP_NAME,
                                 f"Restaurer la disposition du {name[7:11]}-{name[11:13]}-{name[13:15]} ?\n"
                                 "L'application va redémarrer.")
        if r != QMessageBox.Yes:
            return
        try:
            shutil.copy2(CONFIG, os.path.join(DATA_DIR, "backups", "avant-restauration.json"))
        except Exception:
            pass
        shutil.copy2(src, CONFIG)
        self.restart(save=False)

    def restart(self, save=True):
        if save:
            self.save()
        self.no_save = True
        self.save_timer.stop()
        self.save_timer.timeout.disconnect()
        self.dbl.stop()
        if IS_WIN and _MUTEX:
            ctypes.windll.kernel32.CloseHandle(_MUTEX)
        exe = sys.executable
        pw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pw) and not getattr(sys, "frozen", False):
            exe = pw
        args = [exe] if getattr(sys, "frozen", False) else [exe, os.path.abspath(sys.argv[0])]
        subprocess.Popen(args)
        self.tray.hide()
        self.qapp.quit()

    # -- rangement automatique
    def dest_list(self):
        out = []
        for f in self.zones.values():
            tabs = f.data["tabs"]
            for t in tabs:
                label = t["name"] if len(tabs) == 1 else f"{tabs[0]['name']} › {t['name']}"
                out.append((label, f.fid, t["name"]))
        return out

    def dest_label(self, fid, tabname):
        for label, f, t in self.dest_list():
            if f == fid and t == tabname:
                return label
        return "(zone supprimée)"

    def resolve_dest(self, fid, tabname):
        f = self.zones.get(fid)
        if not f:
            return None
        idx = next((i for i, t in enumerate(f.data["tabs"]) if t["name"] == tabname), 0)
        return f, idx

    def dest_for(self, path):
        for r in self.rules:
            if rule_matches(r, path):
                d = self.resolve_dest(r.get("fid"), r.get("tab"))
                if d:
                    return d
        if self.default_dest:
            return self.resolve_dest(self.default_dest.get("fid"), self.default_dest.get("tab"))
        return None

    def desktop_entries(self):
        d = user_desktop()
        res = []
        try:
            names = os.listdir(d)
        except OSError:
            return res
        for name in names:
            low = name.lower()
            if low == "desktop.ini" or name.startswith("~$") or os.path.splitext(low)[1] in IGNORE_EXT:
                continue
            p = os.path.join(d, name)
            try:
                if IS_WIN and (os.stat(p).st_file_attributes & 2):   # fichier cache
                    continue
            except (OSError, AttributeError):
                pass
            res.append(p)
        return res

    def sort_desktop(self, paths=None):
        paths = self.desktop_entries() if paths is None else paths
        groups = {}
        for p in paths:
            d = self.dest_for(p)
            if d:
                groups.setdefault((d[0].fid, d[1]), []).append(p)
        n = 0
        for (fid, ti), ps in groups.items():
            self.add_external(fid, ti, ps, None)
            n += len(ps)
        return n

    def start_watch(self):
        d = user_desktop()
        if d and d not in self.watcher.directories():
            self.watcher.addPath(d)
        self.known = set(self.desktop_entries())

    def stop_watch(self):
        dirs = self.watcher.directories()
        if dirs:
            self.watcher.removePaths(dirs)

    def set_auto_sort(self, on):
        self.auto_sort = bool(on)
        if self.auto_sort:
            self.start_watch()
        else:
            self.stop_watch()
        self.save_soon()

    def _on_desktop_changed(self):
        cur = set(self.desktop_entries())
        new = []
        for p in cur - self.known:
            b = os.path.basename(p).lower()
            if b in self.ignore_names:
                self.ignore_names.discard(b)      # remis volontairement sur le bureau
                continue
            new.append(p)
        self.known = cur
        if new and self.auto_sort:
            n = self.sort_desktop(new)
            if n:
                self.known = set(self.desktop_entries())
                self.notify(f"{n} nouvel(s) élément(s) rangé(s) automatiquement.")

    def toggle_startup(self, on):
        try:
            set_startup(on)
        except Exception as ex:
            QMessageBox.warning(None, APP_NAME, f"Impossible de modifier le démarrage automatique :\n{ex}")

    def make_tray(self):
        self.tray = QSystemTrayIcon(make_app_icon())
        self.tray.setToolTip(f"{APP_NAME} (clic : afficher / masquer)")
        self.tray.activated.connect(self._tray_activated)
        m = self.menu(None)
        bold = m.addAction("Paramètres…", self.open_settings)
        f = bold.font()
        f.setBold(True)
        bold.setFont(f)
        m.addSeparator()
        m.addAction("Nouvelle zone", lambda: self.new_zone())
        m.addAction("Nouvelle zone Performances", lambda: self.new_zone(edit=False, name="Performances", tab_type="perf"))
        m.addAction("Afficher / masquer les zones", self.toggle_all)
        tm = sticky_submenu(m, "Thème")
        self.theme_actions = []
        for key in THEME_ORDER:
            a = make_sticky(tm.addAction(THEMES[key]["label"]))
            a.setCheckable(True)
            a.setChecked(key == self.theme_key)
            a.triggered.connect(lambda _=False, k=key: self.set_theme(k))
            self.theme_actions.append((key, a))
        tm.addSeparator()
        tm.addAction("Personnaliser le thème…", self.open_theme_dialog)
        m.addSeparator()
        m.addAction("Quitter", self.quit)
        self.tray_menu = m
        self.tray.setContextMenu(m)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_all()
        elif reason == QSystemTrayIcon.DoubleClick:
            self.open_settings()

    def _pick_size(self, key):
        self.set_size(key)

    def quit(self):
        self.dbl.stop()
        if IS_WIN:
            set_desktop_icons_visible(True)
        self.save()
        self.tray.hide()
        self.qapp.quit()


def main():
    if IS_WIN:
        global _MUTEX
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = ctypes.c_void_p
        _MUTEX = k32.CreateMutexW(None, False, "Local\\TatamiDeskSingleInstance")
        if k32.GetLastError() == 183:  # deja lance
            return
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setStyle("Fusion")
    qapp.setFont(QFont("Segoe UI", 9))
    qapp.setWindowIcon(make_app_icon())
    app = TatamiApp(qapp)
    qapp.aboutToQuit.connect(app.save)
    if IS_WIN:
        qapp.aboutToQuit.connect(lambda: set_desktop_icons_visible(True))
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
