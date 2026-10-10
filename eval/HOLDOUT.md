# Bekletilen test (hold-out)

5 soru (`eval/holdout.yaml`), ayar bittikten sonra yazıldı; son yapılandırmayla (F3) **bir kez** koşuldu. Sonuca göre hiçbir ayar yapılmadı. Küçük örneklem: tek bir fact %9 eder. Tablolar `eval/report.py`'nin fonksiyonlarıyla üretildi (`summary_table`, `detail_table`, `judge_checks`).

## Özet

| Ölçü | H |
|---|---|
| Soru (hata) | 5 (0) |
| Anahtarı değişip yeniden puanlanan | - |
| Tespit doğru | 4/5 |
| Getirme: beklenen maddeden en az biri | 4/5 |
| Getirme: beklenen maddelerin hepsi | 3/5 |
| Getirme: beklenen madde (toplam) | 6/10 |
| Atıf: beklenen maddeden en az biri [n] ile | 4/5 |
| **must** kapsamı | 6/11 (yok 5, çelişki 0, doğrulanamadı 0) |
| should kapsamı | 2/13 (yok 11, çelişki 0, doğrulanamadı 0) |
| **Çelişki (contradicted)** | 0 |
| Doğrulanamayan hakem kararı | 0 |
| Reddetme: refused=true | 0/0 |
| Reddetme: boş + kaynakta yok dedi | 0/0 |
| Yanlış ret | 1/5 |
| depends_on: soru / madde / soruda zaten var | 3 / 3 / 0 |
| Üretim süresi EU: medyan / en çok (soru) | 5.4 / 5.6 sn (2) |
| Üretim süresi TR: medyan / en çok (soru) | 4.3 / 5.2 sn (2) |
| Üretim süresi compare: medyan / en çok (soru) | 5.5 / 5.5 sn (1) |
| Ortalama token: prompt / çıktı | 5473 / 415 |
| Gemini çağrısı: embedding (önbellek) / üretim / hakem / yeniden deneme | 5 (0) / 5 / 5 / 0 |

## Soru bazında

must/should: ✓ var · ✗ yok · ‼ çelişki · ? doğrulanamadı.

| id | tespit (mod) | liste / parça | beklenen maddelerin sırası | atıf | must | should | ret | depends_on | üretim sn | hata sınıfı |
|---|---|---|---|---|---|---|---|---|---|---|
| h-01 | ✓ null→TR | liste 14 | Madde 15: 1, Madde 8: 4 | ✓ | m1✓ m2✓ | s1✓ s2✗ |  | 1 | 3.4 | - |
| h-02 | ✓ null→TR |  8 | Madde 12: 1 | ✓ | m1✓ m2✗ | s1✗ s2✗ s3✗ |  | 1 | 5.2 | üretim |
| h-03 | ✗ null→EU |  8 | Madde 15: yok, Madde 12: yok | ✗ | m1✗ m2✗ | s1✗ s2✗ s3✗ | yanlış ret | 0 | 5.2 | tespit, reddetme, getirme |
| h-04 | ✓ null→EU |  8 | Article 14 (2019/947): 6, AMC1 UAS.OPEN.020(5)(c) and (d), UAS.OPEN.030(3) and UAS.OPEN.040(4)(c),(d) and (e): 2 | ✓ | m1✗ m2✗ m3✓ | s1✓ s2✗ |  | 1 | 5.6 | üretim |
| h-05 | ✓ compare→compare |  12 | Article 14 (2019/947): 8, UAS.SPEC.020: yok, UAS.SPEC.030: yok | ✓ | m1✓ m2✓ | s1✗ s2✗ s3✗ |  | 0 | 5.5 | - |

## Hakem kararları (hepsi)

