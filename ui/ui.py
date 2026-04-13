from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QMainWindow, QSplitter
from ai_client import AIClient
import sys
from ui.aiAssistant_ui import AIAssistantPanel
from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot, Qt, QThread, Signal
# ...
from ui.readerPanel import ReaderPanel
from PySide6.QtGui import QAction
from doc_converter import Converter
from PySide6.QtWidgets import QFileDialog
        
class MainApp(QMainWindow):
    def __init__(self, client=None):
        super().__init__()

        self.client = client
        self.setWindowTitle("ИИ читалка книг")
        self.docConverter = Converter()
        self.isDarkMode = True

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

    def ApplyTheme(self):
        if self.isDarkMode:
            # VS Code Dark Theme
            self.setStyleSheet("""
                QMainWindow, QWidget#mainWidget {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                }
                QMenuBar {
                    background-color: #323233;
                    color: #cccccc;
                    border-bottom: 1px solid #3c3c3c;
                }
                QMenuBar::item {
                    background-color: transparent;
                    padding: 5px 10px;
                }
                QMenuBar::item:selected {
                    background-color: #4d4d4d;
                    border-radius: 4px;
                }
                QMenu {
                    background-color: #252526;
                    color: #cccccc;
                    border: 1px solid #454545;
                }
                QMenu::item:selected {
                    background-color: #094771;
                }
                QSplitter::handle {
                    background-color: #3c3c3c;
                    width: 1px;
                }
                QSplitter::handle:hover {   
                    background-color: #007acc;
                }
            """)
            if hasattr(self, 'themeAction'):
                self.themeAction.setText("&Светлая тема")
        else:
            # Modern Light Theme
            self.setStyleSheet("""
                QMainWindow, QWidget#mainWidget {
                    background-color: #ffffff;
                    color: #333333;
                }
                QMenuBar {
                    background-color: #f3f3f3;
                    color: #333333;
                    border-bottom: 1px solid #dddddd;
                }
                QMenuBar::item {
                    background-color: transparent;
                    padding: 5px 10px;
                }
                QMenuBar::item:selected {
                    background-color: #e5e5e5;
                    border-radius: 4px;
                }
                QMenu {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                }
                QMenu::item:selected {
                    background-color: #0078d4;
                    color: #ffffff;
                }
                QSplitter::handle {
                    background-color: #eeeeee;
                    width: 1px;
                }
                QSplitter::handle:hover {   
                    background-color: #0078d4;
                }
            """)
            if hasattr(self, 'themeAction'):
                self.themeAction.setText("&Темная тема")
        
        # Обновляем дочерние панели
        self.readerPanel.SetDarkMode(self.isDarkMode)
        self.AIPanel.SetDarkMode(self.isDarkMode)

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
    
    # Сначала создаем и показываем окно
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
