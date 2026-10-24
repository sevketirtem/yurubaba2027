// Canlı skor ve puan durumu. Veri: kendi önbellekli API'miz (skor-api/, Vercel).
// <div class="skor" data-api="https://…" data-mod="tam|ozet" data-link="/canli/">
(function () {
  "use strict";
  var AD = {
    "Fenerbahce": "Fenerbahçe", "Besiktas": "Beşiktaş", "Istanbul Basaksehir": "Başakşehir",
    "Basaksehir": "Başakşehir", "Kasimpasa": "Kasımpaşa", "Goztepe": "Göztepe", "Eyupspor": "Eyüpspor",
    "Rizespor": "Çaykur Rizespor", "Caykur Rizespor": "Çaykur Rizespor", "Genclerbirligi": "Gençlerbirliği",
    "Fatih Karagumruk": "Fatih Karagümrük", "Karagumruk": "Fatih Karagümrük", "Amed SK": "Amedspor",
    "Amed": "Amedspor", "Gaziantep": "Gaziantep FK", "Kocaelispor": "Kocaelispor", "Sivasspor": "Sivasspor",
    "Bodrumspor": "Bodrum FK", "Hatayspor": "Hatayspor", "Pendikspor": "Pendikspor", "Corum FK": "Çorum FK",
    "Erzurumspor": "Erzurumspor", "Bandirmaspor": "Bandırmaspor", "Manisa FK": "Manisa FK"
  };
  var CANLI = ["1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP"];
  var BITTI = ["FT", "AET", "PEN"];
  var DURUM = { HT: "İY", PST: "Ertelendi", CANC: "İptal", ABD: "Yarıda", SUSP: "Durdu", INT: "Ara", TBD: "Saat belli değil", AWD: "Hükmen", WO: "Hükmen", BT: "Ara", P: "Penaltılar" };
  var TZ = "Europe/Istanbul";

  function ad(s) { return AD[s] || s; }
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function saat(iso) { return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: TZ }); }
  function gun(iso) { return new Date(iso).toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long", timeZone: TZ }); }
  function getir(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) throw new Error(j.hata || ("HTTP " + r.status)); return j; });
    });
  }

  function macSatiri(m) {
    var satir = el("div", "mac");
    var canli = CANLI.indexOf(m.durum) >= 0, bitti = BITTI.indexOf(m.durum) >= 0;
    if (canli) satir.classList.add("canli");
    var d = el("span", "mac-durum");
    if (canli) d.textContent = m.durum === "HT" ? "İY" : (m.dakika ? m.dakika + "'" : "Canlı");
    else if (bitti) d.textContent = "MS";
    else d.textContent = DURUM[m.durum] || saat(m.tarih);
    var skor = (canli || bitti) && m.evGol != null ? m.evGol + " - " + m.depGol : "-";
    satir.appendChild(d);
    satir.appendChild(el("span", "mac-ev", ad(m.ev)));
    satir.appendChild(el("span", "mac-skor", skor));
    satir.appendChild(el("span", "mac-dep", ad(m.dep)));
    return satir;
  }

  function maclarCiz(kutu, veri, ozet) {
    var maclar = veri.maclar || [];
    if (ozet) {
      // Özet: canlılar + bugünün/yarının maçları, yoksa son biten 4 maç
      var simdi = Date.now();
      var secili = maclar.filter(function (m) {
        return CANLI.indexOf(m.durum) >= 0 || (m.durum === "NS" && new Date(m.tarih) - simdi < 36 * 3600e3);
      });
      if (!secili.length) secili = maclar.filter(function (m) { return BITTI.indexOf(m.durum) >= 0; }).slice(-4);
      maclar = secili.slice(0, 6);
    }
    if (!maclar.length) { kutu.appendChild(el("p", "empty", "Bu hafta için maç bilgisi yok.")); return; }
    var sonGun = "";
    maclar.forEach(function (m) {
      var g = gun(m.tarih);
      if (g !== sonGun) { kutu.appendChild(el("div", "mac-gun", g)); sonGun = g; }
      kutu.appendChild(macSatiri(m));
    });
  }

  function puanCiz(kutu, veri, ozet) {
    var tablo = veri.tablo || [];
    if (!tablo.length) { kutu.appendChild(el("p", "empty", "Puan durumu henüz yok.")); return; }
    if (ozet) tablo = tablo.slice(0, 5);
    var sar = el("div", "tablo-sar"), t = el("table", "puan");
    var basliklar = ozet ? ["#", "Takım", "O", "AV", "P"] : ["#", "Takım", "O", "G", "B", "M", "A", "Y", "AV", "P"];
    var thead = el("thead"), tr = el("tr");
    basliklar.forEach(function (b) { tr.appendChild(el("th", null, b)); });
    thead.appendChild(tr); t.appendChild(thead);
    var tbody = el("tbody");
    tablo.forEach(function (s) {
      var r = el("tr");
      var hucre = ozet ? [s.sira, ad(s.takim), s.o, s.av, s.p] : [s.sira, ad(s.takim), s.o, s.g, s.b, s.m, s.a, s.y, s.av, s.p];
      hucre.forEach(function (v, i) { r.appendChild(el("td", i === 1 ? "takim" : (i === hucre.length - 1 ? "p" : null), v)); });
      tbody.appendChild(r);
    });
    t.appendChild(tbody); sar.appendChild(t); kutu.appendChild(sar);
  }

  function zaman(iso) { return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: TZ }); }

  function yukle(kok) {
    var api = kok.getAttribute("data-api").replace(/\/$/, "");
    var ozet = kok.getAttribute("data-mod") === "ozet";
    var mKutu = kok.querySelector(".skor-maclar"), pKutu = kok.querySelector(".skor-puan"), alt = kok.querySelector(".skor-alt");
    Promise.allSettled([getir(api + "/api/maclar"), getir(api + "/api/puan")]).then(function (s) {
      mKutu.textContent = ""; pKutu.textContent = "";
      if (s[0].status === "fulfilled") maclarCiz(mKutu, s[0].value, ozet);
      else mKutu.appendChild(el("p", "empty", "Maç bilgisi şu an alınamıyor."));
      if (s[1].status === "fulfilled") puanCiz(pKutu, s[1].value, ozet);
      else pKutu.appendChild(el("p", "empty", "Puan durumu şu an alınamıyor."));
      var m = s[0].status === "fulfilled" ? s[0].value : null;
      if (alt) alt.textContent = m ? ("Son güncelleme " + zaman(m.guncellendi) + (m.canli ? " · canlı maçlar birkaç dakikada bir yenilenir" : "")) : "";
      if (m && m.canli) setTimeout(function () { yukle(kok); }, 120000);
    });
  }

  document.querySelectorAll(".skor[data-api]").forEach(yukle);
})();
