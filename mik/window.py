"""Multi Image Kitchen — раскладка из MIK.pb (WindowMain / MakeMenuBar / MakeToolBar)."""

import getpass
import hashlib
import platform
import shutil
import subprocess
import urllib.parse
import zipfile
from pathlib import Path

from PyQt6.QtCore import QSettings, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QShortcut, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QMessageBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from mik.engine import (
    is_aml_image,
    is_ext4,
    is_sparse,
    pack_firmware,
    pack_partition,
    unpack_firmware,
    unpack_partition,
)

def _assets_dir() -> Path:
    import sys

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / "mik"
    return Path(__file__).resolve().parents[1] / "assets" / "mik"


ASSETS = _assets_dir()
PARTS = ("system", "vendor", "product", "odm")
NEWS = "https://t.me/IMG_TOOLS_NEWS"
DISCUSSION = "https://t.me/IMG_Tools"
CHANNEL = "https://www.youtube.com/channel/UCW4P2Eb49-15phyn_T0i0Fg"


LOCALES = (1049, 1033, 1049, 1028, 2052, 1059, 1058, 1046, 1033, 1033, 1033)


def lng(n: int) -> str:
    lid = getattr(lng, "_id", 1049)
    if getattr(lng, "_lid", None) != lid:
        path = ASSETS / "language" / f"{lid}.lng"
        if not path.is_file():
            path = ASSETS / "1049.lng"
        raw = path.read_text(encoding="utf-8", errors="replace")
        lng._lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        lng._lid = lid
    lines = lng._lines
    if 1 <= n <= len(lines):
        return lines[n - 1]
    return ""


def ico(name: str) -> QIcon:
    path = ASSETS / name
    return QIcon(str(path)) if path.is_file() else QIcon()


def hint() -> str:
    return (
        f"{lng(68)} (*.img), {lng(100)} (*.zip), {lng(66)} "
        f"(*.img, *.PARTITION, *.fex, *.new.dat, *.new.dat.br) {lng(67)}"
    )


class Job(QThread):
    line = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self) -> None:
        try:
            self.fn(self.line.emit)
            self.done.emit(True, "")
        except Exception as e:
            self.line.emit(str(e))
            self.done.emit(False, str(e))


def _put(parent, widget, x, y, w, h):
    widget.setParent(parent)
    widget.setGeometry(x, y, w, h)
    return widget


def _ui_font(size: int = 8, italic: bool = False) -> QFont:
    font = QFont("Tahoma", size)
    if not font.exactMatch():
        font = QFont("Geneva", size)
    font.setItalic(italic)
    return font


