"""Hadi'nin hesaplarında paylaşılan videoları Yürü Baba'nın Facebook Sayfası, Instagram ve Threads'ine de koyar.

Kaynak: hadibaba deposu (iş akışı seyrek klonlar). Video orada `video/paylasildi.txt`'te "<anahtar> instagram"
olarak kayıtlıysa https://hadibaba.com/video/<anahtar>.mp4 yayındadır. Açıklama, anahtarın bilgi JSON'undan
(video/senaryolar, video/tezahurat, video/kampanya, video/tahmin-ligi, video/aytis; "tarih" alanı = anahtar) üretilir.
Günlük atışma videoları (YYYY-AA-GG) yalnızca kendi günü paylaşılır (maç önü; ertesi gün bayat).
Kayıt: bu depoda video/paylasildi.txt ("<anahtar> facebook|instagram|threads|facebook-story|instagram-story"). Hikâyeler yalnızca Hadi listesindeki son 3 video için.

Kullanım: python3 scripts/video_yuru.py <hadibaba_klasoru>
Ortam: META_PAGE_TOKEN, META_SAYFA_ADI ("Yürü Baba"), THREADS_TOKEN, VIDEO_ADET (çalıştırma başına en fazla
video, varsayılan 3), DRY_RUN=true → paylaşmaz.
"""
import glob, json, os, re, sys
from datetime import datetime, timedelta, timezone

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "scripts"))
import meta  # noqa: E402
import kanallar  # noqa: E402

KAYIT = os.path.join(KOK, "video", "paylasildi.txt")
ETIKETLER = "#futbol #süperlig #hadibaba #yurubaba"
SITE = "https://hadibaba.com/video"
IST = timezone(timedelta(hours=3))


def notice(baslik, mesaj, tur="notice"):
    print(f"::{tur} title={baslik}::{mesaj}", flush=True)


def satirlar(yol):
    if not os.path.exists(yol):
        return []
    return [s.strip() for s in open(yol, encoding="utf-8") if s.strip()]


def metin(s, uzun=True):
    y = s.get("yazilar", {})
    parcalar = [s.get("aciklama", s.get("mac", ""))]
    if uzun and y:
        parcalar.append("\n".join(x for x in (
            f"🔥 Hadi: {y['hadi']}" if y.get("hadi") else "",
            f"🧮 Yürü: {y['yuru']}" if y.get("yuru") else "") if x))
    parcalar.append(ETIKETLER)
    if not uzun:
        parcalar.append(kanallar.kisa())
    return "\n\n".join(p for p in parcalar if p)


def instagram_reels(page_token, ig_id, video_url, aciklama):
    kap = meta.istek("POST", f"{meta.GRAPH}/{ig_id}/media", {
        "media_type": "REELS", "video_url": video_url, "caption": aciklama[:2200],
        "share_to_feed": "true", "access_token": page_token,
    })["id"]
    meta._bekle(f"{meta.GRAPH}/{kap}", "status_code", page_token, sure=300)
    return meta.istek("POST", f"{meta.GRAPH}/{ig_id}/media_publish", {
        "creation_id": kap, "access_token": page_token,
    }).get("id")


def facebook_video(page_token, page_id, video_url, aciklama, baslik):
    return meta.istek("POST", f"https://graph-video.facebook.com/v25.0/{page_id}/videos", {
        "file_url": video_url, "description": aciklama, "title": baslik[:250], "access_token": page_token,
    }).get("id")


def threads_video(th_token, video_url, aciklama):
    kap = meta.istek("POST", f"{meta.THREADS}/me/threads", {
        "media_type": "VIDEO", "video_url": video_url, "text": aciklama[:meta.THREADS_SINIRI],
        "access_token": th_token,
    })["id"]
    meta._bekle(f"{meta.THREADS}/{kap}", "status", th_token, sure=300)
    return meta.istek("POST", f"{meta.THREADS}/me/threads_publish", {
        "creation_id": kap, "access_token": th_token,
    }).get("id")


