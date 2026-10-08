# Değerlendirme raporu

Bu dosya `python -m eval.report` ile üretilir; elle düzenlenmez (değişiklik ve hipotez tablosu `eval/CHANGES.md`'den aynen alınır). Yöntem: `eval/run.py` ve `eval/score.py` başları.

Gemini çağrıları her koşunun satırında (son satır). Hakem: her soru için tek çağrı; "present"/"contradicted" kararları cevaptan birebir alıntı ister, alıntı bulunamazsa "doğrulanamadı" sayılır.

## Özet

| Ölçü | A | B | H1all |
|---|---|---|---|
| Soru (hata) | 36 (0) | 36 (0) | 36 (0) |
| Tespit doğru | 36/36 | 36/36 | 36/36 |
| Getirme: beklenen maddeden en az biri | 31/32 | 31/32 | 31/32 |
| Getirme: beklenen maddelerin hepsi | 22/32 | 22/32 | 26/32 |
| Getirme: beklenen madde (toplam) | 45/57 | 45/57 | 50/57 |
| Atıf: beklenen maddeden en az biri [n] ile | 30/32 | 30/32 | 31/32 |
| **must** kapsamı | 45/61 (yok 13, çelişki 0, doğrulanamadı 3) | 43/61 (yok 16, çelişki 0, doğrulanamadı 2) | 44/61 (yok 12, çelişki 1, doğrulanamadı 4) |
| should kapsamı | 10/26 (yok 16, çelişki 0, doğrulanamadı 0) | 10/26 (yok 16, çelişki 0, doğrulanamadı 0) | 7/26 (yok 19, çelişki 0, doğrulanamadı 0) |
| **Çelişki (contradicted)** | 0 | 0 | 1 |
| Doğrulanamayan hakem kararı | 3 | 2 | 4 |
| Reddetme: refused=true | 4/4 | 3/4 | 3/4 |
| Reddetme: boş + kaynakta yok dedi | 4/4 | 3/4 | 3/4 |
| Yanlış ret | 2/32 | 2/32 | 1/32 |
| depends_on: soru / madde / soruda zaten var | 8 / 8 / 0 | 8 / 9 / 0 | 11 / 12 / 0 |
| Üretim süresi EU: medyan / en çok (soru) | 5.7 / 6.8 sn (14) | 5.8 / 8.0 sn (14) | 5.9 / 7.2 sn (14) |
| Üretim süresi TR: medyan / en çok (soru) | 5.3 / 6.3 sn (16) | 6.0 / 7.7 sn (16) | 5.9 / 8.0 sn (16) |
| Üretim süresi compare: medyan / en çok (soru) | 5.8 / 7.1 sn (6) | 6.6 / 7.9 sn (6) | 6.7 / 7.1 sn (6) |
| Ortalama token: prompt / çıktı | 5235 / 322 | 5235 / 296 | 6983 / 338 |
| Gemini çağrısı: embedding (önbellek) / üretim / hakem / yeniden deneme | 36 (0) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 | 0 (36) / 36 / 36 / 0 |

## Yapılandırma

| | A | B | H1all |
|---|---|---|---|
| generation_model | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite |
| thinking_level | default (minimal) | low | default (minimal) |
| judge_model | gemini-3.5-flash-lite | gemini-3.5-flash-lite | gemini-3.5-flash-lite |
| top_k | 8 | 8 | 8 |
| list_top_k | 14 | 14 | 14 |
| compare_per_side | 6 | 6 | 6 |
| core_sections |  | off | all |
| prompt_sha | 0b579e927c61 | 0b579e927c61 | 0b579e927c61 |
| git | 568f665 | aabf77a | aabf77a |
| note | baseline: settings as deployed after PR 7 | A + thinking low | A + core sections for every question (H1) |
| questions | eval/questions.yaml | eval/questions.yaml | eval/questions.yaml |
| sonuç dosyası | `eval/results/2026-10-08T0510-A.json` | `eval/results/2026-10-08T0930-B.json` | `eval/results/2026-10-08T0936-H1all.json` |
| durum | complete | complete | complete |

## Değişiklikler ve hipotezler

Her satır tüm sete (36 soru) karşı ölçüldü; "çevrimdışı" yazanlar yalnız getirmeyi ölçer (önbellekteki soru embedding'leriyle, üretim çağrısı yok). Öncesi/sonrası sayıları aynı soru setinden. Not: model deterministik değil; aynı yapılandırmanın iki koşusu arasında da birkaç fact oynayabilir (bkz. PR notu).

| # | Değişiklik / hipotez | Ölçüm | Sonuç | Karar |
|---|---|---|---|---|
| A | Temel çizgi (PR 7 sonrası ayarlar) | tam koşu | must 45/61, çelişki 0, ret 4/4, yanlış ret 2 | — |
| H2 | Liste sorusu kalıpları ("kurallar neler", "what rules apply" …) | çevrimdışı | setteki 36 sorunun hiçbirinin liste durumu değişmiyor | eklenmedi (etki ölçülemez) |
| H1-liste | Liste sorularına temel maddeler | çevrimdışı | getirme 45/57 → 45/57 (yalnız 4 liste sorusu; beklenen maddeleri zaten vardı) | eklenmedi |
| H1-hepsi | Her soruya temel maddeler | çevrimdışı | getirme 45/57 → 50/57; soru başına ortalama +3,6 parça | tam koşu bekliyor |

## Hata sınıfları — H1all

Sınıflar otomatik çıkarılır: tespit (mod kabul listesinde değil), getirme (eksik must var ve beklenen maddelerden biri getirilmemiş), üretim (eksik must var ve beklenen maddelerden en az biri getirilmiş; çelişki ayrı), atıf (beklenen madde getirildi ama hiçbiri [n] ile gösterilmedi), reddetme, depends_on (soruda zaten olan bilgiyi soruyor). Bir soru birden çok sınıfta olabilir.

| Hata sınıfı | Soru sayısı | Sorular |
|---|---|---|
| üretim | 9 | tr-03, tr-06, tr-07, tr-10, x-03, j-01, j-02, k-04, k-05 |
| reddetme | 2 | r-03, k-01 |
| getirme | 2 | j-01, k-01 |
| üretim (çelişki) | 1 | tr-03 |

## Soru bazında — H1all

must/should: ✓ var · ✗ yok · ‼ çelişki · ? doğrulanamadı. Sıra: beklenen maddenin modele verilen parçalar arasındaki yeri (1 = ilk).

| id | tespit (mod) | liste / parça | beklenen maddelerin sırası | atıf | must | should | ret | depends_on | üretim sn | hata sınıfı |
|---|---|---|---|---|---|---|---|---|---|---|
| tr-01 | ✓ TR→TR |  12 | Madde 15: 1, Madde 11: 9 | ✓ | m1✓ m2✓ m3✓ | s1✗ |  | 0 | 1.9 | — |
| tr-02 | ✓ TR→TR | liste 18 | Madde 8: 2 | ✓ | m1✓ | — |  | 0 | 5.7 | — |
| tr-03 | ✓ null→TR |  10 | Madde 8: 5, Madde 4: 3, Madde 11: 1, Madde 15: 4, Madde 12: 9 | ✓ | m1‼ m2✓ m3✗ | s1✗ |  | 0 | 5.6 | üretim (çelişki), üretim |
| tr-04 | ✓ TR→TR |  11 | Madde 29: 1 | ✓ | m1✓ m2✓ | s1✓ |  | 0 | 5.9 | — |
| tr-05 | ✓ TR→TR |  13 | Geçici Madde 1: 1 | ✓ | m1✓ m2✓ | s1✗ |  | 0 | 5.9 | — |
| tr-06 | ✓ null→TR | liste 17 | Madde 27: 1, Geçici Madde 2: 6, Madde 25: 4 | ✓ | m1✓ m2✓ m3✗ | s1✓ |  | 1 | 7.2 | üretim |
| tr-07 | ✓ TR→TR |  11 | Madde 12: 1 | ✓ | m1✗ m2✓ m3✗ | — |  | 0 | 5.6 | üretim |
| tr-08 | ✓ TR→TR |  10 | Madde 15: 1 | ✓ | m1✓ | s1✗ |  | 0 | 5.8 | — |
| tr-09 | ✓ TR→TR |  10 | Madde 15: 1 | ✓ | m1✓ | s1✗ |  | 0 | 6.0 | — |
| tr-10 | ✓ TR→TR |  11 | Madde 24: 1, Madde 11: 9, Madde 15: 11, Madde 12: 3 | ✓ | m1? m2✗ | s1✓ |  | 1 | 7.2 | üretim |
| en-01 | ✓ EU→EU |  11 | Article 4 (2019/947): 1, UAS.OPEN.010: 2 | ✓ | m1✓ m2✓ | s1✗ s2✗ |  | 1 | 6.3 | — |
| en-02 | ✓ null→EU |  10 | Article 14 (2019/947): 1, Madde 11: yok | ✓ | m1✓ | s1✗ s2✗ |  | 1 | 6.1 | — |
| en-03 | ✓ EU→EU |  12 | UAS.OPEN.030: 2, AMC1 UAS.OPEN.030(1): 1, Part 3 (2019/945 Annex): yok | ✓ | m1✓ m2✓ | s1✗ s2✗ |  | 0 | 5.6 | — |
| en-04 | ✓ EU→EU |  12 | UAS.OPEN.040: 2 | ✓ | m1✓ | — |  | 0 | 5.8 | — |
| en-05 | ✓ EU→EU |  11 | UAS.OPEN.020: 1 | ✓ | m1✓ m2✓ | — |  | 0 | 5.7 | — |
| en-06 | ✓ EU→EU |  12 | UAS.OPEN.070: 1 | ✓ | m1✓ | — |  | 0 | 5.5 | — |
| en-07 | ✓ EU→EU | liste 18 | Part 1 (2019/945 Annex): 1 | ✓ | m1✓ m2✓ m3✓ | s1✓ s2✓ |  | 0 | 6.8 | — |
| en-08 | ✓ EU→EU |  11 | UAS.OPEN.060: 6 | ✓ | m1✓ | — |  | 0 | 5.8 | — |
| en-09 | ✓ EU→EU |  11 | Article 5 (2019/947): 6, Article 12 (2019/947): 1, UAS.SPEC.020: yok | ✓ | m1✓ m2✓ | s1✗ s2✗ |  | 0 | 6.1 | — |
| en-10 | ✓ null→EU |  12 | Article 5 (2019/947): yok, Article 11 (2019/947): 3, Madde 9: yok | ✓ | m1✓ | s1✓ s2✗ |  | 0 | 6.0 | — |
| x-01 | ✓ EU→EU |  11 | UAS.OPEN.020: 1 | ✓ | m1✓ m2✓ | — |  | 1 | 7.2 | — |
| x-02 | ✓ TR→TR |  11 | Madde 6: 2, Madde 15: 3 | ✓ | m1✓ | — |  | 0 | 5.7 | — |
| x-03 | ✓ compare→compare |  18 | Madde 17: 1, Article 9 (2019/947): 10 | ✓ | m1✓ m2✓ m3✗ | s1✓ |  | 1 | 7.1 | üretim |
| x-04 | ✓ TR→TR |  11 | Madde 23: 7 | ✓ | m1✓ | — |  | 2 | 5.9 | — |
| r-01 | ✓ null→TR |  11 | — |  | — | — | ✓ | 0 | 5.7 | — |
| r-02 | ✓ null→EU |  12 | — |  | — | — | ✓ | 0 | 5.8 | — |
| r-03 | ✓ null→TR | liste 15 | — |  | — | — | ✗ | 1 | 8.0 | reddetme |
| r-04 | ✓ EU→EU |  10 | — |  | — | — | ✓ | 0 | 5.7 | — |
| j-01 | ✓ null→TR |  8 | Madde 15: 2, Article 4 (2019/947): yok | ✓ | m1✓ m2? m3✗ | s1✗ |  | 1 | 6.5 | getirme, üretim |
| j-02 | ✓ EU→EU |  10 | UAS.OPEN.020: 2, Part 1 (2019/945 Annex): 4 | ✓ | m1✓ m2✗ | — |  | 1 | 6.3 | üretim |
| j-03 | ✓ TR→TR |  10 | Madde 17: 2 | ✓ | m1✓ | — |  | 1 | 6.1 | — |
| k-01 | ✓ compare→compare |  19 | Article 41 (2019/945): yok | ✗ | m1✗ m2✗ m3✗ | s1✗ | yanlış ret | 0 | 5.9 | reddetme, getirme |
| k-02 | ✓ compare→compare |  21 | Madde 10: 4, Madde 15: 9 | ✓ | m1✓ m2✓ | s1✗ |  | 0 | 6.5 | — |
| k-03 | ✓ compare→compare |  18 | Madde 15: 11 | ✓ | m1✓ | — |  | 0 | 5.2 | — |
| k-04 | ✓ compare→compare |  20 | Madde 15: 1, UAS.OPEN.030: 11 | ✓ | m1? m2? | s1✗ |  | 0 | 7.1 | üretim |
| k-05 | ✓ compare→compare |  18 | Madde 8: 1, Part 1 (2019/945 Annex): 10 | ✓ | m1✗ m2✓ m3✓ | s1✗ |  | 0 | 6.8 | üretim |

## Hakem kararlarını elle kontrol — H1all

Bütün çelişki ve doğrulanamayan kararlar, ayrıca 5 örnek var/yok kararı.

| id | fact | karar | alıntı (cevaptan) | not |
|---|---|---|---|---|
| tr-03 | m1: cevap tanıma bağlıdır; 'oyuncak' kelimesi yetmez | contradicted | Basit İHA (oyuncak) niteliğindeki insansız hava araçları pilot lisansı, kayıt, tescil ve ithal uygunluk izni yükümlülüklerinden muaftır. |  |
| tr-10 | m1: uyum yazılım modülü mevcut ve entegre olmalı; değilse kayıt yapılamaz ve uçurulamaz | unverified | yolcu beraberinde veya bireysel yollarla yurt dışından getirilen insansız hava araçlarında uyum yazılım modülünün mevcudiyeti ve entegrasyonu aranır; bu şart sağlanmadıkça söz konusu araçlar kayıt işlemlerine konu edilem | judge said present; quote not found |
| j-01 | m2: Türkiye: P0/P1 azami 120 m; P2'de 120 m üzeri yalnız ilgili kurumlarla koordinasyonla | unverified | Basit İHA, P0 ve P1 pilot lisansı seviyelerinin azami uçuş zarfı 120 metre yüksekliği aşamaz.  P2 Lisansı ile Uçuş P2 lisansı kapsamındaki 120 metrenin üzerindeki operasyonlar yalnızca ilgili kurum ve kuruluşlarla koordi | judge said present; quote not found |
| k-04 | m1: P1: Türkiye'de ticari uçuş lisansı; VLOS, 120 m / 3.000 m, uygun donanımla gece; aracın sınıfından bağımsız | unverified | Türkiye: P1 İHA Pilot Lisansı (Ticari) ticari operasyon ve uçuşlar için düzenlenir. [2]  P1 Lisansı Türkiye'de P1 lisansı ticari operasyon ve uçuşlar için düzenlenir ve görsel görüş hattında (VLOS), azami 120 metre yükse | judge said present; quote not found |
| k-04 | m2: A2: AB'de C2 sınıfı dron ile ilgisiz kişilerden en az 30 m (düşük hız modunda 5 m); çevrim içi eğitim + sınav, kendi kendine pratik eğitim ve en az 30 soruluk ek sınav (%75) | unverified | A2 sertifikası AB'de kişilerin yakınında (30 metreye kadar veya düşük hız modunda 5 metreye kadar) uçuş yapabilmek için gereken özel bir yetkinliktir.  A2 Sertifikası Avrupa Birliği'nde A2 alt kategorisi, insanların yakı | judge said present; quote not found |
| tr-01 | m1: azami 120 m yükseklik | present | azami 120 metre yükseklik |  |
| tr-06 | m3: süre sonunda dönüştürülmemiş araç uçurulamaz | absent |  |  |
| en-02 | s1: registration is also required at 250 g or more or above 80 J | absent |  |  |
| en-09 | m1: when any Article 4 / Part A requirement is not met (specific category) | present | Where one of the requirements laid down in Article 4 or in Part A of the Annex for the 'open' category is not met, a UAS operator is required to obtain an operational authorisation |  |
| j-01 | m3: AB açık kategori: 120 m | absent |  |  |
