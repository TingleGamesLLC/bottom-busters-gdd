# Bottom Busters — Game Design Document

Started for Assignment #1 (GDD First Draft, due Tue 10/20), Multi-Agent AI for Game Development, ELVTR.
Studio: Tingle Games LLC. First draft 2026-10-08; this revision 2026-10-15, with game facts updated 2026-10-17 (share clip length, uzi streak rule, roast bank) and 2026-10-18 (cheek sets, colorblind mode, version number, demo and full-game builds) and 2026-10-21 (whole-replay share clips, more playable characters, retiled levels, menu hats and shades, the itch web leaderboard plan) and 2026-10-22 (High Score AI difficulty by world, High Score Play Again, roasts picked by the run's events, Custom Game mode defaults) and 2026-10-23 (both players start near each other, developer skip buttons out of every build) and 2026-10-23/24 (itch sign-in, the web leaderboard and clip pages live, High Score replays cut to the last level played, Parsec for online 2P on itch) and 2026-10-24/25 (both players on keyboards, Player 2's own gamepad layout, every controller works in menus, the itch run check built, version 0.9.1, tinglegames.com live) and 2026-10-28 (the itch demo public with version 0.9.1, the run check live with its review in the developer dashboard, a whispered "Tingle" in the intro sting, a warning when quitting would drop a run from the boards, the first trailer, a Bottom Busters YouTube channel and Instagram account) and 2026-10-31 (arms flap on every normal fart, an idle breath for characters standing still, version 0.9.3). A 5-page short form of this document exists alongside it.

Sources: the facts below come from the project's own docs (`CLAUDE.md`, the plan files and the session log in `C:\bbust\BBUST`) and from the game as built on 2026-10-15.

## 0. What changed since the first draft (2026-10-08)

The first draft went through a six-reviewer design board on 2026-10-14. The decisions below were made after that review and are now part of the design. Each one names the board finding it answers.

- **The demo is the whole built game: all 99 levels, not 15.** The run ends, as a win, on the end card after Bonus Round 33, which follows level 99. Both the Steam and itch.io demos are this build. This answers the board's finding that a 15-level, pickup-boosted, bonus-heavy slice was a non-representative sample: what people play is what they will rate, and the flat stretch from level 8 is now exposed to real players before launch instead of after. (Sections 18, 19.)
- **The demo now has a defined end state.** The run is bounded by the end card; nobody plays past Bonus Round 33. For the full game the same mechanism bounds the run at level 200 (Section 18). The endless mode, where the only thing that climbs is the AI difficulty number, is the home for unbounded play and is specified as a separate mode (Section 5). This answers the "no end state" half of the board's top issue; the curve half is answered below.
- **The difficulty curve from level 8 on is a planned deliverable with a mechanism, not a gap.** Enemy count and the per-level difficulty number become a tuning table produced from playtest telemetry by a Difficulty Tuner agent and approved by hand, and the itch.io release exists to generate that telemetry. (Sections 6.3, 16.)
- **Level count stays at 200, and the 101 new levels have a production method.** New single-screen level files come from a Level Architect agent, are checked by a QA agent in a headless build, and are discovered at runtime like today's levels. The art rule of one unique backdrop per level stands and the Wardrobe Stylist agent is scoped to help. The 200 figure is kept because the method for producing the levels is now written down, not because the end card says so. (Section 16.)
- **The Custom Game menu stays in the demo as a teaser.** The board recommended pulling it as a dead click. The decision is to keep it: the end card already tells every player custom games are coming, the demo is explicitly a demo of a game in development, and the mockup is an explorable preview, not a dead button. The procedural-level and asset work from this course is what will sit behind it. (Section 5.)
- **Release intent is now explicit: itch.io first as the proving ground, then Steam as the commercial release, same build.** Price is $9.99 for the full game and free for the demo on both stores. (Section 19.)
- **Replays now cover every mode.** Gauntlet saves the whole run; Burrito Arena keeps a rolling 60-second window with Save Replay in the pause menu. Replay format v12. (Section 13.)
- **More playable characters (2026-10-21).** Feedback on the build asked for more playable characters than the ten skins. This answers that feedback, not a board finding. A seventh agent, the Character Artist, joins the crew to make them, and finished characters drop in through the game's runtime skin discovery. (Sections 7, 16.)
- **A web leaderboard for the itch demo (designed 2026-10-21, live 2026-10-23).** The itch build has no Steam, so its boards were local only. Players now sign in with their itch accounts in the game, and each finished run uploads to a full-window page at tinglegames.com/bottom-busters/leaderboard that replicates the animated main menu without its menus; itch accounts are the only identity. Top-3 runs get public clip pages. Online 2P on itch goes through Parsec, the free remote-play app. (Section 13; `ITCH_LEADERBOARD_PLAN.md`, `CLIP_PAGES_PLAN.md` and `MULTIPLAYER_PLAN.md` in the game repo.)
- **Not yet decided, still open from the board:** 2P fail states and score ownership in versus and co-op; the pickup drop table and the trap presentation; the Chain Kills definition and the bonus-round payout ratio; the roast line spec and announcer count; the Section 3 audience and register; the announcer wave callouts 1 to 50 against 60 Survival waves. These stay in Section 20.

