# relaxed-01 — FAIL

> **Built under the first rule set** (single player, clear the board, a hand of drawn letters),
> before the rules were corrected to the real game's duel against an opponent bot. The team
> workflow and the gate it shows still apply; the win rates are not comparable with later runs.

The first end-to-end run of the level team (`/build-campaign` in Claude Code), on
2026-10-02. Brief: a 10-level campaign for relaxed adult players. Below is the
orchestrator's final report, as it was given (in Turkish, the language of the session).

---

relaxed-01: FAIL, şu an yayınlanmaya hazır değil

Sonuç: Release-reviewer kampanyayı reddetti. Bunu, 2 hak içinden 1. kapı denemesinde verdi. `release_check` aracı 8/10 ile, yani tam %80 eşiğinde geçmişti. Ama zorluğu hedefin altında kalan iki seviye, en zor iki seviye: 8 ve 10. Designer düzeltmeyi denedi; seviye 10 daha da zorlaştı. Durum değişmediği için 2. kapı denemesini kullanmadım.
Yeni denemelerde bandında olan: 8/10

* Seviye 8 (`t0.295_s2170009`): Hedef 0.52–0.72, ölçülen 0.515. Reviewer 300 denemede 0.52 ölçtü; yani tam sınırda.
* Seviye 10 (`t0.522_s3190009`): Hedef 0.32–0.52, ölçülen 0.285. Rahat oynayan oyuncuların yaklaşık 7'de 5'i finali kaybeder.

Hedef eğri ve gerekçesi (designer)
`[0.92, 0.85, 0.78, 0.70, 0.55, 0.80, 0.70, 0.62, 0.50, 0.42]`

* İlk seviyeler kolay, ki oyuncu rahat başlasın.
* Seviye 5'te hafif bir zorluk sıçraması var, seviye 6 nefes molası.
* Sonrasında ikinci bir yükseliş geliyor.
* Final zor ama designer'ın kendi koyduğu yaklaşık 0.35 tabanının üstünde olması gerekiyordu. Şu anki 0.285 bu tabanın altında.

Engellenen kelimeler (4)

* FATTY: Kilo üzerinden aşağılayıcı.
* MODI: Latince çoğul ve özel isim; bilinmez.
* PARA: Yabancı kelime ya da kısaltma gibi duruyor.
* THERES: Kesme işareti düşmüş bir kısaltma ("there's"), gerçek bir kelime değil.

Toplam 73 kelime onaylandı. İnceleme kuyruğu boş.

Analist notları

* Seviye 8: Sorun kelime bilgisi değil, ünsüz tıkanması. Tile Stack'te (SCYNUJTC) J ve C var, el sesli harfsiz ünsüzlerle doluyor. Öneri: J'yi bir sesli harfle değiştirmek.
* Seviye 10: Analiz bir önceki sürüm (`s2190006`) üzerineydi. O sürümde stack ünsüz ağırlıklıydı ve el boyutu 5'ti, kampanyadaki en küçük. Casual bot 6 cevap kelimesinden 3'ünü bilmiyordu. Mevcut sürüm ölçüldü ama ayrıca analiz edilmedi.
* Seviye 9'daki adillik şüphesi temizlendi: Expert bot 30 denemede 25 kazandı (0.833).
* Not: Designer, seviyeleri yeni deneme sonuçlarına bakarak yeniden ürettiği için bu sonuçlar biraz iyimser çıkmış. Reviewer'ın bağımsız ölçümleri 0.01–0.05 daha düşük. Seviye 7 de sınıra yakın (0.627).

Seçenekler: (1) seviye 8 ve 10'u sınırı aşarak tekrar üretmek, (2) hedef eğriyi yumuşatmak,
(3) olduğu gibi bırakmak.

I chose (2), softening the curve, which became relaxed-02.
