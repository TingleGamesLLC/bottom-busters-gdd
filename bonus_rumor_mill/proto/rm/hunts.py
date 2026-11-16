"""The six hunts David approved (2026-11-15). Each game plays one of them.

The rumor you hear, each person's version up the chain, the truth and the proof are fixed,
word for word as approved. The model plays the people live in typed conversation.

Where and when each hop happened, what each starter says when asked who told them, and
the secrets the real culprits keep were filled in by Claude so the hunts can be played."""

# The town the six hunts need. Building keys are the drawn kit pieces, left to right (cast.KIT_ORDER).
STREET = "Main Street"
ROOF_PROP = "teapot"
PLACES = {
    "shop": {"name": "Lemonade Stand", "who": "toby"},
    "house": {"name": "Post Office", "who": "mildred"},
    "dock_shed": {"name": "Dock", "who": "gary"},
    "theater": {"name": "Theater", "who": "ozzie"},
    "tavern": {"name": "Coffee Shop", "who": "bev"},
}
JOBS = {
    "toby": "sells lemonade",
    "mildred": "sorts the mail",
    "gary": "mends nets",
    "ozzie": "writes plays",
    "bev": "serves coffee",
}

# Things a confession would sound like. Nobody says these before they're caught.
CONFESS = ["it was me", "it's me", "that was me", "it was really me", "i'm the one", "i did it", "i do it"]

