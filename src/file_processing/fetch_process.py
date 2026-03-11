import aiohttp
import asyncio
import sys
import re
import os
from urllib.parse import unquote
import fitz
import os
from PIL import Image
if __name__ == "__main__":
    import sys
    sys.path.append("/Users/ezhilrajselvaraj/Ezhil/ever_quint/perkinswill/hub/marketing_toolkit")
    from dotenv import load_dotenv
    load_dotenv()
import logging

logger = logging.getLogger(__name__)

from src.utils.image_to_base import image_to_base64
from src.model.openai_client import OpenAIClient
from src.file_processing.loader.docling_loader.pdf_loader import DoclingLoader
from src.file_processing.loader.docling_loader.audio_process import AudioProcess
from src.file_processing.loader.docling_loader.csv_loader import CSVLoader
from src.file_processing.loader.conversion.audio_process import AudioConversion
from src.file_processing.loader.conversion.csv_conversion import CSVConvertor
from src.file_processing.loader.conversion.docx_process import DocxConvertor
from src.file_processing.loader.conversion.pdf_process import PDFConvertor
from src.file_processing.loader.conversion.pptx_process import PPTXConvertor
from src.utils.hashing import Hashing
from src.utils.file_manager import FileManager

from src.config import SESSION_ID

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff",".psd",".icns",".ico",".webp",".avif")

