# Multi-Tenant SaaS Application

Application SaaS permettant à plusieurs clients d'avoir leurs propres espaces de données séparés.

## Architecture

- **Backend**: FastAPI avec authentification par clé API
- **Frontend**: Streamlit pour l'interface utilisateur
- **Base de données**: SQLite (simplicité) - facilement migrable vers PostgreSQL
- **Séparation des données**: Basée sur le header HTTP `X-APP-KEY`

## Installation

### Prérequis
- Python 3.9+
- pip

### Installation manuelle

1. **Cloner le repository**

```bash
git clone <repository-url>
cd multi-tenant-saas
```

2. **Installer les dépendances du backend**

```bash
cd backend
pip install -r requirements.txt
```

3. **Initialiser la base de données**

```bash
python init_db.py
```

4. **Lancer le backend**

```bash
python app.py
# ou
uvicorn app:app --reload --port 8000
```

5. **Dans un autre terminal, lancer le frontend**

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### Installation avec Docker
```bash
docker-compose up --build
```

## Run locally (without Docker) — detailed (Windows PowerShell)

If you prefer to run the application locally without Docker (recommended for quick testing or debugging on a developer machine), follow these step-by-step instructions for Windows PowerShell. These commands assume you're running on the same machine that hosts the source tree.

1) Stop any running Docker containers that may occupy ports 8000 or 8501 (optional but recommended):

```powershell
cd 'c:\Users\FD Tech\Documents\Sarl_projet'
docker compose down
```

2) Create and activate a Python virtual environment (recommended):

```powershell
cd 'c:\Users\FD Tech\Documents\Sarl_projet\backend'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3) Install backend dependencies:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

4) Initialize the database (creates tables, sample clients/users and documents):

```powershell
# Run the DB initializer which creates clients/users and sample documents
python init_db.py
```

5) Seed per-user personal files (optional but used by the demo frontend):

```powershell
python init_personal_files.py
```

6) Start the backend (FastAPI + Uvicorn) in a dedicated terminal (keep it running):

```powershell
# From backend folder
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Notes:
- If you changed `API_BASE_URL` logic or run the frontend in Docker, set `API_BASE_URL` accordingly (e.g. `http://backend:8000`). For local runs you can leave the default `http://localhost:8000`.

7) In a separate terminal, create/activate a venv for the frontend and install frontend deps, then run Streamlit:

```powershell
cd 'c:\Users\FD Tech\Documents\Sarl_projet\frontend'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# If you run the frontend containerized, set API_BASE_URL to http://backend:8000; for local runs, keep default
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

8) Open the UI in your browser:

- Streamlit frontend: http://localhost:8501
- API health: http://localhost:8000/health
- Swagger UI: http://localhost:8000/docs

Quick manual test (PowerShell):

```powershell
# Login (returns access_token)
$body = @{email='admin@client-a.com'; password='password123'} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/auth/login -ContentType 'application/json' -Body $body

# Use the token to list personal files
# Replace <TOKEN> with access_token from previous command
Invoke-RestMethod -Method Get -Uri http://localhost:8000/my-files/ -Headers @{Authorization = "Bearer <TOKEN>"}
```

Troubleshooting tips
- Connection refused when calling the API: make sure the backend uvicorn process is running and listening on 127.0.0.1:8000. Use `netstat -ano | findstr ":8000"` to check port usage and `Stop-Process -Id <PID>` to kill a stuck process.
- SQLite "database is locked": ensure no other process has a long-running write transaction. Close any running backend instances or Docker containers using the same DB file.
- Streamlit DuplicateWidgetID: if you see Streamlit errors about widget keys, refresh the page and ensure you're using the latest `frontend/app.py` from this repo (we added unique keys and prefill handling).
- If frontend can't reach backend when frontend runs in Docker, set the environment variable `API_BASE_URL=http://backend:8000` for the frontend process or container.

If you want, I can add a short PowerShell script (start-local.ps1) to automate these steps (create venvs, install, init DB and start both services). Ask and I'll add it to the repo.

## Utilisation

### Accès aux applications
- **Backend API**: http://localhost:8000
- **Frontend Streamlit**: http://localhost:8501
- **Documentation API**: http://localhost:8000/docs (Swagger UI)

### Clients disponibles
1. **Client A**
   - Clé API: `temaTA_key`
   - Documents: Documents stratégiques et financiers

2. **Client B**
   - Clé API: `temaTB_key`
   - Documents: Contrats et analyses de marché

### Tester la séparation des données

#### Avec cURL
```bash
# Client A
curl -H "X-APP-KEY: temaTA_key" http://localhost:8000/documents/

# Client B
curl -H "X-APP-KEY: temaTB_key" http://localhost:8000/documents/
```

