from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import secrets

from database import get_db
import models
import schemas

# Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Pour l'authentification API Key
API_KEY_HEADER = HTTPBearer(auto_error=False)

# Use pbkdf2_sha256 as primary to avoid bcrypt binary issues on some environments;
# keep bcrypt as a fallback for compatibility with any existing hashes.
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")

# Utilitaires de hash
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# Gestion des tokens JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# Authentification utilisateur
def authenticate_user(db: Session, email: str, password: str):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    if not user.is_active:
        return False
    return user

# Dépendances d'authentification
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(API_KEY_HEADER),
    db: Session = Depends(get_db)
):
    if credentials:
        # Vérifier si c'est un token JWT
        payload = verify_token(credentials.credentials)
        if payload:
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token invalide"
                )
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Utilisateur non trouvé"
                )
            return user
        
        # Vérifier si c'est une API Key
        api_key = db.query(models.ApiKey).filter(
            models.ApiKey.key == credentials.credentials,
            models.ApiKey.is_active == True
        ).first()
        
        if api_key:
            # Mettre à jour la date d'utilisation
            api_key.last_used = datetime.utcnow()
            db.commit()
            
            user = db.query(models.User).filter(models.User.id == api_key.user_id).first()
            if user and user.is_active:
                return user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentification requise",
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Utilisateur inactif")
    return current_user

def get_current_client(current_user: models.User = Depends(get_current_active_user)):
    client = current_user.client
    if not client or not client.is_active:
        raise HTTPException(status_code=400, detail="Client inactif ou non trouvé")
    return client

# Génération d'API Key
def generate_api_key(length: int = 32):
    return f"tema_{secrets.token_urlsafe(length)}"
