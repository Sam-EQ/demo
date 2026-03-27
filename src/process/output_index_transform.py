"""
Transform palette output records into index-ready documents:
_id, title, text (markdown with embedded JSON metadata + readable content), metadata, vector_field [].
"""
import json
from typing import Any, Dict, List


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False) if v else ""
    return str(v).strip()


def _metadata_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Build metadata object from palette record (our fields)."""
    summary = record.get("summary_text") or {}
    return {
        "id": record.get("id"),
        "title": record.get("name"),
        "created_at": record.get("createdAt"),
        "updated_at": record.get("updatedAt"),
        "creator_name": record.get("creator_name"),
        "creator_email": record.get("creator_email"),
        "updator_name": record.get("updator_name"),
        "updator_email": record.get("updator_email"),
        "shortDescription": record.get("shortDescription"),
        "keywords": record.get("keywords"),
        "stages": record.get("stages"),
        "card_type": record.get("card_type"),
        "status": record.get("status"),
        "publishDate": record.get("publishDate"),
        "reviewDate": record.get("reviewDate"),
        "practices": record.get("practices"),
        "expertEffortTime": record.get("expertEffortTime"),
        "staffEffortTime": record.get("staffEffortTime"),
        "softwaresUsed": record.get("softwaresUsed"),
        "summary_text": summary.get("text"),
        "image_url": summary.get("image_url"),
        "image_description": summary.get("image_description"),
        "resources": record.get("resources"),
        "features": record.get("features"),
        "appURL": record.get("appURL"),
    }


def _build_text(record: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    """Build the 'text' field: ```json metadata ``` + markdown article with our content."""
    title = _safe_str(record.get("name") or record.get("id") or "Palette")
    summary = record.get("summary_text") or {}
    summary_text = _safe_str(summary.get("text"))
    short_desc = _safe_str(record.get("shortDescription"))
    practices = record.get("practices") or []
    resources = record.get("resources") or []
    created = _safe_str(record.get("createdAt"))
    updated = _safe_str(record.get("updatedAt"))
    creator_name = _safe_str(record.get("creator_name"))
    creator_email = _safe_str(record.get("creator_email"))
    updator_name = _safe_str(record.get("updator_name"))
    updator_email = _safe_str(record.get("updator_email"))
    rid = _safe_str(record.get("id"))

    metadata_json = json.dumps(metadata, indent=2, ensure_ascii=False, default=str)

    parts = [
        "\n\n```json",
        metadata_json,
        "```",
        "",
        f"## {title}",
        "",
        f"- **ID:** `{rid}`",
        f"- **Created At:** `{created}`",
        f"- **Updated At:** `{updated}`",
        "",
        "### Created By",
        f"- **Email:** `{creator_email}`",
        f"- **Name:** `{creator_name}`",
        "",
        "### Last Updated By",
        f"- **Email:** `{updator_email}`",
        f"- **Name:** `{updator_name}`",
        "",
        "## Details",
        "",
        f"- **Title:** {title}",
        f"- **Card Type:** `{record.get('card_type') or ''}`",
        f"- **Status:** `{record.get('status') or ''}`",
    ]
    if short_desc:
        parts.extend(["", "### Short Description", "", short_desc])
    if summary_text:
        parts.extend(["", "### Summary", "", summary_text])
    if practices:
        parts.extend(["", "### Practices", "", ", ".join(practices)])
    if resources:
        res_lines = []
        for r in resources:
            rt = r.get("recordType") or "—"
            link = r.get("link") or "—"
            ft = r.get("fileType") or "—"
            res_lines.append(f"- {rt} | {ft} | {link}")
        parts.extend(["", "### Resources", ""] + res_lines)
    return "\n".join(parts).strip()


def record_to_index_doc(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert one palette output record to index document format:
    _id, title, text (markdown with ```json metadata + article), metadata, vector_field [].
    """
    metadata = _metadata_from_record(record)
    text = _build_text(record, metadata)
    return {
        "_id": record.get("id"),
        "title": record.get("name") or record.get("id"),
        "text": text,
        "metadata": metadata,
        "vector_field": [],  # to be filled by embedding the text field
    }


def transform_output_to_index(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform full output list to index-ready documents."""
    return [record_to_index_doc(r) for r in records]
