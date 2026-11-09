"""EP11 staging: If You Shout, Your Head Pops Off (lines live in season1.py).
Every shout ends in `pop`: the head (hair, gear, face) flies off on an arc and lands somewhere silly; the body keeps
acting headless. Dad's head stays on the couch all film; the party ends in a pile of grinning heads."""
from dsl import L

SETS = ["street", "home", "classroom", "hallway", "cafeteria"]
WHO = ["milo", "dad", "kai", "yumi", "brax", "pia", "reyes", "coach"]
CROWD = ("cafeteria", None, 14)
MUSIC = "island"
PROPS = [("tv", "home.center", 0, -9),
         ("speaker", "street.walk2", 0, 4), ("sign:CONCERT", "street.walk3", 3.5, 3),
         ("alarm", "hallway.spot1", 3, 4, -0.8),
         ("cake", "cafeteria.spot1", 0, 3), ("sign:SURPRISE!", "cafeteria.spot4", 0, 3),
         ("fan", "cafeteria.spot3", 0, 2, 9.0)]

STAGE = [
    # RULE: a man shouts on the street and his head pops off onto the sidewalk; Yumi grabs her own head
    L("street", "coach", "wide close:yumi@Head", at="coach@street.walk2 yumi@street.walk1",
      do="^> coach pose cheer/ahh; Shout> coach pop street.walk2 2.5 -1.5; ^> yumi pose panic/scared"),
    # CAUSE: Dad yells at the TV (remote in hand), then his first-person view of the game
    L("home", "dad", "close pov:dad@During", at="dad@home.center",
      do="^> dad form hold_phone:#222222 nopuff; ^> dad pose angry/ahh; During> dad pose holdout/ahh"),
    # VICTIM: Pop - the head lands on the couch; the body cheers anyway
    L("home", "dad", "med low:dad@Cheers",
      do="Pop> dad pop home.couch2 0 0 1.4 grin; Cheers> dad pose cheer"),
    # EX: the teacher whispers
    L("classroom", "reyes", "med", at="reyes@classroom.teacher kai@classroom.desk2>reyes",
      do="^> reyes pose thinkchin/smile; ^> kai pose lean/smile"),
    # EX: the fire alarm only blinks; Brax shrugs under it
    L("hallway", "brax", "med", at="brax@hallway.spot1", do="^> brax pose shrug/smug"),
    # EX: a concert where everyone wears tape over the mouth
    L("street", "yumi", "wide insert:yumi:face@Everybody",
      at="yumi@street.walk1 pia@street.walk2 kai@street.walk3",
      do="^> yumi form wear_tape nopuff; ^> pia form wear_tape nopuff; ^> kai form wear_tape nopuff; "
         "^> yumi pose cheer/grin; ^> pia pose clap/grin; ^> kai pose fistpump/grin"),
    # ME: the loudest kid, mic in hand
    L("classroom", "milo", "close", at="milo@classroom.front",
      do="^> milo form hold_mic nopuff; ^> milo pose mic/grin"),
    # INC: the party room; over Brax's shoulder onto Milo
    L("cafeteria", "milo", "wide ots:brax,milo@Surprise",
      at="milo@cafeteria.spot3>brax brax@cafeteria.spot1>milo yumi@cafeteria.spot4",
      do="^> milo form own nopuff; ^> yumi form own nopuff; ^> milo pose point/grin; ^> brax pose clap/grin; "
         "^> yumi pose wave/smile"),
    # INC: everyone crouched, holding their breath
    L("cafeteria", "milo", "wide med:milo@All",
      do="^> crowd pose sit/scared; ^> brax pose sit/scared; ^> yumi pose sit/scared; ^> milo pose sit/scared"),
    # POP: Kai walks in from below, then everybody jumps up at him
    L("cafeteria", "kai", "low wide@Jump", at="kai@cafeteria.spot0",
      do="^> kai form own nopuff; ^> kai pose wave/smile; Jump> all snapto kai cheer/grin; "
         "SURPRISE> crowd face ahh; SURPRISE> milo face ahh; SURPRISE> brax face ahh; SURPRISE> yumi face ahh; "
         "SURPRISE> kai pose shock/shock"),
    # ESC: Pop! the crowd's heads fly (8 really fly), Yumi's goes up and away; Kai stares
    L("cafeteria", "set", "wide high:kai@Fly",
      do="Pop> crowd pop; Pop> yumi pop up; Fly> kai pose panic/shock"),
    # ESC: Brax's head lands in the cake
    L("cafeteria", "brax", "high", do="^> brax pop cafeteria.spot1 0 3 3.3 grin"),
    # ESC: Milo's head bounces off the ceiling fan and lands on the floor
    L("cafeteria", "milo", "low", do="^> milo pop cafeteria.spot3 0 2 7.0 cafeteria.spot3 3 -2 grin"),
    # REVEAL: the slide over the headless crowd, then Kai looking around
    L("cafeteria", "kai", "slide med@Headless", do="^> kai pose shrug/shock; Headless> kai pose thinkchin/shock"),
    # QUIET: the whisper
    L("cafeteria", "kai", "close", do="^> kai pose lean/smile; Best> kai face grin"),
    # TWIST: Kai shouts, his head pops up and away
    L("cafeteria", "kai", "med low:kai@THANK",
      do="^> kai pose clap/grin; THANK> kai pose fistpump/ahh; Pop> kai pop up ahh"),
    # PAYOFF: the pile of grinning heads on the table beside Kai's body
    L("cafeteria", "kai", "med", do="^> kai pile cafeteria.spot0 -2.5 3 2.55 milo yumi brax reyes grin; "
                                       "^> kai pose shrug"),
    # CALLBACK: back home, headless Dad still cheering at the TV, his head grinning on the couch
    L("home", "dad", "close wide@Quieter", do="^> dad face grin; ^> dad pose cheer"),
]
