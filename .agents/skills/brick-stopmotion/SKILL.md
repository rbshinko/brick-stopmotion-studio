---
name: brick-stopmotion
description: Make vertical story Shorts in a toy-brick stop-motion look (a "brickfilm": plastic brick figures and sets, moved a little per frame and shot like a tabletop animation), with the same content as the Milo channel ("In this town, if you ___, you ___" stories). Use when the user asks for "Lego style", "parang Lego", "brick animation", "brickfilm", "stop motion", or "stoptime" videos; for brick-style episode ideas or scripts; or to build, test or change the brick look. It offers ideas first, shows the script before making the voice, and runs a look test before the first full render.
---

# Brick stop-motion Shorts

You make 30–35 s vertical (1080×1920) story Shorts that look like a stop-motion film made with toy
bricks. Real brickfilms are made by moving the figures a tiny bit, taking one photo, moving them again
and repeating ("inuurong-urong"). Here you get the same look entirely in Blender from code.

Talk in plain words, in the user's language (English, Tagalog or Taglish). Never assume they know
animation or coding terms.

## Ground rules (read first)

- **Brand safety.** "LEGO" is a trademark, and the classic minifigure shape is protected too. Never put
  the LEGO name or logo on studs, boxes, titles, tags or descriptions. Never copy an official minifigure,
  licensed set or theme. Build our own original **brick figure** (design below) and call the style
  "brick animation" or "stop motion" in metadata. If the user wants "Lego" in a title, explain this
  risk once in plain words and suggest "brick" or "stop motion" instead.
- **Original content.** Topics are new and written here. Never copy the user's old channel videos or
  another creator's characters or stories (see `my-rules.md`). Reference channels are for craft only.
- Never upload or post anything. Ask before any paid API. Never print keys. Never commit `inbox/`,
  `outbox/`, `my-style.md`, `my-rules.md` or `my-sounds/`.
- Save progress as you go: keep a log in `milo/BRICK-PROGRESS.md`, so work can resume after usage
  limits, crashes or reboots. Commit snapshots only when the user OKs it.

## How to work with the user (always this order)

1. **Ask before you build.** On the first brick request in a session, ask one short question with
   options (AskUserQuestion when available):
   - Which cast? **Milo's cast rebuilt as brick figures (recommended)**, or a new cast for a separate channel.
   - How many videos for this batch?
   Skip anything the user already answered.
2. **Give ideas first.** Offer 5 episode ideas as a numbered list. Each one gets a title in the winning
   shape ("Why is everyone in this town SCARED of ___??", or "In this town, if you ___, you ___"), the
   rule, and the twist in one line. Let the user pick or mix. Favour ideas that use the brick medium
   itself: things that snap apart, rebuild, turn into a different colour brick by brick, or fall apart.
3. **Show the script before making the voice.** Write it with the recipe below, show it, and wait for
   an OK or changes. No voice and no render until the user approves.
4. **Look test (first time only, or whenever the look changes).** Render 3 stills (a close-up, a medium
   and a wide) plus a 3-second motion test. Show them next to 2–3 reference frames if the user gave any.
   Offer up to 3 variants (for example: chunky plastic, clean toy, or a gritty "home-made" film). Save
   the user's pick in `my-rules.md` with their own words and the date.
5. **Produce:** stage the episode, then voice, plan, stills (show the contact sheet), frames, check,
   post, meta. Send the video and its paste-ready `.txt` (title, description, pinned comment, credits).
6. **Learn.** Save lasting notes ("faster", "bigger captions", "more clicks") to `my-rules.md`.

## Story recipe (the same as Milo; from the reference study)

Full numbers are in `milo/docs/STORY-RECIPE.md`.
- **Length and pace:** 30–34 s, 120–130 words, about 230 words per minute. Speech starts at 0.0 s and
  ends 0.1–0.3 s before the video does.
- **Hook:** at most 2.2 s and 9 words, and it is the title said aloud. 8 of the 10 references open with
  "Bro,".
- **Rhythm:** alternate a setup line (10–14 words) with a short comeback (3–7 words). The first joke
  lands by 5–6 s.
- **Body:** 4 escalations of about 4 s each. The flip (whoever enforces the rule wants out) comes at
  22–26 s. End on a role swap that loops back to shot 1, or, every 3rd video, ask the viewer a question.
- **Beats:** reuse the Milo beat system (RULE CAUSE VICTIM EX×3 ME INC×2 POP ESC×3 REVEAL QUIET
  TWIST PAYOFF CALLBACK) in `milo/episodes/`.

## The stop-motion look (what makes it read as a brickfilm)

**Motion (the most important part)**
- Animate "on twos". The engine runs at 30 fps; hold every pose for 2 frames (15 new poses per
  second). Use 3-frame holds for slow, heavy moments and singles only for very fast hits.
