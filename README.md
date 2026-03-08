# SwissLivraisonPro Fleet Hub

Hub de dispatch multi-restaurant pour connecter :

- Just Eat
- Shipday
- autres plateformes futures

## Local

Créer environnement :

python -m venv .venv
.venv\Scripts\activate

Installer dépendances :

pip install -r requirements.txt

Lancer API :

uvicorn app.main:app --reload

API locale :

http://127.0.0.1:8000