import pytest
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test du endpoint de santé"""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_invalid_api_key():
    """Test avec une clé API invalide"""
    headers = {"X-APP-KEY": "invalid_key"}
    response = requests.get(f"{BASE_URL}/documents/", headers=headers)
    assert response.status_code == 401

def test_client_a_access():
    """Test l'accès du Client A à ses documents"""
    headers = {"X-APP-KEY": "temaTA_key"}
    
    # Récupérer les documents
    response = requests.get(f"{BASE_URL}/documents/", headers=headers)
    assert response.status_code == 200
    
    documents = response.json()
    print(f"Client A a {len(documents)} documents")
    
    # Vérifier que tous les documents appartiennent au Client A
    for doc in documents:
        assert "Client A" in doc["title"] or "strategie" in doc["content"].lower()

def test_client_b_access():
    """Test l'accès du Client B à ses documents"""
    headers = {"X-APP-KEY": "temaTB_key"}
    
    # Récupérer les documents
    response = requests.get(f"{BASE_URL}/documents/", headers=headers)
    assert response.status_code == 200
    
    documents = response.json()
    print(f"Client B a {len(documents)} documents")
    
    # Vérifier que tous les documents appartiennent au Client B
    for doc in documents:
        assert "Client B" in doc["title"] or "marche" in doc["content"].lower()

def test_create_document():
    """Test la création d'un document"""
    headers = {"X-APP-KEY": "temaTA_key", "Content-Type": "application/json"}
    
    new_doc = {
        "title": "Test document Client A",
        "content": "Ceci est un document de test créé via l'API"
    }
    
    response = requests.post(f"{BASE_URL}/documents/", 
                           headers=headers, 
                           data=json.dumps(new_doc))
    
    assert response.status_code == 200
    created_doc = response.json()
    assert created_doc["title"] == new_doc["title"]
    assert created_doc["content"] == new_doc["content"]
    
    # Nettoyer - supprimer le document de test
    doc_id = created_doc["id"]
    response = requests.delete(f"{BASE_URL}/documents/{doc_id}", headers=headers)
    assert response.status_code == 200

def test_search_documents():
    """Test la recherche de documents"""
    headers = {"X-APP-KEY": "temaTA_key"}
    
    response = requests.get(f"{BASE_URL}/search/?query=stratégie", headers=headers)
    assert response.status_code == 200
    
    results = response.json()
    assert len(results) > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