def bilgiler(hb):
    harita = {}
    for yol in glob.glob(f"{hb}/video/**/*.json", recursive=True):
        try:
            j = json.load(open(yol, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(j, dict) and j.get("tarih") and (j.get("mac") or j.get("aciklama")):
            harita[j["tarih"]] = j
    return harita


def main():
    hb = sys.argv[1]
    dry = os.environ.get("DRY_RUN", "false").lower() == "true"
    adet = int(os.environ.get("VIDEO_ADET", "3") or 3)
    bugun = datetime.now(IST).date().isoformat()
    harita = bilgiler(hb)

    # Hadi'nin hesaplarında yayınlanmış videolar, sırayla
    adaylar = []
    for s in satirlar(f"{hb}/video/paylasildi.txt"):
        anahtar, _, platform = s.rpartition(" ")
        # Hadi'nin herhangi bir Meta/Threads paylaşımı başarılıysa video yayındadır; Yürü Hadi'nin Instagram'ına bağlı kalmaz
        if platform in ("instagram", "facebook", "threads") and anahtar not in adaylar:
            adaylar.append(anahtar)
    yapilan = set(satirlar(KAYIT))
    platformlar = []
    page_token = os.environ.get("META_PAGE_TOKEN")
    k = None
    if page_token:
        try:
            k = meta.sayfa_kimlikleri(page_token, os.environ.get("META_SAYFA_ADI") or None)
            platformlar.append("facebook")
            if k.get("ig_id"):
                platformlar.append("instagram")
        except Exception as e:  # noqa: BLE001
            notice("Yürü video Meta", f"Sayfa bulunamadı: {e}", "warning")
    th = os.environ.get("THREADS_TOKEN")
    if th:
        platformlar.append("threads")
    if not platformlar:
        notice("Yürü video", "Hiçbir platform anahtarı yok", "warning")
        return

    son_uc = set(adaylar[-3:])
    bekleyen = []
    for a in adaylar:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", a) and a != bugun:
            continue  # günlük maç önü videosu: yalnızca kendi günü
        if a not in harita:
            notice("Yürü video", f"{a}: bilgi JSON'u bulunamadı, atlandı", "warning")
            continue
        pl = list(platformlar)
        if a in son_uc:  # hikâyeler yalnızca en yeni videolar için (eski videolar yığılmasın)
            pl += [x for x in ("facebook-story", "instagram-story") if x.split("-")[0] in platformlar]
        eksik = [p for p in pl if f"{a} {p}" not in yapilan]
        if eksik:
            bekleyen.append((a, eksik))
    # Bugünün maç önü videosu bekleyemez → öne al
    bekleyen.sort(key=lambda x: x[0] != bugun)
    if not bekleyen:
        notice("Yürü video", "Paylaşılacak yeni video yok")
        return
    notice("Yürü video", f"Bekleyen {len(bekleyen)} video; bu çalıştırmada en fazla {adet}: "
           + ", ".join(a for a, _ in bekleyen[:adet]))

    os.makedirs(os.path.dirname(KAYIT), exist_ok=True)
    for a, eksik in bekleyen[:adet]:
        s = harita[a]
        url = f"{SITE}/{a}.mp4"
        for p in eksik:
            if dry:
                notice(f"Yürü video {p}", f"DENEME: {a} paylaşılacaktı ({url})")
                continue
            try:
                if p == "facebook":
                    kimlik = facebook_video(k["page_token"], k["page_id"], url, metin(s) + "\n\n" + kanallar.uzun(), f"Hadi vs Yürü: {s.get('mac', a)}")
                elif p == "facebook-story":
                    kimlik = meta.facebook_hikaye_video(k["page_token"], k["page_id"], url)
                elif p == "instagram-story":
                    kimlik = meta.instagram_hikaye(k["page_token"], k["ig_id"], url, video=True)
                elif p == "instagram":
                    kimlik = instagram_reels(k["page_token"], k["ig_id"], url, metin(s, uzun=False))
                else:
                    kimlik = threads_video(th, url, metin(s, uzun=False))
                with open(KAYIT, "a", encoding="utf-8") as f:
                    f.write(f"{a} {p}\n")
                notice(f"Yürü video {p}", f"{a} paylaşıldı ({kimlik})")
            except Exception as e:  # noqa: BLE001
                notice(f"Yürü video {p}", f"{a} gönderilemedi: {e}", "warning")


if __name__ == "__main__":
    main()
