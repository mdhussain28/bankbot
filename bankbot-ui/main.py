from fastapi import FastAPI
from fastapi import Request
from fastapi import Form
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine
from sqlalchemy import text

import requests
import os

app = FastAPI(title="BankBot")

# --------------------------------------------------
# Config
# --------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bankbot:BankBot@123@postgres:5432/bankbot"
)

RISK_API_URL = os.getenv(
    "RISK_API_URL",
    "http://risk-api:8001"
)

engine = create_engine(DATABASE_URL)

# --------------------------------------------------
# Templates
# --------------------------------------------------

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

templates = Jinja2Templates(
    directory="templates"
)

# --------------------------------------------------
# Home
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request
        }
    )

# --------------------------------------------------
# Login
# --------------------------------------------------

@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):

    conn = engine.connect()

    user = conn.execute(
        text("""
        SELECT id, role
        FROM users
        WHERE username=:u
        """),
        {
            "u": username
        }
    ).fetchone()

    conn.close()

    if not user:

        return RedirectResponse(
            "/",
            status_code=302
        )

    if user.role == "admin":

        return RedirectResponse(
            "/admin",
            status_code=302
        )

    return RedirectResponse(
        f"/chat/{user.id}",
        status_code=302
    )

# --------------------------------------------------
# User Chat UI
# --------------------------------------------------

@app.get(
    "/chat/{user_id}",
    response_class=HTMLResponse
)
def chat_page(
    request: Request,
    user_id: int
):

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "user_id": user_id,
            "reply": "",
            "risk_score": "",
            "risk_flag": "",
            "model_version": ""
        }
    )

# --------------------------------------------------
# Ask BankBot
# --------------------------------------------------

@app.post(
    "/chat/{user_id}",
    response_class=HTMLResponse
)
def ask_bankbot(
    request: Request,
    user_id: int,
    message: str = Form(...)
):

    try:

        result = requests.get(
            f"{RISK_API_URL}/risk",
            params={
                "message": message
            },
            timeout=120
        ).json()

    except Exception as e:

        result = {
            "reply": str(e),
            "risk_score": 0,
            "risk_flag": "unknown",
            "model_version": "unknown"
        }

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
            "uid": user_id,
            "q": message,
            "a": result.get("reply"),
            "score": result.get("risk_score"),
            "flag": result.get("risk_flag")
        }
    )

    conn.commit()
    conn.close()

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "user_id": user_id,
            "reply": result.get("reply"),
            "risk_score": result.get("risk_score"),
            "risk_flag": result.get("risk_flag"),
            "model_version": result.get("model_version")
        }
    )

# --------------------------------------------------
# Admin Dashboard
# --------------------------------------------------

@app.get(
    "/admin",
    response_class=HTMLResponse
)
def admin_dashboard(
    request: Request
):

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

    reviews = []

    for r in rows:

        reviews.append(
            dict(r._mapping)
        )

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "reviews": reviews
        }
    )

# --------------------------------------------------
# Approve Review
# --------------------------------------------------

@app.get("/approve/{review_id}")
def approve(review_id: int):

    conn = engine.connect()

    conn.execute(
        text("""
        UPDATE review_queue
        SET status='approved'
        WHERE id=:id
        """),
        {
            "id": review_id
        }
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/admin",
        status_code=302
    )

# --------------------------------------------------
# Reject Review
# --------------------------------------------------

@app.get("/reject/{review_id}")
def reject(review_id: int):

    conn = engine.connect()

    conn.execute(
        text("""
        UPDATE review_queue
        SET status='rejected'
        WHERE id=:id
        """),
        {
            "id": review_id
        }
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/admin",
        status_code=302
    )

# --------------------------------------------------
# Health
# --------------------------------------------------

@app.get("/health")
def health():

    return {
        "status": "ok"
    }
