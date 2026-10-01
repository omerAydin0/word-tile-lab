# relaxed-03 — PASS (fourth gate attempt)

The first campaign built under the corrected rules: a duel against an opponent bot on a
shared board, player first, length-based score, a face-down deck. Same brief as before:
10 levels for relaxed adult players. Campaign, levels and a render of the hardest level
are in `relaxed-03/`.

**The levels never changed after the first gate run.** All three FAILs were about the
reports, not the levels:

1. Gate 1 and 2 — the analyst quoted figures from `explain_level`, a tool the reviewer
   didn't have, and the reviewer fails any number it can't reproduce. A contradiction in
   my agent setup, not an agent mistake. Fixed afterwards: the reviewer now has
   `explain_level` (read-only and deterministic), and checks that analysed levels are
   the ones the campaign still holds.
2. Gate 3 — the orchestrator moved the unverifiable section out of the gated report but
   left two half-sentences pointing at it. The reviewer caught both.
3. Gate 4 — PASS. Gates 3 and 4 ran past the two-run limit with my approval.

| level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| target band | 0.82–1.00 | 0.75–0.95 | 0.68–0.88 | 0.60–0.80 | 0.48–0.68 | 0.70–0.90 | 0.60–0.80 | 0.52–0.72 | 0.44–0.64 | 0.35–0.55 |
| casual win rate vs bot, fresh trials | 0.835 | 0.845 | 0.785 | 0.695 | 0.55 | 0.775 | 0.64 | 0.695 | 0.52 | 0.375 |

Curve: `[0.92, 0.85, 0.78, 0.70, 0.58, 0.80, 0.70, 0.62, 0.54, 0.45]` — a gentle start, a
mild bump at 5, a breather at 6, a second climb, and a finale that is clearly the hardest.

**Blocked answer words (levels regenerated):** CUM (sexual slang), DOPE (drug slang and an
insult), MARTIN (proper name), AMAZON (brand). 71 words approved. Flagged by the
orchestrator for a second look: FAT (FATTY was blocked in relaxed-01), STUPID, SEN, and
BUD, BEER, MAC, SRI, JIN.

**Analyst, level 10:** fresh 0.375; the reviewer's own 300 trials (seed 7) 0.443; expert
30/30, so fair; losses are close (about −1 point). Untested suggestion: a slightly weaker
opponent or a vowel in the deck (`TLAHHB` has one).

**Process limits this run exposed:**
- The reviewer judged the corrected sentence as the orchestrator relayed it, not from the
  report itself. Whoever passes the report controls what the gate sees; reports should be
  written to files the reviewer reads directly.
- Level 7's deck has no vowel at all (`FZHTSDR`) on an easy level - chance (about 3%), but
  the generator should guarantee one.

---

## The orchestrator's final report (as given, in Turkish)

relaxed-03: PASS, yayına hazır

Kampanya 4. kapı denemesinde geçti; 3. ve 4. denemeler sizin onayınızla yapıldı. Yeni
denemelerde 10/10 seviye bandında. release_check çıktısı: pass: true, in_band 10/10, sorun
listesi boş. Tüm cevap kelimeleri onaylı.

Seviyeler ilk kapı denemesinden bu yana hiç değişmedi. Önceki iki FAIL'in nedeni hep
raporlardı: önce designer'ın eski sayıları, sonra reviewer'ın doğrulayamadığı tanı rakamları.

Bir kısıt: reviewer 4. denemede düzeltilen cümleyi tam rapor üzerinden değil, benim ona
aktardığım haliyle değerlendirdi.

Analist notları (kapıdan geçen A bölümü), seviye 10: yeni denemelerde 0.375; seed 7 ile 300
denemede 0.443, reviewer da aynı sonucu buldu. Expert bot 30/30, seviye adil. Kayıplar
ortalama yaklaşık 1 puanla. Seviye 1: 0.835, taban 0.82, takılınan harfler V ve Y. Seviye 7
ve 8: sıra seed'e göre değişiyor, aralıklar örtüşüyor, büyük olasılıkla gürültü.

Ek (kapıdan geçmedi, sadece bilgi; explain_level, 100 deneme): seviye 10 — sıradan oyuncu
0.40, bot gücü 0.343, dağarcığı 3019 kelime, deste TLAHHB; örnek kayıp 14–23: bot BARREL ve
EXAM'i aldı, oyuncu desteyi bitirdi ve E ile takıldı. Seviye 7 — 0.67, bot gücü 0.129,
deste FZHTSDR. Seviye 8 — 0.57, bot 0.197, deste RBVUPYA. Seviye 1 — 0.84, bot 0.0, deste
TGDTONTF, örnek kayıp 8–10, Y ile takıldı.
