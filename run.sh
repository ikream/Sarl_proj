#!/bin/bash

echo "🚀 Démarrage de l'application SaaS Multi-Tenant..."

# Vérifier que Python est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    exit 1
fi

# Installer les dépendances du backend
cd backend
pip install -r requirements.txt

# Initialiser la BDD (depuis le dossier backend)
python init_db.py

# Lancer le backend en arrière-plan
if command -v uvicorn &> /dev/null; then
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload &
else
    python app.py &
fi

# Lancer le frontend
cd ../frontend
pip install -r requirements.txt
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &

echo "✅ Services démarrés. Backend: http://localhost:8000 | Frontend: http://localhost:8501"
