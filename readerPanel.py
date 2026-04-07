from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel
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
        self.navigationLayoutWidget = QWidget()

        self.prevPage = QPushButton()
        self.prevPage.clicked.connect(self.OnPrevPageButtonClicked)
        self.prevPage.setText("Назад")
        self.prevPage.setShortcut(Qt.Key.Key_Left)

        self.nextPage = QPushButton()
        self.nextPage.clicked.connect(self.OnNextPageButtonClicked)
        self.nextPage.setText("Вперёд")
        self.nextPage.setShortcut(Qt.Key.Key_Right)

        self.jumpPage = QTextEdit()
        self.jumpPage.selectionChanged.connect(self.JumpTOPage)
        self.jumpPage.setFixedHeight(20)


        self.pagesLabel = QLabel()
        self.pagesLabel.setText("Страница 0 из 0")

        self.navigationLayout = QHBoxLayout()

        self.navigationLayout.addWidget(self.prevPage)
        self.navigationLayout.addWidget(self.jumpPage)
        self.navigationLayout.addWidget(self.pagesLabel)
        self.navigationLayout.addWidget(self.nextPage)
        self.navigationLayoutWidget.setLayout(self.navigationLayout)
        self.navigationLayout.setStretch(0,2)
        self.navigationLayout.setStretch(1,3)
        self.navigationLayout.setStretch(2,3)
        self.navigationLayout.setStretch(3,2)



        #Основной layout
        self.box = QVBoxLayout()
        self.box.addWidget(self.navigationLayoutWidget)
        self.box.addWidget(self.pdfWindow)
        self.box.addWidget(self.convertedTextView)
        self.box.setStretch(0,1)
        self.box.setStretch(1,20)
        self.box.setStretch(2,20)

        self.originalMode = True
        self.convertedTextView.hide()
        self.pdfWindow.show()

        self.setLayout(self.box)

        #Прочее
        self.docConverter = docConverter
        self.currentFilePath = ""
        self.document = QPdfDocument()
        self.maxPages = 0
        self.currentPage = 0
        
        self.convertedPagesCache = []

        
    def GetConvertedText(self):
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
        self.LoadConvertedPage(0)
        self.SetPdfPage(0)

        self.currentPage=0
        self.setPagesCount(self.currentPage)

    def ConvertPage(self, pageIndex):
        text = self.docConverter.convertPdf(self.currentFilePath, 1, pageIndex)
        self.convertedPagesCache[pageIndex] = text

    def LoadConvertedPage(self, pageIndex):
        if(pageIndex < 0 and pageIndex > self.maxPages): pass
        else:
            if(self.convertedPagesCache[pageIndex] == ""):
                self.ConvertPage(pageIndex=pageIndex)
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
        self.pagesLabel.setText(f"Страница {current_page+1} из {self.maxPages}")

    def JumpTOPage(self):
        number = int(self.jumpPage.toPlainText())-1
        if(number < self.maxPages and number > 0):
            self.currentPage = number
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage,QPointF(0,0),1.0)
            self.setPagesCount(self.currentPage)


