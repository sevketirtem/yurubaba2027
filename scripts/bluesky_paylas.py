#!/usr/bin/env python3
"""Sitenin yeni yazılarını Bluesky hesabında (ve varsa Telegram kanalında) paylaşır.

Nasıl çalışır:
  1. Yayındaki sitenin RSS akışını (index.xml) okur; yalnızca yazıları alır
     (adresinde /YYYY/AA/ olanlar), "Hakkında" gibi sayfaları atlar.
  2. Son PAYLASIM_SAAT saat içinde yayınlanmış yazıları seçer.
  3. Bluesky hesabının kendi son gönderilerine bakar; zaten paylaşılmış
     adresleri atlar. Bu sayede ayrı bir "paylaşıldı" dosyası tutmaya gerek
     kalmaz ve bot kaç kez çalışırsa çalışsın aynı yazıyı iki kez paylaşmaz.
  4. Kalanları eskiden yeniye, her çalışmada en fazla EN_FAZLA tane olmak
     üzere, bağlantı kartıyla paylaşır.

Ortam değişkenleri:
  SITE_FEED              Örn. https://hadibaba.com/index.xml (zorunlu)
  BLUESKY_HANDLE         Örn. hadibaba.bsky.social (GitHub secret)
  BLUESKY_APP_PASSWORD   Bluesky "App Password" (GitHub secret; asıl şifre DEĞİL)
  PAYLASIM_SAAT          Kaç saat geriye bakılsın (varsayılan 48)
  EN_FAZLA               Bir çalışmada en fazla kaç gönderi (varsayılan 3)
  ETIKETLER              Gönderi sonuna eklenecek etiketler (varsayılan "#futbol")
  DRY_RUN                "true" ise hiçbir şey paylaşmaz, sadece ne yapacağını yazar
  TELEGRAM_BOT_TOKEN     @BotFather'ın verdiği token (GitHub secret; yoksa Telegram atlanır)
  TELEGRAM_CHANNEL       Kanal adı, ör. @hadibaba (GitHub secret)
  TELEGRAM_KONTROL       "true" ise hiçbir şey paylaşmaz; sadece botun kanala
                         yönetici olarak eklendiğini ve mesaj atabildiğini kontrol eder

Telegram ayrı bir "paylaşıldı" listesi tutmaz: bir yazı Bluesky'da ilk kez
paylaşıldığı anda Telegram kanalına da gönderilir.

Yalnızca Python standart kütüphanesi kullanılır; kurulacak paket yok.
"""

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

ENTRYWAY = "https://bsky.social"
UA = "HadiYuruBot/1.0 (+https://github.com/sevketirtem)"
YAZI_ADRESI = re.compile(r"/\d{4}/\d{2}/[^/]+/?$")
TEXT_SINIRI = 300  # Bluesky gönderi sınırı (grafem); güvenli tarafta kalıyoruz


def http(method, url, body=None, token=None, raw=False):
    headers = {"User-Agent": UA}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            icerik = r.read()
    except urllib.error.HTTPError as e:
        hata = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {e.code}: {hata}") from None
    return icerik if raw else json.loads(icerik or b"{}")


def rss_yazilari(feed_url):
    """RSS'ten (başlık, adres, yayın zamanı) listesi döndürür."""
    son_hata = None
    for deneme in range(3):  # Pages yayından hemen sonra birkaç saniye eski içerik verebilir
        try:
            xml = http("GET", f"{feed_url}?t={int(time.time())}", raw=True)
            break
        except Exception as e:  # noqa: BLE001
            son_hata = e
            time.sleep(20)
    else:
        raise RuntimeError(f"RSS okunamadı: {son_hata}")

    yazilar = []
    for item in ET.fromstring(xml).iter("item"):
        link = (item.findtext("link") or "").strip()
        if not YAZI_ADRESI.search(link):
            continue
        tarih = parsedate_to_datetime(item.findtext("pubDate"))
        yazilar.append({
            "baslik": html.unescape(item.findtext("title") or "").strip(),
            "adres": link,
            "zaman": tarih,
        })
    return yazilar


