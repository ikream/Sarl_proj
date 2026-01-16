import streamlit as st
import requests
from typing import Optional, Dict, Any

class AuthManager:
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        
        # Initialiser l'état de session
        if 'auth' not in st.session_state:
            st.session_state.auth = {
                'is_authenticated': False,
                'access_token': None,
                'user': None,
                'client': None
            }
    
    def get_headers(self) -> Dict[str, str]:
        """Récupérer les headers d'authentification"""
        headers = {"Content-Type": "application/json"}
        if st.session_state.auth['access_token']:
            headers["Authorization"] = f"Bearer {st.session_state.auth['access_token']}"
        return headers
    
    def register(self, email: str, password: str, full_name: str, company_name: str) -> bool:
        """Créer un nouveau compte"""
        try:
            response = requests.post(
                f"{self.api_base_url}/auth/register",
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
                return True
            else:
                st.error(f"Erreur d'inscription: {response.json().get('detail', 'Erreur inconnue')}")
                return False
                
        except Exception as e:
            st.error(f"Erreur de connexion: {str(e)}")
            return False
    
    def login(self, email: str, password: str) -> bool:
        """Se connecter"""
        try:
            response = requests.post(
                f"{self.api_base_url}/auth/login",
                json={"email": email, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                st.session_state.auth.update({
                    'is_authenticated': True,
                    'access_token': data['access_token'],
                    'user': data['user']
                })
                return True
            else:
                st.error(f"Erreur de connexion: {response.json().get('detail', 'Email ou mot de passe incorrect')}")
                return False
                
        except Exception as e:
            st.error(f"Erreur de connexion: {str(e)}")
            return False
    
    def logout(self):
        """Se déconnecter"""
        st.session_state.auth = {
            'is_authenticated': False,
            'access_token': None,
            'user': None,
            'client': None
        }
    
    def refresh_token(self) -> bool:
        """Rafraîchir le token"""
        if not st.session_state.auth['access_token']:
            return False
        
        try:
            headers = self.get_headers()
            response = requests.post(
                f"{self.api_base_url}/auth/refresh",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                st.session_state.auth['access_token'] = data['access_token']
                return True
        except:
            pass
        
        return False
    
    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Récupérer le profil utilisateur"""
        try:
            headers = self.get_headers()
            response = requests.get(
                f"{self.api_base_url}/profile",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
        except:
            pass
        
        return None
    
    def is_authenticated(self) -> bool:
        """Vérifier si l'utilisateur est authentifié"""
        if not st.session_state.auth['is_authenticated']:
            return False
        
        # Optionnel: vérifier la validité du token
        # Ici on pourrait ajouter une vérification JWT
        
        return True
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Récupérer l'utilisateur courant"""
        return st.session_state.auth.get('user')
    
    def make_authenticated_request(self, endpoint: str, method: str = "GET", data: Optional[dict] = None):
        """Faire une requête authentifiée"""
        headers = self.get_headers()
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            
            # Si token expiré, essayer de le rafraîchir
            if response.status_code == 401 and self.refresh_token():
                # Réessayer avec le nouveau token
                headers = self.get_headers()
                if method == "GET":
                    response = requests.get(url, headers=headers)
                elif method == "POST":
                    response = requests.post(url, headers=headers, json=data)
                elif method == "PUT":
                    response = requests.put(url, headers=headers, json=data)
                elif method == "DELETE":
                    response = requests.delete(url, headers=headers)
            
            response.raise_for_status()
            return response.json() if response.content else None
            
        except requests.exceptions.RequestException as e:
            try:
                status_code = response.status_code
            except Exception:
                status_code = None
            if status_code == 401:
                st.error("Session expirée. Veuillez vous reconnecter.")
                self.logout()
                st.rerun()
            else:
                st.error(f"Erreur API: {str(e)}")
            return None
