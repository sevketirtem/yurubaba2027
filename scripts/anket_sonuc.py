"""Threads hesabındaki son anketlerin sonuçlarını okur (salt okuma, hiçbir şey paylaşmaz).

Gerekli: THREADS_TOKEN. Çıktı: notice "Anket <kullanıcı>".
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from meta import THREADS, istek  # noqa: E402

ALAN = ("id,text,timestamp,permalink,poll_attachment{option_a,option_b,option_c,option_d,"
        "option_a_votes_percentage,option_b_votes_percentage,option_c_votes_percentage,"
        "option_d_votes_percentage,total_votes,expiration_timestamp}")


def main():
    tok = os.environ.get("THREADS_TOKEN", "").strip()
    if not tok:
        print("::warning title=Anket::THREADS_TOKEN yok")
        return 0
    try:
        ben = istek("GET", f"{THREADS}/me", {"fields": "username", "access_token": tok})
        r = istek("GET", f"{THREADS}/me/threads", {"fields": ALAN, "limit": 25, "access_token": tok})
    except Exception as e:
        print(f"::error title=Anket::{type(e).__name__}: {str(e)[:300]}")
        return 1
    bulundu = 0
    for t in r.get("data", []):
        p = t.get("poll_attachment")
        if not p:
            continue
        bulundu += 1
        secenek = []
        for h in "abcd":
            ad = p.get(f"option_{h}")
            if ad:
                yuzde = p.get(f"option_{h}_votes_percentage")
                yuzde = f"%{round(float(yuzde) * 100) if yuzde is not None and float(yuzde) <= 1 else yuzde}" if yuzde is not None else "?"
                secenek.append(f"{ad}: {yuzde}")
        print(f"::notice title=Anket @{ben.get('username')}::{(t.get('text') or '')[:120]} || "
              f"{' | '.join(secenek)} || toplam oy {p.get('total_votes')} || bitiş {p.get('expiration_timestamp')} || {t.get('permalink')}")
        print(json.dumps(p, ensure_ascii=False))
    if not bulundu:
        print(f"::notice title=Anket @{ben.get('username')}::Son 25 gönderide anket bulunamadı")
    return 0


if __name__ == "__main__":
    sys.exit(main())
