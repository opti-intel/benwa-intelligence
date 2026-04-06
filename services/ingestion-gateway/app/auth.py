"""
Authentication module — JWT tokens + bcrypt password hashing.
Roles: 'admin' (full access) | 'medewerker' (read-only planning)
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

# ---------------------------------------------------------------------------
# Config — override via environment variables in production
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "opti-intel-change-this-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_wachtwoord(wachtwoord: str) -> str:
    return pwd_context.hash(wachtwoord)


def verifieer_wachtwoord(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def valideer_wachtwoord(wachtwoord: str) -> list[str]:
    """
    Geeft een lijst van fouten terug. Lege lijst = wachtwoord is geldig.
    Regels: min. 8 tekens, 1 hoofdletter, 1 cijfer.
    """
    fouten = []
    if len(wachtwoord) < 8:
        fouten.append("Minimaal 8 tekens")
    if not any(c.isupper() for c in wachtwoord):
        fouten.append("Minimaal 1 hoofdletter")
    if not any(c.isdigit() for c in wachtwoord):
        fouten.append("Minimaal 1 cijfer")
    return fouten


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def maak_token(data: dict, verloopt_over: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + (verloopt_over or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decodeer_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ongeldig of verlopen token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Dependency: huidige gebruiker ophalen uit token
# ---------------------------------------------------------------------------

async def get_huidige_gebruiker(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decodeer_token(token)
    gebruiker_id = payload.get("sub")
    rol = payload.get("rol")
    naam = payload.get("naam")
    bedrijf = payload.get("bedrijf")
    if not gebruiker_id:
        raise HTTPException(status_code=401, detail="Ongeldig token")
    return {"id": gebruiker_id, "rol": rol, "naam": naam, "bedrijf": bedrijf}


async def vereist_admin(gebruiker: dict = Depends(get_huidige_gebruiker)) -> dict:
    if gebruiker.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Alleen beheerders hebben toegang")
    return gebruiker
