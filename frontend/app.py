import streamlit as st
import requests
import json
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
import os
from io import BytesIO

# Configuration
API_BASE_URL = "http://localhost:8000"

# Initialisation de session
if 'auth' not in st.session_state:
    st.session_state.auth = {
        'is_authenticated': False,
        'access_token': None,
        'user': None,
        'client': None
    }

if 'current_page' not in st.session_state:
    st.session_state.current_page = "login"

# Clés API prédéfinies pour le test
PREDEFINED_API_KEYS = {
    "Client A": "temaTA_key",
    "Client B": "temaTB_key"
}

# ==================== UTILS ====================
def get_headers():
    """Récupérer les headers d'authentification"""
    headers = {"Content-Type": "application/json"}
    if st.session_state.auth['access_token']:
        headers["Authorization"] = f"Bearer {st.session_state.auth['access_token']}"
    return headers

def get_headers_multipart():
    """Récupérer les headers pour les requêtes multipart (upload de fichiers)"""
    headers = {}
    if st.session_state.auth['access_token']:
        headers["Authorization"] = f"Bearer {st.session_state.auth['access_token']}"
    return headers

def make_request(endpoint: str, method: str = "GET", data: Optional[dict] = None, files: Optional[dict] = None):
    """Faire une requête à l'API"""
    if files:
        # Requête multipart (upload de fichiers)
        headers = get_headers_multipart()
        url = f"{API_BASE_URL}{endpoint}"
        
        try:
            if method == "POST":
                response = requests.post(url, headers=headers, files=files, data=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, files=files, data=data)
            else:
                st.error(f"Méthode {method} non supportée avec files")
                return None
            
            if response.status_code == 401 and refresh_token():
                headers = get_headers_multipart()
                if method == "POST":
                    response = requests.post(url, headers=headers, files=files, data=data)
                elif method == "PUT":
                    response = requests.put(url, headers=headers, files=files, data=data)
            
            response.raise_for_status()
            return response.json() if response.content else {"message": "Success"}
            
        except requests.exceptions.RequestException as e:
            handle_request_error(e)
            return None
    else:
        # Requête JSON standard
        headers = get_headers()
        url = f"{API_BASE_URL}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            
            if response.status_code == 401 and refresh_token():
                headers = get_headers()
                if method == "GET":
                    response = requests.get(url, headers=headers)
                elif method == "POST":
                    response = requests.post(url, headers=headers, json=data)
                elif method == "PUT":
                    response = requests.put(url, headers=headers, json=data)
                elif method == "DELETE":
                    response = requests.delete(url, headers=headers)
            
            response.raise_for_status()
            return response.json() if response.content else {"message": "Success"}
            
        except requests.exceptions.RequestException as e:
            handle_request_error(e)
            return None

def handle_request_error(e):
    """Gérer les erreurs de requête"""
    if hasattr(e, 'response') and e.response is not None:
        try:
            error_detail = e.response.json().get('detail', str(e))
        except:
            error_detail = str(e)
    else:
        error_detail = str(e)
    
    st.error(f"Erreur API: {error_detail}")

def refresh_token():
    """Rafraîchir le token JWT"""
    try:
        headers = get_headers()
        response = requests.post(f"{API_BASE_URL}/auth/refresh", headers=headers)
        if response.status_code == 200:
            data = response.json()
            st.session_state.auth['access_token'] = data['access_token']
            st.session_state.auth['user'] = data['user']
            return True
    except:
        pass
    return False

def login_with_credentials(email: str, password: str):
    """Se connecter avec email/mot de passe"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.auth.update({
                'is_authenticated': True,
                'access_token': data['access_token'],
                'user': data['user']
            })
            return True, "Connexion réussie!"
        else:
            return False, response.json().get('detail', 'Erreur de connexion')
            
    except Exception as e:
        return False, f"Erreur: {str(e)}"

def login_with_api_key(api_key: str):
    """Se connecter avec une clé API"""
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(f"{API_BASE_URL}/profile", headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            st.session_state.auth.update({
                'is_authenticated': True,
                'access_token': api_key,
                'user': user_data
            })
            return True, "Connexion avec clé API réussie!"
        else:
            return False, "Clé API invalide"
            
    except Exception as e:
        return False, f"Erreur: {str(e)}"

def register_user(email: str, password: str, full_name: str, company_name: str):
    """Créer un nouveau compte"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": full_name,
                "company_name": company_name
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            st.session_state.auth.update({
                'is_authenticated': True,
                'access_token': data['access_token'],
                'user': data['user']
            })
            return True, "Compte créé avec succès!"
        else:
            return False, response.json().get('detail', 'Erreur lors de la création')
            
    except Exception as e:
        return False, f"Erreur: {str(e)}"

def logout():
    """Se déconnecter"""
    st.session_state.auth = {
        'is_authenticated': False,
        'access_token': None,
        'user': None,
        'client': None
    }
    st.session_state.current_page = "login"

