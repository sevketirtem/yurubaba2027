// Süper Lig takımlarının Avrupa kupaları: maçlar ve lig aşaması sıraları. <section class="avrupa" data-api="…" data-mac="/mac/">.
(function () {
  "use strict";
  var H = window.HY, el = H.el, ad = H.ad;

  function macSatiri(m, macYolu) {
    var a = el("a", "mac"); a.href = macYolu + "?id=" + m.id;
    var canli = H.CANLI.indexOf(m.durum) >= 0, bitti = H.BITTI.indexOf(m.durum) >= 0;
    if (canli) a.classList.add("canli");
    var d = el("span", "mac-durum");
    d.textContent = canli ? (m.dakika ? m.dakika + "'" : "Canlı") : bitti ? "MS" : (H.DURUM[m.durum] || H.saat(m.tarih));
    a.appendChild(d);
    a.appendChild(el("span", "mac-ev", ad(m.ev)));
    a.appendChild(el("span", "mac-skor", (canli || bitti) && m.evGol != null ? m.evGol + " - " + m.depGol : "-"));
    a.appendChild(el("span", "mac-dep", ad(m.dep)));
    return a;
  }

  document.querySelectorAll(".avrupa[data-api]").forEach(function (kok) {
    var api = kok.getAttribute("data-api").replace(/\/$/, ""), macYolu = kok.getAttribute("data-mac");
    var govde = kok.querySelector(".avrupa-govde"), alt = kok.querySelector(".skor-alt");
    function yukle() {
      H.getir(api + "/api/avrupa").then(function (v) {
        govde.textContent = "";
        var canliVar = false, bos = true;
        (v.kupalar || []).forEach(function (k) {
          if (!k.maclar.length && !k.siralar.length) return;
          bos = false;
          var b = el("div", "mac-bolum");
          b.appendChild(el("h2", null, k.ad));
          if (k.siralar.length) {
            var ul = el("ul", "avrupa-sira");
            k.siralar.forEach(function (s) {
              var li = el("li");
              li.appendChild(el("b", null, s.sira + "."));
              li.appendChild(H.takimLink(s.takim));
              li.appendChild(el("span", null, s.p + " puan · " + s.o + " maç · averaj " + (s.av > 0 ? "+" : "") + s.av +
                (k.takimSayisi ? " · " + k.takimSayisi + " takım arasında" : "")));
              ul.appendChild(li);
            });
            b.appendChild(ul);
          }
          var sonGun = "";
          k.maclar.forEach(function (m) {
            if (H.CANLI.indexOf(m.durum) >= 0) canliVar = true;
            var g = H.gun(m.tarih);
            if (g !== sonGun) { b.appendChild(el("div", "mac-gun", g)); sonGun = g; }
            b.appendChild(macSatiri(m, macYolu));
          });
          if (!k.maclar.length) b.appendChild(el("p", "empty", "Son bir hafta ve önümüzdeki iki haftada maç yok."));
          govde.appendChild(b);
        });
        if (bos) govde.appendChild(el("p", "empty", "Şu an Avrupa kupalarında Süper Lig takımı maçı ya da sırası yok."));
        if (alt) alt.textContent = "Son güncelleme " + H.saat(v.guncellendi) + (canliVar ? " · canlı maçlar birkaç dakikada bir yenilenir" : "") +
          " · maça tıklayınca kadrolar ve istatistikler açılır";
        if (canliVar) setTimeout(yukle, 120000);
      }).catch(function () {
        govde.textContent = "";
        govde.appendChild(el("p", "empty", "Avrupa kupası bilgisi şu an alınamıyor."));
      });
    }
    yukle();
  });
})();
