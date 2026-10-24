#!/usr/bin/env python3
"""Meta anahtarlarının sağlık kontrolü ve Threads anahtarının yenilenmesi.

- META_PAGE_TOKEN: süresizdir; yalnızca çalışıp çalışmadığı kontrol edilir.
- THREADS_TOKEN: 60 gün geçerlidir; burada yenilenir. Yeni anahtar, YENI_ANAHTAR
  ortam değişkeninin gösterdiği dosyaya yazılır (iş akışı onu GitHub secret'ına
  kaydeder). Anahtar hiçbir zaman ekrana yazılmaz.

Bir anahtar çalışmazsa iş hata ile biter; GitHub sahibine e-posta gönderir.
"""

import os
import sys

import meta


def main():
    page_token = os.environ.get("META_PAGE_TOKEN", "").strip()
    th_token = os.environ.get("THREADS_TOKEN", "").strip()
    cikti = os.environ.get("YENI_ANAHTAR", "").strip()
    sorun = False

    if page_token:
        try:
            k = meta.sayfa_kimlikleri(page_token, os.environ.get("META_SAYFA_ADI") or None)
            print(f"::notice title=Facebook anahtarı::Çalışıyor ({k['page_name']}; Instagram @{k['ig_username']})")
        except Exception as e:  # noqa: BLE001
            sorun = True
            print(f"::error title=Facebook anahtarı çalışmıyor::{e} — yeni Sayfa anahtarı alınmalı (rehberdeki adımlar).")

    if th_token:
        try:
            yeni, gun = meta.threads_yenile(th_token)
            ayni = "aynı anahtar uzatıldı" if yeni == th_token else "yeni anahtar verildi"
            print(f"::notice title=Threads anahtarı yenilendi::{gun} gün geçerli ({ayni}).")
            if cikti:
                with open(cikti, "w") as f:
                    f.write(yeni)
        except Exception as e:  # noqa: BLE001
            # Anahtar hâlâ çalışıyorsa (ör. 24 saatten yeni) bu bir hata değil
            try:
                u = meta.threads_kullanici(th_token)
                print(f"::warning title=Threads anahtarı bu sefer yenilenmedi::Anahtar geçerli "
                      f"(@{u.get('username')}); muhtemelen 24 saatten yeni. Bir sonraki çalışmada yenilenir. ({e})")
            except Exception:  # noqa: BLE001
                sorun = True
                print(f"::error title=Threads anahtarı çalışmıyor::{e} — süresi dolmuş olabilir; yenisi alınmalı (rehberdeki adımlar).")

    if sorun:
        sys.exit(1)


if __name__ == "__main__":
    main()
