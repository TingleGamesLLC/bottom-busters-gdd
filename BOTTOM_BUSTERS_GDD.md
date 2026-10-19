# Bottom Busters — Game Design Document

Second draft, for Assignment #1 (GDD First Draft, due Tue 10/20), Multi-Agent AI for Game Development, ELVTR.
Studio: Tingle Games LLC. First draft 2026-10-08; this revision 2026-10-15, with game facts updated 2026-10-17 (share clip length, uzi streak rule, roast bank) and 2026-10-18 (cheek sets, colorblind mode, version number, demo and full-game builds). A 5-page short form of this document exists alongside it.

Status of this draft: the facts below come from the project's own docs (`CLAUDE.md`, the plan files and the session log in `C:\bbust\BBUST`) and from the game as built on 2026-10-15. Lines marked **[DRAFT]** are proposed wording to confirm or change.

## 0. What changed since the first draft (2026-10-08)

The first draft went through a six-reviewer design board on 2026-10-14. The decisions below were made after that review and are now part of the design. Each one names the board finding it answers.

- **The demo is the whole built game: all 99 levels, not 15.** The run ends, as a win, on the end card after Bonus Round 33, which follows level 99. Both the Steam and itch.io demos are this build. This answers the board's finding that a 15-level, pickup-boosted, bonus-heavy slice was a non-representative sample: what people play is what they will rate, and the flat stretch from level 8 is now exposed to real players before launch instead of after. (Sections 18, 19.)
- **The demo now has a defined end state.** The run is bounded by the end card; nobody plays past Bonus Round 33. For the full game the same mechanism bounds the run at level 200 (Section 18). The endless mode, where the only thing that climbs is the AI difficulty number, is the home for unbounded play and is specified as a separate mode (Section 5). This answers the "no end state" half of the board's top issue; the curve half is answered below.
- **The difficulty curve from level 8 on is a planned deliverable with a mechanism, not a gap.** Enemy count and the per-level difficulty number become a tuning table produced from playtest telemetry by a Difficulty Tuner agent and approved by hand, and the itch.io release exists to generate that telemetry. (Sections 6.3, 16.)
- **Level count stays at 200, and the 101 new levels have a production method.** New single-screen level files come from a Level Architect agent, are checked by a QA agent in a headless build, and are discovered at runtime like today's levels. The art rule of one unique backdrop per level stands and the Wardrobe Stylist agent is scoped to help. The 200 figure is kept because the method for producing the levels is now written down, not because the end card says so. (Section 16.)
- **The Custom Game menu stays in the demo as a teaser.** The board recommended pulling it as a dead click. The decision is to keep it: the end card already tells every player custom games are coming, the demo is explicitly a demo of a game in development, and the mockup is an explorable preview, not a dead button. The procedural-level and asset work from this course is what will sit behind it. (Section 5.)
- **Release intent is now explicit: itch.io first as the proving ground, then Steam as the commercial release, same build.** Price is proposed at $9.99 for the full game and free for the demo on both stores. (Section 19.)
- **Replays now cover every mode.** Gauntlet saves the whole run; Burrito Arena keeps a rolling 60-second window with Save Replay in the pause menu. Replay format v12. (Section 13.)
- **Not yet decided, still open from the board:** 2P fail states and score ownership in versus and co-op; the pickup drop table and the trap presentation; the Chain Kills definition and the bonus-round payout ratio; the roast line spec and announcer count; the Section 3 audience and register; the announcer wave callouts 1 to 50 against 60 Survival waves. These stay in Section 20.

---

## 1. Overview

**Title:** Bottom Busters

**Genre:** 2D arcade action platformer, score attack, local co-op and versus

