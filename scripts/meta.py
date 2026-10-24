"""Meta platformlarına (Facebook Sayfası, Instagram, Threads) paylaşım.

bluesky_paylas.py tarafından kullanılır; tek başına çalışmaz.
Yalnızca Python standart kütüphanesi.

Anahtarlar (GitHub secret):
  META_PAGE_TOKEN  Facebook Sayfa erişim anahtarı (süresiz). Sayfaya bağlı
                   Instagram profesyonel hesabına da bu anahtarla gönderilir.
                   Sayfa ve Instagram kimlikleri anahtardan otomatik bulunur.
  THREADS_TOKEN    Threads uzun ömürlü anahtarı (60 gün; meta_yenile.yml
                   ayda iki kez yeniler).
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v25.0"
THREADS = "https://graph.threads.net/v1.0"
UA = "HadiYuruBot/1.0 (+https://github.com/sevketirtem)"
THREADS_SINIRI = 500


def istek(method, url, params=None):
    """Graph/Threads API çağrısı. Hata mesajında anahtar görünmez."""
    params = dict(params or {})
    veri = None
    if method == "GET":
        url = f"{url}?{urllib.parse.urlencode(params)}"
    else:
        veri = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=veri, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            hata = json.loads(e.read()).get("error", {})
            mesaj = f"{hata.get('type', '')} {hata.get('code', '')}: {hata.get('message', '')}"
        except Exception:  # noqa: BLE001
            mesaj = "(ayrıntı yok)"
        yol = urllib.parse.urlsplit(url).path
        raise RuntimeError(f"{method} {yol} -> HTTP {e.code} {mesaj}") from None


# ---------------------------------------------------------------- Facebook + Instagram

def sayfa_kimlikleri(page_token):
    """Sayfa anahtarından Sayfa ve bağlı Instagram hesabını bulur."""
    me = istek("GET", f"{GRAPH}/me", {
        "fields": "id,name,instagram_business_account{id,username}",
        "access_token": page_token,
    })
    ig = me.get("instagram_business_account") or {}
    return {"page_id": me["id"], "page_name": me.get("name"),
            "ig_id": ig.get("id"), "ig_username": ig.get("username")}


def facebook_paylas(page_token, page_id, metin, link):
    r = istek("POST", f"{GRAPH}/{page_id}/feed", {
        "message": metin, "link": link, "access_token": page_token,
    })
    return r.get("id")


def _bekle(url, alan, token, bitti=("FINISHED",), hata=("ERROR", "EXPIRED"), sure=90):
    """Konteyner hazır olana kadar bekler (Instagram/Threads medya işleme)."""
    son = None
    for _ in range(sure // 5):
        try:
            son = istek("GET", url, {"fields": alan, "access_token": token}).get(alan)
        except RuntimeError:
            son = None
        if son in bitti:
            return
        if son in hata:
            raise RuntimeError(f"Konteyner durumu: {son}")
        time.sleep(5)
    raise RuntimeError(f"Konteyner {sure} sn içinde hazır olmadı (son durum: {son})")


def instagram_paylas(page_token, ig_id, gorsel_url, aciklama):
    kap = istek("POST", f"{GRAPH}/{ig_id}/media", {
        "image_url": gorsel_url, "caption": aciklama[:2200], "access_token": page_token,
    })["id"]
    _bekle(f"{GRAPH}/{kap}", "status_code", page_token)
    r = istek("POST", f"{GRAPH}/{ig_id}/media_publish", {
        "creation_id": kap, "access_token": page_token,
    })
    return r.get("id")


def instagram_kota(page_token, ig_id):
    try:
        r = istek("GET", f"{GRAPH}/{ig_id}/content_publishing_limit", {
            "fields": "quota_usage,config", "access_token": page_token,
        })
        d = (r.get("data") or [{}])[0]
        return f"{d.get('quota_usage')}/{(d.get('config') or {}).get('quota_total')}"
    except RuntimeError as e:
        return f"okunamadı ({e})"


# ---------------------------------------------------------------- Threads

def threads_kullanici(th_token):
    return istek("GET", f"{THREADS}/me", {"fields": "id,username", "access_token": th_token})


def threads_paylas(th_token, metin, link):
    kap = istek("POST", f"{THREADS}/me/threads", {
        "media_type": "TEXT", "text": metin[:THREADS_SINIRI],
        "link_attachment": link, "access_token": th_token,
    })["id"]
    try:
        _bekle(f"{THREADS}/{kap}", "status", th_token, sure=60)
    except RuntimeError as e:
        if "durumu" in str(e):
            raise
        time.sleep(10)  # durum okunamadıysa kısa bekleyip yine de dene
    r = istek("POST", f"{THREADS}/me/threads_publish", {
        "creation_id": kap, "access_token": th_token,
    })
    return r.get("id")


def threads_yenile(th_token):
    """60 günlük anahtarı yeniler; yeni anahtarı ve kalan gün sayısını döndürür."""
    r = istek("GET", "https://graph.threads.net/refresh_access_token", {
        "grant_type": "th_refresh_token", "access_token": th_token,
    })
    return r["access_token"], int(r.get("expires_in", 0)) // 86400


# ---------------------------------------------------------------- metinler

def kisalt(metin, sinir):
    return metin if len(metin) <= sinir else metin[: sinir - 1].rstrip() + "…"


def metinler(yazi, aciklama, etiketler, ig_etiketler, alan):
    baslik = yazi["baslik"]
    govde = f"{baslik}\n\n{aciklama}" if aciklama else baslik
    ilk_etiket = (etiketler.split() or [""])[0]  # Threads gönderi başına tek konu etiketi alır
    th_ek = f"\n\n{ilk_etiket}" if ilk_etiket else ""
    return {
        "facebook": f"{govde}\n\n{etiketler}".strip(),
        "instagram": f"{govde}\n\n👉 Yazının tamamı profildeki bağlantıda: {alan}\n\n{ig_etiketler}".strip(),
        "threads": kisalt(govde, THREADS_SINIRI - len(th_ek)) + th_ek,
    }
