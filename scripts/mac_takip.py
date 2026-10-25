#!/usr/bin/env python3
"""Maçı canlı izler; her golü ve maç sonucunu karakterin ağzından sosyal medyada paylaşır.

Kendi skor API'mizi (/api/maclar, /api/mac) yoklar. Bir gol olayı en az ONAY_SN saniye
listede kalırsa (VAR iptallerine karşı) paylaşılır. Maç bitince "maç sonu" gönderisi atılır
ve program biter. Çift gönderiye karşı: hesabın son Bluesky metinlerinde aynı anahtar
(ör. "⚽ 23' Oyuncu") varsa tekrar gönderilmez; bu yüzden iki kez çalışsa da zarar yok.

Ortam: SITE, SKOR_API, MAC ("Ev-Dep"), SES ("hadi" | "yuru"), ETIKETLER, BASLIK,
PLATFORMLAR (boş = hepsi; Instagram'a gönderilmez), YOKLAMA_SN (75), ONAY_SN (120),
EN_GEC (ISO; bu saatten sonra durur), DRY_RUN, ve bluesky_paylas.py'deki anahtarlar.
"""

import html
import json
import os
import time
from datetime import datetime, timezone

import bluesky_paylas as bp
import bsky_ek
import meta
from ozel_paylasim import api, maci_bul, ortam

AD = {"Fenerbahce": "Fenerbahçe", "Besiktas": "Beşiktaş", "Basaksehir": "Başakşehir",
      "Istanbul Basaksehir": "Başakşehir", "Kasimpasa": "Kasımpaşa", "Goztepe": "Göztepe"}
BITTI = {"FT", "AET", "PEN"}

SESLER = {
    "hadi": {
        "gol": [
            "GOOOL! ⚽ {dk}' {oyuncu}! {ev} {e}-{d} {dep}. Ayağa kalk baba!",
            "Ağlar havalandı! ⚽ {dk}' {oyuncu}. {ev} {e}-{d} {dep}. Hissediyordum!",
            "Yine gol! ⚽ {dk}' {oyuncu} vurdu. {ev} {e}-{d} {dep}. Bu derbi başka baba!",
        ],
        "ms": "Maç bitti! {ev} {e}-{d} {dep}. Bütün goller, kartlar ve istatistikler Maç Merkezi'nde. "
              "Maç sonu yorumu yarın sabah bizde, yaparız baba!",
    },
    "yuru": {
        "gol": [
            "⚽ {dk}' {oyuncu} golü. {ev} {e}-{d} {dep}. Sakin, maç bitmedi.",
            "⚽ {dk}' {oyuncu} attı. {ev} {e}-{d} {dep}. Bir gol bir şey kanıtlamaz, isabetli şuta bakın.",
            "⚽ {dk}' {oyuncu}, gol. {ev} {e}-{d} {dep}. Ben demiştim demeyeceğim. Henüz.",
        ],
        "ms": "Düdük çaldı: {ev} {e}-{d} {dep}. Rakamlar Maç Merkezi'nde. Kim haklıydı yarın yazarız. Görürüz.",
    },
}


def ad(s):
    return AD.get(s, s)


def gol_anahtari(o):
    dk = f"{o['dk']}+{o['ek']}" if o.get("ek") else f"{o['dk']}"
    return f"{dk}' {o.get('oyuncu') or '?'}", dk


class Paylasici:
    def __init__(self, dry_run, platformlar, adres, baslik, etiketler):
        self.dry_run, self.adres, self.baslik, self.etiketler = dry_run, adres, baslik, etiketler
        self.istendi = lambda p: not platformlar or p in platformlar
        self.handle = ortam("BLUESKY_HANDLE")
        sifre = ortam("BLUESKY_APP_PASSWORD")
        self.bsky = bp.oturum_ac(self.handle, sifre) if self.handle and sifre and not dry_run else None
        self.tg = (ortam("TELEGRAM_BOT_TOKEN"), ortam("TELEGRAM_CHANNEL"))
        self.th = ortam("THREADS_TOKEN")
        self.fb = None
        if ortam("META_PAGE_TOKEN") and self.istendi("facebook"):
            try:
                self.fb = meta.sayfa_kimlikleri(ortam("META_PAGE_TOKEN"), ortam("META_SAYFA_ADI") or None)
            except Exception as e:  # noqa: BLE001
                print(f"::warning title=Facebook atlanacak::{e}")
        self.gonderilen = set()

    def daha_once(self, anahtar):
        if anahtar in self.gonderilen:
            return True
        return bool(self.handle) and any(anahtar in t for t in bsky_ek.son_metinler(self.handle))

    def paylas(self, anahtar, metin):
        if self.daha_once(anahtar):
            print(f"Atlandı (zaten gönderilmiş): {anahtar}")
            self.gonderilen.add(anahtar)
            return
        self.gonderilen.add(anahtar)
        tam = f"{metin}\n\n{self.etiketler}".strip()
        if self.dry_run:
            print("DRY_RUN:", tam)
            return
        isler = []
        if self.bsky and self.istendi("bluesky"):
            did, token, pds = self.bsky
            isler.append(("Bluesky", lambda: bsky_ek.gonder(pds, did, token, tam, link=self.adres, link_baslik=self.baslik)))
        if all(self.tg) and self.istendi("telegram"):
            govde = f"<b>{html.escape(metin, quote=False)}</b>\n\n👉 <a href=\"{html.escape(self.adres, quote=True)}\">{html.escape(self.baslik, quote=False)}</a>"
            isler.append(("Telegram", lambda: bp.telegram_api(self.tg[0], "sendMessage", {
                "chat_id": self.tg[1], "text": govde, "parse_mode": "HTML",
                "link_preview_options": json.dumps({"is_disabled": True})})))
        if self.th and self.istendi("threads"):
            ilk = (self.etiketler.split() or [""])[0]
            isler.append(("Threads", lambda: meta.threads_paylas(self.th, f"{metin}\n\n{ilk}".strip(), self.adres)))
        if self.fb:
            isler.append(("Facebook", lambda: meta.facebook_paylas(self.fb["page_token"], self.fb["page_id"], tam, self.adres)))
        for adi, is_ in isler:
            try:
                is_()
                print(f"::notice title={adi}: gönderildi::{metin[:80]}")
            except Exception as e:  # noqa: BLE001
                print(f"::warning title={adi}: gönderilemedi::{e}")