---

## 1. Overview

**Title:** Bottom Busters

**Genre:** 2D arcade action platformer, score attack, local co-op and versus

**Platform:** PC (Windows) on Steam. Steam Deck is a target (Valve's Deck review is part of the launch plan). Mobile has come up as a possibility for clip sharing only.

**Engine:** Unity 6.3 LTS (6000.3.7f1), Universal Render Pipeline

**Players:** 1 or 2, on one machine. Online 2P is planned through Steam Remote Play Together.

**Inspiration:** Nintendo's *Balloon Fight*

**One-line pitch:** A fart-powered Balloon Fight brawler where you pop your enemies' cheeks from above, survive the poo storm, and save every disaster as a replay.

**Elevator pitch:** Every character floats like a balloon and flies by farting. Each one has two cheeks for health. Land on an enemy from above to pop its cheeks; lose both of yours and you deflate and fly off the screen. Water kills instantly. Thirteen powerups range from a speed burrito to an uzi to a cork that plugs you up for four seconds. The Green Burrito sprays poo that piles up, sticks to bodies and hats, and stays on the level. Play 99 single-screen levels for the highest run score, or jump into Burrito Arena, Survival or Gauntlet with a friend on the couch.

## 2. Design pillars

1. **Stomp or be stomped.** Height is power. Flap timing and position decide every fight, the same way they do in *Balloon Fight*.
2. **Couch chaos.** Two players on one screen, as partners or rivals. Local 2P is in every mode and in the demo.
3. **Gross-out humor that leaves a mark.** Poo is physical. It piles, squishes, dirties cheeks, bodies and hats, and the base coat never washes off.
4. **Every run is a clip.** Every run is recorded 1:1, saved to a library, and can be exported as a 25- to 60-second vertical video to share.
5. **Plays on a potato.** Performance is a design requirement, not a polish pass.

## 3. Target audience

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
| Move | A/D (in 1P also the arrow keys), or any gamepad stick | Left/Right arrow keys on any keyboard, or the second gamepad's stick |
| Flap | Space, or gamepad South button | Right Ctrl on any keyboard, or the second gamepad's South button |
| Pause | Escape or gamepad Start | Gamepad Start |

Controls can be remapped in Settings, with separate Player 1 and Player 2 sections for keyboard and gamepad. In 1P, Player 1 reads every connected gamepad. Both players can share one keyboard or each use their own (2026-10-24), and every connected controller works in the menus (2026-10-25).

### 4.3 Health, damage and death

- **Two cheeks** are a character's health. A stomp, a bump, an uzi bullet, a chili flame or a whoopee cushion pops one cheek.
- **Stomp Kill:** landing on an enemy so that both of its cheeks pop at once.
- **Death:** with both cheeks gone the character deflates and flies off on a 5-second death flight, arms flailing. A player's button still flaps the arms during the flight (2026-10-31), with no thrust, sound or stat, because it's funnier that way.
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
| **Custom Game** | teaser | A fully interactive menu mockup with no gameplay behind it yet. Custom games are promised for the full game. Decision 2026-10-15: it stays in the demo as a teaser; the procedural-level and asset-generation work from this course is what goes behind it. Since 2026-10-22 each mode opens at the real game's settings (lives, which powerups spawn, spawn timing, caps, bonus round tuning), all still changeable, and the demo marks Start Game "Not Available in Demo". |

Survival, Gauntlet and versus Burrito Arena end cards have a PLAY AGAIN button. Since 2026-10-22 the High Score GAME OVER card has one too, starting a new run from level 1; High Score's level-complete cards have no retry.

## 6. Levels and world

### 6.1 What a level is

- **One screen, no scrolling:** about 18 x 10 world units on a 1 x 1 grid.
- **Ground:** one strip along the bottom with water gaps cut into it.
- **Platforms:** short runs on three heights.
- **Ceiling drops:** on some levels enemies start far above the screen and fall in. A red triangle at the top of the screen shows where each one will come through.
- **Six all-water levels** (8, 25, 41, 58, 74, 91) have no ground at all; they use only sky or moon backdrops.
- A level is cleared when every enemy is defeated. Levels are static, built once and shipped as-is, so replays and best times stay valid forever.
- **Every level was retiled by hand on 2026-10-21** so terrain rows no longer sit stacked with a single empty cell between them, which left no room to fly.
- **Both players start near each other (2026-10-23):** Player 2 starts on the ground 3 to 4 units to Player 1's left, on the far side of a water gap where Player 1 starts on a middle island, and a short hop up and to the right on the all-water levels.

### 6.2 Worlds and themes

- **99 levels exist today** across six terrain themes. The full game is planned at **200 levels**.
- Themes include blue stone, green sludge, pale bone, ice, charred ember, and a red crimson world. The last world is the red lava world, where lava replaces water.
- Every level has its own layered 3D parallax backdrop, with no backdrop used twice and no two neighboring levels from the same art pack.
- Arena modes borrow a random level's backdrop and matching ground tiles.

### 6.3 Difficulty curve (as built today)

- **Levels 1–3:** 3 enemies.
- **Levels 4–6:** 4 enemies.
- **Ceiling-drop levels:** levels 7, 24, 40, 57, 73 and 90 have 5 enemies, 4 of them falling in from above.
- **Every other level:** 3 enemies.
- **Enemy difficulty by world (2026-10-22):** every High Score enemy, in 1P, 2P co-op and 2P versus, uses its world's value: 1.0 in world 1, then 1.2, 1.4, 1.6, 1.8 and 2.0 in world 6.
- **Lava:** replaces water on levels 84–99.
- **Powerup odds:** Burrito and Green Burrito are 25% more likely in levels 1–15, which is the demo's range.
- **As built, enemy count does not ramp across levels 8–99, and difficulty steps only once per world.** This is the board's top finding and it is now a planned deliverable with a mechanism: enemy count and the per-level difficulty number move out of the level files into one tuning table. The table is produced by the Difficulty Tuner agent (Section 16) from the per-run event logs of itch.io playtests, and nothing in it ships without a human playtest. The first target curve: 3 enemies at 1.0 through level 12, then +1 enemy every 25 levels and +0.05 difficulty every 10 levels, so that level 99 runs 6 enemies at about 1.5 and level 200 runs 10 enemies at about 2.0, with the lava world (levels 185–200) as the finale. Those numbers are a starting point for the first playtest round, not a promise.
- **The run has an end.** The demo ends on the end card after Bonus Round 33 (level 99). The full game ends the same way after level 200's bonus round, with a VICTORY card. Players who want no end play Endless (Section 5).

## 7. Characters

- **Players:** 10 character skins plus RANDOM. A RANDOM pick rolls once and stays the same for the whole run.
- **More playable characters (planned, 2026-10-21):** feedback on the build asked for more. New characters come from the Character Artist agent (Section 16). Each one is a body sprite, its 12 death-flail frames and a Character Select tile, made to the house sprite standard so hats, shades, cheek sets and poo stains sit on it like the original ten. Skins are discovered at runtime, so a finished character drops in. How many: 80 more, in eight sets of ten made one set at a time, for 90 in all (Section 21.1).
- **Enemies:** 10 AI character variants. They fly, fart, drown and bounce off the ceiling under the same rules as players.
- **Character Select** comes before every mode, with one cursor per player: skin, hat, shades and hat colors, then READY.
- **Wearables today:** a santa hat and a turkey hat; black shades and silver aviators; 10 color swatches per hat region plus the art's default colors. Hats get dirty from poo too.
- **Character animation (2026-10-31):** arms flap with open palms on every normal fart, one full flap as fast as the button repeats; a corked fart flaps nothing. A character standing still on the ground breathes, players and enemies alike: the body rises and settles and the cheeks swell a little. The breath also plays on Character Select and in the dressing room. Replays show both; replays saved before the idle have no breath. Each new sprite gets its flap and breath frames from the same tools as the original ten, made from its own pixels.
- **Settings option:** "AI Wear Hats" puts random hats on enemies.
- **Cheek sets (2026-10-18):** every character rolls one of four cheek sets each life, players and enemies alike: smooth (glossy skin), zits (razor burn: stubble, follicle-sized whiteheads, ingrown hairs, blackheads), scarred (stitched scar, bruise, crossed band-aids) and hairy (realistic hair of mixed lengths). All four keep the original disc, 5 px outline and skin tone. The menus roll them too. Replays show each life's own set; replays saved before the sets keep the original hairy cheeks.

## 8. Enemy AI

- A state machine: Flying, Diving, Stunned, Idle.
- One difficulty value controls how aggressive and capable an enemy is. High Score uses its world's value, 1.0 in world 1 up to 2.0 in world 6 in steps of 0.2; Survival uses 1.4, 1.8 and 2.2 by tier; Gauntlet climbs 0.1 per wave without a limit.
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

- **Main menu:** a wrapping menu wheel (keys, stick, mouse and touch) with the Steam leaderboard on screen. A Tingle Games intro sting plays once per launch; since 2026-10-28 a whispered "Tingle" plays 4 seconds into it.
- **Menu background:** a random level's 3D backdrop, a field of characters and pickups flying across the screen and striking on the beat of the menu music, the title dancing letter by letter, and every 25 to 60 seconds a bat splat with one of the ten characters' faces. Since 2026-10-21 every flying character wears a random hat, sunglasses or both, in the items' own colors.
- **Menu pages:** Replays, Stats (lifetime totals), Scoring (the points table), Settings (audio, remapping, announcer voice, colorblind mode, AI Wear Hats; also used as the pause menu), Credits.
- **Colorblind mode (2026-10-18):** Off, Protanopia, Deuteranopia or Tritanopia, ported from Tingle Solitaire. One daltonization filter over the whole finished picture (every menu, the HUD and gameplay), not per-item color swaps. Checked by colorblindness simulation: the red/green problems are fixed (player vs enemy glow under deuteranopia 24.6 -> 69.3 deltaE; burrito vs green burrito under protanopia 3.9 -> 21.2); a few pairs come closer and are accepted (poo on the pale bone ground; the Quadra and Penta badges under tritanopia, which also differ in words). Share clips stay in normal colors.
- **Version (2026-10-18):** the build's version shows in the main menu corner and at the foot of Settings, e.g. "v0.9.0 demo - itch - 2026-10-18 5e6f142", and is recorded in Player.log and every replay.
- **HUD:** each player's run total and underwear life icons, a timer with the Bottom Busters logo on either side, the level number top right, and wave and difficulty % in Survival and Gauntlet. Every HUD text sits on a dark box so it reads on any backdrop.
- **End of run:** a 10-second wind-down, then the result card. GAME OVER (with a sad trombone-style sting) or VICTORY, the final total and best, a roast line, and rotating superlatives such as Methane Released, Held It In, Full Coverage and Died Dirty.
- **Announcer:** three pre-recorded voices, named in Settings as Mr. Announcer (the default), Drill Sergeant and Scottish. They read roast lines, wave callouts 1–50 and uzi kill streaks. Players can turn the announcer off.

## 13. Replays, sharing and leaderboards

- **Replays:** every run is recorded as a 1:1 copy of what was on screen, including poo, splats, sounds and the HUD. Players save runs to a library and can Watch, Rename, Delete or Share them. Library rows show live previews of the replay.
- **Every mode records (as of 2026-10-15, format v12).** High Score and Survival as before. Gauntlet saves the whole run, with the late-spawning wave enemies and the WAVE banners recorded. Burrito Arena, which never ends in 1P and co-op, keeps a rolling window: the recorder holds at most the last 90 seconds, SAVE REPLAY in the pause menu writes the last 60 seconds as a snapshot and the session keeps recording, and the versus winner card saves the last 60 seconds of the match. The button's hover text says "Saves the last 60 seconds." Older replays still load.
- **Share clip:** a 25- to 60-second video (a CLIP LENGTH chooser in 5-second steps, capped at the replay's length; arena and Gauntlet clips default to 60 seconds; a replay longer than 60 seconds can also be saved whole, as one more stop past 60, since 2026-10-21), rendered in-game in one of two shapes, picked on a PHONE | 16:9 switch above the length slider (2026-10-18; the last pick is remembered): PHONE is 9:16 for TikTok, Shorts and Reels, where the camera follows the action and zooms in around fights; 16:9 is the whole screen exactly as Watch shows it, HUD included, for YouTube, Discord and Steam. Players save it through a Save As dialog. The encoder is a bundled LGPL FFmpeg build that uses the computer's own GPU encoder. Once a save lands, the Share screen adds "Saved! Posting it? Tag @bottombusters on Instagram." (2026-10-21; the game's own account since 2026-10-28).
- **Clip pages (built 2026-10-23, itch demo):** when a run makes a board's top 3, the game records its clip on screen the next time the main menu opens (9:16, then 16:9; skippable, and still available from the board while the run stays in the top 3) and uploads it. Each clip gets its own public, anonymous page at tinglegames.com/c/..., rated with 1 to 5 pairs of underwear, with the run's rank history, a Share button and follow buttons. A clip page stays up after its run leaves the top 3.
- **Leaderboards:** Steam boards with Global and Friends tabs, a 1P/2P toggle, and High Score, Survival and Gauntlet, the last two each split into Highest Wave and Most Points (Gauntlet since 2026-10-18). The top 3 entries carry a replay anyone can watch in-game, with Steam names shown over the characters.
- **Anti-cheat:** for Steam, planned: a server checks each run before posting it to trusted boards, which waits on the game's own Steam App ID. For the itch web leaderboard, built 2026-10-25 and live since 2026-10-28: the game sends a summary of the whole run (points paid, awards, flaps, enemies spawned and defeated, deaths, lives, and every hit on a player and how it ended), and the server refuses old versions, banned accounts, repeated runs and floods, and holds runs whose numbers don't agree with themselves for review in the developer dashboard's Run check tab (not on the website), where entries can also be removed and players banned. It shipped with version 0.9.1; older versions can no longer post scores. A run only counts once it ends (a game over, the last level cleared, a Survival win), and since 2026-10-28 quitting a run that would be dropped says so: THIS RUN WON'T COUNT ON THE LEADERBOARDS.
- **itch web leaderboard (designed 2026-10-21, live 2026-10-23):** a page at tinglegames.com/bottom-busters/leaderboard that is the main menu without its menus (the same backdrops, flying characters, dancing title, DEMO stamp, music, beat strikes and bat splats) around one large, scrollable board headed ITCH.IO LEADERBOARD, with a PLAY ON ITCH.IO button to the game's itch page. The game uploads each finished run; only players signed in with an itch account are listed, and a 2P run shows both names, with a seat that was not signed in shown as Player 1 or Player 2 (2P Character Select asks the second player to sign in). Boards match the game's: High Score 1P and 2P with the level reached, Survival and Gauntlet each split into Highest Wave and Most Points; top 10 shown, and each top-3 run links to its own clip page. Those clips are the last 60 seconds for Survival and Gauntlet; for High Score, the last level played, death included, cut to its last 60 seconds when it ran longer (2026-10-23, the same rule as the Steam top-3 replays). The page also has a LONGEST ON THE BOARD view, and the site has a privacy policy at tinglegames.com/privacy.
- **Online 2P on itch (2026-10-24):** through Parsec, which is free: the host runs the game and the guest plays Player 2 with their own controller over the stream. The itch build's 1P/2P chooser points to a how-to page at tinglegames.com/bottom-busters/play-online/. With a keyboard host and one controller connected, that controller becomes Player 2's. Decision 2026-10-25: online 2P for the demo stays Parsec only.

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
- The roast lines come from a pre-written line bank, never generated live. This keeps the cost to $0 per player, works offline, and keeps Steam's disclosure to the pre-generated-content checkbox. The roast lines are due for a rework. As of 2026-10-22 the bank has 40 lines, reviewed on the dashboard's Roast Review page. They are picked by the run's events again: the card's most interesting stat that has a line for the win or loss, else one of the 11 general lines. After an Enemies Defeated roast, the next 3 rounds roast something else. The 24 lines about poo, toilets or smell never play in Gauntlet.
- The announcer voices are text-to-speech recorded ahead of time (ElevenLabs), shipped as audio files. Steam's AI-disclosure rules treat that as pre-generated content.

**For this course: a development-time agent crew.** Two kinds of AI exist in this project and they never mix. The shipped game's only AI is the enemy state machine above plus pre-recorded voices and pre-written text. The crew below runs at development time on the project's own files, and its output is ordinary game data the game already discovers at runtime: level files, a tuning table, text, sprites and test reports. No agent runs on a player's machine and no API key ships in the build. Each agent has one job and one output, no two write the same file, and the handoff between them is a file in the repository. A human playtest is the last gate for all of it.

| Agent | Development role | What the player sees because of it |
|---|---|---|
| Level Architect | Writes new single-screen level files (ground gaps, platforms, spawn points, ceiling-drop markers, theme) that obey the rules in Section 6.1. | Levels 100 to 200 and the Endless mode's layouts. |
| Difficulty Tuner | Reads the per-run event log from playtests and proposes enemy count and the difficulty number for each level and each Endless step. | The curve in Section 6.3 actually climbing after level 8. |
| Roast Writer | Rewrites the roast line bank and superlatives, tagged to the run events that trigger them. | A GAME OVER card that roasts what you actually did, from text shipped inside the game. |
| Wardrobe Stylist | Produces hat and shades sprites and backdrop picks that pass the house sprite standard. | More hats and shades on Character Select; more unique backdrops for the new levels. |
| Character Artist | Makes new playable characters: the body sprite, its 12 death-flail frames and a Character Select tile, to the house sprite standard, so hats, shades, cheek sets and poo stains sit on it like the original ten. | More characters to pick on Character Select, which feedback on the build asked for. |
| QA Playtester | Loads every new level in a headless Unity build and checks that each enemy is reachable, no spawn is over water, and the level can be cleared. | No unwinnable or empty level reaches the demo. |
| Builder | Reads this GDD and the project's coding rules and implements one approved feature at a time in C#, then runs the existing build-and-verify loop. | The Endless mode, the Custom Game screen behind the teaser, and the loaders the other agents' output needs. |

Semester token budget, as a cap: about 5.0 million tokens, of which the Builder is 3 million (six feature slices at about 500,000 each) and the six content agents share the rest.

**Control agents (built 2026-10-30, for Assignment #3):** three agents over the crew, running on the local cluster. The **Orchestrator** takes the first card it has a maker for from the top of the Trello board (Backlog, In Progress, Review, Your Playtest, Done), splits it into tasks, gives it to one agent at a time, and moves finished work to Review. The **Critic** reviews agent output for what the player will see, after the **Bridge**, a script with no AI in it, checks the format. The **Technical Writer** writes the run's summary, keeps the crew's memory short, and closes and archives a card once all of its work is approved. Two failures stop an agent, and the run says why. Nothing goes into the project until the Studio Director approves it, and the Studio Director still plays every build and says commit. The first crew run made two new characters through the Character Artist: new hair and skin tone on the shared body, flail and splat art made by the same tools as the original ten. The crew diagram is `crew.mmd` in the crew's folder, and the earlier picture is `BBUST_agent_crew.png` beside this document. The budget and the per-agent file boundaries are in the short-form GDD.

**Development tooling (2026-10-21).** A local model cluster, the development PC and six Macs behind one router (MindRouter), is available for crew work that doesn't need Claude, and each agent has its own key there, so the tokens it runs locally are counted per agent instead of against the budget above. A development dashboard tracks the crew's cards and token use, and gives the Studio Director one place to approve or reject new characters, hats and levels, tune every sound's volume, review the roast lines and the events that trigger them, and pick the store screenshots. None of it ships with the game.

## 17. Technical summary

- Unity 6.3 LTS, URP, the new Input System, Box2D physics.
- Steam integration through Facepunch.Steamworks: leaderboards, Workshop-hosted replay files, friends.
- Replays are recordings, not deterministic re-simulations, so balance patches never break saved replays.
- One event log per run feeds three things: stats, replay playback and score checking.
- Levels, player skins and AI variants are discovered at runtime, never hardcoded, so new content drops in.
- **One project, two build targets.** The Steam build and the itch.io build come from the same tree, scenes and assets. The itch target turns off the Steam define and leaves the two Steam DLLs out, asserts that no Steam file or debug symbol is in the output, and zips. There is nothing to keep in sync between the two stores because there is one source.
- **Demo builds and full-game test builds (2026-10-18).** Each build command makes two players per store: the demo players download, which saves no diagnostic files on their machines, and a full-game test copy that runs past the demo's end and keeps every diagnostic log, for development only.
- Development so far is about 432 logged hours, counted as a minimum.

## 18. Scope: demo and full game

**Demo (built, 2026-10-15), identical on itch.io and Steam:**
- All 99 built levels, ending as a win on the end card after Bonus Round 33.
- Every mode and 2P are included. Custom Game is present as a teaser (Section 5).
- The end card reads: "THAT'S THE DEMO. You played 99 levels. The full game has 200. Plus more characters, more music, more sounds, more powerups, and custom games you build yourself." Its first button is WISHLIST ON STEAM in the Steam build and FOLLOW ON ITCH (the game's itch page) in the itch build (2026-10-18).
- The developer level-skip buttons were taken out for the demo release (2026-10-18), put back while the levels were being worked on (2026-10-19), and taken out of every build again on 2026-10-23.
- The demo says so (2026-10-18): its exe is "Bottom Busters Demo.exe" and the main menu shows a red DEMO stamp across the bottom corner of BUSTERS. The itch demo is uploaded with butler to the itch page's windows-demo channel (version 0.9.3 since 2026-10-31), so updates patch only what changed.
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

## 19. Business and release

- Publisher: Tingle Games LLC (Texas). Steamworks approval is in its identity-verification step.
- The Steam build contains no sweepstakes, donation button or crypto.
- **Release intent: itch.io first, then Steam, same build.** itch.io is the proving ground: the 99-level demo goes up first as a Draft or password-restricted page for the class and a small group of testers, then public. It is where the curve, the run length, the end card and the agent-made content get played by strangers before anything is promised on a store page that sells, and it is the source of the playtest telemetry the Difficulty Tuner needs. Builds push through itch's butler tool. Steam is the commercial release and carries the account-backed features: global and friends leaderboards with watchable replays, Remote Play Together, Workshop replays.
- **Timeline:**
  - itch.io demo: public since 2026-10-28, version 0.9.3 since 2026-10-31, with devlogs posted for 0.9.2 and 0.9.3.
  - Steam demo in November 2026, once the App ID exists.
  - Steam Next Fest, Feb 22 – Mar 1, 2027, plus the Couch Co-Op Fest, Feb 8–15, 2027.
  - Launch in March or April 2027.
- **Price:** demo free on both stores; full game $9.99 on both, with a 10–15% launch discount. itch stays at price parity with Steam because Steam's terms require it. Level count does not move the price; the Endless mode is the retention feature that lets the price hold through sales.
- Remote Play Together lets one owner play with a friend online. Steam turns it on for games listed as local co-op, and it also qualifies the game for the Couch Co-Op Fest.
- **Marketing:** daily vertical clips from the game's own clip exporter, posted to YouTube Shorts, TikTok and Instagram Reels, with a wishlist link on every post. Since 2026-10-28 the game has its own YouTube channel (Bottom Busters, with a 30-second trailer as its channel trailer, also on the itch page) and Instagram account (@bottombusters, with the trailer as its first post, a collab with @tingle.games).
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

## 21. Content guide

Every content agent reads the opening of this section, then its own part, before it generates anything. Rulings carry the Studio Director's name and date.

**The game, for every agent.** Bottom Busters is a comedy arcade game. Every character is a chubby man in white briefs who floats like a balloon and flies by farting. A character's health is two cheeks, and lives are white underwear icons. The humor is gross-out and physical. Poo piles up and dirties bodies, cheeks and hats, and the base coat never washes off. Other humor-first visuals include cheek "health" and the chef animals in the bonus rounds. Everything new has to read at game size and sit beside what's already in the game. Nothing is copied from real people, brands, logos, or characters from other games or shows.

### 21.1 Characters (Character Artist)

**What it is.** A new playable character with the same chubby body and white briefs as everyone else. Only the skin tone, face and hair change (Studio Director, 2026-10-31: "same chubby body and white briefs, change skin tone, faces and hair"). Each one comes with the body sprite, 12 death-flail frames, 3 idle frames, 8 flying-arm frames and a splat pair. The animations are made by the same tools as the original ten, never drawn by a model.

**Reading at game size.**
- A character is about 100 pixels tall in play.
- Players tell characters apart by the shape and color of the hair first, and the face second.
- Hair uses bold silhouettes. Never green hair.
- A new character can't be mistakable for anyone already on the roster.

**The face.**
- Every face gets the same cartoon treatment, with no exaggerated features.
- That means two eyes with whites and dark pupils, eyebrows, a nose and a mouth.
- A character gets its own face from the shape of its brows, the size of its eyes and its expression.
- No hats, glasses, masks or held objects. Players pick hats and shades at Character Select.

**Names.**
- Every character has one real first name.
- The original ten (Studio Director, 2026-11-01): Larry, Doug, Norm, Greg, Carl, Steve, Barry, Terry, Kevin and Phil.

**The roster today.**

| Name | Look |
|---|---|
| Larry | Balding with dark hair on one side, no beard |
| Doug | Shaggy brown hair, round glasses, big dark brown beard |
| Norm | Gray side-parted hair, balding, no beard |
| Greg | Long wavy brown hair to the shoulders, small goatee |
| Carl | Long brown hair to the shoulders, black bandit mask, dark goatee |
| Steve | Short black hair, glasses, no beard |
| Barry | Dark red swept hair, round glasses, big dark beard |
| Terry | Curly black hair, full black beard |
| Kevin | Short curly ginger-brown hair, black bandit mask |
| Phil | Short curly ginger-brown hair, no mask, no beard |

**Sets.**
- 80 new characters, for 90 in all (Studio Director, 2026-11-07).
- They come in sets of ten, one set at a time (Studio Director, 2026-11-03).
- The set order: African American, East Asian, Southeast Asian, Pacific Islander, Hispanic, Indian, Middle Eastern/North African, Native American/Indigenous.
- Each set has its own skin tones and hair notes.
- The game shows no ethnicity information, just a list of characters with first names.

**The not-offensive line.**
- Names are "comically stereotypical but not offensive" (Studio Director): the most classic name you'd really hear for the set.
- No jokes about accents or the group, no nicknames or titles, and no word that names the group.
- No ethnic or religious caricature, and no feathers, headdresses or face paint.
- The Studio Director approves every name.

**Failure.**
- A character that can be mistaken for one on the roster at game size.
- A name that's already taken, is a joke, or names the group.
- Any exaggerated feature or caricature.

### 21.2 Roast lines (Roast Writer)

**What it is.** The line the narrator reads on the end card, tied to what the player just did. Lines are written ahead of time and ship as text, never generated live. The 40 lines the Studio Director kept are the voice to match. This is the roast line spec Section 20 asks for (Studio Director, 2026-11-04: "thats right").

**The voice.**
- Short: one to three sentences, 15 words at most.
- A flat verdict, then a turn.
- A deadpan, formal narrator who treats something gross like an official matter.
- The gross thing is never named. It's "it," a smell, a plumber, a bad curry, never "poop" or "fart."
- Backhanded praise on a win, meaner on a loss.
- Threes work.
- Periods only, with at most one word in capitals for stress.
- No pop culture.

**Who it talks to.**
- "You": the player whose card it is, about the exact thing the card shows.
- In 2P each player has their own card, so "you" is always one player.
- No names, and nothing about the player's body, race, age or looks, so a line fits any character.

**Events.**
- Lines are tied to the 11 events the kept lines use: General, Methane Released, Enemies Defeated, Lifeguard Off Duty, Bombs On Target, Direct Deposit, In One Sitting, Longest Streak Of Poo, Received, Full Coverage and Died Dirty.
- The seven splat events never play in Gauntlet.
- Any line about poo, toilets or smell is kept out of Gauntlet too.

**Kept lines, quoted exactly.**
- "Dead. Even the enemies looked away out of respect." (loss)
- "Victory. Somewhere, a plumber felt a disturbance." (win)
- "Efficient. Brutal. Faintly upsetting." (Enemies Defeated, win)
- "That is a LOT of propulsion for someone going nowhere." (Methane Released, loss)
- "Precision bombing. Genuinely disgusting. Well done." (Direct Deposit, win)
- "Covered in it AND dead. A comprehensive defeat." (Died Dirty, loss)

**Failure.**
- A line that passes every rule and still isn't funny.
- A line that explains the joke or leans on a pun alone.
- A line that's random, with no tie to the event.
- A line that names the gross thing.
- A line about a character's body or looks.
- The same shape over and over.

### 21.3 Hats and shades (Wardrobe Stylist)

**What it is.** Wearables players put on at Character Select. The game has four today: the Santa hat, the turkey hat, black shades and silver aviators. Each item is drawn by code from flat shapes, the same way those four were (Studio Director, 2026-11-04).

**Style.**
- Pixel art on the characters' own grid.
- A thick dark outline all the way round.
- Flat fills, with no shading or gradients.
- It has to look like it belongs with the four already in the game.

**Color.**
- A hat has one to three color areas that players recolor at Character Select.
- Shades take no colors.

**Fit.**
- Every character faces right, so a hat leans or flops left, toward the back of the head.
- A hat's bottom edge is its brim, and it sits on the head.
- Shades have two lenses, one on each eye, with a bridge between them.
- Every item has to sit right on every character.

**Failure.**
- An item that doesn't read as what it is at game size, or reads as a blob.
- Off-style art.
- A hat that floats above the head, or shades that miss the eyes.
- Real logos, brands or team names.

### 21.4 Backgrounds (Level Architect)

**What it is.** The layered parallax backdrop behind a single-screen level. Every level has its own, and no backdrop is used twice. New ones are made by the crew, with no bought art (Studio Director, 2026-11-03). Each one is a recipe: a palette, plus layers stacked back to front.
- A solid sky made by code.
- A soft haze band made by code.
- Object layers, one kind of object per layer, with each object painted whole, one at a time.
- Every layer is 576 by 324 and loops sideways as it drifts.

**Themes and taste.**
- The game's terrain themes are blue stone, green sludge, pale bone, ice, charred ember and red crimson, with the red lava world last.
- The six all-water levels use only sky or moon backdrops.
- A new idea can't repeat any of the 99 backdrops in the game.
- The Studio Director liked the violets of the first test, a giant mushroom forest at dusk.

**Failure** (Studio Director, 2026-11-04):
- Any visible seam or vertical line while a layer moves.
- An object split across layers.
- Holes inside objects.
- Key color left behind.
- Anything but sky on the sky layer.
- Copying flaws from the bought originals.