def sayfa_aciklamasi(adres):
    """Yazının <meta name="description"> içeriğini alır (kart açıklaması)."""
    try:
        sayfa = http("GET", adres, raw=True).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""
    m = re.search(r'<meta\s+name="?description"?\s+content="([^"]*)"', sayfa)
    return html.unescape(m.group(1)).strip() if m else ""


def oturum_ac(handle, sifre):
    s = http("POST", f"{ENTRYWAY}/xrpc/com.atproto.server.createSession",
             {"identifier": handle, "password": sifre})
    pds = ENTRYWAY
    for servis in (s.get("didDoc") or {}).get("service", []):
        if servis.get("id", "").endswith("#atproto_pds"):
            pds = servis["serviceEndpoint"].rstrip("/")
    return s["did"], s["accessJwt"], pds


def paylasilmis_adresler(pds, did, token):
    """Hesabın son 100 gönderisindeki bağlantı kartı adresleri."""
    q = urllib.parse.urlencode({"repo": did, "collection": "app.bsky.feed.post", "limit": 100})
    r = http("GET", f"{pds}/xrpc/com.atproto.repo.listRecords?{q}", token=token)
    adresler = set()
    for kayit in r.get("records", []):
        dis = ((kayit.get("value") or {}).get("embed") or {}).get("external") or {}
        if dis.get("uri"):
            adresler.add(dis["uri"].rstrip("/"))
    return adresler


def gonderi_olustur(yazi, aciklama, etiketler):
    baslik = yazi["baslik"]
    ek = f"\n\n{etiketler}" if etiketler else ""
    if len(baslik) + len(ek) > TEXT_SINIRI:
        baslik = baslik[: TEXT_SINIRI - len(ek) - 1].rstrip() + "…"
    metin = baslik + ek

    # Etiketlerin tıklanabilir olması için "facet" (bayt konumları UTF-8'e göre)
    facets = []
    for m in re.finditer(r"#(\w+)", metin):
        bas = len(metin[: m.start()].encode())
        son = len(metin[: m.end()].encode())
        facets.append({
            "index": {"byteStart": bas, "byteEnd": son},
            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}],
        })

    kayit = {
        "$type": "app.bsky.feed.post",
        "text": metin,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "langs": ["tr"],
        "embed": {
            "$type": "app.bsky.embed.external",
            "external": {"uri": yazi["adres"], "title": yazi["baslik"], "description": aciklama[:300]},
        },
    }
    if facets:
        kayit["facets"] = facets
    return kayit