class FetchData:
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.file_getting = {
            "model": "Files",
            "type": "query",
            "query": "Files",
            "arguments": {
                "page": 0,
                "size": 1000,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match": {
                                    "customFields.toolkitArticleId": ""
                                }
                            },
                            {
                                "match": {
                                    "settings.isDeleted": False
                                }
                            }
                        ]
                    }
                }
            }
        }
        self.url = "https://api.hub.perkinswill.com/graph"
        self.cookies = {"authentication": SESSION_ID}
        self.pdf_pptx_processor = DoclingLoader()
        self.audio_processor = AudioProcess()
        self.csv_processor = CSVLoader()
        self.file_manager = FileManager()

    async def get_data(self, article_id):
        self.file_getting["arguments"]["query"]["bool"]["must"][0]["match"]["customFields.toolkitArticleId"] = article_id
        results =[]
        async with aiohttp.ClientSession(cookies=self.cookies) as session:
            async with session.post(self.url, json=self.file_getting) as resp:
                if resp.status != 200:
                    raise Exception(f"Graph API failed: {resp.status}")
                data = await resp.json()
                values = data["value"]["values"]
                print("Files found:", len(values))
                try:
                    for res in values:
                        if not res.get("url"):
                            continue
                        out, meta = await self.download_and_process_file(session, res["url"])
                        if out:
                            results.append([out,res["url"],meta])
                except Exception as e:
                    logger.info(f"Error in processing the file {article_id}") 
        return results

    async def download_and_process_file(self, session, url):
        async with session.get(url) as resp:
            content_type = resp.headers.get("Content-Type")
            content_disp = resp.headers.get("Content-Disposition")

            filename = "downloaded_file"

            if content_disp:
                match = re.search(r'filename\*=UTF-8\'\'(.+)', content_disp)
                if match:
                    filename = unquote(match.group(1))
                else:
                    match = re.search(r'filename="([^"]+)"', content_disp)
                    if match:
                        filename = match.group(1)
                    else:
                        match = re.search(r'filename=([^;\s]+)', content_disp)
                        if match:
                            filename = match.group(1).strip('"')

            if not os.path.splitext(filename)[1] and content_type:
                extensions = {
                    'application/pdf': '.pdf',
                    'image/jpeg': '.jpg',
                    'image/png': '.png',
                    'text/html': '.html',
                    'application/json': '.json',
                    'text/plain': '.txt',
                    'application/zip': '.zip',
                }
                ext = extensions.get(content_type.split(';')[0].strip())
                if ext:
                    filename += ext

            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

            print("Downloading:", filename)

            with open(filename, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    f.write(chunk)      

            if filename.lower().endswith(IMAGE_EXTENSIONS): # complete file processing
                try:
                    image_base64 = image_to_base64(filename)
                    Hashing.image_hash(filename)
                    description_for_image = await self.openai_client.get_description(image_base64)
                    return description_for_image, {"image_hash": {str(Hashing.image_hash(filename)):description_for_image},"type": filename.split(".")[-1]} 
                except Exception as e:
                    logger.exception(f"Error in image description extarction {e}")
                    raise RuntimeError(f"Error in image description extarction {e}")
                finally:
                    self.file_manager.remove_file(filename)

            elif filename.lower().endswith((".pcm",".wav",".aiff",".mp3",".aac",".oga",".wma",".flac",".alac")):
                try:
                    pcm_to_wav = self.file_manager.create_temp_file("wav")
                    AudioConversion.normalize_audio(filename,pcm_to_wav)
                    return await self.audio_processor.asr_pipeline_conversion(pcm_to_wav),{"type":filename.split(".")[-1]}
                except Exception as e:
                    logger.exception(f"Error in download and process function {e}")
                finally:
                    self.file_manager.remove_file(filename)
                    self.file_manager.remove_file(pcm_to_wav)

            elif filename.lower().endswith((".pdf",".ppt",".doc",".docx",".odf",".pages",".key",".pptx")):
                try:
                    # ============= PPTX processing ==============
                    if filename.lower().endswith(".ppt"): # processing for ppt
                        try:
                            ppt_to_pptx = self.file_manager.create_temp_file("pptx")
                            PPTXConvertor.convert_to_pptx(filename,ppt_to_pptx)
                            temp_result = await self.pdf_pptx_processor.process_document(ppt_to_pptx)
                            temp_meta = temp_result["image_hash"]
                            temp_meta["type"] = filename.split(".")[-1]
                            return temp_result["markdown"],temp_meta
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e}")
                        finally:
                            self.file_manager.remove_file(filename)
                            self.file_manager.remove_file(ppt_to_pptx)
                    elif filename.lower().endswith(".key"): 
                        try:
                            key_to_pptx = self.file_manager.create_temp_file("pptx")
                            PPTXConvertor.convert_to_pptx(filename,key_to_pptx)
                            temp_result = await self.pdf_pptx_processor.process_document(key_to_pptx)
                            temp_meta = temp_result["image_hash"]
                            temp_meta["type"] = filename.split(".")[-1]
                            return temp_result["markdown"],temp_meta
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e}")
                        finally:
                            self.file_manager.remove_file(filename)
                            self.file_manager.remove_file(key_to_pptx)
                    # ===================== DOCX ====================
                    elif filename.lower().endswith(".doc"):
                        try:
                            doc_to_pptx = self.file_manager.create_temp_file("docx")
                            DocxConvertor.convert_to_docx(filename,doc_to_pptx)
                            temp_result =  await self.pdf_pptx_processor.process_document(doc_to_pptx)
                            temp_meta = temp_result["image_hash"]
                            temp_meta["type"] = filename.split(".")[-1]
                            return temp_result["markdown"],temp_meta
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e}")
                        finally:
                            self.file_manager.remove_file(filename)
                            self.file_manager.remove_file(doc_to_pptx)
                    elif filename.lower().endswith(".odf"):
                        try:
                            odf_to_pptx = self.file_manager.create_temp_file("docx")
                            DocxConvertor.convert_to_docx(filename,odf_to_pptx)
                            # return self.pdf_pptx_processor.process_document(odf_to_pptx)
                            temp_result = await self.pdf_pptx_processor.process_document(odf_to_pptx)
                            temp_meta = temp_result["image_hash"]
                            temp_meta["type"] = filename.split(".")[-1]
                            return temp_result["markdown"],temp_meta
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e}")
                        finally:
                            self.file_manager.remove_file(filename)
                            self.file_manager.remove_file(odf_to_pptx)
                    elif filename.lower().endswith(".pages"):
                        try:
                            pages_to_pptx = self.file_manager.create_temp_file("docx")
                            DocxConvertor.convert_to_docx(filename,pages_to_pptx)
                            temp_result = await self.pdf_pptx_processor.process_document(pages_to_pptx)
                            temp_meta = temp_result["image_hash"]
                            temp_meta["type"] = filename.split(".")[-1]
                            return temp_result["markdown"],temp_meta
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e}")
                        finally:
                            self.file_manager.remove_file(filename)
                            self.file_manager.remove_file(pages_to_pptx)
                    else:
                        try:
                            temp_result =  await self.pdf_pptx_processor.process_document(filename)
                            temp_meta = temp_result["image_hash"]
                            temp_meta["type"] = filename.split(".")[-1]
                            return temp_result["markdown"],temp_meta
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e}")
                        finally:
                            self.file_manager.remove_file(filename)
                      
                except Exception as e:
                    logger.exception(f"Error in download and process function in doc processing{e}")
                    raise RuntimeError(f"Error in download and process function in doc processing{e}")
                
            elif filename.lower().endswith((".csv",".xls",".xlsx",".numbers")):
                try:
                    # ============= csv processing ==============
                    if filename.lower().endswith(".xls"):
                        try:
                            xls_to_csv= self.file_manager.create_temp_file("csv")
                            CSVConvertor.convert_to_csv(filename,xls_to_csv)
                            return await self.csv_processor.process(xls_to_csv),{"type":filename.split(".")[-1]}
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e}")
                        finally:
                            self.file_manager.remove_file(filename)
                            self.file_manager.remove_file(xls_to_csv)
                    elif filename.lower().endswith(".xlsx"):
                        try:
                            xlsx_to_csv = self.file_manager.create_temp_file("csv")
                            CSVConvertor.convert_to_csv(filename,xlsx_to_csv)
                            return await self.csv_processor.process(xlsx_to_csv),{"type":filename.split(".")[-1]}
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e}")
                        finally:
                            self.file_manager.remove_file(filename)
                            self.file_manager.remove_file(xlsx_to_csv)
                    elif filename.lower().endswith(".numbers"): 
                        try:
                            numbers_to_csv = self.file_manager.create_temp_file("csv")
                            CSVConvertor.convert_to_csv(filename,numbers_to_csv)
                            return await self.csv_processor.process(numbers_to_csv),{"type":filename.split(".")[-1]}
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e}")
                        finally:
                            self.file_manager.remove_file(filename)
                            self.file_manager.remove_file(numbers_to_csv)
                    else:
                        try:
                            return await self.csv_processor.process(filename),{"type":filename.split(".")[-1]}
                        except Exception as e:
                            logger.exception(f"Error in download and process function {e} file name : {filename}")
                        finally:
                            self.file_manager.remove_file(filename)
                except Exception as e:
                    logger.exception(f"Error in download and process function in csv processing{e}")
                    raise RuntimeError(f"Error in download and process function in csv processing{e}")
                
            elif filename.lower().endswith(".pdf"):
                try:
                    temp_result = await self.pdf_pptx_processor.process_document(filename)
                    temp_meta = temp_result["image_hash"]
                    temp_meta["type"] = filename.split(".")[-1]
                    return temp_result["markdown"],temp_meta
                except Exception as e:
                    logger.exception(f"Error in download and process function in pdf processing{e}")
                    raise RuntimeError(f"Error in download and process function in pdf processing{e}")
                finally:
                    self.file_manager.remove_file(filename)
            else:
                raise NotImplementedError(f"Error : {filename} is not processable")
            
if __name__ == "__main__":
    import sys
    sys.path.append("/Users/ezhilrajselvaraj/Ezhil/ever_quint/perkinswill/hub/marketing_toolkit")
    from dotenv import load_dotenv
    load_dotenv()
    obj = FetchData()
    asyncio.run(obj.get_data("63241638417ca879fd2f76d0"))