# ==================== NOUVELLES FONCTIONS POUR FICHIERS ====================
def upload_personal_file(file, title: str, tags: str = "", is_public: bool = False):
    """Uploader un fichier personnel"""
    try:
        files = {'file': (file.name, file, file.type)}
        data = {'title': title, 'tags': tags, 'is_public': str(is_public).lower()}
        
        headers = get_headers_multipart()
        response = requests.post(
            f"{API_BASE_URL}/my-files/upload",
            headers=headers,
            files=files,
            data=data
        )
        
        if response.status_code == 200:
            return True, "Fichier uploadé avec succès!", response.json()
        else:
            return False, response.json().get('detail', 'Erreur lors de l\'upload'), None
            
    except Exception as e:
        return False, f"Erreur: {str(e)}", None

def search_in_my_files(query: str, tag: Optional[str] = None):
    """Rechercher dans mes fichiers personnels"""
    endpoint = f"/my-files/search/?query={query}"
    if tag:
        endpoint += f"&tag={tag}"
    return make_request(endpoint)

def ask_rag_question(question: str):
    """Poser une question au RAG personnel"""
    return make_request("/my-files/rag/query", "POST", {"question": question})

def download_file(file_id: int):
    """Télécharger un fichier"""
    try:
        headers = get_headers()
        response = requests.get(
            f"{API_BASE_URL}/my-files/{file_id}/download",
            headers=headers,
            stream=True
        )
        
        if response.status_code == 200:
            return BytesIO(response.content), response.headers.get('content-disposition', ''), None
        else:
            return None, None, response.json().get('detail', 'Erreur de téléchargement')
            
    except Exception as e:
        return None, None, f"Erreur: {str(e)}"

# ==================== PAGES ====================
def show_login_page():
    """Page de connexion"""
    st.title("🔐 Connexion - SaaS Multi-Tenant")
    
    tab1, tab2, tab3 = st.tabs(["🔑 Email/Mot de passe", "🔐 Clé API", "🚀 Créer un compte"])
    
    with tab1:
        st.subheader("Connexion avec identifiants")
        
        with st.form("login_form"):
            # Use separate 'prefill' session keys to avoid modifying session_state keys
            # after the widgets with those keys have been instantiated.
            email = st.text_input("Email", key="login_email", 
                                value=st.session_state.get('login_email_prefill', ''))
            password = st.text_input("Mot de passe", type="password", key="login_password",
                                   value=st.session_state.get('login_password_prefill', ''))
            
            col1, col2 = st.columns([2, 1])
            with col1:
                login_btn = st.form_submit_button("Se connecter", type="primary", use_container_width=True)
            with col2:
                if st.form_submit_button("Effacer", use_container_width=True):
                    # Clear the prefill keys (widget values will reset on rerun)
                    st.session_state['login_email_prefill'] = ""
                    st.session_state['login_password_prefill'] = ""
                    st.rerun()
            
            if login_btn:
                if email and password:
                    with st.spinner("Connexion en cours..."):
                        success, message = login_with_credentials(email, password)
                        if success:
                            st.success(message)
                            st.session_state.current_page = "dashboard"
                            st.rerun()
                        else:
                            st.error(message)
                else:
                    st.warning("Veuillez remplir tous les champs")
        
        # Comptes de test pour les fichiers personnels
        st.markdown("---")
        st.subheader("📋 Comptes de test (fichiers personnels)")
        
        # Test accounts should match the users created by `backend/init_db.py`
        test_accounts = [
            {"label": "👑 Admin Client A", "email": "admin@client-a.com", "password": "password123"},
            {"label": "👤 Utilisateur Client A", "email": "user@client-a.com", "password": "password123"},
            {"label": "👑 Admin Client B", "email": "admin@client-b.com", "password": "password456"}
        ]
        
        cols = st.columns(2)
        for idx, account in enumerate(test_accounts):
            with cols[idx % 2]:
                if st.button(account["label"], use_container_width=True, key=f"test_acc_{idx}"):
                    # Set prefill values so the text_input widgets show them on rerun
                    st.session_state['login_email_prefill'] = account["email"]
                    st.session_state['login_password_prefill'] = account["password"]
                    st.success(f"Compte {account['email']} chargé!")
                    st.rerun()
    
    with tab2:
        st.subheader("Connexion avec clé API")
        
        with st.form("api_key_login_form"):
            api_key = st.text_input("Clé API", type="password", 
                                  value=st.session_state.get('api_key_prefilled', ''),
                                  help="Entrez votre clé API commençant par 'tema_'")
            
            if st.form_submit_button("Se connecter avec clé API"):
                if api_key:
                    with st.spinner("Connexion en cours..."):
                        success, message = login_with_api_key(api_key)
                        if success:
                            st.success(message)
                            st.session_state.current_page = "dashboard"
                            st.rerun()
                        else:
                            st.error(message)
                else:
                    st.warning("Veuillez entrer une clé API")
        
        st.markdown("---")
        st.subheader("🔑 Clés API de test")
        st.info("Ces clés sont des exemples, utilisez vos propres clés générées")
    
    with tab3:
        show_register_page()

