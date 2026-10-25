// Takım sayfası (/takim/<slug>/). <section class="takimsayfa" data-api="…" data-ad="Galatasaray">
// Önce /api/puan'dan takımın numarası ve sırası bulunur, sonra /api/takim?id=… Ortak: adlar.js.
(function () {
  "use strict";
  var H = window.HY, el = H.el, ad = H.ad;
  var SONUC = { G: ["G", "galibiyet"], B: ["B", "beraberlik"], M: ["M", "mağlubiyet"] };

  function bolum(baslik) {
    var b = el("div", "mac-bolum");
    b.appendChild(el("h2", null, baslik));
    return b;
  }

  function sonucHarf(m, id) {
    if (m.evGol == null) return null;
    var biz = m.evId === id ? m.evGol : m.depGol, onlar = m.evId === id ? m.depGol : m.evGol;
    return biz > onlar ? "G" : biz < onlar ? "M" : "B";
  }

  function formRozetleri(form) {
    var d = el("span", "form");
    // API formu "WWDLW" (en yenisi sonda) verir; Türkçe harfe çevir
    String(form || "").split("").forEach(function (c) {
      var h = { W: "G", D: "B", L: "M" }[c];
      if (h) d.appendChild(el("i", "form-" + h, h));
    });
    return d;
  }

  function macListesi(maclar, id, macYolu, oynandi) {
    var ul = el("ul", "takim-maclar");
    maclar.forEach(function (m) {
      var li = el("li");
      var a = el("a", "takim-mac");
      a.href = H.macYolu(m, macYolu);
      a.appendChild(el("span", "tm-tarih", H.tarih(m.tarih) + (oynandi ? "" : " " + H.saat(m.tarih))));
      var ic = m.evId === id;
      a.appendChild(el("span", "tm-yer", ic ? "İç saha" : "Deplasman"));
      a.appendChild(el("span", "tm-rakip", ad(ic ? m.dep : m.ev)));
      var harf = oynandi ? sonucHarf(m, id) : null;
      var skor = el("span", "tm-skor" + (harf ? " sonuc-" + harf : ""),
        // Skor takımın gözünden: "atılan-yenilen"
        oynandi && m.evGol != null ? (ic ? m.evGol + "-" + m.depGol : m.depGol + "-" + m.evGol) : (H.DURUM[m.durum] || "-"));
      if (harf) skor.title = SONUC[harf][1];
      a.appendChild(skor);
      a.appendChild(el("span", "tm-lig", H.lig(m.lig)));
      li.appendChild(a);
      ul.appendChild(li);
    });
    return ul;
  }

  function ciz(kok, satir, t) {
    var govde = kok.querySelector(".takim-govde"), macYolu = kok.getAttribute("data-mac");
    govde.textContent = "";
    var id = t.takim.id;

    // Özet: sıra, puan, form
    var ozet = el("div", "takim-ozet");
    if (satir) {
      [["Sıra", satir.sira + "."], ["Puan", satir.p], ["O-G-B-M", satir.o + "-" + satir.g + "-" + satir.b + "-" + satir.m],
       ["Averaj", (satir.av > 0 ? "+" : "") + satir.av]].forEach(function (x) {
        var k = el("div", "ozet-kutu");
        k.appendChild(el("b", null, x[1]));
        k.appendChild(el("span", null, x[0]));
        ozet.appendChild(k);
      });
      var f = el("div", "ozet-kutu ozet-form");
      f.appendChild(formRozetleri(satir.form));
      f.appendChild(el("span", null, "Son 5 maç formu"));
      ozet.appendChild(f);
    }
    govde.appendChild(ozet);
    var bilgi = [];
    if (t.stat && t.stat.ad) bilgi.push("Stat: " + t.stat.ad + (t.stat.sehir ? ", " + t.stat.sehir : "") +
      (t.stat.kapasite ? " (" + t.stat.kapasite.toLocaleString("tr-TR") + " kişilik)" : ""));
    if (t.takim.kurulus) bilgi.push("Kuruluş: " + t.takim.kurulus);
    if (bilgi.length) govde.appendChild(el("p", "mac-hakem", bilgi.join(" · ")));

    var b1 = bolum("Sıradaki maçlar");
    if (t.sonraki.length) b1.appendChild(macListesi(t.sonraki, id, macYolu, false));
    else b1.appendChild(el("p", "empty", "Planlanmış maç yok."));
    govde.appendChild(b1);

    var b2 = bolum("Son 5 maç");
    if (t.son.length) b2.appendChild(macListesi(t.son, id, macYolu, true));
    else b2.appendChild(el("p", "empty", "Henüz maç yok."));
    govde.appendChild(b2);

    var b3 = bolum("Sakat ve cezalılar");
    if (t.sakatlar.length) {
      var ul = el("ul", "sakat-liste");
      t.sakatlar.forEach(function (s) {
        var li = el("li");
        li.appendChild(el("span", "sakat-ad", s.oyuncu));
        li.appendChild(el("span", "sakat-sebep", H.sebep(s.sebep)));
        li.appendChild(el("span", "sakat-durum durum-" + (s.tur === "Questionable" ? "suphe" : "yok"), H.sakatDurum(s.tur)));
        ul.appendChild(li);
      });
      b3.appendChild(ul);
    } else b3.appendChild(el("p", "empty", "Bildirilmiş sakat ya da cezalı oyuncu yok."));
    govde.appendChild(b3);

    if (t.transferler && t.transferler.length) {
      var b5 = bolum("Bu sezonki transferler"), ul5 = el("ul", "transfer-liste");
      t.transferler.slice(0, 30).forEach(function (x) {
        var li = el("li", "tr-" + x.yon);
        li.appendChild(el("span", "tr-yon", x.yon === "gelen" ? "Gelen" : "Giden"));
        li.appendChild(el("span", "tr-oyuncu", x.oyuncu));
        li.appendChild(el("span", "tr-karsi", (x.yon === "gelen" ? "← " : "→ ") + (x.karsi || "")));
        li.appendChild(el("span", "tr-tur", H.transferTur(x.tur)));
        ul5.appendChild(li);
      });
      b5.appendChild(ul5);
      govde.appendChild(b5);
    }

    var b4 = bolum("Kadro");
    if (t.kadro.length) {
      var gruplar = {};
      t.kadro.forEach(function (o) { (gruplar[o.mevki] = gruplar[o.mevki] || []).push(o); });
      var izgara = el("div", "kadrolar kadro-4");
      ["Kaleci", "Defans", "Orta saha", "Forvet"].concat(Object.keys(gruplar).filter(function (k) {
        return ["Kaleci", "Defans", "Orta saha", "Forvet"].indexOf(k) < 0;
      })).forEach(function (g) {
        if (!gruplar[g]) return;
        var s = el("div", "kadro");
        s.appendChild(el("h4", null, g));
        var ul2 = el("ul", "kadro-liste");
        gruplar[g].forEach(function (o) {
          var li = el("li");
          li.appendChild(el("span", "kadro-no", o.no != null ? o.no : ""));
          li.appendChild(el("span", "kadro-ad", o.ad));
          li.appendChild(el("span", "kadro-mevki", o.yas ? o.yas : ""));
          ul2.appendChild(li);
        });
        s.appendChild(ul2);
        izgara.appendChild(s);
      });
      b4.appendChild(izgara);
      b4.appendChild(el("p", "skor-alt", "Sağdaki sayı oyuncunun yaşı."));
    } else b4.appendChild(el("p", "empty", "Kadro bilgisi yok."));
    govde.appendChild(b4);

    var alt = kok.querySelector(".skor-alt.genel");
    if (alt) alt.textContent = "Son güncelleme " + H.tarih(t.guncellendi) + " " + H.saat(t.guncellendi);
  }

  document.querySelectorAll(".takimsayfa[data-api]").forEach(function (kok) {
    var api = kok.getAttribute("data-api").replace(/\/$/, ""), aranan = H.sade(kok.getAttribute("data-ad"));
    var govde = kok.querySelector(".takim-govde");
    H.getir(api + "/api/puan").then(function (p) {
      var satir = (p.tablo || []).filter(function (s) { return H.sade(s.takim) === aranan; })[0];
      if (!satir) throw new Error("Takım puan tablosunda yok");
      return H.getir(api + "/api/takim?id=" + satir.id).then(function (t) { ciz(kok, satir, t); });
    }).catch(function (e) {
      govde.textContent = "";
      govde.appendChild(el("p", "empty", "Takım bilgisi şu an alınamıyor. Biraz sonra tekrar dene."));
      console.warn(e);
    });
  });
})();
