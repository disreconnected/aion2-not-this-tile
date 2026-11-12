# Not This Tile? helper for Aion 2

A memory aid for "Not This Tile?", a Shugo Festival minigame in Aion 2.

Each round, the trap tiles flash red for a second or two and the safe tiles stay blue. Then the whole floor
turns blue again, and you have to remember where the safe tiles were. This helper takes a picture of that
flash and keeps it on screen until the next round. It also names each safe tile like a spreadsheet cell
(`C4`, `F2`...), so you can find it on the floor quickly.

It only reads what's on your screen, the same way recording software does. More on that under
[Safety](#safety).

## Setup

You need Windows and Python 3. Install the three libraries once:

```bash
pip install numpy opencv-python mss
```

Then start the helper from this folder:

```bash
python notthistile_helper.py
```

Or double-click `start_helper.bat`. If the helper is already running, it closes that copy first, so you
can also use it to restart.

Run Aion 2 in borderless windowed mode. Windows can't draw on top of exclusive fullscreen.

## The control window

| Setting | What it does |
|---|---|
| Helper on | Turns the helper on or off. When it's off, the pictures hide and screen capture stops. |
| Overlay on game screen | A small picture window that stays on top of the game. Drag and resize it out of the way. |
| Window for second monitor | A normal picture window. The first time, it opens on your other monitor. |
| Game is on | Which monitor the game is on. The default is your main one. |

Closing a picture window just turns that switch off. Closing the control window quits the helper. The
helper saves your choices and window positions in `settings.json`.

If screen capture stops, for example while the game is starting, the status line says "Screen capture
stopped!". The helper keeps trying on its own.

## Reading the picture

Tiles are named as they appear in the picture. If you turn the camera, the names turn with it.

- Columns are letters, A, B, C..., from left to right along the far edge.
- Rows are numbers, 1, 2, 3..., starting from the far edge and coming towards you.
- Every safe (blue) tile gets its name, such as `C4`.

Rows count from the far edge because the near rows are often hidden behind the skill bar or below the
screen. Hidden rows get no names.

The helper only names tiles when it's sure. Otherwise you'll see one of these notes:

| Note | What happened | What to do |
|---|---|---|
| Grid cut off - zoom out | The far edge, or one of the far corners, was off-screen. | Zoom out. The near edge can go off-screen. |
| Grid edge hidden - move camera or UI | Tiles carry on under a UI panel, so the helper can't tell where the grid ends. | Move the panel or the camera. |
| Couldn't read the grid | Something covered a corner of the grid, or the grid wasn't a known size. | Keep other overlays (DPS meter, key display) away from the grid. |

A safe tile with a player standing on it may get no name.

Understand that in the later rounds, the grid won't fully fit on the screen so it will throw the "Grid cut off" error; this is not a bug, this is a current limitation.

## Known layouts

Each round picks its safe tiles from a few fixed layouts. The helper knows 23 of them, listed in
`layouts.json`. When the tiles it read fit exactly one of them, it:

- names the safe tiles it couldn't see, in yellow (under a player, behind the skill bar), and
- lists the whole layout above the picture, for example `Known layout: B1 C4 F4 G8 I8 K9`. That includes
  tiles below the bottom of your screen.

It needs at least two safe tiles first. It also has to be sure: every tile it read must be in the layout,
none of the layout's tiles may have read as red, and no other layout may fit. This works with the camera
turned too.

To add a new layout, add a line to `layouts.json` with the round, the grid size and the safe
tiles. Name the tiles with the camera facing the usual way. `helper.log` lists the tiles read for each round,
and `snapshots/` has the pictures to check them against.

## Tips

- Zoom out before the late rounds. Round 8 is 14 columns by 10 rows, and the far edge and both far corners
  must be on screen during the flash. The near edge can go off-screen.
- Hide the game's HUD during the minigame, or keep the grid above the skill bar.
- Keep other overlays away from the grid. If one covers a corner, that round gets no names.
- Try not to turn the camera between the flash and moving. The picture shows your camera angle at the
  flash, so it's easiest to match while the view is the same.
- The picture appears as soon as the flash starts. The names follow a moment later.
- The picture updates again at "Here's the answer", because the game shows the same tiles again.
- Something big and red outside the minigame, like lava or a red skill effect, can trigger a picture. It
  gets no names, and the next real round replaces it.

## Screen resolution

The helper has been used in real games at 1080p and 1440p. For the table, four 1440p recordings were scaled
to each size and replayed: 64 reveals, counting each round's flash and its answer. 4K was scaled up, which
adds no detail, so that row mainly shows nothing breaks at a larger size.

| Resolution | Frames read | Known layout matched | Reveals with a known layout |
|---|---|---|---|
| 4K (2160p) | 678 | 666 | 57 of 64 |
| 1440p | 684 | 672 | 57 of 64 |
| 1080p | 661 | 654 | 57 of 64 |
| 900p | 660 | 656 | 56 of 64 |
| 720p | 656 | 651 | 56 of 64 |

No frame matched the wrong layout at any size. A game running at 720p looks rougher than a scaled
recording, and its UI covers more of the screen, so hiding the HUD matters more there.

## Troubleshooting

The helper writes to `helper.log` next to the script: errors, and how it read each round. The log is capped
at 1 MB, and the older part moves to `helper.log.1`. It also saves the newest picture of each round in
`snapshots/`, keeps the last 40, and clears them each time it starts.

You can also replay a recording instead of watching the screen:

```bash
python notthistile_helper.py --video "path\to\recording.mkv" --start 56
```

`--start` is the number of seconds into the video to begin.

## Safety

The helper only reads screen pixels. It doesn't read game memory, touch the game process or send any input.
Still, any third-party tool used alongside an online game carries some risk under the game's terms of
service. Use it at your own discretion.

[RESEARCH.md](RESEARCH.md) has the round timings, grid sizes and the recording analysis the helper is
built on.
