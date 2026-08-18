"""
Slang Word Detector - Prototype v1.0
--------------------------------------------------------------------
A from-scratch, rule-based slang detection tool. Takes free-text
user input, tokenizes it, and flags words/phrases that match a
curated slang dictionary. No external API calls, no API key needed.

Designed to be easy to extend:
  - Add new slang terms directly to the SLANG_DICTIONARY below.
  - Swap in a bigger dictionary (e.g. loaded from a CSV/JSON file)
    without changing the detection logic.
  - The dictionary structure supports multi-word phrases as well
    as single words.

Run:
    python slang_detector.py
"""

import re
import string
import json
from pathlib import Path


# ==========================================
# MODULE 1: SLANG DICTIONARY
# ==========================================
# Each entry maps a slang term -> {"meaning": str, "category": str}
# category is a free-form tag you can use for filtering/reporting
# (e.g. "internet", "regional", "youth", "offensive", etc.)
#
# This is a small starter set. Replace/extend it with your own
# curated or crowd-sourced list for real training data.

SLANG_DICTIONARY = {
    "lit": {"meaning": "exciting, excellent, or fun", "category": "general"},
    "salty": {"meaning": "bitter, annoyed, or upset", "category": "general"},
    "flex": {"meaning": "to show off", "category": "general"},
    "bet": {"meaning": "an expression of agreement or okay", "category": "general"},
    "extra": {"meaning": "over-the-top or dramatic", "category": "general"},
    "shook": {"meaning": "shocked or surprised", "category": "general"},
    "gucci": {"meaning": "good, fine, or cool", "category": "general"},
    "fam": {"meaning": "close friend or friend group", "category": "general"},
    "bruh": {"meaning": "an expression of disbelief, surprise, or annoyance", "category": "general"},
    "goat": {"meaning": "greatest of all time", "category": "general"},
    "deadass": {"meaning": "seriously or for real", "category": "general"},
    "boujee": {"meaning": "luxurious, fancy, or high-class", "category": "general"},
    "chill": {"meaning": "relaxed or calm", "category": "general"},
    "dope": {"meaning": "excellent, impressive, or cool", "category": "general"},
    "cool": {"meaning": "good, fashionable, or impressive", "category": "general"},
    "awesome": {"meaning": "very good or impressive", "category": "general"},
    "crush": {"meaning": "a person someone likes romantically", "category": "general"},
    "hangout": {"meaning": "spending casual time with someone", "category": "general"},
    "hangry": {"meaning": "angry or irritated because of hunger", "category": "general"},
    "yolo": {"meaning": "you only live once", "category": "general"},
    "swag": {"meaning": "stylish confidence or appearance", "category": "general"},
    "sick": {"meaning": "excellent or impressive", "category": "general"},
    "wicked": {"meaning": "very good or impressive", "category": "general"},
    "rad": {"meaning": "cool or excellent", "category": "general"},
    "epic": {"meaning": "extremely impressive or exciting", "category": "general"},
    "legit": {"meaning": "genuine, real, or very good", "category": "general"},
    "ace": {"meaning": "excellent or very successful", "category": "general"},
    "fire": {"meaning": "excellent, exciting, or impressive", "category": "general"},
    "bomb": {"meaning": "very good or excellent", "category": "general"},
    "banger": {"meaning": "something extremely good, especially a song", "category": "general"},
    "slaps": {"meaning": "is very good or enjoyable", "category": "general"},
    "solid": {"meaning": "good, reliable, or satisfactory", "category": "general"},
    "mint": {"meaning": "excellent or in very good condition", "category": "general"},
    "peak": {"meaning": "excellent or at the highest level", "category": "general"},
    "proper": {"meaning": "very good or impressive", "category": "general"},
    "sorted": {"meaning": "taken care of or successfully arranged", "category": "general"},
    "knackered": {"meaning": "extremely tired", "category": "regional"},
    "gutted": {"meaning": "very disappointed", "category": "regional"},
    "chuffed": {"meaning": "very pleased or happy", "category": "regional"},
    "mate": {"meaning": "friend or companion", "category": "regional"},
    "lad": {"meaning": "a young man or boy", "category": "regional"},
    "bloke": {"meaning": "a man", "category": "regional"},
    "cheers": {"meaning": "thanks or goodbye", "category": "regional"},
    "ta": {"meaning": "thank you", "category": "regional"},
    "loo": {"meaning": "toilet or bathroom", "category": "regional"},
    "quid": {"meaning": "British slang for a pound of money", "category": "regional"},
    "buck": {"meaning": "a dollar", "category": "general"},
    "bucks": {"meaning": "dollars or money", "category": "general"},
    "dough": {"meaning": "money", "category": "general"},
    "bread": {"meaning": "money", "category": "general"},
    "moolah": {"meaning": "money", "category": "general"},
    "cash": {"meaning": "money", "category": "general"},
    "stash": {"meaning": "a hidden or stored supply of something", "category": "general"},
    "rip-off": {"meaning": "something unfairly expensive or a scam", "category": "general"},
    "scam": {"meaning": "a dishonest scheme or trick", "category": "general"},
    "sus": {"meaning": "suspicious or questionable", "category": "internet"},
    "ghost": {"meaning": "to suddenly stop communicating with someone", "category": "internet"},
    "cap": {"meaning": "a lie or exaggeration", "category": "internet"},
    "no cap": {"meaning": "not lying or seriously", "category": "internet"},
    "vibe check": {"meaning": "an assessment of someone's mood or attitude", "category": "internet"},
    "simp": {"meaning": "someone who is overly attentive toward someone they like", "category": "internet"},
    "yeet": {"meaning": "to throw something forcefully or express excitement", "category": "internet"},
    "clout": {"meaning": "influence, popularity, or social status", "category": "internet"},
    "lowkey": {"meaning": "somewhat, secretly, or quietly", "category": "internet"},
    "highkey": {"meaning": "openly, strongly, or very much", "category": "internet"},
    "bussin": {"meaning": "extremely good, especially referring to food", "category": "internet"},
    "mid": {"meaning": "mediocre or average", "category": "internet"},
    "rizz": {"meaning": "charisma or ability to attract someone", "category": "internet"},
    "stan": {"meaning": "an extremely devoted fan", "category": "internet"},
    "on god": {"meaning": "seriously or I swear", "category": "internet"},
    "clapback": {"meaning": "a sharp or witty response to criticism", "category": "internet"},
    "receipts": {"meaning": "proof or evidence", "category": "internet"},
    "ratio": {"meaning": "when a response receives more positive attention than the original post", "category": "internet"},
    "based": {"meaning": "confidently expressing an opinion, often approvingly", "category": "internet"},
    "cringe": {"meaning": "embarrassing or awkward", "category": "internet"},
    "cringey": {"meaning": "embarrassing or awkward", "category": "internet"},
    "based": {"meaning": "boldly expressing an opinion or position", "category": "internet"},
    "cope": {"meaning": "an attempt to deal with an uncomfortable reality", "category": "internet"},
    "copium": {"meaning": "humorous term for unrealistic optimism or denial", "category": "internet"},
    "delulu": {"meaning": "delusional or unrealistic", "category": "internet"},
    "sus af": {"meaning": "extremely suspicious", "category": "internet"},
    "irl": {"meaning": "in real life", "category": "internet"},
    "afk": {"meaning": "away from keyboard", "category": "internet"},
    "brb": {"meaning": "be right back", "category": "internet"},
    "btw": {"meaning": "by the way", "category": "internet"},
    "idk": {"meaning": "I don't know", "category": "internet"},
    "ikr": {"meaning": "I know, right?", "category": "internet"},
    "imo": {"meaning": "in my opinion", "category": "internet"},
    "imho": {"meaning": "in my humble opinion", "category": "internet"},
    "tbh": {"meaning": "to be honest", "category": "internet"},
    "ngl": {"meaning": "not gonna lie", "category": "internet"},
    "fr": {"meaning": "for real", "category": "internet"},
    "frfr": {"meaning": "for real, for real", "category": "internet"},
    "rn": {"meaning": "right now", "category": "internet"},
    "wyd": {"meaning": "what are you doing?", "category": "internet"},
    "wbu": {"meaning": "what about you?", "category": "internet"},
    "hbu": {"meaning": "how about you?", "category": "internet"},
    "omg": {"meaning": "oh my God; expression of surprise", "category": "internet"},
    "omw": {"meaning": "on my way", "category": "internet"},
    "fyi": {"meaning": "for your information", "category": "internet"},
    "dm": {"meaning": "direct message", "category": "internet"},
    "pm": {"meaning": "private message", "category": "internet"},
    "pov": {"meaning": "point of view", "category": "internet"},
    "fomo": {"meaning": "fear of missing out", "category": "internet"},
    "jomo": {"meaning": "joy of missing out", "category": "internet"},
    "goated": {"meaning": "considered one of the greatest", "category": "internet"},
    "goated": {"meaning": "extremely excellent or legendary", "category": "internet"},
    "ate": {"meaning": "performed extremely well", "category": "internet"},
    "ate that": {"meaning": "did something extremely well", "category": "internet"},
    "left no crumbs": {"meaning": "did something exceptionally well", "category": "internet"},
    "understood the assignment": {"meaning": "performed exactly as expected or very well", "category": "internet"},
    "main character": {"meaning": "someone acting as though they are the central person in a situation", "category": "internet"},
    "main character energy": {"meaning": "confident behavior that feels like being the center of attention", "category": "internet"},
    "living rent free": {"meaning": "being unable to stop thinking about something or someone", "category": "internet"},
    "rent free": {"meaning": "occupying someone's thoughts without effort", "category": "internet"},
    "touch grass": {"meaning": "spend time offline or reconnect with reality", "category": "internet"},
    "chronically online": {"meaning": "spending excessive time online", "category": "internet"},
    "doomscrolling": {"meaning": "continuously scrolling through negative or distressing content", "category": "internet"},
    "ragebait": {"meaning": "content intentionally designed to make people angry", "category": "internet"},
    "clickbait": {"meaning": "content designed to attract clicks using a sensational title or image", "category": "internet"},
    "shitpost": {"meaning": "an intentionally silly or low-quality internet post", "category": "internet"},
    "meme": {"meaning": "an idea, image, or joke spread widely online", "category": "internet"},
    "viral": {"meaning": "spreading rapidly online", "category": "internet"},
    "cancelled": {"meaning": "socially rejected or publicly criticized", "category": "internet"},
    "cancel culture": {"meaning": "public rejection or criticism of people for controversial behavior", "category": "internet"},
    "lurker": {"meaning": "someone who reads online content without participating", "category": "internet"},
    "troll": {"meaning": "someone who deliberately provokes others online", "category": "internet"},
    "trolling": {"meaning": "deliberately provoking or annoying people online", "category": "internet"},
    "catfish": {"meaning": "someone who uses a false online identity", "category": "internet"},
    "catfishing": {"meaning": "pretending to be someone else online", "category": "internet"},
    "finsta": {"meaning": "a private or secondary Instagram account", "category": "internet"},
    "stan account": {"meaning": "an account dedicated to supporting a celebrity or fandom", "category": "internet"},
    "fanum tax": {"meaning": "playfully taking some of another person's food", "category": "internet"},
    "sigma": {"meaning": "internet slang describing an independent or self-confident person", "category": "internet"},
    "skibidi": {"meaning": "an internet meme term often used humorously or nonsensically", "category": "internet"},
    "gyatt": {"meaning": "internet slang used as an exclamation of surprise or admiration", "category": "internet"},
    "aura": {"meaning": "perceived charisma, presence, or coolness", "category": "internet"},
    "aura points": {"meaning": "humorous imaginary points representing someone's coolness or charisma", "category": "internet"},
    "NPC": {"meaning": "someone behaving predictably or without independent thought", "category": "internet"},
    "W": {"meaning": "a win or something positive", "category": "internet"},
    "L": {"meaning": "a loss, failure, or something negative", "category": "internet"},
    "W take": {"meaning": "a very good opinion", "category": "internet"},
    "L take": {"meaning": "a bad or unpopular opinion", "category": "internet"},
    "W rizz": {"meaning": "successful or impressive charisma", "category": "internet"},
    "L rizz": {"meaning": "unsuccessful or poor charisma", "category": "internet"},
    "ratioed": {"meaning": "receiving less positive response than a reply or opposing post", "category": "internet"},
    "lol": {"meaning": "laughing out loud", "category": "texting"},
    "lmao": {"meaning": "laughing very hard", "category": "texting"},
    "lmfao": {"meaning": "laughing extremely hard", "category": "texting"},
    "rofl": {"meaning": "rolling on the floor laughing", "category": "texting"},
    "jk": {"meaning": "just kidding", "category": "texting"},
    "nvm": {"meaning": "never mind", "category": "texting"},
    "np": {"meaning": "no problem", "category": "texting"},
    "ty": {"meaning": "thank you", "category": "texting"},
    "thx": {"meaning": "thanks", "category": "texting"},
    "tysm": {"meaning": "thank you so much", "category": "texting"},
    "yw": {"meaning": "you're welcome", "category": "texting"},
    "pls": {"meaning": "please", "category": "texting"},
    "plz": {"meaning": "please", "category": "texting"},
    "sry": {"meaning": "sorry", "category": "texting"},
    "msg": {"meaning": "message", "category": "texting"},
    "txt": {"meaning": "text message", "category": "texting"},
    "b4": {"meaning": "before", "category": "texting"},
    "gr8": {"meaning": "great", "category": "texting"},
    "l8r": {"meaning": "later", "category": "texting"},
    "2day": {"meaning": "today", "category": "texting"},
    "2nite": {"meaning": "tonight", "category": "texting"},
    "cya": {"meaning": "see you", "category": "texting"},
    "ttyl": {"meaning": "talk to you later", "category": "texting"},
    "ttys": {"meaning": "talk to you soon", "category": "texting"},
    "asap": {"meaning": "as soon as possible", "category": "texting"},
    "bff": {"meaning": "best friend forever", "category": "texting"},
    "bffl": {"meaning": "best friends for life", "category": "texting"},
    "ily": {"meaning": "I love you", "category": "texting"},
    "ily2": {"meaning": "I love you too", "category": "texting"},
    "xoxo": {"meaning": "hugs and kisses", "category": "texting"},
    "bae": {"meaning": "a romantic partner or someone loved", "category": "texting"},
    "bestie": {"meaning": "best friend", "category": "texting"},
    "bro": {"meaning": "friend or brother-like person", "category": "texting"},
    "sis": {"meaning": "friend or sister-like person", "category": "texting"},
    "homie": {"meaning": "close friend", "category": "texting"},
    "homie": {"meaning": "close friend or companion", "category": "texting"},
    "vibing": {"meaning": "relaxing or enjoying the atmosphere", "category": "youth"},
    "vibe": {"meaning": "a feeling, mood, or atmosphere", "category": "youth"},
    "vibes": {"meaning": "feelings, atmosphere, or mood", "category": "youth"},
    "valid": {"meaning": "reasonable, acceptable, or worthy of approval", "category": "youth"},
    "goated": {"meaning": "extremely good or considered one of the greatest", "category": "youth"},
    "iconic": {"meaning": "very memorable or highly recognizable", "category": "youth"},
    "legend": {"meaning": "an exceptionally impressive person", "category": "youth"},
    "legendary": {"meaning": "extremely impressive or memorable", "category": "youth"},
    "slay": {"meaning": "to do something extremely well", "category": "youth"},
    "slaying": {"meaning": "doing something extremely well", "category": "youth"},
    "serve": {"meaning": "to look or perform impressively", "category": "youth"},
    "serving": {"meaning": "looking or performing impressively", "category": "youth"},
    "ate": {"meaning": "performed exceptionally well", "category": "youth"},
    "period": {"meaning": "used to emphasize that a statement is final", "category": "youth"},
    "periodt": {"meaning": "emphasized form of 'period'", "category": "youth"},
    "tea": {"meaning": "gossip or interesting information", "category": "youth"},
    "spill the tea": {"meaning": "tell the gossip or reveal information", "category": "youth"},
    "tea spill": {"meaning": "sharing gossip or information", "category": "youth"},
    "sus": {"meaning": "suspicious", "category": "youth"},
    "sussy": {"meaning": "suspicious", "category": "youth"},
    "mid": {"meaning": "average or disappointing", "category": "youth"},
    "fire": {"meaning": "excellent or impressive", "category": "youth"},
    "based": {"meaning": "confident or unapologetic about an opinion", "category": "youth"},
    "cringe": {"meaning": "embarrassing or awkward", "category": "youth"},
    "cracked": {"meaning": "extremely skilled", "category": "gaming"},
    "OP": {"meaning": "overpowered or original poster depending on context", "category": "internet"},
    "goated": {"meaning": "extremely skilled or excellent", "category": "gaming"},
    "noob": {"meaning": "an inexperienced person, especially in gaming", "category": "gaming"},
    "newbie": {"meaning": "a beginner or inexperienced person", "category": "general"},
    "pro": {"meaning": "an expert or highly skilled person", "category": "general"},
    "grind": {"meaning": "to work repeatedly and consistently toward a goal", "category": "gaming"},
    "grinding": {"meaning": "working continuously toward a goal", "category": "gaming"},
    "clutch": {"meaning": "performing successfully under pressure", "category": "gaming"},
    "nerf": {"meaning": "to weaken something in a game", "category": "gaming"},
    "buff": {"meaning": "to strengthen something in a game", "category": "gaming"},
    "spawn": {"meaning": "to appear or generate in a game", "category": "gaming"},
    "camping": {"meaning": "staying in one strategic location in a game", "category": "gaming"},
    "ragequit": {"meaning": "to abruptly leave a game because of frustration", "category": "gaming"},
    "GG": {"meaning": "good game", "category": "gaming"},
    "GGWP": {"meaning": "good game, well played", "category": "gaming"},
    "AFK": {"meaning": "away from keyboard", "category": "gaming"},
    "OP": {"meaning": "overpowered in gaming", "category": "gaming"},
    "ghosting": {"meaning": "suddenly ending communication without explanation", "category": "social"},
    "ghosted": {"meaning": "having communication suddenly stopped by someone", "category": "social"},
    "breadcrumbing": {"meaning": "giving someone small amounts of attention without serious commitment", "category": "social"},
    "situationship": {"meaning": "an undefined romantic or social relationship", "category": "social"},
    "friendzone": {"meaning": "a situation where one person wants romance but the other sees them as a friend", "category": "social"},
    "red flag": {"meaning": "a warning sign of a problem", "category": "social"},
    "green flag": {"meaning": "a positive sign or desirable quality", "category": "social"},
    "ick": {"meaning": "a sudden feeling of dislike or discomfort", "category": "social"},
    "the ick": {"meaning": "a sudden feeling of aversion toward someone", "category": "social"},
    "turn-off": {"meaning": "something that causes dislike or loss of interest", "category": "social"},
    "turn-on": {"meaning": "something that increases interest or attraction", "category": "social"},
    "ship": {"meaning": "to support two people as a couple", "category": "internet"},
    "shipping": {"meaning": "supporting or imagining two people as a couple", "category": "internet"},
    "OTP": {"meaning": "one true pairing", "category": "internet"},
    "ex": {"meaning": "a former romantic partner", "category": "general"},
    "boo": {"meaning": "a term of affection for someone", "category": "general"},
    "babe": {"meaning": "a term of affection", "category": "general"},
    "bestie": {"meaning": "best friend", "category": "general"},
    "buddy": {"meaning": "friend or companion", "category": "general"},
    "pal": {"meaning": "friend", "category": "general"},
    "dude": {"meaning": "a person, usually a man or boy, or a casual way to address someone", "category": "general"},
    "no cap": {"meaning": "seriously or without lying", "category": "internet"},
    "on god": {"meaning": "I swear or seriously", "category": "internet"},
    "for real": {"meaning": "seriously or genuinely", "category": "general"},
    "for real for real": {"meaning": "very seriously or genuinely", "category": "internet"},
    "my bad": {"meaning": "my mistake", "category": "general"},
    "no worries": {"meaning": "it's okay or don't worry", "category": "general"},
    "my dude": {"meaning": "a friendly way of addressing someone", "category": "general"},
    "what's up": {"meaning": "a casual greeting asking how someone is", "category": "general"},
    "what's good": {"meaning": "a casual greeting asking how things are", "category": "general"},
    "hang tight": {"meaning": "wait for a short time", "category": "general"},
    "hit me up": {"meaning": "contact or message me", "category": "internet"},
    "hit the road": {"meaning": "leave or start traveling", "category": "general"},
    "piece of cake": {"meaning": "something very easy", "category": "general"},
    "easy peasy": {"meaning": "very easy", "category": "general"},
    "my two cents": {"meaning": "my opinion", "category": "general"},
    "spill the tea": {"meaning": "share gossip or information", "category": "internet"},
    "throw shade": {"meaning": "subtly criticize or insult someone", "category": "internet"},
    "shade": {"meaning": "subtle criticism or disrespect", "category": "internet"},
    "clap back": {"meaning": "respond sharply to criticism", "category": "internet"},
    "throw hands": {"meaning": "suggest or threaten a physical confrontation", "category": "general"},
    "catch these hands": {"meaning": "a humorous threat of confrontation", "category": "general"},
    "out of pocket": {"meaning": "inappropriate, unexpected, or excessive", "category": "internet"},
    "built different": {"meaning": "unusually capable or exceptional", "category": "internet"},
    "living my best life": {"meaning": "enjoying life to the fullest", "category": "general"},
    "that's wild": {"meaning": "expression of surprise about something unusual", "category": "general"},
    "say less": {"meaning": "I understand or agree without needing more explanation", "category": "internet"},
    "you good": {"meaning": "asking whether someone is okay", "category": "internet"},
    "we move": {"meaning": "accepting a situation and continuing forward", "category": "internet"},
    "it is what it is": {"meaning": "accepting something that cannot be changed", "category": "general"},
    "let him cook": {"meaning": "allow someone to continue because they may succeed", "category": "internet"},
    "let her cook": {"meaning": "allow someone to continue because they may succeed", "category": "internet"},
    "cooked": {"meaning": "in a difficult situation or likely to fail", "category": "internet"},
    "cooking": {"meaning": "doing something well or developing a good idea", "category": "internet"},
    "we're cooked": {"meaning": "we are in trouble or likely to fail", "category": "internet"},
    "lock in": {"meaning": "focus intensely on a task", "category": "internet"},
    "locked in": {"meaning": "highly focused or committed", "category": "internet"},
    "touch grass": {"meaning": "spend less time online and reconnect with reality", "category": "internet"},
    "rent free": {"meaning": "something that occupies someone's thoughts constantly", "category": "internet"},
    "living rent free": {"meaning": "being constantly present in someone's thoughts", "category": "internet"},
    "main character energy": {"meaning": "confident behavior suggesting someone feels central or important", "category": "internet"},
    "understood the assignment": {"meaning": "performed extremely well or exactly as expected", "category": "internet"},
    "left no crumbs": {"meaning": "performed something exceptionally well", "category": "internet"},
    "it's giving": {"meaning": "it has the appearance, feeling, or style of something", "category": "internet"},
    "giving": {"meaning": "having a particular appearance, feeling, or style", "category": "internet"},
    "periodt": {"meaning": "used to strongly emphasize that a statement is final", "category": "internet"},
    "and that's on": {"meaning": "used to strongly emphasize a statement", "category": "internet"},
    "not gonna lie": {"meaning": "used before saying something honestly", "category": "internet"},
    "to be fair": {"meaning": "used to introduce a balanced or qualifying opinion", "category": "internet"},
    "finna": {"meaning": "going to or about to", "category": "regional"},
    "gonna": {"meaning": "going to", "category": "general"},
    "wanna": {"meaning": "want to", "category": "general"},
    "gotta": {"meaning": "have to or need to", "category": "general"},
    "lemme": {"meaning": "let me", "category": "general"},
    "gimme": {"meaning": "give me", "category": "general"},
    "ain't": {"meaning": "informal form of am not, is not, are not, or have not", "category": "regional"},
    "y'all": {"meaning": "you all", "category": "regional"},
    "yup": {"meaning": "yes", "category": "general"},
    "nope": {"meaning": "no", "category": "general"},
    "nah": {"meaning": "no or disagreement", "category": "general"},
    "yeah": {"meaning": "yes or agreement", "category": "general"},
    "yep": {"meaning": "yes", "category": "general"},
    "innit": {"meaning": "informal form of isn't it, often used as a conversational tag", "category": "regional"},
    "bruv": {"meaning": "informal form of brother or friend", "category": "regional"},
    "fam": {"meaning": "close friend or group of friends", "category": "regional"},
    "peng": {"meaning": "attractive or excellent", "category": "regional"},
    "bare": {"meaning": "a lot of or very", "category": "regional"},
    "peak": {"meaning": "unfortunate or disappointing situation", "category": "regional"},
    "allow it": {"meaning": "stop it or leave it alone", "category": "regional"},
    "sorted": {"meaning": "taken care of or arranged", "category": "regional"},
    "knackered": {"meaning": "extremely tired", "category": "regional"},
    "gutted": {"meaning": "very disappointed", "category": "regional"},
    "chuffed": {"meaning": "very pleased", "category": "regional"},
    "dodgy": {"meaning": "suspicious, unreliable, or questionable", "category": "regional"},
    "skint": {"meaning": "having very little or no money", "category": "regional"},
    "cheeky": {"meaning": "slightly rude or playfully disrespectful", "category": "regional"},
    "taking the mick": {"meaning": "making fun of someone or not being serious", "category": "regional"},
    "banter": {"meaning": "playful teasing or joking", "category": "regional"},
    "mate": {"meaning": "friend", "category": "regional"},
    "bloke": {"meaning": "man", "category": "regional"},
    "lass": {"meaning": "girl or young woman", "category": "regional"},
    "quid": {"meaning": "British pound", "category": "regional"},
    "nosh": {"meaning": "food or a snack", "category": "regional"},
    "cuppa": {"meaning": "a cup of tea", "category": "regional"},
    "loo": {"meaning": "toilet", "category": "regional"},
    "brolly": {"meaning": "umbrella", "category": "regional"},
    "chippy": {"meaning": "fish-and-chip shop", "category": "regional"},
    "noob": {"meaning": "an inexperienced player", "category": "gaming"},
    "newbie": {"meaning": "a beginner", "category": "gaming"},
    "pro": {"meaning": "a highly skilled player", "category": "gaming"},
    "bot": {"meaning": "a computer-controlled player or someone behaving predictably", "category": "gaming"},
    "NPC": {"meaning": "a non-player character or someone behaving predictably", "category": "gaming"},
    "OP": {"meaning": "overpowered", "category": "gaming"},
    "nerf": {"meaning": "to weaken a game feature", "category": "gaming"},
    "buff": {"meaning": "to strengthen a game feature", "category": "gaming"},
    "clutch": {"meaning": "a successful action under pressure", "category": "gaming"},
    "carry": {"meaning": "to lead a team to victory", "category": "gaming"},
    "carried": {"meaning": "being helped by a stronger player", "category": "gaming"},
    "grind": {"meaning": "repeatedly playing or working to improve or gain rewards", "category": "gaming"},
    "grinding": {"meaning": "repeatedly working toward a goal", "category": "gaming"},
    "spawn": {"meaning": "to appear in a game", "category": "gaming"},
    "respawn": {"meaning": "to appear again after being eliminated", "category": "gaming"},
    "camp": {"meaning": "stay in one strategic location", "category": "gaming"},
    "camper": {"meaning": "a player who stays in one location", "category": "gaming"},
    "ragequit": {"meaning": "leave a game suddenly because of frustration", "category": "gaming"},
    "GG": {"meaning": "good game", "category": "gaming"},
    "GGWP": {"meaning": "good game, well played", "category": "gaming"},
    "EZ": {"meaning": "easy; often used to taunt after winning", "category": "gaming"},
    "AFK": {"meaning": "away from keyboard", "category": "gaming"},
    "DPS": {"meaning": "damage per second", "category": "gaming"},
    "HP": {"meaning": "health points", "category": "gaming"},
    "XP": {"meaning": "experience points", "category": "gaming"},
    "loot": {"meaning": "items collected in a game", "category": "gaming"},
    "drop": {"meaning": "an item or reward that appears in a game", "category": "gaming"},
    "meta": {"meaning": "the most effective current strategy or approach", "category": "gaming"},
    "sweat": {"meaning": "a highly competitive or serious player", "category": "gaming"},
    "sweaty": {"meaning": "extremely competitive", "category": "gaming"},
    "tryhard": {"meaning": "someone who puts excessive effort into winning", "category": "gaming"},
    "smurf": {"meaning": "an experienced player using a lower-level account", "category": "gaming"},
    "one-shot": {"meaning": "defeat someone with a single attack", "category": "gaming"},
    "headshot": {"meaning": "a successful shot targeting an opponent's head in a game", "category": "gaming"},
    "combo": {"meaning": "a sequence of attacks or actions", "category": "gaming"},
    "lag": {"meaning": "delay between an action and its response in an online game", "category": "gaming"},
    "ping": {"meaning": "network response time in an online game", "category": "gaming"},
    "freshie": {"meaning": "a new student, especially a first-year student", "category": "youth"},
    "senior": {"meaning": "an older or more advanced student", "category": "general"},
    "junior": {"meaning": "a younger or less advanced student", "category": "general"},
    "prof": {"meaning": "short form of professor", "category": "general"},
    "stats": {"meaning": "statistics or numerical information", "category": "general"},
    "bio": {"meaning": "short form of biography or biology depending on context", "category": "general"},
    "calc": {"meaning": "short form of calculus or calculator depending on context", "category": "general"},
    "lab": {"meaning": "laboratory or practical class", "category": "general"},
    "assignment": {"meaning": "a task given for study or work", "category": "general"},
    "cram": {"meaning": "study intensively in a short period", "category": "general"},
    "cramming": {"meaning": "studying intensively shortly before an exam", "category": "general"},
    "burnout": {"meaning": "extreme exhaustion from prolonged stress or work", "category": "general"},
    "procrastinate": {"meaning": "delay doing something that needs to be done", "category": "general"},
    "procrastinating": {"meaning": "delaying a task", "category": "general"},
    "bussin": {"meaning": "extremely delicious or good, especially food", "category": "food"},
    "snack": {"meaning": "someone considered attractive", "category": "general"},
    "munchies": {"meaning": "a strong desire for food", "category": "general"},
    "grub": {"meaning": "food", "category": "general"},
    "nosh": {"meaning": "food or a snack", "category": "regional"},
    "booze": {"meaning": "alcoholic drinks", "category": "general"},
    "party": {"meaning": "a social gathering or celebration", "category": "general"},
    "rager": {"meaning": "a large or energetic party", "category": "general"},
    "pre-game": {"meaning": "socializing or preparing before an event", "category": "general"},
    "afterparty": {"meaning": "a party held after a main event", "category": "general"},
    "turnt": {"meaning": "very excited or energetic at a social event", "category": "general"},
    "lit": {"meaning": "very exciting or energetic", "category": "general"},
    "vibing": {"meaning": "relaxing and enjoying the atmosphere", "category": "general"},
    "what's up": {"meaning": "a casual greeting", "category": "general"},
    "what's good": {"meaning": "a casual greeting asking how things are", "category": "general"},
    "my bad": {"meaning": "my mistake", "category": "general"},
    "no biggie": {"meaning": "not a big problem", "category": "general"},
    "no big deal": {"meaning": "something that is not important or serious", "category": "general"},
    "my bad": {"meaning": "an informal apology for a mistake", "category": "general"},
    "good vibes": {"meaning": "positive feelings or atmosphere", "category": "general"},
    "bad vibes": {"meaning": "negative or uncomfortable feelings", "category": "general"},
    "vibe check": {"meaning": "checking someone's mood or attitude", "category": "internet"},
    "on point": {"meaning": "excellent, accurate, or appropriate", "category": "general"},
    "off the hook": {"meaning": "free from responsibility or trouble", "category": "general"},
    "under the weather": {"meaning": "feeling unwell", "category": "general"},
    "break a leg": {"meaning": "a phrase meaning good luck", "category": "general"},
    "hit the sack": {"meaning": "go to bed", "category": "general"},
    "crash": {"meaning": "go to sleep or stay somewhere temporarily", "category": "general"},
    "chill out": {"meaning": "relax or calm down", "category": "general"},
    "hang loose": {"meaning": "relax or stay calm", "category": "general"},
    "piece of cake": {"meaning": "something very easy", "category": "general"},
    "once in a blue moon": {"meaning": "something that happens very rarely", "category": "general"},
    "hit the nail on the head": {"meaning": "describe something exactly correctly", "category": "general"},
    "spill the beans": {"meaning": "reveal secret information", "category": "general"},
    "blow off": {"meaning": "ignore, reject, or skip something", "category": "general"},
    "blown away": {"meaning": "extremely impressed or surprised", "category": "general"},
    "freak out": {"meaning": "become extremely upset or excited", "category": "general"},
    "mess up": {"meaning": "make a mistake", "category": "general"},
    "screw up": {"meaning": "make a mistake", "category": "general"},
    "figure out": {"meaning": "understand or solve something", "category": "general"},
    "check out": {"meaning": "look at or examine something", "category": "general"},
    "hang out": {"meaning": "spend casual time with someone", "category": "general"},
    "show off": {"meaning": "display something proudly to impress others", "category": "general"},
    "calm down": {"meaning": "become less upset or excited", "category": "general"},
    "cheer up": {"meaning": "become happier", "category": "general"},
    "back off": {"meaning": "move away or stop interfering", "category": "general"},
    "cut it out": {"meaning": "stop doing something annoying", "category": "general"},
    "give me a break": {"meaning": "expression of disbelief or annoyance", "category": "general"},
    "get over it": {"meaning": "move past a problem or disappointment", "category": "general"},
    "whatever": {"meaning": "expression of indifference or dismissal", "category": "general"},
    "seriously": {"meaning": "used to emphasize truth or disbelief", "category": "general"},
    "totally": {"meaning": "completely or strongly", "category": "general"},
    "literally": {"meaning": "used informally for emphasis", "category": "general"},
}