def main():
    dry_run = ortam("DRY_RUN").lower() == "true"
    ses = SESLER[ortam("SES", "hadi")]
    skor_api, site = ortam("SKOR_API"), ortam("SITE").rstrip("/")
    platformlar = {p.strip().lower() for p in ortam("PLATFORMLAR").split(",") if p.strip()}
    m = maci_bul(skor_api, ortam("MAC"))
    adres = f"{site}/mac/?id={m['id']}"
    p = Paylasici(dry_run, platformlar, adres, ortam("BASLIK") or "Maç Merkezi",
                  ortam("ETIKETLER", "#SüperLig #derbi"))
    en_gec = datetime.fromisoformat(ortam("EN_GEC")) if ortam("EN_GEC") else None
    yoklama, onay = float(ortam("YOKLAMA_SN", "75")), float(ortam("ONAY_SN", "120"))
    ilk_gorulme = {}
    print(f"İzleniyor: {adres}")

    while True:
        try:
            d = api(skor_api, f"/api/mac?id={m['id']}")
        except Exception as e:  # noqa: BLE001
            print(f"::warning::Maç okunamadı: {e}")
            d = None
        if d:
            simdi = time.time()
            olaylar = d.get("olaylar", [])
            # VAR'ın iptal ettiği goller paylaşılmaz
            iptal = [(v.get("oyuncu"), v.get("dk") or 0) for v in olaylar
                     if v.get("tur") == "Var" and any(k in (v.get("detay") or "").lower() for k in ("cancel", "disallow"))]
            goller = [o for o in olaylar if o.get("tur") == "Goal" and o.get("detay") != "Missed Penalty"
                      and not any(oy == o.get("oyuncu") and dk >= (o.get("dk") or 0) for oy, dk in iptal)]
            for sira, o in enumerate(goller):
                anahtar, dk = gol_anahtari(o)
                ilk_gorulme.setdefault(anahtar, simdi)
                if simdi - ilk_gorulme[anahtar] < onay or anahtar in p.gonderilen:
                    continue
                oyuncu = o.get("oyuncu") or "?"
                if o.get("detay") == "Own Goal":
                    oyuncu += " (kendi kalesine)"
                elif o.get("detay") == "Penalty":
                    oyuncu += " (penaltı)"
                kalip = ses["gol"][sira % len(ses["gol"])]
                metin = kalip.format(dk=dk, oyuncu=oyuncu, ev=ad(d["ev"]), dep=ad(d["dep"]),
                                     e=d.get("evGol", 0), d=d.get("depGol", 0))
                # Anahtar metnin içinde geçsin ki Bluesky'dan çift kontrolü yapılabilsin
                p.paylas(anahtar, metin)
            if d.get("durum") in BITTI:
                metin = ses["ms"].format(ev=ad(d["ev"]), dep=ad(d["dep"]), e=d.get("evGol", 0), d=d.get("depGol", 0))
                p.paylas(metin.split(".")[0], metin)
                print("Maç bitti, takip sona erdi.")
                return
        if dry_run:
            print(f"DRY_RUN: durum {d.get('durum') if d else '?'}, {len(ilk_gorulme)} gol görüldü; tek yoklamada duruldu.")
            return
        if en_gec and datetime.now(timezone.utc) > en_gec:
            print("::warning::En geç saate gelindi, takip durdu.")
            return
        time.sleep(yoklama)


if __name__ == "__main__":
    main()
