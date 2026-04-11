from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QGridLayout, QLineEdit
from PySide6.QtCore import Qt, Signal, QSize, QPointF, QThread
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtPdf import QPdfDocument, QPdfLink
from PySide6.QtPdfWidgets import QPdfView
from doc_converter import Converter

class ReaderPanel(QWidget):
    def __init__(self, docConverter: Converter, parent=None):
        super().__init__(parent)


       

        #Окно с рендером PDF
        self.pdfWindow = QPdfView(self)
        self.pdfWindow.setPageMode(QPdfView.PageMode.SinglePage)

        #Окно с рендером конвертированного текста
        self.convertedTextView = QTextEdit(self)
        self.convertedTextView.setReadOnly(True)

        #Layout навигации
        self.navigationOverlay = QWidget()
        self.navigationOverlay.setStyleSheet("""
            QWidget {
                background-color: rgba(240, 240, 240, 180);
                border-radius: 5px;
            }
        """)
        self.navigationOverlay.setFixedWidth(250)
        self.navigationOverlay.setFixedHeight(50)

        self.prevPage = QPushButton()
        self.prevPage.clicked.connect(self.OnPrevPageButtonClicked)
        self.prevPage.setText("←")
        self.prevPage.setShortcut(Qt.Key.Key_Left)
        self.prevPage.setFixedSize(30, 30)
        self.prevPage.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 200, 200, 150);
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
                border: 1px solid gray;
            }
            QPushButton:hover {
                background-color: rgba(150, 150, 150, 200);
            }
        """)

        self.nextPage = QPushButton()
        self.nextPage.clicked.connect(self.OnNextPageButtonClicked)
        self.nextPage.setText("→")
        self.nextPage.setShortcut(Qt.Key.Key_Right)
        self.nextPage.setFixedSize(30, 30)
        self.nextPage.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 200, 200, 150);
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
                border: 1px solid gray;
            }
            QPushButton:hover {
                background-color: rgba(150, 150, 150, 200);
            }
        """)

        self.jumpPage = QLineEdit()
        self.jumpPage.returnPressed.connect(self.JumpTOPage)
        self.jumpPage.setFixedSize(40, 25)
        self.jumpPage.setAlignment(Qt.AlignCenter)
        self.jumpPage.setPlaceholderText("...")
        self.jumpPage.setStyleSheet("""
            QLineEdit {
                background-color: white; 
                border-radius: 3px; 
                border: 1px solid gray;
                color: black;
            }
        """)


        self.pagesLabel = QLabel()
        self.pagesLabel.setText("0 из 0")
        self.pagesLabel.setStyleSheet("background: transparent; font-size: 12px;")

        self.navigationLayout = QHBoxLayout(self.navigationOverlay)
        self.navigationLayout.setContentsMargins(5, 5, 5, 5)
        self.navigationLayout.setSpacing(10)

        self.navigationLayout.addWidget(self.prevPage)
        self.navigationLayout.addWidget(self.jumpPage)
        self.navigationLayout.addWidget(self.pagesLabel)
        self.navigationLayout.addWidget(self.nextPage)



        #Основной layout
        self.box = QVBoxLayout()
        
        # Контейнер для области чтения, чтобы кнопки были поверх
        self.readingContainer = QWidget()
        self.readingLayout = QGridLayout(self.readingContainer)
        self.readingLayout.setContentsMargins(0, 0, 0, 0)
        self.readingLayout.setSpacing(0)
        
        self.readingLayout.addWidget(self.pdfWindow, 0, 0)
        self.readingLayout.addWidget(self.convertedTextView, 0, 0)
        
        # Добавляем оверлей навигации в верхний левый угол
        self.readingLayout.addWidget(self.navigationOverlay, 0, 0, Qt.AlignLeft | Qt.AlignTop)
        
        self.navigationOverlay.raise_()

        self.box.addWidget(self.readingContainer)
        self.box.setStretch(0,1)

        self.originalMode = True
        self.convertedTextView.hide()
        self.pdfWindow.show()
        
        self.navigationOverlay.raise_()

        self.setLayout(self.box)

        #Прочее
        self.docConverter = docConverter
        self.currentFilePath = ""
        self.document = QPdfDocument()
        self.maxPages = 0
        self.currentPage = 0
        
        self.convertedPagesCache = []

        
    def GetConvertedText(self):
        text = self.convertedPagesCache[self.currentPage]
        if(text == ""):
            self.ConvertPage(pageIndex=self.currentPage)
        text = self.convertedPagesCache[self.currentPage]
        self.convertedTextView.setHtml(text)
        return self.convertedTextView.toHtml()

    def SwitchModes(self):
        if(self.originalMode == True):
            self.originalMode = False
            self.convertedTextView.show()
            self.pdfWindow.hide()
        else:
            self.originalMode = True
            self.convertedTextView.hide()
            self.pdfWindow.show()
        
        self.navigationOverlay.raise_()

    def SetConvertedText(self, text):
        self.convertedTextView.setHtml(text)

    def LoadDocument(self, filePath):
        self.currentFilePath = filePath
        self.document.load(filePath)
        self.maxPages = self.docConverter.getPagesCount(filePath)
        self.pdfWindow.setDocument(self.document)
        self.convertedPagesCache.clear()
        self.convertedPagesCache = [str() for x in range(self.maxPages)]
        print(self.convertedPagesCache)
        #self.LoadConvertedPage(0)
        self.SetPdfPage(0)

        self.currentPage=0
        self.setPagesCount(self.currentPage)
        self.navigationOverlay.raise_()

    def ConvertPage(self, pageIndex):
        text = self.docConverter.convertPdf(self.currentFilePath, 1, pageIndex)
        self.convertedPagesCache[pageIndex] = text

    def LoadConvertedPage(self, pageIndex):
        if(pageIndex < 0 and pageIndex > self.maxPages): pass
        else:
            #if(self.convertedPagesCache[pageIndex] == ""):
               # self.ConvertPage(pageIndex=pageIndex)
            self.convertedTextView.setHtml(self.convertedPagesCache[pageIndex])

    def SetPdfPage(self, pageIndex):
        pass
        

    def OnPrevPageButtonClicked(self):
        if(self.currentPage - 1 >= 0):
            self.currentPage -= 1
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage,QPointF(0,0),1.0)
            self.setPagesCount(self.currentPage)

    def OnNextPageButtonClicked(self):
        if(self.currentPage + 1 < self.maxPages):
            self.currentPage += 1
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage,QPointF(0,0),1.0)
            self.setPagesCount(self.currentPage)

    def setPagesCount(self, current_page: int = 1):
        self.pagesLabel.setText(f"{current_page+1} из {self.maxPages}")

    def JumpTOPage(self):
        try:
            text = self.jumpPage.text().strip()
            if not text:
                return
            number = int(text) - 1
            if 0 <= number < self.maxPages:
                self.currentPage = number
                self.LoadConvertedPage(self.currentPage)
                self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)
                self.setPagesCount(self.currentPage)
                self.jumpPage.clear()
                self.jumpPage.clearFocus()
        except ValueError:
            self.jumpPage.clear()


