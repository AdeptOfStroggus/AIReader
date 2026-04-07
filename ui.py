from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QMainWindow
from ai_client import AIClient
import sys
from aiAssistant_ui import AIAssistantPanel
from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot
# ...
from readerPanel import ReaderPanel
from PySide6.QtGui import QAction
from doc_converter import Converter
from PySide6.QtWidgets import QFileDialog
        
class MainApp(QMainWindow):
    def __init__(self, client):
        super().__init__()

        self.client = client
        self.setWindowTitle("ИИ читалка книг")
        self.docConverter = Converter()

       # self.TOCPanel = AIAssistantPanel(client)
        self.readerPanel = ReaderPanel(self.docConverter)
        self.AIPanel = AIAssistantPanel(client, self.readerPanel.GetConvertedText)

        self.box = QHBoxLayout()
        #self.box.addWidget(self.TOCPanel)
        self.box.addWidget(self.readerPanel)
        self.box.addWidget(self.AIPanel)
        self.box.setStretch(0,5)
        self.box.setStretch(1,1)

        self.mainWidget = QWidget()
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

    def SwitchModes(self):
        self.readerPanel.SwitchModes()

    def LoadFile(self):

        
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
    # Создаем QApplication ДО импорта AIClient
    app = QApplication(sys.argv)
    
    # Создаем клиент
    client = AIClient()
    
    # Создаем приложение с клиентом
    window = MainApp(client)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
