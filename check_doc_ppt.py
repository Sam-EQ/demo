"""Quick check: doc/docx and ppt/pptx in output_index.json resources."""
import json
from collections import Counter

with open("output_index.json", "r") as f:
    docs = json.load(f)

doc_like = []
ppt_like = []

def is_card(doc):
    meta = doc.get("metadata") or { }
    return isinstance(meta.get("resources"), list)

for doc in docs:
    if not is_card(doc):
        continue
    meta = doc.get("metadata") or {}
    pid = meta.get("id") or doc.get("_id")
    for r in meta.get("resources") or []:
        link = (r.get("link") or "") if isinstance(r.get("link"), str) else ""
        ft = (r.get("fileType") or "").strip().lower()
        fid = r.get("fileId")
        if link and (".docx" in link.lower() or link.lower().endswith(".doc")):
            doc_like.append((pid, link[:80], ft, fid))
        if ft in ("doc", "docx", "document"):
            doc_like.append((pid, link[:80] if link else "(no link)", ft, fid))
        if link and (".pptx" in link.lower() or ".ppt" in link.lower() or "powerpoint" in link.lower()):
            ppt_like.append((pid, link[:80], ft, fid))
        if ft in ("ppt", "pptx", "powerpoint", "presentation"):
            ppt_like.append((pid, link[:80] if link else "(no link)", ft, fid))

print("Doc/docx (link or fileType):", len(doc_like))
for x in doc_like[:20]:
    print(" ", x)
print()
print("Ppt/pptx (link or fileType):", len(ppt_like))
for x in ppt_like[:20]:
    print(" ", x)

all_ft = []
for doc in docs:
    if not is_card(doc):
        continue
    for r in (doc.get("metadata") or {}).get("resources") or []:
        all_ft.append((r.get("fileType") or "").strip().lower() or "(empty)")
print()
print("All fileType values:", Counter(all_ft))

all_links = []
for doc in docs:
    if not is_card(doc):
        continue
    for r in (doc.get("metadata") or {}).get("resources") or []:
        link = r.get("link")
        if link and isinstance(link, str):
            all_links.append(link)
doc_ppt = [L for L in all_links if L and (".doc" in L.lower() or ".ppt" in L.lower() or "docx" in L.lower() or "pptx" in L.lower())]
print("Links containing .doc/.docx/.ppt/.pptx:", len(doc_ppt))
for L in doc_ppt[:25]:
    print(" ", L[:120])