def telegram_api(token, metot, veri):
    url = f"https://api.telegram.org/bot{token}/{metot}"
    req = urllib.request.Request(url, data=urllib.parse.urlencode(veri).encode(),
                                 headers={"User-Agent": UA}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["result"]
    except urllib.error.HTTPError as e:
        aciklama = json.loads(e.read() or b"{}").get("description", "")
        # Hata mesajında token görünmesin diye adresi yazmıyoruz
        raise RuntimeError(f"Telegram {metot} -> HTTP {e.code}: {aciklama}") from None


def telegram_mesaji(yazi, aciklama):
    satirlar = [f"<b>{html.escape(yazi['baslik'], quote=False)}</b>"]
    if aciklama:
        satirlar.append(html.escape(aciklama, quote=False))
    satirlar.append(f'👉 <a href="{html.escape(yazi["adres"], quote=True)}">Yazının tamamı</a>')
    return "\n\n".join(satirlar)


def telegram_gonder(token, kanal, yazi, aciklama):
    return telegram_api(token, "sendMessage", {
        "chat_id": kanal,
        "text": telegram_mesaji(yazi, aciklama),
        "parse_mode": "HTML",
        "link_preview_options": json.dumps({"url": yazi["adres"], "prefer_large_media": True}),
    })


def telegram_kontrol(token, kanal):
    bot = telegram_api(token, "getMe", {})
    sohbet = telegram_api(token, "getChat", {"chat_id": kanal})
    uye = telegram_api(token, "getChatMember", {"chat_id": kanal, "user_id": bot["id"]})
    yazabilir = uye.get("status") == "creator" or uye.get("can_post_messages")
    durum = "mesaj atabilir ✅" if yazabilir else "MESAJ ATAMAZ ❌ (yöneticilikte 'Mesaj gönderme' iznini aç)"
    print(f"::notice title=Telegram kontrolü::Bot @{bot['username']} → {sohbet.get('title')} "
          f"({kanal}), yetki: {uye.get('status')}, {durum}")
    if not yazabilir:
        sys.exit(1)


def main():
    feed = os.environ.get("SITE_FEED", "").strip()
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    sifre = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    saat = float(os.environ.get("PAYLASIM_SAAT", "48"))
    en_fazla = int(os.environ.get("EN_FAZLA", "3"))
    etiketler = os.environ.get("ETIKETLER", "#futbol").strip()
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_kanal = os.environ.get("TELEGRAM_CHANNEL", "").strip()
    if tg_kanal and not tg_kanal.startswith("@") and not tg_kanal.lstrip("-").isdigit():
        tg_kanal = "@" + tg_kanal.split("/")[-1]  # "t.me/hadibaba" veya "hadibaba" yazılmışsa

    if os.environ.get("TELEGRAM_KONTROL", "").lower() == "true":
        if not tg_token or not tg_kanal:
            sys.exit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL secret'ları yok.")
        telegram_kontrol(tg_token, tg_kanal)
        return

    if not feed:
        sys.exit("SITE_FEED tanımlı değil.")

    sinir = datetime.now(timezone.utc) - timedelta(hours=saat)
    adaylar = sorted((y for y in rss_yazilari(feed) if y["zaman"] >= sinir), key=lambda y: y["zaman"])
    print(f"Son {saat:g} saatte {len(adaylar)} yazı var.")

    if not handle or not sifre:
        print("::notice::BLUESKY_HANDLE / BLUESKY_APP_PASSWORD secret'ları yok; paylaşım atlandı.")
        for y in adaylar:
            print(f"  (paylaşılacaktı) {y['adres']}")
        return

    did, token, pds = oturum_ac(handle, sifre)
    eski = paylasilmis_adresler(pds, did, token)
    print(f"::notice::Giriş başarılı ({handle}); {len(eski)} paylaşılmış bağlantı bulundu.")
    yeni = [y for y in adaylar if y["adres"].rstrip("/") not in eski][:en_fazla]
    if not yeni:
        print("Paylaşılacak yeni yazı yok.")
        return

    if not (tg_token and tg_kanal):
        print("Telegram secret'ları yok; yalnızca Bluesky.")

    for y in yeni:
        aciklama = sayfa_aciklamasi(y["adres"])
        kayit = gonderi_olustur(y, aciklama, etiketler)
        if dry_run:
            print("DRY_RUN:", json.dumps(kayit, ensure_ascii=False))
            print(f"::notice title=Deneme (paylaşılmadı)::{y['adres']} | {kayit['text']!r}")
            if tg_token and tg_kanal:
                print("DRY_RUN Telegram:", telegram_mesaji(y, aciklama))
            continue
        r = http("POST", f"{pds}/xrpc/com.atproto.repo.createRecord",
                 {"repo": did, "collection": "app.bsky.feed.post", "record": kayit}, token=token)
        print(f"Paylaşıldı: {y['adres']} -> {r.get('uri')}")
        print(f"::notice title=Bluesky'da paylaşıldı::{y['adres']}")
        if tg_token and tg_kanal:
            try:
                telegram_gonder(tg_token, tg_kanal, y, aciklama)
                print(f"::notice title=Telegram'da paylaşıldı::{y['adres']}")
            except Exception as e:  # noqa: BLE001 — Telegram hatası Bluesky'ı durdurmasın
                print(f"::warning title=Telegram'a gönderilemedi::{y['adres']} | {e}")
        time.sleep(2)


if __name__ == "__main__":
    main()
