"""Yeni yazılar için Gemini ile karakter sahnesi üretir (paylaşım kartındaki yuvarlak avatarın yerine).

Hugo derlemesinden ÖNCE çalışır (hugo.yml). Son 3 günün yazılarından sahnesi olmayanlar için
assets/kart/sahne/<slug>.png üretir; layouts/partials/kart.html bu dosya varsa avatar yerine onu kullanır.
Üretim başarısız olursa <slug>.yok yazılır (o yazı için tekrar denenmez); kart eski avatarla çıkar.
Derleme hiçbir durumda durmaz.

Ortam: GEMINI_API_KEY (yoksa atlanır), KART_SAHNE_SINIR (çalıştırma başına en fazla görsel, varsayılan 3).
Karakter depo adından seçilir: yurubaba* → Yürü, diğerleri → Hadi.
"""
import datetime as dt, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_gorsel  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(KOK, "content", "posts")
SAHNE = os.path.join(KOK, "assets", "kart", "sahne")
KIM = "yuru" if "yuru" in os.environ.get("GITHUB_REPOSITORY", os.path.basename(KOK)) else "hadi"
DUYGU = {
    "hadi": "coşkulu, kahkaha atan, heyecanlı, iyimser",
    "yuru": "soğukkanlı, alaycı, tek kaşı kalkık, yan gülüşlü, istatistik meraklısı",
}


def on_bilgi(yol):
    with open(yol, encoding="utf-8") as f:
        metin = f.read()
    m = re.match(r"^---\n(.*?)\n---", metin, re.S)
    if not m:
        return {}
    alanlar = {}
    for satir in m.group(1).splitlines():
        k = re.match(r'^(title|description|date|draft):\s*"?(.*?)"?\s*$', satir)
        if k:
            alanlar[k.group(1)] = k.group(2)
    return alanlar


def istem(baslik, ozet):
    return (
        f'Bir futbol yorum yazısı için kare kapak görseli. Yazının başlığı: "{baslik}". Özet: {ozet} '
        f"Görselde YALNIZCA {'Hadi Baba' if KIM == 'hadi' else 'Yürü Baba'} olsun ({DUYGU[KIM]}). "
        "Bu konuya uygun bir duygu ve hareketle, karenin tam ortasında, yakın plan (baş ve omuzlar), "
        "yüzü büyük ve net; çerçeve sonradan daireye kırpılacağı için köşelerde önemli bir şey olmasın. "
        "Zemin karakterin kendi zemini olsun. Futbol topu, düdük, kupa, konfeti, grafik, tribün silueti gibi "
        "genel ögeler kullanılabilir; takım renkleri, forma, arma, logo ve herhangi bir yazı/rakam kullanma."
    )


def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY yok; kart sahnesi atlandı")
        return 0
    os.makedirs(SAHNE, exist_ok=True)
    sinir = int(os.environ.get("KART_SAHNE_SINIR", "3"))
    simdi = dt.datetime.now(dt.timezone.utc)
    adaylar = []
    for ad in os.listdir(POSTS):
        if not ad.endswith(".md"):
            continue
        slug = ad[:-3]
        if any(os.path.exists(os.path.join(SAHNE, slug + uz)) for uz in (".png", ".yok")):
            continue
        b = on_bilgi(os.path.join(POSTS, ad))
        if b.get("draft") == "true" or not b.get("title"):
            continue
        try:
            tarih = dt.datetime.fromisoformat(b.get("date", ""))
        except ValueError:
            continue
        if tarih.tzinfo is None:
            tarih = tarih.replace(tzinfo=dt.timezone.utc)
        if tarih > simdi + dt.timedelta(hours=6) or simdi - tarih > dt.timedelta(days=3):
            continue
        adaylar.append((tarih, slug, b))
    adaylar.sort(reverse=True)
    for _, slug, b in adaylar[:sinir]:
        cikti = os.path.join(SAHNE, slug + ".png")
        try:
            gemini_gorsel.gorsel(cikti, istem(b["title"], b.get("description", "")), KIM, "1:1")
        except Exception as e:  # noqa: BLE001
            print(f"::warning title=Kart sahnesi üretilemedi::{slug}: {e}", flush=True)
            with open(os.path.join(SAHNE, slug + ".yok"), "w", encoding="utf-8") as f:
                f.write(str(e)[:500] + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001  — derleme asla durmasın
        print(f"::warning title=Kart sahnesi::{e}", flush=True)
        sys.exit(0)
