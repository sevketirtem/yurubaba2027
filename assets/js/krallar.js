// Gol ve asist krallığı. <section class="krallar" data-api="https://…">. Ortak yardımcılar: adlar.js.
(function () {
  "use strict";
  var H = window.HY, el = H.el, ad = H.ad;

  function tablo(kutu, liste, tur) {
    if (!liste || !liste.length) { kutu.appendChild(el("p", "empty", "Liste henüz oluşmadı.")); return; }
    var sar = el("div", "tablo-sar"), t = el("table", "puan kral");
    var basliklar = tur === "gol" ? ["#", "Oyuncu", "Takım", "Maç", "Pen.", "Gol"] : ["#", "Oyuncu", "Takım", "Maç", "Gol", "Asist"];
    var tr = el("tr"), thead = el("thead");
    basliklar.forEach(function (b) { tr.appendChild(el("th", null, b)); });
    thead.appendChild(tr); t.appendChild(thead);
    var tbody = el("tbody"), onceki = null, sira = 0;
    liste.forEach(function (o, i) {
      // Eşit sayıda olanlar aynı sırayı paylaşır
      if (o.sayi !== onceki) { sira = i + 1; onceki = o.sayi; }
      var r = el("tr");
      var hucre = tur === "gol" ? [sira, o.oyuncu, ad(o.takim), o.mac, o.penalti, o.gol] : [sira, o.oyuncu, ad(o.takim), o.mac, o.gol, o.asist];
      hucre.forEach(function (v, j) {
        r.appendChild(el("td", j === 1 ? "takim oyuncu" : j === 2 ? "kral-takim" : (j === hucre.length - 1 ? "p" : null), v));
      });
      tbody.appendChild(r);
    });
    t.appendChild(tbody); sar.appendChild(t); kutu.appendChild(sar);
  }

  document.querySelectorAll(".krallar[data-api]").forEach(function (kok) {
    var api = kok.getAttribute("data-api").replace(/\/$/, "");
    var g = kok.querySelector(".kral-gol"), a = kok.querySelector(".kral-asist"), alt = kok.querySelector(".skor-alt");
    H.getir(api + "/api/krallar").then(function (v) {
      g.textContent = ""; a.textContent = "";
      tablo(g, v.gol, "gol");
      tablo(a, v.asist, "asist");
      if (alt) alt.textContent = "Son güncelleme " + H.gun(v.guncellendi) + " " + H.saat(v.guncellendi) + " · liste birkaç saatte bir yenilenir";
    }).catch(function () {
      g.textContent = ""; a.textContent = "";
      g.appendChild(el("p", "empty", "Liste şu an alınamıyor."));
    });
  });
})();