def show_register_page():
    """Page d'inscription"""
    st.subheader("Créer un nouveau compte")
    
    with st.form("register_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input("Nom complet")
            company_name = st.text_input("Nom de l'entreprise")
        
        with col2:
            email = st.text_input("Email professionnel")
            password = st.text_input("Mot de passe", type="password")
            confirm_password = st.text_input("Confirmer le mot de passe", type="password")
        
        if st.form_submit_button("Créer mon compte", type="primary"):
            if not all([full_name, company_name, email, password, confirm_password]):
                st.warning("Veuillez remplir tous les champs")
            elif password != confirm_password:
                st.error("Les mots de passe ne correspondent pas")
            elif len(password) < 6:
                st.error("Le mot de passe doit contenir au moins 6 caractères")
            else:
                with st.spinner("Création du compte en cours..."):
                    success, message = register_user(email, password, full_name, company_name)
                    if success:
                        st.success(message)
                        st.session_state.current_page = "dashboard"
                        st.rerun()
                    else:
                        st.error(message)

def show_dashboard():
    """Tableau de bord principal"""
    st.title("🏠 Tableau de bord")
    
    user = st.session_state.auth['user']
    if user:
        # Header avec info utilisateur
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            st.success(f"👋 Bienvenue, **{user['full_name']}**")
            st.caption(f"📧 {user['email']}")
            if user.get('is_admin'):
                st.info("👑 Rôle: Administrateur")
            else:
                st.info("👤 Rôle: Utilisateur")
        
        with col2:
            # Stats de stockage
            stats = make_request("/my-files/stats")
            if stats:
                st.metric("📁 Mes fichiers", stats['file_count'])
                st.metric("💾 Espace utilisé", f"{stats['total_size_mb']} MB")
        
        with col3:
            if st.button("🚪 Déconnexion", key="logout_button"):
                logout()
                st.rerun()
        
        st.markdown("---")
        
        # Quick actions
        st.subheader("🚀 Actions rapides")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("📤 Upload", use_container_width=True, 
                        help="Uploader un fichier personnel", key="dashboard_upload_btn"):
                st.session_state.current_page = "upload_file"
                st.rerun()
        
        with col2:
            if st.button("📁 Mes fichiers", use_container_width=True,
                        help="Voir mes fichiers personnels", key="dashboard_myfiles_btn"):
                st.session_state.current_page = "my_files"
                st.rerun()
        
        with col3:
            if st.button("🤖 RAG Chat", use_container_width=True,
                        help="Chat avec mes fichiers", key="dashboard_rag_btn"):
                st.session_state.current_page = "rag_chat"
                st.rerun()
        
        with col4:
            if st.button("🔍 Rechercher", use_container_width=True, key="dashboard_search_btn"):
                st.session_state.current_page = "search_files"
                st.rerun()
        
        with col5:
            if st.button("⚙️ Profil", use_container_width=True, key="dashboard_profile_btn"):
                st.session_state.current_page = "profile"
                st.rerun()
        
        # Derniers fichiers personnels
        st.markdown("---")
        st.subheader("📋 Mes derniers fichiers")
        
        files = make_request("/my-files/?limit=3")
        
        if files and len(files) > 0:
            for file in files:
                with st.expander(f"📄 {file['title']}"):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"**Taille:** {file['file_size']} octets")
                        st.write(f"**Type:** {file['mime_type']}")
                        if file.get('tags'):
                            st.write(f"**Tags:** {file['tags']}")
                        st.write(f"**Créé le:** {file['created_at']}")
                    
                    with col2:
                        if st.button("📥 Télécharger", key=f"dl_{file['id']}", 
                                   use_container_width=True):
                            file_content = make_request(f"/my-files/{file['id']}")
                            if file_content:
                                st.download_button(
                                    label="Télécharger",
                                    data=file_content['content'],
                                    file_name=file['filename'],
                                    mime=file['mime_type'],
                                    key=f"download_{file['id']}"
                                )
                    
                    with col3:
                        if st.button("🗑️ Supprimer", key=f"del_{file['id']}", 
                                   use_container_width=True):
                            if make_request(f"/my-files/{file['id']}", "DELETE"):
                                st.success("Fichier supprimé!")
                                st.rerun()
        else:
            st.info("Aucun fichier personnel trouvé. Uploader votre premier fichier!")
        
        # Health check
        st.markdown("---")
        with st.expander("🩺 Vérification du système"):
            try:
                health = requests.get(f"{API_BASE_URL}/health").json()
                st.success(f"✅ API: {health['status']} (v{health['version']})")
                st.info(f"🕐 Dernière vérification: {health['timestamp']}")
            except:
                st.error("❌ API non disponible")

