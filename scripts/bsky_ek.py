"""Bluesky ek yardımcıları: düz metin gönderi, cevap, rakibin gönderisini bulma, son metinler.

ozel_paylasim.py ve mac_takip.py kullanır. Yalnızca standart kütüphane.
"""

import re
import time
import urllib.parse
from datetime import datetime, timezone

import bluesky_paylas as bp

APPVIEW = "https://public.api.bsky.app"


def _facets(metin):
    """#etiketleri ve adresleri tıklanabilir yapar (bayt konumları UTF-8)."""
    f = []
    for m in re.finditer(r"#(\w+)", metin):
        f.append({"index": {"byteStart": len(metin[:m.start()].encode()), "byteEnd": len(metin[:m.end()].encode())},
                  "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    for m in re.finditer(r"https?://\S+", metin):
        f.append({"index": {"byteStart": len(metin[:m.start()].encode()), "byteEnd": len(metin[:m.end()].encode())},
                  "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group(0)}]})
    return f


def gonder(pds, did, token, metin, cevap=None, link=None, link_baslik=""):
    """Düz metin gönderi; cevap = {"uri","cid"} (kök ve ebeveyn aynı), link = bağlantı kartı."""
    kayit = {"$type": "app.bsky.feed.post", "text": metin[:300], "langs": ["tr"],
             "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    f = _facets(kayit["text"])
    if f:
        kayit["facets"] = f
    if cevap:
        ref = {"uri": cevap["uri"], "cid": cevap["cid"]}
        kayit["reply"] = {"root": cevap.get("root") or ref, "parent": ref}
    if link:
        kayit["embed"] = {"$type": "app.bsky.embed.external",
                          "external": {"uri": link, "title": link_baslik or link, "description": ""}}
    return bp.http("POST", f"{pds}/xrpc/com.atproto.repo.createRecord",
                   {"repo": did, "collection": "app.bsky.feed.post", "record": kayit}, token=token)


def son_gonderiler(handle, limit=50, filtre="posts_with_replies"):
    q = urllib.parse.urlencode({"actor": handle, "limit": limit, "filter": filtre})
    return [x["post"] for x in bp.http("GET", f"{APPVIEW}/xrpc/app.bsky.feed.getAuthorFeed?{q}").get("feed", [])
            if x.get("post", {}).get("author", {}).get("handle") == handle]


def son_metinler(handle, limit=50):
    """Hesabın son gönderilerinin metinleri (çift gönderi kontrolü için)."""
    try:
        return [(p.get("record") or {}).get("text", "") for p in son_gonderiler(handle, limit)]
    except Exception:  # noqa: BLE001
        return []


def link_iceren_gonderi(handle, parca, bekle_dk=0):
    """Hesabın bağlantı kartında `parca` geçen son gönderisini bulur; gerekirse bekler."""
    bitis = time.time() + bekle_dk * 60
    while True:
        try:
            for p in son_gonderiler(handle, 30, "posts_no_replies"):
                dis = ((p.get("embed") or {}).get("external") or {}).get("uri", "")
                if parca in dis:
                    return {"uri": p["uri"], "cid": p["cid"]}
        except Exception as e:  # noqa: BLE001
            print(f"::warning::{handle} akışı okunamadı: {e}")
        if time.time() >= bitis:
            return None
        time.sleep(60)
