import logging

from src.mongo.data import MongoData
from src.mongo.default import MongoDefault
from src.utils.utils import Utils

logger = logging.getLogger(__name__)

class Pipeline:
    def __init__(self):
        self._mongo_data = MongoData()
        self._mongo_default = MongoDefault()

    async def run(self, pdm_id):
        datas = await self._mongo_data.get_all_active_users(pdm_id)
        for data in datas:
            data = Utils.make_json_safe(data)
            # with open("test.json",'w') as f:
            #     import json
            #     json.dump(Utils.make_json_safe(data),f,indent=4)
            id = data.get("_id")
            layouts = data.get("layouts", {})
            if not layouts:
                logger.warning(f"Layouts for the id : {id} is empty")
                continue
            final_layout_str = layouts.get("finalLayout",None)
            if not final_layout_str:
                logger.warning(f"final layout sting is empty for the id {id}")
                continue
            _final_layout = Utils.final_layout_extractor(final_layout_str)
            final_layout_values = data.get("values",None)
            if not final_layout_values:
                logger.warning(f"final layout values sting is empty for the id {id}")
                continue
            split_chunk = Utils.splitter(final_layout_values)
            for chunk in split_chunk:
                pass