def show_my_files_page():
    """Page de gestion des fichiers personnels"""
    st.title("📁 Mes fichiers personnels")
    
    # Onglets
    tab1, tab2, tab3 = st.tabs(["📋 Liste", "📤 Upload", "📊 Statistiques"])
    
    with tab1:
        # Filtres
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            search_query = st.text_input("Rechercher par titre/tags", 
                                       key="file_search_query")
        
        with col2:
            tag_filter = st.text_input("Filtrer par tag", 
                                     placeholder="ex: travail,projet",
                                     key="file_tag_filter")
        
        with col3:
            if st.button("🔎 Rechercher", use_container_width=True, key="myfiles_tab_search_btn"):
                # La recherche se fait via la fonction search_in_my_files
                pass
        
        # Liste des fichiers
        if search_query or tag_filter:
            # Utiliser l'endpoint de recherche
            files = search_in_my_files(search_query, tag_filter)
        else:
            # Utiliser l'endpoint de liste normale
            files = make_request("/my-files/")
        
        if files and len(files) > 0:
            st.success(f"📊 {len(files)} fichier(s) trouvé(s)")
            
            for file in files:
                with st.expander(f"📄 {file['title']} ({file['file_size']} octets)", 
                               expanded=False):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        # Afficher les métadonnées
                        st.write(f"**Nom:** {file.get('filename', 'N/A')}")
                        if 'original_filename' in file:
                            st.write(f"**Nom original:** {file['original_filename']}")
                        st.write(f"**Type:** {file['mime_type']}")
                        if file.get('tags'):
                            st.write(f"**Tags:** {file['tags']}")
                        st.write(f"**Public:** {'Oui' if file.get('is_public') else 'Non'}")
                        st.write(f"**Créé le:** {file['created_at']}")
                    
                    with col2:
                        # Bouton pour voir le contenu
                        if st.button("👁️ Voir", key=f"view_{file['id']}", 
                                   use_container_width=True):
                            st.session_state.view_file_id = file['id']
                            st.session_state.current_page = "view_file"
                            st.rerun()
                    
                    with col3:
                        # Bouton de suppression
                        if st.button("🗑️ Supprimer", key=f"delete_{file['id']}", 
                                   use_container_width=True):
                            if make_request(f"/my-files/{file['id']}", "DELETE"):
                                st.success("Fichier supprimé!")
                                st.rerun()
        else:
            st.info("📭 Aucun fichier trouvé. Uploader votre premier fichier!")
    
    with tab2:
        show_upload_file_page(minimal=True)
    
    with tab3:
        # Statistiques
        stats = make_request("/my-files/stats")
        
        if stats:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📁 Fichiers", stats['file_count'])
            
            with col2:
                st.metric("💾 Espace total", f"{stats['total_size_bytes']:,} octets")
            
            with col3:
                st.metric("📊 Taille moyenne", 
                         f"{stats['total_size_bytes'] // max(1, stats['file_count']):,} octets")
            
            # Détails
            with st.expander("📋 Détails du stockage"):
                st.json(stats)
        
        # Bouton retour
        st.markdown("---")
        if st.button("🏠 Retour au dashboard", use_container_width=True, key="myfiles_back_dashboard_btn"):
            st.session_state.current_page = "dashboard"
            st.rerun()

def show_upload_file_page(minimal=False):
    """Page d'upload de fichiers"""
    if not minimal:
        st.title("📤 Uploader un fichier personnel")
    
    with st.form("upload_file_form"):
        # Informations sur le fichier
        col1, col2 = st.columns(2)
        
        with col1:
            title = st.text_input("Titre du fichier*", 
                                help="Donnez un titre descriptif à votre fichier")
            tags = st.text_input("Tags (optionnel)", 
                               placeholder="travail,projet,perso",
                               help="Tags séparés par des virgules")
        
        with col2:
            is_public = st.checkbox("Fichier public", 
                                  help="Visible par les autres utilisateurs de votre client")
            file = st.file_uploader("Choisir un fichier*", 
                                  type=['txt', 'pdf', 'doc', 'docx', 'md'],
                                  help="Formats acceptés: .txt, .pdf, .doc, .docx, .md")
        
        if minimal:
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("📤 Uploader", type="primary", use_container_width=True)
            with col2:
                cancel = st.form_submit_button("❌ Annuler", use_container_width=True)
        else:
            submit = st.form_submit_button("📤 Uploader le fichier", type="primary", use_container_width=True)
        
        if submit:
            if not file:
                st.error("⚠️ Veuillez sélectionner un fichier")
            elif not title:
                st.error("⚠️ Veuillez donner un titre à votre fichier")
            else:
                with st.spinner("Upload en cours..."):
                    success, message, file_data = upload_personal_file(file, title, tags, is_public)
                    if success:
                        st.success(f"✅ {message}")
                        if not minimal:
                            st.balloons()
                            st.session_state.current_page = "my_files"
                            st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        if minimal and cancel:
            st.session_state.current_page = "my_files"
            st.rerun()
    
    if not minimal:
        st.markdown("---")
        if st.button("🔙 Retour à mes fichiers", use_container_width=True, key="upload_back_to_myfiles_btn"):
            st.session_state.current_page = "my_files"
            st.rerun()

