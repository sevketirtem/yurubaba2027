"""Dünün (İstanbul saatiyle) ziyaretçi özetini GoatCounter API'sinden okur.

Çıktı GitHub Actions notice'i olarak yazılır; sabah görevi bunu check-run
annotations'tan okur. Yalnızca Python standart kütüphanesi.

Gerekenler:
  GOATCOUNTER_TOKEN  GoatCounter → API → "Read statistics" izinli anahtar (secret)
  GOATCOUNTER_KOD    hadibaba / yurubaba (yoksa hugo.toml'dan okunur)
  GUN                isteğe bağlı, YYYY-AA-GG (boş = dün)
  AY                 isteğe bağlı, YYYY-AA ya da "gecen" → aylık trend (görüntüleme,
                     önceki aya göre değişim, gelir senaryosu); GUN yok sayılır
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


# Aylık trend: Türkiye trafiğinde 1.000 görüntüleme başına tahmini AdSense geliri (USD)
RPM_ALT, RPM_UST = 0.40, 1.50
# Senaryo eşikleri (günlük ortalama görüntüleme; ~1,5 görüntüleme = 1 ziyaret)
SENARYOLAR = [
    (60, "Sabit (haftada ~100 ziyaret düzeyi)"),
    (150, "Sabit → orta arası"),
    (600, "Orta (günde ~100+ ziyaret)"),
    (1500, "Orta → iyi arası"),
    (float("inf"), "İyi (günde ~1.000 ziyaret)"),
]


def sade_ad(h):
    return re.sub(r"\s+·\s+(Hadi|Yürü) Baba.*$", "", (h.get("title") or h.get("path") or "?").strip())


def ay_araligi(yil, ay):
    bas = date(yil, ay, 1)
    son = date(yil + (ay == 12), ay % 12 + 1, 1)
    return bas, son


# Siteler 23 Ekim 2026'da açıldı; öncesi günlük ortalamayı düşürmesin
LANSMAN = date(2026, 10, 23)


def toplam_oku(kod, token, bas_gun, son_gun):
    bas_gun = max(bas_gun, LANSMAN)
    if bas_gun >= son_gun:
        return 0, 1, None
    bas = datetime.combine(bas_gun, time(0, 0), IST).astimezone(timezone.utc)
    son = datetime.combine(son_gun, time(0, 0), IST).astimezone(timezone.utc)
    simdi = datetime.now(timezone.utc)
    if son > simdi:
        son = simdi.replace(minute=0, second=0, microsecond=0)  # API saat başı ister
    params = {"start": bas.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": son.strftime("%Y-%m-%dT%H:%M:%SZ")}
    gun_sayisi = max((son - bas).total_seconds() / 86400, 1 / 24)
    return iste(kod, token, "stats/total", params).get("total", 0), gun_sayisi, params


def aylik(kod, token, ay_str):
    bugun = datetime.now(IST).date()
    if ay_str.lower() in ("gecen", "geçen"):
        ilk = bugun.replace(day=1) - timedelta(days=1)
        yil, ay = ilk.year, ilk.month
    else:
        yil, ay = (int(x) for x in ay_str.split("-")[:2])
    bas, son = ay_araligi(yil, ay)
    if bas > bugun or son <= LANSMAN:
        print(f"::warning title=Aylık trend::{yil}-{ay:02d} için veri yok (gelecek ay ya da lansman öncesi).")
        return 0
    onceki_bas = (bas - timedelta(days=1)).replace(day=1)

    adim = "bu ay toplam"
    try:
        bu_ay, gun, params = toplam_oku(kod, token, bas, son)
        adim = "önceki ay toplam"
        onceki, onceki_gun, _ = toplam_oku(kod, token, onceki_bas, bas)
        adim = "en çok okunanlar"
        sayfalar = iste(kod, token, "stats/hits", {**params, "limit": 3})
    except urllib.error.HTTPError as e:
        print(f"::error title=Aylık trend::GoatCounter {e.code} ({adim}, {e.url}): {e.read().decode('utf-8','replace')[:200]}")
        return 1
    except Exception as e:
        print(f"::error title=Aylık trend::{type(e).__name__}: {e}")
        return 1

    gunluk = bu_ay / gun
    onceki_gunluk = onceki / onceki_gun if onceki else 0
    if onceki_gunluk:
        degisim = f"{(gunluk / onceki_gunluk - 1) * 100:+.0f}% (günlük ort., önceki ay {onceki_gunluk:.1f})"
    else:
        degisim = "önceki ay verisi yok"
    senaryo = next(ad for esik, ad in SENARYOLAR if gunluk < esik)
    aylik_tahmin = gunluk * 30.4
    gelir_ay = (aylik_tahmin * RPM_ALT / 1000, aylik_tahmin * RPM_UST / 1000)
    gelir_yil = (gelir_ay[0] * 12, gelir_ay[1] * 12)
    eksik = " (ay sürüyor)" if son > bugun else ""
    ust = " | ".join(
        "{}: {}".format(sade_ad(h), h.get("count", 0)) for h in sayfalar.get("hits", [])[:3]
    ) or "—"

    metin = (
        f"{yil}-{ay:02d}{eksik}: {bu_ay} görüntüleme, günde ort. {gunluk:.1f} | Değişim: {degisim} | "
        f"Senaryo: {senaryo} | Bu hızla reklam geliri ≈ ayda {gelir_ay[0]:.2f}–{gelir_ay[1]:.2f} $, "
        f"yılda {gelir_yil[0]:.0f}–{gelir_yil[1]:.0f} $ (RPM {RPM_ALT}–{RPM_UST} $) | En çok: {ust}"
    )
    print(f"::notice title=Aylık trend {kod} {yil}-{ay:02d}::{metin}")
    ozet = os.environ.get("GITHUB_STEP_SUMMARY")
    if ozet:
        with open(ozet, "a", encoding="utf-8") as f:
            f.write(f"## {kod} — {yil}-{ay:02d} aylık trend\n\n- {metin.replace(' | ', chr(10) + '- ')}\n")
    return 0


def main():
    token = os.environ.get("GOATCOUNTER_TOKEN", "").strip()
    kod = kod_bul()
    if not token or not kod:
        print("::warning title=Ziyaretçi raporu::GOATCOUNTER_TOKEN secret'ı ya da site kodu yok; rapor atlandı.")
        return 0

    ay_str = os.environ.get("AY", "").strip()
    if ay_str:
        return aylik(kod, token, ay_str)

    gun_str = os.environ.get("GUN", "").strip()
    gun = date.fromisoformat(gun_str) if gun_str else datetime.now(IST).date() - timedelta(days=1)
    bas = datetime.combine(gun, time(0, 0), IST).astimezone(timezone.utc)
    son = bas + timedelta(days=1)
    params = {"start": bas.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": son.strftime("%Y-%m-%dT%H:%M:%SZ")}

    yol = "stats/total"
    try:
        toplam = iste(kod, token, yol, params)
        yol = "stats/hits"
        sayfalar = iste(kod, token, yol, {**params, "limit": 5})
    except urllib.error.HTTPError as e:
        govde = e.read().decode("utf-8", "replace")[:200]
        print(f"::error title=Ziyaretçi raporu::GoatCounter {e.code} ({e.url} ← {yol}): {govde}")
        try:
            me = iste(kod, token, "me", {})
            print(f"::notice title=Ziyaretçi raporu tanı::/me çalışıyor: {json.dumps(me)[:300]}")
        except urllib.error.HTTPError as e2:
            print(f"::notice title=Ziyaretçi raporu tanı::/me {e2.code}: {e2.read().decode('utf-8','replace')[:200]}")
        return 1
    except Exception as e:  # ağ hatası vb.
        print(f"::error title=Ziyaretçi raporu::{type(e).__name__}: {e}")
        return 1

    ziyaret = toplam.get("total", 0)
    satirlar = []
    for h in sayfalar.get("hits", [])[:5]:
        sayi = h.get("count", h.get("count_unique", 0))
        ad = re.sub(r"\s+·\s+(Hadi|Yürü) Baba.*$", "", (h.get("title") or h.get("path") or "?").strip())
        satirlar.append(f"{ad} ({h.get('path')}): {sayi}")
    ust = " | ".join(satirlar) if satirlar else "—"
    print(f"::notice title=Ziyaretçi {kod} {gun.isoformat()}::Toplam {ziyaret} görüntüleme | En çok: {ust}")

    ozet = os.environ.get("GITHUB_STEP_SUMMARY")
    if ozet:
        with open(ozet, "a", encoding="utf-8") as f:
            f.write(f"## {kod} — {gun.isoformat()} ziyaretçileri\n\nToplam: **{ziyaret}**\n\n")
            for s in satirlar:
                f.write(f"- {s}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