class SettingsDialog(QDialog):
    """Окно 395×383 из WindowSettings: вкладки и координаты гаджетов как в MIK.pb."""

    def __init__(self, parent: "MikWindow", settings: QSettings):
        super().__init__(parent)
        self.mik = parent
        self.settings = settings
        self.setWindowTitle(lng(8))
        self.setWindowIcon(ico("setting.ico"))
        self.setFixedSize(395, 383)
        self.setFont(_ui_font())
        self.setStyleSheet("QDialog, QTabWidget, QWidget { background: #f0f0f0; color: #000; }")

        tabs = QTabWidget(self)
        tabs.setGeometry(0, 0, 395, 383)
        tabs.setDocumentMode(True)
        tabs.tabBar().setExpanding(True)
        tabs.tabBar().setUsesScrollButtons(False)
        tabs.setStyleSheet("QTabBar::tab { padding: 2px 1px; }")
        self.pages = {}
        for key, title in (
            ("unpack", lng(50)),
            ("pack", lng(51)),
            ("other", lng(82)),
            ("apk", lng(127)),
            ("window", lng(43)),
            ("sound", lng(60)),
            ("lang", lng(85)),
        ):
            page = QWidget()
            tabs.addTab(page, title)
            self.pages[key] = page
        tabs.setCurrentIndex(int(settings.value("setting_stage", 0)))
        tabs.currentChanged.connect(lambda i: settings.setValue("setting_stage", i))
        self._unpack()
        self._pack()
        self._other()
        self._apk()
        self._window()
        self._sound()
        self._lang()

    def _b(self, key: str, default: bool) -> bool:
        return self.settings.value(key, default, type=bool)

    def _box(self, page, x, y, w, h, text, key, default, italic=False, on=None):
        box = _put(page, QCheckBox(text, page), x, y, w, h)
        if italic:
            box.setFont(_ui_font(10, italic=True))
        box.setChecked(self._b(key, default))

        def changed(on_state, key=key, hook=on):
            self.settings.setValue(key, on_state)
            if hook:
                hook(on_state)

        box.toggled.connect(changed)
        return box

    def _unpack(self) -> None:
        page = self.pages["unpack"]
        _put(page, QGroupBox(lng(52) + " ", page), 10, 10, 364, 172)
        self._box(page, 20, 30, 285, 20, lng(53) + " SUPER (Win x86/x64)", "unpack/super", True, True)
        for y, name in ((55, "SYSTEM"), (80, "VENDOR"), (105, "PRODUCT"), (130, "ODM")):
            self._box(page, 20, y, 265, 20, lng(53) + " " + name, f"unpack/{name.lower()}", True)
        self._box(page, 20, 155, 265, 20, lng(54), "open_folder", True)
        _put(page, QGroupBox("RockChip ", page), 10, 185, 364, 45)
        _put(page, QLabel("imgRePackerRK", page), 20, 205, 97, 20)
        v6 = _put(page, QRadioButton("v 1.06", page), 120, 203, 60, 20)
        v7 = _put(page, QRadioButton("v 1.07 h_test", page), 180, 203, 110, 20)
        (v7 if self.settings.value("rk_ver", "106") == "107" else v6).setChecked(True)
        v6.toggled.connect(lambda on: on and self.settings.setValue("rk_ver", "106"))
        v7.toggled.connect(lambda on: on and self.settings.setValue("rk_ver", "107"))
        sub = self._box(page, 20, 245, 345, 20, lng(137), "subfolder", True)
        seven = self._box(page, 20, 270, 345, 20, lng(138), "seven_unpack", False)
        self._box(page, 20, 295, 345, 20, lng(139), "delete_archive", False)
        self._box(page, 20, 320, 345, 20, lng(81), "not_delete", False)
        seven.setEnabled(sub.isChecked())
        sub.toggled.connect(seven.setEnabled)

    def _pack(self) -> None:
        page = self.pages["pack"]
        _put(page, QGroupBox(lng(55) + " ", page), 10, 10, 364, 150)
        for y, name in ((30, "SYSTEM"), (55, "VENDOR"), (80, "PRODUCT"), (105, "ODM")):
            self._box(page, 20, y, 345, 20, lng(56) + " " + name, f"pack/{name.lower()}", True)
        self._box(page, 20, 130, 345, 20, lng(56) + " SUPER (Win x64 Only!)", "pack/super", True, True)
        _put(page, QGroupBox("Amlogic ", page), 10, 168, 364, 70)
        self._box(page, 20, 185, 345, 20, lng(57), "index_add", False)
        self._box(page, 20, 210, 300, 20, lng(58) + " Amlogic USB Burning Tool", "open_usb", False)
        browse = _put(page, QPushButton("...", page), 344, 211, 20, 20)
        browse.setToolTip(lng(59) + " USB_Burning_Tool.exe")
        browse.clicked.connect(self._pick_usb)
        self._box(page, 20, 245, 345, 20, lng(140) + ": *.md5", "get_hash", False)
        seven = self._box(page, 20, 270, 345, 20, lng(141) + ": *.7z", "seven_pack", False)
        _put(page, QLabel(lng(105), page), 20, 297, 110, 20)
        level = _put(page, QComboBox(page), 130, 294, 40, 20)
        level.addItems(["0", "1", "3", "5", "7", "9"])
        cur = str(self.settings.value("seven_level", "0"))
        level.setCurrentIndex(max(0, level.findText(cur)))
        level.currentTextChanged.connect(lambda t: self.settings.setValue("seven_level", t))
        _put(page, QLabel(lng(143) + ": ", page), 205, 297, 90, 20)
        size = _put(page, QLineEdit(str(self.settings.value("size_part", "")), page), 295, 294, 40, 20)
        size.textChanged.connect(lambda t: self.settings.setValue("size_part", t))
        _put(page, QLabel("Mb", page), 340, 297, 50, 20)
        delete = self._box(page, 20, 320, 345, 20, lng(142), "delete_image", False)

        def gate(on, level=level, size=size, delete=delete):
            level.setEnabled(on)
            size.setEnabled(on)
            delete.setEnabled(on)

        gate(seven.isChecked())
        seven.toggled.connect(gate)

    def _pick_usb(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, lng(59), "", "(*)")
        if path:
            self.settings.setValue("usb_tool", path)

    def _other(self) -> None:
        page = self.pages["other"]
        self._box(page, 10, 10, 240, 20, lng(106) + " 4", "transfer", False)
        _put(page, QGroupBox("Brotli keys: ", page), 10, 37, 364, 70)
        _put(page, QLabel(lng(108), page), 20, 56, 90, 20)
        dec = _put(page, QLineEdit(str(self.settings.value("decompress", "--verbose")), page), 120, 52, 243, 20)
        dec.textChanged.connect(lambda t: self.settings.setValue("decompress", t))
        _put(page, QLabel(lng(107), page), 20, 80, 90, 20)
        comp = _put(page, QLineEdit(str(self.settings.value("compress", "--force --quality 7 --verbose")), page), 120, 78, 243, 20)
        comp.textChanged.connect(lambda t: self.settings.setValue("compress", t))
        _put(page, QGroupBox("Update.zip: ", page), 10, 111, 364, 70)
        _put(page, QLabel(lng(105), page), 20, 133, 120, 20)
        level = _put(page, QComboBox(page), 140, 129, 40, 20)
        level.addItems(["0", "1", "3", "5", "7", "9"])
        level.setCurrentIndex(max(0, level.findText(str(self.settings.value("compress_level", "0")))))
        level.currentTextChanged.connect(lambda t: self.settings.setValue("compress_level", t))
        self._box(page, 20, 152, 220, 20, lng(104), "signature", True)
        _put(page, QGroupBox("Make ext4: ", page), 10, 186, 364, 100)
        expand = self._box(page, 20, 209, 300, 20, lng(144), "expand_size", True)
        _put(page, QLabel(lng(145) + ":", page), 20, 235, 214, 20)
        free = _put(page, QLineEdit(str(self.settings.value("free_space", 100)), page), 235, 232, 50, 20)
        free.textChanged.connect(lambda t: self.settings.setValue("free_space", t))
        _put(page, QLabel("Mb", page), 290, 235, 50, 20)
        resize = self._box(page, 20, 257, 290, 20, lng(171), "resize", True)

        def gate(on, free=free, resize=resize):
            free.setEnabled(not on)
            resize.setEnabled(not on)

        gate(expand.isChecked())
        expand.toggled.connect(gate)
        self._box(page, 10, 295, 290, 20, lng(146) + " (*.bak)", "no_backup", True)
        self._box(page, 10, 320, 290, 20, lng(147) + " (*.org)", "no_org", True)

    def _apk(self) -> None:
        page = self.pages["apk"]
        self._box(page, 10, 10, 270, 20, lng(128) + " framework-res.apk", "framework", False)
        browse = _put(page, QPushButton("...", page), 330, 10, 20, 20)
        browse.setToolTip(lng(129) + " framework-res.apk")
        browse.clicked.connect(self._pick_framework)
        self._box(page, 10, 35, 270, 20, lng(104), "signature_apk", True)
        self._box(page, 10, 60, 270, 20, lng(130), "alignment", True)

    def _pick_framework(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, lng(129), "", "apk (*.apk)")
        if path:
            self.settings.setValue("framework_path", path)

    def _window(self) -> None:
        page = self.pages["window"]
        self._box(page, 10, 10, 140, 20, lng(44), "on_top", False, on=self.mik._toggle_top)
        bg = _put(page, QPushButton(lng(45), page), 219, 12, 100, 20)
        bg.clicked.connect(lambda: self._color("editor_bg", 3618615))
        _put(page, QLabel(lng(46), page), 10, 35, 250, 20)
        op = _put(page, QSlider(Qt.Orientation.Horizontal, page), 10, 55, 315, 20)
        op.setRange(100, 255)
        op.setValue(int(self.settings.value("opacity", 245)))
        op_l = _put(page, QLabel(str(op.value()), page), 340, 55, 30, 20)

        def opacity(v, lab=op_l):
            self.settings.setValue("opacity", v)
            lab.setText(str(v))
            self.mik.apply_look()

        op.valueChanged.connect(opacity)
        font_b = _put(page, QPushButton(lng(47), page), 14, 85, 100, 20)
        font_b.clicked.connect(self._pick_font)
        fg = _put(page, QPushButton(lng(48), page), 219, 85, 100, 20)
        fg.clicked.connect(lambda: self._color("editor_fg", 11842740))
        _put(page, QLabel(lng(49), page), 10, 115, 250, 20)
        size = _put(page, QSlider(Qt.Orientation.Horizontal, page), 10, 135, 315, 20)
        size.setRange(8, 72)
        size.setValue(int(self.settings.value("editor_size", 14)))
        size_l = _put(page, QLabel(str(size.value()), page), 340, 135, 30, 20)

        def font_size(v, lab=size_l):
            self.settings.setValue("editor_size", v)
            lab.setText(str(v))
            self.mik.apply_look()

        size.valueChanged.connect(font_size)
        _put(page, QGroupBox(lng(114) + " ", page), 10, 165, 364, 45)
        modes = (
            (20, 182, 110, lng(115), 1),
            (173, 182, 100, lng(116), 2),
            (303, 182, 60, lng(117), 0),
        )
        current = int(self.settings.value("toolbar", 1))
        for x, y, w, text, mode in modes:
            radio = _put(page, QRadioButton(text, page), x, y, w, 20)
            radio.setChecked(current == mode)
            radio.toggled.connect(lambda on, m=mode: on and self.mik._apply_toolbar_mode(m))
        auto = self._box(page, 10, 222, 150, 20, lng(168) + ":", "auto_exit", True)
        combo = _put(page, QComboBox(page), 160, 221, 50, 23)
        combo.addItems([str(i) for i in range(11)])
        combo.setCurrentIndex(int(self.settings.value("auto_exit_time", 10)))
        combo.currentTextChanged.connect(lambda t: self.settings.setValue("auto_exit_time", int(t)))
        combo.setEnabled(auto.isChecked())
        auto.toggled.connect(combo.setEnabled)

    def _color(self, key: str, default: int) -> None:
        current = QColor(f"#{int(self.settings.value(key, default)):06X}")
        color = QColorDialog.getColor(current, self, lng(45))
        if color.isValid():
            self.settings.setValue(key, int(color.name()[1:], 16))
            self.mik.apply_look()

    def _pick_font(self) -> None:
        from PyQt6.QtWidgets import QFontDialog

        current = QFont(str(self.settings.value("editor_font", "Consolas")), int(self.settings.value("editor_size", 14)))
        font, ok = QFontDialog.getFont(current, self, lng(47))
        if ok:
            self.settings.setValue("editor_font", font.family())
            self.settings.setValue("editor_size", font.pointSize())
            self.mik.apply_look()

    def _sound(self) -> None:
        page = self.pages["sound"]
        self._box(page, 10, 10, 260, 20, lng(62), "sound", True)
        _put(page, QLabel(lng(61), page), 10, 35, 250, 20)
        vol = _put(page, QSlider(Qt.Orientation.Horizontal, page), 10, 55, 328, 20)
        vol.setRange(0, 100)
        vol.setValue(int(self.settings.value("volume", 20)))
        lab = _put(page, QLabel(str(vol.value()), page), 353, 55, 30, 20)

        def changed(v, label=lab):
            self.settings.setValue("volume", v)
            label.setText(str(v))

        vol.valueChanged.connect(changed)
        play = _put(page, QCheckBox(lng(63), page), 10, 85, 250, 20)

        def preview(on):
            if on:
                subprocess.Popen(
                    ["afplay", "-v", str(int(self.settings.value("volume", 20)) / 100), "/System/Library/Sounds/Glass.aiff"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            play.setChecked(False)

        play.toggled.connect(preview)

    def _lang(self) -> None:
        page = self.pages["lang"]
        _put(page, QGroupBox(lng(86) + " ", page), 10, 10, 364, 220)
        combo = _put(page, QComboBox(page), 20, 30, 343, 23)
        combo.addItems(
            [
                "Auto",
                "English - United States ",
                "Russian",
                "Chinese Traditional",
                "Chinese Simplified",
                "Belarusian",
                "Ukrainian ",
                "Portuguese - Brazil",
                "Vietnamese",
                "Turkish",
                "German - Germany",
            ]
        )
        combo.setCurrentIndex(int(self.settings.value("locale_index", 2)))
        combo.currentIndexChanged.connect(lambda i: QTimer.singleShot(0, lambda: self.mik.set_locale(i)))
        lcid = _put(page, QLabel("LCID CODE: 1049", page), 233, 250, 135, 25)
        lcid.setAlignment(Qt.AlignmentFlag.AlignRight)
        lcid.setStyleSheet("color: #808080;")


class AboutDialog(QDialog):
    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.setWindowTitle(lng(18))
        self.setWindowIcon(ico("information.ico"))
        self.setFixedSize(370, 159)
        self.setFont(_ui_font())
        self.setStyleSheet("QDialog { background: #f0f0f0; color: #000; }")
        frame = _put(self, QGroupBox("", self), 70, 4, 290, 145)
        frame
        icon = _put(self, QLabel(self), 10, 23, 48, 48)
        icon.setPixmap(ico("about.ico").pixmap(48, 48))
        build = _put(self, QLabel("Build: 2988", self), 5, 85, 57, 48)
        build.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        build.setStyleSheet("color: #808080;")
        name = _put(self, QLabel(title, self), 75, 20, 250, 25)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Cooper Black", 13)
        font.setItalic(True)
        name.setFont(font)
        desc = _put(self, QLabel(lng(73), self), 80, 48, 240, 35)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        for y, line in (
            (85, "macOS port © Vsevolod Vasin"),
            (105, "UI after CryptoNickSoft / ColdWindScholar"),
            (125, "https://github.com/VsevolodVasin/multi-image-kitchen-macos"),
        ):
            lab = _put(self, QLabel(line, self), 80, y, 270, 24)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)


class MikWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Multi Image Kitchen (macOS)")
        self.setWindowIcon(ico("icon.ico"))
        self.settings = QSettings("VsevolodVasin", "MIK-AML")
        idx = int(self.settings.value("locale_index", 2))
        idx = max(0, min(idx, len(LOCALES) - 1))
        lng._id = LOCALES[idx]
        lng._lid = None
        self.setMinimumSize(473, 308)
        self.resize(473, 308)
        self.job: Job | None = None
        self._last_open: Path | None = None
        self.setAcceptDrops(True)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setAcceptDrops(False)
        self.log.setPlainText(hint())
        self._undo = ""
        self._packed: Path | None = None
        self._skip_close_ask = False
        self.setStyleSheet(
            "QMainWindow { background: #f0f0f0; }"
            "QToolBar { background: #f0f0f0; border: 0; border-bottom: 1px solid #c0c0c0; spacing: 2px; }"
            "QStatusBar { background: #f0f0f0; }"
            "QProgressBar { border: 0; background: #d4d4d4; }"
            "QProgressBar::chunk { background: #06b025; }"
        )

        self.progress = QProgressBar()
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.log, 1)
        lay.addWidget(self.progress)
        self.setCentralWidget(central)

        self._build_menu()
        self._build_toolbar()
        self._build_status()
        self.apply_look()
        self._apply_toolbar_mode(int(self.settings.value("toolbar", 1)))
        if self.settings.value("open_settings", False, type=bool):
            self.open_settings()

    def apply_look(self) -> None:
        bg = int(self.settings.value("editor_bg", 3618615))
        fg = int(self.settings.value("editor_fg", 11842740))
        size = int(self.settings.value("editor_size", 14))
        family = str(self.settings.value("editor_font", "Consolas"))
        font = QFont(family, size)
        if family == "Consolas" and not font.exactMatch():
            font = QFont("Menlo", size)
        self.log.setFont(font)
        self.log.setStyleSheet(
            f"QPlainTextEdit {{ background: #{bg:06X}; color: #{fg:06X};"
            " border: 0; padding-left: 6px; }"
        )
        self.setWindowOpacity(int(self.settings.value("opacity", 245)) / 255)

    def _act(self, text: str, icon: str, slot, shortcut: str = "") -> QAction:
        action = QAction(ico(icon), text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        return action

    def _build_menu(self) -> None:
        bar = self.menuBar()
        file_m = bar.addMenu(lng(4))
        file_m.addAction(self._act(lng(5), "cd_edit.ico", self.unpack_dialog))
        file_m.addAction(self._act(lng(6), "cd.ico", self.pack_dialog))
        self.recent_menu = file_m.addMenu(ico("Recent.ico"), lng(7))
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        file_m.addSeparator()
        file_m.addAction(self._act(lng(8), "setting.ico", self.open_settings))
        file_m.addAction(self._act(lng(187), "cmd.ico", self.open_console))
        file_m.addSeparator()
        file_m.addAction(self._act(lng(9), "exit.ico", self.close))

        edit = bar.addMenu(lng(10))
        edit.addAction(self._act(lng(11), "page.ico", self.clear_log, "Del"))
        edit.addSeparator()
        self.act_copy = self._act(lng(95), "page_copy.ico", self.copy_log, "Ctrl+C")
        self.act_google = self._act(lng(172) + " google", "google.ico", self.search_google, "Ctrl+G")
        self.act_pda = self._act(lng(172) + " 4pda", "pda.ico", self.search_pda, "Ctrl+P")
        self.act_tr = self._act("Translate Google", "translate.ico", self.translate, "Ctrl+T")
        edit.addAction(self.act_copy)
        edit.addAction(self._act(lng(169), "page_paste.ico", self.paste_log, "Ctrl+V"))
        edit.addAction(self._act(lng(96), "page_copy.ico", self.log.selectAll, "Ctrl+A"))
        edit.addAction(self._act(lng(134), "page_paintbrush.ico", self.highlight, "Ctrl+H"))
        edit.addSeparator()
        edit.addAction(self.act_google)
        edit.addAction(self.act_pda)
        edit.addSeparator()
        edit.addAction(self.act_tr)
        self.log.copyAvailable.connect(self._edit_state)
        self._edit_state(False)
        edit.addSeparator()
        edit.addAction(self._act(lng(97), "page_save.ico", self.save_log, "Ctrl+S"))

        view = bar.addMenu(lng(118))
        self.act_top = view.addAction(lng(44))
        self.act_top.setCheckable(True)
        self.act_top.toggled.connect(self._toggle_top)
        view.addSeparator()
        self.act_toolbar = view.addAction(lng(114))
        self.act_toolbar.setCheckable(True)
        self.act_toolbar.toggled.connect(self._toggle_toolbar)
        self.act_vertical = view.addAction(lng(119))
        self.act_vertical.setCheckable(True)
        self.act_vertical.toggled.connect(self._toggle_vertical)
        view.addSeparator()
        self.act_open_settings = view.addAction(lng(170))
        self.act_open_settings.setCheckable(True)
        self.act_open_settings.setChecked(self.settings.value("open_settings", False, type=bool))
        self.act_open_settings.toggled.connect(self._toggle_open_settings)
        view.addSeparator()
        view.addAction(self._act(lng(120), "shortcut.ico", self.create_shortcut))

        help_m = bar.addMenu(lng(12))
        help_m.addAction(self._act(lng(13), "help.ico", self.open_help))
        help_m.addAction(self._act(lng(99), "telegram.ico", lambda: self._open(NEWS)))
        help_m.addAction(self._act(lng(15), "telegram.ico", lambda: self._open(DISCUSSION)))
        help_m.addAction(self._act(lng(16), "youtube.ico", lambda: self._open(CHANNEL)))
        help_m.addAction(self._act(lng(18), "information.ico", self.about))

    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setFixedHeight(25)
        self.toolbar.setStyleSheet("QToolBar { spacing: 2px; border: 0; }")
        self._fill_toolbar()
        QShortcut("Ctrl+Z", self, self.undo_log)

    def _fill_toolbar(self) -> None:
        buttons = (
            ("page.ico", lng(11), self.clear_log),
            ("page_save.ico", lng(97), self.save_log),
            ("cd_edit.ico", lng(5), self.unpack_dialog),
            ("cd.ico", lng(6), self.pack_dialog),
            ("Recent.ico", lng(7), self._popup_recent),
            None,
            ("setting.ico", lng(8), self.open_settings),
            ("cmd.ico", lng(187), self.open_console),
            None,
            ("telegram.ico", lng(99), lambda: self._open(NEWS)),
            ("youtube.ico", lng(16), lambda: self._open(CHANNEL)),
            ("information.ico", lng(18), self.about),
        )
        for item in buttons:
            if item is None:
                self.toolbar.addSeparator()
                continue
            icon, tip, slot = item
            action = self.toolbar.addAction(ico(icon), "")
            action.setToolTip(tip)
            action.triggered.connect(slot)

    def _build_status(self) -> None:
        bar = self.statusBar()
        bar.setSizeGripEnabled(True)
        bar.setStyleSheet("QStatusBar::item { border: 0; }")
        self.status_icon = QLabel()
        self.status_icon.setFixedWidth(23)
        self.status_text = QLabel(lng(71))
        bar.addWidget(self.status_icon)
        bar.addWidget(self.status_text, 1)
        self._set_status(lng(71), busy=False)

    def _set_status(self, text: str, busy: bool) -> None:
        self.status_text.setText(text)
        pix = ico("wait.ico" if busy else "ready.ico").pixmap(16, 16)
        self.status_icon.setPixmap(pix)

    def _apply_toolbar_mode(self, mode: int) -> None:
        self.settings.setValue("toolbar", mode)
        if self.toolBarArea(self.toolbar) != Qt.ToolBarArea.NoToolBarArea:
            self.removeToolBar(self.toolbar)
        self.act_toolbar.blockSignals(True)
        self.act_vertical.blockSignals(True)
        self.act_toolbar.setChecked(mode != 0)
        self.act_vertical.setChecked(mode == 2)
        self.act_toolbar.blockSignals(False)
        self.act_vertical.blockSignals(False)
        if mode == 0:
            self.toolbar.hide()
            return
        area = Qt.ToolBarArea.LeftToolBarArea if mode == 2 else Qt.ToolBarArea.TopToolBarArea
        self.addToolBar(area, self.toolbar)
        if mode == 2:
            self.toolbar.setFixedHeight(16777215)
            self.toolbar.setFixedWidth(28)
            self.toolbar.setOrientation(Qt.Orientation.Vertical)
        else:
            self.toolbar.setFixedWidth(16777215)
            self.toolbar.setFixedHeight(25)
            self.toolbar.setOrientation(Qt.Orientation.Horizontal)
        self.toolbar.show()

    def _toggle_top(self, on: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.show()

    def _toggle_toolbar(self, on: bool) -> None:
        if on:
            self._apply_toolbar_mode(2 if self.act_vertical.isChecked() else 1)
        else:
            self._apply_toolbar_mode(0)

    def _toggle_vertical(self, on: bool) -> None:
        self._apply_toolbar_mode(2 if on else 1)

    def _fill_recent(self) -> None:
        self.recent_menu.clear()
        items = self.settings.value("recent", [], type=list) or []
        for path in items:
            self.recent_menu.addAction(str(path), lambda _=False, p=path: self.handle_path(Path(p)))
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(lng(109), self._clear_recent)

    def _popup_recent(self) -> None:
        self._fill_recent()
        self.recent_menu.popup(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _remember(self, path: Path) -> None:
        items = [str(path)] + [p for p in (self.settings.value("recent", [], type=list) or []) if p != str(path)]
        self.settings.setValue("recent", items[:12])

    def _clear_recent(self) -> None:
        self.settings.setValue("recent", [])

    def selected_parts(self, key: str) -> set[str]:
        return {n for n in PARTS if self.settings.value(f"{key}/{n}", True, type=bool)}

    def append(self, text: str) -> None:
        self.log.appendPlainText(text)
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _edit_state(self, yes: bool) -> None:
        for act in (self.act_copy, self.act_google, self.act_pda, self.act_tr):
            act.setEnabled(yes)

    def copy_log(self) -> None:
        self.log.copy()
        cursor = self.log.textCursor()
        cursor.clearSelection()
        self.log.setTextCursor(cursor)

    def undo_log(self) -> None:
        if self._undo:
            self.log.setPlainText(self._undo)

    def _toggle_open_settings(self, on: bool) -> None:
        self.settings.setValue("open_settings", on)
        if on:
            self.open_settings()

    def set_locale(self, index: int) -> None:
        index = max(0, min(index, len(LOCALES) - 1))
        lid = LOCALES[index]
        if getattr(lng, "_id", None) == lid and int(self.settings.value("locale_index", 2)) == index:
            return
        self.settings.setValue("locale_index", index)
        lng._id = lid
        lng._lid = None
        self.menuBar().clear()
        self._build_menu()
        self.toolbar.clear()
        self._fill_toolbar()
        self._apply_toolbar_mode(int(self.settings.value("toolbar", 1)))
        self.log.setPlainText(hint())
        self._set_status(lng(71), busy=False)
        win = getattr(self, "_settings_win", None)
        if win is not None and win.isVisible():
            win.close()
            self._settings_win = None
            QTimer.singleShot(0, self.open_settings)

    def clear_log(self) -> None:
        self._undo = self.log.toPlainText()
        self.log.setPlainText("")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._set_status(lng(71), busy=False)

    def paste_log(self) -> None:
        from PyQt6.QtWidgets import QApplication

        text = QApplication.clipboard().text()
        if text:
            self.append("--->> Get Clipboard Text <<---")
            self.append(text)
            self.append("--->> End Clipboard Text <<---")

    def highlight(self) -> None:
        cursor = self.log.textCursor()
        if not cursor.hasSelection():
            return
        fmt = QTextCharFormat()
        fmt.setBackground(Qt.GlobalColor.yellow)
        cursor.mergeCharFormat(fmt)

    def _selection(self) -> str:
        return self.log.textCursor().selectedText().replace("\u2029", "\n")

    def search_google(self) -> None:
        self._open("https://www.google.com/search?q=" + urllib.parse.quote(self._selection()))

    def search_pda(self) -> None:
        text = self._selection()
        if not text:
            self._open("https://4pda.to/forum/index.php?act=search")
        else:
            q = urllib.parse.quote(text)
            self._open(
                "https://4pda.to/forum/index.php?act=search&query="
                + q
                + "&username=&forums%5B%5D=all&subforums=1&source=all&sort=rel&result=posts"
            )

    def translate(self) -> None:
        self._open(
            "https://translate.google.com/?sl=auto&tl=auto&text="
            + urllib.parse.quote(self._selection())
            + "&op=translate"
        )

    def save_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, lng(98), "LogFile.txt", "(*.txt)")
        if not path:
            return
        dest = Path(path)
        if dest.exists() and dest.stat().st_size > 0:
            answer = QMessageBox.question(
                self, "", f"Файл: {dest} существует, перезаписать?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return
        header = (
            "MIK version: 4.2 build: 2988\n"
            f"Path: {Path(__file__).resolve()}\n\n"
            f"CPU: {platform.processor() or platform.machine()}\n"
            f"OS Version: {platform.platform()}\n"
            f"User Name: {getpass.getuser()}\n\n"
        )
        dest.write_text(header + self.log.toPlainText(), encoding="utf-8")

    def open_console(self) -> None:
        subprocess.Popen(["open", "-a", "Terminal"])

    def open_help(self) -> None:
        chm = Path.home() / "Downloads" / "MIK_v4.0" / "bin" / "Help.chm"
        if chm.is_file():
            subprocess.Popen(["open", str(chm)])
        else:
            self.append(lng(13))

    def create_shortcut(self) -> None:
        desk = Path.home() / "Desktop" / "MIK.command"
        root = Path(__file__).resolve().parents[1]
        desk.write_text(
            "#!/bin/bash\n"
            f'cd "{root}"\n'
            'exec .venv/bin/python -m mik mik\n',
            encoding="utf-8",
        )
        desk.chmod(0o755)

    def _open(self, url: str) -> None:
        subprocess.Popen(["open", url])

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            self.handle_path(Path(url.toLocalFile()))

    def unpack_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, lng(1), "",
            "img (*.img *.partition *.PARTITION *.fex *.zip *.dat *.br *.apk);;All (*.*)",
        )
        for path in paths:
            self.handle_path(Path(path))

    def pack_dialog(self) -> None:
        path = QFileDialog.getExistingDirectory(self, lng(3))
        if path:
            self.handle_path(Path(path))

    def handle_path(self, path: Path) -> None:
        if self.job and self.job.isRunning():
            self.append(lng(75))
            return
        if path.is_dir():
            self._remember(path)
            self._start_pack(path)
        elif path.is_file():
            self._remember(path)
            self._start_unpack(path)
        else:
            self.append(f"{lng(110)} {path}")

    def _ext_opts(self) -> tuple[int, bool]:
        keep = self.settings.value("expand_size", True, type=bool)
        extra = 0
        if not keep:
            try:
                extra = int(self.settings.value("free_space", 100) or 0)
            except ValueError:
                extra = 0
        return extra, keep

    def _start_unpack(self, path: Path) -> None:
        def work(log):
            suffix = path.suffix.lower()
            if suffix == ".zip" or suffix == ".apk":
                out = path.with_suffix("") if suffix == ".zip" else path.parent / (path.stem + "_apk")
                if self.settings.value("subfolder", True, type=bool):
                    out.mkdir(parents=True, exist_ok=True)
                    target = out
                else:
                    target = path.parent
                log(f"{lng(131)} {path.name}")
                with zipfile.ZipFile(path) as zf:
                    zf.extractall(target)
                self._last_open = target
                if self.settings.value("delete_archive", False, type=bool):
                    path.unlink()
                nested = next(target.glob("*.img"), None)
                if self.settings.value("seven_unpack", False, type=bool) and nested and is_aml_image(nested):
                    unpack_firmware(nested, nested.with_suffix(""), log, self.selected_parts("unpack"))
                    self._last_open = nested.with_suffix("")
                return
            if suffix == ".br":
                brotli = shutil.which("brotli")
                if not brotli:
                    raise RuntimeError(f"{path.name} {lng(64)}")
                out = path.with_suffix("")
                log(lng(108) + f": {path.name}")
                subprocess.run([brotli, "-d", "-f", str(path), "-o", str(out)], check=True)
                self._last_open = out.parent
                return
            if suffix == ".fex":
                raise RuntimeError("imgRePackerRK: Windows-only, " + path.name)
            if is_aml_image(path):
                out = path.with_suffix("")
                if out == path:
                    out = path.parent / (path.name + ".unpack")
                parts = self.selected_parts("unpack")
                if self.settings.value("unpack/super", True, type=bool):
                    log("SUPER: на Mac не распаковывается, раздел останется файлом")
                unpack_firmware(path, out, log, parts)
                self._last_open = out
            elif is_sparse(path) or is_ext4(path) or suffix in {".partition", ".img", ".dat"}:
                out = path.parent / path.stem
                unpack_partition(path, out, log)
                self._last_open = out
            else:
                raise RuntimeError(f"{path.name} {lng(69)}")

        self._run(work)

    def _start_pack(self, folder: Path) -> None:
        extra, keep = self._ext_opts()

        def work(log):
            out = folder.parent / f"{folder.name}.img"
            if self.settings.value("index_add", False, type=bool):
                n = 1
                while out.exists():
                    out = folder.parent / f"{folder.name}_{n}.img"
                    n += 1
            if (folder / "image.cfg").is_file():
                pack_firmware(folder, out, log, self.selected_parts("pack"), extra, keep)
            else:
                pack_partition(folder, out, log, extra, keep)
            if self.settings.value("get_hash", False, type=bool) and out.is_file():
                digest = hashlib.md5(out.read_bytes()).hexdigest()
                out.with_suffix(out.suffix + ".md5").write_text(f"{digest}  {out.name}\n", encoding="utf-8")
                log(f"{lng(140)}: {out.name}.md5")
            if self.settings.value("seven_pack", False, type=bool) and out.is_file():
                seven = shutil.which("7z") or shutil.which("7zz")
                if not seven:
                    log("7z не найден")
                else:
                    level = str(self.settings.value("seven_level", "0"))
                    archive = out.with_suffix(".7z")
                    log(f"{lng(141)}: {archive.name}")
                    subprocess.run([seven, "a", f"-mx={level}", str(archive), str(out)], check=True)
                    if self.settings.value("delete_image", False, type=bool):
                        out.unlink()
                        log(lng(142))
            self._packed = out if out.is_file() else None
            self._last_open = out.parent

        self._run(work)

    def _run(self, fn) -> None:
        self._last_open = None
        self.append(lng(21))
        self._set_status(lng(21), busy=True)
        self.progress.setRange(0, 0)
        self.job = Job(fn)
        self.job.line.connect(self.append)
        self.job.done.connect(self._finished)
        self.job.start()

    def _finished(self, ok: bool, _err: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if ok else 0)
        if ok:
            self.append(lng(76))
            if self.settings.value("open_folder", True, type=bool) and self._last_open:
                subprocess.Popen(["open", str(self._last_open)])
        else:
            self.append(lng(77))
        self.append(lng(27))
        self._set_status(lng(27), busy=False)
        if self.settings.value("sound", True, type=bool):
            vol = int(self.settings.value("volume", 20)) / 100
            subprocess.Popen(
                ["afplay", "-v", str(vol), "/System/Library/Sounds/Glass.aiff"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if ok and self.settings.value("open_usb", False, type=bool) and self._packed:
            sister = Path("/Applications/Burning Tool.app")
            if sister.is_dir():
                subprocess.Popen(["open", "-a", "Burning Tool", str(self._packed)])
            else:
                self.append("USB Burning Tool: https://github.com/VsevolodVasin/usb-burning-tool-macos")
        if ok and self.settings.value("auto_exit", True, type=bool):
            sec = int(self.settings.value("auto_exit_time", 10))
            self.append(f"{lng(168)} {sec}")
            QTimer.singleShot(sec * 1000, self._auto_close)

    def _auto_close(self) -> None:
        self._skip_close_ask = True
        self.close()

    def closeEvent(self, event) -> None:
        if self.job and self.job.isRunning():
            event.ignore()
            return
        if self._skip_close_ask:
            event.accept()
            return
        answer = QMessageBox.question(
            self, lng(74), lng(79),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

    def open_settings(self) -> None:
        win = getattr(self, "_settings_win", None)
        if win is not None and win.isVisible():
            win.raise_()
            win.activateWindow()
            return
        self._settings_win = SettingsDialog(self, self.settings)
        self._settings_win.show()

    def about(self) -> None:
        AboutDialog(self, self.windowTitle()).exec()
