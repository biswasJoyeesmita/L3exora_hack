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
        # ============================================================ 
    # INTERNET / SOCIAL MEDIA SLANG 
    # ============================================================ 
 
    "lit": { 
        "meaning": "exciting, excellent, or impressive", 
        "category": "internet" 
    }, 
 
    "salty": { 
        "meaning": "bitter, annoyed, or upset about something", 
        "category": "internet" 
    }, 
 
    "sus": { 
        "meaning": "suspicious or questionable", 
        "category": "internet" 
    }, 
 
    "sussy": { 
        "meaning": "suspicious or questionable", 
        "category": "internet" 
    }, 
 
    "flex": { 
        "meaning": "to show off", 
        "category": "internet" 
    }, 
 
    "flexing": { 
        "meaning": "showing off", 
        "category": "internet" 
    }, 
 
    "ghost": { 
        "meaning": "to suddenly stop communicating with someone", 
        "category": "internet" 
    }, 
 
    "ghosting": { 
        "meaning": "suddenly ending communication without explanation", 
        "category": "internet" 
    }, 
 
    "ghosted": { 
        "meaning": "having communication suddenly stopped by someone", 
        "category": "internet" 
    }, 
 
    "cap": { 
        "meaning": "a lie or exaggeration", 
        "category": "internet" 
    }, 
 
    "capping": { 
        "meaning": "lying or exaggerating", 
        "category": "internet" 
    }, 
 
    "no cap": { 
        "meaning": "seriously or without lying", 
        "category": "internet" 
    }, 
 
    "bet": { 
        "meaning": "an expression meaning okay, agreed, or sure", 
        "category": "internet" 
    }, 
 
    "vibe": { 
        "meaning": "mood, feeling, or atmosphere", 
        "category": "internet" 
    }, 
 
    "vibes": { 
        "meaning": "moods, feelings, or atmosphere", 
        "category": "internet" 
    }, 
 
    "vibing": { 
        "meaning": "relaxing and enjoying the atmosphere", 
        "category": "internet" 
    }, 
 
    "simp": { 
        "meaning": "someone excessively attentive toward a person they like", 
        "category": "internet" 
    }, 
 
    "simping": { 
        "meaning": "showing excessive attention toward someone", 
        "category": "internet" 
    }, 
 
    "yeet": { 
        "meaning": "to throw something forcefully or express excitement", 
        "category": "internet" 
    }, 
 
    "shook": { 
        "meaning": "shocked or surprised", 
        "category": "internet" 
    }, 
 
    "clout": { 
        "meaning": "influence, popularity, or social status", 
        "category": "internet" 
    }, 
 
    "clout chasing": { 
        "meaning": "trying to gain popularity or attention", 
        "category": "internet" 
    }, 
 
    "mid": { 
        "meaning": "mediocre or average", 
        "category": "internet" 
    }, 
 
    "rizz": { 
        "meaning": "charisma or social charm", 
        "category": "internet" 
    }, 
 
    "goated": { 
        "meaning": "extremely good or considered one of the greatest", 
        "category": "internet" 
    }, 
 
    "goat": { 
        "meaning": "greatest of all time", 
        "category": "internet" 
    }, 
 
    "stan": { 
        "meaning": "an extremely devoted fan", 
        "category": "internet" 
    }, 
 
    "stanning": { 
        "meaning": "strongly supporting or following someone", 
        "category": "internet" 
    }, 
 
    "on god": { 
        "meaning": "seriously or I swear", 
        "category": "internet" 
    }, 
 
    "deadass": { 
        "meaning": "seriously or genuinely", 
        "category": "internet" 
    }, 
 
    "lowkey": { 
        "meaning": "somewhat, secretly, or quietly", 
        "category": "internet" 
    }, 
 
    "highkey": { 
        "meaning": "openly, strongly, or very much", 
        "category": "internet" 
    }, 
 
    "extra": { 
        "meaning": "over-the-top, dramatic, or excessive", 
        "category": "internet" 
    }, 
 
    "boujee": { 
        "meaning": "luxurious, high-class, or fancy", 
        "category": "internet" 
    }, 
 
    "clapback": { 
        "meaning": "a strong or witty response to criticism", 
        "category": "internet" 
    }, 
 
    "receipts": { 
        "meaning": "proof or evidence", 
        "category": "internet" 
    }, 
 
    "tea": { 
        "meaning": "gossip or interesting information", 
        "category": "internet" 
    }, 
 
    "spill the tea": { 
        "meaning": "share gossip or information", 
        "category": "internet" 
    }, 
 
    "shade": { 
        "meaning": "subtle criticism or disrespect", 
        "category": "internet" 
    }, 
 
    "throw shade": { 
        "meaning": "to subtly criticize or insult someone", 
        "category": "internet" 
    }, 
 
    "roast": { 
        "meaning": "to make fun of someone humorously", 
        "category": "internet" 
    }, 
 
    "roasting": { 
        "meaning": "making fun of someone humorously", 
        "category": "internet" 
    }, 
 
    "troll": { 
        "meaning": "a person who deliberately provokes others online", 
        "category": "internet" 
    }, 
 
    "trolling": { 
        "meaning": "deliberately provoking or annoying people online", 
        "category": "internet" 
    }, 
 
    "triggered": { 
        "meaning": "strongly upset or angered by something", 
        "category": "internet" 
    }, 
 
    "cringe": { 
        "meaning": "embarrassing, awkward, or uncomfortable", 
        "category": "internet" 
    }, 
 
    "cringey": { 
        "meaning": "embarrassing or awkward", 
        "category": "internet" 
    }, 
 
    "based": { 
        "meaning": "used to express approval of a confident opinion", 
        "category": "internet" 
    }, 
 
    "ratio": { 
        "meaning": "when a reply receives more positive engagement than the original post", 
        "category": "internet" 
    }, 
 
    "ratioed": { 
        "meaning": "receiving less positive engagement than a reply", 
        "category": "internet" 
    }, 
 
    "viral": { 
        "meaning": "spreading rapidly online", 
        "category": "internet" 
    }, 
 
    "trending": { 
        "meaning": "currently popular or widely discussed", 
        "category": "internet" 
    }, 
 
    "cancelled": { 
        "meaning": "widely criticized or boycotted online", 
        "category": "internet" 
    }, 
 
    "cancel culture": { 
        "meaning": "online practice of collectively criticizing or boycotting people or organizations", 
        "category": "internet" 
    }, 
 
    "doomscrolling": { 
        "meaning": "continuously consuming negative online content", 
        "category": "internet" 
    }, 
 
    "clickbait": { 
        "meaning": "content designed to attract clicks using exaggerated claims", 
        "category": "internet" 
    }, 
 
    "engagement bait": { 
        "meaning": "content designed to artificially encourage likes, comments, or shares", 
        "category": "internet" 
    }, 
 
    "rage bait": { 
        "meaning": "content deliberately designed to provoke anger", 
        "category": "internet" 
    }, 
 
    "ragebait": { 
        "meaning": "content deliberately designed to provoke anger", 
        "category": "internet" 
    }, 
 
    "bait": { 
        "meaning": "content intended to provoke a reaction", 
        "category": "internet" 
    }, 
 
    "meme": { 
        "meaning": "a humorous piece of internet culture that is widely shared", 
        "category": "internet" 
    }, 
 
    "memes": { 
        "meaning": "widely shared humorous internet content", 
        "category": "internet" 
    }, 
 
    "shitpost": { 
        "meaning": "intentionally absurd, low-quality, or humorous online content", 
        "category": "internet" 
    }, 
 
    "shitposting": { 
        "meaning": "posting intentionally absurd or provocative content", 
        "category": "internet" 
    }, 
 
    "FOMO": { 
        "meaning": "fear of missing out", 
        "category": "internet" 
    }, 
 
    "YOLO": { 
        "meaning": "you only live once; used to justify taking a chance", 
        "category": "internet" 
    }, 
 
    "IRL": { 
        "meaning": "in real life", 
        "category": "internet" 
    }, 
 
    "AFK": { 
        "meaning": "away from keyboard", 
        "category": "internet" 
    }, 
 
    "DM": { 
        "meaning": "direct message", 
        "category": "internet" 
    }, 
 
    "PM": { 
        "meaning": "private message", 
        "category": "internet" 
    }, 
 
    "AMA": { 
        "meaning": "ask me anything", 
        "category": "internet" 
    }, 
 
    "TLDR": { 
        "meaning": "too long; didn't read", 
        "category": "internet" 
    }, 
 
    "TL;DR": { 
        "meaning": "a short summary of a longer text", 
        "category": "internet" 
    }, 
 
    "NSFW": { 
        "meaning": "not safe for work", 
        "category": "internet" 
    }, 
 
 
    # ============================================================ 
    # TEXTING / CHAT SLANG 
    # ============================================================ 
 
    "LOL": { 
        "meaning": "laughing out loud", 
        "category": "texting" 
    }, 
 
    "LMAO": { 
        "meaning": "laughing very hard", 
        "category": "texting" 
    }, 
 
    "ROFL": { 
        "meaning": "rolling on the floor laughing", 
        "category": "texting" 
    }, 
 
    "OMG": { 
        "meaning": "expression of surprise or shock", 
        "category": "texting" 
    }, 
 
    "WTF": { 
        "meaning": "expression of strong surprise, confusion, or anger", 
        "category": "texting" 
    }, 
 
    "WTH": { 
        "meaning": "expression of surprise, confusion, or annoyance", 
        "category": "texting" 
    }, 
 
    "IDK": { 
        "meaning": "I don't know", 
        "category": "texting" 
    }, 
 
    "IDC": { 
        "meaning": "I don't care", 
        "category": "texting" 
    }, 
 
    "IMO": { 
        "meaning": "in my opinion", 
        "category": "texting" 
    }, 
 
    "IMHO": { 
        "meaning": "in my humble opinion", 
        "category": "texting" 
    }, 
 
    "TBH": { 
        "meaning": "to be honest", 
        "category": "texting" 
    }, 
 
    "NGL": { 
        "meaning": "not gonna lie", 
        "category": "texting" 
    }, 
 
    "FR": { 
        "meaning": "for real", 
        "category": "texting" 
    }, 
 
    "FRFR": { 
        "meaning": "for real, seriously", 
        "category": "texting" 
    }, 
 
    "RN": { 
        "meaning": "right now", 
        "category": "texting" 
    }, 
 
    "BRB": { 
        "meaning": "be right back", 
        "category": "texting" 
    }, 
 
    "BTW": { 
        "meaning": "by the way", 
        "category": "texting" 
    }, 
 
    "FYI": { 
        "meaning": "for your information", 
        "category": "texting" 
    }, 
 
    "JK": { 
        "meaning": "just kidding", 
        "category": "texting" 
    }, 
 
    "JKLOL": { 
        "meaning": "just kidding, laughing", 
        "category": "texting" 
    }, 
 
    "TY": { 
        "meaning": "thank you", 
        "category": "texting" 
    }, 
 
    "THX": { 
        "meaning": "thanks", 
        "category": "texting" 
    }, 
 
    "NP": { 
        "meaning": "no problem", 
        "category": "texting" 
    }, 
 
    "YW": { 
        "meaning": "you're welcome", 
        "category": "texting" 
    }, 
 
    "BFF": { 
        "meaning": "best friend forever", 
        "category": "texting" 
    }, 
 
    "ILY": { 
        "meaning": "I love you", 
        "category": "texting" 
    }, 
 
    "TTYL": { 
        "meaning": "talk to you later", 
        "category": "texting" 
    }, 
 
    "GTG": { 
        "meaning": "got to go", 
        "category": "texting" 
    }, 
 
    "G2G": { 
        "meaning": "got to go", 
        "category": "texting" 
    }, 
 
    "WBU": { 
        "meaning": "what about you", 
        "category": "texting" 
    }, 
 
    "HBU": { 
        "meaning": "how about you", 
        "category": "texting" 
    }, 
 
    "LMK": { 
        "meaning": "let me know", 
        "category": "texting" 
    }, 
 
    "OMW": { 
        "meaning": "on my way", 
        "category": "texting" 
    }, 
 
    "ASAP": { 
        "meaning": "as soon as possible", 
        "category": "texting" 
    }, 
 
 
    # ============================================================ 
    # YOUTH / MODERN SLANG 
    # ============================================================ 
 
    "slay": { 
        "meaning": "to perform extremely well or look impressive", 
        "category": "youth" 
    }, 
 
    "slaying": { 
        "meaning": "performing extremely well", 
        "category": "youth" 
    }, 
 
    "fire": { 
        "meaning": "excellent, exciting, or impressive", 
        "category": "youth" 
    }, 
 
    "bussin": { 
        "meaning": "extremely good, especially describing food", 
        "category": "youth" 
    }, 
 
    "period": { 
        "meaning": "used to emphasize that a statement is final", 
        "category": "youth" 
    }, 
 
    "periodt": { 
        "meaning": "strongly emphasized form of period", 
        "category": "youth" 
    }, 
 
    "delulu": { 
        "meaning": "delusional or unrealistic", 
        "category": "youth" 
    }, 
 
    "aura": { 
        "meaning": "perceived charisma, confidence, or presence", 
        "category": "youth" 
    }, 
 
    "sigma": { 
        "meaning": "internet term for an independent or self-confident person", 
        "category": "youth" 
    }, 
 
    "alpha": { 
        "meaning": "internet term describing someone perceived as dominant or confident", 
        "category": "youth" 
    }, 
 
    "NPC": { 
        "meaning": "a person perceived as behaving without independent thought", 
        "category": "youth" 
    }, 
 
    "main character": { 
        "meaning": "someone behaving as though they are the center of attention", 
        "category": "youth" 
    }, 
 
    "main character energy": { 
        "meaning": "confident behavior suggesting someone feels like the center of attention", 
        "category": "youth" 
    }, 
 
    "touch grass": { 
        "meaning": "telling someone to spend less time online and reconnect with reality", 
        "category": "youth" 
    }, 
 
    "rent free": { 
        "meaning": "something constantly occupying someone's thoughts", 
        "category": "youth" 
    }, 
 
    "locked in": { 
        "meaning": "highly focused or committed", 
        "category": "youth" 
    }, 
 
    "lock in": { 
        "meaning": "to focus intensely on something", 
        "category": "youth" 
    }, 
 
    "cooked": { 
        "meaning": "being in trouble, exhausted, or in a difficult situation", 
        "category": "youth" 
    }, 
 
    "cooking": { 
        "meaning": "doing something well or developing a good idea", 
        "category": "youth" 
    }, 
 
    "let him cook": { 
        "meaning": "allow someone to continue developing or demonstrating an idea", 
        "category": "youth" 
    }, 
 
    "ate": { 
        "meaning": "performed extremely well", 
        "category": "youth" 
    }, 
 
    "ate that": { 
        "meaning": "performed something exceptionally well", 
        "category": "youth" 
    }, 
 
    "understood the assignment": { 
        "meaning": "successfully did exactly what was expected", 
        "category": "youth" 
    }, 
 
    "it's giving": { 
        "meaning": "it has the feeling or appearance of something", 
        "category": "youth" 
    }, 
 
    "giving": { 
        "meaning": "having a particular appearance, mood, or impression", 
        "category": "youth" 
    }, 
 
    "ick": { 
        "meaning": "a sudden feeling of dislike or discomfort", 
        "category": "youth" 
    }, 
 
    "red flag": { 
        "meaning": "a warning sign of a potential problem", 
        "category": "youth" 
    }, 
 
    "green flag": { 
        "meaning": "a positive or desirable sign", 
        "category": "youth" 
    }, 
 
    "situationship": { 
        "meaning": "an undefined or informal romantic relationship", 
        "category": "youth" 
    }, 
 
 
    # ============================================================ 
    # GAMING SLANG 
    # ============================================================ 
 
    "noob": { 
        "meaning": "an inexperienced player or newcomer", 
        "category": "gaming" 
    }, 
 
    "newbie": { 
        "meaning": "a newcomer or inexperienced person", 
        "category": "gaming" 
    }, 
 
    "pro": { 
        "meaning": "an expert or highly skilled player", 
        "category": "gaming" 
    }, 
 
    "tryhard": { 
        "meaning": "someone who puts excessive effort into winning", 
        "category": "gaming" 
    }, 
 
    "sweaty": { 
        "meaning": "extremely competitive or serious about winning", 
        "category": "gaming" 
    }, 
 
    "OP": { 
        "meaning": "overpowered or unusually strong", 
        "category": "gaming" 
    }, 
 
    "nerf": { 
        "meaning": "to weaken a game feature or character", 
        "category": "gaming" 
    }, 
 
    "buff": { 
        "meaning": "to strengthen a game feature or character", 
        "category": "gaming" 
    }, 
 
    "camping": { 
        "meaning": "staying in one location to gain a strategic advantage", 
        "category": "gaming" 
    }, 
 
    "camper": { 
        "meaning": "a player who stays in one location strategically", 
        "category": "gaming" 
    }, 
 
    "grind": { 
        "meaning": "repeatedly doing tasks to gain progress or rewards", 
        "category": "gaming" 
    }, 
 
    "grinding": { 
        "meaning": "repeatedly performing tasks for progress or rewards", 
        "category": "gaming" 
    }, 
 
    "GG": { 
        "meaning": "good game", 
        "category": "gaming" 
    }, 
 
    "GGWP": { 
        "meaning": "good game, well played", 
        "category": "gaming" 
    }, 
 
    "AFK": { 
        "meaning": "away from keyboard", 
        "category": "gaming" 
    }, 
 
    "rage quit": { 
        "meaning": "to abruptly leave a game because of frustration", 
        "category": "gaming" 
    }, 
 
    "ragequit": { 
        "meaning": "to abruptly leave a game because of frustration", 
        "category": "gaming" 
    }, 
 
    "spawn": { 
        "meaning": "to appear or reappear in a game", 
        "category": "gaming" 
    }, 
 
    "respawn": { 
        "meaning": "to appear again after being eliminated", 
        "category": "gaming" 
    }, 
 
    "loot": { 
        "meaning": "items collected in a game", 
        "category": "gaming" 
    }, 
 
    "griefer": { 
        "meaning": "a player who intentionally disrupts others' gameplay", 
        "category": "gaming" 
    }, 
 
    "griefing": { 
        "meaning": "intentionally disrupting other players", 
        "category": "gaming" 
    }, 
 
    "carry": { 
        "meaning": "to contribute most of the success of a team", 
        "category": "gaming" 
    }, 
 
    "carried": { 
        "meaning": "being helped significantly by a stronger teammate", 
        "category": "gaming" 
    }, 
 
    "clutch": { 
        "meaning": "performing successfully under pressure", 
        "category": "gaming" 
    }, 
 
    "one-shot": { 
        "meaning": "defeating an opponent with one attack", 
        "category": "gaming" 
    }, 
 
    "meta": { 
        "meaning": "the most effective current strategy or approach", 
        "category": "gaming" 
    }, 
 
    "DPS": { 
        "meaning": "damage per second", 
        "category": "gaming" 
    }, 
 
 
    # ============================================================ 
    # INDIAN ENGLISH / INDIAN INTERNET SLANG 
    # ============================================================ 
 
    "jugaad": { 
        "meaning": "an improvised or clever solution", 
        "category": "indian" 
    }, 
 
    "jugaadu": { 
        "meaning": "a person skilled at finding improvised solutions", 
        "category": "indian" 
    }, 
 
    "bakwaas": { 
        "meaning": "nonsense, rubbish, or something of poor quality", 
        "category": "indian" 
    }, 
 
    "timepass": { 
        "meaning": "an activity done mainly to pass time", 
        "category": "indian" 
    }, 
 
    "timepass karna": { 
        "meaning": "to spend time without doing anything productive", 
        "category": "indian" 
    }, 
 
    "panga": { 
        "meaning": "trouble, conflict, or unnecessary problem", 
        "category": "indian" 
    }, 
 
    "lafda": { 
        "meaning": "trouble, conflict, controversy, or messy situation", 
        "category": "indian" 
    }, 
 
    "lafda hai": { 
        "meaning": "there is trouble or a problematic situation", 
        "category": "indian" 
    }, 
 
    "chamcha": { 
        "meaning": "a person who excessively supports or flatters someone powerful", 
        "category": "indian" 
    }, 
 
    "chamchagiri": { 
        "meaning": "excessive flattering or sycophantic behavior", 
        "category": "indian" 
    }, 
 
    "setting": { 
        "meaning": "an arrangement, connection, or influence used to achieve something", 
        "category": "indian" 
    }, 
 
    "setting karna": { 
        "meaning": "to arrange something through contacts or connections", 
        "category": "indian" 
    }, 
 
    "scene": { 
        "meaning": "a situation, issue, or matter", 
        "category": "indian" 
    }, 
 
    "scene hai": { 
        "meaning": "there is a situation or problem", 
        "category": "indian" 
    }, 
 
    "scene kya hai": { 
        "meaning": "what is happening or what is the situation?", 
        "category": "indian" 
    }, 
 
    "full on": { 
        "meaning": "completely, intensely, or enthusiastically", 
        "category": "indian" 
    }, 
 
    "bindass": { 
        "meaning": "carefree, confident, or without worry", 
        "category": "indian" 
    }, 
 
    "mast": { 
        "meaning": "excellent, enjoyable, or great", 
        "category": "indian" 
    }, 
 
    "jhakaas": { 
        "meaning": "excellent, impressive, or stylish", 
        "category": "indian" 
    }, 
 
    "bakchodi": { 
        "meaning": "silly, pointless, or mischievous behavior", 
        "category": "indian" 
    }, 
 
    "bakchod": { 
        "meaning": "a person who frequently jokes around or talks nonsense", 
        "category": "indian" 
    }, 
 
    "chill maar": { 
        "meaning": "relax or don't worry", 
        "category": "indian" 
    }, 
 
    "kya scene hai": { 
        "meaning": "what is happening or what is the plan?", 
        "category": "indian" 
    }, 
 
    "jhol": { 
        "meaning": "a suspicious, messy, or problematic situation", 
        "category": "indian" 
    }, 
 
    "jhol hai": { 
        "meaning": "something seems suspicious or problematic", 
        "category": "indian" 
    }, 
 
    "funda": { 
        "meaning": "basic idea, principle, or concept", 
        "category": "indian" 
    }, 
 
    "fundas": { 
        "meaning": "basic concepts or principles", 
        "category": "indian" 
    }, 
 
    "vella": { 
        "meaning": "someone with nothing productive to do", 
        "category": "indian" 
    }, 
 
    "velli": { 
        "meaning": "someone with nothing productive to do", 
        "category": "indian" 
    }, 
 
    "chill": { 
        "meaning": "relaxed or calm", 
        "category": "indian" 
    }, 
 
    "yaar": { 
        "meaning": "friend or buddy; commonly used casually", 
        "category": "indian" 
    }, 
 
    "bhai": { 
        "meaning": "brother or close male friend", 
        "category": "indian" 
    }, 
 
    "bro": { 
        "meaning": "close male friend or casual form of address", 
        "category": "indian" 
    }, 
 
    "dude": { 
        "meaning": "casual term for a person or friend", 
        "category": "general" 
    }, 
 
    "mate": { 
        "meaning": "friend or companion", 
        "category": "general" 
    }, 
 
 
    # ============================================================ 
    # GENERAL INFORMAL SLANG 
    # ============================================================ 
 
    "awesome": { 
        "meaning": "extremely good or impressive", 
        "category": "general" 
    }, 
 
    "cool": { 
        "meaning": "good, fashionable, or acceptable", 
        "category": "general" 
    }, 
 
    "dope": { 
        "meaning": "excellent or impressive", 
        "category": "general" 
    }, 
 
    "sick": { 
        "meaning": "extremely good or impressive in slang usage", 
        "category": "general" 
    }, 
 
    "wicked": { 
        "meaning": "excellent or impressive in slang usage", 
        "category": "general" 
    }, 
 
    "epic": { 
        "meaning": "extremely impressive or memorable", 
        "category": "general" 
    }, 
 
    "legit": { 
        "meaning": "genuine, real, or acceptable", 
        "category": "general" 
    }, 
 
    "sketchy": { 
        "meaning": "suspicious or unreliable", 
        "category": "general" 
    }, 
 
    "dodgy": { 
        "meaning": "suspicious, unreliable, or potentially dishonest", 
        "category": "general" 
    }, 
 
    "shady": { 
        "meaning": "suspicious, dishonest, or questionable", 
        "category": "general" 
    }, 
 
    "fishy": { 
        "meaning": "suspicious or difficult to trust", 
        "category": "general" 
    }, 
 
    "weird": { 
        "meaning": "strange or unusual", 
        "category": "general" 
    }, 
 
    "weirdo": { 
        "meaning": "a person considered strange or unusual", 
        "category": "general" 
    }, 
 
    "nerd": { 
        "meaning": "a person strongly interested in a particular technical or academic subject", 
        "category": "general" 
    }, 
 
    "geek": { 
        "meaning": "a person highly interested in a particular subject", 
        "category": "general" 
    }, 
 
    "loser": { 
        "meaning": "an insulting term for someone perceived as unsuccessful", 
        "category": "insult" 
    }, 
 
    "noob": { 
        "meaning": "an inexperienced person", 
        "category": "insult" 
    }, 
 
    "clown": { 
        "meaning": "an insulting term for someone behaving foolishly", 
        "category": "insult" 
    }, 
 
    "bozo": { 
        "meaning": "a foolish or incompetent person", 
        "category": "insult" 
    }, 
 
    "dummy": { 
        "meaning": "a foolish or unintelligent person", 
        "category": "insult" 
    }, 
 
    "idiot": { 
        "meaning": "an insulting term for someone considered foolish", 
        "category": "insult" 
    }, 
 
    "moron": { 
        "meaning": "an insulting term for someone considered foolish", 
        "category": "insult" 
    }, 
 
    "jerk": { 
        "meaning": "an unpleasant or rude person", 
        "category": "insult" 
    }, 
 
    "nasty": { 
        "meaning": "unpleasant, offensive, or mean", 
        "category": "general" 
    }, 
 
    "toxic": { 
        "meaning": "harmful, hostile, or excessively negative", 
        "category": "internet" 
    }, 
 
    "toxic behavior": { 
        "meaning": "behavior that is harmful, hostile, or excessively negative", 
        "category": "internet" 
    }, 
 
 
    # ============================================================ 
    # WORKPLACE / PROFESSIONAL INFORMAL SLANG 
    # ============================================================ 
 
    "hustle": { 
        "meaning": "working hard or aggressively pursuing an opportunity", 
        "category": "workplace" 
    }, 
 
    "side hustle": { 
        "meaning": "an additional source of work or income", 
        "category": "workplace" 
    }, 
 
    "grind": { 
        "meaning": "persistent hard work", 
        "category": "workplace" 
    }, 
 
    "burnout": { 
        "meaning": "extreme exhaustion caused by prolonged stress or work", 
        "category": "workplace" 
    }, 
 
    "micromanage": { 
        "meaning": "to control someone's work excessively", 
        "category": "workplace" 
    }, 
 
    "micromanaging": { 
        "meaning": "excessively controlling another person's work", 
        "category": "workplace" 
    }, 
 
    "ghost job": { 
        "meaning": "a job advertisement that may not represent an actively available position", 
        "category": "workplace" 
    }, 
 
    "quiet quitting": { 
        "meaning": "doing only the required duties rather than going beyond them", 
        "category": "workplace" 
    }, 
 
    "quiet firing": { 
        "meaning": "behavior intended to encourage an employee to leave a job", 
        "category": "workplace" 
    }, 
 
    "hustler": { 
        "meaning": "a person who aggressively pursues opportunities", 
        "category": "workplace" 
    }, 
 
    "startup bro": { 
        "meaning": "informal term for someone strongly associated with startup culture", 
        "category": "workplace" 
    }, 
 
 
    # ============================================================ 
    # SCAM / FRAUD / ONLINE SAFETY SLANG 
    # ============================================================ 
 
    "scam": { 
        "meaning": "a fraudulent or deceptive scheme", 
        "category": "fraud" 
    }, 
 
    "scammer": { 
        "meaning": "a person who conducts fraudulent activity", 
        "category": "fraud" 
    }, 
 
    "scamming": { 
        "meaning": "conducting fraudulent activity", 
        "category": "fraud" 
    }, 
 
    "fraudster": { 
        "meaning": "a person who commits fraud", 
        "category": "fraud" 
    }, 
 
    "con": { 
        "meaning": "a dishonest trick or fraud", 
        "category": "fraud" 
    }, 
 
    "con artist": { 
        "meaning": "a person who deceives others for personal gain", 
        "category": "fraud" 
    }, 
 
    "phishing": { 
        "meaning": "attempting to obtain sensitive information through deception", 
        "category": "cyber" 
    }, 
 
    "smishing": { 
        "meaning": "phishing conducted through text messages", 
        "category": "cyber" 
    }, 
 
    "vishing": { 
        "meaning": "phishing conducted through voice calls", 
        "category": "cyber" 
    }, 
 
    "spoofing": { 
        "meaning": "pretending to be a trusted person, service, or system", 
        "category": "cyber" 
    }, 
 
    "catfish": { 
        "meaning": "a person who uses a false online identity", 
        "category": "internet" 
    }, 
 
    "catfishing": { 
        "meaning": "using a false online identity", 
        "category": "internet" 
    }, 
 
    "doxxing": { 
        "meaning": "publishing someone's private information online without permission", 
        "category": "cyber" 
    }, 
 
    "swatting": { 
        "meaning": "making a false emergency report intended to trigger a police response", 
        "category": "internet" 
    }, 
 
    "bot": { 
        "meaning": "an automated account or program", 
        "category": "internet" 
    }, 
 
    "bot account": { 
        "meaning": "an account operated automatically or semi-automatically", 
        "category": "internet" 
    }, 
 
    "sockpuppet": { 
        "meaning": "a deceptive online identity controlled by the same person", 
        "category": "internet" 
    }, 
 
    "sock puppet": { 
        "meaning": "a deceptive online identity controlled by the same person", 
        "category": "internet" 
    }, 
 
 
    # ============================================================ 
    # ONLINE ABUSE / HARASSMENT TERMINOLOGY 
    # ============================================================ 
 
    "cyberbullying": { 
        "meaning": "bullying or harassment conducted through digital platforms", 
        "category": "abuse" 
    }, 
 
    "bully": { 
        "meaning": "a person who repeatedly intimidates or mistreats others", 
        "category": "abuse" 
    }, 
 
    "bullying": { 
        "meaning": "repeated intimidating or harmful behavior toward another person", 
        "category": "abuse" 
    }, 
 
    "harass": { 
        "meaning": "to repeatedly disturb, intimidate, or target someone", 
        "category": "abuse" 
    }, 
 
    "harassment": { 
        "meaning": "repeated unwanted or hostile behavior", 
        "category": "abuse" 
    }, 
 
    "hater": { 
        "meaning": "a person who repeatedly expresses strong dislike or criticism", 
        "category": "internet" 
    }, 
 
    "hate comment": { 
        "meaning": "an insulting or hostile online comment", 
        "category": "abuse" 
    }, 
 
    "hate speech": { 
        "meaning": "hostile or hateful expression targeting people based on protected characteristics", 
        "category": "abuse" 
    }, 
 
    "flame": { 
        "meaning": "an insulting or hostile online message", 
        "category": "internet" 
    }, 
 
    "flaming": { 
        "meaning": "posting hostile or insulting messages online", 
        "category": "internet" 
    }, 
 
    "dogpile": { 
        "meaning": "many people collectively attacking or criticizing someone online", 
        "category": "internet" 
    }, 
 
    "pile-on": { 
        "meaning": "a situation where many people collectively criticize someone", 
        "category": "internet" 
    }, 
 
 
    # ============================================================ 
    # COMMON INSULT / ABUSIVE SLANG 
    # ============================================================ 
 
    "ass": { 
        "meaning": "an insulting term for a foolish or unpleasant person", 
        "category": "insult" 
    }, 
 
    "dumbass": { 
        "meaning": "a strong informal insult meaning foolish person", 
        "category": "insult" 
    }, 
 
    "jackass": { 
        "meaning": "an insulting term for a foolish or annoying person", 
        "category": "insult" 
    }, 
 
    "smartass": { 
        "meaning": "someone who behaves in an irritatingly clever or sarcastic way", 
        "category": "insult" 
    }, 
 
    "wiseass": { 
        "meaning": "someone who makes sarcastic or disrespectful remarks", 
        "category": "insult" 
    }, 
 
    "lame": { 
        "meaning": "boring, weak, or unimpressive", 
        "category": "insult" 
    }, 
 
    "loser": { 
        "meaning": "an insulting term for someone perceived as unsuccessful", 
        "category": "insult" 
    }, 
 
    "screwup": { 
        "meaning": "a person who repeatedly makes mistakes", 
        "category": "insult" 
    }, 
 
    "screw-up": { 
        "meaning": "a person or mistake resulting from poor performance", 
        "category": "insult" 
    }, 
 
    "fool": { 
        "meaning": "a person behaving without good judgment", 
        "category": "insult" 
    }, 
 
    "foolish": { 
        "meaning": "lacking good judgment", 
        "category": "insult" 
    }, 
 
    "airhead": { 
        "meaning": "a person perceived as lacking intelligence or attention", 
        "category": "insult" 
    }, 
 
    "blockhead": { 
        "meaning": "a foolish or unintelligent person", 
        "category": "insult" 
    }, 
 
    "dimwit": { 
        "meaning": "a foolish or unintelligent person", 
        "category": "insult" 
    }, 
 
    "nitwit": { 
        "meaning": "a foolish or silly person", 
        "category": "insult" 
    }, 
 
    "dork": { 
        "meaning": "a socially awkward or foolish person", 
        "category": "insult" 
    }, 
 
    "nerd": { 
        "meaning": "a person strongly interested in technical or academic subjects", 
        "category": "general" 
    }, 
 
    "weirdo": { 
        "meaning": "a person considered strange or unusual", 
        "category": "insult" 
    }, 
 
    "creep": { 
        "meaning": "a person perceived as disturbing or unpleasant", 
        "category": "insult" 
    }, 
 
    "creepy": { 
        "meaning": "unpleasantly strange or disturbing", 
        "category": "general" 
    }, 
 
 
    # ============================================================ 
    # COMMON INFORMAL EXPRESSIONS 
    # ============================================================ 
 
    "what's up": { 
        "meaning": "a casual greeting asking how someone is doing", 
        "category": "expression" 
    }, 
 
    "wassup": { 
        "meaning": "informal version of what's up", 
        "category": "expression" 
    }, 
 
    "sup": { 
        "meaning": "very informal version of what's up", 
        "category": "expression" 
    }, 
 
    "no worries": { 
        "meaning": "it's okay or there is no problem", 
        "category": "expression" 
    }, 
 
    "my bad": { 
        "meaning": "my mistake", 
        "category": "expression" 
    }, 
 
    "hang out": { 
        "meaning": "spend casual time together", 
        "category": "expression" 
    }, 
 
    "hangout": { 
        "meaning": "a casual social gathering", 
        "category": "expression" 
    }, 
 
    "chill out": { 
        "meaning": "relax or calm down", 
        "category": "expression" 
    }, 
 
    "take it easy": { 
        "meaning": "relax or don't worry too much", 
        "category": "expression" 
    }, 
 
    "hit me up": { 
        "meaning": "contact or message me", 
        "category": "expression" 
    }, 
 
    "hit up": { 
        "meaning": "contact or approach someone", 
        "category": "expression" 
    }, 
 
    "catch up": { 
        "meaning": "talk or meet after some time apart", 
        "category": "expression" 
    }, 
 
    "hook up": { 
        "meaning": "meet or connect casually; meaning depends on context", 
        "category": "expression" 
    }, 
 
    "bail": { 
        "meaning": "leave suddenly or cancel plans", 
        "category": "expression" 
    }, 
 
    "bail out": { 
        "meaning": "leave or withdraw from a situation", 
        "category": "expression" 
    }, 
 
    "ghost town": { 
        "meaning": "a place or online space with very little activity", 
        "category": "expression" 
    }, 
 
    "crash": { 
        "meaning": "sleep somewhere or arrive unexpectedly, depending on context", 
        "category": "expression" 
    }, 
 
    "hangry": { 
        "meaning": "irritable because of hunger", 
        "category": "general" 
    }, 
 
    "brain freeze": { 
        "meaning": "temporary inability to think clearly", 
        "category": "general" 
    }, 
 
    "mess up": { 
        "meaning": "make a mistake", 
        "category": "general" 
    }, 
 
    "screw up": { 
        "meaning": "make a mistake or cause a problem", 
        "category": "general" 
    }, 
 
    "blow up": { 
        "meaning": "become very angry or suddenly become popular", 
        "category": "general" 
    }, 
 
    "blown up": { 
        "meaning": "made very popular or widely noticed", 
        "category": "general" 
    }, 
 
    "freak out": { 
        "meaning": "become extremely upset, excited, or frightened", 
        "category": "general" 
    }, 
 
    "freaking": { 
        "meaning": "an informal intensifier", 
        "category": "general" 
    }, 
 
    "heck": { 
        "meaning": "mild informal expression of surprise or annoyance", 
        "category": "general" 
    }, 
 
    "darn": { 
        "meaning": "mild informal expression of annoyance", 
        "category": "general" 
    }, 
 
    "dang": { 
        "meaning": "mild informal expression of surprise or annoyance", 
        "category": "general" 
    }, 
 
    "crap": { 
        "meaning": "nonsense, poor-quality material, or an expression of annoyance", 
        "category": "general" 
    }, 
 
    "crappy": { 
        "meaning": "poor quality or unpleasant", 
        "category": "general" 
    }, 
 
    "sucks": { 
        "meaning": "is very bad, unpleasant, or disappointing", 
        "category": "general" 
    }, 
 
    "sucked": { 
        "meaning": "was very bad or disappointing", 
        "category": "general" 
    }, 
 
 
    # ============================================================ 
    # POLITICAL / PUBLIC DISCUSSION INTERNET SLANG 
    # ============================================================ 
 
    "political troll": { 
        "meaning": "a person who deliberately provokes political arguments online", 
        "category": "political_internet" 
    }, 
 
    "troll farm": { 
        "meaning": "an organized operation producing coordinated online activity", 
        "category": "political_internet" 
    }, 
 
    "bot farm": { 
        "meaning": "a coordinated collection of automated or fake accounts", 
        "category": "political_internet" 
    }, 
 
    "astroturfing": { 
        "meaning": "creating the appearance of widespread grassroots support artificially", 
        "category": "political_internet" 
    }, 
 
    "echo chamber": { 
        "meaning": "an environment where people mainly encounter views similar to their own", 
        "category": "social_media" 
    }, 
 
    "fake news": { 
        "meaning": "false or misleading information presented as news", 
        "category": "misinformation" 
    }, 
 
    "misinfo": { 
        "meaning": "short form of misinformation", 
        "category": "misinformation" 
    }, 
 
    "disinfo": { 
        "meaning": "short form of disinformation", 
        "category": "misinformation" 
    }, 
 
    "misinformation": { 
        "meaning": "false or inaccurate information, regardless of intent", 
        "category": "misinformation" 
    }, 
 
    "disinformation": { 
        "meaning": "false information deliberately spread to mislead", 
        "category": "misinformation" 
    }, 
 
    "propaganda": { 
        "meaning": "information or messaging intended to influence public opinion", 
        "category": "public_discussion" 
    }, 
 
    "fearmongering": { 
        "meaning": "deliberately spreading fear or alarm", 
        "category": "public_discussion" 
    }, 
 
    "whataboutism": { 
        "meaning": "responding to criticism by raising an unrelated criticism", 
        "category": "public_discussion" 
    }, 
 
    "ragebait": { 
        "meaning": "content deliberately created to provoke anger", 
        "category": "social_media" 
    }, 
 
    "engagement farming": { 
        "meaning": "artificially trying to increase online engagement", 
        "category": "social_media" 
    }, 
 
    "brigading": { 
        "meaning": "coordinated online activity targeting a person or community", 
        "category": "social_media" 
    }, 
 
    "pile on": { 
        "meaning": "many people collectively criticizing someone", 
        "category": "social_media" 
    }
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