#!/usr/bin/env python3
"""Yayından sonra değişen sayfaları IndexNow ile Yandex ve Bing'e bildirir.

Türkiye'de aramaların büyük kısmı Google'ın yanında Yandex'te (Statcounter, Kasım 2025: ~%38).
Google IndexNow kullanmaz; Google için site haritası yeterli (Search Console'a gönderildi).

Nasıl çalışır:
  1. Derlenmiş sitenin (SITE_KLASORU, ör. _site) her index.html'inin "imzasını" çıkarır
     (sürekli değişen "Son güncelleme" satırları hariç).
  2. Önceki çalışmanın imzalarıyla (IMZA_DOSYASI, Actions önbelleğinde saklanır) karşılaştırır.
  3. Yeni ya da değişen adresleri Yandex ve Bing'e gönderir (en fazla 10.000).
  4. Gönderim başarılıysa imzaları kaydeder; başarısızsa bir sonraki çalışmada yeniden dener.

Anahtar: static/<anahtar>.txt (içinde yalnızca anahtar). Ortam: SITE_KLASORU, IMZA_DOSYASI.
Hiçbir durumda iş akışını durdurmaz. Yalnızca standart kütüphane.
"""

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
UCLAR = ["https://yandex.com/indexnow", "https://www.bing.com/indexnow"]
ATLA = re.compile(r"^/(mac/|404\.html|kategoriler/.+/page/|page/)")
OYNAK = re.compile(r"Son güncelleme[^<]*|integrity=\S+|/js/[\w.-]+\.js|/css/[\w.-]+\.css")


def ayar():
    toml = (KOK / "hugo.toml").read_text(encoding="utf-8")
    taban = re.search(r'^baseURL\s*=\s*"([^"]+)"', toml, re.M).group(1).rstrip("/")
    anahtarlar = [p.stem for p in (KOK / "static").glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", p.stem)]
    return taban, (anahtarlar[0] if anahtarlar else None)


def imzalar(klasor):
    out = {}
    for dosya in klasor.rglob("index.html"):
        yol = "/" + str(dosya.parent.relative_to(klasor)).replace("\\", "/").strip(".") + "/"
        yol = re.sub(r"/+", "/", yol)
        if ATLA.match(yol):
            continue
        metin = dosya.read_text(encoding="utf-8", errors="replace")
        if 'content="noindex' in metin or "content=noindex" in metin:
            continue
        out[yol] = hashlib.sha1(OYNAK.sub("", metin).encode()).hexdigest()
    return out


def gonder(uc, taban, anahtar, adresler):
    host = taban.split("://", 1)[1]
    govde = json.dumps({"host": host, "key": anahtar, "keyLocation": f"{taban}/{anahtar}.txt",
                        "urlList": adresler}).encode()
    req = urllib.request.Request(uc, data=govde, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def main():
    klasor = Path(os.environ.get("SITE_KLASORU", "public"))
    imza_dosyasi = Path(os.environ.get("IMZA_DOSYASI", ".indexnow/imzalar.json"))
    taban, anahtar = ayar()
    if not anahtar:
        print("::warning title=IndexNow::static/ altında anahtar dosyası yok; atlandı")
        return
    simdi = imzalar(klasor)
    once = json.loads(imza_dosyasi.read_text()) if imza_dosyasi.exists() else {}
    degisen = sorted(y for y, h in simdi.items() if once.get(y) != h)
    if not degisen:
        print("::notice title=IndexNow::Değişen sayfa yok")
        return
    adresler = [taban + y for y in degisen][:10000]
    basarili = False
    sonuc = []
    for uc in UCLAR:
        durum, ayrinti = gonder(uc, taban, anahtar, adresler)
        sonuc.append(f"{uc.split('/')[2]}: {durum}{(' ' + ayrinti) if ayrinti else ''}")
        basarili = basarili or durum in (200, 202)
    if basarili:
        imza_dosyasi.parent.mkdir(parents=True, exist_ok=True)
        imza_dosyasi.write_text(json.dumps(simdi))
        print(f"::notice title=IndexNow::{len(adresler)} adres bildirildi ({'; '.join(sonuc)}). Örnek: {', '.join(degisen[:5])}")
    else:
        print(f"::warning title=IndexNow::Gönderilemedi, sonraki yayında yeniden denenecek ({'; '.join(sonuc)})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"::warning title=IndexNow::beklenmeyen hata: {e}")
    sys.exit(0)
