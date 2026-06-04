from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "bankbot-secret-key"

ALGORITHM = "HS256"

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
