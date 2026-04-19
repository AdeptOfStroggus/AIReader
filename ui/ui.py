from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QMainWindow, QSplitter, QSpinBox, QLabel
from ai_client import AIClient
import sys
import os

os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false;qt.text.font=false;qt.gui.fontdatabase=false"

from ui.aiAssistant_ui import AIAssistantPanel
from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot, Qt, QThread, Signal, qInstallMessageHandler, QtMsgType
from ui.readerPanel import ReaderPanel
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence
from doc_converter import Converter
from PySide6.QtWidgets import QFileDialog

def qt_message_handler(mode, context, message):
    if "setPointSize" in message and "Point size <= 0" in message:
        return
    if "OpenType support missing" in message:
        return
    if mode == QtMsgType.QtDebugMsg:
        sys.stdout.write(f"Debug: {message}\n")
    elif mode == QtMsgType.QtWarningMsg:
        sys.stderr.write(f"Warning: {message}\n")
    elif mode == QtMsgType.QtCriticalMsg:
        sys.stderr.write(f"Critical: {message}\n")
    elif mode == QtMsgType.QtFatalMsg:
        sys.stderr.write(f"Fatal: {message}\n")
        sys.exit(1)
    elif mode == QtMsgType.QtInfoMsg:
        sys.stdout.write(f"Info: {message}\n")

def get_preferred_font_family():
    for family in QFontDatabase.families():
        normalized = family.replace(" ", "").lower()
        if normalized.startswith("worksans") or normalized.startswith("dmsans"):
            return family
    return ""