def show_view_file_page():
    """Voir un fichier en détail (version corrigée)"""
    if 'view_file_id' not in st.session_state:
        st.session_state.current_page = "my_files"
        st.rerun()
        return

    file_id = st.session_state.view_file_id

    # Nous avons besoin de DEUX appels API :
    # 1. Pour les métadonnées (contient file_size)
    file_metadata = make_request(f"/my-files/{file_id}")

    # 2. Récupérer le contenu retourné par l'API (si présent)
    # Certains environnements MIME peuvent ne pas être exacts, donc on s'appuie
    # d'abord sur le champ `content` renvoyé par l'endpoint qui contient
    # le texte pour les fichiers .txt.
    file_content = None
    file_bytes = None
    if file_metadata:
        file_content = file_metadata.get('content')

    # Si l'API n'a pas retourné de contenu (fichier binaire ou absence),
    # tenter de télécharger le binaire pour prévisualisation/téléchargement.
    if not file_content:
        file_bytes, _, _ = download_file(file_id)

    if not file_metadata:
        st.error("Fichier non trouvé")
        if st.button("🔙 Retour", key="view_notfound_back_btn"):
            st.session_state.current_page = "my_files"
            st.rerun()
        return

    st.title(f"📄 {file_metadata['title']}")

    # Boutons d'action
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        if st.button("🔙 Retour à la liste", use_container_width=True, key=f"view_back_{file_id}"):
            st.session_state.current_page = "my_files"
            st.rerun()

    with col2:
        # Bouton de téléchargement
        # Re-use file_bytes if already downloaded
        if not file_bytes:
            file_bytes, _, _ = download_file(file_id)
        if file_bytes:
            st.download_button(
                label="📥 Télécharger",
                data=file_bytes,
                file_name=file_metadata.get('filename', f"file_{file_id}"),
                mime=file_metadata.get('mime_type', 'text/plain'),
                use_container_width=True,
                key=f"download_{file_id}"
            )

    with col3:
        if st.button("✏️ Modifier", use_container_width=True, key=f"edit_{file_id}"):
            st.session_state.edit_file_id = file_id
            st.session_state.current_page = "edit_file"
            st.rerun()

    with col4:
        if st.button("🗑️ Supprimer", use_container_width=True, key=f"delete_{file_id}"):
            if make_request(f"/my-files/{file_id}", "DELETE"):
                st.success("Fichier supprimé!")
                st.session_state.current_page = "my_files"
                st.rerun()

    st.markdown("---")

    # Contenu du fichier
    st.subheader("📝 Contenu")

    # Afficher différemment selon le type de fichier
    if file_content:
        # Fichier texte
        st.text_area("", file_content, height=400, disabled=True, key=f"content_{file_id}")
    else:
        # Fichier binaire ou pas de contenu
        # Pour obtenir la taille, nous devons faire un appel supplémentaire à l'endpoint de liste
        files_list = make_request("/my-files/")
        file_size = "N/A"
        
        if files_list:
            for file in files_list:
                if file['id'] == file_id:
                    file_size = file.get('file_size', 'N/A')
                    break
        
        if file_bytes:
            st.info(f"Fichier binaire de {file_size} octets")
            st.download_button(
                label="📥 Télécharger le fichier",
                data=file_bytes,
                file_name=file_metadata.get('filename', f"file_{file_id}"),
                mime=file_metadata.get('mime_type', 'application/octet-stream'),
                use_container_width=True,
                key=f"download_bin_{file_id}"
            )
        else:
            st.info(f"Fichier de {file_size} octets - Contenu non disponible en prévisualisation")

    # Métadonnées - CORRIGÉ : Utiliser file_metadata au lieu de file_data
    st.markdown("---")
    with st.expander("📋 Métadonnées"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**ID:**", file_metadata['id'])
            st.write("**Nom du fichier:**", file_metadata.get('filename', 'N/A'))
            
            # Obtenir la taille depuis la liste des fichiers
            file_size_display = "N/A"
            files_list = make_request("/my-files/")
            if files_list:
                for file in files_list:
                    if file['id'] == file_id:
                        file_size_display = f"{file.get('file_size', 'N/A'):,} octets"
                        break
            
            st.write("**Taille:**", file_size_display)
            st.write("**Type MIME:**", file_metadata.get('mime_type', 'N/A'))
        
        with col2:
            st.write("**Utilisateur ID:**", file_metadata['user_id'])
            st.write("**Tags:**", file_metadata.get('tags', 'Aucun'))
            st.write("**Public:**", "Oui" if file_metadata.get('is_public') else "Non")
            st.write("**Créé le:**", file_metadata['created_at'])

def show_edit_file_page():
    """Modifier les métadonnées d'un fichier"""
    if 'edit_file_id' not in st.session_state:
        st.session_state.current_page = "my_files"
        st.rerun()
        return
    
    file_id = st.session_state.edit_file_id
    file_data = make_request(f"/my-files/{file_id}")
    
    if not file_data:
        st.error("Fichier non trouvé")
        if st.button("🔙 Retour", key="edit_notfound_back_btn"):
            st.session_state.current_page = "my_files"
            st.rerun()
        return
    
    st.title(f"✏️ Modifier: {file_data['title']}")
    
    with st.form("edit_file_form"):
        title = st.text_input("Titre", value=file_data['title'])
        tags = st.text_input("Tags", value=file_data.get('tags', ''))
        is_public = st.checkbox("Fichier public", value=file_data.get('is_public', False))
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            save = st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("❌ Annuler", use_container_width=True)
        with col3:
            delete = st.form_submit_button("🗑️ Supprimer", use_container_width=True)
        
        if save:
            update_data = {}
            if title != file_data['title']:
                update_data['title'] = title
            if tags != file_data.get('tags', ''):
                update_data['tags'] = tags
            if is_public != file_data.get('is_public', False):
                update_data['is_public'] = is_public
            
            if update_data:
                result = make_request(f"/my-files/{file_id}", "PUT", update_data)
                if result:
                    st.success("✅ Fichier mis à jour!")
                    st.session_state.current_page = "my_files"
                    st.rerun()
            else:
                st.info("Aucune modification détectée")
        
        if cancel:
            st.session_state.current_page = "my_files"
            st.rerun()
        
        if delete:
            if make_request(f"/my-files/{file_id}", "DELETE"):
                st.success("✅ Fichier supprimé!")
                st.session_state.current_page = "my_files"
                st.rerun()

def show_search_files_page():
    """Page de recherche dans les fichiers"""
    st.title("🔍 Recherche dans mes fichiers")
    
    # Barre de recherche principale
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        search_query = st.text_input("Rechercher dans le contenu de mes fichiers",
                                   placeholder="Ex: projet, budget, réunion...",
                                   key="main_file_search")
    
    with col2:
        tag_filter = st.text_input("Tag", 
                                 placeholder="optionnel",
                                 key="file_search_tag")
    
    with col3:
        if st.button("🔎 Rechercher", type="primary", use_container_width=True, key="search_files_main_btn"):
            if search_query:
                st.session_state.file_search_results = search_in_my_files(search_query, tag_filter)
            else:
                st.warning("Veuillez entrer un terme de recherche")
    
    # Résultats de recherche
    if hasattr(st.session_state, 'file_search_results'):
        results = st.session_state.file_search_results
        
        if results and len(results) > 0:
            st.success(f"✅ {len(results)} fichier(s) trouvé(s) pour: '{search_query}'")
            
            for i, file in enumerate(results):
                with st.expander(f"📄 {file['title']} (Score: {i+1})", expanded=(i==0)):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        # Afficher l'extrait avec surlignage
                        if file['content']:
                            content = file['content']
                            # Recherche simple du terme
                            if search_query.lower() in content.lower():
                                # Trouver la première occurrence
                                idx = content.lower().find(search_query.lower())
                                start = max(0, idx - 100)
                                end = min(len(content), idx + len(search_query) + 100)
                                excerpt = f"...{content[start:end]}..."
                                st.write(excerpt)
                            else:
                                st.write(content[:200] + "..." if len(content) > 200 else content)
                        
                        # Métadonnées
                        st.caption(f"📏 {file.get('file_size', 0)} octets")
                        if file.get('tags'):
                            st.caption(f"🏷️ {file['tags']}")
                        st.caption(f"📅 {file['created_at']}")
                    
                    with col2:
                        if st.button("👁️ Voir", key=f"view_res_{file['id']}", 
                                   use_container_width=True):
                            st.session_state.view_file_id = file['id']
                            st.session_state.current_page = "view_file"
                            st.rerun()
        else:
            st.warning(f"❌ Aucun fichier trouvé pour: '{search_query}'")
            st.info("""
            **Conseils de recherche:**
            - Essayez d'autres mots-clés
            - Utilisez des tags spécifiques
            - Vérifiez l'orthographe
            """)
    
    # Recherches suggérées
    st.markdown("---")
    st.subheader("🔤 Recherches suggérées")
    
    suggestions = ["projet", "rapport", "budget", "réunion", "contact", "email"]
    
    cols = st.columns(3)
    for idx, suggestion in enumerate(suggestions):
        with cols[idx % 3]:
            if st.button(suggestion, use_container_width=True, key=f"suggest_file_{idx}"):
                st.session_state.main_file_search = suggestion
                st.rerun()
    
    # Bouton retour
    st.markdown("---")
    if st.button("🏠 Retour au dashboard", use_container_width=True, key="searchfiles_back_dashboard_btn"):
        st.session_state.current_page = "dashboard"
        st.rerun()

def show_rag_chat_page():
    """Page de chat RAG avec les fichiers personnels"""
    st.title("🤖 Chat avec mes fichiers")
    
    # Initialiser l'historique de chat
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Instructions
    with st.expander("ℹ️ Comment ça marche"):
        st.markdown("""
        **Le chatbot RAG personnel:**
        - 🔍 **Recherche** uniquement dans **VOS** fichiers personnels
        - 📄 **Ne connaît pas** les fichiers des autres utilisateurs
        - ❌ **N'invente pas** d'informations
        - 💬 **Répond** uniquement à partir de vos documents
        
        **Exemples de questions:**
        - "Quels sont mes objectifs pour ce trimestre ?"
        - "Qui est mon contact principal ?"
        - "Quel est le budget de mon projet ?"
        - "Quelles sont les procédures que je dois suivre ?"
        """)
    
    # Afficher l'historique de chat
    st.markdown("---")
    st.subheader("💬 Conversation")
    
    for message in st.session_state.chat_history:
        if message['role'] == 'user':
            with st.chat_message("user"):
                st.write(f"**Vous:** {message['content']}")
        else:
            with st.chat_message("assistant"):
                st.write(f"**Assistant:** {message['content']}")
                
                # Afficher les sources si disponibles
                if 'sources' in message and message['sources']:
                    with st.expander("📄 Sources utilisées"):
                        for source in message['sources']:
                            st.write(f"- **{source['title']}** (pertinence: {source['relevance']:.2f})")
    
    # Input utilisateur
    st.markdown("---")
    question = st.chat_input("Posez une question sur vos fichiers...")
    
    if question:
        # Ajouter la question à l'historique
        st.session_state.chat_history.append({
            'role': 'user',
            'content': question,
            'timestamp': datetime.now().isoformat()
        })
        
        # Afficher la question
        with st.chat_message("user"):
            st.write(f"**Vous:** {question}")
        
        # Obtenir la réponse du RAG
        with st.spinner("🔍 Recherche dans vos fichiers..."):
            response = ask_rag_question(question)
        
        if response:
            # Ajouter la réponse à l'historique
            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': response['answer'],
                'sources': response.get('source_files', []),
                'timestamp': datetime.now().isoformat()
            })
            
            # Afficher la réponse
            with st.chat_message("assistant"):
                st.write(f"**Assistant:** {response['answer']}")
                
                # Afficher les sources
                if response.get('source_files'):
                    with st.expander("📄 Sources utilisées"):
                        for source in response['source_files']:
                            st.write(f"- **{source['title']}** (pertinence: {source['relevance']:.2f})")
        else:
            st.error("❌ Erreur lors de la recherche")
    
    # Exemples de questions
    st.markdown("---")
    st.subheader("💡 Exemples de questions")
    
    example_questions = [
        "Quels sont mes projets en cours ?",
        "Qui sont mes contacts importants ?",
        "Quel est mon budget disponible ?",
        "Quelles sont mes tâches mensuelles ?",
        "Quand sont mes prochaines deadlines ?"
    ]
    
    cols = st.columns(3)
    for idx, example in enumerate(example_questions):
        with cols[idx % 3]:
            if st.button(example, use_container_width=True, key=f"example_{idx}"):
                # Simuler un chat input
                st.session_state.chat_input = example
                st.rerun()
    
    # Actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🗑️ Effacer l'historique", use_container_width=True, key="rag_clear_history_btn"):
            st.session_state.chat_history = []
            st.rerun()
    
    with col2:
        if st.button("📁 Voir mes fichiers", use_container_width=True, key="rag_view_files_btn"):
            st.session_state.current_page = "my_files"
            st.rerun()
    
    with col3:
        if st.button("🏠 Dashboard", use_container_width=True, key="rag_dashboard_btn"):
            st.session_state.current_page = "dashboard"
            st.rerun()

