import json
from collections import defaultdict

with open('Lexora/L3exora_hack/scratch/eval_full_results.json', encoding='utf-8') as f:
    results = json.load(f)

print(f"TOTAL TEST DATASET ITEMS: {len(results)}\n")

cats = defaultdict(list)
for r in results:
    cats[r['category']].append(r)

for cat, items in cats.items():
    print("=" * 60)
    print(f"CATEGORY: {cat} ({len(items)} items)")
    print(f"GROUND TRUTH: {items[0]['ground_truth']}")
    print("=" * 60)
    
    lex_tiers = defaultdict(int)
    rob_tiers = defaultdict(int)
    gem_tiers = defaultdict(int)
    
    for item in items:
        lex_tiers[item['lexicon_tier']] += 1
        rob_tiers[item['roberta_tier']] += 1
        gem_tiers[item['gemini_tier']] += 1
        
    print(f"Lexicon Tiers: {dict(lex_tiers)}")
    print(f"RoBERTa Tiers: {dict(rob_tiers)}")
    print(f"Gemini Tiers:  {dict(gem_tiers)}")
    print("-" * 60)
    
    false_cases = []
    for item in items:
        gt = item['ground_truth']
        lt = item['lexicon_tier']
        rt = item['roberta_tier']
        gtier = item['gemini_tier']
        
        iss = []
        if gt == 'Non-Compliant / Harmful':
            # Expected Tier 3 (Incitement/Hate) or Tier 4 (Threat/Harmful)
            if lt < 3:
                iss.append(f"Lexicon False Tier {lt} (Missed Harmful content)")
            if rt < 3:
                iss.append(f"RoBERTa False Tier {rt} (Missed Harmful content)")
            if gtier < 3:
                iss.append(f"Gemini/Fallback False Tier {gtier} (Missed Harmful content)")
        elif gt == 'Compliant / Sensitive':
            # Expected Tier 1 (Lawful) or Tier 2 (Abusive/Sentiment)
            if lt >= 3:
                iss.append(f"Lexicon False Tier {lt} (Over-flagged as Hate/Threat)")
            if rt >= 3:
                iss.append(f"RoBERTa False Tier {rt} (Over-flagged as Hate/Threat)")
            if gtier >= 3:
                iss.append(f"Gemini False Tier {gtier} (Over-flagged as Hate/Threat)")
        elif gt == 'Compliant / Safe':
            # Expected Tier 1
            if lt > 1:
                iss.append(f"Lexicon False Tier {lt} (Flagged safe content)")
            if rt > 1:
                iss.append(f"RoBERTa False Tier {rt} (Flagged safe content)")
            if gtier > 1:
                iss.append(f"Gemini False Tier {gtier} (Flagged safe content)")
                
        if iss:
            false_cases.append((item['id'], item['query'], iss, lt, rt, gtier))
            
    print(f"False Tier Queries ({len(false_cases)}/{len(items)}):")
    for qid, q, issues, lt, rt, gtier in false_cases:
        print(f"\n  [ID {qid:02d}] Lexicon: Tier {lt} | RoBERTa: Tier {rt} | Gemini: Tier {gtier}")
        print(f"    Query: \"{q}\"")
        for issue in issues:
            print(f"    -> {issue}")
    print("\n")
