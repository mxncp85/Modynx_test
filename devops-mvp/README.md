# DevOps-as-a-Service MVP

Une application qui analyse automatiquement votre code et configure les pipelines CI/CD appropriés.

## Fonctionnalités

- Analyse automatique du code source
- Détection du langage et du framework
- Génération de configuration CI/CD pour GitHub Actions
- Interface web simple et intuitive

## Prérequis

- Python 3.9+
- Docker (optionnel)

## Installation

### Installation locale

1. Clonez le repository :
```bash
git clone <votre-repo>
cd devops-mvp
```

2. Installez les dépendances :
```bash
pip install -r requirements.txt
```

3. Lancez l'application :
```bash
uvicorn main:app --reload
```

### Installation avec Docker

1. Construisez l'image Docker :
```bash
docker build -t devops-mvp .
```

2. Lancez le conteneur :
```bash
docker run -p 8000:8000 devops-mvp
```

## Utilisation

1. Ouvrez votre navigateur et accédez à `http://localhost:8000`
2. Entrez l'URL de votre repository Git
3. Cliquez sur "Analyser le Repository"
4. Consultez les résultats de l'analyse et la configuration CI/CD suggérée

## Structure du projet

```
devops-mvp/
├── main.py              # Application FastAPI
├── requirements.txt     # Dépendances Python
├── Dockerfile          # Configuration Docker
├── templates/          # Templates HTML
│   └── index.html      # Page d'accueil
└── static/            # Fichiers statiques
```

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## Licence

MIT 