class MainApp(QMainWindow):
    def __init__(self, client=None):
        super().__init__()

        self.client = client
        self.setWindowTitle("AIReader")
        self.docConverter = Converter()
        self.isDarkMode = True
        self.globalFontSize = 14
        self._initialized = False

        self.readerPanel = ReaderPanel(self.docConverter, self.client)
        self.AIPanel = AIAssistantPanel(self.client, self.readerPanel.GetConvertedText)

        self.AIPanel.sourceClicked.connect(self.readerPanel.JumpToSource)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.readerPanel)
        self.splitter.addWidget(self.AIPanel)

        self.readerPanel.setMinimumWidth(400)
        self.AIPanel.setMinimumWidth(280)

        self.splitter.setStretchFactor(0, 7)
        self.splitter.setStretchFactor(1, 3)

        self.box = QHBoxLayout()
        self.box.addWidget(self.splitter)
        self.box.setContentsMargins(0, 0, 0, 0)

        self.mainWidget = QWidget()
        self.mainWidget.setObjectName("mainWidget")
        self.mainWidget.setLayout(self.box)
        self.setCentralWidget(self.mainWidget)

        self.ApplyTheme()
        self._initialized = True

        self.fileMenu = self.menuBar().addMenu("Файл")
        importFile = QAction("Загрузить файл", self)
        importFile.triggered.connect(self.LoadFile)
        self.fileMenu.addAction(importFile)

        self.ViewMenu = self.menuBar().addMenu("Вид")

        switchModesAction = QAction("Показать конвертированный текст", self)
        switchModesAction.triggered.connect(self.SwitchModes)
        self.ViewMenu.addAction(switchModesAction)

        self.themeAction = QAction("Светлая тема", self)
        self.themeAction.triggered.connect(self.ToggleTheme)
        self.ViewMenu.addAction(self.themeAction)

        self.ocrMenu = self.menuBar().addMenu("Настройки")

        ocrLanguageAction = QAction("Язык распознавания (OCR)", self)
        self.ocrMenu.addAction(ocrLanguageAction)

        ocrEngineAction = QAction("Движок OCR", self)
        self.ocrMenu.addAction(ocrEngineAction)

        self.ocrMenu.addSeparator()

        ocrHighQualityAction = QAction("Высокое качество (медленно)", self)
        ocrHighQualityAction.setCheckable(True)
        ocrHighQualityAction.setChecked(True)
        self.ocrMenu.addAction(ocrHighQualityAction)

        self.fontSizeSpinBox = QSpinBox()
        self.fontSizeSpinBox.setRange(8, 72)
        self.fontSizeSpinBox.setValue(self.globalFontSize)

        self.zoomInAction = QAction("Увеличить шрифт", self)
        self.zoomInAction.setShortcuts([QKeySequence.StandardKey.ZoomIn, QKeySequence("Ctrl+=")])
        self.zoomInAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.zoomInAction.triggered.connect(self.IncreaseFontSize)

        self.zoomOutAction = QAction("Уменьшить шрифт", self)
        self.zoomOutAction.setShortcuts([QKeySequence.StandardKey.ZoomOut, QKeySequence("Ctrl+-")])
        self.zoomOutAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.zoomOutAction.triggered.connect(self.DecreaseFontSize)

        self.resetFontAction = QAction("Сбросить размер шрифта", self)
        self.resetFontAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.resetFontAction.triggered.connect(lambda: self.fontSizeSpinBox.setValue(14))

        status_bar = self.statusBar()
        status_bar.setSizeGripEnabled(False)

    def IncreaseFontSize(self):
        self.fontSizeSpinBox.setValue(min(self.fontSizeSpinBox.maximum(), self.fontSizeSpinBox.value() + 1))

    def DecreaseFontSize(self):
        self.fontSizeSpinBox.setValue(max(self.fontSizeSpinBox.minimum(), self.fontSizeSpinBox.value() - 1))

    def OnFontSizeChanged(self, value):
        self.globalFontSize = value
        self.ApplyTheme()

    def ApplyTheme(self):
        fs = self.globalFontSize

        splitter_sizes = self.splitter.sizes() if hasattr(self, 'splitter') and self._initialized else None

        if self.isDarkMode:
            self.setStyleSheet(f"""
                QMainWindow, QWidget#mainWidget {{
                    background-color: #05050D;
                    color: #D8EEFF;
                }}
                QStatusBar {{
                    background-color: #09091A;
                    color: #3A5A78;
                    border-top: 1px solid rgba(0,200,255,0.12);
                    font-size: {fs - 2}px;
                }}
                QMenuBar {{
                    background-color: #09091A;
                    color: #6888A8;
                    border-bottom: 1px solid rgba(0,200,255,0.15);
                    font-size: {fs - 1}px;
                    padding: 2px 4px;
                    spacing: 2px;
                }}
                QMenuBar::item {{
                    background-color: transparent;
                    padding: 5px 12px;
                    border-radius: 2px;
                }}
                QMenuBar::item:selected {{
                    background-color: rgba(0,200,255,0.14);
                    color: #80E8FF;
                }}
                QMenu {{
                    background-color: #0E0E24;
                    color: #A0C8E0;
                    border: 1px solid rgba(0,200,255,0.22);
                    border-radius: 2px;
                    padding: 4px;
                    font-size: {fs - 1}px;
                }}
                QMenu::item {{
                    padding: 7px 20px;
                    border-radius: 1px;
                    margin: 1px 2px;
                }}
                QMenu::item:selected {{
                    background-color: rgba(0,200,255,0.18);
                    color: #C0F0FF;
                }}
                QMenu::separator {{
                    height: 1px;
                    background-color: rgba(0,200,255,0.10);
                    margin: 4px 8px;
                }}
                QSplitter::handle {{
                    background-color: rgba(0,200,255,0.08);
                    width: 1px;
                }}
                QSplitter::handle:hover {{
                    background-color: rgba(0,200,255,0.55);
                }}
                QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QTextEdit {{
                    font-size: {fs}px;
                }}
                QLabel {{
                    color: #D8EEFF;
                }}
                QSpinBox {{
                    background-color: rgba(0,200,255,0.06);
                    color: #D8EEFF;
                    border: 1px solid rgba(0,200,255,0.18);
                    border-radius: 2px;
                    padding: 2px 6px;
                }}
                QScrollBar:vertical {{
                    background-color: transparent;
                    width: 6px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background-color: rgba(0,200,255,0.18);
                    border-radius: 3px;
                    min-height: 32px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background-color: rgba(0,200,255,0.38);
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: transparent;
                }}
                QScrollBar:horizontal {{
                    background-color: transparent;
                    height: 6px;
                    margin: 0px;
                }}
                QScrollBar::handle:horizontal {{
                    background-color: rgba(0,200,255,0.18);
                    border-radius: 3px;
                    min-width: 32px;
                }}
                QScrollBar::handle:horizontal:hover {{
                    background-color: rgba(0,200,255,0.38);
                }}
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                    width: 0px;
                }}
            """)
            if hasattr(self, 'themeAction'):
                self.themeAction.setText("Светлая тема")
        else:
            self.setStyleSheet(f"""
                QMainWindow, QWidget#mainWidget {{
                    background-color: #EEEEE6;
                    color: #0A1828;
                }}
                QStatusBar {{
                    background-color: #E4E4DC;
                    color: #607080;
                    border-top: 1px solid #B8C8D8;
                    font-size: {fs - 2}px;
                }}
                QMenuBar {{
                    background-color: #E4E4DC;
                    color: #304050;
                    border-bottom: 1px solid #B0C0D0;
                    font-size: {fs - 1}px;
                    padding: 2px 4px;
                    spacing: 2px;
                }}
                QMenuBar::item {{
                    background-color: transparent;
                    padding: 5px 12px;
                    border-radius: 2px;
                }}
                QMenuBar::item:selected {{
                    background-color: rgba(0,80,180,0.12);
                    color: #0040AA;
                }}
                QMenu {{
                    background-color: #F0F0E8;
                    color: #1A2A3A;
                    border: 1px solid #90A8C0;
                    border-radius: 2px;
                    padding: 4px;
                    font-size: {fs - 1}px;
                }}
                QMenu::item {{
                    padding: 7px 20px;
                    border-radius: 1px;
                    margin: 1px 2px;
                }}
                QMenu::item:selected {{
                    background-color: rgba(0,80,180,0.12);
                    color: #0040AA;
                }}
                QMenu::separator {{
                    height: 1px;
                    background-color: #C0D0E0;
                    margin: 4px 8px;
                }}
                QSplitter::handle {{
                    background-color: #C0CCE0;
                    width: 1px;
                }}
                QSplitter::handle:hover {{
                    background-color: #0055CC;
                }}
                QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QTextEdit {{
                    font-size: {fs}px;
                }}
                QLabel {{
                    color: #0A1828;
                }}
                QSpinBox {{
                    background-color: #F8F8F0;
                    color: #0A1828;
                    border: 1px solid #90A8C0;
                    border-radius: 2px;
                    padding: 2px 6px;
                }}
                QScrollBar:vertical {{
                    background-color: transparent;
                    width: 6px;
                    margin: 0px;
                }}
                QScrollBar::handle:vertical {{
                    background-color: rgba(0,80,180,0.18);
                    border-radius: 3px;
                    min-height: 32px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background-color: rgba(0,80,180,0.35);
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: transparent;
                }}
                QScrollBar:horizontal {{
                    background-color: transparent;
                    height: 6px;
                    margin: 0px;
                }}
                QScrollBar::handle:horizontal {{
                    background-color: rgba(0,80,180,0.18);
                    border-radius: 3px;
                    min-width: 32px;
                }}
                QScrollBar::handle:horizontal:hover {{
                    background-color: rgba(0,80,180,0.35);
                }}
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                    width: 0px;
                }}
            """)
            if hasattr(self, 'themeAction'):
                self.themeAction.setText("Тёмная тема")

        self.readerPanel.SetDarkMode(self.isDarkMode, fs)
        self.AIPanel.SetDarkMode(self.isDarkMode, fs)

        if hasattr(self, 'splitter') and splitter_sizes and sum(splitter_sizes) > 0:
            self.splitter.setSizes(splitter_sizes)

    def SetClient(self, client):
        self.client = client
        self.readerPanel.aiClient = client
        self.AIPanel.client = client
        self.AIPanel.OnRefreshModelButtonClicked()

    def ToggleTheme(self):
        self.isDarkMode = not self.isDarkMode
        self.ApplyTheme()

    def closeEvent(self, event):
        if hasattr(self, 'readerPanel'):
            self.readerPanel.StopAllWorkers()

        if hasattr(self, 'AIPanel'):
            self.AIPanel.StopAllWorkers()

        global initializer
        if 'initializer' in globals() and initializer.isRunning():
            initializer.quit()
            initializer.wait()

        event.accept()

    def SwitchModes(self):
        self.readerPanel.SwitchModes()

    def LoadFile(self):
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Импортировать файл",
            "",
            "Поддерживаемые форматы (*.pdf);;Все файлы (*.*)"
        )
        if filePath:
            self.readerPanel.LoadDocument(filePath)


def main():
    qInstallMessageHandler(qt_message_handler)

    app = QApplication(sys.argv)

    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

    if os.path.exists(fonts_dir):
        for font_file in os.listdir(fonts_dir):
            if font_file.lower().endswith((".otf", ".ttf")):
                font_path = os.path.join(fonts_dir, font_file)
                QFontDatabase.addApplicationFont(font_path)

    font_family = get_preferred_font_family()
    system_font = QFont(font_family) if font_family else QFont()
    system_font.setPointSize(14)
    app.setFont(system_font)

    window = MainApp()
    window.show()
    client = AIClient()
    window.SetClient(client)

    app.exec()


if __name__ == "__main__":
    main()
