
from pathlib import Path

from docling_core.types.doc import DoclingDocument

from docling.datamodel import asr_model_specs
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.document import ConversionResult
from docling.datamodel.pipeline_options import AsrPipelineOptions
from docling.document_converter import AudioFormatOption, DocumentConverter
from docling.pipeline.asr_pipeline import AsrPipeline


class AudioProcess():
    def __init__(self):
        self.converter = self.get_asr_converter()

    def get_asr_converter(self):
        pipeline_options = AsrPipelineOptions()
        pipeline_options.asr_options = asr_model_specs.WHISPER_TURBO
        converter = DocumentConverter(
            format_options={
                InputFormat.AUDIO: AudioFormatOption(
                    pipeline_cls=AsrPipeline,
                    pipeline_options=pipeline_options,
                )
            }
        )
        return converter


    async def asr_pipeline_conversion(self,audio_path: Path) -> DoclingDocument:
        assert audio_path.exists(), f"Test audio file not found: {audio_path}"
        converter = self.get_asr_converter()
        result: ConversionResult = converter.convert(audio_path)
        assert result.status == ConversionStatus.SUCCESS, (
            f"Conversion failed with status: {result.status}"
        )
        return result.document.export_to_markdown()

if __name__ == "__main__":
    obj = AudioProcess()
    # Hello? Hello? Hello? Hello? Hello?
    obj.asr_pipeline_conversion(Path("/Users/ezhilrajselvaraj/Ezhil/ever_quint/perkinswill/hub/marketing_toolkit/backup/test_asr/recording.wav"))
