from src.opensearch_cli.opensearch_client import OpenSearchClient

class VerifyChunk:
    def __init__(self):
        self._open_srearch_client = OpenSearchClient()
        self.data = None
    
    # async def reload(self):
    #     self.data = self._open_srearch_client.get_all_data()['']
        
