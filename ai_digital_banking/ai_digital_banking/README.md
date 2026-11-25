# AI-Based Digital Banking Solutions

A simple base project: a web banking app (Flask + SQLite) with built-in AI features.

## Features
| Module | What it does |
|---|---|
| Accounts | Register / login, auto-generated account number, deposit, withdraw |
| Transfers | Send money to another account in the system |
| **AI Fraud Detection** | Scores every transfer 0-100 (z-score vs. your history + rules for velocity, draining balance, odd hours). Score >= 70 is **blocked**, 40-69 is **flagged** |
| **AI Spending Insights** | Auto-categorises transactions (Food, Bills, ...) and shows savings tips |
| **AI Chatbot** | Intent-based assistant for balance, history, spending, loans, fraud help |
| **AI Loan Scoring** | Credit score (300-900) and EMI/eligibility from income, EMIs and account behaviour |

## Project structure
```
ai_digital_banking/
├── app.py            # Flask routes
├── ai_engine.py      # All AI logic (fraud, chatbot, loan, categorisation)
├── database.py       # SQLite schema + helpers
├── requirements.txt
├── static/style.css
└── templates/        # HTML pages
```

## Run it
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000, register, and try it out.

## Quick demo script
1. Register two users (open the second in a private window) and note each account number on the dashboard.
2. Deposit Rs. 50,000 into user A with note "salary".
3. Withdraw a few small amounts with notes like "pizza", "uber", "netflix" - see the spending chart.
4. Transfer a small amount to user B -> normal.
5. Transfer 95% of the balance -> flagged/blocked by the fraud AI.
6. Visit **Loan** and **Assistant** pages.

## Notes / extending
* The AI here is deliberately lightweight (no external libraries). You can swap
  `fraud_check()` for scikit-learn's `IsolationForest` or `detect_intent()` for a
  trained text classifier without changing the app.
* For production: use a fixed `SECRET_KEY`, CSRF protection (Flask-WTF), HTTPS, and a real DB.
* This is a learning/demo project and is not a real banking system.
