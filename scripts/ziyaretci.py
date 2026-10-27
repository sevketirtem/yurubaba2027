"""Dünün (İstanbul saatiyle) ziyaretçi özetini GoatCounter API'sinden okur.

Çıktı GitHub Actions notice'i olarak yazılır; sabah görevi bunu check-run
annotations'tan okur. Yalnızca Python standart kütüphanesi.

Gerekenler:
  GOATCOUNTER_TOKEN  GoatCounter → API → "Read statistics" izinli anahtar (secret)
  GOATCOUNTER_KOD    hadibaba / yurubaba (yoksa hugo.toml'dan okunur)
  GUN                isteğe bağlı, YYYY-AA-GG (boş = dün)
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=3))  # Türkiye yaz/kış saati uygulamıyor


def kod_bul():
    kod = os.environ.get("GOATCOUNTER_KOD", "").strip()
    if kod:
        return kod
    try:
        with open("hugo.toml", encoding="utf-8") as f:
            m = re.search(r'^\s*goatcounter\s*=\s*"([^"]+)"', f.read(), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def iste(kod, token, yol, params):
    adres = f"https://{kod}.goatcounter.com/api/v0/{yol}?" + urllib.parse.urlencode(params)
    istek = urllib.request.Request(adres, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "hadiyuru-rapor",
    })
    with urllib.request.urlopen(istek, timeout=30) as yanit:
        return json.load(yanit)


def main():
    token = os.environ.get("GOATCOUNTER_TOKEN", "").strip()
    kod = kod_bul()
    if not token or not kod:
        print("::warning title=Ziyaretçi raporu::GOATCOUNTER_TOKEN secret'ı ya da site kodu yok; rapor atlandı.")
        return 0

    gun_str = os.environ.get("GUN", "").strip()
    gun = date.fromisoformat(gun_str) if gun_str else datetime.now(IST).date() - timedelta(days=1)
    bas = datetime.combine(gun, time(0, 0), IST).astimezone(timezone.utc)
    son = bas + timedelta(days=1)
    params = {"start": bas.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": son.strftime("%Y-%m-%dT%H:%M:%SZ")}

    try:
        toplam = iste(kod, token, "stats/total", params)
        sayfalar = iste(kod, token, "stats/hits", {**params, "limit": 5})
    except urllib.error.HTTPError as e:
        govde = e.read().decode("utf-8", "replace")[:200]
        print(f"::error title=Ziyaretçi raporu::GoatCounter {e.code}: {govde}")
        return 1
    except Exception as e:  # ağ hatası vb.
        print(f"::error title=Ziyaretçi raporu::{type(e).__name__}: {e}")
        return 1

    ziyaret = toplam.get("total", 0)
    satirlar = []
    for h in sayfalar.get("hits", [])[:5]:
        sayi = h.get("count", h.get("count_unique", 0))
        ad = (h.get("title") or h.get("path") or "?").strip()
        satirlar.append(f"{ad} ({h.get('path')}): {sayi}")
    ust = " | ".join(satirlar) if satirlar else "—"
    print(f"::notice title=Ziyaretçi {kod} {gun.isoformat()}::Toplam {ziyaret} | En çok: {ust}")

    ozet = os.environ.get("GITHUB_STEP_SUMMARY")
    if ozet:
        with open(ozet, "a", encoding="utf-8") as f:
            f.write(f"## {kod} — {gun.isoformat()} ziyaretçileri\n\nToplam: **{ziyaret}**\n\n")
            for s in satirlar:
                f.write(f"- {s}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
