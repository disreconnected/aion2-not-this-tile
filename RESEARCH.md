# Aion 2 — Shugo Festival: "Not This Tile?" (이 타일 아닌가요?)

Research notes gathered 2026-11-10. The section "From the recording" is first-hand, and it wins over
the web guides further down where they disagree.

## From the recording (2026-11-10 00-02-13, 1920×1080 60 fps, 4:30)

**Round flow, the same every round:**
1. "Round N" banner. The grid is **all blue** and every tile looks identical.
2. A 3-2-1 countdown (red circle) while the grid is still all blue.
3. **Reveal:** most tiles turn **red** (traps). The few **safe tiles stay blue**. This lasts about **2 s** in
   rounds 1–3 and about **1.5 s** by round 8 (Shugo: "We'll speed up from here on").
4. **"START":** the grid goes back to all blue, so you can't tell safe from trap any more.
   - Round 1: "3s left to answer". Just walk onto a safe tile.
   - Round 2 onward: balloons spawn (green 20 / yellow 30). "You have **8 seconds** to get the balloons and
     return to the correct tile." The last round gets extra time.
5. **"Here's the answer":** the same red/blue pattern is shown again, then only the safe tiles stay lit.
   Score is applied.

**In-game rules panel:** Blue tile: Correct, earn 100 points. Festival balloon: Green 20 / Yellow 30.
Red tile: Incorrect, lose points.

**Grid:** grows every round, and it isn't always square. Sizes were counted from both recordings
(00-02-13 and 02-02-50), which agree; no web guide lists them:

| Round | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Columns × rows | 6×6 | 8×8 | 10×8 | 10×8 | 10×10 | 12×10 | 12×10 | 14×10 |
| Safe tiles | 6–7 | 8 | 8 | 7 | 7 | 5–6 | 6 | 4 |

The sizes were the same in all ten recorded games (2026-11-10 00-02-13, 15-00-55, 23-02-38, 2026-11-11
00-03-00, 01-01-45, 12-02-59, 23-02-50 and 2026-11-12 00-02-52, 12-03-00, 23-02-58). An earlier note here said rounds 7 and 8 of 15-00-55 were both 14 columns; that
was a miscount (round 7 was 12).
**Layouts repeat between games:** each round picks from a small set of 2–3 layouts. The 23 seen so far are in
`layouts.json`. Every reveal in the ten recordings fits exactly one of them. Round 7 of 15-00-55 showed only 4
of its tiles (two were behind the skill bar); 2026-11-12 12-03-00 showed all six. Likewise, the round 5 layout B2 C7 E4 H3 H8 I7 was
missing C10 until 23-02-58 showed row 10. Three reads were taken with the camera
turned a quarter turn (23-02-38 round 2; 01-01-45 rounds 2 and 3) and still fit, turned. Tiles that players stood on were found from
the best blue coverage of each cell across all frames of the reveal and its answer.

**Camera:** the player is free to rotate and zoom, including *during* the reveal (seen in round 8). So the
safe tiles don't sit at a fixed screen position from one moment to the next.

**What the helper must catch:** the ~1.5–2 s window where a large red area appears. Grab the frame with
the most red, then keep showing it after the grid turns blue again.

## What the game is

- Shugo Festival / Shugo Festa minigame. KR name: **이 타일 아닌가요?**
- 1–6 players. Play time is **3:15** (EN guides) or **3:20** (Inven), after a 3-minute ready phase.
- **8 rounds.** Your rank comes from the total score across all rounds.
- Each round starts by showing the correct (safe) tiles in **blue** for a few seconds. They then vanish
  and the floor looks uniform again. You have to remember where they were.
- Later rounds show more tiles (redwendy).
- **Festival balloons** spawn after the blue tiles disappear, from round 2 onward. You grab one and get back
  onto a safe tile before the round ends.

## Scoring (per guides)

| Event | Points |
|---|---|
| End the round on a correct (blue) tile | +100 |
| Festival balloon | +50 (a later patch changed balloon types and values) |
| End the round on a wrong (red) tile | −50 |

You keep a round's points only if you end the round on a correct tile.

## Patch notes (Inven)

- The floor tiles were made **more visible ("clearer")**. This should make reading tiles from screen capture easier.
- Balloon types and values changed. The recording confirms green balloons are worth 20 and yellow 30.

## Community tips

- Memorize the tile you'll finally stand on first. Use the other blue tiles as route waypoints (Inven #1241).
- The balloon usually spawns **on or next to a blue tile** (author claims 90%+). Dodge/dash to it, then return.
- If the balloon is far away, staying put on a blue tile is often worth more (redwendy).


## Sources

Guides:
- [AllThings.How — every Shugo Festival minigame](https://allthings.how/aion-2-every-shugo-festival-minigame-and-its-rewards/)
- [Fextralife wiki — Shugo Festival](https://aion2.wiki.fextralife.com/Shugo_Festival)
- [Inven — 이타일아닌가요? 1등하는법 (balloon-near-blue-tile tip)](https://www.inven.co.kr/board/aion2/6444/1241)
- [Inven — 슈고 페스타 시간/보상/정보 총정리](https://www.inven.co.kr/board/aion2/6493/12)
- [Inven — 슈고 페스타 변경점 (clearer floor)](https://www.inven.co.kr/board/aion2/6493/91)
- [redwendy — 슈고페스타 미니게임 공략](https://redwendy.com/archives/2635) (has a screenshot)
- [Game Rant — all nine minigames](https://gamerant.com/aion-2-shugo-festival-guide-join-all-minigames/)
- [metabot.gg — Shugo Festival](https://metabot.gg/en/aion-2/events/shugo-festival)

Videos:
- [[아이온2] 이 타일 아닌가요? (슈고 페스타 미니 게임)](https://www.youtube.com/watch?v=upxuuzwbPJg)
- [AION2 - 슈고페스타 미니게임 - 이 타일이 아닌가요?](https://www.youtube.com/watch?v=LuAz5nCHJY8)
- [Video linked in the Inven 1st-place guide](https://www.youtube.com/watch?v=qbWt1sLN3GY)
- [슈고페스타 미니게임 9종 핵심 정리](https://www.youtube.com/watch?v=cprde8dDE5g)
- [AION 2 Shugo Festival Guide (EN)](https://www.youtube.com/watch?v=AYFt7XcbQTs)
