import json
from database import SessionLocal, engine
import models
from sqlalchemy.orm import Session
from auth import get_password_hash


def init_database():
    """Initialiser la base de données avec les données de test"""
    # Créer les tables
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # Créer des clients et utilisateurs de test
        clients_data = [
            {
                "name": "client_a",
                "company_name": "Entreprise A SA",
                "email": "contact@client-a.com",
                "users": [
                    {
                        "email": "admin@client-a.com",
                        "password": "password123",
                        "full_name": "Admin Client A",
                        "is_admin": True
                    },
                    {
                        "email": "user@client-a.com",
                        "password": "password123",
                        "full_name": "Utilisateur Client A",
                        "is_admin": False
                    }
                ]
            },
            {
                "name": "client_b",
                "company_name": "Société B SARL",
                "email": "info@client-b.com",
                "users": [
                    {
                        "email": "admin@client-b.com",
                        "password": "password456",
                        "full_name": "Admin Client B",
                        "is_admin": True
                    }
                ]
            }
        ]

        for client_data in clients_data:
            client = db.query(models.Client).filter(
                models.Client.email == client_data["email"]
            ).first()

            if not client:
                client = models.Client(
                    name=client_data["name"],
                    company_name=client_data["company_name"],
                    email=client_data["email"],
                    is_active=True
                )
                db.add(client)
                db.commit()
                db.refresh(client)
                print(f"✅ Client créé: {client.name}")

            # Créer les utilisateurs
            for user_data in client_data["users"]:
                user = db.query(models.User).filter(
                    models.User.email == user_data["email"]
                ).first()

                if not user:
                    user = models.User(
                        email=user_data["email"],
                        full_name=user_data["full_name"],
                        hashed_password=get_password_hash(user_data["password"]),
                        is_admin=user_data["is_admin"],
                        client_id=client.id,
                        is_active=True
                    )
                    db.add(user)
                    print(f"   👤 Utilisateur créé: {user.email}")

        db.commit()
        print("\n🎉 Base de données initialisée avec succès!")

        # Ajouter des documents réels fournis
        add_test_documents(db)

    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        db.rollback()
    finally:
        db.close()


def add_test_documents(db: Session):
    """Ajouter les documents réels fournis"""
    documents_data = [
        {
            "title": "Procédure résiliation",
            "content": "Procédure résiliation\nLa résiliation doit être enregistrée dans le CRM.\nUn accusé de réception est envoyé sous 48h.\nLe responsable conformité valide les dossiers sensibles.",
            "client_name": "client_a",
            "user_email": "admin@client-a.com"
        },
        {
            "title": "Produit RC Pro A",
            "content": "Produit RC Pro A\nLa RC Pro couvre les dommages causés aux tiers dans le cadre de l'activité déclarée.\nExclusion : travaux en hauteur au-delà de 3 mètres.\nDéclaration de sinistre : service sinistres@assureur-a.fr.",
            "client_name": "client_a",
            "user_email": "admin@client-a.com"
        },
        {
            "title": "Procédure sinistre",
            "content": "Procédure sinistre\nTout sinistre doit être déclaré dans les 5 jours ouvrés.\nL'équipe gestion transmet le dossier au gestionnaire assureur.\nLe suivi du sinistre est effectué de manière hebdomadaire.",
            "client_name": "client_b",
            "user_email": "admin@client-b.com"
        },
        {
            "title": "Produit RC Pro B",
            "content": "Produit RC Pro B\nLa RC Pro couvre l'activité déclarée.\nExclusion : sous-traitance non déclarée.\nDéclaration de sinistre : claims@assureur-b.com.",
            "client_name": "client_b",
            "user_email": "admin@client-b.com"
        }
    ]
    
    for doc_data in documents_data:
        # Trouver le client
        client = db.query(models.Client).filter(
            models.Client.name == doc_data["client_name"]
        ).first()
        
        # Trouver l'utilisateur
        user = db.query(models.User).filter(
            models.User.email == doc_data["user_email"]
        ).first()
        
        if client and user:
            # Vérifier si le document existe déjà
            existing = db.query(models.Document).filter(
                models.Document.title == doc_data["title"],
                models.Document.client_id == client.id
            ).first()
            
            if not existing:
                document = models.Document(
                    title=doc_data["title"],
                    content=doc_data["content"],
                    client_id=client.id,
                    user_id=user.id
                )
                db.add(document)
                print(f"   📄 Document créé: {doc_data['title']}")
    
    db.commit()
    print(f"\n📚 {len(documents_data)} documents réels ajoutés")
    print("   Client A: Procédure résiliation, Produit RC Pro A")
    print("   Client B: Procédure sinistre, Produit RC Pro B")


if __name__ == "__main__":
    init_database()