def show_profile_page():
    """Page de profil"""
    st.title("👤 Mon profil")
    
    user = st.session_state.auth['user']
    if not user:
        st.error("Utilisateur non connecté")
        return
    
    # Informations du profil
    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            email = st.text_input("Email", value=user['email'])
            full_name = st.text_input("Nom complet", value=user['full_name'])
        
        with col2:
            st.text_input("Rôle", value="Administrateur" if user['is_admin'] else "Utilisateur", disabled=True)
            st.text_input("Client ID", value=str(user['client_id']), disabled=True)
            if user['last_login']:
                st.text_input("Dernière connexion", value=user['last_login'], disabled=True)
        
        col1, col2 = st.columns(2)
        with col1:
            save = st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("❌ Annuler", use_container_width=True)
        
        if save:
            if email and full_name:
                result = make_request("/profile", "PUT", {"email": email, "full_name": full_name})
                if result:
                    st.success("✅ Profil mis à jour!")
                    st.session_state.auth['user'] = result
                    st.rerun()
            else:
                st.error("⚠️ Veuillez remplir tous les champs")
        
        if cancel:
            st.rerun()
    
    # Statistiques de fichiers
    st.markdown("---")
    st.subheader("📊 Mes statistiques")
    
    stats = make_request("/my-files/stats")
    if stats:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📁 Fichiers", stats['file_count'])
        
        with col2:
            st.metric("💾 Espace", f"{stats['total_size_mb']} MB")
        
        with col3:
            avg_size = stats['total_size_bytes'] // max(1, stats['file_count'])
            st.metric("📏 Taille moyenne", f"{avg_size:,} octets")
        
        with st.expander("📋 Détails"):
            st.json(stats)
    
    # Actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🏠 Dashboard", use_container_width=True):
            st.session_state.current_page = "dashboard"
            st.rerun()
    
    with col2:
        if st.button("📁 Mes fichiers", use_container_width=True):
            st.session_state.current_page = "my_files"
            st.rerun()
    
    with col3:
        if st.button("🚪 Déconnexion", use_container_width=True):
            logout()
            st.rerun()

