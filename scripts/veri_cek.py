#!/usr/bin/env python3
"""Derlemeden önce skor API'mizden verileri çeker; Hugo bunları sayfalara HTML olarak gömer.

"Siteyi yayınla" iş akışında Hugo'dan hemen önce çalışır. Yazdıkları (depoya commit'lenmez):
  data/veri/puan.json, krallar.json, sakat.json, avrupa.json, milli.json, gurbetci.json,
  transferler.json, fikstur.json
  data/veri/takim/<slug>.json           18 takım (sayfa: /takim/<slug>/)
  data/veri/mac/<maç no>.json           yakın tarihli maçların ayrıntısı (önbellekte birikir)
  content/maclar/<sezon>/<ev>-<dep>.md  sezonun her Süper Lig maçı için sayfa

Bir veri alınamazsa uyarı yazar ve devam eder; sayfalar o zaman yalnızca tarayıcıda yüklenen
veriyle çalışır (eskisi gibi). Hiçbir durumda derlemeyi durdurmaz.

Ortam: SKOR_API (yoksa hugo.toml'daki skorAPI), MAC_GERI_GUN (3), MAC_ILERI_GUN (2).
Yalnızca Python standart kütüphanesi.
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
VERI = KOK / "data" / "veri"
MACLAR = KOK / "content" / "maclar"
UA = "HadiYuruDerleme/1.0 (+https://github.com/sevketirtem)"

# Takım sayfası adresleri — assets/js/adlar.js'teki SLUG ile aynı olmalı
SLUG = {
    "galatasaray": "galatasaray", "fenerbahce": "fenerbahce", "besiktas": "besiktas", "trabzonspor": "trabzonspor",
    "kasimpasa": "kasimpasa", "kocaelispor": "kocaelispor", "erzurumspor": "erzurumspor", "corum": "corum-fk",
    "goztepe": "goztepe", "alanyaspor": "alanyaspor", "basaksehir": "basaksehir", "rizespor": "rizespor",
    "konyaspor": "konyaspor", "gaziantep": "gaziantep-fk", "genclerbirligi": "genclerbirligi", "samsunspor": "samsunspor",
    "eyupspor": "eyupspor", "amed": "amedspor", "amedspor": "amedspor",
}
# Türkçe yazım — adlar.js'teki AD ile uyumlu
AD = {
    "Fenerbahce": "Fenerbahçe", "Besiktas": "Beşiktaş", "Istanbul Basaksehir": "Başakşehir", "Basaksehir": "Başakşehir",
    "Kasimpasa": "Kasımpaşa", "Goztepe": "Göztepe", "Eyupspor": "Eyüpspor", "Rizespor": "Çaykur Rizespor",
    "Caykur Rizespor": "Çaykur Rizespor", "Genclerbirligi": "Gençlerbirliği", "Gençlerbirliği S.K.": "Gençlerbirliği",
    "Amed SK": "Amedspor", "Amed": "Amedspor", "Gaziantep": "Gaziantep FK", "Corum FK": "Çorum FK",
    "Erzurumspor FK": "Erzurumspor", "Turkey": "Türkiye",
}


def sade(s):
    """adlar.js'teki sade() ile birebir: 'Gençlerbirliği S.K.' → 'genclerbirligi'."""
    s = str(s or "").replace("ı", "i").replace("İ", "I")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()
    s = re.sub(r"\b(s|a)\.(k|s)\.?", " ", s)
    s = re.sub(r"\b(fk|sk|as)\b", " ", s).strip()
    s = re.sub(r"^(istanbul|caykur)\s+", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def takim_slug(ad):
    return SLUG.get(sade(ad)) or sade(ad).replace(" ", "-")


def sezon_adi(sezon):
    return f"{sezon}-{str(int(sezon) + 1)[-2:]}"


def mac_yolu(m, sezon):
    """Maç sayfasının kalıcı adresi: /maclar/2026-27/galatasaray-fenerbahce/ (ertelense de değişmez)."""
    return f"{sezon_adi(sezon)}/{takim_slug(m['ev'])}-{takim_slug(m['dep'])}"


def sezon_tarihten(iso):
    """Maç tarihinden sezon: Temmuz ve sonrası o yılın sezonu (adlar.js'teki macYolu ile aynı)."""
    yil, ay = int(iso[:4]), int(iso[5:7])
    return str(yil if ay >= 7 else yil - 1)


_b = datetime.now(timezone.utc)
BU_SEZON = str(_b.year if _b.month >= 7 else _b.year - 1)


def zenginlestir(x):
    """Şablonların doğrudan kullanacağı alanları ekler: Türkçe ad, takım adresi, maç sayfası yolu."""
    if isinstance(x, list):
        for o in x:
            zenginlestir(o)
    elif isinstance(x, dict):
        if isinstance(x.get("ev"), str) and isinstance(x.get("dep"), str):
            x["evAd"], x["depAd"] = AD.get(x["ev"], x["ev"]), AD.get(x["dep"], x["dep"])
            x["evSlug"], x["depSlug"] = takim_slug(x["ev"]), takim_slug(x["dep"])
            if x.get("ligId") in (203, "203") and x.get("tarih") and sezon_tarihten(x["tarih"]) == BU_SEZON:
                x["yol"] = f"/maclar/{mac_yolu(x, sezon_tarihten(x['tarih']))}/"
        if isinstance(x.get("takim"), str):
            x["takimAd"], x["takimSlug"] = AD.get(x["takim"], x["takim"]), takim_slug(x["takim"])
        for v in x.values():
            if isinstance(v, (list, dict)):
                zenginlestir(v)
    return x


def uyar(mesaj):
    print(f"::warning title=Veri çekme::{mesaj}")


def getir(api, yol, deneme=2):
    for i in range(deneme):
        try:
            req = urllib.request.Request(f"{api}{yol}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            ayrinti = ""
            if hasattr(e, "read"):
                try:
                    ayrinti = " " + e.read().decode("utf-8", "replace")[:200]
                except Exception:  # noqa: BLE001
                    pass
            if i + 1 == deneme:
                uyar(f"{yol}: {e}{ayrinti}")
                return None
            time.sleep(35)  # hata yanıtı 30 sn önbellekte kalır


def yaz(yol, veri):
    zenginlestir(veri)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")


def skor_api():
    if os.environ.get("SKOR_API"):
        return os.environ["SKOR_API"].rstrip("/")
    m = re.search(r'^\s*skorAPI\s*=\s*"([^"]*)"', (KOK / "hugo.toml").read_text(encoding="utf-8"), re.M)
    return (m.group(1) if m else "").rstrip("/")


def tirnak(s):
    return json.dumps(str(s), ensure_ascii=False)


def mac_sayfalari(fikstur):
    """Sezonun her Süper Lig maçı için content/maclar/<sezon>/<ev>-<dep>.md üretir."""
    sezon = fikstur.get("sezon", "2026")
    sayi = 0
    for m in fikstur.get("maclar", []):
        yol = MACLAR / f"{mac_yolu(m, sezon)}.md"
        ev, dep = AD.get(m["ev"], m["ev"]), AD.get(m["dep"], m["dep"])
        gun = m["tarih"][:10]
        yil, ay, g = gun.split("-")
        aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        tarih_metni = f"{int(g)} {aylar[int(ay) - 1]} {yil}"
        hafta = m.get("hafta") or "?"
        saat = m["tarih"][11:16]
        bitti = m.get("durum") in ("FT", "AET", "PEN") and m.get("evGol") is not None
        # Başlıklar insanların aradığı biçimde: maçtan önce "ne zaman, saat kaçta", sonra skor
        if bitti:
            baslik = f"{ev} {m['evGol']}-{m['depGol']} {dep}: maç sonucu, goller ve istatistikler ({tarih_metni})"
            aciklama = (f"{ev} - {dep} maçı {m['evGol']}-{m['depGol']} bitti. Süper Lig {hafta}. hafta: goller, kartlar, "
                        "ilk 11'ler, istatistikler ve iki takımın puan durumu.")
        else:
            baslik = f"{ev} - {dep} maçı ne zaman, saat kaçta? İlk 11'ler ve canlı skor ({tarih_metni})"
            aciklama = (f"Süper Lig {hafta}. hafta: {ev} - {dep} maçı {tarih_metni}, saat {saat} (TSİ). "
                        "İlk 11'ler, canlı skor, goller, istatistikler ve son karşılaşmalar.")
        satirlar = [
            "---",
            f"title: {tirnak(baslik)}",
            f"linkTitle: {tirnak(ev + ' - ' + dep)}",
            f"description: {tirnak(aciklama)}",
            f"macId: {m['id']}",
            f"tarih: {tirnak(m['tarih'])}",
            f"hafta: {tirnak(m.get('hafta') or '')}",
            f"ev: {tirnak(m['ev'])}",
            f"dep: {tirnak(m['dep'])}",
            f"evSlug: {tirnak(takim_slug(m['ev']))}",
            f"depSlug: {tirnak(takim_slug(m['dep']))}",
            f"stat: {tirnak(m.get('stat') or '')}",
            f"sehir: {tirnak(m.get('sehir') or '')}",
            f"hakem: {tirnak(m.get('hakem') or '')}",
            f"durum: {tirnak(m.get('durum') or '')}",
            f"evGol: {m['evGol'] if m.get('evGol') is not None else 'null'}",
            f"depGol: {m['depGol'] if m.get('depGol') is not None else 'null'}",
            "---",
            "",
        ]
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text("\n".join(satirlar), encoding="utf-8")
        sayi += 1
    return sayi


def main():
    api = skor_api()
    if not api:
        print("skorAPI tanımlı değil; veri çekilmedi.")
        return
    simdi = datetime.now(timezone.utc)
    sayac = {}

    # Tek istekli listeler
    tekler = {"puan": "/api/puan", "krallar": "/api/krallar", "sakat": "/api/sakat", "avrupa": "/api/avrupa",
              "fikstur": "/api/fikstur", "maclar": "/api/maclar", "milli": "/api/milli"}
    with ThreadPoolExecutor(4) as havuz:
        sonuc = dict(zip(tekler, havuz.map(lambda y: getir(api, y), tekler.values())))
    # Çok istekli olanlar (transferler ~19, gurbetçi ~28) tek tek
    for ad, yol in (("transferler", "/api/transferler"), ("gurbetci", "/api/gurbetci")):
        sonuc[ad] = getir(api, yol)
    for ad, veri in sonuc.items():
        if veri is not None:
            yaz(VERI / f"{ad}.json", veri)
            sayac[ad] = "✓"

    # Takım sayfaları
    tablo = (sonuc.get("puan") or {}).get("tablo") or []
    # Sırayla ve aralıklı: her takım 6 API-Football isteği; Pro plan dakikada 300 istekle sınırlı.
    # Yanıtlar 3 saat önbellekte; önbellekteyse bekleme kısa sürer.
    takimlar = []
    for satir in tablo:
        bas = time.time()
        takimlar.append((satir, getir(api, f"/api/takim?id={satir['id']}")))
        if time.time() - bas > 1:  # gerçekten API'ye gittiyse biraz nefes al
            time.sleep(2)
    for satir, veri in takimlar:
        if veri:
            yaz(VERI / "takim" / f"{takim_slug(satir['takim'])}.json", veri)
    sayac["takım"] = sum(1 for _, v in takimlar if v)

    # Maç sayfaları + yakın maçların ayrıntısı
    fikstur = sonuc.get("fikstur")
    if fikstur:
        sayac["maç sayfası"] = mac_sayfalari(fikstur)
        geri = timedelta(days=float(os.environ.get("MAC_GERI_GUN", "3")))
        ileri = timedelta(days=float(os.environ.get("MAC_ILERI_GUN", "2")))
        yakin = [m for m in fikstur.get("maclar", [])
                 if simdi - geri <= datetime.fromisoformat(m["tarih"]) <= simdi + ileri]
        with ThreadPoolExecutor(6) as havuz:
            detay = list(havuz.map(lambda m: (m["id"], getir(api, f"/api/mac?id={m['id']}")), yakin))
        for mid, veri in detay:
            if veri:
                yaz(VERI / "mac" / f"{mid}.json", veri)
        sayac["maç ayrıntısı"] = sum(1 for _, v in detay if v)
        onceki = len(list((VERI / "mac").glob("*.json"))) if (VERI / "mac").exists() else 0
        sayac["önbellekteki maç"] = onceki

    print("::notice title=Veri çekme::" + ", ".join(f"{k}: {v}" for k, v in sayac.items()))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — derleme hiçbir zaman bu yüzden durmasın
        uyar(f"beklenmeyen hata: {e}")
    sys.exit(0)
