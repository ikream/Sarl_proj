import requests
import sys


def test_document_separation():
    # Login Client A
    resp = requests.post("http://127.0.0.1:8000/auth/login",
                         json={"email": "admin@client-a.com", "password": "password123"})
    resp.raise_for_status()
    token_a = resp.json()["access_token"]

    # Login Client B
    resp = requests.post("http://127.0.0.1:8000/auth/login",
                         json={"email": "admin@client-b.com", "password": "password456"})
    resp.raise_for_status()
    token_b = resp.json()["access_token"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Test 1: Client A documents
    resp = requests.get("http://127.0.0.1:8000/documents/", headers=headers_a)
    resp.raise_for_status()
    docs_a = resp.json()
    titles_a = [d["title"] for d in docs_a]
    print("Client A documents:", titles_a)
    assert "Procédure résiliation" in titles_a
    assert "Produit RC Pro A" in titles_a

    # Test 1b: Client B documents
    resp = requests.get("http://127.0.0.1:8000/documents/", headers=headers_b)
    resp.raise_for_status()
    docs_b = resp.json()
    titles_b = [d["title"] for d in docs_b]
    print("Client B documents:", titles_b)
    assert "Procédure sinistre" in titles_b
    assert "Produit RC Pro B" in titles_b

    # Test 2: Search specific (résiliation)
    resp = requests.get("http://127.0.0.1:8000/search/?query=résiliation", headers=headers_a)
    resp.raise_for_status()
    results = resp.json()
    print("Search 'résiliation' for A ->", [d['title'] for d in results])
    assert any(d["title"] == "Procédure résiliation" for d in results), f"Expected 'Procédure résiliation' in {results}"

    resp = requests.get("http://127.0.0.1:8000/search/?query=résiliation", headers=headers_b)
    resp.raise_for_status()
    results_b = resp.json()
    print("Search 'résiliation' for B ->", [d['title'] for d in results_b])
    assert results_b == [], f"Expected no results for client B but got {results_b}"

    # Test 3: Client A search for 'hebdomadaire' (term that exists only for Client B)
    resp = requests.get("http://127.0.0.1:8000/search/?query=hebdomadaire", headers=headers_a)
    resp.raise_for_status()
    print("Search 'hebdomadaire' for A ->", resp.json())
    assert resp.json() == [], f"Expected empty list for 'hebdomadaire' on client A but got {resp.json()}"

    # Test 4: cross-keyword 'assureur' should return only A's document content when searched by A
    resp = requests.get("http://127.0.0.1:8000/search/?query=assureur", headers=headers_a)
    resp.raise_for_status()
    results = resp.json()
    assert any("sinistres@assureur-a.fr" in d["content"] for d in results)
    assert not any("claims@assureur-b.com" in d["content"] for d in results)

    print("✅ Tous les tests de séparation avec documents réels passent!")


if __name__ == "__main__":
    try:
        test_document_separation()
    except AssertionError as e:
        print("❌ Assertion failed:", e)
        sys.exit(1)
    except Exception as e:
        print("❌ Error during tests:", e)
        sys.exit(2)
    print("All checks OK")