# ==================== SIDEBAR ====================
def show_sidebar():
    """Afficher la sidebar"""
    with st.sidebar:
        st.title("📁 SaaS Multi-Tenant")
        
        if st.session_state.auth['is_authenticated']:
            user = st.session_state.auth['user']
            
            # Info utilisateur
            st.success(f"👤 {user['full_name']}")
            st.caption(f"📧 {user['email']}")
            
            if user.get('is_admin'):
                st.info("👑 Administrateur")
            
            # Stats rapides
            stats = make_request("/my-files/stats")
            if stats:
                st.caption(f"📁 {stats['file_count']} fichiers | 💾 {stats['total_size_mb']} MB")
            
            st.markdown("---")
            
            # Navigation principale
            st.subheader("📍 Navigation")
            
            pages = {
                "🏠 Dashboard": "dashboard",
                "📤 Upload": "upload_file",
                "📁 Mes fichiers": "my_files",
                "🤖 RAG Chat": "rag_chat",
                "🔍 Rechercher": "search_files",
                "👤 Profil": "profile"
            }
            
            for page_name, page_id in pages.items():
                if st.button(page_name, 
                           use_container_width=True,
                           type="primary" if st.session_state.current_page == page_id else "secondary"):
                    st.session_state.current_page = page_id
                    st.rerun()
            
            # Déconnexion
            st.markdown("---")
            if st.button("🚪 Déconnexion", use_container_width=True):
                logout()
                st.rerun()
        
        else:
            # Logo/description pour les non connectés
            st.markdown("""
            ### 📁 SaaS Multi-Tenant
            **Système de fichiers personnels avec RAG**
            
            ---
            
            **Comptes de test:**
            - 👑 Admin Entreprise A
              `admin@entreprise-a.com`
              `password123`
            
            - 👤 Jean Dupont
              `jean@entreprise-a.com`
              `password123`
            
            - 👑 Admin Société B
              `admin@societe-b.com`
              `password456`
            
            - 👤 Marie Martin
              `marie@societe-b.com`
              `password456`
            
            ---
            
            **Fonctionnalités:**
            - 📁 **Fichiers personnels** par utilisateur
            - 🤖 **RAG personnel** (recherche dans vos fichiers)
            - 🔍 **Recherche avancée**
            - 🏷️ **Tags et catégories**
            - 👥 **Partage contrôlé**
            """)

# ==================== MAIN APP ====================
def main():
    # Configuration de la page
    st.set_page_config(
        page_title="SaaS Multi-Tenant - Fichiers Personnels",
        page_icon="📁",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Afficher la sidebar
    show_sidebar()
    
    # Gestion de la navigation
    if not st.session_state.auth['is_authenticated'] and st.session_state.current_page != "login":
        st.session_state.current_page = "login"
    
    # Router vers la bonne page
    page_handlers = {
        "login": show_login_page,
        "dashboard": show_dashboard,
        "upload_file": show_upload_file_page,
        "my_files": show_my_files_page,
        "view_file": show_view_file_page,
        "edit_file": show_edit_file_page,
        "search_files": show_search_files_page,
        "rag_chat": show_rag_chat_page,
        "profile": show_profile_page
    }
    
    handler = page_handlers.get(st.session_state.current_page, show_login_page)
    handler()
    
    # Footer
    st.markdown("---")
    st.caption("📁 SaaS Multi-Tenant - Fichiers personnels avec RAG - Chaque utilisateur a son propre espace de stockage")

if __name__ == "__main__":
    main()