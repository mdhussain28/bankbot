from fastapi import FastAPI
import requests
import json
import socket
import os
import time
from sqlalchemy import create_engine, text

app = FastAPI()

# ---------------------------------------------------
# Configuration
# ---------------------------------------------------

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://bankbot-llm-ollama:11434"
)

MODEL = os.getenv(
    "MODEL",
    "qwen2.5:0.5b"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bankbot:BankBot@123@postgres:5432/bankbot"
)

engine = create_engine(DATABASE_URL)

HIGH_CONFIDENCE = 0.80
REVIEW_CONFIDENCE = 0.50

# ---------------------------------------------------
# Banking Policies
# ---------------------------------------------------

POLICIES = {

    "account_fraud":
        (
            "Potential fraud detected. "
            "Please contact customer support immediately "
            "or visit your nearest branch."
        ),

    "lost_card":
        (
            "Your card may be at risk. "
            "Please block it immediately using mobile banking "
            "or contact customer support."
        ),

    "account_locked":
        (
            "Please visit your nearest branch with valid ID "
            "for account verification."
        )
}

# ---------------------------------------------------
# Review Queue
# ---------------------------------------------------

def save_review(question, answer, confidence):

    try:

        conn = engine.connect()

        conn.execute(
            text("""
                INSERT INTO review_queue(
                    question,
                    ai_answer,
                    confidence,
                    status
                )
                VALUES(
                    :q,
                    :a,
                    :c,
                    'pending'
                )
            """),
            {
                "q": question,
                "a": answer,
                "c": confidence
            }
        )

        conn.commit()
        conn.close()

    except Exception as e:

        print("Review queue error:", e)

# ---------------------------------------------------
# Intent Prompt
# ---------------------------------------------------

def classification_prompt(message):

    return f"""
You are a banking risk engine.

Analyze the customer message.

Return ONLY valid JSON.

Intent options:

balance_check
loan_query
lost_card
account_fraud
banking_info
unknown

Risk scoring:

0.0 to 1.0

High risk examples:

- stolen money
- unauthorized transaction
- fraud
- hacked account
- scam

Message:

{message}

Return format:

{{
"intent":"",
"confidence":0.0,
"risk_score":0.0,
"risk_flag":""
}}
"""

# ---------------------------------------------------
# Answer Prompt
# ---------------------------------------------------

def answer_prompt(message):

    return f"""
You are BankBot.

Rules:

1. Answer only banking questions.
2. Be concise.
3. Never discuss politics.
4. Never discuss religion.
5. Never provide investment advice.
6. If not banking related, say:
   "I can assist only with banking services."

Customer:

{message}
"""

# ---------------------------------------------------
# Ollama Call
# ---------------------------------------------------

def call_ollama(prompt):

    payload = {

        "model": MODEL,

        "prompt": prompt,

        "stream": False
    }

    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json=payload,
        timeout=120
    )

    return r.json()

# ---------------------------------------------------
# Intent Detection
# ---------------------------------------------------

def classify(message):

    result = call_ollama(
        classification_prompt(message)
    )

    raw = result.get(
        "response",
        "{}"
    )

    try:

        return json.loads(raw)

    except:

        return {
            "intent": "unknown",
            "confidence": 0.40,
            "risk_score": 0.20,
            "risk_flag": "low_risk"
        }

# ---------------------------------------------------
# Answer Generation
# ---------------------------------------------------

def generate_answer(message):

    result = call_ollama(
        answer_prompt(message)
    )

    return result.get(
        "response",
        "Unable to generate answer."
    )

# ---------------------------------------------------
# Health
# ---------------------------------------------------

@app.get("/health")
def health():

    return {

        "status": "ok",

        "model": MODEL,

        "served_by": socket.gethostname()
    }

# ---------------------------------------------------
# Ready
# ---------------------------------------------------

@app.get("/ready")
def ready():

    try:

        requests.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=5
        )

        return {
            "ready": True
        }

    except:

        return {
            "ready": False
        }

# ---------------------------------------------------
# Risk API
# ---------------------------------------------------

@app.get("/risk")
def risk(message: str):

    start = time.time()

    result = classify(message)

    intent = result.get(
        "intent",
        "unknown"
    )

    confidence = float(
        result.get(
            "confidence",
            0.5
        )
    )

    risk_score = float(
        result.get(
            "risk_score",
            0.2
        )
    )

    risk_flag = result.get(
        "risk_flag",
        "low_risk"
    )

    # ---------------------------------------
    # Banking Policy Overrides
    # ---------------------------------------

    if intent == "account_fraud":

        answer = POLICIES[
            "account_fraud"
        ]

    elif intent == "lost_card":

        answer = POLICIES[
            "lost_card"
        ]

    else:

        answer = generate_answer(
            message
        )

    # ---------------------------------------
    # Human Review Workflow
    # ---------------------------------------

    if confidence < REVIEW_CONFIDENCE:

        save_review(
            message,
            answer,
            confidence
        )

        answer = (
            "Your query requires specialist review. "
            "Our banking team will contact you."
        )

    elif confidence < HIGH_CONFIDENCE:

        save_review(
            message,
            answer,
            confidence
        )

    # ---------------------------------------
    # Response
    # ---------------------------------------

    return {

        "reply": answer,

        "intent": intent,

        "confidence": confidence,

        "risk_score": risk_score,

        "risk_flag": risk_flag,

        "model_version": MODEL,

        "processing_ms": round(
            (time.time() - start) * 1000,
            2
        ),

        "served_by": socket.gethostname()
    }
