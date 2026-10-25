// Ortak yardımcılar (skor.js, mac.js, krallar.js'den önce paketlenir).
// API-Football takım adlarını Türkçe yazımına çevirir.
(function () {
  "use strict";
  var AD = {
    "Fenerbahce": "Fenerbahçe", "Besiktas": "Beşiktaş", "Istanbul Basaksehir": "Başakşehir",
    "Basaksehir": "Başakşehir", "Kasimpasa": "Kasımpaşa", "Goztepe": "Göztepe", "Eyupspor": "Eyüpspor",
    "Rizespor": "Çaykur Rizespor", "Caykur Rizespor": "Çaykur Rizespor", "Genclerbirligi": "Gençlerbirliği",
    "Gençlerbirliği S.K.": "Gençlerbirliği",
    "Fatih Karagumruk": "Fatih Karagümrük", "Karagumruk": "Fatih Karagümrük", "Amed SK": "Amedspor",
    "Amed": "Amedspor", "Gaziantep": "Gaziantep FK", "Kocaelispor": "Kocaelispor", "Sivasspor": "Sivasspor",
    "Bodrumspor": "Bodrum FK", "Hatayspor": "Hatayspor", "Pendikspor": "Pendikspor", "Corum FK": "Çorum FK",
    "Erzurumspor": "Erzurumspor", "Erzurumspor FK": "Erzurumspor", "Bandirmaspor": "Bandırmaspor", "Manisa FK": "Manisa FK"
  };
  var TZ = "Europe/Istanbul";
  window.HY = {
    TZ: TZ,
    CANLI: ["1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP"],
    BITTI: ["FT", "AET", "PEN"],
    DURUM: { HT: "İY", PST: "Ertelendi", CANC: "İptal", ABD: "Yarıda", SUSP: "Durdu", INT: "Ara", TBD: "Saat belli değil", AWD: "Hükmen", WO: "Hükmen", BT: "Ara", P: "Penaltılar" },
    ad: function (s) { return AD[s] || s; },
    el: function (tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; },
    saat: function (iso) { return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: TZ }); },
    gun: function (iso) { return new Date(iso).toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long", timeZone: TZ }); },
    getir: function (url) {
      return fetch(url, { cache: "no-cache" }).then(function (r) {
        return r.json().then(function (j) { if (!r.ok) throw new Error(j.hata || ("HTTP " + r.status)); return j; });
      });
    }
  };
})();
