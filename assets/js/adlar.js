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
    "Erzurumspor": "Erzurumspor", "Erzurumspor FK": "Erzurumspor", "Bandirmaspor": "Bandırmaspor", "Manisa FK": "Manisa FK", "Turkey": "Türkiye"
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
  var ULKE = { "England": "İngiltere", "Spain": "İspanya", "Italy": "İtalya", "Germany": "Almanya", "France": "Fransa",
    "Netherlands": "Hollanda", "Portugal": "Portekiz", "Belgium": "Belçika", "Austria": "Avusturya", "Switzerland": "İsviçre",
    "Scotland": "İskoçya", "Greece": "Yunanistan", "Saudi-Arabia": "Suudi Arabistan", "USA": "ABD", "Denmark": "Danimarka",
    "Norway": "Norveç", "Sweden": "İsveç", "Russia": "Rusya", "Ukraine": "Ukrayna", "Croatia": "Hırvatistan", "Qatar": "Katar",
    "United-Arab-Emirates": "BAE", "Czech-Republic": "Çekya", "Poland": "Polonya" };
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
    // Maçın kalıcı sayfası (yalnızca Süper Lig): /maclar/2026-27/galatasaray-fenerbahce/
    // scripts/veri_cek.py'deki mac_yolu ile aynı kural; diğer maçlar /mac/?id=
    macYolu: function (m, yedek) {
      var lig = m.ligId == null ? 203 : Number(m.ligId);
      if (lig !== 203 || !m.tarih) return (yedek || "/mac/") + "?id=" + m.id;
      var yil = Number(m.tarih.slice(0, 4)), ay = Number(m.tarih.slice(5, 7)), bas = ay >= 7 ? yil : yil - 1;
      // Yalnızca bu sezonun maçlarının sayfası var; eski sezonlar /mac/?id=
      var b = new Date(), buSezon = b.getMonth() + 1 >= 7 ? b.getFullYear() : b.getFullYear() - 1;
      if (bas !== buSezon) return (yedek || "/mac/") + "?id=" + m.id;
      var t = function (x) { return SLUG[sade(x)] || sade(x).replace(/ /g, "-"); };
      return "/maclar/" + bas + "-" + String(bas + 1).slice(-2) + "/" + t(m.ev) + "-" + t(m.dep) + "/";
    },
    takimLink: function (s, cls) {
      var slug = SLUG[sade(s)], e = document.createElement(slug ? "a" : "span");
      if (cls) e.className = cls;
      e.textContent = AD[s] || s;
      if (slug) e.href = "/takim/" + slug + "/";
      return e;
    },
    transferTur: function (t) {
      var m = { "Free": "Bedelsiz", "Loan": "Kiralık", "N/A": "", "Back from Loan": "Kiralıktan dönüş", "Return from loan": "Kiralıktan dönüş", "Transfer": "Bonservisli" };
      return t in m ? m[t] : (t || "");
    },
    lig: function (l) {
      var m = { "UEFA Champions League": "Şampiyonlar Ligi", "UEFA Europa League": "Avrupa Ligi", "UEFA Europa Conference League": "Konferans Ligi",
        "UEFA Conference League": "Konferans Ligi", "Super Lig": "Süper Lig", "Cup": "Türkiye Kupası", "Turkish Cup": "Türkiye Kupası",
        "Super Cup": "Süper Kupa", "World Cup - Qualification Europe": "Dünya Kupası Elemeleri", "World Cup": "Dünya Kupası",
        "UEFA Nations League": "UEFA Uluslar Ligi", "Friendlies": "Hazırlık maçı", "Club Friendlies": "Hazırlık maçı",
        "Euro Championship - Qualification": "EURO Elemeleri", "Euro Championship": "EURO" };
      return m[l] || l || "";
    },
    ulke: function (u) { return ULKE[u] || u || ""; },
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