HUNTS = [
    {
        "id": 1,
        "kind": "liar",
        "chain": [
            {"npc": "mildred", "change": "started it",
             "version": 'You\'ve been mailing yourself love letters signed "a secret admirer."'},
            {"npc": "bev", "change": "added that Mildred has to hand them to you with a straight face",
             "version": 'You\'ve been mailing yourself love letters signed "a secret admirer," and Mildred has to hand them to you with a straight face.'},
            {"npc": "gary", "change": "made it every day for a month",
             "version": 'You\'ve mailed yourself a love letter signed "a secret admirer" every day for a month, and Mildred has to hand them to you with a straight face.'},
            {"npc": "toby", "change": "added the perfume",
             "version": 'You\'ve mailed yourself a perfumed love letter signed "a secret admirer" every day for a month, and Mildred has to hand them to you with a straight face.'},
        ],
        "hops": [
            {"where": "the Coffee Shop", "when": "Wednesday morning"},
            {"where": "the Coffee Shop", "when": "Wednesday afternoon"},
            {"where": "the Lemonade Stand", "when": "Wednesday evening"},
        ],
        "truth": ('Ozzie mails himself love letters signed "a secret admirer." When Bev asked who keeps getting the '
                  "pink envelopes, Mildred named you to protect her friend Ozzie."),
        "claim": "Nobody had to tell me. I hand those letters to you myself.",
        "friends": [("mildred", "ozzie")],
        "truth_person": "ozzie",
        "truth_secret": 'You mail yourself love letters signed "a secret admirer." Only your friend Mildred knows.',
        "guard": ["i mail myself", "my letters", "my love letters", "my typewriter"],
        "finds": [
            {"id": "envelope", "where": "house", "icon": "note", "title": "An envelope from Mildred's dead-letter tray",
             "lines": ["No address on it.", 'Typed on the front: "a s_cr_t admir_r"']},
            {"id": "typewriter", "where": "theater", "icon": "note", "title": "Ozzie's typewriter, at the Theater",
             "lines": ['Its "e" key is missing.']},
        ],
        "catch": ["envelope"],
    },
    {
        "id": 2,
        "kind": "liar",
        "chain": [
            {"npc": "bev", "change": "started it",
             "version": "You cried at the children's puppet show."},
            {"npc": "gary", "change": "made it every show this month",
             "version": "You've cried at every children's puppet show this month."},
            {"npc": "mildred", "change": "added that the theater seats you behind the kids now",
             "version": "You've cried at every children's puppet show this month, and the theater seats you behind the kids now."},
            {"npc": "toby", "change": "added the hankie",
             "version": "You've cried at every children's puppet show this month, the theater seats you behind the kids now, and you bring your own hankie."},
        ],
        "hops": [
            {"where": "the Coffee Shop", "when": "Wednesday morning"},
            {"where": "the Post Office", "when": "Wednesday afternoon"},
            {"where": "the Lemonade Stand", "when": "Wednesday evening"},
        ],
        "truth": ("Nothing happened. Bev made it up because on Tuesday you told her, in front of customers, "
                  "that her coffee was lukewarm."),
        "claim": "Nobody told me. I saw it myself, at the puppet show.",
        "friends": [],
        "truth_person": None,
        "knows": {"ozzie": ("You run the Theater. There was one children's puppet show this month, Tuesday morning. "
                            "Eleven tickets were sold, all of them children's half-price.")},
        "finds": [
            {"id": "stub_book", "where": "theater", "icon": "ticket_stub", "title": "The Theater's ticket stub book",
             "lines": ["One puppet show this month: Tuesday morning.", "Eleven tickets sold, all children's half-price."]},
        ],
        "catch": ["stub_book"],
    },
    {
        "id": 3,
        "kind": "mistake",
        "chain": [
            {"npc": "gary", "change": "started it",
             "version": "You got locked out in your nightshirt on Wednesday morning."},
            {"npc": "toby", "change": "added the kitchen window",
             "version": "You got locked out in your nightshirt on Wednesday morning and climbed in through your own kitchen window."},
            {"npc": "mildred", "change": "added that you got stuck halfway",
             "version": "You got locked out in your nightshirt on Wednesday morning, climbed in through your own kitchen window, and got stuck halfway."},
        ],
        "hops": [
            {"where": "the Lemonade Stand", "when": "Wednesday morning"},
            {"where": "the Post Office", "when": "Wednesday afternoon"},
        ],
        "truth": ("Bev got locked out in her nightshirt at 6:15 Wednesday morning. From the dock, Gary saw someone in "
                  "a nightshirt by the coffee shop through the fog and took it for you."),
        "seen": ("At a quarter past six on Wednesday morning, from the Dock, you saw someone in a nightshirt by the "
                 "Coffee Shop through the fog. You're sure it was the player."),
        "claim": "Nobody told me. I saw you myself from the Dock, a quarter past six Wednesday morning, in the fog by the Coffee Shop.",
        "friends": [],
        "truth_person": "bev",
        "truth_secret": "At 6:15 on Wednesday morning you got locked out in your nightshirt. You'd die before anyone found out.",
        "guard": ["i got locked out", "i was locked out", "locked myself out", "my nightshirt"],
        "finds": [
            {"id": "door_note", "where": "tavern", "icon": "note", "title": "A note taped to the Coffee Shop door",
             "lines": ['"Locked out. Coffee at 7. —B."']},
        ],
        "solve": ["door_note"],
    },
    {
        "id": 4,
        "kind": "mistake",
        "chain": [
            {"npc": "mildred", "change": "started it",
             "version": "You mailed your teddy bear to a toy mender."},
            {"npc": "toby", "change": "added getting its ear sewn back on",
             "version": "You mailed your teddy bear to a toy mender to get its ear sewn back on."},
            {"npc": "bev", "change": "added the note so it wouldn't be scared",
             "version": "You mailed your teddy bear to a toy mender to get its ear sewn back on, with a note so it wouldn't be scared."},
        ],
        "hops": [
            {"where": "the Post Office", "when": "Wednesday morning"},
            {"where": "the Coffee Shop", "when": "Wednesday afternoon"},
        ],
        "truth": ('It\'s Gary\'s bear, "Admiral Snuggles." It came back from the toy mender with a rain-smudged label, '
                  "and Mildred read your name on it."),
        "seen": ("A parcel came back from the toy mender. The label was smudged by the rain, and you read the player's "
                 "name on it. It's on the shelf at the Post Office, waiting to go out."),
        "claim": "Nobody told me. The toy mender's parcel came back with your name on the label.",
        "friends": [],
        "truth_person": "gary",
        "truth_secret": 'You mailed your teddy bear, "Admiral Snuggles," to the toy mender to get his ear sewn back on. Nobody can ever know.',
        "guard": ["my bear", "my teddy", "admiral snuggles"],
        "finds": [
            {"id": "receipt", "where": "house", "icon": "receipt", "title": "The receipt inside the toy mender's parcel",
             "lines": ['"One bear, \'Admiral Snuggles,\' left ear reattached."', '"Paid: G. Gusto."']},
        ],
        "solve": ["receipt"],
    },
    {
        "id": 5,
        "kind": "liar",
        "chain": [
            {"npc": "ozzie", "change": "started it",
             "version": "You practice proposing to Bev on one knee, to a coat rack."},
            {"npc": "gary", "change": "made it every night",
             "version": "You practice proposing to Bev on one knee every night, to a coat rack."},
            {"npc": "toby", "change": "added the curly wig",
             "version": "You practice proposing to Bev on one knee every night, to a coat rack in a curly wig."},
            {"npc": "mildred", "change": "added the hole in your carpet",
             "version": "You practice proposing to Bev on one knee every night, to a coat rack in a curly wig, and you've worn a hole in your carpet where you kneel."},
        ],
        "hops": [
            {"where": "the Theater", "when": "Tuesday evening"},
            {"where": "the Lemonade Stand", "when": "Wednesday morning"},
            {"where": "the Post Office", "when": "Wednesday afternoon"},
        ],
        "truth": ('Ozzie practices proposing to Bev every night, on one knee, to the theater\'s coat rack. When Gary '
                  'heard "Bev, my darling" through the stage door and asked, Ozzie said it was you.'),
        "claim": "Nobody told me. I saw you myself, through your window.",
        "friends": [],
        "truth_person": None,
        "finds": [
            {"id": "cue_card", "where": "theater", "icon": "note", "title": "A cue card in the coat rack's hat",
             "lines": ["In Ozzie's handwriting:", '"Bev, my darling, my little coffee bean—"']},
        ],
        "catch": ["cue_card"],
    },
    {
        "id": 7,
        "kind": "liar",
        "chain": [
            {"npc": "bev", "change": "started it",
             "version": "You talk baby talk to the dock cat."},
            {"npc": "mildred", "change": "added the name, which she'd seen painted at the dock",
             "version": "You talk baby talk to the dock cat and call it Mister Snuggle-Whiskers."},
            {"npc": "gary", "change": "made it the whole dock",
             "version": "You talk baby talk to the dock cat and call it Mister Snuggle-Whiskers, and now the whole dock calls it that."},
        ],
        "hops": [
            {"where": "the Coffee Shop", "when": "Wednesday morning"},
            {"where": "the Dock", "when": "Wednesday afternoon"},
        ],
        "truth": ("It's Toby. He picks up ice at the dock every morning for his lemonade, and while it's loaded he coos "
                  "at the cat. When Mildred asked who it was, Bev, his friend, named you to protect him."),
        "claim": "Nobody told me. I saw you myself, behind the icehouse.",
        "friends": [("bev", "toby")],
        "truth_person": "toby",
        "truth_secret": ("Every morning, while your ice is loaded at the Dock, you coo baby talk at the dock cat, Mister "
                         "Snuggle-Whiskers. Only your friend Bev knows."),
        "guard": ["i baby talk", "i talk baby talk", "i coo", "my crate", "my cat"],
        "finds": [
            {"id": "crate", "where": "dock_shed", "icon": "note", "title": "A lemonade crate behind the icehouse",
             "lines": ["One of Toby's lemonade crates, with a pillow in it.",
                       '"Mister Snuggle-Whiskers" is painted on the side, in Toby\'s sign lettering.']},
        ],
        "catch": ["crate"],
    },
]
