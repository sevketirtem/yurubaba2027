// Süper Lig sakat ve cezalı listesi, takım takım. <section class="sakatlar" data-api="…">. Ortak: adlar.js.
(function () {
  "use strict";
  var H = window.HY, el = H.el;

  document.querySelectorAll(".sakatlar[data-api]").forEach(function (kok) {
    var api = kok.getAttribute("data-api").replace(/\/$/, "");
    var govde = kok.querySelector(".sakat-govde"), alt = kok.querySelector(".skor-alt");
    H.getir(api + "/api/sakat").then(function (v) {
      govde.textContent = "";
      var liste = v.liste || [];
      if (!liste.length) { govde.appendChild(el("p", "empty", "Önümüzdeki maçlar için bildirilmiş sakat ya da cezalı oyuncu yok.")); return; }
      var takimlar = {};
      liste.forEach(function (s) { (takimlar[s.takim] = takimlar[s.takim] || []).push(s); });
      Object.keys(takimlar).sort(function (a, b) { return H.ad(a).localeCompare(H.ad(b), "tr"); }).forEach(function (t) {
        var kutu = el("div", "sakat-takim");
        var h = el("h3"); h.appendChild(H.takimLink(t)); h.appendChild(el("span", "sakat-sayi", " " + takimlar[t].length));
        kutu.appendChild(h);
        var ul = el("ul", "sakat-liste");
        takimlar[t].forEach(function (s) {
          var li = el("li");
          li.appendChild(el("span", "sakat-ad", s.oyuncu));
          li.appendChild(el("span", "sakat-sebep", H.sebep(s.sebep)));
          li.appendChild(el("span", "sakat-durum durum-" + (s.tur === "Questionable" ? "suphe" : "yok"), H.sakatDurum(s.tur)));
          ul.appendChild(li);
        });
        kutu.appendChild(ul);
        govde.appendChild(kutu);
      });
      if (alt) alt.textContent = "Son güncelleme " + H.tarih(v.guncellendi) + " " + H.saat(v.guncellendi) +
        " · \"Oynamayacak\": maç kadrosunda olmayacağı bildirildi; \"Şüpheli\": durumu belirsiz.";
    }).catch(function () {
      govde.textContent = "";
      govde.appendChild(el("p", "empty", "Liste şu an alınamıyor."));
    });
  });
})();
