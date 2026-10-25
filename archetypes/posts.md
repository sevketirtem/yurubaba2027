---
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
date: {{ .Date }}
draft: true
# Biri seçilir: mac-onu, mac-sonu, transfer-kulisi, hadiye-cevap
kategoriler: ["mac-onu"]
description: ""
# Maç önü/sonu yazısında iki takımın sırası, formu ve son 5 karşılaşması otomatik kutu olarak eklenir:
# karsilasma: ["Galatasaray", "Fenerbahçe"]   (ev sahibi önce; gerek yoksa satırı silin)
# Her gerçek bilgi (skor, puan, transfer) en az bir kaynağa dayanır
kaynaklar:
  - ad: ""
    url: ""
---

