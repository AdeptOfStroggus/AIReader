from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QGridLayout, QLineEdit, QProgressBar, QComboBox
from PySide6.QtCore import Qt, Signal, QSize, QPointF, QThread, Slot, QPropertyAnimation, QEasingCurve, QRunnable, QThreadPool, QTimer, QTime, QWaitCondition, QMutex, QMutexLocker
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPalette
from PySide6.QtPdf import QPdfDocument, QPdfLink
from PySide6.QtPdfWidgets import QPdfView
from doc_converter import Converter
from multiprocessing import cpu_count


class GpuWorker(QThread):
    pageConverted = Signal(int, str, str, list)  # pageIndex, text, html, images

    def __init__(self, docConverter, filePath):
        super().__init__()
        self.docConverter = docConverter
        self.filePath = filePath
        self.queue = []
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.running = True
        self._is_closing = False

    def add_page(self, pageIndex):
        with QMutexLocker(self.mutex):
            self.queue.append(pageIndex)
            self.condition.wakeOne()

    def run(self):
        print("GpuWorker запущен")
        while self.running:
            with QMutexLocker(self.mutex):
                if not self.queue:
                    self.condition.wait(self.mutex)
                if not self.running:
                    break
                pageIndex = self.queue.pop(0)
            print(f"GpuWorker: начата обработка страницы {pageIndex}")
            try:
                text, html, images = self.docConverter.convertPdf(self.filePath, 1, pageIndex)
                print(f"GpuWorker: страница {pageIndex} обработана, длина HTML: {len(html)}")
                self.pageConverted.emit(pageIndex, text, html, images)
            except Exception as e:
                print(f"GpuWorker: ошибка на странице {pageIndex}: {e}")
                self.pageConverted.emit(pageIndex, "", f"<p>Ошибка: {e}</p>", [])

class IndexingTask(QRunnable):
    def __init__(self, aiClient, pageIndex, text, images):
        super().__init__()
        self.aiClient = aiClient
        self.pageIndex = pageIndex
        self.text = text
        self.images = images

    def run(self):
        self.aiClient.rag_manager.add_page_text(self.text, self.pageIndex)
        for img in self.images:
            self.aiClient.image_indexer.add_image(img, self.pageIndex)