**Platform:** PC (Windows) on Steam. Steam Deck is a target (Valve's Deck review is part of the launch plan). Mobile has come up as a possibility for clip sharing only.

**Engine:** Unity 6.3 LTS (6000.3.7f1), Universal Render Pipeline

**Players:** 1 or 2, on one machine. Online 2P is planned through Steam Remote Play Together.

**Inspiration:** Nintendo's *Balloon Fight*

**[DRAFT] One-line pitch:** A fart-powered Balloon Fight brawler where you pop your enemies' cheeks from above, survive the poo storm, and save every disaster as a replay.

**[DRAFT] Elevator pitch:** Every character floats like a balloon and flies by farting. Each one has two cheeks for health. Land on an enemy from above to pop its cheeks; lose both of yours and you deflate and fly off the screen. Water kills instantly. Thirteen powerups range from a speed burrito to an uzi to a cork that plugs you up for four seconds. The Green Burrito sprays poo that piles up, sticks to bodies and hats, and stays on the level. Play 99 single-screen levels for the highest run score, or jump into Burrito Arena, Survival or Gauntlet with a friend on the couch.

## 2. Design pillars [DRAFT]

1. **Stomp or be stomped.** Height is power. Flap timing and position decide every fight, the same way they do in *Balloon Fight*.
2. **Couch chaos.** Two players on one screen, as partners or rivals. Local 2P is in every mode and in the demo.
3. **Gross-out humor that leaves a mark.** Poo is physical. It piles, squishes, dirties cheeks, bodies and hats, and the base coat never washes off.
4. **Every run is a clip.** Every run is recorded 1:1, saved to a library, and can be exported as a 25- to 60-second vertical video to share.
5. **Plays on a potato.** Performance is a design requirement, not a polish pass.

## 3. Target audience [DRAFT]

- Players who like short-session arcade action and chasing a high score.
- Friends and families looking for a local couch co-op or versus game.
- Fans of crude, silly humor. The marketing plan treats this audience as separate from cozy or ambient players.
- Streamers and short-form video viewers, through shareable clips.

## 4. Core gameplay

### 4.1 The core loop

Spawn → flap for height → stomp enemies' cheeks from above while dodging theirs → grab powerups → clear every enemy on the screen → next level. Score carries across the whole run. When the last life is gone, the run ends on the GAME OVER card, with a roast and a list of superlatives, and the run can be saved as a replay.

### 4.2 Movement and controls

- **Flap (fart):** each flap pushes the character up. Holding the button repeats the flap. Every flap plays a fart sound at a random pitch.
- **Move:** left and right. There is no jump; flight is the only way up.
- **Gravity** pulls everything down. Characters can stand and walk on ground and platforms.
- **Ceiling:** characters bounce off the top of the screen.
- **Screen wrap:** flying off the left or right edge brings you in on the other side, so the play field works like a cylinder.

| Input | Player 1 | Player 2 |
|---|---|---|
| Move | A/D or arrow keys, or any gamepad stick | Gamepad stick, or a second keyboard |
| Flap | Space, or gamepad South button | Gamepad South button, or a second keyboard |
| Pause | Escape or gamepad Start | Gamepad Start |

Controls can be remapped for keyboard and gamepad in Settings. In 1P, Player 1 reads every connected gamepad.

### 4.3 Health, damage and death

- **Two cheeks** are a character's health. A stomp, a bump, an uzi bullet, a chili flame or a whoopee cushion pops one cheek.
- **Stomp Kill:** landing on an enemy so that both of its cheeks pop at once.
- **Death:** with both cheeks gone the character deflates and flies off on a 5-second death flight, arms flailing.
- **Instant deaths:** water (or lava), the splat bat pickup, and the bomb pickup.
- **Water** kills when the character's center is inside it, not on a graze, so standing at a ledge is safe.
- Screen-wrap edge copies of a character can be hit, and those hits count on the real character.

### 4.4 Lives and respawn

- 3 lives per player, shown as white underwear icons. A 1UP pickup adds one. Lives are uncapped; after five icons the display collapses to one icon with a number.
- Lives carry from level to level for the whole run.
- After a death with lives left, the player respawns at their spawn point with the same character and flickers invincible for 1 second (2 seconds in Survival).
- In 2P co-op, if one player is out, the next 1UP the other player picks up revives them.

## 5. Game modes

| Mode | Players | Summary |
|---|---|---|
| **High Score** | 1P, 2P co-op, 2P versus | The main mode. Levels in order, three lives, one score for the whole run. A bonus round every 3 levels. |
| **Burrito Arena** | 1P, 2P co-op, 2P versus | Casual fun mode on a random level's backdrop and terrain. 1P has infinite hidden lives and no visible timer. 2P versus is a deathmatch with three lives each; the last player standing gets a "P1 WINS!" or "P2 WINS!" victory card. |
| **Survival** | 1P, 2P co-op | 60 waves in three tiers of 20. Each tier climbs from 1 to 20 enemies falling in from the sky; difficulty steps up at waves 21 and 41 (shown as 100%, +25%, +25%). Clearing wave 60 is a VICTORY. Own leaderboards for Highest Wave and Most Points. |
| **Gauntlet** | 1v1 or 2v2 against AI | No powerups. The AI gets 10% tougher every wave, with no cap. One life per player; an eliminated player returns when their partner clears the wave. Every wave fully resets both sides, cheeks included. Own leaderboards for Highest Wave and Most Points, like Survival. |
| **Bonus Round** | inside High Score | Four chef animals flip food straight up; catch it for 500 points each (20 pieces in 1P, 40 in 2P). Nobody can die. When the round ends, the chefs' hats become trampolines until the player continues. |
| **Endless** (planned) | 1P, 2P co-op | Levels keep coming with no end. Nothing changes but the enemy difficulty number, which climbs a step every few levels with no cap, until the lives are gone. Ranked by the level reached. The infinite-play home for players who want more than 200. |
| **Custom Game** | teaser | A fully interactive menu mockup with no gameplay behind it yet. Custom games are promised for the full game. Decision 2026-10-15: it stays in the demo as a teaser; the procedural-level and asset-generation work from this course is what goes behind it. |

Survival, Gauntlet and versus Burrito Arena end cards have a PLAY AGAIN button. High Score has no retry: a run is a run.

## 6. Levels and world

### 6.1 What a level is

- **One screen, no scrolling:** about 18 x 10 world units on a 1 x 1 grid.
- **Ground:** one strip along the bottom with water gaps cut into it.
- **Platforms:** short runs on three heights.
- **Ceiling drops:** on some levels enemies start far above the screen and fall in. A red triangle at the top of the screen shows where each one will come through.
- **Six all-water levels** (8, 25, 41, 58, 74, 91) have no ground at all; they use only sky or moon backdrops.
- A level is cleared when every enemy is defeated. Levels are static, built once and shipped as-is, so replays and best times stay valid forever.

### 6.2 Worlds and themes

- **99 levels exist today** across six terrain themes. The full game is planned at **200 levels**.
- Themes include blue stone, green sludge, pale bone, ice, charred ember, and a red crimson world. The last world is the red lava world, where lava replaces water.
- Every level has its own layered 3D parallax backdrop, with no backdrop used twice and no two neighboring levels from the same art pack.
- Arena modes borrow a random level's backdrop and matching ground tiles.

### 6.3 Difficulty curve (as built today)

- **Levels 1–3:** 3 enemies.
- **Levels 4–6:** 4 enemies.
- **Ceiling-drop levels:** levels 7, 24, 40, 57, 73 and 90 have 5 enemies, 4 of them falling in from above.
- **Every other level:** 3 enemies at difficulty 1.0 to 1.3.
- **Lava:** replaces water on levels 84–99.
- **Powerup odds:** Burrito and Green Burrito are 25% more likely in levels 1–15, which is the demo's range.
- **As built, enemy count and difficulty do not ramp across levels 8–99.** This is the board's top finding and it is now a planned deliverable with a mechanism: enemy count and the per-level difficulty number move out of the level files into one tuning table. The table is produced by the Difficulty Tuner agent (Section 16) from the per-run event logs of itch.io playtests, and nothing in it ships without a human playtest. The first target curve is **[DRAFT]**: 3 enemies at 1.0 through level 12, then +1 enemy every 25 levels and +0.05 difficulty every 10 levels, so that level 99 runs 6 enemies at about 1.5 and level 200 runs 10 enemies at about 2.0, with the lava world (levels 185–200) as the finale. Those numbers are a starting point for the first playtest round, not a promise.
- **The run has an end.** The demo ends on the end card after Bonus Round 33 (level 99). The full game ends the same way after level 200's bonus round, with a VICTORY card **[DRAFT]**. Players who want no end play Endless (Section 5).

## 7. Characters

- **Players:** 10 character skins plus RANDOM. A RANDOM pick rolls once and stays the same for the whole run.
- **Enemies:** 10 AI character variants. They fly, fart, drown and bounce off the ceiling under the same rules as players.
- **Character Select** comes before every mode, with one cursor per player: skin, hat, shades and hat colors, then READY.
- **Wearables today:** a santa hat and a turkey hat; black shades and silver aviators; 10 color swatches per hat region plus the art's default colors. Hats get dirty from poo too.
- **Settings option:** "AI Wear Hats" puts random hats on enemies.
- **Cheek sets (2026-10-18):** every character rolls one of four cheek sets each life, players and enemies alike: smooth (glossy skin), zits (razor burn: stubble, follicle-sized whiteheads, ingrown hairs, blackheads), scarred (stitched scar, bruise, crossed band-aids) and hairy (realistic hair of mixed lengths). All four keep the original disc, 5 px outline and skin tone. The menus roll them too. Replays show each life's own set; replays saved before the sets keep the original hairy cheeks.

## 8. Enemy AI

- A state machine: Flying, Diving, Stunned, Idle.
- One difficulty value controls how aggressive and capable an enemy is. High Score levels use 1.0 to 1.3; Survival uses 1.4, 1.8 and 2.2 by tier; Gauntlet climbs 0.1 per wave without a limit.
- Enemies avoid water using look-ahead box checks.
- In Survival, falling enemies are held at a height cap so they don't stay off screen too long and then drop in at extreme speed.

## 9. Powerups

Pickups float and pulse, and each pickup scores 50 points. High Score levels carry the full roster; the all-water levels leave out the three that need ground (cork, whoopee, toilet).

| Powerup | Effect |
|---|---|
| Burrito | 2.5x speed for 5 seconds |
| Green Burrito | Chaos: uncontrollable flight while spraying poo |
| Ham | Restores a cheek |
| Gum | A pink bubble that absorbs one pop; water and bombs still kill |
| 1UP | +1 life, or revives an out co-op partner |
| Uzi | 3-second burst; one bullet pops one cheek; chained kills call out DOUBLE through MEGA KILL |
| Chili | For 6 seconds every flap also shoots a flame that pops cheeks and burns loose poo |
| Cork | Flapping does nothing for 4 seconds, then a pop launches you up |
| Whoopee Cushion | Carried until you touch ground, then planted; whoever lands on it loses a cheek and is launched into the ceiling |
| Spinning Platform | Spawns a rotating hazard platform; it and its pickup invert the colors of the backdrop behind them |
| Splat Bat | A trap: instant splat death (unless the gum bubble takes it), with a full-screen splat effect |
| Bomb | A trap: kills the player who grabs it and pushes everyone nearby away |
| Toilet | No longer a pickup. In the arena modes, once enough poo piles up, a toilet falls from the sky onto the biggest pile and flushes everything within a small radius |

## 10. The poo system

- The Green Burrito's spray turns into physical poo chunks that fall, settle and pile up on the ground.
- Poo dirties cheeks, bodies and hats, and the stains stay.
- Walking or landing in poo makes squishy footstep sounds.
- The first layer, the base coat, is permanent. Chili fire and toilet flushes clear only the loose chunks above it.
- Poo is also a performance budget. The toilet strike is triggered by the poo chunk count, and in Survival that threshold drops each wave.

## 11. Scoring

The score is one total for the whole run, never per level.

| Action | Points |
|---|---|
| Stomp Kill (both cheeks at once) | 500 |
| Cheek Pop (stomp, uzi, chili or bump) | 100 |
| Splat An Enemy (Green Burrito spray hits a character) | 10 |
| Direct Deposit (spray lands on their head) | 25 |
| Marked For Death (kill within 3 s of splatting them) | 250 |
| Chain Kills (kills made in the air) | x2, x3, x4... |
| Flawless Clear (no cheeks lost, High Score only) | 1,000 |
| Powerup Pickup | 50 |
| Uzi Kill Streak (Double / Triple / Quadra / Penta / Mega) | 1,000 / 1,500 / 2,000 / 2,500 / 3,000 |
| Bonus round food | 500 each |

- Kills by bombs, whoopee cushions, the bat or a dead player's flying body score for nobody. Drowning an enemy scores nothing.
- Points pop up on screen where they were earned, and pop-ups lift so they never overlap.
- Uzi streak badges appear where the enemies died.
- The end card lists each kill combo earned, for example "Double Kill: x2 – 2,000".
- A streak counts once, at the top badge it reached: each new badge pays only the step up to its value, so a penta streak totals 2,500 and the card lists only that Penta Kill. The 6th kill is the mega and the last badge. A kill that lands after the shooter died or the level ended gets no badge and no bonus (2026-10-17).

## 12. Feedback, UI and presentation

- **Main menu:** a wrapping menu wheel (keys, stick, mouse and touch) with the Steam leaderboard on screen. A Tingle Games intro sting plays once per launch.
- **Menu pages:** Replays, Stats (lifetime totals), Scoring (the points table), Settings (audio, remapping, announcer voice, colorblind mode, AI Wear Hats; also used as the pause menu), Credits.
- **Colorblind mode (2026-10-18):** Off, Protanopia, Deuteranopia or Tritanopia, ported from Tingle Solitaire. One daltonization filter over the whole finished picture (every menu, the HUD and gameplay), not per-item color swaps. Checked by colorblindness simulation: the red/green problems are fixed (player vs enemy glow under deuteranopia 24.6 -> 69.3 deltaE; burrito vs green burrito under protanopia 3.9 -> 21.2); a few pairs come closer and are accepted (poo on the pale bone ground; the Quadra and Penta badges under tritanopia, which also differ in words). Share clips stay in normal colors.
- **Version (2026-10-18):** the build's version shows in the main menu corner and at the foot of Settings, e.g. "v0.9.0 demo - itch - 2026-10-18 5e6f142", and is recorded in Player.log and every replay.
- **HUD:** each player's run total and underwear life icons, a timer with the Bottom Busters logo on either side, the level number top right, and wave and difficulty % in Survival and Gauntlet. Every HUD text sits on a dark box so it reads on any backdrop.
- **End of run:** a 10-second wind-down, then the result card. GAME OVER (with a sad trombone-style sting) or VICTORY, the final total and best, a roast line, and rotating superlatives such as Methane Released, Held It In, Full Coverage and Died Dirty.
- **Announcer:** three pre-recorded voices, named in Settings as Mr. Announcer (the default), Drill Sergeant and Scottish. They read roast lines, wave callouts 1–50 and uzi kill streaks. Players can turn the announcer off.

## 13. Replays, sharing and leaderboards

- **Replays:** every run is recorded as a 1:1 copy of what was on screen, including poo, splats, sounds and the HUD. Players save runs to a library and can Watch, Rename, Delete or Share them. Library rows show live previews of the replay.
- **Every mode records (as of 2026-10-15, format v12).** High Score and Survival as before. Gauntlet saves the whole run, with the late-spawning wave enemies and the WAVE banners recorded. Burrito Arena, which never ends in 1P and co-op, keeps a rolling window: the recorder holds at most the last 90 seconds, SAVE REPLAY in the pause menu writes the last 60 seconds as a snapshot and the session keeps recording, and the versus winner card saves the last 60 seconds of the match. The button's hover text says "Saves the last 60 seconds." Older replays still load.
- **Share clip:** a 25- to 60-second video (a CLIP LENGTH chooser in 5-second steps, capped at the replay's length; arena and Gauntlet clips default to 60 seconds), rendered in-game in one of two shapes, picked on a PHONE | 16:9 switch above the length slider (2026-10-18; the last pick is remembered): PHONE is 9:16 for TikTok, Shorts and Reels, where the camera follows the action and zooms in around fights; 16:9 is the whole screen exactly as Watch shows it, HUD included, for YouTube, Discord and Steam. Players save it through a Save As dialog. The encoder is a bundled LGPL FFmpeg build that uses the computer's own GPU encoder.
- **Clip pages (planned, not built):** each shared clip gets its own public, anonymous page on tinglegames.com, rated in pairs of white underwear.
- **Leaderboards:** Steam boards with Global and Friends tabs, a 1P/2P toggle, and High Score, Survival and Gauntlet, the last two each split into Highest Wave and Most Points (Gauntlet since 2026-10-18). The top 3 entries carry a replay anyone can watch in-game, with Steam names shown over the characters.
- **Anti-cheat (planned):** a server checks each run before posting it to trusted boards. This waits on the game's own Steam App ID.

## 14. Art direction

- 2D sprite characters over layered 3D parallax backdrops, one per level.
- Terrain is 32-pixel tile art with point filtering, drawn large on screen.
- Gameplay has a light post-processing grade: bloom, slight contrast and saturation, and a soft vignette.
- The splat effect is one flat brown (RGB 117, 74, 40) with no shading.
- The splat bat throws the character it hit at the screen wearing its own face, with X eyes and a frown.
- Humor-first visuals: underwear life icons, cheek "health", poo stains that stay, chef animals in the bonus rounds.
- A house sprite standard (import settings, density against a 4K screen) is applied automatically to every new sprite.

## 15. Audio

- A fart on every flap, at random pitch, for players and AI.
- Level music comes from a shuffled set of 10 tracks, so a song never repeats until all 10 have played. There is a menu track and lo-fi music in the bonus rounds.
- Squishy poo footsteps, water splashes, cork pops, flushes, chef bounce sounds by species, and death and game over stings.
- All sound levels are tuned from one shared audio library asset.
- A music composition and license agreement for original music is drafted, pending an attorney's review.

## 16. AI in Bottom Busters

**In the game:**
- Enemy AI with a single tunable difficulty value (section 8).
- The roast lines come from a pre-written line bank, never generated live. This keeps the cost to $0 per player, works offline, and keeps Steam's disclosure to the pre-generated-content checkbox. The roast lines are due for a rework. As of 2026-10-17 the bank has 46 lines, picked by win or loss only, and the 25 lines about poo, toilets or smell never play in Gauntlet.
- The announcer voices are text-to-speech recorded ahead of time (ElevenLabs), shipped as audio files. Steam's AI-disclosure rules treat that as pre-generated content.

**For this course: a development-time agent crew.** Two kinds of AI exist in this project and they never mix. The shipped game's only AI is the enemy state machine above plus pre-recorded voices and pre-written text. The crew below runs at development time on the project's own files, and its output is ordinary game data the game already discovers at runtime: level files, a tuning table, text, sprites and test reports. No agent runs on a player's machine and no API key ships in the build. Each agent has one job and one output, no two write the same file, and the handoff between them is a file in the repository. A human playtest is the last gate for all of it.

| Agent | Development role | What the player sees because of it |
|---|---|---|
| Level Architect | Writes new single-screen level files (ground gaps, platforms, spawn points, ceiling-drop markers, theme) that obey the rules in Section 6.1. | Levels 100 to 200 and the Endless mode's layouts. |
| Difficulty Tuner | Reads the per-run event log from playtests and proposes enemy count and the difficulty number for each level and each Endless step. | The curve in Section 6.3 actually climbing after level 8. |
| Roast Writer | Rewrites the roast line bank and superlatives, tagged to the run events that trigger them. | A GAME OVER card that roasts what you actually did, from text shipped inside the game. |
| Wardrobe Stylist | Produces hat and shades sprites and backdrop picks that pass the house sprite standard. | More hats and shades on Character Select; more unique backdrops for the new levels. |
| QA Playtester | Loads every new level in a headless Unity build and checks that each enemy is reachable, no spawn is over water, and the level can be cleared. | No unwinnable or empty level reaches the demo. |
| Builder | Reads this GDD and the project's coding rules and implements one approved feature at a time in C#, then runs the existing build-and-verify loop. | The Endless mode, the Custom Game screen behind the teaser, and the loaders the other agents' output needs. |

Semester token budget, as a cap: about 4.8 million tokens, of which the Builder is 3 million (six feature slices at about 500,000 each) and the five content agents share the rest. The budget and the per-agent file boundaries are in the short-form GDD.

## 17. Technical summary

- Unity 6.3 LTS, URP, the new Input System, Box2D physics.
- Steam integration through Facepunch.Steamworks: leaderboards, Workshop-hosted replay files, friends.
- Replays are recordings, not deterministic re-simulations, so balance patches never break saved replays.
- One event log per run feeds three things: stats, replay playback and score checking.
- Levels, player skins and AI variants are discovered at runtime, never hardcoded, so new content drops in.
- **One project, two build targets.** The Steam build and the itch.io build come from the same tree, scenes and assets. The itch target turns off the Steam define and leaves the two Steam DLLs out, asserts that no Steam file or debug symbol is in the output, and zips. There is nothing to keep in sync between the two stores because there is one source.
- **Demo builds and full-game test builds (2026-10-18).** Each build command makes two players per store: the demo players download, which saves no diagnostic files on their machines, and a full-game test copy that runs past the demo's end and keeps every diagnostic log, for development only.
- Development so far is about 413 logged hours, counted as a minimum.

## 18. Scope: demo and full game

**Demo (built, 2026-10-15), identical on itch.io and Steam:**
- All 99 built levels, ending as a win on the end card after Bonus Round 33.
- Every mode and 2P are included. Custom Game is present as a teaser (Section 5).
- The end card reads: "THAT'S THE DEMO. You played 99 levels. The full game has 200. Plus more characters, more music, more sounds, more powerups, and custom games you build yourself." Its first button is WISHLIST ON STEAM in the Steam build and FOLLOW ON ITCH (the game's itch page) in the itch build (2026-10-18).
- The developer level-skip buttons are gone from every build (2026-10-18).
- The demo says so (2026-10-18): its exe is "Bottom Busters Demo.exe" and the main menu shows a red DEMO stamp across the bottom corner of BUSTERS. The itch demo is uploaded with butler to the itch page's windows-demo channel (version 0.9.0), so updates patch only what changed.
- Why 99 and not 15 (decision 2026-10-15): the 15-level slice was pickup-boosted, ended on a bonus round and was too short to show the curve, so wishlists and reviews would have come from a game the demo did not resemble. At 99, the demo is the honest version, the flat curve and the run length get real feedback before Next Fest, and the class deliverable is the actual game. The cost, accepted: the built game is free, and the purchase incentive is the 101 levels, the Endless mode and the content still to come.
- The pickup boost for levels 1–15 (Section 6.3) was tuned for the old demo range and is on the drop-table list in Section 20.

**Full game:**
- 200 levels, with the curve and ending in Section 6.3.
- The Endless mode (Section 5).
- More characters, music, sounds and powerups.
- A custom game builder, fronted by the Custom Game screen that ships as a teaser today.

**Planned later:**
- A Hats 'n Shades store (real money).
- Seasonal and collectible hats.
- Steam Workshop hats.
- Steam Cloud sync of owned items.
- Achievements (a list of about 60 has been drafted).
- Remote Play Together for online 2P.

## 19. Business and release [DRAFT]

- Publisher: Tingle Games LLC (Texas). Steamworks approval is in its identity-verification step.
- The Steam build contains no sweepstakes, donation button or crypto.
- **Release intent: itch.io first, then Steam, same build.** itch.io is the proving ground: the 99-level demo goes up first as a Draft or password-restricted page for the class and a small group of testers, then public. It is where the curve, the run length, the end card and the agent-made content get played by strangers before anything is promised on a store page that sells, and it is the source of the playtest telemetry the Difficulty Tuner needs. Builds push through itch's butler tool. Steam is the commercial release and carries the account-backed features: global and friends leaderboards with watchable replays, Remote Play Together, Workshop replays.
- **Proposed timeline:**
  - itch.io demo: October 2026, restricted; public when the first playtest round is in.
  - Steam demo in November 2026, once the App ID exists.
  - Steam Next Fest, Feb 22 – Mar 1, 2027, plus the Couch Co-Op Fest, Feb 8–15, 2027.
  - Launch in March or April 2027.
- **Price [DRAFT, proposed]:** demo free on both stores; full game $9.99 on both, with a 10–15% launch discount. itch stays at price parity with Steam because Steam's terms require it. Level count does not move the price; the Endless mode is the retention feature that lets the price hold through sales.
- Remote Play Together lets one owner play with a friend online. Steam turns it on for games listed as local co-op, and it also qualifies the game for the Couch Co-Op Fest.
- **Marketing:** daily vertical clips from the game's own clip exporter, posted to YouTube Shorts, TikTok and Instagram Reels, with a wishlist link on every post.
- **Localization:** store pages first, starting with Simplified Chinese. The game has very little text to translate.

## 20. Risks and open questions

- **Steam App ID:** online play, trusted leaderboards and Workshop features wait on Steamworks approval. The itch.io release does not.
- **Difficulty curve:** as built, levels 8–99 repeat the same enemy setup. The mechanism and first target curve are in Section 6.3; the risk is now that the first playtest round is late, not that the curve is unplanned.
- **2P fail states and score ownership (open, from the board):** versus has no rule for simultaneous death; 1UP is not ruled out of versus; co-op does not say whose last life ends the run; Sections 5 and 11 say one score for the run while the HUD shows each player's total. To be written before the public itch page.
- **Pickup drop table and trap presentation (open, from the board):** no per-pickup weights or placement rules; Splat Bat, Bomb and Cork share the reward presentation of real pickups; the levels 1–15 boost is left over from the old demo range.
- **Scoring definitions (open, from the board):** Chain Kills base and stacking, Stomp Kill 500 vs 700, Flawless Clear's "lost," and the bonus-round payout against three levels of play.
- **Roast lines and announcer:** the roast bank needs a spec (target, register, 1P vs 2P addressee) before the rework; whether the demo ships one announcer or three is undecided. Replays freeze whatever line was live, so the rework deadline is before the public demo records its first run.
- **Announcer wave callouts** cover 1–50 against 60 Survival waves. One number.
- **Audience and register (open, from the board):** "friends and families" next to an uzi and kill-streak callouts. Decide the buyer or the vocabulary, and write the roast spec on the same decision.
- **Level variety:** single-screen levels on a fixed ground strip and three platform heights can look alike across 200 levels. Layout concepts are in `LEVEL_DESIGN_CONCEPTS.md`; the Level Architect agent's rules will be written from whichever are chosen.
- **Remote Play latency:** remote play is video streamed, and the added delay may hurt flap timing. Not yet tested.
- **Music and audio rights:** need to be cleared before clips and streams are promoted.
- **Fill in:** pitch, pillars and audience wording.
