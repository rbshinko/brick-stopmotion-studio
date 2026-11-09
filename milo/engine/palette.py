"""The channel's fixed sound palette, picked once from my-sounds/ (paths relative to my-sounds/).
credit=None means no credit needed (CC0 or Sonniss GDC); otherwise the line goes in the description."""
import os
SOUNDS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "my-sounds")
KIT = "sfx/sfx-kit/sounds/"
GDC = "sfx/gdc26/Sonniss.com-GDC2026-GameAudioBundle/"
OCULUS = "Sound effects: Oculus Audio Pack (Meta), CC BY 4.0"
SFX = {
    "pop1": (KIT + "pops/pop-small-in.wav", None),
    "pop2": (KIT + "pops/pop-medium-in.wav", None),
    "sparkle": (KIT + "shimmers/shimmer-short-sparkle.wav", None),
    "whoosh": (KIT + "swishes-and-zips/swish-medium.wav", None),
    "whoosh2": (KIT + "swishes-and-zips/swish-soft.wav", None),
    "impact": (KIT + "impacts/impact-deep-firm.wav", None),
    "boing": (KIT + "bounce-spin-zoom/move-spring.wav", None),
    "zip": (KIT + "swishes-and-zips/zip-in-hard.wav", None),
    "snip": (KIT + "everyday-props/props-scissors.wav", None),
    "ding": (KIT + "tones/tone-ding-high.wav", None),
    "doorbell": (KIT + "everyday-props/props-doorbell.wav", None),
    "knock": (KIT + "notifications/notification-failure-knock.wav", None),
    "sting": (KIT + "logo-stings/sting-warm-long.wav", None),
    "slap": ("sfx/own/slap-face.wav", None),
    "gasp": (GDC + "Epic Stock Media - AAA Game Character Police Officer/HMNBrth_Police Officer Gasp Vocal Male Shocked Alert 1.wav", None),
    "cough": (GDC + "Epic Stock Media - AAA Game Character Police Officer/HMNCough_Police Officer Cough Vocal Male 11.wav", None),
    "laugh": (GDC + "SoundBits - Vox Hominis - Human Effort Voices/VOXLaff_Laughing Female 02 06_SNDBTS_VH.wav", None),
    "whistle": (GDC + "SoundBits - Vox Hominis - Human Effort Voices/WHSTHmn_Whistle Male 06 09_SNDBTS_VH.wav", None),
    "squeak": (GDC + "Epic Stock Media - HD Game Materials/ICEFric_Dry Ice Squeak Metal Animal Mouse Imitation Short 07_ESM_HDGM.wav", None),
    "crack": (GDC + "Alexander Kopeikin - 100 kHz Designed Ice/ice, crack, ice block snapping-001.wav", None),
    "growl": (GDC + "Cinematic Sound Design - Cartoon & Animation Vol 2/Cartoon Transition Bass Down.wav", None),
    "bubbles": (GDC + "Cinematic Sound Design - Cartoon & Animation Vol 2/Cartoon Bubbles Short.wav", None),
    "dizzy": (GDC + "Cinematic Sound Design - Cartoon Bloopers/Cartoon Confused Dizzy.wav", None),
    "chicken": ("sfx/Meta-open-sound/corpora/oculus-audio-pack/ogg/BIRDFowl_Chicken_OS_01.ogg", OCULUS),
}
MUSIC = {
    "island": (os.path.join("..", "milo", "assets", "dl_audio", "music", "island_0.ogg"), None),
    "riley": ("music/incompetech/uplifting/Life of Riley.mp3",
              '"Life of Riley" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/'),
}


def path(rel):
    return os.path.normpath(os.path.join(SOUNDS, rel))
