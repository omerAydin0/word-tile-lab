# relaxed-02 — PASS (second gate attempt)

> **Built under the first rule set** (single player, clear the board, a hand of drawn letters),
> before the rules were corrected to the real game's duel against an opponent bot. The team
> workflow and the gate it shows still apply; the win rates are not comparable with later runs.

Same brief as relaxed-01, with the curve softened at two points (level 8: 0.62 → 0.66,
level 10: 0.42 → 0.50), my call after relaxed-01. Two rounds: the first gate failed on level 5,
I approved one regeneration past the designer's limit, and the second gate passed.
The orchestrator's reports are below, as given (in Turkish, the session's language).
The campaign and its levels are in `relaxed-02/`.

---

## Gate attempt 1 — FAIL

relaxed-02: FAIL (2 hakkın 1. kapı denemesi), tek bir sorun kaldı

Durum: Yeni denemelerde 9/10 seviye bandında. release_check 9/10 ile geçti. Reviewer yine de
FAIL verdi, çünkü seviye 5 fazla kolay. Hedef bandı 0.45–0.65. Yeni denemelerde 0.785 ölçüldü.
Reviewer kendi 300 denemesinde 0.750 ölçtü (güven aralığı 0.698–0.796). Sonuç: ortadaki zorluk
çukuru oluşmuyor. Seviye 4, 5 ve 6 sırasıyla 0.675, 0.785 ve 0.75 ölçülüyor, yani düz bir plato.

Neden kendim düzeltmedim: Seviye 5 zaten 2 kez yeniden üretildi. İkisini de engelli kelimeler
yüzünden ben yaptım: önce TRIPOLI/KRIS/CIS, sonra SEPT. Designer'ın tanımında "aynı seviyeyi
ikiden fazla yeniden üretme" kuralı var. Onayınız olmadan aşmayacağım.

| Kelime | Neden engellendi |
|---|---|
| FUCKED | küfür |
| CIS | tek başına kelime değil |
| KRIS | bilinmez |
| TRIPOLI | özel isim |
| SEPT | kısaltma gibi okunuyor |

My reply: "Evet, seviye 5 için sınırı bir kez aşmaya onay veriyorum." (Yes, I approve going past
the limit once for level 5.)

## Gate attempt 2 — PASS

relaxed-02: PASS, ama sınırda

Sonuç: Kampanya 2. kapı denemesinde geçti; yeni denemelerde 10/10 seviye bandında.
release_check çıktısı: `{"pass":true,"in_band":"10/10","problems":[]}`. Tüm cevap kelimeleri
onaylı. Reviewer'ın kendi ölçümleri raporla 0.08 içinde tutarlı çıktı.

Ama iki seviye bandın tam kenarında:

| Seviye | Bant | Rapordaki ölçüm | Reviewer'ın 300 denemesi |
|---|---|---|---|
| 3 | 0.68–0.88 | 0.88 | seed 7: 0.857, seed 11: 0.903 (bandın üstünde) |
| 5 (yeni) | 0.45–0.65 | 0.53 | 0.450 (tam alt sınırda) |

Hedef eğri: `[0.92, 0.85, 0.78, 0.70, 0.55, 0.80, 0.70, 0.66, 0.50, 0.50]`.
Ölçülen eğri: 1.0, 0.785, 0.88, 0.675, 0.53, 0.75, 0.68, 0.60, 0.455, 0.56.

Bu kampanyada toplam 48 kelime onaylandı. GUN, SLAP, THRUST ve DAM sınırda kaldı; gündelik
anlamları masum olduğu için onaylandı.

Analist ve reviewer notları:
- En zor seviye 9 (0.455): zorluğunu kelime bilgisi değil, nadir harf tuzağı (J, K, Q, B)
  belirliyor. Expert bot 30 denemenin 30'unu kazandı, yani seviye adil.
- Final (seviye 10, 0.56) seviye 9'dan daha kolay; ikisinin hedefi de 0.50 ve ikisi de bandında.
- Yeni seviye 5 10 taşlık, 3 kelimelik küçük bir tahta. Tahta boyutları her seviyede büyümüyor
  (seviye 4'te 24 taş varken seviye 5'te 10).
- Seviye 8 alt sınıra yakın (0.60, bant tabanı 0.56).

Süreç notu: Seviye 5'in 3. yeniden üretimini, sizin "evet"inizle kendim yaptım. **Designer onayın
benden aktarılmış olmasını yeterli bulmadı ve yapmadı.**

Örnek render — en zor seviye (seviye 9): `out/render/t0.338_s180004.html`
