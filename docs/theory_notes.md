# Theory notes

Facts, numbers and figures for the theory part of the report (brief sections 3.1–3.4). Every
number here comes from the committed notebook and `results/`. Figure names refer to `figures/`.

---

## 3.1 Model scenario

**Problem.** Phishing emails trick people into handing over credentials, money or access
("verify your account", "invoice overdue"). They are one of the most common first steps of
an attack, and they target people, so firewalls and antivirus don't stop them.

**What the model does.** It reads an email (subject + body) and returns the **probability
that it is phishing or spam**, plus the **words that drove the decision**.

**How it is used** (as built in this project):
* An **API** (`POST /predict`, `/explain`, `/predict_batch`) that a mail server, a security
  tool or a SOC workflow can call for every incoming email.
* A **desktop app** for an analyst or user: paste or load an email, get a verdict, adjust the
  **decision threshold** (trading missed phishing against false alarms), and see red/blue
  highlighting that shows *why*.
* A **batch mode** to triage a whole mailbox export (CSV) at once.

**Security value.** It automates first-line triage, flags suspicious mail before a person acts
on it, and the explanations help analysts check verdicts rather than trusting a black box.

**Scope note.** In the dataset, label 1 covers **phishing, spam and advance-fee fraud**
(four of the six source corpora are spam collections). So the model is really a
*malicious/unwanted email* detector.

---

## 3.2 Model architecture

### DistilBERT (`distilbert-base-uncased`, fine-tuned)

A Transformer **encoder** distilled from BERT-base (Sanh et al., 2019): 40% smaller and 60%
faster, keeping about 97% of BERT's language understanding.

| component | details (from `models/distilbert_best/config.json`) |
|---|---|
| tokeniser | WordPiece, vocabulary 30,522, lowercases (*uncased*). Unknown words are split into sub-words, e.g. `acc0unt` → `acc` `##0` `##unt` |
| input | `[CLS]` + up to 254 tokens + `[SEP]` (**max length 256**), with an attention mask for padding |
| embeddings | token + learned position embeddings (up to 512 positions), dimension **768**, LayerNorm, dropout 0.1 |
| encoder | **6 Transformer layers**. Each has **multi-head self-attention** (12 heads × 64 dims) and a **feed-forward network 768 → 3072 → 768 with GELU** activation, both wrapped in residual connections + LayerNorm, dropout 0.1 |
| classification head | final `[CLS]` vector → Linear 768→768 → **ReLU** → dropout 0.2 → Linear 768→2 → **softmax** gives P(legitimate), P(phishing) |
| parameters | **66.96 million**, all fine-tuned |

**Self-attention in one line:** each token builds a query, key and value. Its new representation
is a weighted mix of all tokens' values, with weights `softmax(QKᵀ/√d)`. So every word is read in
the context of the whole email (Vaswani et al., 2017).

**Training** (notebook §3.2, one config cell):

| setting | value | why |
|---|---|---|
| loss | cross-entropy | standard for classification |
| optimiser | **AdamW**, lr 2e-5, weight decay 0.01 (not on bias/LayerNorm) | standard for fine-tuning Transformers (Loshchilov & Hutter, 2019) |
| schedule | **linear warm-up** over the first 6% of steps, then linear decay to 0 | warm-up avoids destroying pre-trained weights with early large updates |
| batch | 32 (dynamic padding) | |
| precision | bf16 mixed precision on GPU | faster and uses less memory; the loss is computed in float32 |
| gradient clipping | max norm 1.0 | stability |
| evaluation | full validation set every **200 steps** | enough points for curves and early stopping |
| early stopping | on **validation loss**, patience **3**, min_delta 0.001, best checkpoint saved and restored | loss also catches over-confidence, which F1 misses |
| max epochs | 3 | |

**Why DistilBERT suits this data**
* Phishing is recognised from *wording and intent* ("kindly confirm your credentials"), which
  depends on context. Self-attention models context; bag-of-words doesn't.
* Pre-training on large amounts of English gives transfer learning: phrasings never seen in
  training still map close to known ones.
* Sub-word tokens cope with misspellings and obfuscation (`paypa1`, `ver1fy`).
* Distilled = small enough to fine-tune in minutes on one GPU and to serve in about 10 ms
  (GPU) / 30 ms (CPU) per email.

**Baseline for comparison:** TF-IDF (word unigrams + bigrams, 200k features, sublinear tf) +
L2-regularised **Logistic Regression** (sigmoid output, balanced class weights, C tuned on
validation; best C = 10,000).

---

## 3.3 Result analysis

### Data (notebook §2)

* 82,486 raw emails from 6 corpora → **74,237** after removing junk and **8,237 duplicates**
  (3,463 exact + 4,774 near-duplicates + 2 with conflicting labels). Duplicates were removed
  **before** splitting, so no email appears in both train and test.
