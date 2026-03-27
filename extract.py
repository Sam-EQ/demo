import argparse
import asyncio
import base64
import html
import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import requests
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
import config as cfg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("extract")

OUTPUT_FILE = "extracted.json"


def _oid(v: Any) -> Optional[ObjectId]:
    try:
        return ObjectId(str(v))
    except Exception:
        return None


class DB:
    def __init__(self):
        self.data    = AsyncIOMotorClient(cfg.MONGO_DATA_URI, maxPoolSize=20)[cfg.DATA_DB]
        self.default = AsyncIOMotorClient(cfg.MONGO_DEFAULT_URI, maxPoolSize=5)[cfg.DEFAULT_DB]

    async def all(self, coll: str, query: Dict = None) -> List[Dict]:
        if not coll:
            return []
        q = {"isDeleted": False, **(query or {})}
        return await self.data[coll].find(q).to_list(None)

    async def by_ids(self, coll: str, ids: List) -> List[Dict]:
        if not coll or not ids:
            return []
        oids = [o for o in (_oid(i) for i in ids) if o]
        if not oids:
            return []
        return await self.data[coll].find({"_id": {"$in": oids}, "isDeleted": False}).to_list(None)

    async def user(self, uid: Any) -> Optional[Dict]:
        oid = _oid(uid)
        if not oid:
            return None
        doc = await self.default["users"].find_one({"_id": oid})
        if not doc:
            return None
        n = doc.get("name", {})
        return {
            "name":  f"{n.get('first','')} {n.get('last','')}".strip() or "Unknown",
            "email": doc.get("email"),
        }

    async def bookmark_counts(self) -> Dict[str, int]:
        for field in ("microknowledgeId", "microknowldgeId"):
            try:
                pipeline = [
                    {"$match": {"isDeleted": False}},
                    {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
                ]
                rows = await self.data[cfg.MKBOOKMARK].aggregate(pipeline).to_list(None)
                if rows:
                    return {str(r["_id"]): r["count"] for r in rows if r.get("_id")}
            except Exception:
                pass
        return {}

def _get_hub_token() -> str:
    if not cfg.HUB_CLIENT_ID or not cfg.HUB_CLIENT_SECRET:
        return ""
    try:
        r = requests.post(
            "https://api.hub.perkinswill.com/oauth/token",
            json={"client_id": cfg.HUB_CLIENT_ID, "grant_type": "client_credentials",
                  "client_secret": cfg.HUB_CLIENT_SECRET},
            timeout=15,
        )
        r.raise_for_status()
        val = r.json().get("value")
        return val if isinstance(val, str) else (val or {}).get("access_token", "")
    except Exception as e:
        log.warning("Hub token fetch failed: %s", e)
        return ""


def _hub_headers() -> Dict[str, str]:
    token = _get_hub_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    if cfg.HUB_AUTH_COOKIE:
        c = cfg.HUB_AUTH_COOKIE.strip()
        return {"Cookie": c if "=" in c else f"authentication={c}"}
    return {}

def _strip_tags(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style[^>]*>[\s\S]*?</style>",  " ", s, flags=re.I)
    s = re.sub(r"</(p|div|li|h\d)\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n", "\n", s)).strip()


def _first_image(html_str: str) -> Tuple[Optional[str], Optional[str]]:
    if not html_str:
        return None, None
    base = cfg.HUB_FILE_DOWNLOAD_URL + "/"
    for tag in re.finditer(r"<img\s[^>]*>", html_str, re.I):
        m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', tag.group(0), re.I)
        if not m:
            continue
        src = m.group(1).strip()
        if src.startswith("data:") and "base64," in src:
            return None, src.split("base64,", 1)[1]
        url = src if src.startswith("http") else base + src
        return url, None
    return None, None


async def _fetch_b64(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                return base64.b64encode(await r.read()).decode()
    except Exception:
        pass
    return None

def _person(p: Dict) -> Optional[Dict]:
    if not p:
        return None
    n = p.get("name", {})
    if isinstance(n, dict):
        name = " ".join(filter(None, [n.get("first"), n.get("middle"), n.get("last")])).strip()
    else:
        name = str(n or "")
    addr  = p.get("address") or {}
    title = p.get("title") or {}
    return {
        "_id":          str(p["_id"]) if p.get("_id") else None,
        "name":         name,
        "primaryEmail": p.get("primaryEmail"),
        "job":          title.get("job") if isinstance(title, dict) else None,
        "city":         addr.get("city")    if isinstance(addr, dict) else None,
        "country":      addr.get("country") if isinstance(addr, dict) else None,
    }


async def _resolve_credits(db: DB, ids: List) -> List[Dict]:
    rows = await db.by_ids(cfg.CREDITS, ids)
    return [{"creditId": str(c["_id"]), "name": c.get("CreditName") or c.get("creditName"),
             "points": c.get("creditPoints"), "certification": c.get("Certification") or c.get("certification"),
             "ratingSystem": c.get("ratingSystem"), "version": c.get("version")} for c in rows]


async def _resolve_projects(db: DB, ids: List) -> List[Dict]:
    rows = await db.by_ids(cfg.PROJECTS, ids)
    result = []
    for p in rows:
        stage = p.get("stage")
        if isinstance(stage, dict):
            stage = stage.get("stage")
        result.append({"_id": str(p["_id"]), "name": p.get("name"), "stage": stage,
                        "type": p.get("type") or [], "services": p.get("services") or [],
                        "status": p.get("status")})
    return result


async def _resolve_palette_projects(db: DB, mk_id: str) -> List[Dict]:
    rows = await db.all(cfg.PALETTEPROJECTS, {"paletteCardIds": ObjectId(mk_id)})
    return [{"_id": str(d["_id"]),
             "projectId": str(d["projectId"]) if d.get("projectId") else None,
             "projectName": (d.get("foreign") or {}).get("projectName")} for d in rows]


async def _resolve_team(db: DB, team_ids: List) -> List[Dict]:
    person_ids = [t.get("personId") for t in team_ids if t.get("personId")]
    people     = await db.by_ids(cfg.PEOPLE, person_ids)
    by_id      = {str(p["_id"]): _person(p) for p in people}
    return [{"_id": str(t.get("_id")), "isExpert": t.get("isExpert", False),
             "person": by_id.get(str(t.get("personId")))} for t in team_ids]


async def _resolve_related_mk(db: DB, ids: List) -> List[Dict]:
    rows = await db.by_ids(cfg.MICROKNOWLEDGE, ids)
    return [{"id": str(m["_id"]), "name": m.get("name"),
             "shortDescription": m.get("shortDescription")} for m in rows]


async def _resolve_creator_updater(db: DB, creator_id, updater_id) -> Dict:
    creator, updater = await asyncio.gather(db.user(creator_id), db.user(updater_id))
    return {
        "creator_name":  creator.get("name")  if creator else None,
        "creator_email": creator.get("email") if creator else None,
        "updator_name":  updater.get("name")  if updater else None,
        "updator_email": updater.get("email") if updater else None,
    }


async def _resolve_palette_mk(db: DB, mk_id: str) -> List[Dict]:
    links = await db.all(cfg.PALETTE_MICROKNOWLEDGE, {"paletteId": ObjectId(mk_id)})
    if not links:
        return []
    mk_card_ids = [l.get("mkId") for l in links if l.get("mkId")]
    cards       = await db.by_ids(cfg.MKCARDS, mk_card_ids)
    base        = cfg.HUB_CARD_BASE_URL + "/"
    cards_by_id = {}
    for c in cards:
        fid = c.get("cardFileId")
        cards_by_id[str(c["_id"])] = {
            "_id": str(c["_id"]), "category": c.get("category"),
            "title": c.get("title"), "cardFileId": str(fid) if fid else None,
            "cardURL": base + str(fid) if fid else None,
        }
    return [{"_id": str(l["_id"]), "mkId": str(l["mkId"]) if l.get("mkId") else None,
             "card": cards_by_id.get(str(l["mkId"])),
             "paletteId": str(l["paletteId"]) if l.get("paletteId") else None} for l in links]


async def _resolve_comments(db: DB, mk_id: str) -> List[Dict]:
    rows = await db.all(cfg.PALETTECOMMENTS, {"paletteId": ObjectId(mk_id)})
    if not rows:
        return []
    people = await db.by_ids(cfg.PEOPLE, [r.get("creatorId") for r in rows if r.get("creatorId")])
    by_id  = {str(p["_id"]): _person(p) for p in people}
    return [{"_id": str(c["_id"]), "comment": c.get("comment"),
             "creator": by_id.get(str(c.get("creatorId")))} for c in rows]


async def _resolve_resources(db: DB, mk_id: str) -> Tuple[List[Dict], List[Dict]]:
    files = await db.all(cfg.MICROFILES, {"paletteId": ObjectId(mk_id)})
    if not files:
        return [], []

    resources, pdf_candidates = [], []
    for f in files:
        fid  = str(f["fileId"]) if f.get("fileId") else None
        link = f.get("link") or ""
        ext  = (f.get("extension") or "").lstrip(".").lower()

        if ext == "pdf" or (isinstance(link, str) and ".pdf" in link.lower()):
            ft = "pdf"
        elif f.get("fileFrom", "").lower() == "video" or any(
            x in (link or "") for x in ("vimeo", "youtube", "youtu.be")
        ) or ext in ("mp4", "mov", "webm", "avi"):
            ft = "video"
        else:
            ft = "other"

        resources.append({
            "_id":        str(f["_id"]),
            "fileType":   ft,
            "fileId":     fid,
            "link":       link if isinstance(link, str) else None,
            "recordType": f.get("recordType"),
            "title":      f.get("title") or f.get("name") or "",
        })
        if ft == "pdf":
            pdf_candidates.append({
                "_id":      str(f["_id"]),
                "paletteId": mk_id,
                "fileId":   fid,
                "pdf_url":  link if not fid and isinstance(link, str) else None,
                "title":    f.get("title") or f.get("name") or "",
            })
        elif fid:
            pdf_candidates.append({
                "_id":      str(f["_id"]),
                "paletteId": mk_id,
                "fileId":   fid,
                "pdf_url":  None,
                "title":    f.get("title") or f.get("name") or "",
            })

    return resources, pdf_candidates


async def _resolve_practices(db: DB, ids: List) -> List[str]:
    rows = await db.by_ids(cfg.PRACTICE, ids)
    return [r["name"] for r in rows if r.get("name")]


async def _resolve_splashscreen(db: DB) -> List[Dict]:
    rows = await db.all(cfg.SPLASHSCREEN)
    return [{"_id": str(r["_id"]), "title": r.get("title"), "content": r.get("content"),
             "imageUrl": r.get("imageUrl")} for r in rows]

async def _describe_image(b64: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=cfg.OPENAI_KEY)
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o", temperature=0, max_tokens=80,
            messages=[{"role": "system", "content": "Describe images in one short sentence for search."},
                      {"role": "user", "content": [
                          {"type": "text", "text": "Describe this image in one sentence (under 25 words)."},
                          {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                      ]}],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        log.debug("Image describe failed: %s", e)
        return ""

async def _enrich_card(
    doc: Dict,
    db: DB,
    bookmark_counts: Dict[str, int],
    hub_auth: Dict,
    sem: asyncio.Semaphore,
    session: aiohttp.ClientSession,
) -> Tuple[Dict, List[Dict]]:
    async with sem:
        mk_id = str(doc["_id"])

        # Run all DB lookups in parallel
        (credits, projects, palette_projects, team, related_mk,
         creator_info, palette_mk, comments, (resources, pdf_candidates), practices) = await asyncio.gather(
            _resolve_credits(db, doc.get("creditIds") or []),
            _resolve_projects(db, doc.get("projectIds") or []),
            _resolve_palette_projects(db, mk_id),
            _resolve_team(db, doc.get("teamIds") or []),
            _resolve_related_mk(db, doc.get("mk40Ids") or []),
            _resolve_creator_updater(db, doc.get("creatorId"), doc.get("updatedById") or doc.get("updaterId")),
            _resolve_palette_mk(db, mk_id),
            _resolve_comments(db, mk_id),
            _resolve_resources(db, mk_id),
            _resolve_practices(db, doc.get("practiceIds") or []),
        )

        summary_html = doc.get("summary") or ""
        summary_text = _strip_tags(re.sub(r"<img[^>]*>", "", summary_html, flags=re.I))
        img_url, img_b64 = _first_image(summary_html)

        image_description = ""
        if img_b64:
            image_description = await _describe_image(img_b64)
        elif img_url:
            b64 = await _fetch_b64(session, img_url)
            if b64:
                image_description = await _describe_image(b64)

        record = {
            "id":                    mk_id,
            "name":                  doc.get("name"),
            "shortDescription":      doc.get("shortDescription"),
            "keywords":              doc.get("keywords") or [],
            "stages":                doc.get("stages") or [],
            "card_type":             doc.get("cardType"),
            "status":                doc.get("status"),
            "isPinToTop":            doc.get("isPinToTop", False),
            "livingDesignPetals":    doc.get("livingDesignPetals") or [],
            "certificationCategory": doc.get("certificationCategory"),
            "certificationType":     doc.get("certificationType"),
            "expertEffortTime":      doc.get("expertEffortTime"),
            "staffEffortTime":       doc.get("staffEffortTime"),
            "softwaresUsed":         doc.get("softwaresUsed") or [],
            "features":              doc.get("features") or [],
            "appURL":                doc.get("appURL"),
            "publishDate":           str(doc["publishDate"]) if doc.get("publishDate") else None,
            "reviewDate":            str(doc["reviewDate"])  if doc.get("reviewDate")  else None,
            "createdAt":             str(doc["createdAt"])   if doc.get("createdAt")   else None,
            "updatedAt":             str(doc["updatedAt"])   if doc.get("updatedAt")   else None,
            "practices":             practices,
            "credits":               credits,
            "projects":              projects,
            "palette_projects":      palette_projects,
            "team":                  team,
            "related_cards":         related_mk,
            "palette_mk_links":      palette_mk,
            "comments":              comments,
            "resources":             resources,
            **creator_info,
            "summary": {
                "text":              summary_text,
                "image_url":         img_url,
                "image_description": image_description,
            },
            "bookmark_count": bookmark_counts.get(mk_id, 0),
        }
        return record, pdf_candidates

async def run(output_path: str, limit: Optional[int]):
    db          = DB()
    hub_auth    = _hub_headers()
    bookmarks   = await db.bookmark_counts()
    splashscreen = await _resolve_splashscreen(db)

    all_cards = await db.all(cfg.MICROKNOWLEDGE)
    if limit:
        all_cards = all_cards[:limit]
    total = len(all_cards)
    log.info("Extracting %d cards ...", total)

    sem = asyncio.Semaphore(cfg.CARD_CONCURRENCY)
    all_records: List[Dict] = []
    all_pdf_candidates: List[Dict] = []

    async with aiohttp.ClientSession() as session:
        tasks = [
            _enrich_card(doc, db, bookmarks, hub_auth, sem, session)
            for doc in all_cards
        ]
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            try:
                record, pdfs = await coro
                all_records.append(record)
                all_pdf_candidates.extend(pdfs)
                if i % 20 == 0 or i == total:
                    log.info("  Enriched %d / %d", i, total)
            except Exception as exc:
                log.error("Card enrichment failed (idx %d): %s", i, exc)

    output = {
        "cards":          all_records,
        "pdf_candidates": all_pdf_candidates,
        "splashscreen":   splashscreen,
        "total_cards":    len(all_records),
        "total_pdfs":     len(all_pdf_candidates),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    log.info("✓ Saved %d cards + %d PDF candidates → %s",
             len(all_records), len(all_pdf_candidates), output_path)


def main():
    ap = argparse.ArgumentParser(description="Extract all Palette data from MongoDB")
    ap.add_argument("--output", default=OUTPUT_FILE,  help=f"Output JSON file (default: {OUTPUT_FILE})")
    ap.add_argument("--limit",  type=int, default=None, help="Limit number of cards (for testing)")
    args = ap.parse_args()
    asyncio.run(run(args.output, args.limit))


if __name__ == "__main__":
    main()