#### Avec l'interface
1. Accédez à http://localhost:8501
2. Utilisez le sélecteur dans la sidebar pour changer de client
3. Observez que les documents changent complètement

## Tests

```bash
# Naviguer vers le dossier tests
cd tests

# Lancer les tests
python test_api.py

# ou avec pytest
pytest test_api.py -v
```

## Validation avec les documents fournis

Ce dépôt contient maintenant les vrais documents fournis pour les clients A et B. Voici comment initialiser, lancer et valider le comportement (PowerShell-friendly).

1) Initialiser la base de données avec les documents réels

```powershell
cd 'c:\Users\FD Tech\Documents\Sarl_projet\backend'
pip install -r requirements.txt
python init_db.py
```

Vous devriez voir la création des clients, utilisateurs et l'ajout des 4 documents :

- Procédure résiliation (Client A)
- Produit RC Pro A (Client A)
- Procédure sinistre (Client B)
- Produit RC Pro B (Client B)

2) Lancer le backend

```powershell
uvicorn app:app --reload --port 8000
```

3) Tests manuels rapides (PowerShell)

```powershell
# Login Admin Client A
$resp = curl -s -X POST "http://localhost:8000/auth/login" -H "Content-Type: application/json" -d '{"email":"admin@client-a.com","password":"password123"}'
$tokenA = ($resp | ConvertFrom-Json).access_token

# Login Admin Client B
$resp = curl -s -X POST "http://localhost:8000/auth/login" -H "Content-Type: application/json" -d '{"email":"admin@client-b.com","password":"password456"}'
$tokenB = ($resp | ConvertFrom-Json).access_token

# Lister les documents
curl -s -X GET "http://localhost:8000/documents/" -H "Authorization: Bearer $tokenA" | jq '.[].title'
curl -s -X GET "http://localhost:8000/documents/" -H "Authorization: Bearer $tokenB" | jq '.[].title'

# Rechercher "résiliation" (doit trouver le document de Client A seulement)
curl -s -X GET "http://localhost:8000/search/?query=résiliation" -H "Authorization: Bearer $tokenA" | jq .
curl -s -X GET "http://localhost:8000/search/?query=résiliation" -H "Authorization: Bearer $tokenB" | jq .

# Rechercher "hebdomadaire" (mot unique à Client B) — ne doit rien retourner pour A
curl -s -X GET "http://localhost:8000/search/?query=hebdomadaire" -H "Authorization: Bearer $tokenA" | jq .

```

4) Test automatisé fourni

Un script de test `tests/test_specific_documents.py` est inclus :

```powershell
cd 'c:\Users\FD Tech\Documents\Sarl_projet'
python tests/test_specific_documents.py
```

Le script exécute :
- login pour `admin@client-a.com` et `admin@client-b.com`
- vérification des listes de documents
- recherches ciblées (résiliation, hebdomadaire, etc.)

Résultat attendu :

```
Client A documents:
   "Procédure résiliation"
   "Produit RC Pro A"

Client B documents:
   "Procédure sinistre"
   "Produit RC Pro B"

Les recherches retournent uniquement les documents du client interrogé (séparation stricte).
```

Remarque sur un terme observé
- Le mot `sinistre` apparaît également dans le contenu du document "Produit RC Pro A" (email de contact `sinistres@assureur-a.fr`).
- Pour cette raison, un test qui cherchait explicitement `sinistre` pour valider "aucune réponse pour A" échouerait — j'ai donc utilisé le terme `hebdomadaire` (unique à Client B) dans le script de test. Si vous préférez que la recherche `sinistre` renvoie vide pour A, je peux retirer ce mot de `Produit RC Pro A`.

## Approche technique

### Séparation multi-tenant
1. **Authentification par clé API**: Chaque requête doit inclure `X-APP-KEY` dans le header
2. **Middleware de validation**: Vérifie la clé API et récupère le client correspondant
3. **Filtrage automatique**: Toutes les requêtes sont automatiquement filtrées par `client_id`
4. **Isolation totale**: Un client ne peut jamais accéder aux données d'un autre client

## Points d'amélioration potentiels

1. **Production**: 
   - Utiliser PostgreSQL au lieu de SQLite
   - Ajouter HTTPS
   - Implémenter un système de rotation des clés API
   - Ajouter du logging et du monitoring

2. **Fonctionnalités**:
   - Pagination avancée
   - Filtrage plus complexe
   - Export des données
   - Gestion des permissions utilisateur par client

3. **Performance**:
   - Mise en cache des requêtes fréquentes
   - Indexation avancée pour la recherche
   - Compression des documents volumineux
