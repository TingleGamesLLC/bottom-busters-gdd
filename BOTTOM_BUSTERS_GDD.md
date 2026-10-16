# Bottom Busters — Game Design Document

First draft, for Assignment #1 (GDD First Draft, due Tue 10/20), Multi-Agent AI for Game Development, ELVTR.
Studio: Tingle Games LLC. Draft date: 2026-10-08.

Status of this draft: the facts below come from the project's own docs (`CLAUDE.md`, the plan files and the session log in `C:\bbust\BBUST`). Lines marked **[DRAFT]** are proposed wording to confirm or change. The course template is handed out in class 02 (10/13); this draft follows a standard GDD structure so it can be moved into that template.

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
4. **Every run is a clip.** Every run is recorded 1:1, saved to a library, and can be exported as a 25-second vertical video to share.
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
- **Death:** with both cheeks gone the character deflates and flies off on a 5-second death flight.
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
| **Gauntlet** | 1v1 or 2v2 against AI | No powerups. The AI gets 10% tougher every wave, with no cap. One life per player; an eliminated player returns when their partner clears the wave. Every wave fully resets both sides, cheeks included. Ranked by wave. |
| **Bonus Round** | inside High Score | Four chef animals flip food straight up; catch it for 500 points each (20 pieces in 1P, 40 in 2P). Nobody can die. When the round ends, the chefs' hats become trampolines until the player continues. |
| **Custom Game** | teaser | A fully interactive menu mockup with no gameplay behind it yet. Custom games are promised for the full game. |

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
- **[DRAFT]** Enemy count and difficulty do not ramp yet across levels 8–99. A planned curve for the full 200 belongs here.

## 7. Characters

- **Players:** 10 character skins plus RANDOM. A RANDOM pick rolls once and stays the same for the whole run.
- **Enemies:** 10 AI character variants. They fly, fart, drown and bounce off the ceiling under the same rules as players.
- **Character Select** comes before every mode, with one cursor per player: skin, hat, shades and hat colors, then READY.
- **Wearables today:** a santa hat and a turkey hat; black shades and silver aviators; 10 color swatches per hat region plus the art's default colors. Hats get dirty from poo too.
- **Settings option:** "AI Wear Hats" puts random hats on enemies.

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

## 12. Feedback, UI and presentation

- **Main menu:** a wrapping menu wheel (keys, stick, mouse and touch) with the Steam leaderboard on screen. A Tingle Games intro sting plays once per launch.
- **Menu pages:** Replays, Stats (lifetime totals), Scoring (the points table), Settings (audio, remapping, announcer voice, AI Wear Hats; also used as the pause menu), Credits.
- **HUD:** each player's run total and underwear life icons, a timer with the Bottom Busters logo on either side, the level number top right, and wave and difficulty % in Survival and Gauntlet. Every HUD text sits on a dark box so it reads on any backdrop.
- **End of run:** a 10-second wind-down, then the result card. GAME OVER (with a sad trombone-style sting) or VICTORY, the final total and best, a roast line, and rotating superlatives such as Methane Released, Held It In, Full Coverage and Died Dirty.
- **Announcer:** three pre-recorded voices (Grant is the default; also a drill sergeant and a Scottish voice). They read roast lines, wave callouts 1–50 and uzi kill streaks. Players can turn the announcer off.

## 13. Replays, sharing and leaderboards

- **Replays:** every run is recorded as a 1:1 copy of what was on screen, including poo, splats, sounds and the HUD. Players save runs to a library and can Watch, Rename, Delete or Share them. Library rows show live previews of the replay.
- **Share clip:** a 25-second video, 9:16 for TikTok, Shorts and Reels, rendered in-game. The camera follows the action and zooms in around fights. Players save it through a Save As dialog. The encoder is a bundled LGPL FFmpeg build that uses the computer's own GPU encoder.
- **Clip pages (planned, not built):** each shared clip gets its own public, anonymous page on tinglegames.com, rated in pairs of white underwear.
- **Leaderboards:** Steam boards with Global and Friends tabs, a 1P/2P toggle, and High Score, Survival (Highest Wave and Most Points) and Gauntlet (by wave). The top 3 entries carry a replay anyone can watch in-game, with Steam names shown over the characters.
- **Anti-cheat (planned):** a server checks each run before posting it to trusted boards. This waits on the game's own Steam App ID.

