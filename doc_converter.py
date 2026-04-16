import os
import tempfile
# Тяжелые импорты вынесены в ленивую загрузку
from docling.datamodel.settings import settings
settings.perf.page_batch_size = 32
class Converter:
    def __init__(self):
        self._converter = None

    @property
    def converter(self):
        if self._converter is None:
            import torch
            print("CUDA доступна:", torch.cuda.is_available())
            
            from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption
            from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions, ThreadedPdfPipelineOptions
            from docling.pipeline.vlm_pipeline import VlmPipeline
            from docling_core.types.doc.base import ImageRefMode
          #  
            # Configure accelerator options for GPU
            accelerator_options = AcceleratorOptions(
                device=AcceleratorDevice.CUDA
            )

            print("Устройство:", accelerator_options.device)
            

            # Customize PDF pipeline
            pipeline_options = ThreadedPdfPipelineOptions()
            pipeline_options.do_ocr = True
            # Отключаем принудительный OCR для всех страниц, чтобы ускорить работу с текстовыми PDF
            pipeline_options.ocr_options = EasyOcrOptions(lang=['ru', 'en'])
            
            pipeline_options.do_table_structure = True
            pipeline_options.accelerator_options = accelerator_options
            # Формулы замедляют процесс
            pipeline_options.do_formula_enrichment = True
            pipeline_options.do_code_enrichment = True

            pipeline_options.generate_picture_images = True
            pipeline_options.generate_table_images = True
            pipeline_options.generate_page_images = True

            pipeline_options.ocr_batch_size = 32
            pipeline_options.layout_batch_size = 32

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

        from docling_core.types.doc.base import ImageRefMode
        from docling_core.types.doc.document import PictureItem, TableItem
        import base64
        from io import BytesIO

        reader = PdfReader(filePath)
        number_of_pages = len(reader.pages)

        result_text = str()
        result_overall = str()
        result_imgs = []

        if numOfPages == 1:
            page_range = (offset + 1, offset + 1)   # одна страница
        else:
            page_range = (offset + 1, offset + numOfPages)
        result_loc = self.converter.convert(filePath, page_range=page_range).document
        result_text += result_loc.export_to_text()
        result_overall += result_loc.export_to_html(image_mode=ImageRefMode.EMBEDDED)

        for element, _ in result_loc.iterate_items():
            if isinstance(element, (PictureItem, TableItem)):
                buffered = BytesIO()
                image = element.get_image(result_loc)   # получаем PIL Image
                image.save(buffered, format='JPEG')
                result_imgs.append(base64.b64encode(buffered.getvalue()).decode())  # конвертируем в base64 для передачи в UI

    
    
        return [result_text, result_overall, result_imgs]
