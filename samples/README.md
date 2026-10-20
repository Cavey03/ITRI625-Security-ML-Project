# Demo emails

Self-written examples (invented companies, `example.com` domains) for demonstrating the
desktop app. Load them with **Load .txt / .eml** (single email tab) or **Open CSV** (batch tab).

| file | true label | model P(phishing) | what it shows |
|---|---|---|---|
| `1_phishing_account_suspended.eml` | phishing | 0.999 | classic credential phishing in HTML; the fake login URL is the strongest red word |
| `2_legit_project_meeting.txt` | legitimate | 0.001 | normal work email |
| `3_hard_legit_password_reset.eml` | legitimate | 0.967 | **false positive**: a real password reset uses phishing vocabulary. Raising the threshold to 0.98 makes it legitimate |
| `4_hard_phishing_no_link.txt` | phishing | 0.017 | **false negative**: a gift-card scam with no link or urgency words |
| `demo_batch.csv` | mixed | | 8 rows: 4 phishing, 3 legitimate, 1 empty row reported as an error |
