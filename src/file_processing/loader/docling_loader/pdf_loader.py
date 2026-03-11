import sys
import time
import asyncio
import base64
import re
import logging
from pathlib import Path
from typing import Dict, Optional

from docling_core.types.doc import ImageRefMode, PictureItem, TableItem
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

if __name__ == "__main__":
    import sys
    sys.path.append("/Users/ezhilrajselvaraj/Ezhil/ever_quint/perkinswill/hub/marketing_toolkit/src/model")
    sys.path.append("/Users/ezhilrajselvaraj/Ezhil/ever_quint/perkinswill/hub/marketing_toolkit/")
    from dotenv import load_dotenv
    load_dotenv() 
    print("looded dot env")
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
from src.utils.hashing import Hashing
from src.cache.pdf_data.image_cache import ImageCache
from src.config import OCR_LIMIT,IMAGE_RESOLUTION_SCALE
from src.model.openai_client import OpenAIClient
from src.utils.clean import cleanup_directory

logger = logging.getLogger(__name__)


class DoclingLoader:
    def __init__(self):
        self.result = []
        self.hash = Hashing()
        self.cache = ImageCache()
        self.openai_client = OpenAIClient()
        pipeline_options = PdfPipelineOptions()
        pipeline_options.images_scale = 2.0
        pipeline_options.generate_page_images = True
        pipeline_options.generate_picture_images = True
        
        self.doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    async def get_image_descriptions(self, image_paths: list) -> Dict[str, str]:
        # [('picture-1', PosixPath('waste/test-picture-1.png')), 
        #  ('table-1', PosixPath('waste/test-table-1.png')), 
        #  ('picture-2', PosixPath('waste/test-picture-2.png')), 
        #  ('table-2', PosixPath('waste/test-table-2.png'))]
        temp_hash_stg = {}
        async def describe_one(key: str, img_path: Path) -> tuple:
            try:
                nonlocal temp_hash_stg
                temp_hash = self.hash.image_hash(img_path.resolve())

                temp_hash = str(temp_hash)
                cache_data = self.cache.get_text(temp_hash)
                doc = self.doc_converter.convert(img_path)
                text = doc.document.export_to_text()
                if len(text.strip()) <= OCR_LIMIT:
                    logger.info(f"{text} is not added to context due to the length less than {OCR_LIMIT}")
                    return (key, None)
                if cache_data:
                    logger.info(f"returing description from the cache")
                    temp_hash_stg[temp_hash] = cache_data
                    return (key,cache_data)
                with open(img_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode('utf-8')
                description = await self.openai_client.get_description(img_data)
                self.cache.put_text(temp_hash,description)
                temp_hash_stg[temp_hash] = description
                return (key, description)
            except Exception as e:
                logger.error(f"Error describing {key}: {e}")
                return (key, None)
        tasks = [describe_one(key, path) for key, path in image_paths]
        results = await asyncio.gather(*tasks)
        return dict(results),temp_hash_stg
    
    def replace_images_with_descriptions(self, markdown_text: str, image_descriptions: Dict[str, str]) -> str:
        picture_count = 0
        table_count = 0
        def replace_match(match):
            nonlocal picture_count, table_count
            alt_text = match.group(1).lower()
            if "table" in alt_text:
                table_count += 1
                key = f"table-{table_count}"
                desc = image_descriptions.get(key, None)
                if desc:
                    return f"\n\n**Table {table_count}:**\n\n{desc}\n\n"
                return ""
            else:
                picture_count += 1
                key = f"picture-{picture_count}"
                desc = image_descriptions.get(key, None)
                if desc:
                    return f"\n\n**Image {picture_count}:**\n\n{desc}\n\n"
                return ""
        
        enhanced = re.sub(
            r'!\[([^\]]*)\]\(data:image/[^)]+\)',
            replace_match,
            markdown_text
        )
        enhanced = re.sub(r'\n{3,}', '\n\n', enhanced)
        return enhanced
    
    async def process_document(
        self,
        source_path: str,
        output_dir: str = "scratch"
    ) -> Dict:
        try:
            hash_data = {}
            output_path = Path(output_dir)
            count = 0
            while output_path.exists() and output_path.is_dir():
                count+=1
                output_path = Path(output_dir+f"_{count}")
                logger.warning(f"directory already exists : {output_dir}_{count-1}")
            output_path.mkdir(parents=True, exist_ok=True)  
            
            logger.info("Converting document with Docling...")
            conv_res = self.doc_converter.convert(source_path)
            doc = conv_res.document
            base_name = conv_res.input.file.stem if conv_res.input and conv_res.input.file else "document"
            
            md_embedded = output_path / f"{base_name}-with-images.md"
            doc.save_as_markdown(md_embedded, image_mode=ImageRefMode.EMBEDDED)
            logger.info(f"Initial markdown saved: {md_embedded}")
            
            image_paths = []
            
            picture_counter = 0
            table_counter = 0
            for element, _level in doc.iterate_items():
                if isinstance(element, PictureItem):
                    picture_counter += 1
                    img_path = output_path / f"{base_name}-picture-{picture_counter}.png"
                    with img_path.open("wb") as fp:
                        element.get_image(doc).save(fp, "PNG")
                    image_paths.append((f"picture-{picture_counter}", img_path))
                    
                elif isinstance(element, TableItem):
                    table_counter += 1
                    img_path = output_path / f"{base_name}-table-{table_counter}.png"
                    with img_path.open("wb") as fp:
                        element.get_image(doc).save(fp, "PNG")
                    image_paths.append((f"table-{table_counter}", img_path))
            
            logger.info(f"Extracted {picture_counter} pictures and {table_counter} tables")
            
            logger.info("Getting AI descriptions...")

            descriptions,hash_stg = await self.get_image_descriptions(image_paths)
            
            logger.info("Creating enhanced markdown...")
            original_md = md_embedded.read_text(encoding="utf-8")
            enhanced_md = self.replace_images_with_descriptions(original_md, descriptions)
            
            enhanced_md_path = output_path / f"{base_name}-enhanced.md"
            enhanced_md_path.write_text(enhanced_md, encoding="utf-8")
            
            plain_text = re.sub(r'[#*`_]', '', enhanced_md)
            plain_text = re.sub(r'\n{2,}', '\n\n', plain_text).strip()
            
            enhanced_txt_path = output_path / f"{base_name}-enhanced.txt"
            enhanced_txt_path.write_text(plain_text, encoding="utf-8")
            
            logger.info("Processing complete!")
            try: 
                formatted_text = enhanced_md.encode().decode("unicode_escape")
            except Exception as e:
                formatted_text = enhanced_md

            return {
                "markdown": formatted_text,
                "image_hash": hash_stg
                # "enhanced_text": str(enhanced_txt_path),
                # "original_markdown": str(md_embedded),
                # "image_count": len(image_paths),
                # "descriptions": descriptions,
                # "output_dir": str(output_path)
            }
        except Exception as e:
            logger.exception("Error in the processing document {source_path} message {e}")
            raise RuntimeError("Error in the processing document {source_path} message {e}")
        finally:
            cleanup_directory(output_path)

if __name__=="__main__":

    obj = DoclingLoader()
    from openai_client import OpenAIClient
    openai_client = OpenAIClient()
    out = asyncio.run(obj.process_document("/Users/ezhilrajselvaraj/Downloads/test.pdf","waste"))
    print("=========================")
    print(out)
    with open("file_laoder_check.json",'w') as f:
        import json
        json.dump(out,f,indent=4)