"""Simple, dependency-free 'AI' engine for the digital banking project.

Contains:
  * categorize()        - keyword-based transaction categorisation
  * fraud_check()       - anomaly / risk scoring for outgoing transactions
  * chatbot_reply()     - intent-matching virtual banking assistant
  * loan_assessment()   - rule-based credit scoring
  * spending_insights() - category totals and savings tips
"""
import re
import statistics
from datetime import datetime

# --------------------------------------------------------------------------
# 1. Transaction categorisation
# --------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "Food": ["restaurant", "swiggy", "zomato", "cafe", "food", "pizza", "dinner", "lunch", "grocery", "groceries"],
    "Transport": ["uber", "ola", "fuel", "petrol", "diesel", "metro", "bus", "train", "flight", "taxi"],
    "Shopping": ["amazon", "flipkart", "shopping", "clothes", "mall", "myntra", "shoes"],
    "Bills": ["electricity", "water", "bill", "rent", "internet", "recharge", "insurance", "emi"],
    "Entertainment": ["netflix", "movie", "spotify", "game", "concert", "prime"],
    "Health": ["hospital", "pharmacy", "doctor", "medicine", "clinic"],
    "Education": ["school", "college", "tuition", "course", "books", "fees"],
    "Salary": ["salary", "payroll", "bonus", "stipend"],
}


def categorize(description: str) -> str:
    text = (description or "").lower()
    for category, words in CATEGORY_KEYWORDS.items():
        if any(w in text for w in words):
            return category
    return "Other"


# --------------------------------------------------------------------------
# 2. Fraud detection
# --------------------------------------------------------------------------
def fraud_check(amount, balance, past_amounts, recent_count_10min, hour=None):
    """Return (score 0-100, [reasons]).

    score >= 70  -> block, 40-69 -> allow but flag, < 40 -> normal.
    Combines a statistical z-score against the user's own history with
    simple business rules.
    """
    score, reasons = 0, []
    hour = datetime.now().hour if hour is None else hour

    # Rule 1: statistical outlier vs. user's usual spending
    if len(past_amounts) >= 3:
        mean = statistics.mean(past_amounts)
        stdev = statistics.pstdev(past_amounts) or 1.0
        z = (amount - mean) / stdev
        if z > 3:
            score += 40
            reasons.append(f"Amount is {z:.1f} std-devs above your usual spending")
        elif z > 2:
            score += 20
            reasons.append("Amount is unusually high compared to your history")
    elif amount > 50000:
        score += 25
        reasons.append("Large transfer on an account with little history")

    # Rule 2: draining the account
    if balance > 0 and amount >= 0.9 * balance:
        score += 25
        reasons.append("Transfer drains 90%+ of the balance")

    # Rule 3: very large absolute amount
    if amount >= 100000:
        score += 20
        reasons.append("Very large transaction amount")

    # Rule 4: velocity - many transactions in a short time
    if recent_count_10min >= 3:
        score += 25
        reasons.append("Multiple transactions within 10 minutes")

    # Rule 5: odd hours
    if 0 <= hour < 5 and amount > 10000:
        score += 15
        reasons.append("Large transaction at an unusual hour (12am-5am)")

    return min(score, 100), reasons


# --------------------------------------------------------------------------
# 3. Chatbot
# --------------------------------------------------------------------------
INTENTS = {
    "greeting": ["hello", "hi", "hey", "good morning", "good evening"],
    "balance": ["balance", "how much money", "funds"],
    "history": ["transaction", "history", "statement", "last payment", "recent"],
    "spending": ["spending", "expenses", "spent", "budget", "save", "savings"],
    "transfer": ["transfer", "send money", "pay someone", "neft", "imps", "upi"],
    "loan": ["loan", "borrow", "credit", "emi", "eligible"],
    "fraud": ["fraud", "scam", "suspicious", "hacked", "unauthorised", "unauthorized", "phishing"],
    "card": ["card", "block", "lost", "stolen", "pin"],
    "hours": ["hours", "timing", "open", "branch"],
    "thanks": ["thanks", "thank you", "bye"],
}


