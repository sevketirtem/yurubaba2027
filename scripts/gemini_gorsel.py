"""Gemini API ile Hadi/Yürü karakter görseli üretimi (yalnızca standart kütüphane).

Kullanım:
  python scripts/gemini_gorsel.py liste
      Anahtarın erişebildiği, görsel üretebilen modelleri listeler (notice olarak).
  python scripts/gemini_gorsel.py gorsel <çıktı.png> "<istem>" [hadi|yuru|ikisi] [en-boy]
      Karakter resimlerini (video/hadi.png, video/yuru.png) referans vererek görsel üretir.

Ortam değişkenleri:
  GEMINI_API_KEY        Google Cloud API anahtarı (yalnızca Gemini API'ye kısıtlı, gemini-github servis hesabı).
  GEMINI_GORSEL_MODEL   İsteğe bağlı model adı (ör. models/gemini-...-image). Boşsa listeden seçilir.
  GEMINI_GUNLUK_SINIR   Bir çalıştırmada üretilecek en fazla görsel (varsayılan 4) — kredi koruması.

Kurallar: yalnızca kendi karakterlerimiz; gerçek kişi yüzü, kulüp arması, forma, stadyum, yazı/logo yok.
"""
import base64, json, os, sys, urllib.error, urllib.request

API = "https://generativelanguage.googleapis.com/v1beta"
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KURALLAR = (
    "Düz (flat) çizgi film stili; karakterlerin yüzünü, renklerini ve zeminlerini referans resimlerdeki gibi koru. "
    "Gerçek kişi yüzü, kulüp arması veya logosu, forma, stadyum görüntüsü, marka ve ekranda yazı KULLANMA. "
    "Bahis, oran, kupon ögesi yok."
)
TARIF = {
    "hadi": "Hadi Baba: turuncu ışınlı zemin, bıyıklı, kahkaha atan coşkulu taraftar (1. referans resim).",
    "yuru": "Yürü Baba: lacivert zemin, soluk istatistik grafikleri, gözlüklü, bıyıklı, tek kaşı kalkık, yan gülüşlü alaycı abi (2. referans resim).",
}


def notice(baslik, mesaj):
    print(f"::notice title={baslik}::{mesaj}", flush=True)


def _istek(yol, govde=None):
    anahtar = os.environ["GEMINI_API_KEY"]
    veri = json.dumps(govde).encode() if govde is not None else None
    req = urllib.request.Request(
        f"{API}/{yol}", data=veri, method="POST" if veri else "GET",
        headers={"Content-Type": "application/json", "x-goog-api-key": anahtar},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            mesaj = json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            mesaj = ""
        raise RuntimeError(f"Gemini {yol.split('?')[0]} -> HTTP {e.code}: {mesaj[:300]}") from None


def modeller():
    sonuc, sayfa = [], ""
    while True:
        y = _istek(f"models?pageSize=1000{'&pageToken=' + sayfa if sayfa else ''}")
        sonuc += y.get("models", [])
        sayfa = y.get("nextPageToken", "")
        if not sayfa:
            return sonuc


def gorsel_modelleri():
    return [m["name"] for m in modeller()
            if "image" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])]


def model_sec():
    istenen = os.environ.get("GEMINI_GORSEL_MODEL", "").strip()
    if istenen:
        return istenen if istenen.startswith("models/") else "models/" + istenen
    adaylar = gorsel_modelleri()
    if not adaylar:
        raise RuntimeError("Görsel üretebilen Gemini modeli bulunamadı")
    # Ucuz ve hızlı olanı (flash) tercih et, önizleme olmayanı öne al
    adaylar.sort(key=lambda n: ("flash" not in n, "preview" in n, n))
    return adaylar[0]


def _ref(kim):
    """Karakter referans resmi: assets/kart/ref-<kim>.png (iki depoda), yoksa video/<kim>.png."""
    for yol in (os.path.join(KOK, "assets", "kart", f"ref-{kim}.png"), os.path.join(KOK, "video", f"{kim}.png")):
        if os.path.exists(yol):
            return yol
    raise FileNotFoundError(f"{kim} referans resmi yok")


def _resim(yol):
    with open(yol, "rb") as f:
        return {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(f.read()).decode()}}


def gorsel(cikti, istem, kim="ikisi", en_boy="1:1"):
    model = model_sec()
    kimler = ["hadi", "yuru"] if kim == "ikisi" else [kim]
    parcalar = [_resim(_ref("hadi")), _resim(_ref("yuru"))]
    metin = " ".join(TARIF[k] for k in kimler) + " SAHNE: " + istem + " " + KURALLAR
    parcalar.append({"text": metin})
    govde = {
        "contents": [{"role": "user", "parts": parcalar}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": en_boy}},
    }
    try:
        y = _istek(f"{model}:generateContent", govde)
    except RuntimeError as e:
        if "imageConfig" in str(e) or "aspect" in str(e).lower():
            govde["generationConfig"].pop("imageConfig", None)
            y = _istek(f"{model}:generateContent", govde)
        else:
            raise
    for aday in y.get("candidates", []):
        for p in aday.get("content", {}).get("parts", []):
            veri = p.get("inline_data") or p.get("inlineData")
            if veri and veri.get("data"):
                with open(cikti, "wb") as f:
                    f.write(base64.b64decode(veri["data"]))
                kullanim = y.get("usageMetadata", {})
                notice("Gemini görsel", f"{os.path.basename(cikti)} üretildi ({model}, "
                                        f"token: {kullanim.get('totalTokenCount', '?')})")
                return cikti
    neden = y.get("promptFeedback", {}) or [a.get("finishReason") for a in y.get("candidates", [])]
    raise RuntimeError(f"Görsel dönmedi ({model}): {str(neden)[:300]}")


def main():
    if not os.environ.get("GEMINI_API_KEY"):
        notice("Gemini", "GEMINI_API_KEY yok; atlandı")
        return 0
    mod = sys.argv[1] if len(sys.argv) > 1 else "liste"
    if mod == "liste":
        adlar = gorsel_modelleri()
        notice("Gemini modeller", "Görsel modelleri: " + (", ".join(adlar) or "YOK"))
        notice("Gemini seçilen", model_sec() if adlar else "-")
        return 0
    if mod == "gorsel":
        sinir = int(os.environ.get("GEMINI_GUNLUK_SINIR", "4"))
        isler = json.loads(sys.argv[2]) if sys.argv[2].startswith("[") else [
            {"cikti": sys.argv[2], "istem": sys.argv[3],
             "kim": sys.argv[4] if len(sys.argv) > 4 else "ikisi",
             "en_boy": sys.argv[5] if len(sys.argv) > 5 else "1:1"}]
        hata = 0
        for is_ in isler[:sinir]:
            try:
                gorsel(is_["cikti"], is_["istem"], is_.get("kim", "ikisi"), is_.get("en_boy", "1:1"))
            except Exception as e:  # noqa: BLE001
                hata += 1
                print(f"::warning title=Gemini görsel hatası::{e}", flush=True)
        return 1 if hata == len(isler[:sinir]) else 0
    print("Bilinmeyen mod", mod)
    return 2


if __name__ == "__main__":
    sys.exit(main())
