#!/usr/bin/env python3
"""Yazı olmayan özel bir duyuruyu (ör. derbi günü "Maç Merkezi" bağlantısı) sosyal medyada paylaşır.

bluesky_paylas.py ve meta.py'deki yardımcıları kullanır. Akış:
  1. MAC verilirse ("Galatasaray-Fenerbahce") skor API'sinin /api/maclar listesinden maçı bulur,
     adres = SITE/mac/?id=<maç numarası>.
  2. HEDEF_ZAMAN verilirse o ana kadar bekler (en fazla ~5,5 saat; Actions işi 6 saatle sınırlı).
  3. ILK11_BEKLE dakika boyunca ilk 11'lerin açıklanmasını bekler (/api/mac). Açıklandıysa
     METIN_ILK11, açıklanmadıysa METIN_ONCE kullanılır.
  4. Bluesky'da aynı adres zaten paylaşılmışsa hiçbir yere göndermez (iki tetikleme çift gönderi yapmaz).
     Maç başlamış ve SON_DAKIKA'dan fazla geçmişse de göndermez.
  5. Bluesky, Telegram, Facebook, Instagram, Threads (anahtarı olanlar); her biri bağımsız.

Ortam değişkenleri: SITE (https://hadibaba.com), SKOR_API, MAC ("Ev-Dep", ASCII API adları),
ADRES (MAC yoksa doğrudan adres), BASLIK (bağlantı kartı başlığı), METIN_ILK11, METIN_ONCE,
HEDEF_ZAMAN (ISO, ör. 2026-10-26T20:35:00+03:00), ILK11_BEKLE (dk), SON_DAKIKA (dk),
ETIKETLER, IG_ETIKETLER, PLATFORMLAR (boş = hepsi; ör. "bluesky,telegram"), DRY_RUN,
ve bluesky_paylas.py'deki anahtarlar.
"""

import html
import json
import os
import sys
import time
import unicodedata
import urllib.parse
from datetime import datetime, timezone

import bluesky_paylas as bp
import bsky_ek
import meta


def ortam(ad, varsayilan=""):
    return os.environ.get(ad, varsayilan).strip()


def api(skor_api, yol):
    return bp.http("GET", f"{skor_api.rstrip('/')}{yol}")


def sade(ad):
    """'Fenerbahçe' ile 'Fenerbahce'yi eşit sayar (Türkçe harfler, büyük/küçük)."""
    ad = ad.replace("ı", "i").replace("İ", "I")
    return "".join(c for c in unicodedata.normalize("NFKD", ad) if not unicodedata.combining(c)).casefold().strip()


def maci_bul(skor_api, mac):
    ev, dep = [sade(x) for x in mac.split("-", 1)]
    for m in api(skor_api, "/api/maclar").get("maclar", []):
        if sade(m["ev"]) == ev and sade(m["dep"]) == dep:
            return m
    raise RuntimeError(f"'{mac}' bu haftanın maç listesinde yok")


