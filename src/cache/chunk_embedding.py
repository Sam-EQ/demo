import lmdb
import pickle
import numpy as np

class LMDBEmbeddingCache:
    def __init__(self, path="embedding_cache", map_size=10 * 1024 * 1024 * 1024): 
        self.env = lmdb.open(path,
            map_size=map_size,  # 10GB default value
            subdir=True,
            lock=True
        )

    def get(self, key: str):
        with self.env.begin() as txn:
            value = txn.get(key.encode())
            if value:
                return pickle.loads(value)
        return None

    def set(self, key: str, embedding):
        with self.env.begin(write=True) as txn:
            txn.put(key.encode(), pickle.dumps(embedding))
