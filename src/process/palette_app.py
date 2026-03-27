import asyncio
import base64
import logging
import re
import html
from bson import ObjectId
import aiohttp
from src.db_connections.db import MongoService
from src.config import *
from src.llm_models.openai_llms import OpenAIClient
from src.process.pdf_chunks import build_pdf_chunks
from src.process.output_index_transform import transform_output_to_index

async def _null(): return None


def _strip_img_from_html(html_str):
    """Remove <img> tags from HTML so summary has no image URLs."""
    if not html_str or not isinstance(html_str, str):
        return html_str
    return re.sub(r"<img[^>]*>", "", html_str, flags=re.IGNORECASE)


def _extract_first_image_url_and_alt(html_str):
    """Extract first img: (url, alt, base64). For data: src return (None, alt, base64); for http/id return (url, alt, None)."""
    if not html_str or not isinstance(html_str, str):
        return None, None, None
    base = (HUB_FILE_BASE_URL or "https://hub.perkinswill.com/files/").rstrip("/") + "/"
    for tag in re.finditer(r"<img\s[^>]*>", html_str, re.IGNORECASE):
        tag_str = tag.group(0)
        src_m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', tag_str, re.IGNORECASE)
        alt_m = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', tag_str, re.IGNORECASE)
        src = src_m.group(1).strip() if src_m else ""
        alt = html.unescape((alt_m.group(1) or "").strip()) if alt_m else ""
        if not src:
            continue
        if src.startswith("data:"):
            # e.g. data:image/png;base64,<payload>
            if "base64," in src:
                b64 = src.split("base64,", 1)[1].strip()
                if b64:
                    return None, (alt[:120] + ("..." if len(alt) > 120 else "")) if alt else "Summary image", b64
            continue
        url = src if src.startswith(("http://", "https://")) else (base + src)
        desc = (alt[:120] + ("..." if len(alt) > 120 else "")) if alt else "Summary image"
        return url, desc, None
    return None, None, None


