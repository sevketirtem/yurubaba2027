#!/usr/bin/env python3
"""Sitenin yeni yazılarını Bluesky'da ve (anahtarları varsa) Telegram, Facebook,
Instagram ve Threads'te paylaşır.

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

  META_PAGE_TOKEN        Facebook Sayfa anahtarı (süresiz; Instagram da bununla)
  THREADS_TOKEN          Threads anahtarı (60 gün; meta_yenile.yml yeniler)
  IG_ETIKETLER           Instagram etiketleri (varsayılan "#futbol #süperlig #türkfutbolu")
  META_SAYFA_ADI         Kullanıcı anahtarı birden çok Sayfa yönetiyorsa hangisi (ör. "Hadi Baba")
  META_KONTROL           "true" ise hiçbir şey paylaşmaz; Meta anahtarlarını kontrol eder
  META_YAZI              Bir yazı adresi verilirse yalnızca o yazı yalnızca Facebook,
                         Instagram ve Threads'e gönderilir (Bluesky/Telegram'a dokunulmaz).
                         Deneme ve geriye dönük paylaşım için; DRY_RUN'a uyar.

Diğer platformlar ayrı bir "paylaşıldı" listesi tutmaz: bir yazı Bluesky'da
ilk kez paylaşıldığı anda öbürlerine de gönderilir. Birinin hatası diğerlerini
durdurmaz (Actions özetinde uyarı olarak görünür).

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

import meta

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


def _meta(sayfa, ad):
    """<meta name|property=ad content=...> değerini bulur (tırnaklı/tırnaksız)."""
    m = re.search(r'<meta\s+(?:name|property)="?' + re.escape(ad) + r'"?\s+content="([^"]*)"', sayfa)
    return html.unescape(m.group(1)).strip() if m else ""


def sayfa_bilgisi(adres):
    """Yazı sayfasından açıklama ve paylaşım kartı adreslerini alır."""
    try:
        sayfa = http("GET", adres, raw=True).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {"aciklama": "", "kart": "", "kare": ""}
    return {
        "aciklama": _meta(sayfa, "description"),
        "kart": _meta(sayfa, "og:image"),        # 1200x630, bağlantı önizlemesi
        "kare": _meta(sayfa, "hadiyuru:kare"),   # 1080x1080, Instagram
    }


def sayfa_aciklamasi(adres):
    return sayfa_bilgisi(adres)["aciklama"]


def kart_yukle(pds, token, kart_adresi):
    """Kart görselini Bluesky'a yükler; bağlantı kartında küçük resim olur."""
    if not kart_adresi:
        return None
    try:
        veri = http("GET", kart_adresi, raw=True)
        if len(veri) > 950_000:
            return None
        req = urllib.request.Request(f"{pds}/xrpc/com.atproto.repo.uploadBlob", data=veri, method="POST",
                                     headers={"User-Agent": UA, "Content-Type": "image/jpeg",
                                              "Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["blob"]
    except Exception as e:  # noqa: BLE001 — resim olmadan da paylaşılır
        print(f"::warning::Kart görseli yüklenemedi: {e}")
        return None


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


def gonderi_olustur(yazi, aciklama, etiketler, thumb=None):
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
    if thumb:
        kayit["embed"]["external"]["thumb"] = thumb
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


def meta_kontrol(page_token, th_token, sayfa_adi=None):
    tamam = True
    if page_token:
        try:
            k = meta.sayfa_kimlikleri(page_token, sayfa_adi)
            print(f"::notice title=Facebook kontrolü::Sayfa: {k['page_name']} ({k['page_id']}) ✅ [{k['kaynak']}]")
            if k["ig_id"]:
                print(f"::notice title=Instagram kontrolü::@{k['ig_username']} ({k['ig_id']}) ✅, "
                      f"24 saatlik kota: {meta.instagram_kota(k['page_token'], k['ig_id'])}")
            else:
                tamam = False
                print("::warning title=Instagram kontrolü::Sayfaya bağlı Instagram profesyonel hesabı bulunamadı ❌")
        except Exception as e:  # noqa: BLE001
            tamam = False
            print(f"::error title=Facebook kontrolü::{e}")
    else:
        print("::notice::META_PAGE_TOKEN yok; Facebook/Instagram atlanır.")
    if th_token:
        try:
            u = meta.threads_kullanici(th_token)
            print(f"::notice title=Threads kontrolü::@{u.get('username')} ({u.get('id')}) ✅")
        except Exception as e:  # noqa: BLE001
            tamam = False
            print(f"::error title=Threads kontrolü::{e}")
    else:
        print("::notice::THREADS_TOKEN yok; Threads atlanır.")
    if not tamam:
        sys.exit(1)


def meta_gonder(y, bilgi, aciklama, etiketler, ig_etiketler, page_token, th_token, kimlik, dry_run):
    """Bir yazıyı Facebook, Instagram ve Threads'e gönderir; her biri bağımsız."""
    alan = urllib.parse.urlsplit(y["adres"]).netloc
    m = meta.metinler(y, aciklama, etiketler, ig_etiketler, alan)
    hedefler = []
    if page_token and kimlik:
        pt = kimlik["page_token"]
        hedefler.append(("Facebook", lambda: meta.facebook_paylas(pt, kimlik["page_id"], m["facebook"], y["adres"])))
        if kimlik.get("ig_id"):
            if bilgi.get("kare"):
                hedefler.append(("Instagram", lambda: meta.instagram_paylas(pt, kimlik["ig_id"], bilgi["kare"], m["instagram"])))
            else:
                print(f"::warning title=Instagram atlandı::{y['adres']} | sayfada kare kart görseli yok")
    if th_token:
        hedefler.append(("Threads", lambda: meta.threads_paylas(th_token, m["threads"], y["adres"])))
    ekler = {"Facebook": ("'ta", "'a"), "Instagram": ("'da", "'a"), "Threads": ("'te", "'e")}
    for ad, gorev in hedefler:
        if dry_run:
            print(f"DRY_RUN {ad}:", json.dumps(m[ad.lower()], ensure_ascii=False))
            continue
        try:
            gorev()
            print(f"::notice title={ad}{ekler[ad][0]} paylaşıldı::{y['adres']}")
        except Exception as e:  # noqa: BLE001
            print(f"::warning title={ad}{ekler[ad][1]} gönderilemedi::{y['adres']} | {e}")


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

    page_token = os.environ.get("META_PAGE_TOKEN", "").strip()
    th_token = os.environ.get("THREADS_TOKEN", "").strip()
    ig_etiketler = os.environ.get("IG_ETIKETLER", "").strip() or "#futbol #süperlig #türkfutbolu"
    sayfa_adi = os.environ.get("META_SAYFA_ADI", "").strip() or None

    if os.environ.get("META_KONTROL", "").lower() == "true":
        meta_kontrol(page_token, th_token, sayfa_adi)
        return

    tek_yazi = os.environ.get("META_YAZI", "").strip()
    if tek_yazi:
        if not feed:
            sys.exit("SITE_FEED tanımlı değil.")
        bul = [y for y in rss_yazilari(feed) if y["adres"].rstrip("/") == tek_yazi.rstrip("/")]
        if not bul:
            sys.exit(f"Yazı RSS'te bulunamadı: {tek_yazi}")
        y = bul[0]
        bilgi = sayfa_bilgisi(y["adres"])
        kimlik = meta.sayfa_kimlikleri(page_token, sayfa_adi) if page_token else None
        print(f"Yalnızca Meta'ya gönderiliyor: {y['adres']}")
        meta_gonder(y, bilgi, bilgi["aciklama"], etiketler, ig_etiketler, page_token, th_token, kimlik, dry_run)
        return

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
        print("Telegram secret'ları yok; Telegram atlanır.")
    kimlik = None
    if page_token:
        try:
            kimlik = meta.sayfa_kimlikleri(page_token, sayfa_adi)
        except Exception as e:  # noqa: BLE001
            print(f"::warning title=Facebook/Instagram atlandı::Sayfa anahtarı çalışmadı: {e}")

    for y in yeni:
        bilgi = sayfa_bilgisi(y["adres"])
        aciklama = bilgi["aciklama"]
        thumb = None if dry_run else kart_yukle(pds, token, bilgi["kart"])
        kayit = gonderi_olustur(y, aciklama, etiketler, thumb)
        if dry_run:
            print("DRY_RUN:", json.dumps(kayit, ensure_ascii=False))
            print(f"::notice title=Deneme (paylaşılmadı)::{y['adres']} | {kayit['text']!r}")
            if tg_token and tg_kanal:
                print("DRY_RUN Telegram:", telegram_mesaji(y, aciklama))
            meta_gonder(y, bilgi, aciklama, etiketler, ig_etiketler, page_token, th_token, kimlik, True)
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
        meta_gonder(y, bilgi, aciklama, etiketler, ig_etiketler, page_token, th_token, kimlik, False)
        time.sleep(2)


if __name__ == "__main__":
    main()