class ReaderPanel(QWidget):
    pageIndexed = Signal(int, str)
    pageConversionFinished = Signal(int, str)

    def __init__(self, docConverter: Converter, aiClient, parent=None):
        super().__init__(parent)
        self.aiClient = aiClient

        # PDF renderer
        self.pdfWindow = QPdfView(self)
        self.pdfWindow.setPageMode(QPdfView.PageMode.SinglePage)
        self.pdfWindow.setStyleSheet("background-color: #05050D;")

        # Converted text view
        self.convertedTextView = QTextEdit(self)
        self.convertedTextView.setAcceptRichText(True)
        self.convertedTextView.setReadOnly(True)
        self.convertedTextView.setStyleSheet("""
            QTextEdit {
                background-color: #05050D;
                color: #B0D8F0;
                border: none;
                padding: 24px 32px;
                font-size: 14px;
                line-height: 1.7;
            }
        """)

        # Navigation overlay — rectangular terminal-style, bottom-center
        self.navigationOverlay = QWidget()
        self.navigationOverlay.setStyleSheet("""
            QWidget {
                background-color: rgba(5, 5, 20, 0.92);
                border: 1px solid rgba(0,200,255,0.30);
                border-radius: 3px;
            }
        """)
        self.navigationOverlay.setFixedWidth(240)
        self.navigationOverlay.setFixedHeight(44)

        self.prevPage = QPushButton()
        self.prevPage.clicked.connect(self.OnPrevPageButtonClicked)
        self.prevPage.setText("←")
        self.prevPage.setShortcut(Qt.Key.Key_Left)
        self.prevPage.setFixedSize(32, 32)
        self.prevPage.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #3A6880;
                border-radius: 2px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(0,200,255,0.16);
                color: #00C8FF;
            }
            QPushButton:pressed {
                background-color: rgba(0,200,255,0.32);
                color: #80F0FF;
            }
        """)

        self.nextPage = QPushButton()
        self.nextPage.clicked.connect(self.OnNextPageButtonClicked)
        self.nextPage.setText("→")
        self.nextPage.setShortcut(Qt.Key.Key_Right)
        self.nextPage.setFixedSize(32, 32)
        self.nextPage.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #3A6880;
                border-radius: 2px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(0,200,255,0.16);
                color: #00C8FF;
            }
            QPushButton:pressed {
                background-color: rgba(0,200,255,0.32);
                color: #80F0FF;
            }
        """)

        self.jumpPage = QLineEdit()
        self.jumpPage.returnPressed.connect(self.JumpTOPage)
        self.jumpPage.setFixedSize(42, 26)
        self.jumpPage.setAlignment(Qt.AlignCenter)
        self.jumpPage.setPlaceholderText("...")
        self.jumpPage.setStyleSheet("""
            QLineEdit {
                background-color: rgba(0,200,255,0.06);
                border-radius: 2px;
                border: 1px solid rgba(0,200,255,0.18);
                color: #80C8E8;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(0,200,255,0.65);
                background-color: rgba(0,200,255,0.10);
            }
        """)

        self.pagesLabel = QLabel()
        self.pagesLabel.setText("0 / 0")
        self.pagesLabel.setStyleSheet(
            "background: transparent; color: #3A6880; font-size: 12px;"
        )

        self.navigationLayout = QHBoxLayout(self.navigationOverlay)
        self.navigationLayout.setContentsMargins(6, 6, 6, 6)
        self.navigationLayout.setSpacing(6)
        self.navigationLayout.addWidget(self.prevPage)
        self.navigationLayout.addWidget(self.jumpPage)
        self.navigationLayout.addWidget(self.pagesLabel)
        self.navigationLayout.addWidget(self.nextPage)

        # Loading bar — full-width strip at top of panel
        self.loadingBar = QProgressBar()
        self.loadingBar.setRange(0, 0)
        self.loadingBar.setTextVisible(False)
        self.loadingBar.setFixedHeight(3)
        self.loadingBar.setStyleSheet("""
            QProgressBar {
                background-color: transparent;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #00C8FF;
                border-radius: 0px;
            }
        """)
        self.loadingBar.hide()

        # Status overlay — top-right corner, terminal-style box
        self.statusOverlay = QWidget()
        self.statusOverlay.setStyleSheet("""
            QWidget {
                background-color: rgba(5, 5, 20, 0.92);
                border: 1px solid rgba(0,200,255,0.25);
                border-radius: 3px;
            }
        """)
        self.statusOverlay.setFixedWidth(210)
        self.statusOverlay.setFixedHeight(58)

        self.statusCombo = QComboBox()
        self.statusCombo.currentIndexChanged.connect(self.OnStatusComboChanged)
        self.statusCombo.setStyleSheet("""
            QComboBox {
                border: none;
                background-color: transparent;
                color: #6888A8;
                padding: 3px 8px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #3A6880;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #0E0E24;
                color: #6888A8;
                border: 1px solid rgba(0,200,255,0.22);
                border-radius: 2px;
                selection-background-color: rgba(0,200,255,0.18);
                selection-color: #C0F0FF;
                outline: 0px;
                padding: 4px;
            }
        """)

        self.statusLayout = QVBoxLayout(self.statusOverlay)
        self.statusLayout.setContentsMargins(6, 6, 6, 6)
        self.statusLayout.setSpacing(2)

        self.statusSummaryLabel = QLabel("0/0/(0)")
        self.statusSummaryLabel.setStyleSheet(
            "background: transparent; color: #2A5068; font-size: 10px;"
        )
        self.statusSummaryLabel.setToolTip(
            "x/y/(z): x — обработанных страниц, y — всего страниц, z — сейчас обрабатывается"
        )
        self.statusLayout.addWidget(self.statusSummaryLabel)
        self.statusLayout.addWidget(self.statusCombo)

        # Reading container with overlays
        self.readingContainer = QWidget()
        self.readingLayout = QGridLayout(self.readingContainer)
        self.readingLayout.setContentsMargins(0, 0, 8, 16)
        self.readingLayout.setSpacing(0)

        self.readingLayout.addWidget(self.pdfWindow, 0, 0)
        self.readingLayout.addWidget(self.convertedTextView, 0, 0)

        # Nav at bottom-center, status at top-right
        self.readingLayout.addWidget(self.navigationOverlay, 0, 0, Qt.AlignHCenter | Qt.AlignBottom)
        self.readingLayout.addWidget(self.statusOverlay, 0, 0, Qt.AlignRight | Qt.AlignTop)

        self.navigationOverlay.raise_()
        self.statusOverlay.raise_()

        # Main layout: loading bar on top, reading area fills rest
        self.box = QVBoxLayout()
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(0)
        self.box.addWidget(self.loadingBar, 0)
        self.box.addWidget(self.readingContainer, 1)

        self.originalMode = True
        self.convertedTextView.hide()
        self.pdfWindow.show()

        self.navigationOverlay.raise_()

        self.setLayout(self.box)

        # State
        self.docConverter = docConverter
        self.currentFilePath = ""
        self.document = QPdfDocument()
        self.maxPages = 0
        self.currentPage = 0

        self.convertedPagesCache = []
        self.conversionInProgress = set()
        self.workerQueue = []
        self.pendingQueueUpdate = False
        self._pendingHighlight = ""
        self._lastUIUpdateTime = 0
        self._uiUpdateDebounce = 100

        try:
            num_cores = cpu_count()
            self.maxConcurrentWorkers = 1
        except:
            self.maxConcurrentWorkers = 1

        self.cpuPool = QThreadPool.globalInstance()
        try:
            num_cores = cpu_count()
            cpu_threads = max(2, num_cores // 2)
        except:
            cpu_threads = 4
        self.cpuPool.setMaxThreadCount(cpu_threads)
        print(f"CPU пул для индексации: {cpu_threads} потоков")

        self.gpuWorker = None
        self._is_closing = False
        self.isDarkMode = True

    def GetConvertedText(self):
        if not self.convertedPagesCache or self.currentPage >= len(self.convertedPagesCache):
            return "Текст не загружен"

        text = self.convertedPagesCache[self.currentPage]
        if text == "":
            self.LoadConvertedPage(self.currentPage)
            return "Текст загружается, подождите..."

        return self.convertedTextView.toPlainText()

    def SwitchModes(self):
        if self.originalMode:
            self.originalMode = False
            self.convertedTextView.show()
            self.pdfWindow.hide()
            self.LoadConvertedPage(self.currentPage)
        else:
            self.originalMode = True
            self.convertedTextView.hide()
            self.pdfWindow.show()

        self.navigationOverlay.raise_()

    def SetConvertedText(self, text):
        self.convertedTextView.setHtml(text)

    def LoadDocument(self, filePath):
        if self.gpuWorker is not None:
            self.gpuWorker.running = False
            self.gpuWorker.condition.wakeOne()
            self.gpuWorker.wait()
            self.gpuWorker = None

        self.cpuPool.waitForDone()

        self.currentFilePath = filePath
        self.document.load(filePath)
        self.maxPages = self.docConverter.getPagesCount(filePath)

        self.statusCombo.blockSignals(True)
        self.statusCombo.clear()
        for i in range(self.maxPages):
            self.statusCombo.addItem(f"Стр. {i+1}  —  ◌ Ожидание")
            self.statusCombo.setItemData(i, QColor("#3A5A78"), Qt.ItemDataRole.ForegroundRole)
        self.statusCombo.blockSignals(False)

        self.pdfWindow.setDocument(self.document)
        self.convertedPagesCache.clear()
        self.convertedPagesCache = ["" for _ in range(self.maxPages)]

        self.conversionInProgress.clear()
        self.workerQueue.clear()
        self.pendingQueueUpdate = False
        if self.aiClient is not None:
            self.aiClient.rag_manager.clear()

        print("Инициализирую конвертер для первой страницы...")
        try:
            _ = self.docConverter.converter
            print("Конвертер инициализирован успешно")
        except Exception as e:
            print(f"Ошибка при инициализации конвертера: {e}")

        try:
            self.gpuWorker = GpuWorker(self.docConverter, filePath)
            self.gpuWorker.pageConverted.connect(self._onPageConversionFinished)
            self.gpuWorker.start()
            print("gpuWorker запущен")
        except Exception as e:
            print(f"Ошибка создания gpuWorker: {e}")
        print(f"LoadDocument: gpuWorker создан, running={self.gpuWorker.running}")

        self.currentPage = 0
        self.setPagesCount(self.currentPage)
        self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)

        self.LoadConvertedPage(self.currentPage)
        self.UpdateStatusSummary()
        self.navigationOverlay.raise_()

    def UpdatePageStatus(self, pageIndex, force=False):
        if pageIndex < 0 or pageIndex >= self.statusCombo.count():
            return

        if self.convertedPagesCache[pageIndex] != "":
            status_text = "✓ Готово"
            color = QColor("#00FF88")
        elif pageIndex in self.conversionInProgress:
            status_text = "● Обработка"
            color = QColor("#00C8FF")
        elif pageIndex in self.workerQueue:
            status_text = "○ В очереди"
            color = QColor("#6888A8")
        else:
            status_text = "◌ Ожидание"
            color = QColor("#3A5A78")

        current_text = self.statusCombo.itemText(pageIndex)
        new_text = f"Стр. {pageIndex + 1}  —  {status_text}"

        if force or current_text != new_text:
            self.statusCombo.setItemText(pageIndex, new_text)
            self.statusCombo.setItemData(pageIndex, color, Qt.ItemDataRole.ForegroundRole)

        self.UpdateStatusSummary()

    def OnStatusComboChanged(self, index):
        if index != self.currentPage and index >= 0:
            self.currentPage = index
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)
            self.setPagesCount(self.currentPage)

    def UpdateStatusSummary(self):
        total_pages = self.maxPages
        processed_pages = sum(1 for t in self.convertedPagesCache if t != "") if total_pages else 0
        processing_pages = len(self.conversionInProgress)
        self.statusSummaryLabel.setText(f"{processed_pages}/{total_pages}/({processing_pages})")

    def UpdateQueueOrder(self):
        self.workerQueue.clear()
        if self.convertedPagesCache[self.currentPage] == "" and self.currentPage not in self.conversionInProgress:
            self.workerQueue.append(self.currentPage)
            self.UpdatePageStatus(self.currentPage)
        for i in range(self.currentPage - 1, -1, -1):
            if self.convertedPagesCache[i] == "" and i not in self.conversionInProgress and i not in self.workerQueue:
                self.workerQueue.append(i)
                self.UpdatePageStatus(i)
        for i in range(self.currentPage + 1, self.maxPages):
            if self.convertedPagesCache[i] == "" and i not in self.conversionInProgress and i not in self.workerQueue:
                self.workerQueue.append(i)
                self.UpdatePageStatus(i)
        self.ProcessQueue()

    def PreloadNearbyPages(self, radius=5):
        start = max(0, self.currentPage - radius)
        end = min(self.maxPages, self.currentPage + radius + 1)
        added = False
        for i in range(start, end):
            if i != self.currentPage:
                if self.convertedPagesCache[i] == "" and i not in self.conversionInProgress and i not in self.workerQueue:
                    self.workerQueue.append(i)
                    added = True
        if added:
            self.ProcessQueue()

    def ProcessQueue(self):
        if self.gpuWorker is None:
            print("ProcessQueue: gpuWorker is None")
            return
        if not self.gpuWorker.running:
            print(f"ProcessQueue: gpuWorker.running = {self.gpuWorker.running}")
            return
        if not self.gpuWorker or not self.gpuWorker.running:
            print("ProcessQueue: gpuWorker не готов")
            return
        while self.workerQueue:
            pageIndex = self.workerQueue.pop(0)
            if self.convertedPagesCache[pageIndex] != "" or pageIndex in self.conversionInProgress:
                continue
            self.conversionInProgress.add(pageIndex)
            self.UpdatePageStatus(pageIndex)
            print(f"ProcessQueue: отправляю страницу {pageIndex} в gpuWorker")
            self.gpuWorker.add_page(pageIndex)
        def OnPageConverted(self, pageIndex, text):
            self.pageConversionFinished.emit(pageIndex, text)

    @Slot(int, str, str, list)
    def _onPageConversionFinished(self, pageIndex, text, html, images):
        if self._is_closing:
            return
        print(f"Главный поток: получена страница {pageIndex}")

        if pageIndex in self.conversionInProgress:
            self.conversionInProgress.discard(pageIndex)

        self.convertedPagesCache[pageIndex] = html

        indexing_task = IndexingTask(self.aiClient, pageIndex, text, images)
        self.cpuPool.start(indexing_task)

        self.UpdatePageStatus(pageIndex, force=(pageIndex == self.currentPage))

        if pageIndex == self.currentPage:
            self.convertedTextView.setHtml(html)
            self.loadingBar.hide()

            if self._pendingHighlight:
                self._HighlightSnippet(self._pendingHighlight)
                self._pendingHighlight = ""

            self.PreloadNearbyPages(radius=5)

        if self.pendingQueueUpdate:
            self.pendingQueueUpdate = False
            self.UpdateQueueOrder()
        else:
            self.ProcessQueue()

    def LoadConvertedPage(self, pageIndex):
        if pageIndex < 0 or pageIndex >= self.maxPages:
            return

        if self.convertedPagesCache[pageIndex] == "":
            self.loadingBar.show()

            if pageIndex in self.conversionInProgress or pageIndex in self.workerQueue:
                self.convertedTextView.setHtml(
                    "<div style='color: #00C8FF; text-align: center; margin-top: 60px; font-size: 14px;'>"
                    "Страница загружается...</div>"
                )

            if self.conversionInProgress:
                self.pendingQueueUpdate = True
            else:
                self.UpdateQueueOrder()
        else:
            self.loadingBar.hide()
            self.convertedTextView.setHtml(self.convertedPagesCache[pageIndex])

            if self._pendingHighlight:
                self._HighlightSnippet(self._pendingHighlight)
                self._pendingHighlight = ""

            if self.conversionInProgress:
                self.pendingQueueUpdate = True
            else:
                self.UpdateQueueOrder()

    def SetPdfPage(self, pageIndex):
        pass

    def closeEvent(self, event):
        self._is_closing = True
        if self.gpuWorker is not None:
            try:
                self.gpuWorker.pageConverted.disconnect(self._onPageConversionFinished)
            except TypeError:
                pass
            self.gpuWorker.running = False
            self.gpuWorker.condition.wakeOne()
            if not self.gpuWorker.wait(3000):
                print("GpuWorker не завершился, принудительно завершаем")
                self.gpuWorker.terminate()
                self.gpuWorker.wait()
        self.cpuPool.waitForDone(2000)
        super().closeEvent(event)

    def OnPrevPageButtonClicked(self):
        if self.currentPage - 1 >= 0:
            self.currentPage -= 1
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)
            self.setPagesCount(self.currentPage)

    def OnNextPageButtonClicked(self):
        if self.currentPage + 1 < self.maxPages:
            self.currentPage += 1
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)
            self.setPagesCount(self.currentPage)

    def JumpToSource(self, pageIndex, snippet):
        if pageIndex < 0 or pageIndex >= self.maxPages:
            return

        self._pendingHighlight = snippet

        if self.currentPage == pageIndex:
            self._HighlightSnippet(snippet)
            self._pendingHighlight = ""
        else:
            self.currentPage = pageIndex
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)
            self.setPagesCount(self.currentPage)

        if self.originalMode:
            self.SwitchModes()

    def _HighlightSnippet(self, snippet):
        if not snippet:
            return

        self.convertedTextView.setExtraSelections([])

        cursor = self.convertedTextView.document().find(snippet)
        if not cursor.isNull():
            from PySide6.QtWidgets import QTextEdit
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#004060"))
            selection.format.setForeground(QColor("#00F0FF"))
            selection.cursor = cursor
            self.convertedTextView.setExtraSelections([selection])
            self.convertedTextView.setTextCursor(cursor)
            self.convertedTextView.ensureCursorVisible()

    def SetDarkMode(self, is_dark, fs=14):
        self.isDarkMode = is_dark

        if is_dark:
            self.pdfWindow.setStyleSheet("background-color: #05050D;")
            self.convertedTextView.setStyleSheet(f"""
                QTextEdit {{
                    background-color: #05050D;
                    color: #B0D8F0;
                    border: none;
                    padding: 24px 32px;
                    line-height: 1.7;
                    font-size: {fs}px;
                }}
            """)

            palette = self.convertedTextView.palette()
            palette.setColor(QPalette.ColorRole.Link, QColor("#00C8FF"))
            palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#80E0FF"))
            self.convertedTextView.setPalette(palette)

            self.navigationOverlay.setStyleSheet("""
                QWidget {
                    background-color: rgba(5, 5, 20, 0.92);
                    border: 1px solid rgba(0,200,255,0.30);
                    border-radius: 3px;
                }
            """)

            nav_button_style = f"""
                QPushButton {{
                    background-color: transparent;
                    color: #3A6880;
                    border-radius: 2px;
                    font-weight: bold;
                    border: none;
                    font-size: {fs + 2}px;
                }}
                QPushButton:hover {{
                    background-color: rgba(0,200,255,0.16);
                    color: #00C8FF;
                }}
                QPushButton:pressed {{
                    background-color: rgba(0,200,255,0.32);
                    color: #80F0FF;
                }}
            """
            self.prevPage.setStyleSheet(nav_button_style)
            self.nextPage.setStyleSheet(nav_button_style)

            self.jumpPage.setStyleSheet(f"""
                QLineEdit {{
                    background-color: rgba(0,200,255,0.06);
                    border-radius: 2px;
                    border: 1px solid rgba(0,200,255,0.18);
                    color: #80C8E8;
                    font-size: {fs - 2}px;
                }}
                QLineEdit:focus {{
                    border: 1px solid rgba(0,200,255,0.65);
                    background-color: rgba(0,200,255,0.10);
                }}
            """)
            self.pagesLabel.setStyleSheet(
                f"background: transparent; color: #3A6880; font-size: {fs - 2}px;"
            )
            self.loadingBar.setStyleSheet("""
                QProgressBar {
                    background-color: transparent;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: #00C8FF;
                    border-radius: 0px;
                }
            """)
            self.statusOverlay.setStyleSheet("""
                QWidget {
                    background-color: rgba(5, 5, 20, 0.92);
                    border: 1px solid rgba(0,200,255,0.25);
                    border-radius: 3px;
                }
            """)
            self.statusSummaryLabel.setStyleSheet(
                "background: transparent; color: #2A5068; font-size: 10px;"
            )
            self.statusCombo.setStyleSheet(f"""
                QComboBox {{
                    border: none;
                    background-color: transparent;
                    color: #6888A8;
                    padding: 3px 8px;
                    font-size: {fs - 3}px;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 18px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #3A6880;
                    margin-right: 6px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: #0E0E24;
                    color: #6888A8;
                    border: 1px solid rgba(0,200,255,0.22);
                    border-radius: 2px;
                    selection-background-color: rgba(0,200,255,0.18);
                    selection-color: #C0F0FF;
                    outline: 0px;
                    padding: 4px;
                    font-size: {fs - 3}px;
                }}
            """)
        else:
            self.pdfWindow.setStyleSheet("background-color: #EEEEE6;")
            self.convertedTextView.setStyleSheet(f"""
                QTextEdit {{
                    background-color: #EEEEE6;
                    color: #0A1828;
                    border: none;
                    padding: 24px 32px;
                    line-height: 1.7;
                    font-size: {fs}px;
                }}
            """)

            palette = self.convertedTextView.palette()
            palette.setColor(QPalette.ColorRole.Link, QColor("#0055CC"))
            palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#7700CC"))
            self.convertedTextView.setPalette(palette)

            self.navigationOverlay.setStyleSheet("""
                QWidget {
                    background-color: rgba(240, 240, 230, 0.96);
                    border: 1px solid #90A8C0;
                    border-radius: 3px;
                }
            """)

            nav_button_style = f"""
                QPushButton {{
                    background-color: transparent;
                    color: #6080A0;
                    border-radius: 2px;
                    font-weight: bold;
                    border: none;
                    font-size: {fs + 2}px;
                }}
                QPushButton:hover {{
                    background-color: rgba(0,80,180,0.10);
                    color: #0055CC;
                }}
                QPushButton:pressed {{
                    background-color: rgba(0,80,180,0.20);
                    color: #0040AA;
                }}
            """
            self.prevPage.setStyleSheet(nav_button_style)
            self.nextPage.setStyleSheet(nav_button_style)

            self.jumpPage.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #F0F0E8;
                    border-radius: 2px;
                    border: 1px solid #90A8C0;
                    color: #0A1828;
                    font-size: {fs - 2}px;
                }}
                QLineEdit:focus {{
                    border: 1px solid #0055CC;
                    background-color: rgba(0,80,180,0.06);
                }}
            """)
            self.pagesLabel.setStyleSheet(
                f"background: transparent; color: #6080A0; font-size: {fs - 2}px;"
            )
            self.loadingBar.setStyleSheet("""
                QProgressBar {
                    background-color: transparent;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: #0055CC;
                    border-radius: 0px;
                }
            """)
            self.statusOverlay.setStyleSheet("""
                QWidget {
                    background-color: rgba(240, 240, 230, 0.96);
                    border: 1px solid #90A8C0;
                    border-radius: 3px;
                }
            """)
            self.statusSummaryLabel.setStyleSheet(
                "background: transparent; color: #6080A0; font-size: 10px;"
            )
            self.statusCombo.setStyleSheet(f"""
                QComboBox {{
                    border: none;
                    background-color: transparent;
                    color: #304050;
                    padding: 3px 8px;
                    font-size: {fs - 3}px;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 18px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #6080A0;
                    margin-right: 6px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: #F0F0E8;
                    color: #1A2A3A;
                    border: 1px solid #90A8C0;
                    border-radius: 2px;
                    selection-background-color: rgba(0,80,180,0.12);
                    selection-color: #0040AA;
                    outline: 0px;
                    padding: 4px;
                    font-size: {fs - 3}px;
                }}
            """)

    def setPagesCount(self, current_page: int = 1):
        self.pagesLabel.setText(f"{current_page + 1} / {self.maxPages}")

    def StopAllWorkers(self):
        self.conversionInProgress.clear()
        self.workerQueue.clear()

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
