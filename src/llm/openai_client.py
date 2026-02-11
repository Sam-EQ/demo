import asyncio
from openai import AsyncOpenAI
import pandas as pd
import logging

from dotenv import load_dotenv
load_dotenv() 

logger = logging.getLogger(__name__)

from src.config import OPENAI_API_KEY

class OpenAIClient:
    def __init__(self):
        try:
            self._client =  AsyncOpenAI(api_key=OPENAI_API_KEY)
        except Exception as e:
            logger.exception(f"Error in connecting with open AI for getting user data: {e}")
            raise ConnectionError(f"Error in connecting with open AI for getting user data: {e}")
        
    async def get_embedding(self,text, model="text-embedding-3-large"):
        try:
            text = text.replace("\n", " ")
            response = await self._client.embeddings.create(
                input=[text],
                model=model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.exception(f"Error in generating embedding : {e}")
            raise RuntimeError(f"Error in generating embedding : {e}")
    
    async def get_description(self,image_base64):
        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe the meaning of this image and clearly explain the message it is trying to convey."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.exception(f"Error in the getting image description part {e}")
            raise RuntimeError("Error in the getting image description part {e}")