def detect_intent(message: str) -> str:
    text = message.lower()
    best, best_score = "unknown", 0
    for intent, words in INTENTS.items():
        score = sum(1 for w in words if re.search(r"\b" + re.escape(w), text))
        if score > best_score:
            best, best_score = intent, score
    return best


def chatbot_reply(message: str, balance: float, recent_txns, insights) -> str:
    intent = detect_intent(message)
    if intent == "greeting":
        return "Hello! I'm your AI banking assistant. Ask me about your balance, spending, transfers or loans."
    if intent == "balance":
        return f"Your current balance is Rs. {balance:,.2f}."
    if intent == "history":
        if not recent_txns:
            return "You have no transactions yet."
        lines = [f"- {t['type'].replace('_', ' ').title()}: Rs. {t['amount']:,.2f} ({t['description'] or 'no note'})"
                 for t in recent_txns[:5]]
        return "Here are your latest transactions:\n" + "\n".join(lines)
    if intent == "spending":
        return insights["tip"]
    if intent == "transfer":
        return "To send money, open the Transfer page, enter the recipient's account number and amount. Large or unusual transfers are checked by our fraud-detection AI."
    if intent == "loan":
        return "Open the Loan page and enter your monthly income and EMIs. Our AI credit model will give you an instant eligibility estimate."
    if intent == "fraud":
        return "If you see an unauthorised transaction, change your password immediately and contact support. Never share your OTP or PIN with anyone."
    if intent == "card":
        return "To block a lost or stolen card, call the 24x7 helpline right away. (Demo bot: card management is not implemented.)"
    if intent == "hours":
        return "Digital banking is available 24x7. Branches are open Mon-Sat, 10am-4pm."
    if intent == "thanks":
        return "You're welcome! Have a great day."
    return "Sorry, I didn't get that. Try asking about your balance, recent transactions, spending, transfers, loans or fraud."


# --------------------------------------------------------------------------
# 4. Loan / credit assessment
# --------------------------------------------------------------------------
def loan_assessment(monthly_income, existing_emi, loan_amount, tenure_months, avg_balance, txn_count):
    """Rule-based credit score (300-900) and eligibility decision."""
    if monthly_income <= 0 or loan_amount <= 0 or tenure_months <= 0:
        return {"eligible": False, "score": 300, "message": "Please enter valid positive values.", "emi": 0}

    annual_rate = 0.11  # assumed flat 11% p.a.
    r = annual_rate / 12
    emi = loan_amount * r * (1 + r) ** tenure_months / ((1 + r) ** tenure_months - 1)

    dti = (existing_emi + emi) / monthly_income  # debt-to-income ratio
    score = 600
    score += 100 if dti < 0.3 else 40 if dti < 0.4 else -80 if dti < 0.5 else -160
    score += min(int(avg_balance / monthly_income * 40), 80)  # savings behaviour
    score += min(txn_count, 20) * 2                           # account activity
    score = max(300, min(900, score))

    eligible = score >= 650 and dti <= 0.5
    message = (f"Approved: estimated EMI Rs. {emi:,.0f}/month at 11% p.a." if eligible else
               "Not eligible right now. Try a smaller amount, a longer tenure or reduce existing EMIs.")
    return {"eligible": eligible, "score": score, "emi": round(emi, 2), "dti": round(dti * 100, 1), "message": message}


# --------------------------------------------------------------------------
# 5. Spending insights
# --------------------------------------------------------------------------
def spending_insights(transactions):
    totals = {}
    for t in transactions:
        if t["type"] in ("withdraw", "transfer_out") and t["status"] == "completed":
            totals[t["category"]] = totals.get(t["category"], 0) + t["amount"]
    total_spent = sum(totals.values())
    if not totals:
        return {"totals": {}, "total_spent": 0, "tip": "No spending recorded yet. Make a few transactions to get insights."}
    top_cat, top_amt = max(totals.items(), key=lambda kv: kv[1])
    share = top_amt / total_spent * 100
    tip = f"You spent Rs. {total_spent:,.0f} in total; {top_cat} is your biggest category ({share:.0f}%)."
    if share > 40:
        tip += f" Consider setting a monthly budget for {top_cat} to save more."
    return {"totals": dict(sorted(totals.items(), key=lambda kv: -kv[1])), "total_spent": total_spent, "tip": tip}