def main():
    site = ortam("SITE").rstrip("/")
    skor_api = ortam("SKOR_API")
    dry_run = ortam("DRY_RUN").lower() == "true"
    platformlar = {p.strip().lower() for p in ortam("PLATFORMLAR").split(",") if p.strip()}
    istendi = lambda p: not platformlar or p in platformlar  # noqa: E731
    etiketler = ortam("ETIKETLER", "#futbol")
    ig_etiketler = ortam("IG_ETIKETLER", "#futbol #süperlig #türkfutbolu")

    # 1. Adres
    mac_no, baslama = None, None
    if ortam("MAC"):
        m = maci_bul(skor_api, ortam("MAC"))
        mac_no, baslama = m["id"], datetime.fromisoformat(m["tarih"])
        adres = f"{site}/mac/?id={mac_no}"
        print(f"::notice title=Maç bulundu::{m['ev']} - {m['dep']} ({m['tarih']}) → {adres}")
    else:
        adres = ortam("ADRES")
    if not adres:
        sys.exit("ADRES ya da MAC gerekli")

    # 2. Hedef zamana kadar bekle
    if ortam("HEDEF_ZAMAN"):
        hedef = datetime.fromisoformat(ortam("HEDEF_ZAMAN"))
        kalan = (hedef - datetime.now(timezone.utc)).total_seconds()
        if kalan > 5.5 * 3600:
            sys.exit(f"::error::Hedef zaman çok uzak ({kalan / 3600:.1f} saat); daha yakın bir zamanda tetikleyin")
        if kalan > 0 and not dry_run:
            print(f"Hedef zamana {kalan / 60:.0f} dk var, bekleniyor…")
            time.sleep(kalan)

    # Maç çoktan başladıysa duyuru anlamsız
    son_dk = float(ortam("SON_DAKIKA", "20"))
    if baslama and (datetime.now(timezone.utc) - baslama).total_seconds() > son_dk * 60:
        print(f"::warning title=Gönderilmedi::Maç başlayalı {son_dk:.0f} dakikadan fazla oldu")
        return

    # 3. İlk 11'leri bekle
    ilk11 = False
    if mac_no:
        bitis = time.time() + float(ortam("ILK11_BEKLE", "0")) * 60
        while True:
            try:
                d = api(skor_api, f"/api/mac?id={mac_no}")
                ilk11 = bool((d.get("kadro") or {}).get("ev") and (d.get("kadro") or {}).get("dep"))
            except Exception as e:  # noqa: BLE001
                print(f"::warning::Maç ayrıntısı okunamadı: {e}")
            if ilk11 or time.time() >= bitis or dry_run:
                break
            time.sleep(120)
    metin = ortam("METIN_ILK11") if ilk11 and ortam("METIN_ILK11") else (ortam("METIN_ONCE") or ortam("METIN_ILK11"))
    print(f"İlk 11'ler: {'açıklandı' if ilk11 else 'henüz yok'}")
    baslik = ortam("BASLIK") or "Maç Merkezi"
    bilgi = bp.sayfa_bilgisi(adres)
    yazi = {"adres": adres, "baslik": baslik}

    # 4. Bluesky (aynı zamanda "paylaşıldı" kaydı)
    handle, sifre = ortam("BLUESKY_HANDLE"), ortam("BLUESKY_APP_PASSWORD")
    did = token = pds = None
    if handle and sifre:
        did, token, pds = bp.oturum_ac(handle, sifre)
        if adres.rstrip("/") in bp.paylasilmis_adresler(pds, did, token):
            print(f"::notice title=Zaten paylaşılmış::{adres} — hiçbir yere tekrar gönderilmedi")
            return
        if istendi("bluesky"):
            kayit = bp.gonderi_olustur({"adres": adres, "baslik": metin}, bilgi.get("aciklama", ""), etiketler,
                                       None if dry_run else bp.kart_yukle(pds, token, bilgi.get("kart")))
            kayit["embed"]["external"]["title"] = baslik
            if dry_run:
                print("DRY_RUN Bluesky:", json.dumps(kayit["text"], ensure_ascii=False))
            else:
                try:
                    bp.http("POST", f"{pds}/xrpc/com.atproto.repo.createRecord",
                            {"repo": did, "collection": "app.bsky.feed.post", "record": kayit}, token=token)
                    print(f"::notice title=Bluesky'da paylaşıldı::{adres}")
                except Exception as e:  # noqa: BLE001
                    print(f"::warning title=Bluesky'a gönderilemedi::{e}")

    # 5. Telegram
    tg_token, tg_kanal = ortam("TELEGRAM_BOT_TOKEN"), ortam("TELEGRAM_CHANNEL")
    if tg_token and tg_kanal and istendi("telegram"):
        ilk, _, kalan = metin.partition("\n")
        govde = f"<b>{html.escape(ilk, quote=False)}</b>"
        if kalan.strip():
            govde += "\n" + html.escape(kalan.strip(), quote=False)
        govde += f'\n\n👉 <a href="{html.escape(adres, quote=True)}">{html.escape(baslik, quote=False)}</a>'
        if dry_run:
            print("DRY_RUN Telegram:", govde)
        else:
            try:
                bp.telegram_api(tg_token, "sendMessage", {
                    "chat_id": tg_kanal, "text": govde, "parse_mode": "HTML",
                    "link_preview_options": json.dumps({"url": adres, "prefer_large_media": True}),
                })
                print(f"::notice title=Telegram'a gönderildi::{tg_kanal}")
            except Exception as e:  # noqa: BLE001
                print(f"::warning title=Telegram'a gönderilemedi::{e}")

    # 6. Facebook, Instagram, Threads
    page_token, th_token = ortam("META_PAGE_TOKEN"), ortam("THREADS_TOKEN")
    alan = urllib.parse.urlsplit(adres).netloc
    ilk_etiket = (etiketler.split() or [""])[0]
    hedefler = []
    if page_token and (istendi("facebook") or istendi("instagram")):
        try:
            k = meta.sayfa_kimlikleri(page_token, ortam("META_SAYFA_ADI") or None)
            if istendi("facebook"):
                hedefler.append(("Facebook", lambda: meta.facebook_paylas(k["page_token"], k["page_id"],
                                                                         f"{metin}\n\n{etiketler}".strip(), adres)))
            if istendi("instagram") and k.get("ig_id") and bilgi.get("kare"):
                ig_metin = f"{metin}\n\n👉 Bağlantı profilde: {alan}\n\n{ig_etiketler}".strip()
                hedefler.append(("Instagram", lambda: meta.instagram_paylas(k["page_token"], k["ig_id"],
                                                                           bilgi["kare"], ig_metin)))
        except Exception as e:  # noqa: BLE001
            print(f"::warning title=Facebook/Instagram atlandı::{e}")
    if th_token and istendi("threads"):
        th_metin = meta.kisalt(metin, meta.THREADS_SINIRI - len(ilk_etiket) - 2) + (f"\n\n{ilk_etiket}" if ilk_etiket else "")
        hedefler.append(("Threads", lambda: meta.threads_paylas(th_token, th_metin, adres)))
    for ad, gorev in hedefler:
        if dry_run:
            print(f"DRY_RUN {ad}: hazır")
            continue
        try:
            gorev()
            print(f"::notice title={ad} paylaşıldı::{adres}")
        except Exception as e:  # noqa: BLE001
            print(f"::warning title={ad} gönderilemedi::{e}")

    # 7. Rakibin aynı duyurusuna Bluesky'da tek satır laf sokma (kayfabe)
    rakip, cevap = ortam("RAKIP_BLUESKY"), ortam("RAKIP_CEVAP")
    if did and rakip and cevap and mac_no and istendi("bluesky"):
        hedef = bsky_ek.link_iceren_gonderi(rakip, f"/mac/?id={mac_no}", 0 if dry_run else float(ortam("RAKIP_BEKLE", "40")))
        if not hedef:
            print(f"::warning title=Rakibe cevap yazılmadı::{rakip} gönderisi bulunamadı")
        elif dry_run:
            print("DRY_RUN rakibe cevap:", cevap)
        else:
            try:
                bsky_ek.gonder(pds, did, token, cevap, cevap=hedef)
                print(f"::notice title=Rakibe cevap yazıldı::{rakip}")
            except Exception as e:  # noqa: BLE001
                print(f"::warning title=Rakibe cevap yazılamadı::{e}")


if __name__ == "__main__":
    main()
