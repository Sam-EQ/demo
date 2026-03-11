from pathlib import Path

from docling.document_converter import DocumentConverter

class CSVLoader():
    def __init__(self):
        self.converter = DocumentConverter()
    
    async def process(self, path):
        result = self.converter.convert(path)
        output = result.document.export_to_markdown()
        return output
    
if __name__ == "__main__":
    obj = CSVLoader()
    import asyncio
    asyncio.run(obj.process(Path("/Users/ezhilrajselvaraj/Downloads/colors.csv")))