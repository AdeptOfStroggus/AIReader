from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QMainWindow, QSplitter, QSpinBox, QLabel
from ai_client import AIClient
import sys
import os
from ui.aiAssistant_ui import AIAssistantPanel
from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot, Qt, QThread, Signal
# ...
from ui.readerPanel import ReaderPanel
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence
from doc_converter import Converter
from PySide6.QtWidgets import QFileDialog


def get_dm_sans_family():
    for family in QFontDatabase.families():
        normalized = family.replace(" ", "").lower()
        if normalized.startswith("dmsans"):
            return family
    return ""
        
class MainApp(QMainWindow):
    def __init__(self, client=None):
        super().__init__()

        self.client = client
        self.setWindowTitle("ИИ читалка книг")
        self.docConverter = Converter()
        self.isDarkMode = True
        self.globalFontSize = 14

        # Если клиент не передан сразу, создадим его позже или будем ждать
        self.readerPanel = ReaderPanel(self.docConverter, self.client)
        self.AIPanel = AIAssistantPanel(self.client, self.readerPanel.GetConvertedText)

        # Применяем тему
        self.ApplyTheme()

        # Создаем сплиттер для разделения книги и чата
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.readerPanel)
        self.splitter.addWidget(self.AIPanel)
        
        # Устанавливаем минимальные размеры для панелей (разумные пределы)
        self.readerPanel.setMinimumWidth(400)
        self.AIPanel.setMinimumWidth(300)
        
        # Начальное распределение места (70% книге, 30% чату)
        self.splitter.setStretchFactor(0, 7)
        self.splitter.setStretchFactor(1, 3)

        self.box = QHBoxLayout()
        self.box.addWidget(self.splitter)
        self.box.setContentsMargins(0, 0, 0, 0)
        

        self.mainWidget = QWidget()
        self.mainWidget.setObjectName("mainWidget")
        self.mainWidget.setLayout(self.box)
        self.setCentralWidget(self.mainWidget)

        menuBar = self.menuBar()


        self.fileMenu = self.menuBar().addMenu("&Файл")
        importFile = QAction("&Загрузить файл", self)
        importFile.triggered.connect(self.LoadFile)
        self.fileMenu.addAction(importFile)


        self.ViewMenu = self.menuBar().addMenu("&Вид")

        switchModesAction = QAction("&Показать конвертированный текст", self)
        switchModesAction.triggered.connect(self.SwitchModes)
        self.ViewMenu.addAction(switchModesAction)

        self.themeAction = QAction("&Светлая тема", self)
        self.themeAction.triggered.connect(self.ToggleTheme)
        self.ViewMenu.addAction(self.themeAction)

        self.fontSizeSpinBox = QSpinBox()
        self.fontSizeSpinBox.setRange(8, 72)
        self.fontSizeSpinBox.setValue(self.globalFontSize)
        self.fontSizeSpinBox.valueChanged.connect(self.OnFontSizeChanged)

        self.zoomInAction = QAction("Увеличить шрифт", self)
        self.zoomInAction.setShortcuts([QKeySequence.StandardKey.ZoomIn, QKeySequence("Ctrl+=")])
        self.zoomInAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.zoomInAction.triggered.connect(self.IncreaseFontSize)
        self.ViewMenu.addAction(self.zoomInAction)
        self.addAction(self.zoomInAction)

        self.zoomOutAction = QAction("Уменьшить шрифт", self)
        self.zoomOutAction.setShortcuts([QKeySequence.StandardKey.ZoomOut, QKeySequence("Ctrl+-")])
        self.zoomOutAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.zoomOutAction.triggered.connect(self.DecreaseFontSize)
        self.ViewMenu.addAction(self.zoomOutAction)
        self.addAction(self.zoomOutAction)

        self.resetFontAction = QAction("Сбросить размер шрифта", self)
        self.resetFontAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.resetFontAction.triggered.connect(lambda: self.fontSizeSpinBox.setValue(14))
        self.ViewMenu.addAction(self.resetFontAction)

        status_bar = self.statusBar()
        status_bar.setSizeGripEnabled(False)
        status_bar.addPermanentWidget(QLabel("Размер шрифта:"))
        status_bar.addPermanentWidget(self.fontSizeSpinBox)

    def IncreaseFontSize(self):
        self.fontSizeSpinBox.setValue(min(self.fontSizeSpinBox.maximum(), self.globalFontSize + 1))

    def DecreaseFontSize(self):
        self.fontSizeSpinBox.setValue(max(self.fontSizeSpinBox.minimum(), self.globalFontSize - 1))

    def OnFontSizeChanged(self, value):
        self.globalFontSize = value
        self.ApplyTheme()

    def ApplyTheme(self):
        fs = self.globalFontSize

        common_text_style = f"""
            font-size: {fs}px;
        """
        
        if self.isDarkMode:
            # VS Code Dark Theme
            self.setStyleSheet(f"""
                QMainWindow, QWidget#mainWidget {{
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                }}
                QMenuBar {{
                    background-color: #323233;
                    color: #cccccc;
                    border-bottom: 1px solid #3c3c3c;
                    {common_text_style}
                }}
                QMenuBar::item {{
                    background-color: transparent;
                    padding: 5px 10px;
                }}
                QMenuBar::item:selected {{
                    background-color: #4d4d4d;
                    border-radius: 4px;
                }}
                QMenu {{
                    background-color: #252526;
                    color: #cccccc;
                    border: 1px solid #454545;
                    {common_text_style}
                }}
                QMenu::item:selected {{
                    background-color: #094771;
                }}
                QSplitter::handle {{
                    background-color: #3c3c3c;
                    width: 1px;
                }}
                QSplitter::handle:hover {{   
                    background-color: #007acc;
                }}
                /* Таргетируем только текстовые виджеты */
                QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QTextEdit {{
                    {common_text_style}
                }}
                QLabel {{
                    color: #d4d4d4;
                }}
                QSpinBox {{
                    background-color: #3c3c3c;
                    color: #d4d4d4;
                    border: 1px solid #454545;
                    border-radius: 4px;
                    padding: 2px;
                }}
            """)
            if hasattr(self, 'themeAction'):
                self.themeAction.setText("&Светлая тема")
        else:
            # Modern Light Theme
            self.setStyleSheet(f"""
                QMainWindow, QWidget#mainWidget {{
                    background-color: #ffffff;
                    color: #333333;
                }}
                QMenuBar {{
                    background-color: #f3f3f3;
                    color: #333333;
                    border-bottom: 1px solid #dddddd;
                    {common_text_style}
                }}
                QMenuBar::item {{
                    background-color: transparent;
                    padding: 5px 10px;
                }}
                QMenuBar::item:selected {{
                    background-color: #e5e5e5;
                    border-radius: 4px;
                }}
                QMenu {{
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    {common_text_style}
                }}
                QMenu::item:selected {{
                    background-color: #0078d4;
                    color: #ffffff;
                }}
                QSplitter::handle {{
                    background-color: #eeeeee;
                    width: 1px;
                }}
                QSplitter::handle:hover {{   
                    background-color: #0078d4;
                }}
                /* Таргетируем только текстовые виджеты */
                QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QTextEdit {{
                    {common_text_style}
                }}
                QLabel {{
                    color: #333333;
                }}
                QSpinBox {{
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 2px;
                }}
            """)
            if hasattr(self, 'themeAction'):
                self.themeAction.setText("&Темная тема")
        
        # Обновляем дочерние панели
        self.readerPanel.SetDarkMode(self.isDarkMode, fs)
        self.AIPanel.SetDarkMode(self.isDarkMode, fs)

    def SetClient(self, client):
        self.client = client
        self.readerPanel.aiClient = client
        self.AIPanel.client = client
        # Обновляем список моделей
        self.AIPanel.OnRefreshModelButtonClicked()

    def ToggleTheme(self):
        self.isDarkMode = not self.isDarkMode
        self.ApplyTheme()

    def SwitchModes(self):
        self.readerPanel.SwitchModes()

    def LoadFile(self):

        
        # Переводим заголовок диалога в русский
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "Импортировать файл",
            "",
            "Все файлы (*.*)"
        )
        if filePath:
            self.readerPanel.LoadDocument(filePath)

        