- After the motion is keyed, add a tiny random placement error per held pose so it looks hand-moved:
  about ±0.15 mm position and ±0.4° rotation at brick scale. Characters that aren't acting keep their
  error frozen (a real animator wouldn't touch them).
- No motion blur at all. Fast moves get 1–2 frames of a stretched "smear" pose or brick dust instead.
- Camera on a tripod: mostly locked shots. Any pan or push moves in steps on the same twos, never
  smooth.
- Tiny exposure flicker per held frame (±1–2%), like a real camera between photos.

**Scale, lens and light (tabletop miniature)**
- Build in real brick units: stud pitch 8 mm, plate 3.2 mm, brick 9.6 mm. A figure is about 4 cm tall.
- **No blur of any kind (user's rule, 2026-11-08: "make it all clear and no blurs").** Depth of field
  stays OFF on every shot, with no background blur, no macro blur, no motion blur and no blurred
  transitions. Everything is sharp front to back. Sell the "toy on a table" feel with scale, studs,
  plastic shine and lighting instead.
- Lens around 35–50 mm, camera close to the figures.
- Light like a desk set: 1–2 big soft area lights (softboxes) at 3800–4500 K, a warm practical lamp in
  the set, soft shadows, and a little bounce. The background is a brick-built set or a printed backdrop
  card.

**Plastic**
- ABS look: Principled roughness 0.25–0.35, specular 0.5, a light clearcoat and faint roughness
  variation (fingerprints, scuffs).
- Every edge gets a 0.1–0.2 mm bevel. Studs sit on top of bricks and plates with no logos. Use a slight
  translucent subsurface on light colours, and real transparent elements for glass, water and fire.

**Our brick figure (original design; not a minifigure copy)**
- About 4 cm tall, 6 parts: a rounded-box head (not a cylinder, no stud on top), separate hair pieces,
  a straight rounded-rectangle torso (not a trapezoid), mitten hands with a thumb, bendable arms, one
  leg block per side, and a peg-joint waist.
- Faces are printed decals in a simple style: dot eyes, thin brows, mouth shapes. Reuse the expression
  list from `milo/engine/facelist.py` and draw them thinner and simpler.
- Milo stays recognisable: red spiky hair piece with one curl (ahoge), round glasses, black jacket
  print, white tee, red pendant print.

**Sets and effects**
- Sets are built from bricks: baseplate ground with studs, running-bond brick walls, plate floors,
  round-brick trees, and furniture built from plates and tiles.
- Transformations happen brick by brick: for "you turn to stone", pieces swap to grey one at a time
  from the feet up, with a snap click on each.
- Smoke is cotton-wool puffs (fluffy, matte), fire and water are translucent pieces, and speed is shown
  with brick dust.

**Sound**
- Same kid narrator and mix as Milo: Kokoro, -14 LUFS, tanh soft clip.
- Add plastic foley: a tiny clack on each footstep, brick snaps on every transformation step, rattles
  when things fall. Keep the music light.

**Captions**
- Same as the Milo "real" look: 1–3 lowercase words, regular sans at 104 px with a 6 px outline and a
  soft shadow, centred at 60% height, and key words in red caps with a thicker outline.

## Building it in the engine (first run)

Reuse the Milo pipeline in `milo/` (`run.py`, `engine/plan.py`, `voice.py`, `post.py`, the episode DSL)
and add a brick look next to "brand" and "real". Read `milo/REAL-LOOK-PROGRESS.md` and
`milo/STAGING.md` first. Check that Eevee renders with a tiny test before long jobs; the GPU on this PC
once needed a reboot after hours of rendering.
- `engine/brickkit.py` (new): brick, plate and tile generators with studs, built with Geometry Nodes
  instancing so thousands of studs stay cheap, plus builders for a baseplate, walls, trees and furniture.
- `engine/brickfig.py` (new): the original brick figure rig, with the same pose and face interface as
  `core.Char` so episodes and the DSL work unchanged.
- `engine/look.py`: `MILO_LOOK=brick` sets up the plastic materials, desk lighting and grade. Depth of
  field must stay off; check that the camera's DOF is disabled before rendering.
- Stepped motion: a post-pass after `write_motion`. Keys are already one per frame with constant
  interpolation, so copy each held frame's value onto the following frame(s), then add the per-pose
  jitter. Apply the same pass to camera keys.
- Brick-by-brick transformation: a new form helper that swaps part colours in order over the effect's
  duration.
- Use subagents for parallel parts (figure, kit, look) with clear file ownership, as in the Milo
  real-look rounds.

## Quality loop (before calling the look done)

If the user names reference channels or videos, run the same study used for Milo:
1. Rank by views and engagement, and download the top 10 privately into `milo/reference/<channel>/`
   (gitignored).
2. Measure cuts, colour, light and audio with `milo/tools/stillstats.py`.
3. Have subagents analyse the visuals and the story flow.

Then build, and judge each round with a fresh judge subagent:
- Make a board of every 5th shot from 02, with real captions, over 6 reference frames
  (`milo/tools/epboard.py`).
- Score with weights: lighting 15, grade 10, materials/sets 15, characters 20, camera 20, acting/props 20.
- Fix the top issues it lists and repeat until it scores at least 90%. Log every round in
  `milo/BRICK-PROGRESS.md`.
