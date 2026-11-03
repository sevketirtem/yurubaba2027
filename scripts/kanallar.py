"""Ulaşım kanallarımız — tüm paylaşım açıklamalarının sonuna eklenen ortak blok (iki depoda aynı dosya).

uzun()          YouTube, Facebook, podcast RSS: tüm kanallar, bağlantılı, çok satır
telegram_html() Telegram mesajları (HTML, tıklanabilir kısa satır)
duz_kisa()      Telegram video altyazısı (1024 karakter sınırı): tek satır, bağlantılı
kisa()          Instagram / Threads: bağlantı tıklanmadığı için adlar, tek satır
TikTok'a eklenmez (TikTok kuralı: API videosunda bağlantı/alan adı yok). Bluesky 300 karakter → eklenmez.
"""
import html

SPOTIFY = "https://open.spotify.com/show/63Xz9bgfflG26ysr8xr2fW"
YOUTUBE = "https://www.youtube.com/@hadivsyuru"
TIKTOK = "https://www.tiktok.com/@hadivsyuru"
# Sinan'ın kanalı (canlı maç önü/sonu yayınları). Yeni yayın gelince yalnızca SINAN_YAYIN'ı değiştir.
SINAN_KANAL = "https://www.youtube.com/channel/UCKzFD2DLKCZZdzwVl0szTOw"
SINAN_YAYIN = "https://www.youtube.com/live/wWsKtOdMhIo"


def uzun():
    return "\n".join([
        f"🔴 Canlı yayın: Sinan'la Futbol kanalında maç önü/sonu canlı sohbet. Son yayın: {SINAN_YAYIN} · Kanal: {SINAN_KANAL}",
        "",
        "📢 Bizi takip et",
        f"🎧 Podcast (Spotify): {SPOTIFY}",
        f"▶️ YouTube: {YOUTUBE}",
        f"🎵 TikTok: {TIKTOK}",
        "🔥 Hadi Baba: https://hadibaba.com · https://t.me/hadibabacom · https://www.instagram.com/hadibabacom/",
        "🧮 Yürü Baba: https://yurubaba.com · https://t.me/yurubaba · https://www.instagram.com/yurubabacom/",
    ])


def telegram_html():
    a = lambda u, t: f'<a href="{html.escape(u, quote=True)}">{t}</a>'  # noqa: E731
    return f"🎧 {a(SPOTIFY, 'Spotify')} · ▶️ {a(YOUTUBE, 'YouTube')} · 🎵 {a(TIKTOK, 'TikTok')} · 🔴 {a(SINAN_KANAL, "Sinan'la Futbol canlı")}"


def duz_kisa():
    return f"🎧 Spotify: {SPOTIFY}\n▶️ YouTube: {YOUTUBE}"


def kisa():
    return "🎧 Spotify & ▶️ YouTube: \"Hadi vs Yürü\" · 🎵 TikTok @hadivsyuru"