def main():
    """Точка входа в приложение."""
    app = QApplication(sys.argv)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fonts_dir = os.path.join(base_dir, "fonts")

    if os.path.exists(fonts_dir):
        for font_file in os.listdir(fonts_dir):
            if font_file.lower().endswith((".otf", ".ttf")):
                font_path = os.path.join(fonts_dir, font_file)
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id == -1:
                    print(f"Ошибка загрузки шрифта: {font_path}")
                else:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    print(f"Загружен шрифт: {families}")

    dm_sans_family = get_dm_sans_family()
    if not dm_sans_family:
        print("Внимание: DM Sans не найден, используется системный шрифт по умолчанию.")
        system_font = app.font()
    else:
        print(f"Используется семейство шрифта: {dm_sans_family}")
        system_font = QFont(dm_sans_family)
    system_font.setPointSize(14)
    app.setFont(system_font)

    window = MainApp()
    window.show()
    
    # Фоновая инициализация клиента, чтобы не блокировать интерфейс
    class ClientInitializer(QThread):
        finished = Signal(object)
        def run(self):
            client = AIClient()
            self.finished.emit(client)

    def on_client_ready(client):
        window.SetClient(client)

    # Сохраняем ссылку на поток, чтобы его не удалил GC
    global initializer
    initializer = ClientInitializer()
    initializer.finished.connect(on_client_ready)
    initializer.start()
    
    app.exec()


if __name__ == "__main__":
    main()
