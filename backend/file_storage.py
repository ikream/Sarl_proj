import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
import mimetypes
from fastapi import UploadFile, HTTPException, status

class FileStorageManager:
    """Gestionnaire de stockage de fichiers pour chaque utilisateur"""
    
    def __init__(self, base_storage_path: str = "./user_files"):
        self.base_storage_path = Path(base_storage_path)
        self.base_storage_path.mkdir(exist_ok=True)
        
    def get_user_storage_path(self, client_id: int, user_id: int) -> Path:
        """Obtenir le chemin de stockage pour un utilisateur spécifique"""
        user_path = self.base_storage_path / f"client_{client_id}" / f"user_{user_id}"
        user_path.mkdir(parents=True, exist_ok=True)
        return user_path
    
    def save_user_file(self, client_id: int, user_id: int, file: UploadFile, title: str = None, tags: str = "") -> Dict[str, Any]:
        """Sauvegarder un fichier pour un utilisateur spécifique"""
        # Valider le type de fichier
        allowed_extensions = ['.txt', '.pdf', '.doc', '.docx', '.md']
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Seuls les fichiers {', '.join(allowed_extensions)} sont autorisés"
            )
        
        # Obtenir le chemin utilisateur
        user_path = self.get_user_storage_path(client_id, user_id)
        
        # Générer un nom de fichier unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename.replace(' ', '_')}"
        file_path = user_path / safe_filename
        
        # Sauvegarder le fichier
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Lire le contenu si c'est un fichier texte
        content = ""
        if file_ext == '.txt':
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                content = ""
        
        # Retourner les métadonnées
        return {
            "filename": safe_filename,
            "original_filename": file.filename,
            "file_path": str(file_path),
            "title": title or Path(file.filename).stem,
            "content": content,
            "file_size": file_path.stat().st_size,
            "mime_type": mimetypes.guess_type(file_path)[0] or "text/plain",
            "tags": tags
        }
    
    def read_user_file(self, client_id: int, user_id: int, file_path: str) -> str:
        """Lire le contenu d'un fichier utilisateur"""
        full_path = Path(file_path)
        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fichier non trouvé"
            )
        
        # Vérifier que le fichier appartient au bon utilisateur
        if not self._check_user_file_access(client_id, user_id, full_path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé à ce fichier"
            )
        
        # Lire selon le type de fichier
        file_ext = full_path.suffix.lower()
        if file_ext == '.txt':
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            # Pour les fichiers non-text, retourner le chemin seulement
            return f"Fichier binaire: {full_path.name}"
    
    def delete_user_file(self, client_id: int, user_id: int, file_path: str) -> bool:
        """Supprimer un fichier utilisateur"""
        full_path = Path(file_path)
        # If the file does not exist, return a 404 so the caller can handle it
        if not full_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fichier physique non trouvé"
            )

        # Vérifier les permissions (après avoir confirmé l'existence)
        if not self._check_user_file_access(client_id, user_id, full_path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé à ce fichier"
            )

        # Supprimer le fichier
        try:
            full_path.unlink()
            return True
        except Exception as e:
            # Renvoyer une erreur claire au caller
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Impossible de supprimer le fichier: {e}"
            )
    
    def list_user_files(self, client_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Lister tous les fichiers d'un utilisateur"""
        user_path = self.get_user_storage_path(client_id, user_id)
        files = []
        
        for file_path in user_path.glob("*"):
            if file_path.is_file():
                stats = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "original_filename": file_path.stem,
                    "file_path": str(file_path),
                    "file_size": stats.st_size,
                    "created_at": datetime.fromtimestamp(stats.st_ctime),
                    "updated_at": datetime.fromtimestamp(stats.st_mtime),
                    "mime_type": mimetypes.guess_type(file_path)[0] or "application/octet-stream"
                })
        
        return files
    
    def list_public_files_in_client(self, client_id: int) -> List[Dict[str, Any]]:
        """Lister les fichiers publics de tous les utilisateurs d'un client"""
        client_path = self.base_storage_path / f"client_{client_id}"
        public_files = []
        
        if not client_path.exists():
            return []
        
        # Parcourir tous les dossiers utilisateurs
        for user_dir in client_path.iterdir():
            if user_dir.is_dir():
                for file_path in user_dir.glob("*"):
                    if file_path.is_file():
                        stats = file_path.stat()
                        public_files.append({
                            "filename": file_path.name,
                            "user_folder": user_dir.name,
                            "file_path": str(file_path),
                            "file_size": stats.st_size,
                            "created_at": datetime.fromtimestamp(stats.st_ctime)
                        })
        
        return public_files
    
    def _check_user_file_access(self, client_id: int, user_id: int, file_path: Path) -> bool:
        """Vérifier qu'un fichier appartient à un utilisateur spécifique"""
        expected_path = self.get_user_storage_path(client_id, user_id)
        return str(file_path).startswith(str(expected_path))
    
    def get_storage_stats(self, client_id: int, user_id: int) -> Dict[str, Any]:
        """Obtenir les statistiques de stockage d'un utilisateur"""
        user_path = self.get_user_storage_path(client_id, user_id)
        
        total_size = 0
        file_count = 0
        
        for file_path in user_path.glob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
        
        return {
            "user_id": user_id,
            "client_id": client_id,
            "file_count": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "storage_path": str(user_path)
        }

# Instance globale
file_storage = FileStorageManager()
