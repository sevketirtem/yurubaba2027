// Maç sayfası (/mac/?id=…): skor, olaylar, istatistik, ilk 11'ler.
// <section class="macsayfa" data-api="https://…" data-canli="/canli/">. Ortak yardımcılar: adlar.js.
(function () {
  "use strict";
  var H = window.HY, el = H.el, ad = H.ad;
  var OLAY = {
    "Normal Goal": ["⚽", "Gol"], "Own Goal": ["⚽", "Kendi kalesine"], "Penalty": ["⚽", "Penaltı golü"],
    "Missed Penalty": ["✖", "Kaçan penaltı"], "Yellow Card": ["🟨", "Sarı kart"], "Red Card": ["🟥", "Kırmızı kart"],
    "Second Yellow card": ["🟥", "İkinci sarıdan kırmızı"]
  };
  var VAR = {
    "Goal cancelled": "gol iptal", "Goal Disallowed": "gol iptal", "Penalty confirmed": "penaltı verildi",
    "Penalty cancelled": "penaltı iptal", "Goal confirmed": "gol onaylandı", "Card upgrade": "kart değişti"
  };
  var MEVKI = { G: "K", D: "D", M: "O", F: "F" };

  function dakika(o) { return o.dk + (o.ek ? "+" + o.ek : "") + "'"; }

  function olayMetni(o) {
    if (o.tur === "subst") return ["⇄", "Değişiklik: " + (o.oyuncu || "?") + " ↔ " + (o.yardimci || "?")];
    if (o.tur === "Var") return ["📺", "VAR: " + (VAR[o.detay] || o.detay || "inceleme") + (o.oyuncu ? " (" + o.oyuncu + ")" : "")];
    var t = OLAY[o.detay] || [o.tur === "Card" ? "🟨" : "•", o.detay || o.tur];
    var metin = t[1] + (o.oyuncu ? ": " + o.oyuncu : "");
    if (o.tur === "Goal" && o.yardimci && o.detay !== "Own Goal") metin += " (asist: " + o.yardimci + ")";
    return [t[0], metin];
  }

  function bas(kutu, m, canli, bitti) {
    var ust = el("div", "mac-ust");
    var bilgi = [m.hafta ? m.hafta + ". hafta" : null, H.gun(m.tarih) + " " + H.saat(m.tarih), m.stat].filter(Boolean).join(" · ");
    ust.appendChild(el("p", "mac-bilgi", bilgi));
    var skorSatir = el("div", "mac-tabela" + (canli ? " canli" : ""));
    skorSatir.appendChild(el("span", "tabela-ev", ad(m.ev)));
    var skor = (canli || bitti) && m.evGol != null ? m.evGol + " - " + m.depGol : H.saat(m.tarih);
    skorSatir.appendChild(el("span", "tabela-skor", skor));
    skorSatir.appendChild(el("span", "tabela-dep", ad(m.dep)));
    ust.appendChild(skorSatir);
    var durum = canli ? (m.durum === "HT" ? "Devre arası" : (m.dakika ? m.dakika + ". dakika" : "Canlı"))
      : bitti ? "Maç sonu" : (H.DURUM[m.durum] || "Başlamadı");
    if ((canli || bitti) && m.iy && m.iy.home != null && m.durum !== "1H") durum += " · İY " + m.iy.home + "-" + m.iy.away;
    ust.appendChild(el("p", "mac-durumu" + (canli ? " canli" : ""), durum));
    if (m.hakem) ust.appendChild(el("p", "mac-hakem", "Hakem: " + m.hakem.replace(/,.*$/, "")));
    kutu.appendChild(ust);
  }

  function olaylar(kutu, m) {
    var bolum = el("div", "mac-bolum");
    bolum.appendChild(el("h2", null, "Maçın olayları"));
    if (!m.olaylar.length) { bolum.appendChild(el("p", "empty", "Henüz olay yok.")); kutu.appendChild(bolum); return; }
    var liste = el("ol", "olaylar");
    m.olaylar.forEach(function (o) {
      var t = olayMetni(o);
      var li = el("li", "olay olay-" + o.taraf + (o.tur === "Goal" && o.detay !== "Missed Penalty" ? " gol" : ""));
      li.appendChild(el("span", "olay-dk", dakika(o)));
      li.appendChild(el("span", "olay-ikon", t[0]));
      li.appendChild(el("span", "olay-metin", t[1]));
      li.appendChild(el("span", "olay-takim", ad(o.taraf === "ev" ? m.ev : m.dep)));
      liste.appendChild(li);
    });
    bolum.appendChild(liste);
    kutu.appendChild(bolum);
  }

  function sayi(v) { return typeof v === "string" ? parseFloat(v) || 0 : (v || 0); }

  function istatistik(kutu, m) {
    if (!m.istatistik.length) return;
    var bolum = el("div", "mac-bolum");
    bolum.appendChild(el("h2", null, "İstatistikler"));
    var t = el("div", "istatistik");
    var ustSatir = el("div", "ist-satir ist-bas");
    ustSatir.appendChild(el("span", "ist-ev", ad(m.ev)));
    ustSatir.appendChild(el("span", "ist-dep", ad(m.dep)));
    t.appendChild(ustSatir);
    m.istatistik.forEach(function (s) {
      var satir = el("div", "ist-satir");
      satir.appendChild(el("span", "ist-ev", s.ev));
      satir.appendChild(el("span", "ist-ad", s.ad));
      satir.appendChild(el("span", "ist-dep", s.dep));
      var a = sayi(s.ev), b = sayi(s.dep), top = a + b;
      var cubuk = el("div", "ist-cubuk");
      var sol = el("i", "ist-sol"); sol.style.width = (top ? a / top * 100 : 50) + "%";
      cubuk.appendChild(sol);
      satir.appendChild(cubuk);
      t.appendChild(satir);
    });
    bolum.appendChild(t);
    kutu.appendChild(bolum);
  }

  function kadroListesi(baslik, oyuncular) {
    var ul = el("ul", "kadro-liste");
    oyuncular.forEach(function (o) {
      var li = el("li");
      li.appendChild(el("span", "kadro-no", o.no != null ? o.no : ""));
      li.appendChild(el("span", "kadro-ad", o.ad));
      li.appendChild(el("span", "kadro-mevki", MEVKI[o.mevki] || ""));
      ul.appendChild(li);
    });
    var d = el("div");
    d.appendChild(el("h4", null, baslik));
    d.appendChild(ul);
    return d;
  }

  function kadrolar(kutu, m, bitti) {
    var bolum = el("div", "mac-bolum");
    bolum.appendChild(el("h2", null, "İlk 11'ler"));
    if (!m.kadro.ev && !m.kadro.dep) {
      bolum.appendChild(el("p", "empty", bitti ? "Bu maç için kadro bilgisi yok." :
        "İlk 11'ler genellikle maçtan yaklaşık 1 saat önce açıklanır. Bu sayfa kendiliğinden yenilenir."));
      kutu.appendChild(bolum); return;
    }
    var iki = el("div", "kadrolar");
    [["ev", m.ev], ["dep", m.dep]].forEach(function (x) {
      var k = m.kadro[x[0]], sutun = el("div", "kadro");
      sutun.appendChild(el("h3", null, ad(x[1]) + (k && k.dizilis ? " (" + k.dizilis + ")" : "")));
      if (!k) { sutun.appendChild(el("p", "empty", "Henüz açıklanmadı.")); iki.appendChild(sutun); return; }
      if (k.hoca) sutun.appendChild(el("p", "kadro-hoca", "Teknik direktör: " + k.hoca));
      sutun.appendChild(kadroListesi("İlk 11", k.ilk11));
      if (k.yedek.length) sutun.appendChild(kadroListesi("Yedekler", k.yedek));
      iki.appendChild(sutun);
    });
    bolum.appendChild(iki);
    kutu.appendChild(bolum);
  }

  function yukle(kok, id) {
    var api = kok.getAttribute("data-api").replace(/\/$/, "");
    var govde = kok.querySelector(".mac-govde"), alt = kok.querySelector(".skor-alt");
    H.getir(api + "/api/mac?id=" + encodeURIComponent(id)).then(function (m) {
      var canli = H.CANLI.indexOf(m.durum) >= 0, bitti = H.BITTI.indexOf(m.durum) >= 0;
      govde.textContent = "";
      bas(govde, m, canli, bitti);
      olaylar(govde, m);
      istatistik(govde, m);
      kadrolar(govde, m, bitti);
      var baslik = ad(m.ev) + " - " + ad(m.dep) + ((canli || bitti) && m.evGol != null ? " " + m.evGol + "-" + m.depGol : "");
      document.title = baslik + " · " + document.title.split(" · ").pop();
      var h1 = document.querySelector(".post-head h1");
      if (h1) h1.textContent = ad(m.ev) + " - " + ad(m.dep);
      var kalan = new Date(m.tarih) - Date.now();
      var yenile = canli ? 60000 : (!bitti && kalan < 2 * 3600e3 && kalan > -3 * 3600e3) ? 300000 : 0;
      if (alt) alt.textContent = "Son güncelleme " + H.saat(m.guncellendi) + (yenile ? " · sayfa kendiliğinden yenilenir" : "");
      if (yenile) setTimeout(function () { yukle(kok, id); }, yenile);
    }).catch(function (e) {
      govde.textContent = "";
      govde.appendChild(el("p", "empty", "Maç bilgisi şu an alınamıyor. Biraz sonra tekrar dene."));
      console.warn(e);
    });
  }

  document.querySelectorAll(".macsayfa[data-api]").forEach(function (kok) {
    var id = new URLSearchParams(location.search).get("id");
    if (!id || !/^\d+$/.test(id)) {
      var g = kok.querySelector(".mac-govde");
      g.textContent = "";
      var p = el("p", "empty", "Maç seçilmedi. ");
      var a = el("a", null, "Bu haftanın maçlarına git →");
      a.href = kok.getAttribute("data-canli") || "/canli/";
      p.appendChild(a); g.appendChild(p);
      return;
    }
    yukle(kok, id);
  });
})();
