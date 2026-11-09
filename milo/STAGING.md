# Staging a Milo episode (read this instead of the engine)

An episode = its lines in `episodes/season1.py` (already written and voiced) + one staging file
`episodes/epNN.py`. You only write the staging file. `episodes/ep01.py` is the worked example.
The direction language is documented at the top of `engine/dsl.py`.

## Commands (from `milo/`)

```
python run.py epNN plan      # checks shot lengths (0.6-2.5 s); exit 2 lists the bad shots
python run.py epNN stills    # 50% still per shot -> work/epNN/stills/_sheet.png (view it)
```
Word timings: `work/epNN/words.json` (`text`, `start`, `line` 0-based). Cut words must be words of that line.
Do not run `voice`, `frames`, `check` or `post`; the render queue does those.

## Beats -> what each line needs (the spec's structure)

| Beat | Shots | Must show |
|---|---|---|
| RULE | `wide close@...` | a wide of someone ALREADY paying for the rule, then a close |
| CAUSE / VICTIM | close each | the cause, then the victim; victim's transformation lands on its sound word |
| EX (x3) | 1 shot each | how the town lives with the rule (props + signs are cheap gags) |
| ME | `close` on milo | auto: Milo snaps into his peace-sign + wink on the key word |
| INC (x2) | 3 fast shots total | Milo breaks/tests the rule |
| POP | 2 shots | consequence on its word: `form` (puff + pop are automatic) |
| ESC (x3) | 1 shot each, `med:milo` | each step bigger than the last |
| REVEAL | `slide med@...` | the crowd set; the slide shot is the film's one slow slide |
| QUIET | `close` | music cuts automatically; the key noun's sound plays |
| TWIST | `med close@...` | newcomer arrives with `show` (puff) on Poof |
| PAYOFF | 1-2 shots | the transformation back/new on its word |
| CALLBACK | `close:X wide@Word close:Y@$+0.5` | `Word> all snapto Y` (whole cast snaps toward it) and a final close that holds |

## Sets and spots (`set.spot`, heading 0 faces the default camera)

- home: couch couch2 center table1 table2 door
- street: walk0..walk4 busstop door1 door2 roof1 (roof1 is on a roof, z 10.5)
- classroom: desk1..desk6 front teacher door
- hallway: spot0..spot4 office
- cafeteria: spot0..spot4 counter
- gym: floor0..floor4 door (crowd on bleachers)
- museum: floor0..floor2 (crowd on pedestals)
- farm: field0..field2
- sky: roof0..roof2 (on a rooftop above the clouds, z 5.2)
Crowd capacity: street 40, classroom 27, hallway 34, cafeteria 21, gym 48, museum 50, farm 68, sky 22.

## Building blocks

- Cast keys (`cast.py`): milo kai yumi brax pia mom dad lola reyes tan coach. One-offs go in
  `EXTRAS = {"uncle": dict(skin=, hair=, hair_col=, face=, own=dict(shirt=, pants=, shoes=, sleeve=, acc=[]))}`
  and must also be listed in `WHO`.
- Hair styles: short spiky bun ponytail long afro milo swoop pigtails.
- Faces: smile grin angry scared shock determined smug ahh sneeze twitch wink cry sleepy.
- Poses: idle stiff hold hold1 shock shock2 scared akimbo proud nod salute king sword ahh ahh2 sneeze
  lookdown cheer ballet twitch whistle peace point think sit sleep float.
  Expressive set (arms have elbows + mitten hands; one-handed gestures use the prop hand):
  facepalm shrug thinkchin crossarms panic (hands on head, shaking) wave (waves) clap (claps) fistpump
  raise (prop held high: trophy!) phone (looks down at the phone in hand) holdout (offers the prop
  forward) show (holds the prop up beside the face, front to camera) carry (both hands out, plate/box)
  eat (prop to mouth) mic (mic at the mouth) lean sad angry.
