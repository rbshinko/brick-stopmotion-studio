"""YouTube title, description and pinned comment per episode (post.py writes them into outbox/*.txt).
Pattern: "In This Town, <the rule> <emoji>" (searchable keyword first, curiosity rule, under ~60 chars),
then a hook line, the setup, a comment question, a follow line and 4-5 hashtags (the first 3 show above the title)."""

TAGS = "#stopmotion #brickanimation #animation #shorts"
FOLLOW = "Follow Milo for a new crazy town rule every week! 🏙️"

META = {
    "ep11": dict(
        title="In This Town, If You Shout Your Head POPS Off 😭",
        hook="In this town, if you shout… your head POPS off. 💥",
        setup="Kai's surprise party. Thirty kids hiding in the dark. Then everybody yells SURPRISE… 😭",
        question="Who's the LOUDEST person you know? Tag them 👇",
        pinned="Would you survive one day in this town? 🤫👇",
        tags="#stopmotion #brickanimation #animation #shorts"),
}


def description(ep, credits=()):
    m = META[ep]
    lines = [m["hook"], m["setup"], "", m["question"], FOLLOW, "", m.get("tags", TAGS)]
    if credits:
        lines += ["", "Credits:"] + list(credits)
    return "\n".join(lines)
