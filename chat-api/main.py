from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from passlib.hash import bcrypt
from jose import jwt
from datetime import datetime, timedelta

# --------------------------------------------------
# Configuration
# --------------------------------------------------

DATABASE_URL = (
    "postgresql://bankbot:BankBot@123"
    "@postgres.bankbot.svc.cluster.local:5432/bankbot"
)

SECRET_KEY = "bankbot-secret-key"
ALGORITHM = "HS256"

engine = create_engine(DATABASE_URL)

app = FastAPI(title="BankBot API")

# --------------------------------------------------
# Models
# --------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    user_id: int
    message: str


class ApproveRequest(BaseModel):
    review_id: int
    answer: str


# --------------------------------------------------
# JWT
# --------------------------------------------------

def create_token(username):

    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=12)
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# --------------------------------------------------
# Health
# --------------------------------------------------

@app.get("/health")
def health():

    return {
        "status": "ok"
    }


# --------------------------------------------------
# Register
# --------------------------------------------------

@app.post("/register")
def register(req: RegisterRequest):

    conn = engine.connect()

    existing = conn.execute(
        text("""
            SELECT id
            FROM users
            WHERE username=:u
        """),
        {"u": req.username}
    ).fetchone()

    if existing:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    conn.execute(
        text("""
            INSERT INTO users(
                username,
                password_hash,
                role
            )
            VALUES(
                :u,
                :p,
                'user'
            )
        """),
        {
            "u": req.username,
            "p": bcrypt.hash(req.password)
        }
    )

    conn.commit()
    conn.close()

    return {
        "status": "registered"
    }


# --------------------------------------------------
# Login
# --------------------------------------------------

@app.post("/login")
def login(req: LoginRequest):

    conn = engine.connect()

    row = conn.execute(
        text("""
            SELECT
                username,
                password_hash,
                role
            FROM users
            WHERE username=:u
        """),
        {"u": req.username}
    ).fetchone()

    conn.close()

    if not row:

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not bcrypt.verify(
        req.password,
        row.password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    token = create_token(
        row.username
    )

    return {
        "token": token,
        "role": row.role
    }


# --------------------------------------------------
# Chat
# --------------------------------------------------

@app.post("/chat")
def chat(req: ChatRequest):

    answer = (
        "AI service not integrated yet. "
        "Part 3 will connect Ollama."
    )

    risk_score = 0.0
    risk_flag = "unknown"

    conn = engine.connect()

    conn.execute(
        text("""
            INSERT INTO conversations(
                user_id,
                question,
                answer,
                risk_score,
                risk_flag
            )
            VALUES(
                :uid,
                :q,
                :a,
                :score,
                :flag
            )
        """),
        {
            "uid": req.user_id,
            "q": req.message,
            "a": answer,
            "score": risk_score,
            "flag": risk_flag
        }
    )

    conn.commit()
    conn.close()

    return {
        "reply": answer,
        "risk_score": risk_score,
        "risk_flag": risk_flag
    }


# --------------------------------------------------
# Conversation History
# --------------------------------------------------

@app.get("/history/{user_id}")
def history(user_id: int):

    conn = engine.connect()

    rows = conn.execute(
        text("""
            SELECT
                id,
                question,
                answer,
                risk_score,
                risk_flag,
                created_at
            FROM conversations
            WHERE user_id=:uid
            ORDER BY id DESC
            LIMIT 50
        """),
        {
            "uid": user_id
        }
    ).fetchall()

    conn.close()

    return {
        "history": [
            dict(r._mapping)
            for r in rows
        ]
    }


# --------------------------------------------------
# Admin - Pending Reviews
# --------------------------------------------------

@app.get("/admin/reviews")
def pending_reviews():

    conn = engine.connect()

    rows = conn.execute(
        text("""
            SELECT *
            FROM review_queue
            WHERE status='pending'
            ORDER BY id DESC
        """)
    ).fetchall()

    conn.close()

    return {
        "reviews": [
            dict(r._mapping)
            for r in rows
        ]
    }


# --------------------------------------------------
# Admin Approve
# --------------------------------------------------

@app.post("/admin/approve")
def approve(req: ApproveRequest):

    conn = engine.connect()

    review = conn.execute(
        text("""
            SELECT *
            FROM review_queue
            WHERE id=:id
        """),
        {
            "id": req.review_id
        }
    ).fetchone()

    if not review:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Review not found"
        )

    conn.execute(
        text("""
            INSERT INTO approved_answers(
                question_pattern,
                answer,
                category
            )
            VALUES(
                :q,
                :a,
                'approved'
            )
        """),
        {
            "q": review.question,
            "a": req.answer
        }
    )

    conn.execute(
        text("""
            UPDATE review_queue
            SET status='approved',
                reviewed_at=NOW()
            WHERE id=:id
        """),
        {
            "id": req.review_id
        }
    )

    conn.commit()
    conn.close()

    return {
        "status": "approved"
    }


# --------------------------------------------------
# Admin Reject
# --------------------------------------------------

@app.post("/admin/reject/{review_id}")
def reject(review_id: int):

    conn = engine.connect()

    conn.execute(
        text("""
            UPDATE review_queue
            SET status='rejected',
                reviewed_at=NOW()
            WHERE id=:id
        """),
        {
            "id": review_id
        }
    )

    conn.commit()
    conn.close()

    return {
        "status": "rejected"
    }


# --------------------------------------------------
# Approved Answers
# --------------------------------------------------

@app.get("/admin/approved")
def approved_answers():

    conn = engine.connect()

    rows = conn.execute(
        text("""
            SELECT *
            FROM approved_answers
            ORDER BY id DESC
        """)
    ).fetchall()

    conn.close()

    return {
        "approved_answers": [
            dict(r._mapping)
            for r in rows
        ]
    }


# --------------------------------------------------
# Users
# --------------------------------------------------

@app.get("/admin/users")
def users():

    conn = engine.connect()

    rows = conn.execute(
        text("""
            SELECT
                id,
                username,
                role,
                created_at
            FROM users
            ORDER BY id
        """)
    ).fetchall()

    conn.close()

    return {
        "users": [
            dict(r._mapping)
            for r in rows
        ]
    }
