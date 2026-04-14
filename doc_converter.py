import os
import tempfile
# Тяжелые импорты вынесены в ленивую загрузку

class Converter:
    def __init__(self):
        self._converter = None

    @property
    def converter(self):
        if self._converter is None:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions

            # Configure accelerator options for GPU
            accelerator_options = AcceleratorOptions(
                device=AcceleratorDevice.AUTO
            )

            # Customize PDF pipeline
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = False
            # Отключаем принудительный OCR для всех страниц, чтобы ускорить работу с текстовыми PDF
            pipeline_options.ocr_options = EasyOcrOptions(lang=['ru', 'en'], force_full_page_ocr=False)
            pipeline_options.do_table_structure = False
            pipeline_options.accelerator_options = accelerator_options
            # Формулы замедляют процесс
            pipeline_options.do_formula_enrichment = False

            # Apply options to converter
            self._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        return self._converter

    def getPagesCount(self, filePath):
        from pypdf import PdfReader
        reader = PdfReader(filePath)
        number_of_pages = len(reader.pages)
        return number_of_pages
        
    def convertPdf(self, filePath, numOfPages, offset):
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(filePath)
        number_of_pages = len(reader.pages)

        result = str()
        if(numOfPages + offset <= number_of_pages ):
            for i in range(numOfPages):
                page = reader.pages[i + offset]

                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    
                    # Записываем PDF
                    writer = PdfWriter()
                    writer.add_page(page)
                    writer.write(tmp_path)

                    result += self.converter.convert(tmp_path).document.export_to_html()
                    
                    # Удаляем временный файл после конвертации
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
        return result
