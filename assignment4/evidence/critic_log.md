# What the Critic did, run by run

Compiled from each run's `run.json` (C:\cluster\crew\runs) by `critic_tally.py`. Runs on 2026-11-07 and 2026-11-08, Assignment #4.

| Run | Designs checked | Passed | Sent back | Roast lines checked | Lines sent back | How the run ended |
|---|---|---|---|---|---|---|
| 20261107-155047-character-artist | 1 | 0 | 1 | 0 | 0 | stopped: character-artist lost both cheeks on t1: the GDD check failed twice: The characte |
| 20261107-155047-level-architect | 0 | 0 | 0 | 0 | 0 | stopped: level-architect lost both cheeks on t1: the recipe failed its checks twice: Make  |
| 20261107-155047-roast-writer | 0 | 0 | 0 | 18 | 10 | waiting on David |
| 20261107-155047-wardrobe-stylist | 2 | 0 | 2 | 0 | 0 | stopped: wardrobe-stylist lost both cheeks on t1: the GDD check failed twice: The top hat  |
| 20261107-163826-character-artist | 1 | 1 | 0 | 0 | 0 | stopped: character-artist lost both cheeks on t1: the first name Marvin is already on the  |
| 20261107-163826-roast-writer | 0 | 0 | 0 | 0 | 0 | stopped: critic gave malformed output twice (missing fields ['lines']) |
| 20261107-163826-wardrobe-stylist | 2 | 2 | 0 | 0 | 0 | stopped: wardrobe-stylist lost both cheeks on t2: the hat doesn't reach the bottom of its  |
| 20261107-163827-level-architect | 2 | 2 | 0 | 0 | 0 | stopped: level-architect lost both cheeks on t1: Fill the hole inside the object at x 280  |
| 20261107-164801-character-artist | 2 | 1 | 1 | 0 | 0 | stopped: character-artist lost both cheeks on t1: the Critic sent it back against the GDD: |
| 20261107-164801-level-architect | 1 | 1 | 0 | 0 | 0 | waiting on David |
| 20261107-164801-roast-writer | 0 | 0 | 0 | 53 | 0 | stopped: MindRouter answered HTTP 429 for roast-writer: {"detail":"Token quota exceeded"} |
| 20261107-164801-wardrobe-stylist | 2 | 2 | 0 | 0 | 0 | stopped: wardrobe-stylist lost both cheeks on t1: the name Top Hat is taken |
| 20261107-165733-character-artist | 1 | 1 | 0 | 0 | 0 | stopped: PixelLab's job failed: {'code': 5000, 'type': 'message_progress', 'error': "Gener |
| 20261107-165733-roast-writer | 0 | 0 | 0 | 69 | 6 | waiting on David |
| 20261107-165733-wardrobe-stylist | 1 | 1 | 0 | 0 | 0 | waiting on David |
| 20261107-170123-character-artist | 5 | 5 | 0 | 0 | 0 | stopped: character-artist lost both cheeks on t4: the first name Marvin is already on the  |
| 20261107-170737-character-artist | 2 | 2 | 0 | 0 | 0 | stopped: character-artist lost both cheeks on t1: Make the face look less like player11's: |
| 20261107-170937-character-artist | 2 | 2 | 0 | 0 | 0 | stopped: character-artist lost both cheeks on t1: Make the face look less like player12's: |
| 20261107-171426-character-artist | 2 | 1 | 1 | 0 | 0 | stopped: character-artist lost both cheeks on t1: Make the face look less like player11's: |
| 20261107-171522-character-artist | 6 | 6 | 0 | 0 | 0 | waiting on David |
| 20261108-213543-character-artist | 9 | 8 | 1 | 0 | 0 | stopped: character-artist lost both cheeks on t7: the Critic sent it back against the GDD: |
| 20261108-214330-character-artist | 2 | 1 | 1 | 0 | 0 | stopped: character-artist lost both cheeks on t1: the Critic sent it back against the GDD: |
| 20261108-214431-character-artist | 2 | 1 | 1 | 0 | 0 | stopped: character-artist lost both cheeks on t1: the Critic sent it back against the GDD: |
| 20261108-214537-character-artist | 2 | 2 | 0 | 0 | 0 | stopped: character-artist reached its cap of 30000 tokens for this run |
| 20261108-214743-character-artist | 1 | 1 | 0 | 0 | 0 | stopped: character-artist lost both cheeks on t1: 'slanted' is against the rules for this  |
| 20261108-214852-character-artist | 1 | 1 | 0 | 0 | 0 | waiting on David |