## 14. Art direction

- 2D sprite characters over layered 3D parallax backdrops, one per level.
- Terrain is 32-pixel tile art with point filtering, drawn large on screen.
- Gameplay has a light post-processing grade: bloom, slight contrast and saturation, and a soft vignette.
- The splat effect is one flat brown (RGB 117, 74, 40) with no shading.
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
- The roast lines come from a pre-written line bank, never generated live. This keeps the cost to $0 per player, works offline, and keeps Steam's disclosure to the pre-generated-content checkbox. The roast lines are due for a rework.
- The announcer voices are text-to-speech recorded ahead of time (ElevenLabs), shipped as audio files. Steam's AI-disclosure rules treat that as pre-generated content.

**[DRAFT] For this course:** later assignments build an agent crew, a RAG content pipeline, a GDD-reading coding agent, a style guide agent and QA/balance agents around this game. Which parts of Bottom Busters they target goes here once the template's AI sections are known.

## 17. Technical summary

- Unity 6.3 LTS, URP, the new Input System, Box2D physics.
- Steam integration through Facepunch.Steamworks: leaderboards, Workshop-hosted replay files, friends.
- Replays are recordings, not deterministic re-simulations, so balance patches never break saved replays.
- One event log per run feeds three things: stats, replay playback and score checking.
- Levels, player skins and AI variants are discovered at runtime, never hardcoded, so new content drops in.
- Development so far is about 374 logged hours, counted as a minimum.

## 18. Scope: demo and full game

**Steam demo (built):**
- 15 levels, ending after Bonus Round 5.
- Burrito Arena and 2P are included.
- The end card reads: "THAT'S THE DEMO. You played 15 levels. The full game has 200. Plus more characters, more music, more sounds, more powerups, and custom games you build yourself. Wishlist Bottom Busters on Steam."

**Full game:**
- 200 levels.
- More characters, music, sounds and powerups.
- A custom game builder.

**Planned later:**
- A Hats 'n Shades store (real money).
- Seasonal and collectible hats.
- Steam Workshop hats.
- Steam Cloud sync of owned items.
- Achievements (a list of about 60 has been drafted).
- Remote Play Together for online 2P.

## 19. Business and release [DRAFT]

- Publisher: Tingle Games LLC (Texas). Steamworks approval is pending.
- The Steam build contains no sweepstakes, donation button or crypto.
- **Proposed timeline:**
  - Demo in November 2026.
  - Steam Next Fest, Feb 22 – Mar 1, 2027, plus the Couch Co-Op Fest, Feb 8–15, 2027.
  - Launch in March or April 2027.
- Remote Play Together lets one owner play with a friend online. Steam turns it on for games listed as local co-op, and it also qualifies the game for the Couch Co-Op Fest.
- **Marketing:** daily vertical clips from the game's own clip exporter, posted to YouTube Shorts, TikTok and Instagram Reels, with a wishlist link on every post.
- **Localization:** store pages first, starting with Simplified Chinese. The game has very little text to translate.
- The price is not set yet.

## 20. Risks and open questions

- **Steam App ID:** online play, trusted leaderboards and Workshop features wait on Steamworks approval.
- **Difficulty curve:** levels 8–99 mostly repeat the same enemy setup (section 6.3).
- **Level variety:** single-screen levels on a fixed ground strip and three platform heights can look alike across 200 levels. Layout concepts to break that up are written in `LEVEL_DESIGN_CONCEPTS.md` and not yet decided.
- **Remote Play latency:** remote play is video streamed, and the added delay may hurt flap timing. Not yet tested.
- **Music and audio rights:** need to be cleared before clips and streams are promoted.
- **Roast lines:** need a rework before they appear on clip pages or in marketing.
- **Fill in:** pitch, pillars and audience wording, price, and the course template's AI-specific sections.
