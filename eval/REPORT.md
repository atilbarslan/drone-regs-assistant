# Değerlendirme raporu

Bu dosya `python -m eval.report` ile üretilir; elle düzenlenmez (değişiklik ve hipotez tablosu `eval/CHANGES.md`'den aynen alınır). Yöntem: `eval/run.py` ve `eval/score.py` başları.

Gemini çağrıları her koşunun satırında (son satır). Hakem: her soru için tek çağrı; "present"/"contradicted" kararları cevaptan birebir alıntı ister, alıntı bulunamazsa "doğrulanamadı" sayılır.

## Özet

| Ölçü | A | A2 | B | H1all | F1 | F2 | H5 | F3 | C |
|---|---|---|---|---|---|---|---|---|---|
| Soru (hata) | 36 (0) | 36 (0) | 36 (0) | 36 (0) | 36 (0) | 36 (0) | 36 (0) | 36 (0) | 14 (13) |
| Anahtarı değişip yeniden puanlanan | j-01 | — | — | — | — | j-01 | — | — | — |
| Tespit doğru | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 | 1/1 |
| Getirme: beklenen maddeden en az biri | 31/32 | 31/32 | 31/32 | 31/32 | 31/32 | 31/32 | 31/32 | 31/32 | 0/1 |
| Getirme: beklenen maddelerin hepsi | 23/32 | 22/32 | 22/32 | 26/32 | 22/32 | 23/32 | 22/32 | 23/32 | 0/1 |
| Getirme: beklenen madde (toplam) | 45/56 | 45/57 | 45/57 | 50/57 | 45/57 | 45/56 | 45/57 | 45/56 | 0/1 |
| Atıf: beklenen maddeden en az biri [n] ile | 30/32 | 30/32 | 30/32 | 31/32 | 31/32 | 31/32 | 31/32 | 31/32 | 0/1 |
| **must** kapsamı | 45/59 (yok 11, çelişki 0, doğrulanamadı 3) | 41/61 (yok 15, çelişki 1, doğrulanamadı 4) | 43/61 (yok 16, çelişki 0, doğrulanamadı 2) | 44/61 (yok 12, çelişki 1, doğrulanamadı 4) | 50/61 (yok 10, çelişki 0, doğrulanamadı 1) | 48/59 (yok 10, çelişki 1, doğrulanamadı 0) | 49/61 (yok 10, çelişki 0, doğrulanamadı 2) | 48/59 (yok 9, çelişki 0, doğrulanamadı 2) | 1/3 (yok 2, çelişki 0, doğrulanamadı 0) |
| should kapsamı | 10/27 (yok 17, çelişki 0, doğrulanamadı 0) | 9/26 (yok 17, çelişki 0, doğrulanamadı 0) | 10/26 (yok 16, çelişki 0, doğrulanamadı 0) | 7/26 (yok 19, çelişki 0, doğrulanamadı 0) | 9/26 (yok 17, çelişki 0, doğrulanamadı 0) | 8/27 (yok 19, çelişki 0, doğrulanamadı 0) | 9/26 (yok 17, çelişki 0, doğrulanamadı 0) | 8/27 (yok 18, çelişki 0, doğrulanamadı 1) | 0/1 (yok 1, çelişki 0, doğrulanamadı 0) |
| **Çelişki (contradicted)** | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 |
| Doğrulanamayan hakem kararı | 3 | 4 | 2 | 4 | 1 | 0 | 2 | 3 | 0 |
| Reddetme: refused=true | 4/4 | 3/4 | 3/4 | 3/4 | 3/4 | 4/4 | 4/4 | 4/4 | 0/0 |
| Reddetme: boş + kaynakta yok dedi | 4/4 | 3/4 | 3/4 | 3/4 | 3/4 | 4/4 | 4/4 | 4/4 | 0/0 |
| Yanlış ret | 2/32 | 2/32 | 2/32 | 1/32 | 1/32 | 0/32 | 1/32 | 1/32 | 0/1 |
| depends_on: soru / madde / soruda zaten var | 8 / 8 / 0 | 7 / 9 / 0 | 8 / 9 / 0 | 11 / 12 / 0 | 11 / 14 / 1 | 7 / 8 / 0 | 9 / 11 / 0 | 8 / 10 / 0 | 0 / 0 / 0 |
| Üretim süresi EU: medyan / en çok (soru) | 5.7 / 6.8 sn (14) | 6.3 / 11.8 sn (14) | 5.8 / 8.0 sn (14) | 5.9 / 7.2 sn (14) | 6.2 / 7.9 sn (14) | 6.0 / 6.7 sn (14) | 6.2 / 7.3 sn (14) | 5.9 / 8.6 sn (14) | — |
| Üretim süresi TR: medyan / en çok (soru) | 5.3 / 6.3 sn (16) | 6.1 / 11.4 sn (16) | 6.0 / 7.7 sn (16) | 5.9 / 8.0 sn (16) | 6.1 / 7.6 sn (16) | 5.9 / 7.2 sn (16) | 5.9 / 10.9 sn (16) | 6.1 / 7.8 sn (16) | — |
| Üretim süresi compare: medyan / en çok (soru) | 5.8 / 7.1 sn (6) | 6.4 / 10.4 sn (6) | 6.6 / 7.9 sn (6) | 6.7 / 7.1 sn (6) | 6.3 / 7.7 sn (6) | 6.9 / 7.6 sn (6) | 6.8 / 7.7 sn (6) | 6.6 / 8.1 sn (6) | 45.4 / 45.4 sn (1) |
| Ortalama token: prompt / çıktı | 5235 / 322 | 5235 / 306 | 5235 / 296 | 6983 / 338 | 5396 / 376 | 5442 / 338 | 5422 / 352 | 5569 / 342 | 7558 / 719 |
| Gemini çağrısı: embedding (önbellek) / üretim / hakem / yeniden deneme | 36 (0) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (14) / 14 / 1 / 0 |

## Yapılandırma

| | A | A2 | B | H1all | F1 | F2 | H5 | F3 | C |
|---|---|---|---|---|---|---|---|---|---|
| generation_model | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.8-flash |
| thinking_level | default (minimal) | default (minimal) | low | default (minimal) | default (minimal) | default (minimal) | default (minimal) | default (minimal) | default (minimal) |
| judge_model | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite |
| top_k | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 |
| list_top_k | 14 | 14 | 14 | 14 | 14 | 14 | 14 | 14 | 14 |
| compare_per_side | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| core_sections |  | off | off | all | off | off | off | off | off |
| prompt_sha | 0b579e927c61 | 0b579e927c61 | 0b579e927c61 | 0b579e927c61 | 4d69e0186ead | b0ae697a0014 | 80baeb68cee0 | b5f911baaf76 | 0b579e927c61 |
| git | 568f665 | aabf77a | aabf77a | aabf77a | 4304733 | 8778a87 | 8778a87+dirty(app) | c8262f0 | c8262f0+dirty(app) |
| note | baseline: settings as deployed after PR 7 | repeat of A (noise) | A + thinking low | A + core sections for every question (H1) | A + general prompt fixes (conditions, general rule, everyday descriptions, one language) | F1 + refuse questions regulations do not settle | F2 without the transitional-provisions sentence (ablation) | F2 + case arms, not_in_sources scope, no internal words, Turkish terms first | A prompt, stronger model, questions wrong in A or B; no retries |
| questions | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml | /Users/atil/Desktop/drone-regs-assistant/eval/questions.yaml |
| sonuç dosyası | `eval/results/2026-10-08T0510-A.json` | `eval/results/2026-10-08T0946-A2.json` | `eval/results/2026-10-08T0930-B.json` | `eval/results/2026-10-08T0936-H1all.json` | `eval/results/2026-10-08T1001-F1.json` | `eval/results/2026-10-08T1009-F2.json` | `eval/results/2026-10-08T1015-H5.json` | `eval/results/2026-10-09T0842-F3.json` | `eval/results/2026-10-09T0848-C.json` |
| durum | complete | complete | complete | complete | complete | complete | complete | complete | complete |

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
| j-01 | **Anahtar değişti** (Atıl'ın onayı, 8 Ekim): PR 6 tasarımı kalıyor; sinyalsiz soru sayfa dilindeki tarafta cevaplanır. Beklenen kaynak yalnız Madde 15; must 3 → 1 ("Türkiye: P0/P1 azami 120 m; P2'de …"), AB 120 m ve engel istisnası should | A ve F2 yeniden puanlandı (`eval/rescore.py`, 2 hakem çağrısı) | A: must 45/59, F2: 48/59 (toplam must 61 → 59). A2, F1, B, H1all, H5 eski anahtarla kaldı (61) | — |
| F3 | F2 + (a) bir case'in izni/muafiyeti/sınırı başka case'e taşınmaz (kural 4); (b) not_in_sources yalnız sorulan ya da cevap için gereken eksikler (kural 7); (c) cevapta prompt'un iç kelimeleri yok, "kaynaklar" denir (kural 11) + sunucuda `scrub_internal_terms`; (d) Türkçede terim önce Türkçe, İngilizcesi gerekirse parantezde (kural 9) | tam koşu | must 48/59 (F2: 48), çelişki 1 → **0**, ret 4/4, yanlış ret 0 → 1 (k-01; 7 koşunun 5'inde aynı, getirme). Hedefler: x-01 C1 kolu çelişki → var; sorulmamış ücret/fiyat başlığı 3 → 1 soru; iç kelime 6 → **0** cevap (ham çıktıda da 0: prompt kuralı yetti, sunucu kontrolü güvenlik ağı); parantezsiz İngilizce terim (Türkçe cevaplar) 5 → 2 | **tutuldu** |
| C (2. deneme) | gemini-3.8-flash, A prompt'u, `--retries 0`, 14 soru (j-01 yeni anahtarla) | 14 üretim + 1 hakem | 13 soruda yine `503 UNAVAILABLE`; iki günde 36 istekten 35'i 503. Cevaplanan tek soru k-01: reddetmedi (flash-lite 7 koşunun 5'inde reddetti) ama Article 41 getirilmediği için m1, m2 yine yok; üretim 45 sn | karşılaştırma yapılamadı; README'de "ücretsiz katmanın sınırı" olarak |

## Hata sınıfları — F3

Sınıflar otomatik çıkarılır: tespit (mod kabul listesinde değil), getirme (eksik must var ve beklenen maddelerden biri getirilmemiş), üretim (eksik must var ve beklenen maddelerden en az biri getirilmiş; çelişki ayrı), atıf (beklenen madde getirildi ama hiçbiri [n] ile gösterilmedi), reddetme, depends_on (soruda zaten olan bilgiyi soruyor). Bir soru birden çok sınıfta olabilir.

| Hata sınıfı | Soru sayısı | Sorular |
|---|---|---|
| üretim | 7 | tr-03, tr-07, en-09, en-10, x-03, k-04, k-05 |
| getirme | 4 | tr-03, en-09, en-10, k-01 |
| reddetme | 1 | k-01 |

## Soru bazında — F3

† anahtar değişti; kayıtlı cevap yeni anahtarla yeniden puanlandı (`eval/rescore.py`). must/should: ✓ var · ✗ yok · ‼ çelişki · ? doğrulanamadı. Sıra: beklenen maddenin modele verilen parçalar arasındaki yeri (1 = ilk).

| id | tespit (mod) | liste / parça | beklenen maddelerin sırası | atıf | must | should | ret | depends_on | üretim sn | hata sınıfı |
|---|---|---|---|---|---|---|---|---|---|---|
| tr-01 | ✓ TR→TR |  8 | Madde 15: 1, Madde 11: yok | ✓ | m1✓ m2✓ m3✓ | s1✗ |  | 0 | 1.8 | — |
| tr-02 | ✓ TR→TR | liste 14 | Madde 8: 2 | ✓ | m1✓ | — |  | 0 | 5.7 | — |
| tr-03 | ✓ null→TR |  8 | Madde 8: 5, Madde 4: 3, Madde 11: 1, Madde 15: 4, Madde 12: yok | ✓ | m1✗ m2✓ m3✗ | s1✗ |  | 0 | 5.8 | getirme, üretim |
| tr-04 | ✓ TR→TR |  8 | Madde 29: 1 | ✓ | m1✓ m2✓ | s1✓ |  | 0 | 6.1 | — |
| tr-05 | ✓ TR→TR |  8 | Geçici Madde 1: 1 | ✓ | m1✓ m2✓ | s1✗ |  | 0 | 7.0 | — |
| tr-06 | ✓ null→TR | liste 14 | Madde 27: 1, Geçici Madde 2: 6, Madde 25: 4 | ✓ | m1✓ m2✓ m3✓ | s1✓ |  | 1 | 6.6 | — |
| tr-07 | ✓ TR→TR |  8 | Madde 12: 1 | ✓ | m1✓ m2✓ m3✗ | — |  | 0 | 5.7 | üretim |
| tr-08 | ✓ TR→TR |  8 | Madde 15: 1 | ✓ | m1✓ | s1✓ |  | 0 | 6.1 | — |
| tr-09 | ✓ TR→TR |  8 | Madde 15: 1 | ✓ | m1✓ | s1✗ |  | 0 | 5.8 | — |
| tr-10 | ✓ TR→TR |  8 | Madde 24: 1, Madde 11: yok, Madde 15: yok, Madde 12: 3 | ✓ | m1✓ m2✓ | s1✓ |  | 2 | 7.8 | — |
| en-01 | ✓ EU→EU |  8 | Article 4 (2019/947): 1, UAS.OPEN.010: 2 | ✓ | m1✓ m2✓ | s1✓ s2✓ |  | 0 | 5.6 | — |
| en-02 | ✓ null→EU |  8 | Article 14 (2019/947): 1, Madde 11: yok | ✓ | m1✓ | s1✗ s2✗ |  | 1 | 6.1 | — |
| en-03 | ✓ EU→EU |  8 | UAS.OPEN.030: 2, AMC1 UAS.OPEN.030(1): 1, Part 3 (2019/945 Annex): yok | ✓ | m1✓ m2✓ | s1✗ s2✗ |  | 0 | 5.8 | — |
| en-04 | ✓ EU→EU |  8 | UAS.OPEN.040: 2 | ✓ | m1✓ | — |  | 0 | 5.5 | — |
| en-05 | ✓ EU→EU |  8 | UAS.OPEN.020: 1 | ✓ | m1✓ m2✓ | — |  | 0 | 4.9 | — |
| en-06 | ✓ EU→EU |  8 | UAS.OPEN.070: 1 | ✓ | m1✓ | — |  | 0 | 5.6 | — |
| en-07 | ✓ EU→EU | liste 14 | Part 1 (2019/945 Annex): 1 | ✓ | m1✓ m2✓ m3✓ | s1✓ s2✓ |  | 0 | 7.9 | — |
| en-08 | ✓ EU→EU |  8 | UAS.OPEN.060: 6 | ✓ | m1✓ | — |  | 0 | 1.7 | — |
| en-09 | ✓ EU→EU |  8 | Article 5 (2019/947): 6, Article 12 (2019/947): 1, UAS.SPEC.020: yok | ✓ | m1✓ m2✗ | s1✗ s2✗ |  | 0 | 6.2 | getirme, üretim |
| en-10 | ✓ null→EU |  8 | Article 5 (2019/947): yok, Article 11 (2019/947): 3, Madde 9: yok | ✓ | m1? | s1✗ s2✗ |  | 0 | 6.7 | getirme, üretim |
| x-01 | ✓ EU→EU |  8 | UAS.OPEN.020: 1 | ✓ | m1✓ m2✓ | — |  | 1 | 8.6 | — |
| x-02 | ✓ TR→TR |  8 | Madde 6: 2, Madde 15: 3 | ✓ | m1✓ | — |  | 0 | 6.1 | — |
| x-03 | ✓ compare→compare |  12 | Madde 17: 1, Article 9 (2019/947): 7 | ✓ | m1✓ m2✓ m3? | s1? |  | 1 | 8.1 | üretim |
| x-04 | ✓ TR→TR |  8 | Madde 23: 7 | ✓ | m1✓ | — |  | 2 | 6.3 | — |
| r-01 | ✓ null→TR |  8 | — |  | — | — | ✓ | 0 | 5.3 | — |
| r-02 | ✓ null→EU |  8 | — |  | — | — | ✓ | 0 | 6.0 | — |
| r-03 | ✓ null→TR | liste 14 | — |  | — | — | ✓ | 0 | 5.9 | — |
| r-04 | ✓ EU→EU |  8 | — |  | — | — | ✓ | 0 | 5.8 | — |
| j-01 | ✓ null→TR |  8 | Madde 15: 2 | ✓ | m1✓ | s1✗ s2✗ |  | 1 | 7.2 | — |
| j-02 | ✓ EU→EU |  8 | UAS.OPEN.020: 2, Part 1 (2019/945 Annex): 4 | ✓ | m1✓ m2✓ | — |  | 1 | 6.7 | — |
| j-03 | ✓ TR→TR |  8 | Madde 17: 2 | ✓ | m1✓ | — |  | 0 | 7.1 | — |
| k-01 | ✓ compare→compare |  12 | Article 41 (2019/945): yok | ✗ | m1✗ m2✗ m3✓ | s1✗ | yanlış ret | 0 | 5.8 | reddetme, getirme |
| k-02 | ✓ compare→compare |  12 | Madde 10: 4, Madde 15: yok | ✓ | m1✓ m2✓ | s1✗ |  | 0 | 6.3 | — |
| k-03 | ✓ compare→compare |  12 | Madde 15: 7 | ✓ | m1✓ | — |  | 0 | 5.5 | — |
| k-04 | ✓ compare→compare |  12 | Madde 15: 1, UAS.OPEN.030: 7 | ✓ | m1✗ m2✗ | s1✗ |  | 0 | 7.3 | üretim |
| k-05 | ✓ compare→compare |  12 | Madde 8: 1, Part 1 (2019/945 Annex): 7 | ✓ | m1✗ m2✓ m3✓ | s1✗ |  | 0 | 6.9 | üretim |

## Hakem kararlarını elle kontrol — F3

Bütün çelişki ve doğrulanamayan kararlar, ayrıca 5 örnek var/yok kararı.

| id | fact | karar | alıntı (cevaptan) | not |
|---|---|---|---|---|
| en-10 | m1: a risk assessment according to Article 11, with adequate mitigating measures | unverified | submitting an application based on an operational risk assessment in accordance with Article 11. [...] identify possible risk mitigating measures, and determine the necessary level of robustness of those measures. | judge said present; quote not found |
| x-03 | m3: AB'de üye devlet açık kategoride en fazla 4 yıl, specific kategoride en fazla 2 yıl düşürebilir (yani yaşın kendisi değil indirim miktarı) | unverified | AB'de üye devletler risk temelli yaklaşım izleyerek açık kategoride yaşı en fazla 4 yıl, özel kategoride en fazla 2 yıl düşürebilirler | judge said present; quote not found |
| x-03 | s1: AB istisnaları: C0 oyuncak ile A1, 250 g altı kendi yapımı, gözetim altında uçuş | unverified | AB'de A1 alt kategorisinde oyuncak sınıfı C0 İHA'lar, 250 gramdan hafif özel yapım İHA'lar ile 16 yaş şartını sağlayan bir pilotun doğrudan denetimi altında uçuş yapanlar için asgari yaş aranmaz. | judge said present; quote not found |
| tr-01 | m1: azami 120 m yükseklik | present | azami 120 metre yükseklik |  |
| tr-06 | m2: son tarih 31/07/2027 | present | son tarih 31/07/2027 olarak belirlenmiştir. |  |
| en-01 | s2: unmanned sailplanes under 10 kg exception | present | unmanned sailplanes with a maximum take-off mass including payload of less than 10 kg may be flown at a distance exceeding 120 metres from the surface of the earth |  |
| en-07 | s2: follow-me mode within 50 m | present | If equipped with a follow-me mode, the UAS must remain in a range not exceeding 50 m from the remote pilot when the function is on |  |
| j-01 | s2: AB'de engel istisnası (50 m içinde, 105 m üstü engel, +15 m) | absent |  |  |