## Findings plain code or the second look threw out

Counted from run 20261107-163826 on, after the fix (the first run had no filter beyond the quoted rule).

| Why it was dropped | Findings |
|---|---|
| a maybe, not a break | 88 |
| it blames words the rule allows: only a banned word names the gross thing, and the Bridge checks those | 16 |
| the second look found no break | 15 |
| its rule is about how the finished art looks, which is checked on the picture after it's made | 4 |
| it quotes a sentence that describes the game today, not a rule for new work | 3 |

## Every send-back against the GDD

- **20261107-155047-character-artist**, design t1: The character has a full, neatly trimmed beard, which is not explicitly prohibited, but combined with the afro and facial features, it may create a caricature that borders on stereotypical representation, violating the 'no caricature' rule in spirit, though not in letter. (GDD: "No hats, glasses, masks or held objects. Players pick hats and shades at Character Select."); The combination of a tight, coiled afro with slight asymmetry and a full, neatly trimmed beard closely resembles existing characters like Carl and Terry, who also have full beards and distinct hairstyles, making it potentially mistakable at game size. (GDD: "A character can't be mistakable for anyone already on the roster.")
- **20261107-155047-roast-writer**, roast line "The lifeguard is off duty. So are you.": The line 'The lifeguard is off duty. So are you.' implies a failure tied to bodily function or shame, but more critically, it breaks the rule by being a weak, non-specific joke that doesn't tie to the event with the required tone or structure. It lacks the deadpan, formal delivery and the turn after a flat verdict. It also fails to reference the event meaningfully—'off duty' is repeated without consequence, and it doesn't treat the situation as an official matter. It’s a cliché with no gross-out or physical humor, and it doesn’t fit the voice of the narrator as defined in the GDD. (GDD: "The gross thing is never named. It's 'it,' a smell, a plumber, a bad curry, never 'poop' or 'fart.'")
- **20261107-155047-roast-writer**, roast line "Ten in a row. The level is now a monument.": The line references 'Ten in a row' which implies a named gross thing (poop), breaking the rule against naming the gross thing. (GDD: "The gross thing is never named. It's 'it,' a smell, a plumber, a bad curry, never 'poop' or 'fart.'")
- **20261107-155047-roast-writer**, roast line "Full coverage. Even the air gave up. Period.": The line implies the 'it' of full coverage is named or directly referenced through 'air gave up,' which leans into naming the gross thing indirectly, violating the rule against referencing the gross thing by association or metaphor. (GDD: "The gross thing is never named. It's 'it,' a smell, a bad curry, never 'poop' or 'fart.'")
- **20261107-155047-roast-writer**, roast line "Every target hit. Every one of them. A thorough mess.": The line is overly literal and explanatory, using 'A thorough mess' as a direct explanation rather than a deadpan, formal verdict with a turn, making it fail the humor and tone requirements. (GDD: "A line that passes every rule and still isn't funny.")
- **20261107-155047-roast-writer**, roast line "You left nothing untouched. Nothing left to say.": The line is a clichéd, non-sequitur conclusion with no comedic payoff or turn, failing to deliver the required deadpan, formal tone with a sharp, unexpected twist. (GDD: "A line that passes every rule and still isn't funny.")
- **20261107-155047-roast-writer**, roast line "No survivors. No witnesses. No dignity.": The line uses the phrase 'No dignity,' which is a common pop culture trope often associated with over-the-top or dramatic statements, violating the rule against pop culture references. (GDD: "No pop culture.")
- **20261107-155047-roast-writer**, roast line "Full coverage. The air itself refused to carry it further.": The line references 'it' in a way that directly names the gross thing by implication, and 'the smell' is too explicit and breaks the rule of never naming the gross thing directly. (GDD: "The gross thing is never named. It's 'it,' a smell, a plumber, a bad curry, never 'poop' or 'fart.'")
- **20261107-155047-roast-writer**, roast line "Every target hit. The cleanup crew has been reassigned.": The phrase 'the cleanup crew has been reassigned' implies the gross thing is named or directly referenced, violating the rule against naming the gross thing. (GDD: "The gross thing is never named. It's 'it,' a smell, a plumber, a bad curry, never 'poop' or 'fart.'")
- **20261107-155047-roast-writer**, roast line "You left no trace. Just the smell. And the regret.": The line explicitly names 'the smell,' which directly violates the rule against naming the gross thing. (GDD: "The gross thing is never named. It's 'it,' a smell, a plumber, a bad curry, never 'poop' or 'fart.'")
- **20261107-155047-roast-writer**, roast line "Complete. The level has been declared unfit for occupancy.": The line implies the gross thing by stating the level is unfit for occupancy due to it, which indirectly names the gross thing through context, violating the rule. (GDD: "The gross thing is never named. It's 'it,' a smell, a plumber, a bad curry, never 'poop' or 'fart.'")
- **20261107-155047-wardrobe-stylist**, design t1: The top hat has two color areas, which is within the allowed range, but the design includes a band that may not be intended as a separate recolorable region; however, the main issue is that the hat's shape and structure do not match the established style of the existing hats, which are simpler and more cartoonish, making it look out of place. (GDD: "A hat has one to three color areas that players recolor at Character Select."); The top hat's tall, narrow design with a flat top and narrow brim does not sit properly on the character's head as the existing hats do, likely causing visual misalignment or floating. (GDD: "Every item has to sit right on every character."); The top hat's formal, structured shape contrasts sharply with the playful, exaggerated, and simple flat shapes of the Santa hat, turkey hat, black shades, and silver aviators, breaking visual consistency. (GDD: "It has to look like it belongs with the four already in the game.")
- **20261107-155047-wardrobe-stylist**, design t1: The top hat has two color areas, which is within the allowed range, but the design includes a band that may not align with the flat fill and thick outline style of the existing hats. (GDD: "A hat has one to three color areas that players recolor at Character Select."); The tall, flat-topped cylinder shape may not fit properly on the character's head due to its height and narrow brim, potentially causing misalignment or floating. (GDD: "Every item has to sit right on every character."); The top hat's design is too stylized and distinct from the simple, cartoonish flat shapes of the existing hats, breaking visual consistency. (GDD: "It has to look like it belongs with the four already in the game.")
- **20261107-164801-character-artist**, design t1: Referencing 'Terry' by name and hair style creates a direct link that risks confusion, violating the distinctiveness rule. (GDD: "A new character can't be mistakable for anyone already on the roster.")
- **20261107-165733-roast-writer**, roast line "No margin. No mercy. No explanation.": The line contains three sentences, each with three words, totaling nine words, which is within the 15-word limit. However, it breaks the 'threes work' rule by being too rigidly structured in a triplet that lacks the required turn. The kept lines use threes, but always with a twist or shift in tone. This line lacks a turn and reads like a slogan, not a deadpan verdict. (GDD: "Short: one to three sentences, 15 words at most.")
- **20261107-165733-roast-writer**, roast line "Too precise. The air is still recovering.": The phrase "the air is still recovering" is a pun on the aftermath of a strong smell, which is a pun-based joke, violating the rule against puns. (GDD: "A line that explains the joke or leans on a pun alone.")
- **20261107-165733-roast-writer**, roast line "One hit. The entire floor is now a memorial.": The phrase "a memorial" is a pun on the idea of honoring something gross, which is a pun-based joke, violating the rule. (GDD: "A line that explains the joke or leans on a pun alone.")
- **20261107-165733-roast-writer**, roast line "The impact was not in the head. It was in the timeline.": The phrase "in the timeline" is a pun on time travel or historical impact, which is a pun-based joke, violating the rule. (GDD: "A line that explains the joke or leans on a pun alone.")
- **20261107-165733-roast-writer**, roast line "That’s not a splat. That’s a historical event.": The phrase "historical event" is a pun on the gravity of the moment, which is a pun-based joke, violating the rule. (GDD: "A line that explains the joke or leans on a pun alone.")
- **20261107-165733-roast-writer**, roast line "The target is now a monument. To you.": The phrase "a monument" is a pun on the idea of being remembered for something gross, which is a pun-based joke, violating the rule. (GDD: "A line that explains the joke or leans on a pun alone.")
- **20261107-171426-character-artist**, design t1: The combination of 'thick brows' and 'small eyes' constitutes exaggerated features, which violates the rule against exaggerated facial characteristics. (GDD: "The face. Every face gets the same cartoon treatment, with no exaggerated features.")
- **20261108-213543-character-artist**, design t7: The combination of 'wide-set eyes' and 'thick bushy brows' constitutes exaggerated facial features, which breaks the rule against exaggerated features. (GDD: "The face. Every face gets the same cartoon treatment, with no exaggerated features.")
- **20261108-214330-character-artist**, design t1: The description includes exaggerated facial features such as 'wide-set eyes', 'thick bushy brows', and 'surprised grimace', which violate the rule against exaggerated features. (GDD: "The face. Every face gets the same cartoon treatment, with no exaggerated features.")
- **20261108-214431-character-artist**, design t1: The combination of 'wide eyes' and 'startled expression' constitutes an exaggerated facial feature, which violates the rule against exaggerated features. (GDD: "The face. Every face gets the same cartoon treatment, with no exaggerated features.")

