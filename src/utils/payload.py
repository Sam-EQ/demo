FILE_PAYLOAD = {
    "model": "files",
    "type": "query",
    "query": "Files",
    "arguments": {
        "page": 0,
        "size": 1000,
        "sort": [
            "createdAt:desc"
        ],
        "query": {
            "bool": {
                "must": [
                    {
                        "query_string": {
                            "query": "**",
                            "fields": [
                                "title"
                            ]
                        }
                    },
                    {
                        "match": {
                            "customFields.pdmApp": "64c0ab7a8234db562d08bfe5"
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
    },
    "resolve": {
        "creator": True,
        "_id": True,
        "extension": True,
        "name": True,
        "size": True,
        "title": True,
        "type": True,
        "url": True,
        "createdAt": True
    }
}