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
  // Takım sayfası adresleri (/takim/<slug>/). Anahtar: sade() ile sadeleşmiş API adı.
  var SLUG = {
    "galatasaray": "galatasaray", "fenerbahce": "fenerbahce", "besiktas": "besiktas", "trabzonspor": "trabzonspor",
    "kasimpasa": "kasimpasa", "kocaelispor": "kocaelispor", "erzurumspor": "erzurumspor", "corum": "corum-fk",
    "goztepe": "goztepe", "alanyaspor": "alanyaspor", "basaksehir": "basaksehir", "rizespor": "rizespor",
    "konyaspor": "konyaspor", "gaziantep": "gaziantep-fk", "genclerbirligi": "genclerbirligi", "samsunspor": "samsunspor",
    "eyupspor": "eyupspor", "amed": "amedspor", "amedspor": "amedspor"
  };
  // Takım adını karşılaştırma için sadeleştirir: "Gençlerbirliği S.K." → "genclerbirligi"
  function sade(s) {
    s = String(s || "").replace(/ı/g, "i").replace(/İ/g, "I").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    s = s.replace(/\b(s|a)\.(k|s)\.?/g, " ").replace(/\b(fk|sk|as)\b/g, " ").trim().replace(/^(istanbul|caykur)\s+/, "");
    return s.replace(/[^a-z0-9]+/g, " ").trim();
  }
  var DURUMSAKAT = { "Missing Fixture": "Oynamayacak", "Questionable": "Şüpheli" };
  var SEBEP = {
    "Injury": "Sakatlık", "Knee Injury": "Diz sakatlığı", "Muscle Injury": "Kas sakatlığı", "Hamstring Injury": "Arka adale sakatlığı",
    "Ankle Injury": "Ayak bileği sakatlığı", "Groin Injury": "Kasık sakatlığı", "Calf Injury": "Baldır sakatlığı", "Thigh Injury": "Uyluk sakatlığı",
    "Back Injury": "Sırt sakatlığı", "Foot Injury": "Ayak sakatlığı", "Shoulder Injury": "Omuz sakatlığı", "Hip Injury": "Kalça sakatlığı",
    "Head Injury": "Kafa travması", "Concussion": "Sarsıntı", "Achilles Tendon Injury": "Aşil tendonu sakatlığı", "Knock": "Darbe",
    "Illness": "Hastalık", "Virus": "Hastalık", "Red Card": "Kırmızı kart cezası", "Yellow Cards": "Sarı kart cezası",
    "Suspended": "Cezalı", "Suspension": "Cezalı", "Personal Reasons": "Kişisel nedenler", "Lack of fitness": "Kondisyon eksikliği",
    "Rest": "Dinlendiriliyor", "Inactive": "Kadro dışı", "Broken Leg": "Bacak kırığı", "Ligament Injury": "Bağ sakatlığı",
    "Cruciate Ligament Injury": "Çapraz bağ sakatlığı", "Muscle Strain": "Kas zorlanması", "Surgery": "Ameliyat"
  };
  window.HY = {
    TZ: TZ,
    CANLI: ["1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP"],
    BITTI: ["FT", "AET", "PEN"],
    DURUM: { HT: "İY", PST: "Ertelendi", CANC: "İptal", ABD: "Yarıda", SUSP: "Durdu", INT: "Ara", TBD: "Saat belli değil", AWD: "Hükmen", WO: "Hükmen", BT: "Ara", P: "Penaltılar" },
    ad: function (s) { return AD[s] || s; },
    sade: sade,
    slug: function (s) { return SLUG[sade(s)] || null; },
    takimLink: function (s, cls) {
      var slug = SLUG[sade(s)], e = document.createElement(slug ? "a" : "span");
      if (cls) e.className = cls;
      e.textContent = AD[s] || s;
      if (slug) e.href = "/takim/" + slug + "/";
      return e;
    },
    sakatDurum: function (t) { return DURUMSAKAT[t] || t || ""; },
    sebep: function (t) { return SEBEP[t] || t || ""; },
    tarih: function (iso) { return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long", timeZone: TZ }); },
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
