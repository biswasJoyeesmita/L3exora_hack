# Eldorado — Slang Word Detection Model (Prototype)

A from-scratch, trainable prototype that flags slang words inside a piece of text.

## How it works
- **Model**: character n-gram TF-IDF (`analyzer="char_wb"`, sizes 2–4) + Logistic Regression.
- **Why char n-grams**: slang words are often out-of-dictionary or spelled unconventionally
  ("finna", "bussin", "sksksk"). Learning sub-word patterns generalizes better than
  memorizing exact words.
- **Unit of classification**: individual words. The detector tokenizes user input,
  classifies each token as `SLANG` or `standard`, and reports a confidence score.

## Files
- `slang_dataset_sample.csv` — starter dataset (`word,label`), label 1 = slang, 0 = standard.
  Replace/expand this with your real dataset.
- `train_model.py` — trains the model from a CSV and saves `slang_model.pkl`.
- `detect_slang.py` — interactive CLI: type a sentence, get slang words flagged.
- `requirements.txt` — dependencies.

## Setup
```bash
pip install -r requirements.txt
```

## 1. Train the model
```bash
python train_model.py --data slang_dataset_sample.csv --model_out slang_model.pkl
```
This prints accuracy + a classification report on a held-out test split, and saves the
trained pipeline to `slang_model.pkl`.

## 2. Detect slang interactively
```bash
python detect_slang.py --model slang_model.pkl
```
Example:
```
Enter text: bruh that movie was lit fr
--- Eldorado Slang Detection Result ---
[bruh]* that movie was [lit]* fr

Details:
  bruh            -> SLANG      (confidence: 0.87)
  that            -> standard   (confidence: 0.04)
  movie           -> standard   (confidence: 0.06)
  was             -> standard   (confidence: 0.03)
  lit             -> SLANG      (confidence: 0.91)
  fr              -> SLANG      (confidence: 0.62)
```
Adjust sensitivity with `--threshold` (default 0.5). Lower = more aggressive flagging.

## Building a proper dataset
The sample CSV (~130 words) is only enough to prove the pipeline works end-to-end —
it will NOT generalize well. To train something usable:

1. **Collect slang terms** from sources like:
   - Urban Dictionary (scrape top-defined entries — check their terms of use)
   - Twitter/Reddit slang word lists and NLP slang lexicons on GitHub/Kaggle
     (search "slang dataset", "internet slang lexicon", "noisy text normalization dataset")
   - Genre-specific slang (gaming, AAVE-influenced internet slang, regional slang, etc.)
     depending on what your group wants to target
2. **Collect standard words** — any large English word list or frequency list
   (e.g. Brown corpus word list, common English word frequency lists) labeled 0.
3. **Balance classes** roughly 40/60 to 60/40 between slang and standard.
4. **Dedupe and lowercase** consistently (the training script already does this).
5. Aim for at least a few thousand examples per class for a meaningful model;
   tens of thousands is better.

## Next steps beyond this prototype
- Move from word-level classification to **context-aware sequence labeling**
  (e.g. fine-tune a small transformer like DistilBERT as a token classifier) so the
  same word can be judged differently depending on context.
- Add a **confusion/ambiguous word list** (words that are slang only in some contexts,
  e.g. "sick", "fire", "wicked") and route those through the context-aware model.
- Log user corrections from `detect_slang.py` to build an active-learning feedback loop.
