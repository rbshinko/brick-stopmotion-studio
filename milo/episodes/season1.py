"""Season 1 scripts. Every episode follows the same beat sheet (the spec's structure), so the
engine can map beats to shots: RULE CAUSE VICTIM EX ME INC POP ESC REVEAL QUIET TWIST PAYOFF CALLBACK.
[brackets] mark the key nouns that turn red in the captions."""

EPISODES = {
    "ep11": dict(
        title="If You Shout, Your Head Pops Off 😭", form="headless",
        lines=[
            ("RULE", "Bro, in this town, if you shout, your [head] pops off."),
            ("CAUSE", "Dad yelled at the [TV] during the game."),
            ("VICTIM", "Pop. Now he cheers with no [head]."),
            ("EX", "Teachers here only [whisper]."),
            ("EX", "Fire alarms just [blink]."),
            ("EX", "And concerts? Everybody brings [tape]."),
            ("ME", "Me? I'm the loudest kid in [school]."),
            ("INC", "Today is Kai's surprise [party]."),
            ("INC", "Thirty kids hiding in the dark, all holding their [breath]."),
            ("POP", "Kai walks in. We all jump up. SURPRISE!"),
            ("ESC", "Pop! Thirty [heads] fly into the air."),
            ("ESC", "One lands in the [cake]."),
            ("ESC", "Mine bounces off the [ceiling fan]."),
            ("REVEAL", "Kai looks around... at thirty headless [friends]."),
            ("QUIET", "Then he whispers: \"Best party [ever].\""),
            ("TWIST", "Then HE shouts: \"THANK YOU!\" [Pop]."),
            ("PAYOFF", "Now we're all just heads in a [pile]."),
            ("CALLBACK", "Dad says it's still quieter than the [game]."),
        ]),
}
