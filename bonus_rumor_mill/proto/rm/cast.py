"""The five Milestone 1 actors and the human-written bounds: the tone guide, the content
rails, the catalog and the game numbers.

Each actor keeps their type and fingerprint every game. Their job, workplace,
relationships and secret are generated each game by the Casting Director."""

TONE_GUIDE = """Rumor Mill is a comedy detective game about small-town gossip, played like the
childhood game Telephone. What funny means here:
- Slapstick, never cruel. Comeuppance, not cruelty.
- Specific, not generic: name the place, the thing and the amount. Never "a shop" or "some stuff".
- Townsfolk are deadpan about absurd things.
- Escalation, callbacks, and the rule of three.
- Short lines. One or two sentences. Spoken out loud, not narrated."""

RAILS = """Content rails: cartoon violence only, PG-13, no real people, no slurs.
Kids and animals are never the targets of slapstick. Plain American English only."""

# Each person passes a rumor on with exactly one kind of change. That style is their fingerprint.
CAST = {
    "toby": {
        "name": "Toby Crumb",
        "short": "Toby",
        "type": "the Salesman",
        "mutation": "add_detail",
        "field": "extras",
        "does": "adds one vivid detail",
        "fingerprint": "none; he never plugs his lemonade, prices or specials",
        "voice": "fast and cheery, a friendly salesman",
        "look": "paper hat, apron dusted white, huge grin",
        "color": "#F2A541",
        "markers": [],
        "say": "",
        "phrase": "",
        "anims": ["finger_guns", "thumbs_up", "shrug", "nod"],
    },
    "mildred": {
        "name": "Mildred Ashby",
        "short": "Mildred",
        "type": "the Busybody",
        "mutation": "merge",
        "field": "act",
        "does": "merges two rumors into one",
        "fingerprint": "'AND you know what ELSE'",
        "voice": "rapid, nasal, delighted to be the one who knows",
        "look": "hair curlers, bathrobe, binoculars around her neck",
        "color": "#B99CEB",
        "markers": ["you know what else"],
        "say": "the exact words 'AND you know what ELSE'",
        "phrase": "AND you know what ELSE?",
        "anims": ["peer_binoculars", "lean_over_fence", "gasp", "point"],
    },
    "gary": {
        "name": "Gary Gusto",
        "short": "Gary",
        "type": "the Exaggerator",
        "mutation": "exaggerate",
        "field": "scale",
        "does": "makes it bigger: more often, more of it, more people",
        "fingerprint": "'every day,' 'hundreds,' 'the size of a wagon'",
        "voice": "booming baritone, every story is a fish story",
        "look": "enormous handlebar mustache, tall striped hat, barrel chest",
        "color": "#E0464E",
        "markers": ["every day", "every single day", "hundred", "dozens", "size of", "thousand",
                    "every morning", "every night", "every week", "million"],
        "say": "'every day' or 'hundreds' or 'the size of a wagon'",
        "phrase": "Every single day!",
        "anims": ["this_big_sweep", "point", "gasp", "nod"],
    },
    "bev": {
        "name": "Bev Fairweather",
        "short": "Bev",
        "type": "the Drama Queen",
        "mutation": "add_detail",
        "field": "extras",
        "does": "adds one emotional, theatrical detail",
        "fingerprint": "'and I nearly DIED,' 'I can't even,' fainting",
        "voice": "swooping and theatrical, everything is the worst thing that ever happened",
        "look": "enormous sun hat, giant sunglasses, feather boa",
        "color": "#E8489E",
        "markers": ["died", "can't even", "wept", "faint", "sob", "tears", "heart", "swoon"],
        "say": "'I nearly DIED' or 'I can't even'",
        "phrase": "I nearly DIED.",
        "anims": ["faint", "gasp", "facepalm", "point"],
    },
    "ozzie": {
        "name": "Ozzie Fink",
        "short": "Ozzie",
        "type": "the Liar",
        "mutation": "swap_name_on_purpose",
        "field": "subject",
        "does": "swaps a name on purpose, to frame someone or cover for a friend",
        "fingerprint": "oddly specific alibis, 'trust me,' 'I would never'",
        "voice": "smooth and oily, too friendly",
        "look": "slicked hair, pencil mustache, pinstripe suit a size too small, a deck of cards",
        "color": "#9AA0AE",
        "markers": ["trust me", "i would never", "honest", "swear"],
        "say": "'trust me' or 'I would never'",
        "phrase": "Trust me.",
        "anims": ["rub_hands", "shrug", "wave_off", "cross_arms"],
    },
}
KEYS = list(CAST)