* Split 70/15/15, **stratified on corpus × label**: 51,965 / 11,136 / 11,136, 48.8% phishing in each.
* **Leakage removed:** years (legitimate mail is 1998–2008, Nazario phishing 2015–2020), email
  addresses, header lines and the Nazario mailbox owner's name.
* **Corpus leakage measured:** knowing *only* the corpus gives 57.5% accuracy (majority class
  51.2%). The source is still recognisable from topic (macro-F1 0.93), which is real content and
  can't be removed.

### Training (§3.7–3.9, `distilbert_loss_curves.png`, `distilbert_val_metrics.png`)

* Validation F1 was already 0.965 after 200 steps, thanks to transfer learning.
* Best validation loss **0.0387 at step 1200**. Validation loss then rose for 3 checks while
  train loss kept falling (0.048 → 0.021): the start of overfitting. **Early stopping triggered
  at step 1800** (1.1 of 3 epochs), and step 1200 was restored and verified. Training took 3.5 min.
* F1 at step 1800 was *higher* (0.9889) than at the best step, yet the loss was worse. The model
  was becoming over-confident, which is why the stopping rule watches the loss.

### Test set (§4, scored once)

| model | accuracy | precision | recall | F1 | AUC-ROC | AP | errors | false positives | false negatives |
|---|---|---|---|---|---|---|---|---|---|
| DistilBERT | 0.9892 | 0.9915 | 0.9864 | 0.9889 | 0.9994 | 0.9994 | 120 | **46 (0.81%)** | 74 (1.36%) |
| TF-IDF + LR | **0.9913** | 0.9890 | **0.9932** | **0.9911** | **0.9997** | 0.9996 | **97** | 60 (1.05%) | **37 (0.68%)** |

Figures: `distilbert_roc_pr.png`, `distilbert_confusion.png`, `baseline_*`, `comparison_roc_pr.png`.

* Test F1 matches validation F1 (0.9875), so there's no sign of overfitting to validation.
* **The two models are tied overall.** DistilBERT has **fewer false alarms**; the baseline
  **misses less**. Only 29 emails fool both, so they use different signals.
* Only **1.5%** of emails get a probability between 0.1 and 0.9 (`distilbert_prob_hist.png`).
  The model is confident even when wrong, so moving the threshold changes few verdicts.

### Per source (`distilbert_per_source.png`)

| corpus | accuracy | FPR (legitimate flagged) | FNR (phishing missed) |
|---|---|---|---|
| CEAS_08 | 0.9959 | 0.70% | 0.09% |
| Enron | 0.9838 | 0.79% | 2.50% |
| SpamAssassin | 0.9762 | 1.47% | 4.76% |
| Ling | 0.9907 | 0.56% | 2.94% |
| Nigerian_Fraud | 1.0000 | n/a | 0.00% |
| Nazario (true phishing) | 0.9693 | n/a | 3.07% |

High accuracy on the mixed corpora shows the model learned more than "which corpus".
Credential phishing (Nazario) is missed more often (3.1%) than spam (CEAS 0.1%).

### Errors (§4.6)

* **False positives:** legitimate automated mail that *sounds* like phishing (bounce messages,
  "confirm your subscription", IT notices saying "urgent … press the button"), and marketing
  newsletters.
* **False negatives:** spam written like business mail (52 of 74 are from Enron), short friendly
  scams with no link, and word-salad spam.

### Explainability (§5.1–5.3, `xai_*.png`)

* **Integrated Gradients** (Sundararajan et al., 2017) on the embeddings, explaining the
  phishing log-odds. The **completeness check** holds: attributions add up to the output within under 1%.
* **Deletion test:** removing IG's top-10 words leaves **91.7%** detected, against 96.0% for 10
  random words. The explanations are faithful, and the evidence is spread over the whole email.
* **Corpus shortcut, visible:** the top legitimate-pushing words are `opensuse`, `enron`,
  `python-dev`, `vince`, `linguistics`. One spam email was let through *because* it mentioned
  "linguists". The TF-IDF baseline relies on the same kind of words.
* We use IG rather than attention weights, because attention isn't a faithful explanation
  (Jain & Wallace, 2019).

### Robustness (§5.4, `robustness.png`, `robustness_legit_fpr.png`)

| 80% of words perturbed | DistilBERT: phishing caught | TF-IDF: phishing caught | DistilBERT: legitimate flagged | TF-IDF: legitimate flagged |
|---|---|---|---|---|
| none | 98.2% | 99.1% | 0.9% | 1.5% |
| typos | 99.9% | 97.6% | **52.4%** | 7.1% |
| homoglyphs (Cyrillic look-alikes) | 100% | **90.8%** | **64.2%** | 2.0% |
| synonyms | 98.2% | 99.0% | 0.9% | 1.3% |

