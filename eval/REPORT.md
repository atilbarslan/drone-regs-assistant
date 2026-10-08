# Değerlendirme raporu

Bu dosya `python -m eval.report` ile üretilir; elle düzenlenmez (değişiklik ve hipotez tablosu `eval/CHANGES.md`'den aynen alınır). Yöntem: `eval/run.py` ve `eval/score.py` başları.

Gemini çağrıları her koşunun satırında (son satır). Hakem: her soru için tek çağrı; "present"/"contradicted" kararları cevaptan birebir alıntı ister, alıntı bulunamazsa "doğrulanamadı" sayılır.

## Özet

| Ölçü | A |
|---|---|
| Soru (hata) | 36 (0) |
| Tespit doğru | 36/36 |
| Getirme: beklenen maddeden en az biri | 31/32 |
| Getirme: beklenen maddelerin hepsi | 22/32 |
| Getirme: beklenen madde (toplam) | 45/57 |
| Atıf: beklenen maddeden en az biri [n] ile | 30/32 |
| **must** kapsamı | 45/61 (yok 13, çelişki 0, doğrulanamadı 3) |
| should kapsamı | 10/26 (yok 16, çelişki 0, doğrulanamadı 0) |
| **Çelişki (contradicted)** | 0 |
| Doğrulanamayan hakem kararı | 3 |
| Reddetme: refused=true | 4/4 |
| Reddetme: boş + kaynakta yok dedi | 4/4 |
| Yanlış ret | 2/32 |
| depends_on: soru / madde / soruda zaten var | 8 / 8 / 0 |
| Üretim süresi EU: medyan / en çok (soru) | 5.7 / 6.8 sn (14) |
| Üretim süresi TR: medyan / en çok (soru) | 5.3 / 6.3 sn (16) |
| Üretim süresi compare: medyan / en çok (soru) | 5.8 / 7.1 sn (6) |
| Ortalama token: prompt / çıktı | 5235 / 322 |
| Gemini çağrısı: embedding (önbellek) / üretim / hakem / yeniden deneme | 36 (0) / 36 / 36 / 0 |

## Yapılandırma

| | A |
|---|---|
| generation_model | gemini-3.5-flash-lite |
| thinking_level | default (minimal) |
| judge_model | gemini-3.5-flash-lite |
| top_k | 8 |
| list_top_k | 14 |
| compare_per_side | 6 |
| core_sections |  |
| prompt_sha | 0b579e927c61 |
| git | 568f665 |
| note | baseline: settings as deployed after PR 7 |
| questions | eval/questions.yaml |
| sonuç dosyası | `eval/results/2026-10-08T0510-A.json` |
| durum | complete |

## Hata sınıfları — A

Sınıflar otomatik çıkarılır: tespit (mod kabul listesinde değil), getirme (eksik must var ve beklenen maddelerden biri getirilmemiş), üretim (eksik must var ve beklenen maddelerden en az biri getirilmiş; çelişki ayrı), atıf (beklenen madde getirildi ama hiçbiri [n] ile gösterilmedi), reddetme, depends_on (soruda zaten olan bilgiyi soruyor). Bir soru birden çok sınıfta olabilir.

| Hata sınıfı | Soru sayısı | Sorular |
|---|---|---|
| üretim | 10 | tr-01, tr-03, tr-07, tr-10, x-01, j-01, j-02, k-02, k-04, k-05 |
| getirme | 6 | tr-01, tr-03, tr-10, j-01, k-01, k-02 |
| reddetme | 2 | k-01, k-02 |
| atıf | 1 | k-02 |

## Soru bazında — A

must/should: ✓ var · ✗ yok · ‼ çelişki · ? doğrulanamadı. Sıra: beklenen maddenin modele verilen parçalar arasındaki yeri (1 = ilk).

| id | tespit (mod) | liste / parça | beklenen maddelerin sırası | atıf | must | should | ret | depends_on | üretim sn | hata sınıfı |
|---|---|---|---|---|---|---|---|---|---|---|
| tr-01 | ✓ TR→TR |  8 | Madde 15: 1, Madde 11: yok | ✓ | m1✓ m2✓ m3✗ | s1✗ |  | 0 | 2.0 | getirme, üretim |
| tr-02 | ✓ TR→TR | liste 14 | Madde 8: 2 | ✓ | m1✓ | — |  | 0 | 5.3 | — |
| tr-03 | ✓ null→TR |  8 | Madde 8: 5, Madde 4: 3, Madde 11: 1, Madde 15: 4, Madde 12: yok | ✓ | m1✗ m2✓ m3✗ | s1✗ |  | 0 | 5.3 | getirme, üretim |
| tr-04 | ✓ TR→TR |  8 | Madde 29: 1 | ✓ | m1✓ m2✓ | s1✓ |  | 0 | 5.2 | — |
| tr-05 | ✓ TR→TR |  8 | Geçici Madde 1: 1 | ✓ | m1✓ m2✓ | s1✓ |  | 0 | 5.3 | — |
| tr-06 | ✓ null→TR | liste 14 | Madde 27: 1, Geçici Madde 2: 6, Madde 25: 4 | ✓ | m1✓ m2✓ m3✓ | s1✓ |  | 1 | 6.3 | — |
| tr-07 | ✓ TR→TR |  8 | Madde 12: 1 | ✓ | m1✗ m2✓ m3✗ | — |  | 0 | 5.0 | üretim |
| tr-08 | ✓ TR→TR |  8 | Madde 15: 1 | ✓ | m1✓ | s1✗ |  | 0 | 5.4 | — |
| tr-09 | ✓ TR→TR |  8 | Madde 15: 1 | ✓ | m1✓ | s1✗ |  | 0 | 5.2 | — |
| tr-10 | ✓ TR→TR |  8 | Madde 24: 1, Madde 11: yok, Madde 15: yok, Madde 12: 3 | ✓ | m1✓ m2✗ | s1✓ |  | 1 | 6.0 | getirme, üretim |
| en-01 | ✓ EU→EU |  8 | Article 4 (2019/947): 1, UAS.OPEN.010: 2 | ✓ | m1✓ m2✓ | s1✓ s2✓ |  | 0 | 5.7 | — |
| en-02 | ✓ null→EU |  8 | Article 14 (2019/947): 1, Madde 11: yok | ✓ | m1✓ | s1✗ s2✗ |  | 1 | 5.3 | — |
| en-03 | ✓ EU→EU |  8 | UAS.OPEN.030: 2, AMC1 UAS.OPEN.030(1): 1, Part 3 (2019/945 Annex): yok | ✓ | m1✓ m2✓ | s1✗ s2✗ |  | 0 | 6.1 | — |
| en-04 | ✓ EU→EU |  8 | UAS.OPEN.040: 2 | ✓ | m1✓ | — |  | 0 | 5.1 | — |
| en-05 | ✓ EU→EU |  8 | UAS.OPEN.020: 1 | ✓ | m1✓ m2✓ | — |  | 0 | 5.7 | — |
| en-06 | ✓ EU→EU |  8 | UAS.OPEN.070: 1 | ✓ | m1✓ | — |  | 0 | 5.5 | — |
| en-07 | ✓ EU→EU | liste 14 | Part 1 (2019/945 Annex): 1 | ✓ | m1✓ m2✓ m3✓ | s1✓ s2✓ |  | 0 | 5.8 | — |
| en-08 | ✓ EU→EU |  8 | UAS.OPEN.060: 6 | ✓ | m1✓ | — |  | 0 | 5.2 | — |
| en-09 | ✓ EU→EU |  8 | Article 5 (2019/947): 6, Article 12 (2019/947): 1, UAS.SPEC.020: yok | ✓ | m1✓ m2✓ | s1✗ s2✗ |  | 0 | 5.8 | — |
| en-10 | ✓ null→EU |  8 | Article 5 (2019/947): yok, Article 11 (2019/947): 3, Madde 9: yok | ✓ | m1✓ | s1✓ s2✗ |  | 0 | 5.8 | — |
| x-01 | ✓ EU→EU |  8 | UAS.OPEN.020: 1 | ✓ | m1? m2✓ | — |  | 1 | 6.8 | üretim |
| x-02 | ✓ TR→TR |  8 | Madde 6: 2, Madde 15: 3 | ✓ | m1✓ | — |  | 0 | 5.1 | — |
| x-03 | ✓ compare→compare |  12 | Madde 17: 1, Article 9 (2019/947): 7 | ✓ | m1✓ m2✓ m3✓ | s1✓ |  | 1 | 7.1 | — |
| x-04 | ✓ TR→TR |  8 | Madde 23: 7 | ✓ | m1✓ | — |  | 0 | 4.8 | — |
| r-01 | ✓ null→TR |  8 | — |  | — | — | ✓ | 0 | 5.4 | — |
| r-02 | ✓ null→EU |  8 | — |  | — | — | ✓ | 0 | 5.2 | — |
| r-03 | ✓ null→TR | liste 14 | — |  | — | — | ✓ | 0 | 5.7 | — |
| r-04 | ✓ EU→EU |  8 | — |  | — | — | ✓ | 0 | 5.6 | — |
| j-01 | ✓ null→TR |  8 | Madde 15: 2, Article 4 (2019/947): yok | ✓ | m1✗ m2✓ m3✗ | s1✗ |  | 1 | 6.2 | getirme, üretim |
| j-02 | ✓ EU→EU |  8 | UAS.OPEN.020: 2, Part 1 (2019/945 Annex): 4 | ✓ | m1? m2✓ | — |  | 1 | 6.0 | üretim |
| j-03 | ✓ TR→TR |  8 | Madde 17: 2 | ✓ | m1✓ | — |  | 1 | 4.9 | — |
| k-01 | ✓ compare→compare |  12 | Article 41 (2019/945): yok | ✗ | m1✗ m2✗ m3✓ | s1✗ | yanlış ret | 0 | 5.1 | reddetme, getirme |
| k-02 | ✓ compare→compare |  12 | Madde 10: 4, Madde 15: yok | ✗ | m1✗ m2✗ | s1✗ | yanlış ret | 0 | 5.1 | reddetme, getirme, üretim, atıf |
| k-03 | ✓ compare→compare |  12 | Madde 15: 7 | ✓ | m1✓ | — |  | 0 | 5.2 | — |
| k-04 | ✓ compare→compare |  12 | Madde 15: 1, UAS.OPEN.030: 7 | ✓ | m1✓ m2? | s1✗ |  | 0 | 6.4 | üretim |
| k-05 | ✓ compare→compare |  12 | Madde 8: 1, Part 1 (2019/945 Annex): 7 | ✓ | m1✗ m2✓ m3✓ | s1✗ |  | 0 | 6.6 | üretim |

## Hakem kararlarını elle kontrol — A

Bütün çelişki ve doğrulanamayan kararlar, ayrıca 5 örnek var/yok kararı.

| id | fact | karar | alıntı (cevaptan) | not |
|---|---|---|---|---|
| x-01 | m1: 250 g altı / C0: ilgisiz kişilerin üzerinden uçulabilir ama kalabalıkların üzerinden asla | unverified | C0 sınıfı veya azami kalkış ağırlığı 250 gramdan küçük olan özel yapım insansız hava araçlarının ilgisiz kişilerin üzerinden uçmasına izin verilir, ancak mümkün olduğunca kaçınılmalı ve kaçınılmaz durumlarda aşırı dikkat | judge said present; quote not found |
| j-02 | m1: 250 g altı / C0 ile A1'de çevrim içi eğitim ve sınav şartı yok; zorunlu eğitim C1 için | unverified | Özel yapım, C0 sınıfı veya 1 Ocak 2024'ten önce piyasaya sürülmüş hafif insansız hava araçları için açık kategoride çevrimiçi eğitim zorunluluğu bulunmamaktadır; uzaktan pilotun üretici talimatlarına aşina olması yeterli | judge said present; quote not found |
| k-04 | m2: A2: AB'de C2 sınıfı dron ile ilgisiz kişilerden en az 30 m (düşük hız modunda 5 m); çevrim içi eğitim + sınav, kendi kendine pratik eğitim ve en az 30 soruluk ek sınav (%75) | unverified | A2 is an EU subcategory competency certificate for operations maintaining a safe horizontal distance from uninvolved persons... maintaining a safe horizontal distance of at least 30 metres or down to 5 metres with an act | judge said present; quote not found |
| tr-01 | m1: azami 120 m yükseklik | present | azami 120 metre yükseklik |  |
| tr-06 | m2: son tarih 31/07/2027 | present | Mevcut insansız hava araçlarının yeni kurallara ve dönüştürme gerekliliklerine uyumlu hâle getirilmesi 31/07/2027 tarihine kadar tamamlanmalıdır. |  |
| en-01 | s2: unmanned sailplanes under 10 kg exception | present | unmanned sailplanes with a maximum take-off mass, including payload, of less than 10 kg may be flown at a distance in excess of 120 metres from the closest point of the surface of the earth, provided that the unmanned sa |  |
| en-07 | s2: follow-me mode within 50 m | present | follow-me mode, the function must operate within a range not exceeding 50 m |  |
| j-01 | m1: cevap iki yetki alanına ayrılır | absent |  |  |
