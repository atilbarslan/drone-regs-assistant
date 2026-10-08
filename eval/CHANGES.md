## Değişiklikler ve hipotezler

Her satır tüm sete (36 soru) karşı ölçüldü; "çevrimdışı" yazanlar yalnız getirmeyi ölçer (önbellekteki soru embedding'leriyle, üretim çağrısı yok). Öncesi/sonrası sayıları aynı soru setinden. Not: model deterministik değil; aynı yapılandırmanın iki koşusu arasında da birkaç fact oynayabilir (bkz. PR notu).

| # | Değişiklik / hipotez | Ölçüm | Sonuç | Karar |
|---|---|---|---|---|
| A | Temel çizgi (PR 7 sonrası ayarlar) | tam koşu | must 45/61, çelişki 0, ret 4/4, yanlış ret 2 | — |
| H2 | Liste sorusu kalıpları ("kurallar neler", "what rules apply" …) | çevrimdışı | setteki 36 sorunun hiçbirinin liste durumu değişmiyor | eklenmedi (etki ölçülemez) |
| H1-liste | Liste sorularına temel maddeler | çevrimdışı | getirme 45/57 → 45/57 (yalnız 4 liste sorusu; beklenen maddeleri zaten vardı) | eklenmedi |
| H1-hepsi | Her soruya temel maddeler | çevrimdışı + tam koşu | getirme 45/57 → 50/57 (hepsi gelen 22 → 26/32); must 44/61, çelişki 1, should 10 → 7, prompt +1.750 token (+%33) | eklenmedi: must artmadı, maliyet yüksek |
| A2 | A'nın tekrarı (gürültü) | tam koşu | must 41/61 (A: 45), çelişki 1, ret 3/4; 13 soruda en az bir must/ret farklı | gürültü ≈ ±4 must |
| B | thinking low (H3 ile birlikte) | tam koşu | must 43/61, çelişki 0, ret 3/4, üretim ~0,5 sn daha yavaş | A kaldı (ölçüt: çelişki eşit → must A önde) |
| F1 | Genel prompt düzeltmeleri: kurala bağlı her koşul ve sınır korunsun, başka fıkraya atıf açılsın, koşul sağlanmazsa ne olacağı (kural 8); genel kuralı veren parça "ilgili" sayılsın (kural 3); gündelik tanım yasal kategoriyi belirlemez (kural 5); bütün alanlar tek dilde (kural 9) | tam koşu | must 45 → **50/61**, çelişki 0, doğrulanamadı 1, yanlış ret 2 → 1; düzelenler tr-07, tr-10, k-02, k-04, x-01; bozulan j-02 m2 | **tutuldu** (en iyi temel çizgiden +5, A2'den +9) |
| C | gemini-3.8-flash, A prompt'u, A/B'de eksik kalan 14 soru | tam koşu denemesi | 10 soruda `503 UNAVAILABLE`; 22 üretim denemesi günlük 20'lik kotayı bitirdi; sonuç yok | yarın, yeniden denemesiz (`--retries 0`) tekrar |
