"""Gemini çağrıları için ortak taşıyıcı: önce Vertex AI (deneme kredisi), olmazsa AI Studio (GEMINI_API_KEY).

Vertex: iş akışında google-github-actions/auth (Workload Identity, anahtarsız) → GOOGLE_VERTEX_TOKEN.
Yollar AI Studio biçiminde verilir; Vertex'e çevrilir:
  "models/<ad>:<yöntem>"   → v1/projects/P/locations/global/publishers/google/models/<ad>:<yöntem>
  "models?..."              → yayıncı model listesi (AI Studio biçimine dönüştürülür)
  "interactions[/<id>]"     → v1beta1/projects/P/locations/global/interactions[/<id>]
"""
import json, os, urllib.error, urllib.request

PROJE = os.environ.get("VERTEX_PROJE", "hadi-yuru-ses")
STUDIO = "https://generativelanguage.googleapis.com/v1beta"
VX = "https://aiplatform.googleapis.com"


def var_mi():
    return bool(os.environ.get("GOOGLE_VERTEX_TOKEN") or os.environ.get("GEMINI_API_KEY"))


def _cagir(url, govde, basliklar, timeout):
    req = urllib.request.Request(url, data=json.dumps(govde).encode() if govde is not None else None,
                                 method="POST" if govde is not None else "GET",
                                 headers={"Content-Type": "application/json", **basliklar})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        govde_ = e.read()[:600]
        try:
            mesaj = json.loads(govde_).get("error", {}).get("message", "") or govde_.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            mesaj = govde_.decode("utf-8", "replace")
        raise HataHTTP(e.code, mesaj) from None


class HataHTTP(RuntimeError):
    def __init__(self, kod, mesaj):
        super().__init__(f"HTTP {kod}: {mesaj[:400]}")
        self.kod = kod


def _model_adi(yol):
    return yol.split("/", 1)[1] if yol.startswith("models/") else yol


def _vertex(yol, govde, timeout):
    t = os.environ["GOOGLE_VERTEX_TOKEN"]
    b = {"Authorization": f"Bearer {t}", "x-goog-user-project": PROJE}
    if yol.startswith("models?") or yol == "models":
        y = _cagir(f"{VX}/v1beta1/publishers/google/models?pageSize=200", None, b, timeout)
        modeller = []
        for m in y.get("publisherModels", []):
            ad = m.get("name", "").split("/")[-1]
            modeller.append({"name": "models/" + ad, "supportedGenerationMethods": ["generateContent"]})
        return {"models": modeller}
    if yol.startswith("interactions"):
        return _cagir(f"{VX}/v1beta1/projects/{PROJE}/locations/global/{yol}", govde, b, timeout)
    if yol.startswith("models/"):
        # Vertex her contents öğesinde role ister (AI Studio istemez) → eksikse "user" ekle
        if isinstance(govde, dict) and isinstance(govde.get("contents"), list):
            govde = {**govde, "contents": [({"role": "user", **c} if isinstance(c, dict) and not c.get("role") else c)
                                           for c in govde["contents"]]}
        return _cagir(f"{VX}/v1/projects/{PROJE}/locations/global/publishers/google/{yol}", govde, b, timeout)
    raise ValueError(f"Bilinmeyen yol: {yol}")


def istek(yol, govde=None, timeout=300):
    """AI Studio biçimindeki yolu çağırır. Vertex varsa önce onu dener; model/erişim hatasında AI Studio'ya düşer."""
    hata = None
    if os.environ.get("GOOGLE_VERTEX_TOKEN"):
        try:
            return _vertex(yol, govde, timeout)
        except HataHTTP as e:
            hata = e
            if not os.environ.get("GEMINI_API_KEY") or e.kod not in (400, 403, 404):
                raise
            print(f"::warning title=Vertex::{yol.split('?')[0]} Vertex'te olmadı ({e}); AI Studio deneniyor", flush=True)
    if os.environ.get("GEMINI_API_KEY"):
        return _cagir(f"{STUDIO}/{yol}", govde, {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout)
    raise hata or RuntimeError("Ne GOOGLE_VERTEX_TOKEN ne GEMINI_API_KEY var")