## Every Bridge send-back (plain code, after the GDD check)

- **20261107-163826-character-artist**: t1: Make the face look less like player12's: difference 23.8, needs at least 29.7.
- **20261107-163826-wardrobe-stylist**: t2: the hat doesn't reach the bottom of its box, so it would float above the head
- **20261107-163827-level-architect**: t1: Fill the hole inside the object at x 488 on 02.png. Fill the hole inside the object at x 193 on 02.png. Fill the hole inside the object at x 321 on 02.png. Fill the hole inside the object at x 176 on 
- **20261107-163827-level-architect**: t1: Fill the hole inside the object at x 280 on 02.png. Fill the hole inside the object at x 394 on 02.png. Fill the hole inside the object at x 31 on 03.png. Fill the hole inside the object at x 259 on 0
- **20261107-164801-character-artist**: t1: Make the hair look less like player11's: difference 6.7, needs at least 9.8.
- **20261107-164801-wardrobe-stylist**: t1: the name Top Hat is taken
- **20261107-164801-wardrobe-stylist**: t1: the name Top Hat is taken
- **20261107-170123-character-artist**: t1: Make the face look less like player11's: difference 29.6, needs at least 29.7.
- **20261107-170123-character-artist**: t4: Make the face look less like player11's: difference 27.6, needs at least 29.7.
- **20261107-170737-character-artist**: t1: Make the face look less like player12's: difference 27.7, needs at least 29.7.
- **20261107-170737-character-artist**: t1: Make the face look less like player11's: difference 22.0, needs at least 29.7.
- **20261107-170937-character-artist**: t1: Make the face look less like player11's: difference 22.3, needs at least 29.7.
- **20261107-170937-character-artist**: t1: Make the face look less like player12's: difference 29.3, needs at least 29.7.
- **20261107-171426-character-artist**: t1: Make the face look less like player11's: difference 22.8, needs at least 29.7.
- **20261107-171522-character-artist**: t3: Make the face look less like player11's: difference 25.8, needs at least 29.7.
- **20261108-213543-character-artist**: t3: Make the hair look less like player13's: difference 8.9, needs at least 9.8. Make the face look less like player13's: difference 28.3, needs at least 29.7.
- **20261108-213543-character-artist**: t7: Make the face look less like player15's: difference 27.5, needs at least 29.7.
- **20261108-214330-character-artist**: t1: Make the hair look less like player15's: difference 9.1, needs at least 9.8. Make the face look less like player11's: difference 28.3, needs at least 29.7.
- **20261108-214431-character-artist**: t1: Make the hair look less like player18's: difference 9.8, needs at least 9.8. Make the face look less like player11's: difference 28.6, needs at least 29.7.
- **20261108-214537-character-artist**: t1: Make the face look less like player11's: difference 28.9, needs at least 29.7.
- **20261108-214743-character-artist**: t1: Make the hair look less like player19's: difference 9.5, needs at least 9.8. Make the face look less like player19's: difference 13.5, needs at least 29.7.

