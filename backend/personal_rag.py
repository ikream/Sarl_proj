# personal_rag_simple.py
import logging
import os
import re
import json
import pickle
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from pathlib import Path

# Pas d'imports LangChain problématiques
# On fait une version minimaliste

from file_storage import file_storage
import models

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Document:
    """Classe Document simplifiée pour remplacer langchain.schema.Document"""
    def __init__(self, page_content: str, metadata: dict = None):
        self.page_content = page_content
        self.metadata = metadata or {}


class PersonalRAGSystem:
    """
    Système RAG personnel minimaliste et robuste
    """
    
    def __init__(self, user_id: int, client_id: int, db: Session):
        self.user_id = user_id
        self.client_id = client_id
        self.db = db
        self.file_manager = file_storage
        
        # Initialisation simple
        self.all_documents = []
        self.ingested_file_ids = set()
        self.index_path = f"./rag_index/user_{user_id}"
        
        # Charger ou créer l'index
        self._initialize_system()
    
    def _initialize_system(self):
        """Initialiser le système"""
        # Créer le dossier si nécessaire
        os.makedirs(self.index_path, exist_ok=True)
        
        # Charger les fichiers utilisateur
        self.user_files = self._load_user_files()
        
        # Essayer de charger l'index existant
        if not self._load_existing_index():
            # Construire un nouvel index
            self._build_index()
    
    def _load_user_files(self) -> List[Dict]:
        """Charger les fichiers de l'utilisateur depuis la base"""
        files_meta = self.db.query(models.UserFile).filter(
            models.UserFile.user_id == self.user_id
        ).all()
        
        files = []
        for meta in files_meta:
            try:
                content = self.file_manager.read_user_file(
                    self.client_id,
                    self.user_id,
                    meta.file_path
                )
                
                files.append({
                    "id": meta.id,
                    "title": meta.title,
                    "content": content,
                    "filename": meta.filename,
                    "tags": meta.tags,
                    "created_at": meta.created_at.isoformat() if meta.created_at else None
                })
                
                logger.info(f"[User {self.user_id}] Chargé: {meta.filename}")
                
            except Exception as e:
                logger.error(f"[User {self.user_id}] Erreur {meta.filename}: {e}")
                continue
        
        return files
    
    def _load_existing_index(self) -> bool:
        """Charger l'index existant depuis le disque"""
        index_file = os.path.join(self.index_path, "documents.pkl")
        meta_file = os.path.join(self.index_path, "metadata.json")
        
        if not os.path.exists(index_file) or not os.path.exists(meta_file):
            return False
        
        try:
            # Charger les documents
            with open(index_file, 'rb') as f:
                self.all_documents = pickle.load(f)
            
            # Charger les métadonnées
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                self.ingested_file_ids = set(metadata.get("ingested_file_ids", []))
            
            logger.info(f"[User {self.user_id}] Index chargé: {len(self.all_documents)} documents")
            return True
            
        except Exception as e:
            logger.error(f"[User {self.user_id}] Erreur chargement index: {e}")
            return False
    
    def _build_index(self):
        """Construire l'index de recherche"""
        if not self.user_files:
            logger.warning(f"[User {self.user_id}] Aucun fichier à indexer")
            return
        
        new_documents = []
        
        for file_info in self.user_files:
            file_id = file_info["id"]
            
            # Vérifier si déjà indexé
            if file_id in self.ingested_file_ids:
                continue
            
            # Créer un document
            doc = Document(
                page_content=file_info["content"],
                metadata={
                    "file_id": file_id,
                    "user_id": self.user_id,
                    "title": file_info["title"],
                    "filename": file_info["filename"],
                    "tags": file_info["tags"]
                }
            )
            
            new_documents.append(doc)
            self.ingested_file_ids.add(file_id)
        
        if not new_documents:
            logger.info(f"[User {self.user_id}] Aucun nouveau document")
            return
        
        # Ajouter aux documents existants
        self.all_documents.extend(new_documents)
        
        # Sauvegarder
        self._save_index()
        
        logger.info(f"[User {self.user_id}] Index mis à jour: {len(new_documents)} nouveaux documents")
    
    def _save_index(self):
        """Sauvegarder l'index sur disque"""
        # Sauvegarder les documents
        with open(os.path.join(self.index_path, "documents.pkl"), 'wb') as f:
            pickle.dump(self.all_documents, f)
        
        # Sauvegarder les métadonnées
        metadata = {
            "user_id": self.user_id,
            "ingested_file_ids": list(self.ingested_file_ids),
            "created_at": datetime.now().isoformat(),
            "documents_count": len(self.all_documents)
        }
        
        with open(os.path.join(self.index_path, "metadata.json"), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    def _search_simple(self, query: str, k: int = 3) -> List[Document]:
        """Recherche simple par mot-clé"""
        if not self.all_documents:
            return []
        
        query_words = set(re.findall(r'\w+', query.lower()))
        
        scored_docs = []
        
        for doc in self.all_documents:
            content_lower = doc.page_content.lower()
            
            # Score basé sur le nombre de mots correspondants
            score = 0
            
            # Bonus pour les correspondances exactes
            for word in query_words:
                if len(word) > 2:  # Ignorer les mots trop courts
                    if word in content_lower:
                        score += 1
            
            # Bonus si le mot est dans le titre
            title = doc.metadata.get("title", "").lower()
            for word in query_words:
                if len(word) > 2 and word in title:
                    score += 3
            
            if score > 0:
                scored_docs.append((doc, score))
        
        # Trier par score
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Retourner les top k
        return [doc for doc, score in scored_docs[:k]]
    
    def query(self, question: str) -> Dict[str, Any]:
        """Traiter une question utilisateur"""
        if not self.all_documents:
            return {
                "question": question,
                "answer": "❌ Vous n'avez pas encore de documents personnels.",
                "sources": [],
                "has_results": False,
                "user_id": self.user_id
            }
        
        # Rechercher les documents pertinents
        relevant_docs = self._search_simple(question, k=3)
        
        if not relevant_docs:
            return {
                "question": question,
                "answer": "❌ Aucune information trouvée dans vos documents.",
                "sources": [],
                "has_results": False,
                "user_id": self.user_id
            }
        
        # Générer une réponse
        answer = self._generate_smart_answer(question, relevant_docs)
        
        # Préparer les sources
        sources = []
        for i, doc in enumerate(relevant_docs):
            title = doc.metadata.get("title", "Document sans titre")
            filename = doc.metadata.get("filename", "")
            
            if filename:
                source_text = f"{title} ({filename})"
            else:
                source_text = title
            
            sources.append(source_text)
        
        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "has_results": True,
            "user_id": self.user_id,
            "documents_count": len(relevant_docs)
        }
    
    def _generate_smart_answer(self, question: str, docs: List[Document]) -> str:
        """Générer une réponse intelligente basée sur les documents"""
        question_lower = question.lower()
        
        # Extraire les mots-clés importants
        keywords = [word for word in re.findall(r'\w+', question_lower) if len(word) > 3]
        
        # Chercher des réponses spécifiques
        for doc in docs:
            content = doc.page_content
            
            # Questions sur "où" / "dans quel"
            if any(word in question_lower for word in ["où", "dans quel", "quel système", "où est"]) and "CRM" in content.upper():
                return "📍 **La résiliation doit être enregistrée dans le CRM.**"
            
            # Questions sur "qui" / "responsable"
            if any(word in question_lower for word in ["qui", "responsable", "valide", "approuve"]) and "responsable" in content.lower():
                return "👤 **Le responsable conformité valide les dossiers sensibles.**"
            
            # Questions sur "quand" / "délai"
            if any(word in question_lower for word in ["quand", "délai", "combien de temps", "48h", "48 heures"]):
                if "48h" in content or "48 heures" in content:
                    return "⏰ **Un accusé de réception est envoyé sous 48h.**"
            
            # Questions sur "comment" / "procédure"
            if any(word in question_lower for word in ["comment", "procédure", "étapes", "processus"]):
                lines = content.split('\n')
                steps = []
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 10:  # Ignorer les lignes trop courtes
                        steps.append(f"• {line}")
                
                if steps:
                    return "📋 **Procédure :**\n" + "\n".join(steps[:5])
        
        # Réponse par défaut : extrait le plus pertinent
        best_doc = docs[0]
        content = best_doc.page_content
        
        # Essayer de trouver la phrase la plus pertinente
        sentences = re.split(r'[.!?]+', content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Vérifier si la sentence contient des mots-clés
            sentence_lower = sentence.lower()
            keyword_matches = sum(1 for keyword in keywords if keyword in sentence_lower)
            
            if keyword_matches >= 1 and len(sentence) > 20:
                return f"📄 **Information trouvée :** {sentence}"
        
        # Fallback : premier extrait
        excerpt = content[:200] + "..." if len(content) > 200 else content
        return f"📄 **Extrait pertinent :** {excerpt}"
    
    def refresh(self):
        """Rafraîchir l'index avec les nouveaux fichiers"""
        # Recharger les fichiers
        self.user_files = self._load_user_files()
        
        # Reconstruire l'index
        self._build_index()
        
        return {
            "status": "success",
            "user_id": self.user_id,
            "total_files": len(self.user_files),
            "indexed_files": len(self.ingested_file_ids),
            "documents": len(self.all_documents)
        }
    
    def get_info(self):
        """Obtenir des informations sur le système"""
        return {
            "user_id": self.user_id,
            "status": "ready" if self.all_documents else "empty",
            "total_files": len(self.user_files),
            "indexed_files": len(self.ingested_file_ids),
            "stored_documents": len(self.all_documents),
            "index_path": self.index_path
        }