DistilBERT learned "odd-looking text = spam". Attackers can't evade it with random noise, but it
then **blocks messy legitimate mail**. The perturbations are random, not adaptive; targeted attacks
are stronger (Jin et al., 2020).

### Is the model effective?

Yes, for *this distribution*: about 99% accuracy with few false alarms, fast enough for real-time
use, and explainable. The caveats:
1. a simple baseline does just as well here
2. part of the signal is corpus identity, which won't transfer to a new organisation
3. it is sensitive to unusual characters and typos in legitimate mail
4. the "phishing" class is mostly spam

---

## 3.4 Real-world use of ML in cybersecurity

**Where ML is used**
* **Intrusion detection (NIDS/HIDS):** classify network flows or system calls as attack or normal.
* **Threat / malware classification:** families of malware, threat categories in reports.
* **Anomaly detection:** spot unusual logins, traffic or processes without labelled attacks.
* **Risk assessment:** score users, assets or events to prioritise analyst attention.
* **Phishing and spam filtering:** one of the most mature applications. Mail providers combine
  ML text and URL models with sender reputation and authentication (SPF/DKIM/DMARC).

**Strengths:** handles scale no analyst team can, adapts by retraining instead of hand-written
rules, and finds patterns across many weak signals. **This project:** about 99% accuracy, about 10 ms per email.

**Challenges, with evidence from this project**

| challenge | general point | in this project |
|---|---|---|
| **Data quality and dataset bias** | public security datasets are old, merged from different sources, and contain artefacts that models exploit (Arp et al., 2022) | merged corpora; years, addresses and corpus topics leak the label; 10% duplicates |
| **Concept drift** | attacks change over time, so performance degrades without retraining (Gama et al., 2014) | training data is 1998–2020; current phishing (QR codes, AI-written text) is unseen |
| **False positives and base rates** | at real-world volumes even a 1% FPR means thousands of wrong alerts and alert fatigue, because attacks are rare (Axelsson, 2000) | 0.81% FPR at a 49% phishing rate here; real inboxes have far fewer phishing emails, so the share of alerts that are real would be much lower |
| **Adversarial evasion** | attackers adapt to the detector (Jin et al., 2020) | robustness tests: homoglyphs drop TF-IDF to 91%; DistilBERT resists but over-flags |
| **Explainability and trust** | analysts need reasons to act on alerts | IG highlights in the app; deletion test shows they're faithful |
| **Lab vs real world** | high benchmark scores often fail to carry over to deployment (Sommer & Paxson, 2010; Apruzzese et al., 2023) | the baseline tie and corpus shortcuts show why benchmark accuracy alone isn't enough |

**Takeaway:** ML is effective as one layer in defence-in-depth, with continuous retraining, human
review of alerts and other controls around it. It isn't a standalone solution.

---

## References (verify details before citing)

* Apruzzese, G. et al. (2023). The role of machine learning in cybersecurity. *Digital Threats: Research and Practice*, 4(1).
* Arp, D. et al. (2022). Dos and don'ts of machine learning in computer security. *USENIX Security Symposium*.
* Axelsson, S. (2000). The base-rate fallacy and the difficulty of intrusion detection. *ACM Transactions on Information and System Security*, 3(3).
* Devlin, J. et al. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. *NAACL-HLT*.
* Fette, I., Sadeh, N. & Tomasic, A. (2007). Learning to detect phishing emails. *Proceedings of the 16th International World Wide Web Conference (WWW)*.
* Gama, J. et al. (2014). A survey on concept drift adaptation. *ACM Computing Surveys*, 46(4).
* Jain, S. & Wallace, B. C. (2019). Attention is not explanation. *NAACL-HLT*.
* Jin, D. et al. (2020). Is BERT really robust? A strong baseline for natural language attack on text classification and entailment. *AAAI*.
* Loshchilov, I. & Hutter, F. (2019). Decoupled weight decay regularization. *ICLR*.
* Sanh, V. et al. (2019). DistilBERT, a distilled version of BERT: smaller, faster, cheaper and lighter. *arXiv:1910.01108*.
* Sommer, R. & Paxson, V. (2010). Outside the closed world: On using machine learning for network intrusion detection. *IEEE Symposium on Security and Privacy*.
* Sundararajan, M., Taly, A. & Yan, Q. (2017). Axiomatic attribution for deep networks. *ICML*.
* Vaswani, A. et al. (2017). Attention is all you need. *NeurIPS*.
* Dataset: Alam, N. A. Phishing Email Dataset. Kaggle. <https://www.kaggle.com/datasets/naserabdullahalam/phishing-email-dataset>