## Everything made

- **20261107-155047-roast-writer**: roast line rw_drowned_001: "No one’s coming. Not even the cleanup crew."
- **20261107-155047-roast-writer**: roast line rw_drowned_002: "Even the current looked away."
- **20261107-155047-roast-writer**: roast line rw_longestStreak_001: "That was not a strategy. That was a statement."
- **20261107-163826-wardrobe-stylist**: Top Hat (top_hat)
- **20261107-164801-level-architect**: haunted mansion on a crooked hill (background_t1)
- **20261107-165733-roast-writer**: roast line rw_drowned_003: "You drowned them all. The water is still angry."
- **20261107-165733-roast-writer**: roast line rw_drowned_004: "The water remembers. It is not forgiving."
- **20261107-165733-roast-writer**: roast line rw_drowned_005: "The lifeguard is off duty. A permanent one."
- **20261107-165733-roast-writer**: roast line rw_bombsOnTarget_001: "That was not a shot. That was a declaration."
- **20261107-165733-roast-writer**: roast line rw_bombsOnTarget_002: "Precision. Brutal. Unavoidable."
- **20261107-165733-roast-writer**: roast line rw_bombsOnTarget_003: "That was not a hit. That was a complaint."
- **20261107-165733-roast-writer**: roast line rw_directDeposit_001: "The head is now a permanent fixture."
- **20261107-165733-roast-writer**: roast line rw_directDeposit_002: "On target. The structural integrity is not."
- **20261107-165733-roast-writer**: roast line rw_directDeposit_003: "You hit the same spot twice. The building is angry."
- **20261107-165733-roast-writer**: roast line rw_inOneSitting_001: "Every one. All of them. No breaks."
- **20261107-165733-roast-writer**: roast line rw_inOneSitting_002: "No pauses. No mercy. No clean-up crew."
- **20261107-165733-roast-writer**: roast line rw_inOneSitting_003: "That was not a string. That was a flood."
- **20261107-165733-roast-writer**: roast line rw_longestStreak_002: "The air is still. The silence is worse."
- **20261107-165733-roast-writer**: roast line rw_longestStreak_003: "That’s not a pattern. That’s a crime scene."
- **20261107-165733-roast-writer**: roast line rw_longestStreak_004: "It’s not a streak. It’s a warning."
- **20261107-165733-roast-writer**: roast line rw_received_001: "Efficient. Unpleasantly thorough. Well done."
- **20261107-165733-roast-writer**: roast line rw_received_002: "You absorbed it all. Even the leftovers."
- **20261107-165733-roast-writer**: roast line rw_diedDirty_001: "Caked in it. Even the air gave up."
- **20261107-165733-roast-writer**: roast line rw_diedDirty_002: "Died dirty. The floor has a new stain. It’s not going away."
- **20261107-165733-wardrobe-stylist**: Top Hat (top_hat_2)
- **20261107-170123-character-artist**: Curtis (player13)
- **20261107-170123-character-artist**: Reggie (player14)
- **20261107-170123-character-artist**: Trevor (player15)
- **20261107-171522-character-artist**: Darius (player16)
- **20261107-171522-character-artist**: James (player17)
- **20261107-171522-character-artist**: Marcus (player18)
- **20261107-171522-character-artist**: Daniel (player19)
- **20261107-171522-character-artist**: Derrick (player20)
- **20261108-213543-character-artist**: David (player13)
- **20261108-213543-character-artist**: Clay (player14)
- **20261108-213543-character-artist**: Marcus (player15)
- **20261108-213543-character-artist**: Daniel (player16)
- **20261108-213543-character-artist**: Derrick (player17)
- **20261108-213543-character-artist**: Curtis (player18)
- **20261108-214537-character-artist**: Clayton (player19)
- **20261108-214852-character-artist**: James (player20)
