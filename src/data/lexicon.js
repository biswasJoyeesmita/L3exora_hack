/* ==========================================================================
   LEXORA — Backend lexicon
   Same categories as the frontend demo, expanded with a `severity` weight
   (1-10) used by the risk-scoring engine in src/analyze.js.

   This is still a hardcoded/rule-based dataset — swap or augment
   getLexicon() with a real ML/NLP classifier or moderation API call
   whenever you're ready (see analyze.js for the seam).
   ========================================================================== */

const LEXICON = [
  { word: "clown", meaning: "Used mockingly to call someone foolish or incompetent.", category: "insult", severity: 3 },
  { word: "idiot", meaning: "A common insult questioning someone's intelligence.", category: "insult", severity: 3 },
  { word: "loser", meaning: "Derogatory term aimed at belittling someone.", category: "insult", severity: 3 },
  { word: "moron", meaning: "Insult questioning someone's intelligence.", category: "insult", severity: 3 },
  { word: "pathetic", meaning: "Used to demean or dismiss someone's efforts.", category: "insult", severity: 3 },

  { word: "corrupt", meaning: "Accusation of dishonest or unlawful conduct.", category: "offensive", severity: 4 },
  { word: "traitor", meaning: "Accusation of betrayal, often used in political attacks.", category: "offensive", severity: 4 },
  { word: "fraud", meaning: "Accusation of deceit, often directed at public figures.", category: "offensive", severity: 4 },
  { word: "liar", meaning: "Accusation of dishonesty.", category: "offensive", severity: 4 },
  { word: "hypocrite", meaning: "Accusation of not practicing what one preaches.", category: "offensive", severity: 3 },

  { word: "shut up", meaning: "Dismissive phrase used to silence someone rudely.", category: "abusive", severity: 5 },
  { word: "useless", meaning: "Demeaning term suggesting someone has no value or worth.", category: "abusive", severity: 5 },
  { word: "worthless", meaning: "Demeaning term suggesting someone has no value.", category: "abusive", severity: 5 },
  { word: "shut your mouth", meaning: "Aggressive phrase used to silence someone.", category: "abusive", severity: 6 },
  { word: "nobody likes you", meaning: "Isolating, demeaning statement aimed at causing distress.", category: "abusive", severity: 6 },

  { word: "destroy you", meaning: "Aggressive phrase implying intent to harm or ruin.", category: "threatening", severity: 9 },
  { word: "burn it down", meaning: "Phrase implying destructive or violent intent.", category: "threatening", severity: 9 },
  { word: "kill you", meaning: "Direct threatening language implying violent intent.", category: "threatening", severity: 10 },
  { word: "hunt you down", meaning: "Threatening phrase implying pursuit with intent to harm.", category: "threatening", severity: 9 },
  { word: "watch your back", meaning: "Implied threat suggesting future harm.", category: "threatening", severity: 7 },

  { word: "sus", meaning: "Slang for 'suspicious' — informal, not necessarily hostile.", category: "slang", severity: 1 },
  { word: "lowkey", meaning: "Slang meaning 'somewhat' or 'secretly'.", category: "slang", severity: 1 },
  { word: "cap", meaning: "Slang for a lie or exaggeration (e.g. 'that's cap').", category: "slang", severity: 1 },
  { word: "goat", meaning: "Slang acronym for 'greatest of all time'.", category: "slang", severity: 1 },
  { word: "bet", meaning: "Slang for agreement or confirmation.", category: "slang", severity: 1 },
  { word: "no cap", meaning: "Slang meaning 'no lie' or 'seriously'.", category: "slang", severity: 1 },
];

/**
 * getLexicon()
 * Returns the active detection dataset.
 *
 * FUTURE: replace this with a call to a real classifier — e.g. a
 * fine-tuned model, a hosted moderation endpoint (OpenAI Moderation,
 * Perspective API, AWS Comprehend, etc.), or a database-backed term
 * list that product/trust-and-safety teams can edit without a deploy.
 */
function getLexicon() {
  return LEXICON;
}

module.exports = { getLexicon };
