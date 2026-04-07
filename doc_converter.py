from docling.document_converter import DocumentConverter
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from pypdf import PdfReader, PdfWriter
from io import BytesIO
import tempfile
import os
from PySide6.QtPdf import QPdfDocument

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode, RapidOcrOptions, EasyOcrOptions


class Converter:
    def __init__(self):
        # Configure accelerator options for GPU
        accelerator_options = AcceleratorOptions(
            device=AcceleratorDevice.AUTO,  # or AcceleratorDevice.AUTO
        )


        # Customize PDF pipeline
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.ocr_options = EasyOcrOptions(lang=['ru', 'en'], force_full_page_ocr=True, recog_network="craft")
        pipeline_options.do_table_structure = True
        #pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
        pipeline_options.accelerator_options = accelerator_options
        pipeline_options.do_formula_enrichment = True


        # Apply options to converter
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    def getPagesCount(self, filePath):
        reader = PdfReader(filePath)
        number_of_pages = len(reader.pages)
        return number_of_pages
        
    def convertPdf(self, filePath, numOfPages, offset):

        reader = PdfReader(filePath)
        number_of_pages = len(reader.pages)

        result = str()
        if(numOfPages + offset < number_of_pages ):
            for i in range(numOfPages):
                page = reader.pages[i + offset]

                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    
                    # Записываем PDF
                    writer = PdfWriter()
                    writer.add_page(page)
                    writer.write(tmp_path)

                    result += self.converter.convert(tmp_path).document.export_to_html()
        return result
