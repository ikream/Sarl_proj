import os
from pathlib import Path
from database import SessionLocal
import models
from file_storage import FileStorageManager

def init_personal_files():
    """Initialiser les fichiers personnels pour chaque utilisateur"""
    db = SessionLocal()
    file_manager = FileStorageManager()
    
    try:
        # Récupérer tous les utilisateurs
        users = db.query(models.User).all()
        
        for user in users:
            user_path = file_manager.get_user_storage_path(user.client_id, user.id)
            print(f"📁 Dossier de {user.email}: {user_path}")
            
            # Créer des fichiers d'exemple personnalisés
            create_personal_sample_files(user, user_path, db)
    
    finally:
        db.close()

def create_personal_sample_files(user, user_path, db):
    """Créer des fichiers .txt personnels pour un utilisateur"""
    
    # Fichiers spécifiques selon le rôle
    if user.is_admin:
        sample_files = [
            {
                "filename": "mes_notes_admin.txt",
                "title": "Mes Notes Administratives",
                "content": f"""MES NOTES - {user.full_name}
                
Rapports à générer chaque mois :
1. Rapport d'activité clients
2. Suivi des paiements
3. Audit sécurité

Contacts importants :
- Support technique : tech@{user.client.email}
- Comptabilité : accounting@{user.client.email}

Projets en cours :
• Migration base de données
• Mise à jour sécurité
""",
                "tags": "admin,rapports,contacts"
            },
            {
                "filename": "procédures_internes.txt",
                "title": "Procédures Internes",
                "content": """PROCÉDURES INTERNES

Création de compte utilisateur :
1. Vérifier l'email dans le CRM
2. Générer un mot de passe temporaire
3. Envoyer les instructions de connexion

Gestion des incidents :
• Niveau 1 : Support utilisateur
• Niveau 2 : Administration système
• Niveau 3 : Développeur
""",
                "tags": "procédures,administration"
            }
        ]
    else:
        sample_files = [
            {
                "filename": "mes_documents_personnels.txt",
                "title": "Mes Documents Personnels",
                "content": f"""DOCUMENTS DE {user.full_name}

Informations personnelles :
• Poste : Utilisateur standard
• Date d'embauche : 2023-01-15
• Manager : Administration

Fichiers importants :
- Contrat de travail
- Notes de réunion
- Suivi de projet

Objectifs trimestriels :
1. Formation produit
2. Documentation utilisateur
3. Tests qualité
""",
                "tags": "personnel,documents"
            },
            {
                "filename": "suivi_projets.txt", 
                "title": "Suivi de Mes Projets",
                "content": """SUIVI DE PROJETS

Projet Alpha :
• Statut : En cours
• Deadline : 2024-03-15
• Livrables : 3/5 complétés

Projet Beta :
• Statut : Planification
• Deadline : 2024-06-30
• Équipe : 4 membres
""",
                "tags": "projets,suivi"
            }
        ]
    
    for file_info in sample_files:
        file_path = user_path / file_info["filename"]
        
        # Écrire le fichier
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_info["content"])
        
        # Enregistrer en base
        user_file = models.UserFile(
            filename=file_info["filename"],
            original_filename=file_info["filename"],
            file_path=str(file_path),
            title=file_info["title"],
            client_id=user.client_id,
            user_id=user.id,
            file_size=file_path.stat().st_size,
            mime_type="text/plain",
            is_public=False,  # Par défaut privé
            tags=file_info["tags"]
        )
        
        db.add(user_file)
    
    db.commit()
    print(f"   ✅ Fichiers personnels créés pour {user.email}")

if __name__ == "__main__":
    init_personal_files()