- Forms (`form NAME`): stone, stone_legs, stone_arms, stone_chest, ghost, rock, paper, scissors,
  pizza_1..pizza_4 (pizza = 4), chicken_1..chicken_4 (chicken = 4), hold_X+Y (props below, or any
  accessory like helmet), wear_X (same as hold), look_KEY (wear another cast member's clothes),
  headless (see popping heads below), own (back to normal). `nopuff` skips the puff.
- Hand props for hold_ (engine/props.py; they follow the hand and stay upright in any pose):
  phone (lit chat screen) plate (plate + sandwich; `sandwich` = same) test (graded paper, red circled A+)
  cash cookie slice (pizza) book trophy clock (alarm clock) mic lunchbox tissue.
  Default hand is the prop hand (a 2nd hand prop in the same hold_ goes to the other hand by itself);
  `_l` forces the other hand; `:#hex` recolours (book, clock, cash,
  phone, lunchbox, trophy): `^> kai form hold_phone+cash_l nopuff; ^> kai pose phone/scared`,
  `Win> milo form hold_trophy; Win> milo pose raise/grin`, `^> pia form hold_test nopuff; Grade> pia pose show/grin`.
  Body props: backpack (`wear_backpack:#E5262B`), beanbag, hamster.
  Props read best with: phone -> phone/show; test, book, cash, clock -> show/holdout; plate -> carry/hold;
  trophy -> raise/holdout; cookie, slice -> eat; mic -> mic.
- Accessories usable in hold_/wear_: helmet hairnet firehelmet cap tutu apron vest dress tie whistle glasses ...
- Motion: `size K` (0.25 tiny .. 3 giant), `lift DZ` (float up DZ units; 0 drops back), `run set.spot`,
  `spin`, `flail SECONDS`, `swap CHAR` (trade places), `show set.spot` (appear with a puff), `hide`.
- `PROPS = [("kind", "set.spot", dx, dy)]`: sign:TEXT (red text on a white board), pizzabox, cake,
  speaker, trampoline, ladder, car, dog, cat, tv (screen lit on both faces), fan (ceiling fan;
  the hub height is a 5th value: `("fan", "cafeteria.spot3", 0, 2, 9.0)`), alarm (wall fire alarm whose strobe
  blinks all film; 5th value raises/lowers it). An optional 5th value raises any prop.
- Popping heads (ep11): `form headless` hides the head, hair and head gear (`nopuff` as usual).
  `Word> dad pop SET.SPOT [dx dy dz] [more stops] [face]` = headless + a puff + a copy of the head (hair, head
  gear, current face, or the face named) flying on a tumbling arc to that spot (dz = height of the surface it lands
  on: couch seat 1.4, cafeteria table 2.55, the cake 3.3), through every stop listed
  (`pop cafeteria.spot3 0 2 7.0 cafeteria.spot3 3 -2` = hits the fan's underside, then lands on the floor), one
  small bounce, then it stays. `pop up` flies up out of the shot; `pop scatter` lands on the floor nearby.
  `crowd pop` pops every crowd member (rippled), but only 8 crowd heads really fly (render cost).
  `^> kai pile SET.SPOT [dx dy dz] milo yumi brax [face]` stacks the heads of kai + the listed cast (default grin)
  in a pyramid on that spot with a puff; flying heads of those characters / the crowd disappear when it appears.
  A camera can't frame a pile or a flying head by itself: frame a body beside it (`med:kai`, `high:brax`).
- `wear_tape`: crossed tape over the mouth (sits on the head, so a popped head keeps it).
- `CROWD = ("set", "form or None", count, scale)`; crowd members can be targeted with who `crowd`.
- `MUSIC = "island"` or `"riley"`.

## Shot grammar (what the judge scores)

Cam presets: `close med wide slide low high two:a,b` plus
- `insert:WHO` - macro of the prop in WHO's hand (WHO must `form hold_X` before the shot; pose `show`,
  `holdout`, `mic`, `raise` read best). Slightly high, the prop about 40% of the frame, the face behind it
  with the whole head (hair included) in frame. `insert:WHO:face` = tight close-up of the face (a
  transformation landing, a reaction): full head + hair ~44% of the frame height, a hint of shoulders and
  room - never just the eyes. Real look: both try a few sides / heights and avoid a head slicing background
  text (signs, boards).
- `pov:WHO` - first person: from just behind / above WHO's head (beside it, on the prop-hand side) looking
  down at the prop in their hand(s): hands + prop in the lower half, the scene beyond in the top half, 60 deg
  lens, a sliver of WHO's own hair may frame one edge. It looks the way WHO faces, so face them at something
  (`milo@..>pia`). Best with a prop held low: pose `holdout`, `phone`, `carry`, `hold` (a mic at the mouth is
  skipped for the prop in the other hand). Holding nothing -> `top`.
- `top:WHO` - top-down insert, ~75 deg straight down on the prop in WHO's hand(s), WHO's head at the top
  edge; holding nothing = WHO from above. Under a ceiling the camera comes down to fit.
- `fg:WHO` - a medium with foreground framing: the camera swings / eases back until a desk edge, a prop or
  another person sits soft in the near foreground at one side or the bottom (8-22% of the frame). Real look
  also does this by itself on up to 3 spaced eye-level mediums / close-ups.
- `ots:A,B` - over A's shoulder onto B: B's face just under the upper third on one side, A's head + shoulder
  at the opposite frame edge (at least ~45% of A's head in frame - never an orphan arm), ray-measured to
  <= ~30% of the frame width. If no position shows A's head, it becomes a clean single on B from A's side.
  Place them facing each other (`A@..>B B@..>A`) 4+ units apart (closer = A bigger). The occlusion fixer
  leaves OTS (and inserts) alone; walls behind A pull the camera in, another person in the way flips it to
  the other shoulder.
- Real look depth of field (keyed per frame on the subject): inserts / pov / top f/2 on the prop, close-ups and
  OTS f/2.8 on the head (OTS: B's head, so A is soft), foreground-framed mediums f/4; other mediums / wides
  sharp. The f-numbers are on a 1:22 scale for our 6-unit-tall people (`MILO_DOFK` overrides the 22).
- Real-look lenses (vertical FOV): close / insert / OTS 42-46 deg (no wide-angle bulge on faces), med /
  low / high 58, two 60, wide / slide 70, pov 60, top 50. `low` fills the frame (head top near the top, feet
  on the bottom edge) with the camera near the floor and the tilt capped at 20 deg; then every shot that looks
  up is ray-measured and the camera rises (and eases in) until ceiling / sky is under 15% of the frame.
- Real look: never 3 eye-level close/med/two shots in a row. The 3rd is converted automatically (a prop shot if
  the subject holds a prop - pov / top when held low, insert when held up -, OTS if someone faces them, else
  low/high) - but stage it yourself so you choose.
Aim per episode: 3+ inserts, 2+ pov / top on props, 2+ OTS, low on statues/heroes/arrivals, high on
victims/caught-out moments.
Acting: every close/med character gets a pose on its line (facepalm shrug thinkchin crossarms panic wave clap
fistpump point lean holdout show sad angry ...); never leave a main character in the default idle on camera.
A prop for every gag the line allows (mic for a joke, cash for paying, test for grades, phone for news...).
`episodes/ep01.py` is the worked example.

## Camera rules that bit us

- Every line needs at least one shot; split long lines (over ~1.8 s) into 2 cams. Each shot 0.6-2.5 s.
  A cut word needs ~0.6 s before the next cut: check `words.json` before choosing.
- `two:a,b` only when a and b stand within ~5 units; otherwise use `med:` on one of them.
- A character only exists on screen after it is placed (`at=`) or shown (`show`). Place everyone a line
  BEFORE their first shot. Placements happen at the start of the line that lists them.
- Characters keep forms/props until changed: add `^> kai form own nopuff` when a gag should end.
- Characters standing between the camera and the subject block the shot: check the sheet.
- Look at `_sheet.png` after every stills run and fix: empty/blue frames (camera inside a wall or a
  hidden character), backs instead of faces, the subject cut off, something blocking the lens.
