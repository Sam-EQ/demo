import argparse
import asyncio
import json
import logging
import os
from src.process.palette_app import Palette
from src.db_connections.db import MongoService

# Optional: Setup logging to see errors if lookups fail
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Write output_index.json / output.json only for debugging (set DEBUG_WRITE_INDEX=1)
DEBUG_WRITE_INDEX = os.getenv("DEBUG_WRITE_INDEX", "").strip().lower() in ("1", "true", "yes")

async def main(debug_dump: bool = False):
    # 1. Initialize the Singleton MongoService (reads MONGO_DATA_URI, MONGO_DEFAULT_URI from config)
    MongoService()
    
    # 2. Initialize the Palette Application
    app = Palette()

    logger.info("Starting data aggregation...")
    
    # 3. Run the aggregation (all in memory)
    result, pdf_chunks, index_docs = await app.get_single_full_record()

    # 4. Index-ready list: palette docs + PDF chunk docs (all in memory)
    all_index_docs = index_docs + pdf_chunks
    logger.info("Index docs in memory: %d total (%d palette + %d PDF chunks)", len(all_index_docs), len(index_docs), len(pdf_chunks))

    # Next steps (in-memory): optionally run_pdf_parser_to_index.process_pdfs_into_chunks(all_index_docs),
    # then opensearch.bulk_upsert.bulk_upsert_index_docs(all_index_docs, add_embeddings=True). No file I/O.

    # 5. Optional debug: write files for inspection (output_index.json is for debugging only)
    if debug_dump:
        out_path = "output.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str, ensure_ascii=False)
        logger.info("Debug: written %d records to %s", len(result), out_path)
        index_path = "output_index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(all_index_docs, f, indent=2, default=str, ensure_ascii=False)
        logger.info("Debug: written %d index docs to %s", len(all_index_docs), index_path)

    return result, all_index_docs

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run palette aggregation (in-memory). Use --debug-dump to write output.json and output_index.json.")
    parser.add_argument("--debug-dump", action="store_true", help="Write output.json and output_index.json for debugging")
    args = parser.parse_args()
    debug = args.debug_dump or os.getenv("DEBUG_WRITE_INDEX", "").strip().lower() in ("1", "true", "yes")
    try:
        asyncio.run(main(debug_dump=debug))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Application failed: {e}")