def _html_to_clean_text(html_str):
    """Parse HTML and return clean plain text (strip tags, decode entities, normalize whitespace)."""
    if not html_str or not isinstance(html_str, str):
        return None
    # Remove script and style elements and their content
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html_str, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    # Replace block-level tags with newline so we get paragraph breaks
    text = re.sub(r"</(p|div|li|tr|h[1-6])\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode HTML entities
    text = html.unescape(text)
    # Normalize whitespace: collapse runs, strip
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    return text.strip() or None


def _summary_and_text(raw_summary):
    """Return (summary_html_without_images, summary_text_dict with text, image_url, image_alt, image_base64). image_description set later via OpenAI."""
    if not raw_summary or not isinstance(raw_summary, str):
        return None, {"text": None, "image_url": None, "image_alt": None, "image_base64": None}
    summary_no_img = _strip_img_from_html(raw_summary)
    image_url, image_alt, image_base64 = _extract_first_image_url_and_alt(raw_summary)
    text = _html_to_clean_text(summary_no_img)
    return summary_no_img, {"text": text, "image_url": image_url, "image_alt": image_alt, "image_base64": image_base64}


async def _fetch_image_base64(url):
    """Fetch image from URL and return base64 string, or None on failure."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
                return base64.b64encode(data).decode("ascii") if data else None
    except Exception:
        return None


def _shape_person_from_people(p):
    """From a PEOPLE doc: _id, name, primaryEmail, job, city, country, avatarId."""
    if not p:
        return None
    name = p.get("name")
    if isinstance(name, dict):
        first = name.get("first") or name.get("firstName") or ""
        middle = name.get("middle") or ""
        last = name.get("last") or name.get("lastName") or ""
        name_str = " ".join(x for x in [first, middle, last] if x).strip() or None
    else:
        name_str = name
    title = p.get("title") or {}
    address = p.get("address") or {}
    return {
        "_id": str(p.get("_id")) if p.get("_id") is not None else None,
        "name": name_str,
        "primaryEmail": p.get("primaryEmail"),
        "job": title.get("job") if isinstance(title, dict) else None,
        "city": address.get("city") if isinstance(address, dict) else None,
        "country": address.get("country") if isinstance(address, dict) else None,
        "avatarId": str(p.get("avatarId")) if p.get("avatarId") is not None else p.get("avatarId"),
    }


class Palette:
    def __init__(self):
        self.db = MongoService()

    async def get_single_full_record(self):
        raw_data = await self.db.get_all_records(MICROKNOWLEDGE)
        final_output = []
        all_pdf_resources = []
        total = len(raw_data)
        for i, doc in enumerate(raw_data):
            mk_id = str(doc.get("_id"))
            if (i + 1) % 50 == 0 or i == 0 or i == total - 1:
                logging.getLogger(__name__).info("Processing record %d / %d (id=%s)", i + 1, total, mk_id)
            tasks = [
                self._resolve_credit_details(doc.get("creditIds", [])),
                self._resolve_project_details(doc.get("projectIds", [])),
                self._resolve_palette_project_details(mk_id),
                self._resolve_team_details(doc.get("teamIds", [])),
                self._resolve_related_mk(doc.get("mk40Ids", [])),
                self._resolve_creator_updater(doc.get("creatorId"), doc.get("updatedById") or doc.get("updaterId")),
                self._resolve_palette_microknowledge_details(mk_id),
                self._resolve_palette_comments(mk_id),
                self._resolve_resources(mk_id),
                self._resolve_practice_details(doc.get("practiceIds", [])),
            ]
            (credit_details, project_details, palette_project_details, team_details, related_mk_details,
             creator_updater, palette_microknowledge_details, palette_comments, resources_and_pdf,
             practice_details) = await asyncio.gather(*tasks)
            resources, pdf_resources = resources_and_pdf
            all_pdf_resources.extend(pdf_resources)

            summary_html, summary_text_obj = _summary_and_text(doc.get("summary"))
            image_alt = summary_text_obj.get("image_alt")
            image_base64 = summary_text_obj.get("image_base64")
            image_url = summary_text_obj.get("image_url")
            image_description = image_alt
            if image_base64:
                try:
                    image_description = await OpenAIClient().get_description(image_base64)
                except Exception:
                    image_description = image_alt or "Summary image"
            elif image_url:
                b64 = await _fetch_image_base64(image_url)
                if b64:
                    try:
                        image_description = await OpenAIClient().get_description(b64)
                    except Exception:
                        pass
                if not image_description:
                    image_description = image_alt or "Summary image"
            summary_text_obj["image_description"] = image_description
            summary_text_obj.pop("image_alt", None)
            summary_text_obj.pop("image_base64", None)
            final_output.append({
                "id": mk_id,
                "name": doc.get("name"),
                "shortDescription": doc.get("shortDescription"),
                "keywords": doc.get("keywords"),
                "stages": doc.get("stages"),
                "card_type": doc.get("cardType"),
                "livingDesignPetals": doc.get("livingDesignPetals"),
                "status": doc.get("status"),
                "summary_text": summary_text_obj,
                "certificationCategory": doc.get("certificationCategory"),
                "certificationType": doc.get("certificationType"),
                "credit_details": credit_details,
                "expertEffortTime": doc.get("expertEffortTime"),
                "staffEffortTime": doc.get("staffEffortTime"),
                "softwaresUsed": doc.get("softwaresUsed"),
                "team_details": team_details,
                "publishDate": doc.get("publishDate"),
                "reviewDate": doc.get("reviewDate"),
                "project_details": project_details,
                "palette_project_details": palette_project_details,
                "createdAt": doc.get("createdAt"),
                "updatedAt": doc.get("updatedAt"),
                "creator_name": creator_updater.get("creator_name"),
                "creator_email": creator_updater.get("creator_email"),
                "updator_name": creator_updater.get("updator_name"),
                "updator_email": creator_updater.get("updator_email"),
                "related_mk_details": related_mk_details,
                "palette_microknowledge_details": palette_microknowledge_details,
                "palette_comments": palette_comments,
                "resources": resources,
                "isPinToTop": doc.get("isPinToTop"),
                "practices": practice_details,
                "features": doc.get("features"),
                "appURL": doc.get("appURL"),
            })
        # PDF resources: extract text, chunk, build chunk documents (Hub auth via HUB_CLIENT_ID/SECRET or HUB_AUTH_COOKIE)
        pdf_chunks = []
        if all_pdf_resources:
            download_base = HUB_FILE_DOWNLOAD_URL or "https://files.hub.perkinswill.com/download"
            logging.getLogger("src.process.palette_app").info("Building PDF chunks for %d resources (Hub download + chunk)...", len(all_pdf_resources))
            pdf_chunks = await build_pdf_chunks(all_pdf_resources, download_base)
            logging.getLogger("src.process.palette_app").info("Built %d PDF chunks.", len(pdf_chunks))
        # Index format: _id, title, text (json + markdown), metadata, vector_field []
        index_docs = transform_output_to_index(final_output)
        return final_output, pdf_chunks, index_docs

    async def _resolve_credit_details(self, ids):
        """credit_details: [{ creditId, credit_name, creditPoints, creditCertification, ratingSystem, version }]"""
        if not ids or not CREDITS:
            return []
        data = await self.db.get_many_by_ids(CREDITS, ids)
        return [
            {
                "creditId": str(c.get("_id")) if c.get("_id") is not None else None,
                "credit_name": c.get("CreditName") or c.get("creditName"),
                "creditPoints": c.get("creditPoints"),
                "creditCertification": c.get("Certification") or c.get("certification"),
                "ratingSystem": c.get("ratingSystem"),
                "version": c.get("version") if c.get("version") is not None else " ",
            }
            for c in data
        ]

    async def _resolve_project_details(self, project_ids):
        """project_details: [{ _id, name, stage (from stage.stage), type, services, status }] from PROJECTS."""
        if not project_ids or not PROJECTS:
            return []
        projects_data = await self.db.get_many_by_ids(PROJECTS, project_ids)
        result = []
        for p in projects_data:
            stage_val = p.get("stage")
            if isinstance(stage_val, dict):
                stage_val = stage_val.get("stage")
            result.append({
                "_id": str(p.get("_id")) if p.get("_id") is not None else None,
                "name": p.get("name"),
                "stage": stage_val,
                "type": p.get("type") if isinstance(p.get("type"), list) else (p.get("type") or []),
                "services": p.get("services") if isinstance(p.get("services"), list) else (p.get("services") or []),
                "status": p.get("status"),
            })
        return result

    async def _resolve_practice_details(self, ids):
        """practices: [ name, ... ] from PRACTICE collection."""
        if not ids or not PRACTICE:
            return []
        data = await self.db.get_many_by_ids(PRACTICE, ids)
        return [p.get("name") for p in data if p.get("name") is not None]

    async def _resolve_palette_project_details(self, mk_id):
        """PALETTEPROJECTS: paletteCardIds is connected to _id of MICROKNOWLEDGE. Return [{ _id (PALETTEPROJECTS._id), projectId, ProjectName (from foreign.projectName) }]."""
        if not PALETTEPROJECTS:
            return []
        # paletteCardIds contains the MICROKNOWLEDGE _id
        docs = await self.db.get_all_records(PALETTEPROJECTS, {"paletteCardIds": ObjectId(mk_id)})
        return [
            {
                "_id": str(d.get("_id")) if d.get("_id") is not None else None,
                "projectId": str(d.get("projectId")) if d.get("projectId") is not None else d.get("projectId"),
                "ProjectName": (d.get("foreign") or {}).get("projectName") if isinstance(d.get("foreign"), dict) else None,
            }
            for d in docs
        ]

    async def _resolve_team_details(self, team_ids):
        """team_details: [{ _id, personId (shaped from PEOPLE: _id, name, primaryEmail, job, city, country), isExpert }]"""
        if not team_ids or not PEOPLE:
            return []
        person_ids = [t.get("personId") for t in team_ids if t.get("personId")]
        if not person_ids:
            return []
        people = await self.db.get_many_by_ids(PEOPLE, person_ids)
        by_id = {}
        for p in people:
            oid = p.get("_id")
            if oid is not None:
                by_id[str(oid)] = _shape_person_from_people(p)
        result = []
        for t in team_ids:
            pid = t.get("personId")
            pid_str = str(pid) if pid is not None else None
            person_shaped = by_id.get(pid_str) if pid_str else None
            result.append({
                "_id": str(t.get("_id")) if t.get("_id") is not None else None,
                "personId": person_shaped,
                "isExpert": t.get("isExpert", False),
            })
        return result

    async def _resolve_related_mk(self, ids):
        """related_mk_details: [{ related_mk_Id, related_mk_name, related_mk_summary }]"""
        if not ids or not MICROKNOWLEDGE:
            return []
        data = await self.db.get_many_by_ids(MICROKNOWLEDGE, ids)
        return [
            {
                "related_mk_Id": str(m.get("_id")) if m.get("_id") is not None else None,
                "related_mk_name": m.get("name"),
                "related_mk_summary": _strip_img_from_html(m.get("summary")),
            }
            for m in data
        ]

    async def _resolve_creator_updater(self, creator_id, updater_id):
        c_task = self.db.get_user(creator_id) if creator_id else _null()
        u_task = self.db.get_user(updater_id) if updater_id else _null()
        creator_data, updator_data = await asyncio.gather(c_task, u_task)
        return {
            "creator_name": creator_data.get("name") if creator_data else None,
            "creator_email": creator_data.get("email") if creator_data else None,
            "updator_name": updator_data.get("name") if updator_data else None,
            "updator_email": updator_data.get("email") if updator_data else None,
        }

    async def _resolve_palette_microknowledge_details(self, mk_id):
        """palette_microknowledge_details: mkId is _id of MKCARDS. Each item: _id, mkId, microknowledge_card_details (from MKCARDS: _id, category, title, cardFileId, cardURL), paletteId."""
        if not PALETTE_MICROKNOWLEDGE:
            return []
        links = await self.db.get_all_records(PALETTE_MICROKNOWLEDGE, {"paletteId": ObjectId(mk_id)})
        if not links:
            return []
        mk_ids = [l.get("mkId") for l in links if l.get("mkId")]
        card_details_by_mk = {}
        if mk_ids and MKCARDS:
            # mkId in PALETTE_MICROKNOWLEDGE = _id of MKCARDS
            mkcards = await self.db.get_many_by_ids(MKCARDS, mk_ids)
            base_url = (HUB_CARD_BASE_URL or "https://hub.perkinswill.com/6318ce1dffb963c1c1d3bb1f/").rstrip("/") + "/"
            for mc in mkcards:
                oid = mc.get("_id")
                if oid is not None:
                    cid = str(oid)
                    card_file_id = mc.get("cardFileId")
                    card_url = (base_url + str(card_file_id)) if card_file_id is not None else None
                    card_details_by_mk[cid] = {
                        "_id": cid,
                        "category": mc.get("category"),
                        "title": mc.get("title"),
                        "cardFileId": str(card_file_id) if card_file_id is not None else None,
                        "cardURL": card_url,
                    }
        result = []
        for pm in links:
            pm_mk_id = pm.get("mkId")
            pm_mk_str = str(pm_mk_id) if pm_mk_id is not None else None
            card_details = card_details_by_mk.get(pm_mk_str) if pm_mk_str else None
            result.append({
                "_id": str(pm.get("_id")) if pm.get("_id") is not None else None,
                "mkId": pm_mk_str,
                "microknowledge_card_details": card_details,
                "paletteId": str(pm.get("paletteId")) if pm.get("paletteId") is not None else None,
            })
        return result

    async def _resolve_palette_comments(self, mk_id):
        """PALETTECOMMENTS: paletteId = MICROKNOWLEDGE._id. Return [{ _id, comment, creatorId, creator (PEOPLE-shaped) }]."""
        if not PALETTECOMMENTS:
            return []
        comments = await self.db.get_all_records(PALETTECOMMENTS, {"paletteId": ObjectId(mk_id)})
        if not comments:
            return []
        creator_ids = [c.get("creatorId") for c in comments if c.get("creatorId")]
        creator_map = {}
        if creator_ids and PEOPLE:
            creators = await self.db.get_many_by_ids(PEOPLE, creator_ids)
            for p in creators:
                oid = p.get("_id")
                if oid is not None:
                    creator_map[str(oid)] = _shape_person_from_people(p)
        return [
            {
                "_id": str(c.get("_id")) if c.get("_id") is not None else None,
                "comment": c.get("comment"),
                "creatorId": str(c.get("creatorId")) if c.get("creatorId") is not None else None,
                "creator": creator_map.get(str(c.get("creatorId"))) if c.get("creatorId") is not None else None,
            }
            for c in comments
        ]

    async def _resolve_resources(self, mk_id):
        """MICROFILES: paletteId = MICROKNOWLEDGE._id. Return (resources, pdf_resources). resources = [{ _id, recordType, link, fileType }]. pdf_resources = [{ _id, paletteId, fileId, title }] for PDFs with fileId."""
        if not MICROFILES:
            return [], []
        files = await self.db.get_all_records(MICROFILES, {"paletteId": ObjectId(mk_id)})
        if not files:
            return [], []

        def _file_id(f):
            v = f.get("fileId") or f.get("file_id")
            return str(v) if v is not None else None

        def _file_extension(f):
            ext = f.get("extension")
            if ext:
                return str(ext).lstrip(".").lower() if ext else None
            fn = f.get("fileName") or f.get("filename") or f.get("originalFileName") or f.get("name")
            if fn and isinstance(fn, str) and "." in fn:
                return fn.rsplit(".", 1)[-1].lower()
            return None

        def _file_type(f):
            ext = _file_extension(f)
            link = (f.get("link") or "") if isinstance(f.get("link"), str) else ""
            file_from = (f.get("fileFrom") or "").lower()
            if ext == "pdf":
                return "pdf"
            if file_from == "video":
                return "video"
            if link and ("vimeo" in link or "youtube" in link or "youtu.be" in link):
                return "video"
            if ext in ("mp4", "webm", "mov", "avi", "mkv", "m4v", "wmv"):
                return "video"
            return "others"

        resources = []
        pdf_resources = []
        for f in files:
            ft = _file_type(f)
            rid = str(f.get("_id")) if f.get("_id") is not None else None
            link = (f.get("link") or "") if isinstance(f.get("link"), str) else ""
            fid = _file_id(f)
            resources.append({
                "_id": rid,
                "recordType": f.get("recordType"),
                "link": f.get("link"),
                "fileType": ft,
                "fileId": fid,
            })
            # PDF candidates: (1) fileType pdf with fileId, (2) any resource with fileId (Hub file – try download; skip if not PDF), (3) link URL that points to PDF
            is_pdf_link = link.lower().rstrip("/").endswith(".pdf") or "application/pdf" in (f.get("contentType") or "").lower()
            if ft == "pdf" and fid:
                pdf_resources.append({
                    "_id": rid,
                    "paletteId": str(f.get("paletteId")) if f.get("paletteId") is not None else None,
                    "fileId": fid,
                    "pdf_url": None,
                    "title": f.get("title") or f.get("name") or "",
                })
            elif fid:
                # Hub-hosted file without extension: try as PDF (will skip in chunker if not PDF)
                pdf_resources.append({
                    "_id": rid,
                    "paletteId": str(f.get("paletteId")) if f.get("paletteId") is not None else None,
                    "fileId": fid,
                    "pdf_url": None,
                    "title": f.get("title") or f.get("name") or "",
                })
            elif is_pdf_link and link:
                pdf_resources.append({
                    "_id": rid,
                    "paletteId": str(f.get("paletteId")) if f.get("paletteId") is not None else None,
                    "fileId": None,
                    "pdf_url": link,
                    "title": f.get("title") or f.get("name") or "",
                })
        return resources, pdf_resources