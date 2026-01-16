from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
import os

from database import get_db, engine
import models
import schemas
import auth
from file_storage import file_storage
from personal_rag import PersonalRAGSystem

# Créer les tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Multi-Tenant SaaS API - Authentification Complète",
    description="API SaaS avec création de compte, reconnexion et séparation des données",
    version="2.0.0"
)

# Middleware CORS
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ENDPOINTS PUBLICS ====================

@app.post("/auth/register", response_model=schemas.Token)
def register_user(
    user_data: schemas.UserCreate,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Créer un nouveau compte client et utilisateur admin
    """
    # Vérifier si l'email existe déjà
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email déjà utilisé"
        )
    
    # Créer le client
    client = models.Client(
        name=user_data.email.split('@')[0],  # Nom basé sur l'email
        company_name=user_data.company_name,
        email=user_data.email,
        is_active=True
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    
    # Créer l'utilisateur admin
    hashed_password = auth.get_password_hash(user_data.password)
    user = models.User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        is_admin=True,
        client_id=client.id,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Générer un token d'accès
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@app.post("/auth/login", response_model=schemas.Token)
def login_user(
    login_data: schemas.UserLogin,
    db: Session = Depends(get_db)
):
    """
    Se connecter avec email/mot de passe
    """
    user = auth.authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Mettre à jour la date de dernière connexion
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Générer un token
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@app.post("/auth/refresh", response_model=schemas.Token)
def refresh_token(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Rafraîchir le token JWT
    """
    access_token = auth.create_access_token(
        data={"sub": str(current_user.id)}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": current_user
    }

# ==================== ENDPOINTS API KEYS ====================

@app.post("/api-keys/", response_model=schemas.ApiKey)
def create_api_key(
    api_key_data: schemas.ApiKeyCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Créer une nouvelle API Key pour l'utilisateur
    """
    # Générer une clé unique
    key = auth.generate_api_key()
    
    api_key = models.ApiKey(
        key=key,
        name=api_key_data.name,
        user_id=current_user.id,
        client_id=current_user.client_id,
        is_active=True
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return api_key

@app.get("/api-keys/", response_model=List[schemas.ApiKey])
def get_api_keys(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lister toutes les API Keys de l'utilisateur
    """
    api_keys = db.query(models.ApiKey).filter(
        models.ApiKey.user_id == current_user.id
    ).all()
    
    return api_keys

@app.delete("/api-keys/{api_key_id}")
def delete_api_key(
    api_key_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Désactiver une API Key
    """
    api_key = db.query(models.ApiKey).filter(
        models.ApiKey.id == api_key_id,
        models.ApiKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key non trouvée"
        )
    
    api_key.is_active = False
    db.commit()
    
    return {"message": "API Key désactivée avec succès"}

# ==================== ENDPOINTS PROFIL ====================

@app.get("/profile", response_model=schemas.User)
def get_profile(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Récupérer le profil de l'utilisateur connecté
    """
    return current_user

@app.put("/profile", response_model=schemas.User)
def update_profile(
    user_update: schemas.UserBase,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Mettre à jour le profil utilisateur
    """
    # Vérifier si l'email est déjà utilisé par un autre utilisateur
    if user_update.email != current_user.email:
        existing_user = db.query(models.User).filter(
            models.User.email == user_update.email,
            models.User.id != current_user.id
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email déjà utilisé"
            )
    
    current_user.email = user_update.email
    current_user.full_name = user_update.full_name
    
    db.commit()
    db.refresh(current_user)
    
    return current_user

# ==================== ENDPOINTS DOCUMENTS (sécurisés) ====================

@app.post("/documents/", response_model=schemas.Document)
def create_document(
    document: schemas.DocumentCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Créer un nouveau document pour le client connecté
    """
    db_document = models.Document(
        **document.dict(),
        client_id=current_user.client_id,
        user_id=current_user.id
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

@app.get("/documents/", response_model=List[schemas.Document])
def get_documents(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Récupérer tous les documents du client connecté
    """
    documents = db.query(models.Document).filter(
        models.Document.client_id == current_user.client_id
    ).offset(skip).limit(limit).all()
    return documents

@app.get("/documents/{document_id}", response_model=schemas.Document)
def get_document(
    document_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Récupérer un document spécifique du client connecté
    """
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.client_id == current_user.client_id
    ).first()
    
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    return document

@app.put("/documents/{document_id}", response_model=schemas.Document)
def update_document(
    document_id: int,
    document_update: schemas.DocumentCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Mettre à jour un document du client connecté
    """
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.client_id == current_user.client_id
    ).first()
    
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    for field, value in document_update.dict().items():
        setattr(document, field, value)
    
    document.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(document)
    return document

@app.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Supprimer un document du client connecté
    """
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.client_id == current_user.client_id
    ).first()
    
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    db.delete(document)
    db.commit()
    
    return {"message": "Document supprimé avec succès"}

@app.get("/search/", response_model=List[schemas.Document])
def search_documents(
    query: str,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Rechercher des documents par titre ou contenu pour le client connecté
    """
    documents = db.query(models.Document).filter(
        models.Document.client_id == current_user.client_id,
        (models.Document.title.contains(query)) | (models.Document.content.contains(query))
    ).all()
    return documents

# ==================== ENDPOINTS FICHIERS UTILISATEUR ====================

@app.post("/my-files/upload", response_model=schemas.UserFileMetadata)
async def upload_my_file(
    title: str = Form(...),
    tags: Optional[str] = Form(None),
    is_public: bool = Form(False),
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Uploader un fichier personnel
    """
    # Sauvegarder le fichier physiquement
    file_info = file_storage.save_user_file(
        client_id=current_user.client_id,
        user_id=current_user.id,
        file=file,
        title=title,
        tags=tags or ""
    )
    
    # Enregistrer les métadonnées en base
    db_file = models.UserFile(
        filename=file_info["filename"],
        original_filename=file_info.get("original_filename"),
        file_path=file_info["file_path"],
        title=file_info["title"],
        client_id=current_user.client_id,
        user_id=current_user.id,
        file_size=file_info["file_size"],
        mime_type=file_info["mime_type"],
        is_public=is_public,
        tags=tags or ""
    )
    
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    return db_file

@app.get("/my-files/", response_model=List[schemas.UserFileMetadata])
def list_my_files(
    skip: int = 0,
    limit: int = 100,
    tag: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lister tous mes fichiers personnels (avec filtre par tag optionnel)
    """
    query = db.query(models.UserFile).filter(
        models.UserFile.user_id == current_user.id
    )
    
    if tag:
        query = query.filter(models.UserFile.tags.contains(tag))
    
    files = query.offset(skip).limit(limit).all()
    return files

@app.get("/my-files/stats", response_model=schemas.UserStorageStats)
def get_my_storage_stats(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Obtenir les statistiques de mon stockage
    """
    stats = file_storage.get_storage_stats(
        client_id=current_user.client_id,
        user_id=current_user.id
    )
    return stats

@app.get("/my-files/{file_id}", response_model=schemas.UserFileContent)
def get_my_file(
    file_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Récupérer le contenu d'un de mes fichiers
    """
    file_meta = db.query(models.UserFile).filter(
        models.UserFile.id == file_id,
        models.UserFile.user_id == current_user.id  # Seulement ses propres fichiers
    ).first()
    
    if file_meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier non trouvé"
        )
    
    # Lire le contenu du fichier physique
    try:
        content = file_storage.read_user_file(
            current_user.client_id,
            current_user.id,
            file_meta.file_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de lecture du fichier: {str(e)}"
        )
    
    return {
        "id": file_meta.id,
        "title": file_meta.title,
        "content": content,
        "filename": file_meta.filename,
        "user_id": file_meta.user_id,
        "created_at": file_meta.created_at,
        "tags": file_meta.tags
    }

@app.get("/my-files/{file_id}/download")
def download_my_file(
    file_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Télécharger un de mes fichiers
    """
    file_meta = db.query(models.UserFile).filter(
        models.UserFile.id == file_id,
        models.UserFile.user_id == current_user.id
    ).first()
    
    if file_meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier non trouvé"
        )
    
    if not Path(file_meta.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier physique non trouvé"
        )
    
    return FileResponse(
        path=file_meta.file_path,
        filename=file_meta.original_filename or file_meta.filename,
        media_type=file_meta.mime_type
    )

@app.put("/my-files/{file_id}", response_model=schemas.UserFileMetadata)
def update_my_file(
    file_id: int,
    file_update: schemas.UserFileUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Mettre à jour les métadonnées d'un de mes fichiers
    """
    file_meta = db.query(models.UserFile).filter(
        models.UserFile.id == file_id,
        models.UserFile.user_id == current_user.id
    ).first()
    
    if file_meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier non trouvé"
        )
    
    # Mettre à jour les champs
    update_data = file_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(file_meta, field, value)
    
    file_meta.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(file_meta)
    
    return file_meta

@app.delete("/my-files/{file_id}")
def delete_my_file(
    file_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Supprimer un de mes fichiers
    """
    file_meta = db.query(models.UserFile).filter(
        models.UserFile.id == file_id,
        models.UserFile.user_id == current_user.id
    ).first()
    
    if file_meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier non trouvé"
        )
    
    # Supprimer le fichier physique
    try:
        file_storage.delete_user_file(
            current_user.client_id,
            current_user.id,
            file_meta.file_path
        )
    except HTTPException as he:
        # Propager les HTTPExceptions (404, 403...) telles quelles pour conserver le code et le détail
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression du fichier: {str(e)}"
        )
    
    # Supprimer l'entrée en base
    db.delete(file_meta)
    db.commit()
    
    return {"message": "Fichier supprimé avec succès"}

@app.get("/shared-files/", response_model=List[schemas.UserFileMetadata])
def list_shared_files(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lister les fichiers publics des autres utilisateurs de mon client
    """
    files = db.query(models.UserFile).filter(
        models.UserFile.client_id == current_user.client_id,
        models.UserFile.is_public == True,
        models.UserFile.user_id != current_user.id  # Exclure mes propres fichiers
    ).offset(skip).limit(limit).all()
    
    return files

@app.get("/my-files/search/", response_model=List[schemas.UserFileContent])
def search_in_my_files(
    query: str,
    tag: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Rechercher dans LE CONTENU de mes fichiers personnels
    """
    # 1. Récupérer mes fichiers (avec filtre tag si spécifié)
    files_query = db.query(models.UserFile).filter(
        models.UserFile.user_id == current_user.id
    )
    
    if tag:
        files_query = files_query.filter(models.UserFile.tags.contains(tag))
    
    my_files = files_query.all()
    
    results = []
    
    for file_meta in my_files:
        try:
            # Lire le contenu du fichier
            content = file_storage.read_user_file(
                current_user.client_id,
                current_user.id,
                file_meta.file_path
            )
            
            # Recherche dans le titre ET le contenu
            if (query.lower() in content.lower() or 
                query.lower() in file_meta.title.lower() or
                (file_meta.tags and query.lower() in file_meta.tags.lower())):
                
                # Extraire l'extrait pertinent
                excerpt = content
                if query.lower() in content.lower():
                    # Trouver la position de la requête
                    pos = content.lower().find(query.lower())
                    start = max(0, pos - 50)
                    end = min(len(content), pos + len(query) + 50)
                    excerpt = f"...{content[start:end]}..."
                
                results.append({
                    "id": file_meta.id,
                    "title": file_meta.title,
                    "content": excerpt,
                    "filename": file_meta.filename,
                    "user_id": file_meta.user_id,
                    "created_at": file_meta.created_at,
                    "tags": file_meta.tags
                })
        except Exception as e:
            print(f"Erreur de lecture du fichier {file_meta.filename}: {e}")
            continue
    
    return results

@app.post("/my-files/rag/query")
def rag_query_my_files(
    request: dict,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Interroger un chatbot RAG sur MES fichiers seulement
    """
    question = request.get("question", "")
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question requise"
        )
    
    # Initialiser le système RAG pour cet utilisateur
    rag_system = PersonalRAGSystem(current_user.id, current_user.client_id, db)
    
    # Traiter la question
    result = rag_system.query(question)
    
    return result

# ==================== ENDPOINTS ADMIN ====================

@app.get("/admin/users", response_model=List[schemas.User])
def get_all_users(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Récupérer tous les utilisateurs du même client (admin seulement)
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    users = db.query(models.User).filter(
        models.User.client_id == current_user.client_id
    ).all()
    
    return users

@app.post("/admin/users", response_model=schemas.User)
def create_user(
    user_data: schemas.UserCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Créer un nouvel utilisateur (admin seulement)
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    # Vérifier si l'email existe déjà
    if db.query(models.User).filter(models.User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email déjà utilisé"
        )
    
    hashed_password = auth.get_password_hash(user_data.password)
    user = models.User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_password,
        is_admin=False,  # Par défaut, pas admin
        client_id=current_user.client_id,
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user

# ==================== ENDPOINTS UTILITAIRES ====================

@app.get("/health")
def health_check():
    """
    Endpoint de vérification de santé de l'API
    """
    return {
        "status": "healthy",
        "service": "multi-tenant-saas-api",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/debug/client-info")
def debug_client_info(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint de debug pour voir les infos du client
    """
    client = current_user.client
    user_count = db.query(models.User).filter(
        models.User.client_id == current_user.client_id
    ).count()
    
    doc_count = db.query(models.Document).filter(
        models.Document.client_id == current_user.client_id
    ).count()
    
    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "company_name": client.company_name,
            "email": client.email,
            "created_at": client.created_at.isoformat()
        },
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "is_admin": current_user.is_admin
        },
        "statistics": {
            "users_count": user_count,
            "documents_count": doc_count
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