# ---------------------------------------------------------------- the catalog
# The building kit, already drawn, left to right on the street. One person per building.
KIT = {
    "shop": "a shop with a giant prop on the roof",
    "house": "a house with a picket fence",
    "dock_shed": "a shed on the docks, by the water",
    "theater": "a theater with marquee lights",
    "tavern": "a tavern with a hanging sign",
}
KIT_ORDER = ["shop", "house", "dock_shed", "theater", "tavern"]

# Giant props that can sit on the shop's roof (drawn in art.py).
ROOF_PROPS = ["teapot", "boot", "key", "cheese", "anvil", "scissors", "clock", "top_hat",
              "fish", "candle", "book", "bell"]

FACES = ["talking", "shocked", "smug", "lying", "busted", "crying"]
ANIMS = [
    "whisper_behind_hand", "gasp", "this_big_sweep", "finger_guns", "thumbs_up", "faint",
    "peer_binoculars", "lean_over_fence", "shifty_eyes", "rub_hands", "shrug", "point",
    "wave_off", "cross_arms", "nod", "facepalm", "cower", "grovel",
]
# Comedy props for comeuppances.
PROPS = [
    "custard_pie", "fish", "rubber_chicken", "liars_hat", "baguette", "bucket_of_water",
    "garden_hose", "megaphone", "confetti_cannon", "sign_board", "wanted_poster",
    "feather_boa", "folding_fan", "deck_of_cards", "tankard", "binoculars", "fishing_rod", "fountain",
]
# What the player can be holding that proves the true event.
EVIDENCE = {
    "receipt": "a paper receipt",
    "ticket_stub": "a torn ticket stub",
    "note": "a handwritten note",
}
# What the town can do about a rumor (already drawn).
TOWN_ASSETS = ["wanted_poster", "guard", "stocks"]
SHOTS = ["wide", "slow_push_in", "whip_pan", "dolly_zoom", "freeze_frame", "low_angle", "close_up"]

# Faces and moves that would mark a liar on screen. Nobody can use them until they've been cracked,
# so a face or a stage direction never tells the player who is lying.
TELL_FACES = {"lying", "busted"}
TELL_ANIMS = {"shifty_eyes", "cower", "grovel"}
OPEN_FACES = [f for f in FACES if f not in TELL_FACES]
OPEN_ANIMS = [a for a in ANIMS if a not in TELL_ANIMS]

# Readable names for animation tags, shown as stage directions.
ANIM_TEXT = {
    "whisper_behind_hand": "whispers behind a hand", "gasp": "gasps", "this_big_sweep": "sweeps both arms out THIS big",
    "finger_guns": "fires finger guns", "thumbs_up": "gives a double thumbs-up", "faint": "swoons",
    "peer_binoculars": "peers through binoculars", "lean_over_fence": "leans over the fence",
    "shifty_eyes": "glances left, then right", "rub_hands": "rubs both hands together", "shrug": "shrugs",
    "point": "points", "wave_off": "waves it off", "cross_arms": "crosses arms", "nod": "nods",
    "facepalm": "facepalms", "cower": "cowers", "grovel": "grovels",
}

SHOT_TEXT = {
    "wide": "wide shot", "slow_push_in": "slow push in", "whip_pan": "whip pan", "dolly_zoom": "dolly zoom",
    "freeze_frame": "freeze frame", "low_angle": "low angle", "close_up": "close up",
}

# ---------------------------------------------------------------- game numbers
GAME_DAY = "Thursday"
DAY_START, DAY_END = 9, 18          # 9 AM to 6 PM; each conversation costs an hour
# The two days before the game day. True events and every hop of the chain happen in these slots.
SLOTS = ["Tuesday morning", "Tuesday afternoon", "Tuesday evening",
         "Wednesday morning", "Wednesday afternoon", "Wednesday evening"]
TIERS = [(0.0, "Whispers"), (0.45, "Talk of the Town"), (1.0, "Scandal")]
TURNS_PER_VISIT = 6                 # lines the player can type per visit
BELIEVER_THRESHOLD = 5              # this many believers and the town acts on the rumor
CHAIN_LENGTHS = {3: 0.3, 4: 0.4, 5: 0.3}   # people in the chain, source to messenger
TWIST_DECK = {"none": 0.5, "victim_stunt": 0.5}
EVENTS_MIN, EVENTS_MAX, EVENTS_ABOUT_YOU = 5, 10, 3
MAX_TRIES = 3                       # an agent's tries before code builds a plain line from the ledger
MAX_PREMISES = 4                    # premises thrown out before the night stops with an error
CRITIC_PASS = 3                     # the Comedy Critic's "decent" score, out of 5. A 1, or a 2 that doesn't make sense, goes back
DIRECTOR_IDLE_HOURS = 3             # hours without progress before the Director gives a push
REP_START = 5
