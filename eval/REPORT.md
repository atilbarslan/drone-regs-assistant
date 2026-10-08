# Değerlendirme raporu

Bu dosya `python -m eval.report` ile üretilir; elle düzenlenmez (değişiklik ve hipotez tablosu `eval/CHANGES.md`'den aynen alınır). Yöntem: `eval/run.py` ve `eval/score.py` başları.

Gemini çağrıları her koşunun satırında (son satır). Hakem: her soru için tek çağrı; "present"/"contradicted" kararları cevaptan birebir alıntı ister, alıntı bulunamazsa "doğrulanamadı" sayılır.

## Özet

| Ölçü | A | A2 | B | H1all | F1 | F2 | H5 |
|---|---|---|---|---|---|---|---|
| Soru (hata) | 36 (0) | 36 (0) | 36 (0) | 36 (0) | 36 (0) | 36 (0) | 36 (0) |
| Tespit doğru | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 |
| Getirme: beklenen maddeden en az biri | 31/32 | 31/32 | 31/32 | 31/32 | 31/32 | 31/32 | 31/32 |
| Getirme: beklenen maddelerin hepsi | 22/32 | 22/32 | 22/32 | 26/32 | 22/32 | 22/32 | 22/32 |
| Getirme: beklenen madde (toplam) | 45/57 | 45/57 | 45/57 | 50/57 | 45/57 | 45/57 | 45/57 |
| Atıf: beklenen maddeden en az biri [n] ile | 30/32 | 30/32 | 30/32 | 31/32 | 31/32 | 31/32 | 31/32 |
| **must** kapsamı | 45/61 (yok 13, çelişki 0, doğrulanamadı 3) | 41/61 (yok 15, çelişki 1, doğrulanamadı 4) | 43/61 (yok 16, çelişki 0, doğrulanamadı 2) | 44/61 (yok 12, çelişki 1, doğrulanamadı 4) | 50/61 (yok 10, çelişki 0, doğrulanamadı 1) | 48/61 (yok 12, çelişki 1, doğrulanamadı 0) | 49/61 (yok 10, çelişki 0, doğrulanamadı 2) |
| should kapsamı | 10/26 (yok 16, çelişki 0, doğrulanamadı 0) | 9/26 (yok 17, çelişki 0, doğrulanamadı 0) | 10/26 (yok 16, çelişki 0, doğrulanamadı 0) | 7/26 (yok 19, çelişki 0, doğrulanamadı 0) | 9/26 (yok 17, çelişki 0, doğrulanamadı 0) | 8/26 (yok 18, çelişki 0, doğrulanamadı 0) | 9/26 (yok 17, çelişki 0, doğrulanamadı 0) |
| **Çelişki (contradicted)** | 0 | 1 | 0 | 1 | 0 | 1 | 0 |
| Doğrulanamayan hakem kararı | 3 | 4 | 2 | 4 | 1 | 0 | 2 |
| Reddetme: refused=true | 4/4 | 3/4 | 3/4 | 3/4 | 3/4 | 4/4 | 4/4 |
| Reddetme: boş + kaynakta yok dedi | 4/4 | 3/4 | 3/4 | 3/4 | 3/4 | 4/4 | 4/4 |
| Yanlış ret | 2/32 | 2/32 | 2/32 | 1/32 | 1/32 | 0/32 | 1/32 |
| depends_on: soru / madde / soruda zaten var | 8 / 8 / 0 | 7 / 9 / 0 | 8 / 9 / 0 | 11 / 12 / 0 | 11 / 14 / 1 | 7 / 8 / 0 | 9 / 11 / 0 |
| Üretim süresi EU: medyan / en çok (soru) | 5.7 / 6.8 sn (14) | 6.3 / 11.8 sn (14) | 5.8 / 8.0 sn (14) | 5.9 / 7.2 sn (14) | 6.2 / 7.9 sn (14) | 6.0 / 6.7 sn (14) | 6.2 / 7.3 sn (14) |
| Üretim süresi TR: medyan / en çok (soru) | 5.3 / 6.3 sn (16) | 6.1 / 11.4 sn (16) | 6.0 / 7.7 sn (16) | 5.9 / 8.0 sn (16) | 6.1 / 7.6 sn (16) | 5.9 / 7.2 sn (16) | 5.9 / 10.9 sn (16) |
| Üretim süresi compare: medyan / en çok (soru) | 5.8 / 7.1 sn (6) | 6.4 / 10.4 sn (6) | 6.6 / 7.9 sn (6) | 6.7 / 7.1 sn (6) | 6.3 / 7.7 sn (6) | 6.9 / 7.6 sn (6) | 6.8 / 7.7 sn (6) |
| Ortalama token: prompt / çıktı | 5235 / 322 | 5235 / 306 | 5235 / 296 | 6983 / 338 | 5396 / 376 | 5442 / 338 | 5422 / 352 |
| Gemini çağrısı: embedding (önbellek) / üretim / hakem / yeniden deneme | 36 (0) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 |

## Yapılandırma

| | A | A2 | B | H1all | F1 | F2 | H5 |
|---|---|---|---|---|---|---|---|
| generation_model | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite |
| thinking_level | default (minimal) | default (minimal) | low | default (minimal) | default (minimal) | default (minimal) | default (minimal) |
| judge_model | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite |
| top_k | 8 | 8 | 8 | 8 | 8 | 8 | 8 |
| list_top_k | 14 | 14 | 14 | 14 | 14 | 14 | 14 |
| compare_per_side | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| core_sections |  | off | off | all | off | off | off |
| prompt_sha | 0b579e927c61 | 0b579e927c61 | 0b579e927c61 | 0b579e927c61 | 4d69e0186ead | b0ae697a0014 | 80baeb68cee0 |
| git | 568f665 | aabf77a | aabf77a | aabf77a | 4304733 | 8778a87 | 8778a87+dirty(app) |
| note | baseline: settings as deployed after PR 7 | repeat of A (noise) | A + thinking low | A + core sections for every question (H1) | A + general prompt fixes (conditions, general rule, everyday descriptions, one language) | F1 + refuse questions regulations do not settle | F2 without the transitional-provisions sentence (ablation) |
| questions | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml |
| sonuç dosyası | `eval/results/2026-10-08T0510-A.json` | `eval/results/2026-10-08T0946-A2.json` | `eval/results/2026-10-08T0930-B.json` | `eval/results/2026-10-08T0936-H1all.json` | `eval/results/2026-10-08T1001-F1.json` | `eval/results/2026-10-08T1009-F2.json` | `eval/results/2026-10-08T1015-H5.json` |
| durum | complete | complete | complete | complete | complete | complete | complete |

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
| F2 | F1 + mevzuatın çözmediği sorular (satın alma önerisi, fiyat, ücret, maliyet) reddedilsin, yakın bir soru cevaplanmasın (kural 7) | tam koşu | reddetme 3/4 → **4/4**, yanlış ret 1 → **0/32**; must 48/61 (F1: 50, gürültü içinde), çelişki 1 (x-01 C1; aynı hata A2'de de var, F2'ye bağlı değil) | **tutuldu** |
| H5 | F2'den "geçiş hükümleri yalnız soru geçişle ilgiliyse" cümlesi çıkarıldı (ablasyon) | tam koşu | must 49/61, çelişki 0, ret 4/4, yanlış ret 1; F2'den farkı gürültü içinde. Setin hiçbir sorusu bu hatayı tetiklemiyor (PR 6 duman testi Q2 setin dışında) | kural **korundu** (ölçülebilir etkisi yok, zararı da yok; karar Atıl'ın) |
| H6 | Gecikme, mod bazında | bütün koşular | üretim medyanı EU 5,7–6,3 · TR 5,3–6,1 · compare 5,8–6,9 sn; en çok 11,8 sn; zaman aşımı yok | compare_per_side 6 kaldı (ayar gerekmiyor) |

## Hata sınıfları — F2

Sınıflar otomatik çıkarılır: tespit (mod kabul listesinde değil), getirme (eksik must var ve beklenen maddelerden biri getirilmemiş), üretim (eksik must var ve beklenen maddelerden en az biri getirilmiş; çelişki ayrı), atıf (beklenen madde getirildi ama hiçbiri [n] ile gösterilmedi), reddetme, depends_on (soruda zaten olan bilgiyi soruyor). Bir soru birden çok sınıfta olabilir.

| Hata sınıfı | Soru sayısı | Sorular |
|---|---|---|
| üretim | 8 | tr-03, tr-04, tr-07, tr-10, en-09, x-01, j-01, k-05 |
| getirme | 5 | tr-03, tr-10, en-09, j-01, k-01 |
| üretim (çelişki) | 1 | x-01 |

## Soru bazında — F2

must/should: ✓ var · ✗ yok · ‼ çelişki · ? doğrulanamadı. Sıra: beklenen maddenin modele verilen parçalar arasındaki yeri (1 = ilk).

| id | tespit (mod) | liste / parça | beklenen maddelerin sırası | atıf | must | should | ret | depends_on | üretim sn | hata sınıfı |
|---|---|---|---|---|---|---|---|---|---|---|
| tr-01 | ✓ TR→TR |  8 | Madde 15: 1, Madde 11: yok | ✓ | m1✓ m2✓ m3✓ | s1✗ |  | 0 | 2.3 | — |
| tr-02 | ✓ TR→TR | liste 14 | Madde 8: 2 | ✓ | m1✓ | — |  | 0 | 5.6 | — |
| tr-03 | ✓ null→TR |  8 | Madde 8: 5, Madde 4: 3, Madde 11: 1, Madde 15: 4, Madde 12: yok | ✓ | m1✗ m2✓ m3✗ | s1✗ |  | 0 | 5.8 | getirme, üretim |
| tr-04 | ✓ TR→TR |  8 | Madde 29: 1 | ✓ | m1✓ m2✗ | s1✗ |  | 0 | 5.9 | üretim |
| tr-05 | ✓ TR→TR |  8 | Geçici Madde 1: 1 | ✓ | m1✓ m2✓ | s1✗ |  | 0 | 6.2 | — |
| tr-06 | ✓ null→TR | liste 14 | Madde 27: 1, Geçici Madde 2: 6, Madde 25: 4 | ✓ | m1✓ m2✓ m3✓ | s1✓ |  | 1 | 7.2 | — |
| tr-07 | ✓ TR→TR |  8 | Madde 12: 1 | ✓ | m1✗ m2✓ m3✓ | — |  | 1 | 6.3 | üretim |
| tr-08 | ✓ TR→TR |  8 | Madde 15: 1 | ✓ | m1✓ | s1✗ |  | 0 | 5.8 | — |
| tr-09 | ✓ TR→TR |  8 | Madde 15: 1 | ✓ | m1✓ | s1✗ |  | 0 | 5.5 | — |
| tr-10 | ✓ TR→TR |  8 | Madde 24: 1, Madde 11: yok, Madde 15: yok, Madde 12: 3 | ✓ | m1✓ m2✗ | s1✓ |  | 2 | 7.2 | getirme, üretim |
| en-01 | ✓ EU→EU |  8 | Article 4 (2019/947): 1, UAS.OPEN.010: 2 | ✓ | m1✓ m2✓ | s1✓ s2✓ |  | 0 | 5.8 | — |
| en-02 | ✓ null→EU |  8 | Article 14 (2019/947): 1, Madde 11: yok | ✓ | m1✓ | s1✗ s2✗ |  | 1 | 6.5 | — |
| en-03 | ✓ EU→EU |  8 | UAS.OPEN.030: 2, AMC1 UAS.OPEN.030(1): 1, Part 3 (2019/945 Annex): yok | ✓ | m1✓ m2✓ | s1✗ s2✓ |  | 0 | 6.3 | — |
| en-04 | ✓ EU→EU |  8 | UAS.OPEN.040: 2 | ✓ | m1✓ | — |  | 0 | 5.4 | — |
| en-05 | ✓ EU→EU |  8 | UAS.OPEN.020: 1 | ✓ | m1✓ m2✓ | — |  | 0 | 5.8 | — |
| en-06 | ✓ EU→EU |  8 | UAS.OPEN.070: 1 | ✓ | m1✓ | — |  | 0 | 5.7 | — |
| en-07 | ✓ EU→EU | liste 14 | Part 1 (2019/945 Annex): 1 | ✓ | m1✓ m2✓ m3✓ | s1✓ s2✓ |  | 0 | 6.7 | — |
| en-08 | ✓ EU→EU |  8 | UAS.OPEN.060: 6 | ✓ | m1✓ | — |  | 0 | 5.4 | — |
| en-09 | ✓ EU→EU |  8 | Article 5 (2019/947): 6, Article 12 (2019/947): 1, UAS.SPEC.020: yok | ✓ | m1✓ m2✗ | s1✗ s2✗ |  | 0 | 6.1 | getirme, üretim |
| en-10 | ✓ null→EU |  8 | Article 5 (2019/947): yok, Article 11 (2019/947): 3, Madde 9: yok | ✓ | m1✓ | s1✗ s2✗ |  | 0 | 6.0 | — |
| x-01 | ✓ EU→EU |  8 | UAS.OPEN.020: 1 | ✓ | m1✓ m2‼ | — |  | 1 | 6.7 | üretim (çelişki), üretim |
| x-02 | ✓ TR→TR |  8 | Madde 6: 2, Madde 15: 3 | ✓ | m1✓ | — |  | 0 | 5.8 | — |
| x-03 | ✓ compare→compare |  12 | Madde 17: 1, Article 9 (2019/947): 7 | ✓ | m1✓ m2✓ m3✓ | s1✓ |  | 0 | 7.2 | — |
| x-04 | ✓ TR→TR |  8 | Madde 23: 7 | ✓ | m1✓ | — |  | 1 | 6.0 | — |
| r-01 | ✓ null→TR |  8 | — |  | — | — | ✓ | 0 | 5.9 | — |
| r-02 | ✓ null→EU |  8 | — |  | — | — | ✓ | 0 | 6.0 | — |
| r-03 | ✓ null→TR | liste 14 | — |  | — | — | ✓ | 0 | 5.9 | — |
| r-04 | ✓ EU→EU |  8 | — |  | — | — | ✓ | 0 | 5.9 | — |
| j-01 | ✓ null→TR |  8 | Madde 15: 2, Article 4 (2019/947): yok | ✓ | m1✗ m2✓ m3✗ | s1✗ |  | 1 | 6.8 | getirme, üretim |
| j-02 | ✓ EU→EU |  8 | UAS.OPEN.020: 2, Part 1 (2019/945 Annex): 4 | ✓ | m1✓ m2✓ | — |  | 0 | 6.7 | — |
| j-03 | ✓ TR→TR |  8 | Madde 17: 2 | ✓ | m1✓ | — |  | 0 | 5.7 | — |
| k-01 | ✓ compare→compare |  12 | Article 41 (2019/945): yok | ✗ | m1✗ m2✗ m3✗ | s1✗ |  | 0 | 5.7 | getirme |
| k-02 | ✓ compare→compare |  12 | Madde 10: 4, Madde 15: yok | ✓ | m1✓ m2✓ | s1✗ |  | 0 | 6.9 | — |
| k-03 | ✓ compare→compare |  12 | Madde 15: 7 | ✓ | m1✓ | — |  | 0 | 5.6 | — |
| k-04 | ✓ compare→compare |  12 | Madde 15: 1, UAS.OPEN.030: 7 | ✓ | m1✓ m2✓ | s1✗ |  | 0 | 7.6 | — |
| k-05 | ✓ compare→compare |  12 | Madde 8: 1, Part 1 (2019/945 Annex): 7 | ✓ | m1✗ m2✓ m3✓ | s1✗ |  | 0 | 6.9 | üretim |

## Hakem kararlarını elle kontrol — F2

Bütün çelişki ve doğrulanamayan kararlar, ayrıca 5 örnek var/yok kararı.

| id | fact | karar | alıntı (cevaptan) | not |
|---|---|---|---|---|
| x-01 | m2: C1: ilgisiz kişilerin üzerinden uçulmaması beklenir; beklenmedik durumda süre en aza indirilir | contradicted | C1 sınıfı insansız hava araçları ile uninvolved kişilerin üzerinden geçilebilir ancak kalabalık insan topluluklarının (assemblies of people) üzerinden kesinlikle uçulamaz |  |
| tr-01 | m1: azami 120 m yükseklik | present | azami 120 metre yükseklik |  |
| tr-06 | m3: süre sonunda dönüştürülmemiş araç uçurulamaz | present | dönüştürülmemiş ve yazılım sertifikasyonu bulunmayan insansız hava araçları, dönüştürme tamamlanıncaya veya sertifikalandırılıncaya kadar Türk hava sahasında işletilemez ve kullanılamaz. |  |
| en-02 | s1: registration is also required at 250 g or more or above 80 J | absent |  |  |
| en-09 | m2: authorisation from the competent authority of the state of registration, with a risk assessment | absent |  |  |
| j-02 | m1: 250 g altı / C0 ile A1'de çevrim içi eğitim ve sınav şartı yok; zorunlu eğitim C1 için | present | sınıf C1 gibi çevrim içi eğitim ve sınav zorunluluğu bu araçlar için aranmaz. |  |