| id | fact | karar | alıntı (cevaptan) | not |
|---|---|---|---|---|
| h-01 | m1: lisans dronun modeline, sınıfına ya da ağırlığına göre değil operasyonun türüne göre belirlenir (M.15(2); M.8(4)) | present | Cevap şunlara bağlı: - Operasyonun amacı nedir? (Amatör (Ticari değil) / Ticari amaçlı / Yüksek riskli / BVLOS) |  |
| h-01 | m2: ticari olmayan uçuş için P0, ticari uçuş için P1 (M.15(2)(a)-(b)) | present | - Amatör (Ticari olmayan) operasyonlar - P0 Lisansı: Ticari amaç taşımayan amatör operasyonlar için asgari P0 İHA pilot lisansı alınması gerekir. [3][5] - Ticari operasyonlar - P1 Lisansı: Ticari operasyonlar ve uçuşlar  |  |
| h-01 | s1: görüş hattı dışı ve yüksek riskli operasyonlar için P2 (M.15(2)(c)) | present | - Yüksek riskli veya görüş hattı dışı (BVLOS) operasyonlar - P2 Lisansı: Görüş hattı dışı (BVLOS) operasyonlar ile kalabalık üstü uçuş gibi yüksek riskli operasyonlar P2 lisansı kapsamında icra edilir. [3][5] |  |
| h-01 | s2: eğitim ve sınavdan sonra diploma lisansı KDM-ORG'dan; uçmak için ayrıca KDM-ERP'den operasyonel lisans gerekir (M.15(4)) | absent |  |  |
| h-02 | m1: yeşil bölgede belirlenen irtifa ve şartlar altında operasyonel izin gerekmez (M.12(2)(a)) | present | Yeşil bölgelerde, belirlenen irtifa ve şartlar altında operasyonel izne gerek duyulmadan uçuş yapılabilir. |  |
| h-02 | m2: P0 ve P1 yeşil bölgede sistem üzerinden ayrıca izin almadan uçar (M.12(7)(b)) | absent |  |  |
| h-02 | s1: P2'de yükseklik ya da uzun mesafe gerektirirse koordinasyon, Genel Müdürlük izni ve NOTAM aranır (M.12(7)(c)) | absent |  |  |
| h-02 | s2: lisansın uçuş zarfı bölgenin tavan irtifasını aşamaz (M.12(6)) | absent |  |  |
| h-02 | s3: yeşil bölgeler İHATTYS haritasında yayımlanır (M.12(1)) | absent |  |  |
| h-03 | m1: treats P1 as the Turkish commercial UAS pilot licence and answers under SHT-İHA (M.15(2)(b)) | absent |  |  |
| h-03 | m2: VLOS only, maximum 120 m height and 3,000 m visual or horizontal distance (M.15(2)(b)) | absent |  |  |
| h-03 | s1: night operations allowed with suitable equipment; an observer may be required (M.15(2)(b)) | absent |  |  |
| h-03 | s2: flying needs the operational licence (KDM-ERP) after the diploma licence (M.15(4)) | absent |  |  |
| h-03 | s3: green zone without a permit; outside it with a permit (M.12(7)(b)) | absent |  |  |
| h-04 | m1: in the open category the operator registers, not each drone (only UA whose design is subject to certification are registered individually) (Art. 14(5), 14(7)) | absent |  |  |
| h-04 | m2: an operator not yet registered must register if the modified UA now has an MTOM of 250 g or more, or a sensor able to capture personal data (Art. 14(5)(a)) | absent |  |  |
| h-04 | m3: a modification that changes the weight outside the manufacturer's specifications invalidates the class (C0-C4) conformity; the class label must be removed and the UA may then only be flown in the specific category (AMC1/GM1 UAS.OPEN.020(5)…, p. 429) | present | Modifications to a UAS with a class identification label that affect weight or performance outside the manufacturer's specifications or instructions are considered modifications that breach compliance. For classes C0 thr |  |
| h-04 | s1: registration information must be kept accurate (Art. 14(6)) | present | must update registration data when it changes |  |
| h-04 | s2: payload or original replacement parts allowed by the manufacturer are not a modification (AMC1, p. 429) | absent |  |  |
| h-05 | m1: Türkiye: SHT-İHA'da sigorta zorunluluğuna ilişkin hüküm yok; cevap bunu kaynakta yok olarak söyler, uydurmaz | present | Türkiye'deki kaynaklarda sigorta zorunluluğu konusunda herhangi bir düzenleme bulunmamaktadır. |  |
| h-05 | m2: AB: 2019/947 genel bir sigorta zorunluluğu koymaz; sigorta Birlik ya da ulusal hukuk gerektiriyorsa aranır (kayıtta poliçe numarası yalnız bu durumda: Art. 14(2)(d)) | present | AB: Kayıt sistemleri, birlik veya ulusal hukuk gerektiriyorsa sigorta poliçesi numarası için veri alanları sağlar. [11] |  |
| h-05 | s1: specific kategoride beyan ve izinde uygun sigortanın olacağı teyit edilir, yine 'gerekiyorsa' (UAS.SPEC.020(2)(d), UAS.SPEC.030(3)(f)) | absent |  |  |
| h-05 | s2: üye devletlerin ulusal sigorta kuralları farklı olabilir (AMC1 UAS.OPEN.020(4)(b), p. 427) | absent |  |  |
| h-05 | s3: üye devlet kayıtta poliçenin bitiş tarihini isteyebilir (GM1 Article 14(1), p. 401) | absent |  |  |