# ==========================================
# MODULE 2: TEXT PREPROCESSING
# ==========================================

def normalize_text(text):
    """Lowercase and strip surrounding whitespace, keep basic punctuation
    for phrase matching but normalize repeated spaces."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text):
    """Split into word tokens, stripping punctuation from each token
    (but not from the text used for phrase matching)."""
    cleaned = text.translate(str.maketrans("", "", string.punctuation))
    return cleaned.split()


# ==========================================
# MODULE 3: DETECTION LOGIC
# ==========================================

def build_lookup(dictionary):
    """Split dictionary keys into single-word and multi-word (phrase)
    entries so we can check phrases first (longest match) then words."""
    single_word = {}
    phrases = {}
    for term, info in dictionary.items():
        term_norm = term.lower().strip()
        if " " in term_norm:
            phrases[term_norm] = info
        else:
            single_word[term_norm] = info
    return single_word, phrases


def detect_slang(text, dictionary=SLANG_DICTIONARY):
    """
    Detects slang terms in the given text.
    Returns a list of matches, each a dict with:
        term, meaning, category, start_char, end_char
    Phrase matches are checked first so multi-word slang (e.g. "no cap")
    isn't just partially matched by its component words.
    """
    single_word, phrases = build_lookup(dictionary)
    normalized = normalize_text(text)

    matches = []
    covered_spans = []  # character ranges already claimed by a phrase match

    # 1. Phrase matches (longest phrases first to avoid partial overlaps)
    for phrase in sorted(phrases.keys(), key=len, reverse=True):
        for m in re.finditer(r"\b" + re.escape(phrase) + r"\b", normalized):
            start, end = m.span()
            # skip if this span overlaps an already-claimed span
            if any(not (end <= s or start >= e) for s, e in covered_spans):
                continue
            info = phrases[phrase]
            matches.append({
                "term": phrase,
                "meaning": info["meaning"],
                "category": info["category"],
                "start_char": start,
                "end_char": end,
            })
            covered_spans.append((start, end))

    # 2. Single-word matches, skipping anything inside a phrase span
    for m in re.finditer(r"\b[\w']+\b", normalized):
        word = m.group().strip(string.punctuation)
        start, end = m.span()
        if any(not (end <= s or start >= e) for s, e in covered_spans):
            continue
        if word in single_word:
            info = single_word[word]
            matches.append({
                "term": word,
                "meaning": info["meaning"],
                "category": info["category"],
                "start_char": start,
                "end_char": end,
            })

    # Sort matches by position in the text for readable output
    matches.sort(key=lambda m: m["start_char"])
    return matches


# ==========================================
# MODULE 4: REPORTING
# ==========================================

def build_report(text, matches):
    lines = []
    lines.append("=" * 60)
    lines.append("  SLANG DETECTION REPORT")
    lines.append("=" * 60)
    lines.append(f"\nInput text:\n  \"{text}\"\n")

    if not matches:
        lines.append("No slang terms detected.")
        lines.append("=" * 60)
        return "\n".join(lines)

    lines.append(f"Detected {len(matches)} slang term(s):\n")
    for i, m in enumerate(matches, start=1):
        lines.append(f"{i}. \"{m['term']}\"")
        lines.append(f"   Meaning  : {m['meaning']}")
        lines.append(f"   Category : {m['category']}")
        lines.append(f"   Position : chars {m['start_char']}-{m['end_char']}")
        lines.append("")

    categories = {}
    for m in matches:
        categories[m["category"]] = categories.get(m["category"], 0) + 1
    lines.append("Category breakdown:")
    for cat, count in categories.items():
        lines.append(f"   {cat}: {count}")

    lines.append("=" * 60)
    return "\n".join(lines)


# ==========================================
# MODULE 5: DICTIONARY PERSISTENCE (optional helpers)
# ==========================================

def save_dictionary(path, dictionary=SLANG_DICTIONARY):
    """Save the current dictionary to a JSON file so it can be
    edited, versioned, or swapped out without touching this script."""
    Path(path).write_text(json.dumps(dictionary, indent=2), encoding="utf-8")


def load_dictionary(path):
    """Load a slang dictionary from a JSON file. Falls back to the
    built-in SLANG_DICTIONARY if the file doesn't exist."""
    p = Path(path)
    if not p.exists():
        return SLANG_DICTIONARY
    return json.loads(p.read_text(encoding="utf-8"))


# ==========================================
# MODULE 6: MAIN LOOP (interactive user input)
# ==========================================

def main():
    print("Slang Word Detector (prototype)")
    print("Type a sentence to scan for slang, or 'quit' to exit.\n")

    dictionary = SLANG_DICTIONARY

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.lower() in {"quit", "exit", "q"}:
            print("Exiting.")
            break

        if not user_input:
            continue

        matches = detect_slang(user_input, dictionary)
        report = build_report(user_input, matches)
        print("\n" + report + "\n")


if __name__ == "__main__":
    main()