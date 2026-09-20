import json
import os
import re
import sys

sys.path.append(os.path.abspath('Lexora/L3exora_hack'))
from dotenv import load_dotenv
load_dotenv('Lexora/L3exora_hack/.env')

with open('Lexora/L3exora_hack/lexora_test_dataset.json', encoding='utf-8') as f:
    dataset = json.load(f)

TARGET_HINTS = (
    'government', 'govt', 'minister', 'pm', 'parliament', 'policy', 'official',
    'public servant', 'neta', 'leader', 'bureaucrat', 'citizen', 'state',
    'india', 'modi', 'cabinet', 'election', 'court', 'police', 'mla', 'mp'
)


def is_domain_relevant(item):
    text = f"{item.get('query', '')} {item.get('category', '')}".lower()
    return any(re.search(rf"\b{re.escape(hint)}\b", text) for hint in TARGET_HINTS)

# 1. Lexicon evaluation
import lexicon as lex_mod
print("=== LEXICON ENGINE ===")
lex_false = []
lex_counts = {1:0, 2:0, 3:0, 4:0}
for item in dataset:
    res = lex_mod.check_lexicon(item['query'])
    tier = res.get('lexicon_tier') or 1
    lex_counts[tier] = lex_counts.get(tier, 0) + 1
    
    gt = item['ground_truth']
    if gt == "Non-Compliant / Harmful" and tier < 3:
        lex_false.append((item, tier, "False Negative: Rule-based lexicon missed harmful/prohibited content (gave Tier 1/2)"))
    elif gt == "Compliant / Safe" and tier > 1:
        lex_false.append((item, tier, "False Positive: Lexicon flagged safe content"))
    elif gt == "Compliant / Sensitive" and tier >= 3:
        lex_false.append((item, tier, "False Over-flagging: Lexicon flagged sensitive debate as hate/threat"))

print(f"Lexicon Tiers breakdown: {lex_counts}")
print(f"Lexicon False Tiers count: {len(lex_false)}")

# 2. Local RoBERTa evaluation
import classify_local as local_mod
print("\n=== LOCAL ROBERTA ENGINE ===")
local_false = []
local_counts = {1:0, 2:0, 3:0, 4:0}
for item in dataset:
    res = local_mod.classify(item['query'])
    tier = res['tier']
    local_counts[tier] = local_counts.get(tier, 0) + 1
    gt = item['ground_truth']
    if gt == "Non-Compliant / Harmful" and tier < 3:
        local_false.append((item, tier, "False Negative: Local model missed harmful content (gave Tier 1/2)"))
    elif gt == "Compliant / Safe" and tier > 1:
        local_false.append((item, tier, "False Positive: Local model flagged safe content"))
    elif gt == "Compliant / Sensitive" and tier >= 3:
        local_false.append((item, tier, "False Over-flagging: Local model flagged sensitive debate as Tier 3/4"))

print(f"Local RoBERTa Tiers breakdown: {local_counts}")
print(f"Local RoBERTa False Tiers count: {len(local_false)}")

# 3. Gemini LLM evaluation
import classify as gemini_mod
print("\n=== GEMINI LLM ENGINE ===")
gemini_false = []
gemini_counts = {1:0, 2:0, 3:0, 4:0}
gemini_results = []
batch_size = 10
for i in range(0, len(dataset), batch_size):
    batch = dataset[i:i+batch_size]
    formatted = [{'text': d['query'], 'context': d['category']} for d in batch]
    try:
        results = gemini_mod.classify_batch(formatted)
        for d, r in zip(batch, results):
            tier = r['tier']
            gemini_counts[tier] = gemini_counts.get(tier, 0) + 1
            gt = d['ground_truth']
            gemini_results.append((d, r))
            if gt == "Non-Compliant / Harmful" and tier < 3:
                gemini_false.append((d, r, "False Negative: Gemini missed harmful/prohibited content (gave Tier 1/2)"))
            elif gt == "Compliant / Safe" and tier > 1:
                gemini_false.append((d, r, "False Positive: Gemini flagged safe content as Tier > 1"))
            elif gt == "Compliant / Sensitive" and tier >= 3:
                gemini_false.append((d, r, "False Over-flagging: Gemini flagged sensitive debate/commentary as Tier 3/4"))
    except Exception as e:
        print(f"Batch {i} Gemini error: {e}")

print(f"Gemini Tiers breakdown: {gemini_counts}")
print(f"Gemini False Tiers count: {len(gemini_false)}")

# Write detailed analysis output to file
with open('Lexora/L3exora_hack/scratch/eval_summary.txt', 'w', encoding='utf-8') as out:
    out.write("=== EVALUATION SUMMARY FOR LEXORA TEST DATASET ===\n\n")
    out.write(f"1. LEXICON ENGINE: False Tier Cases ({len(lex_false)}/100):\n")
    for d, t, reason in lex_false:
        out.write(f"  [ID {d['id']}] Cat: {d['category']} | GT: {d['ground_truth']} | Pred: Tier {t}\n")
        out.write(f"    Query: {d['query']}\n")
        out.write(f"    Reason: {reason}\n\n")

    out.write(f"\n2. LOCAL ROBERTA ENGINE: False Tier Cases ({len(local_false)}/100):\n")
    for d, t, reason in local_false:
        out.write(f"  [ID {d['id']}] Cat: {d['category']} | GT: {d['ground_truth']} | Pred: Tier {t}\n")
        out.write(f"    Query: {d['query']}\n")
        out.write(f"    Reason: {reason}\n\n")

    out.write(f"\n3. GEMINI LLM ENGINE: False Tier Cases ({len(gemini_false)}/100):\n")
    for d, r, reason in gemini_false:
        out.write(f"  [ID {d['id']}] Cat: {d['category']} | GT: {d['ground_truth']} | Pred: Tier {r['tier']}\n")
        out.write(f"    Query: {d['query']}\n")
        out.write(f"    Reason: {reason}\n")
        out.write(f"    Sentiment: {r.get('overall_sentiment')} | Target: {r.get('target_description')}\n")
        out.write(f"    Justification: {r.get('justification')}\n\n")

print("\nSaved output to Lexora/L3exora_hack/scratch/eval_summary.txt")
