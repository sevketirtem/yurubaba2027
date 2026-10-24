#!/usr/bin/env python3
"""İleri tarihli yazıları zamanı gelince yayına sokar.

GitHub'ın zamanlanmış (cron) derlemesi güvenilir değil: "saatte bir" diye
kurulsa da pratikte 4-6 saatte bir çalışıyor. Bu betik push'tan sonra
content/posts altındaki ileri tarihli yazıları bulur, her birinin saati
gelene kadar bekler ve "Siteyi yayınla" iş akışını (hugo.yml) tetikler.
Ardından paylaşım botu kendiliğinden çalışmadıysa onu da tetikler.

Yalnızca standart kütüphane + GitHub Actions'taki `gh` komutu kullanılır.

Ortam değişkenleri:
  EN_FAZLA_BEKLEME_DK  Bu kadar dakikadan uzak yazılar beklenmez (varsayılan 340;
                       GitHub işi en fazla 6 saat sürebilir). Onları cron yakalar.
  SADECE_LISTELE       "true" ise beklemez/tetiklemez, sadece ne yapacağını yazar.
"""
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys
import time

YAZI_KLASORU = "content/posts"
EN_FAZLA_BEKLEME = dt.timedelta(minutes=int(os.environ.get("EN_FAZLA_BEKLEME_DK", "340")))
SADECE_LISTELE = os.environ.get("SADECE_LISTELE", "false").lower() == "true"
PAYLASIM_BEKLEME_SN = 300  # derleme + paylaşım botunun başlaması için süre


def on_bilgi(yol):
    """Dosyanın baştaki --- ... --- bloğundan date ve draft değerlerini okur."""
    with open(yol, encoding="utf-8") as f:
        metin = f.read()
    m = re.match(r"^---\s*\n(.*?)\n---", metin, re.S)
    if not m:
        return None, False
    blok = m.group(1)
    tarih = re.search(r"^date:\s*[\"']?([^\"'\n]+)", blok, re.M)
    taslak = re.search(r"^draft:\s*true\b", blok, re.M)
    if not tarih:
        return None, bool(taslak)
    try:
        t = dt.datetime.fromisoformat(tarih.group(1).strip())
    except ValueError:
        return None, bool(taslak)
    if t.tzinfo is None:  # site saati İstanbul
        t = t.replace(tzinfo=dt.timezone(dt.timedelta(hours=3)))
    return t, bool(taslak)


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def bildir(seviye, mesaj):
    print(f"::{seviye}::{mesaj}", flush=True)


def tetikle_ve_kontrol_et(zaman):
    baslangic = dt.datetime.now(dt.timezone.utc)
    gh("workflow", "run", "hugo.yml", "--ref", "main")
    bildir("notice title=Derleme tetiklendi", f"{zaman.isoformat()} saatli yazı(lar) için")

    # Paylaşım botu normalde derleme bitince kendiliğinden çalışır (workflow_run).
    # GITHUB_TOKEN ile tetiklenen derlemelerde bu zincir çalışmayabilir; kontrol edip
    # gerekirse botu elle tetikleriz. Bot zaten paylaşılmış yazıları atladığı için
    # iki kez çalışması çift gönderi yapmaz (aynı anda da çalışmaz: concurrency).
    time.sleep(PAYLASIM_BEKLEME_SN)
    kosular = json.loads(gh("run", "list", "--workflow", "bluesky.yml", "--limit", "5",
                            "--json", "createdAt"))
    yeni = [k for k in kosular
            if dt.datetime.fromisoformat(k["createdAt"].replace("Z", "+00:00")) >= baslangic]
    if yeni:
        bildir("notice", "Paylaşım botu kendiliğinden çalıştı.")
    else:
        gh("workflow", "run", "bluesky.yml", "--ref", "main", "-f", "dry_run=false")
        bildir("notice title=Paylaşım botu tetiklendi", "derleme sonrası kendiliğinden başlamadığı için")


def main():
    simdi = dt.datetime.now(dt.timezone.utc)
    zamanlar = set()
    uzak = []
    for yol in sorted(glob.glob(os.path.join(YAZI_KLASORU, "*.md"))):
        t, taslak = on_bilgi(yol)
        if t is None or taslak or t <= simdi:
            continue
        if t - simdi <= EN_FAZLA_BEKLEME:
            zamanlar.add(t.astimezone(dt.timezone.utc))
        else:
            uzak.append((yol, t))

    for yol, t in uzak:
        bildir("warning title=Çok ileri tarihli yazı",
               f"{yol} ({t.isoformat()}) bu iş tarafından beklenmeyecek; saatlik derlemeye kaldı.")

    if not zamanlar:
        print("Beklenecek ileri tarihli yazı yok.")
        return 0

    for zaman in sorted(zamanlar):
        bekle = (zaman - dt.datetime.now(dt.timezone.utc)).total_seconds() + 60
        print(f"{zaman.isoformat()} için {max(0, int(bekle))} sn beklenecek.", flush=True)
        if SADECE_LISTELE:
            continue
        if bekle > 0:
            time.sleep(bekle)
        tetikle_ve_kontrol_et(zaman)
    return 0


if __name__ == "__main__":
    sys.exit(main())
