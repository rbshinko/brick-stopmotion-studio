"""The Milo cast bible: every recurring character's look, saved once and reused in every episode.
Colours are sRGB hex (the engine converts to linear). Outfit fields: shirt, pants, shoes,
sleeve (short/long), plen (long/short legs), acc (accessories), hair (style), hair_col."""

CAST = {
    # the star: spiky red hair with one curl on top, round glasses, open black jacket over a
    # white tee, red pendant on a black cord, black pants, black-and-white sneakers
    "milo": dict(
        name="Milo", role="narrator, 11, the kid every disaster finds", skin="#F5C59A",
        hair="milo", hair_col="#E0242B", eyes="#7A4FD0", face="smile", signature="peace sign and wink",
        own=dict(shirt="#F4F4F4", pants="#1C1C22", shoes="#1A1A1A", sleeve="long",
                 acc=["jacket:#1E1E24", "pendant", "glasses"], sleeve_col="#1E1E24"),
    ),
    # best friend: chill gamer, always half asleep, headphones round his neck
    "kai": dict(
        name="Kai", role="best friend, gamer, loyal", skin="#8D5524", hair="short", hair_col="#141414",
        face="smile",
        own=dict(shirt="#2FB86A", pants="#2B3A55", shoes="#F2F2F2", sleeve="long", acc=["headphones"]),
    ),
    # best friend: top of the class, plans everything, purple ponytail and a red bow
    "yumi": dict(
        name="Yumi", role="best friend, smartest kid in class", skin="#FFDBAC", hair="ponytail",
        hair_col="#7B4FD6", face="smile",
        own=dict(shirt="#FFD23F", pants="#3A5BD9", shoes="#FFFFFF", sleeve="long", acc=["bow"]),
    ),
    # rival: rich show-off, gold jacket, sunglasses on his head
    "brax": dict(
        name="Brax", role="rival, rich, smug", skin="#F5C59A", hair="swoop", hair_col="#F2D16B",
        face="smug",
        own=dict(shirt="#F2C230", pants="#FFFFFF", shoes="#F2C230", sleeve="long", acc=["shades_up", "chain"]),
    ),
    # little sister: pink pigtails, causes chaos, usually saves the day
    "pia": dict(
        name="Pia", role="Milo's little sister, 6, wildcard", skin="#F5C59A", hair="pigtails",
        hair_col="#E0242B", face="grin", scale=0.78,
        own=dict(shirt="#FF7BB5", pants="#FF7BB5", shoes="#FFFFFF", plen="short", acc=["dress:#FF7BB5"]),
    ),
    "mom": dict(
        name="Mom", role="Milo's mom", skin="#F5C59A", hair="long", hair_col="#5A2A1A", face="smile",
        own=dict(shirt="#3FA9A0", pants="#2B2B44", shoes="#5A3A2A", sleeve="long", acc=[]),
    ),
    "dad": dict(
        name="Dad", role="Milo's dad, tells bad jokes", skin="#F5C59A", hair="short", hair_col="#B0261F",
        face="smile",
        own=dict(shirt="#3A6FD8", pants="#4A4A4A", shoes="#2B2B2B", sleeve="short", acc=["glasses"]),
    ),
    "lola": dict(
        name="Lola", role="grandma, undefeated at everything", skin="#E0A878", hair="bun", hair_col="#D9D9D9",
        face="smile",
        own=dict(shirt="#B39DDB", pants="#7E6BA8", shoes="#5A4A3A", sleeve="long", acc=[]),
    ),
    "reyes": dict(
        name="Ms. Reyes", role="class teacher", skin="#E0A878", hair="bun", hair_col="#4A2E1A", face="smile",
        own=dict(shirt="#2E9E6B", pants="#2B2B44", shoes="#3B2A1A", sleeve="long", acc=["glasses"]),
    ),
    "tan": dict(
        name="Principal Tan", role="principal", skin="#F1C27D", hair="short", hair_col="#9E9E9E",
        face="determined",
        own=dict(shirt="#1E2A5A", pants="#1E2A5A", shoes="#111111", sleeve="long",
                 acc=["shirtfront", "tie", "mustache"]),
    ),
    "coach": dict(
        name="Coach Bolt", role="PE coach, whistle always ready", skin="#8D5524", hair="short",
        hair_col="#111111", face="determined",
        own=dict(shirt="#E5262B", pants="#E5262B", shoes="#FFFFFF", sleeve="long",
                 acc=["cap:#1F4FD1", "whistle"]),
    ),
}

# pets reuse the box-animal builder
PETS = {"mochi": dict(name="Mochi", kind="cat", col="#F39C12"),
        "biscuit": dict(name="Biscuit", kind="dog", col="#C68642")}
