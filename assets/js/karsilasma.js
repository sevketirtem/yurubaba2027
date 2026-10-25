// "Karşılaşma kutusu": iki takımın sırası, puanı, formu ve son 5 karşılaşması.
// Yazılarda: <section class="karsilasma" data-api="…" data-ev="Galatasaray" data-dep="Fenerbahçe" data-mac="/mac/">
// Maç sayfasında mac.js, HY.karsilasma(kutu, api, ev, dep, macYolu, haricId) ile çağırır. Ortak: adlar.js.
(function () {
  "use strict";
  var H = window.HY, el = H.el, ad = H.ad;

  function form(f) {
    var d = el("span", "form");
    String(f || "").split("").forEach(function (c) {
      var h = { W: "G", D: "B", L: "M" }[c];
      if (h) d.appendChild(el("i", "form-" + h, h));
    });
    return d;
  }

  function takimKarti(satir, adi) {
    var k = el("div", "kars-takim");
    var h = el("h3"); h.appendChild(H.takimLink(satir ? satir.takim : adi)); k.appendChild(h);
    if (satir) {
      k.appendChild(el("p", "kars-sira", satir.sira + ". sırada · " + satir.p + " puan · averaj " + (satir.av > 0 ? "+" : "") + satir.av));
      k.appendChild(form(satir.form));
    } else k.appendChild(el("p", "kars-sira", "Puan durumunda yok"));
    return k;
  }

  H.karsilasma = function (kutu, api, evAd, depAd, macYolu, haricId) {
    api = api.replace(/\/$/, "");
    var a = H.sade(evAd), b = H.sade(depAd);
    return H.getir(api + "/api/puan").then(function (p) {
      var bul = function (x) { return (p.tablo || []).filter(function (s) { return H.sade(s.takim) === x; })[0]; };
      var ev = bul(a), dep = bul(b);
      var bolum = el("div", "mac-bolum karsilasma-ic");
      bolum.appendChild(el("h2", null, "Karşılaşma öncesi"));
      var iki = el("div", "kars-iki");
      iki.appendChild(takimKarti(ev, evAd));
      iki.appendChild(takimKarti(dep, depAd));
      bolum.appendChild(iki);
      kutu.appendChild(bolum);
      if (!ev || !dep) return;
      return H.getir(api + "/api/h2h?a=" + ev.id + "&b=" + dep.id).then(function (h) {
        var maclar = (h.maclar || []).filter(function (m) { return m.id !== haricId; });
        bolum.appendChild(el("h4", "kars-baslik", "Son karşılaşmalar"));
        if (!maclar.length) { bolum.appendChild(el("p", "empty", "Kayıtlı karşılaşma yok.")); return; }
        var ul = el("ul", "takim-maclar");
        maclar.forEach(function (m) {
          var li = el("li"), x = el("a", "takim-mac kars-mac");
          x.href = (macYolu || "/mac/") + "?id=" + m.id;
          x.appendChild(el("span", "tm-tarih", new Date(m.tarih).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric", timeZone: H.TZ })));
          x.appendChild(el("span", "tm-rakip", ad(m.ev) + " " + m.evGol + "-" + m.depGol + " " + ad(m.dep)));
          x.appendChild(el("span", "tm-lig", m.lig || ""));
          li.appendChild(x); ul.appendChild(li);
        });
        bolum.appendChild(ul);
      });
    }).catch(function (e) { console.warn("karşılaşma kutusu:", e); });
  };

  document.querySelectorAll(".karsilasma[data-api]").forEach(function (kok) {
    var govde = kok.querySelector(".kars-govde");
    govde.textContent = "";
    H.karsilasma(govde, kok.getAttribute("data-api"), kok.getAttribute("data-ev"), kok.getAttribute("data-dep"), kok.getAttribute("data-mac"));
  });
})();
