import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User


def get_current_user(
    db: Session = Depends(get_db),
    x_user_email: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> User:
    email = _extract_email(x_user_email, authorization)

    user = db.query(User).filter(User.email == email).first()
    if user:
        return user

    user = User(email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _extract_email(x_user_email: str | None, authorization: str | None) -> str:
    if settings.auth_mode == "header":
        if not x_user_email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_auth")
        return x_user_email

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")
    if not settings.supabase_jwt_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="jwt_secret_not_configured")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc

    email = payload.get("email") or payload.get("user_email")
    if not email:
        sub = payload.get("sub")
        if isinstance(sub, str) and "@" in sub:
            email = sub
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="email_claim_missing")
    return str(email)
