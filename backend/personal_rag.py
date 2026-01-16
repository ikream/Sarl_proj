# personal_rag_simple.py - VERSION CORRIGÉE POUR QUESTIONS GÉNÉRALES
import logging
import os
import re
import json
import pickle
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from pathlib import Path

from file_storage import file_storage
import models

# Optional BM25 dependency (best-effort)
try:
    from rank_bm25 import BM25Okapi
except Exception:
    BM25Okapi = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Document:
    """Classe Document simplifiée pour remplacer langchain.schema.Document"""
    def __init__(self, page_content: str, metadata: dict = None):
        self.page_content = page_content
        self.metadata = metadata or {}


class PersonalRAGSystem:
    """
    Système RAG personnel pour TOUTES les questions générales
    IGNORE les fichiers d'exemple mais répond à toutes les questions pertinentes
    """
    
    def __init__(self, user_id: int, client_id: int, db: Session):
        self.user_id = user_id
        self.client_id = client_id
        self.db = db
        self.file_manager = file_storage
        
        # Initialisation simple
        self.all_documents = []
        # For hybrid search compatibility
        self.all_chunks: List[Any] = []
        self.chunk_id_map: Dict[int, int] = {}
        self.vector_store = None
        self.bm25_index = None
        self.ingested_file_ids = set()
        self.index_path = f"./rag_index/user_{user_id}"
        
        # Fichiers d'exemple à IGNORER COMPLÈTEMENT
        self.EXAMPLE_FILES_TO_IGNORE = [
            "Mes Notes Administratives",
            "Procédures Internes", 
            "Mes Documents Personnels",
            "Suivi de Mes Projets",
            "mes_notes_admin.txt",
            "procédures_internes.txt",
            "mes_documents_personnels.txt",
            "suivi_projets.txt"
        ]
        
        # Charger ou créer l'index
        self._initialize_system()
    
    def _initialize_system(self):
        """Initialiser le système"""
        # Créer le dossier si nécessaire
        os.makedirs(self.index_path, exist_ok=True)
        
        # TOUJOURS charger les fichiers utilisateur à jour
        self.user_files = self._load_user_files()

        # Si des fichiers existent, RECONSTRUIRE l'index
        if self.user_files:
            # Réinitialiser l'index existant
            self.ingested_file_ids = set()
            self.all_documents = []
            self._build_index()
            logger.info(f"[User {self.user_id}] Index reconstruit avec {len(self.user_files)} fichiers utilisateur")
        else:
            # Essayer de charger l'index existant seulement si aucun fichier
            if not self._load_existing_index():
                # Construire un nouvel index vide
                self._build_index()
    
    def _load_user_files(self) -> List[Dict]:
        """Charger les fichiers de l'utilisateur depuis la base - IGNORER LES FICHIERS D'EXEMPLE"""
        files_meta = self.db.query(models.UserFile).filter(
            models.UserFile.user_id == self.user_id
        ).all()
        
        files = []
        for meta in files_meta:
            # FILTRER : ignorer COMPLÈTEMENT les fichiers d'exemple
            if (meta.title in self.EXAMPLE_FILES_TO_IGNORE or 
                meta.filename in self.EXAMPLE_FILES_TO_IGNORE or
                (meta.original_filename and meta.original_filename in self.EXAMPLE_FILES_TO_IGNORE)):
                logger.info(f"[User {self.user_id}] IGNORÉ (fichier d'exemple): '{meta.title}'")
                continue
                
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
                
                logger.info(f"[User {self.user_id}] Chargé (fichier utilisateur): '{meta.title}'")
                
            except Exception as e:
                logger.error(f"[User {self.user_id}] Erreur lecture {meta.filename}: {e}")
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
        """Construire l'index de recherche - IGNORER LES FICHIERS D'EXEMPLE"""
        if not self.user_files:
            logger.warning(f"[User {self.user_id}] Aucun fichier utilisateur à indexer (après filtrage)")
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
            logger.info(f"[User {self.user_id}] Aucun nouveau document utilisateur")
            return
        
        # Ajouter aux documents existants
        self.all_documents.extend(new_documents)
        
        # Sauvegarder
        self._save_index()
        
        logger.info(f"[User {self.user_id}] Index mis à jour: {len(new_documents)} nouveaux documents utilisateur")
    
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

        # Update in-memory chunks mapping for hybrid search
        try:
            self.all_chunks = self.all_documents
            self.chunk_id_map = {id(doc): i for i, doc in enumerate(self.all_chunks)}
            # Build BM25 index if possible
            if BM25Okapi:
                tokenized = [doc.page_content.lower().split() for doc in self.all_chunks]
                try:
                    self.bm25_index = BM25Okapi(tokenized) if tokenized else None
                except Exception:
                    self.bm25_index = None
        except Exception:
            # non-fatal
            pass

    def _hybrid_search(self, query: str, k: int = 10) -> List[Tuple[Any, float]]:
        """Hybrid search: BM25 + Vector similarity.
        Works when either FAISS vector_store OR BM25 index is available.
        """
        if not getattr(self, 'all_chunks', None):
            # fallback to documents list
            self.all_chunks = self.all_documents
            self.chunk_id_map = {id(doc): i for i, doc in enumerate(self.all_chunks)}

        if not self.vector_store and not self.bm25_index:
            return []

        tokenized_query = query.lower().split()
        # BM25 scores (may be empty)
        if self.bm25_index:
            try:
                bm25_scores = self.bm25_index.get_scores(tokenized_query)
            except Exception:
                bm25_scores = [0.0] * len(self.all_chunks) if self.all_chunks else []
        else:
            bm25_scores = [0.0] * len(self.all_chunks) if self.all_chunks else []

        max_bm25 = max(bm25_scores) if bm25_scores and max(bm25_scores) > 0 else 1
        bm25_norm = [s / max_bm25 for s in bm25_scores] if bm25_scores else []

        # Vector similarity (if FAISS available)
        vector_results = []
        if self.vector_store:
            try:
                vector_results = self.vector_store.similarity_search_with_score(query, k=k*2)
            except Exception as e:
                logger.warning("⚠️ Vector search failed: %s", e)
                vector_results = []

        vector_scores = {id(doc): 1 / (1 + dist) for doc, dist in vector_results}

        combined = []
        for doc in self.all_chunks:
            doc_id = id(doc)
            idx = self.chunk_id_map.get(doc_id)
            bm25_score = bm25_norm[idx] if idx is not None and idx < len(bm25_norm) else 0
            vec_score = vector_scores.get(doc_id, 0)
            score = 0.6 * vec_score + 0.4 * bm25_score
            combined.append((doc, score))

        combined.sort(key=lambda x: x[1], reverse=True)
        return combined[:k]
    
    def _search_simple(self, query: str, k: int = 5) -> List[Document]:
        """Recherche simple par mot-clé - POUR TOUTES LES QUESTIONS"""
        if not self.all_documents:
            return []
        
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))
        
        scored_docs = []
        
        for doc in self.all_documents:
            # VÉRIFIER que ce n'est pas un fichier d'exemple
            title = doc.metadata.get("title", "")
            filename = doc.metadata.get("filename", "")
            
            if (title in self.EXAMPLE_FILES_TO_IGNORE or 
                filename in self.EXAMPLE_FILES_TO_IGNORE):
                continue  # IGNORER COMPLÈTEMENT
            
            content_lower = doc.page_content.lower()
            title_lower = title.lower()
            
            # Score basé sur la pertinence GÉNÉRALE
            score = 0
            
            # 1. Correspondance EXACTE avec le titre (très important)
            for q_word in query_words:
                if len(q_word) > 2 and q_word in title_lower:
                    score += 20
            
            # 2. Correspondance dans le contenu
            for q_word in query_words:
                if len(q_word) > 3 and q_word in content_lower:
                    score += 5
            
            # 3. Nombre de correspondances totales
            total_matches = sum(1 for word in query_words if len(word) > 2 and word in content_lower)
            score += total_matches * 3
            
            # 4. BONUS pour les phrases complètes dans le contenu
            # Vérifier si des groupes de mots sont présents
            if len(query_words) >= 2:
                # Chercher des paires de mots
                query_word_list = list(query_words)
                for i in range(len(query_word_list)):
                    for j in range(i+1, len(query_word_list)):
                        word1 = query_word_list[i]
                        word2 = query_word_list[j]
                        if len(word1) > 2 and len(word2) > 2:
                            if word1 in content_lower and word2 in content_lower:
                                score += 15  # Bonus pour plusieurs mots trouvés
            
            # 5. BONUS pour documents récents (si date disponible)
            # Pas de pénalités - on accepte tous les documents pertinents
            
            # SEUIL MODÉRÉ pour être considéré pertinent
            if score >= 10:  # Seuil modéré pour questions générales
                scored_docs.append((doc, score))
        
        # Si pas de résultats PERTINENTS, retourner liste VIDE
        if not scored_docs:
            logger.info(f"[User {self.user_id}] Aucun document pertinent pour: '{query}'")
            return []
        
        # Trier par score
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # Debug détaillé
        logger.info(f"[User {self.user_id}] Recherche: '{query}' - {len(scored_docs)} documents pertinents")
        for i, (doc, score) in enumerate(scored_docs[:3]):
            title = doc.metadata.get("title", "Sans titre")
            logger.info(f"  {i+1}. '{title}' - Score: {score}")
        
        return [doc for doc, score in scored_docs[:k]]
    
    def _extract_best_response(self, question: str, docs: List[Document]) -> Optional[str]:
        """Extraire la meilleure réponse des documents - POUR TOUTES LES QUESTIONS"""
        if not docs:
            return None
            
        question_lower = question.lower()
        
        # Prendre les 3 meilleurs documents
        top_docs = docs[:3]
        relevant_snippets = []
        
        for doc in top_docs:
            content = doc.page_content
            title = doc.metadata.get("title", "")
            content_lower = content.lower()
            
            # VÉRIFIER LA PERTINENCE BASIQUE
            question_words = set(re.findall(r'\w+', question_lower))
            content_words = set(re.findall(r'\w+', content_lower))
            overlap = len(question_words & content_words)
            
            # Si moins de 2 mots en commun, document peu pertinent
            if overlap < 2 and len(question_words) > 3:
                continue
            
            # Chercher les parties les plus pertinentes
            lines = content.split('\n')
            relevant_lines = []
            
            for line in lines:
                line = line.strip()
                if not line or len(line) < 15:  # Lignes trop courtes ignorées
                    continue
                    
                line_lower = line.lower()
                line_score = 0
                
                # Score basé sur la correspondance avec la question
                line_words = set(re.findall(r'\w+', line_lower))
                line_overlap = len(question_words & line_words)
                
                if question_words:
                    line_score = line_overlap / len(question_words) * 100
                
                # Bonus pour les mots clés importants
                important_keywords = ["important", "déclaration", "procédure", "couvre", 
                                    "garantit", "exclusion", "obligatoire", "nécessaire",
                                    "étape", "processus", "condition", "règle"]
                
                for keyword in important_keywords:
                    if keyword in line_lower:
                        line_score += 10
                
                # Si la ligne est pertinente, l'ajouter
                if line_score >= 20:  # Seuil modéré
                    relevant_lines.append((line, line_score))
            
            # Trier les lignes par pertinence et prendre les 2 meilleures
            relevant_lines.sort(key=lambda x: x[1], reverse=True)
            best_lines = [line for line, score in relevant_lines[:2]]
            
            if best_lines:
                snippet = f"**{title}:**\n" + "\n".join([f"• {line}" for line in best_lines])
                relevant_snippets.append(snippet)
        
        # Si on a trouvé des snippets pertinents
        if relevant_snippets:
            # Limiter à 3 snippets maximum
            snippets_to_show = relevant_snippets[:3]
            return "\n\n".join(snippets_to_show)
        
        # Fallback : extrait intelligent du document le plus pertinent
        if top_docs:
            best_doc = top_docs[0]
            content = best_doc.page_content
            title = best_doc.metadata.get("title", "Document")
            
            # Essayer de trouver un paragraphe pertinent
            paragraphs = re.split(r'\n\s*\n', content)  # Split par paragraphes
            
            best_paragraph = None
            best_score = 0
            
            for para in paragraphs:
                para = para.strip()
                if len(para) < 50 or len(para) > 500:  # Paragraphes trop courts/longs
                    continue
                    
                para_lower = para.lower()
                para_words = set(re.findall(r'\w+', para_lower))
                para_overlap = len(question_words & para_words)
                
                if question_words:
                    para_score = para_overlap / len(question_words) * 100
                    
                    if para_score > best_score:
                        best_score = para_score
                        best_paragraph = para
            
            if best_paragraph and best_score >= 15:
                return f"**{title}:**\n{best_paragraph}"
            
            # Dernier recours : début du document
            excerpt = content[:300].strip()
            if excerpt:
                # Essayer de finir sur une phrase complète
                last_period = excerpt.rfind('.')
                if last_period > 150:  # Au moins 150 caractères avant le point
                    excerpt = excerpt[:last_period + 1]
                
                return f"**Extrait de {title}:**\n{excerpt}..."
        
        return None
    
    def query(self, question: str) -> Dict[str, Any]:
        """Traiter une question utilisateur - POUR TOUTES LES QUESTIONS"""
        logger.info(f"[User {self.user_id}] Question: '{question}'")
        
        # Vérifier si l'utilisateur a des documents (après filtrage des exemples)
        user_files = self._load_user_files()
        
        if not user_files:
            return {
                "question": question,
                "answer": "❌ Vous n'avez pas encore uploadé de documents personnels.",
                "sources": [],
                "has_results": False,
                "user_id": self.user_id,
                "relevance_score": 0.0,
                "quality": "vide"
            }
        
        if not self.all_documents:
            return {
                "question": question,
                "answer": "❌ Aucun document indexé. Veuillez rafraîchir l'index RAG avec /my-files/rag/refresh",
                "sources": [],
                "has_results": False,
                "user_id": self.user_id,
                "relevance_score": 0.0,
                "quality": "vide"
            }
        
        # Rechercher les documents pertinents
        hybrid_results = self._hybrid_search(question, k=10)
        relevant_docs = [doc for doc, _ in hybrid_results] if hybrid_results else []

        # Si hybrid_search ne donne rien, fallback à la recherche simple
        if not relevant_docs:
            relevant_docs = self._search_simple(question, k=5)
        
        logger.info(f"[User {self.user_id}] Documents trouvés: {len(relevant_docs)}")

        # Vérifier qu'on a des documents PERTINENTS
        if not relevant_docs:
            return {
                "question": question,
                "answer": f"🤔 Je n'ai pas trouvé d'informations correspondant à votre question dans vos documents.\n\n"
                         f"**Question :** {question}\n\n"
                         f"**Suggestion :** Vérifiez que vos documents contiennent des informations sur ce sujet, "
                         f"ou essayez de reformuler votre question.",
                "sources": [],
                "has_results": False,
                "user_id": self.user_id,
                "relevance_score": 0.0,
                "quality": "non pertinente"
            }
        
        # Générer une réponse
        answer = self._extract_best_response(question, relevant_docs)

        # Si pas de réponse pertinente
        if not answer:
            # Lister les documents consultés
            consulted_titles = [doc.metadata.get("title", "Document") for doc in relevant_docs[:3]]
            
            return {
                "question": question,
                "answer": f"🔍 Je n'ai pas trouvé de réponse précise à votre question dans vos documents.\n\n"
                         f"**Documents consultés :** {', '.join(consulted_titles)}\n\n"
                         f"**Suggestion :** Les documents peuvent ne pas contenir l'information exacte recherchée. "
                         f"Essayez de poser votre question différemment ou vérifiez vos documents.",
                "sources": consulted_titles,
                "has_results": False,
                "user_id": self.user_id,
                "documents_consulted": len(relevant_docs),
                "relevance_score": 0.0,
                "quality": "non pertinente"
            }

        # Si une réponse a été trouvée
        # Calculer un score de pertinence
        question_lower = question.lower()
        answer_lower = answer.lower()

        question_words = set(re.findall(r'\w+', question_lower))
        answer_words = set(re.findall(r'\w+', answer_lower))

        relevance_score = 0.0
        if question_words:
            overlap = len(question_words & answer_words)
            relevance_score = min(overlap / len(question_words), 1.0)

        # Préparer les sources
        sources = []
        for i, doc in enumerate(relevant_docs[:3]):
            title = doc.metadata.get("title", "Document sans titre")
            filename = doc.metadata.get("filename", "")

            if filename:
                source_text = f"{title} ({filename})"
            else:
                source_text = title

            sources.append(source_text)

        # Déterminer la qualité
        if relevance_score >= 0.7:
            quality = "excellente"
        elif relevance_score >= 0.5:
            quality = "bonne"
        elif relevance_score >= 0.3:
            quality = "moyenne"
        else:
            quality = "faible"

        logger.info(f"[User {self.user_id}] Réponse générée - Score: {relevance_score}, Qualité: {quality}")

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "has_results": True,
            "user_id": self.user_id,
            "documents_count": len(relevant_docs),
            "relevance_score": round(relevance_score, 2),
            "quality": quality
        }
    
    def refresh(self):
        """Rafraîchir l'index avec les nouveaux fichiers"""
        # Recharger les fichiers
        self.user_files = self._load_user_files()
        
        # Reconstruire l'index
        self._build_index()
        
        return {
            "status": "success",
            "user_id": self.user_id,
            "total_files_utilisateur": len(self.user_files),
            "indexed_files": len(self.ingested_file_ids),
            "documents_indexés": len(self.all_documents),
            "message": "Index RAG rafraîchi pour toutes les questions générales"
        }
    
    def get_info(self):
        """Obtenir des informations sur le système"""
        # Analyser les types de documents disponibles (hors fichiers d'exemple)
        document_titles = []
        
        for doc in self.all_documents:
            title = doc.metadata.get("title", "")
            
            # Filtrer les fichiers d'exemple
            if title in self.EXAMPLE_FILES_TO_IGNORE:
                continue
                
            document_titles.append(title)
        
        return {
            "user_id": self.user_id,
            "status": "ready" if self.all_documents else "empty",
            "total_fichiers_utilisateur": len(self.user_files),
            "fichiers_indexés": len(self.ingested_file_ids),
            "documents_stockés": len(self.all_documents),
            "index_path": self.index_path,
            "titres_documents_disponibles": document_titles[:15],  # Limiter à 15 pour lisibilité
            "configuration": "RAG général - répond à toutes les questions"
        }