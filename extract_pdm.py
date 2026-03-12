import asyncio
import json
import os
import re
import requests

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MONGO_DATA_URL = os.getenv("MONGO_DATA_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HUB_CLIENT_ID = os.getenv("HUB_CLIENT_ID")
HUB_CLIENT_SECRET = os.getenv("HUB_CLIENT_SECRET")

IMAGE_PATTERN = r"https://files\.hub\.perkinswill\.com/download/[A-Za-z0-9]+"

openai_client = OpenAI(api_key=OPENAI_API_KEY)

COLLECTION = "64c0ab8f0339a238341b61b8"


class PerkinsAuth:

    def __init__(self, client_id, client_secret):

        self.base_url = "https://api.hub.perkinswill.com"
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None

    def get_token(self):

        url = f"{self.base_url}/oauth/token"

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }

        headers = {
            "Content-Type": "application/json"
        }

        r = requests.post(url, json=payload, headers=headers)

        r.raise_for_status()

        data = r.json()

        value = data.get("value")

        if isinstance(value, str):
            self.token = value
        elif isinstance(value, dict):
            self.token = value.get("access_token")

        return self.token


def extract_images(text):

    if not text:
        return []

    matches = re.findall(IMAGE_PATTERN, text)

    return list(set(matches))


def describe_image(image_bytes, page_text):

    prompt = f"""
You are analyzing an image from the Perkins&Will Project Delivery Manual.

Page context:
{page_text}

Describe the image clearly so someone can understand it without seeing it.
Focus on UI elements, diagrams, buttons, and labels.
"""

    response = openai_client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image": image_bytes}
                ]
            }
        ]
    )

    return response.output_text


async def extract():

    print("Connecting to Mongo...")

    mongo = AsyncIOMotorClient(MONGO_DATA_URL)

    db = mongo["hub365-data"]

    cursor = db[COLLECTION].find({"isDeleted": False})

    auth = PerkinsAuth(HUB_CLIENT_ID, HUB_CLIENT_SECRET)

    token = auth.get_token()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    articles = []

    article_count = 0
    total_images = 0

    async for doc in cursor:

        article_count += 1

        print("\nProcessing article:", article_count)

        text = doc.get("values") or ""

        image_urls = extract_images(text)

        print("Images found:", len(image_urls))

        enriched_text = text

        for url in image_urls:

            try:

                print("Downloading image:", url)

                r = requests.get(url, headers=headers)

                if r.status_code != 200:

                    print("Failed download:", r.text)
                    continue

                image_bytes = r.content

                print("Calling VLM...")

                description = describe_image(image_bytes, text)

                enriched_text += f"\n\nIMAGE DESCRIPTION:\n{description}\n"

                total_images += 1

            except Exception as e:

                print("Image processing failed:", e)

        article = {
            "id": str(doc["_id"]),
            "title": doc.get("name"),
            "parentId": str(doc["parentId"]) if doc.get("parentId") else None,
            "sortOrder": doc.get("sortOrder"),
            "countries": doc.get("countries"),
            "content": enriched_text
        }

        articles.append(article)

    with open("pdm_articles.json", "w") as f:

        json.dump(articles, f, indent=2)

    print("\nExtraction complete")
    print("Articles:", len(articles))
    print("Images processed:", total_images)


if __name__ == "__main__":
    asyncio.run(extract())