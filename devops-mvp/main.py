import os
import shutil
import tempfile
import subprocess
from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import git
import yaml
import json
from pathlib import Path
from fastapi.templating import Jinja2Templates

app = FastAPI(title="DevOps-as-a-Service MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration des templates et fichiers statiques
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

class RepoRequest(BaseModel):
    repo_url: str

@app.post("/setup-ci")
async def setup_ci(req: RepoRequest):
    tmp_dir = tempfile.mkdtemp()
    try:
        repo = git.Repo.clone_from(req.repo_url, tmp_dir)
        if os.path.exists(os.path.join(tmp_dir, "main.py")) or os.path.exists(os.path.join(tmp_dir, "app.py")):
            stack = "python"
        else:
            raise HTTPException(status_code=400, detail="Stack non détectée")

        workflow_dir = os.path.join(tmp_dir, ".github", "workflows")
        os.makedirs(workflow_dir, exist_ok=True)
        workflow_file = os.path.join(workflow_dir, "ci.yml")

        with open(workflow_file, "w") as f:
            f.write(generate_github_action(stack))

        repo.git.add(A=True)
        repo.git.commit(m="feat: add auto-generated CI workflow")
        repo.git.push()

        return {"message": "Workflow CI/CD généré et poussé avec succès."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir)

def generate_github_action(stack):
    if stack == "python":
        return """name: CI

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Run tests
      run: |
        pytest || echo 'No tests found'
    - name: Build Docker image
      run: |
        docker build -t myapp:latest .
        docker images
"""
    return ""

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze-repo")
async def analyze_repository(repo_url: str = Form(...)):
    try:
        # Cloner le repository
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        local_path = f"temp/{repo_name}"
        os.makedirs("temp", exist_ok=True)
        
        print(f"Clonage du repository {repo_url} vers {local_path}")
        
        # Cloner avec fetch_depth=0 pour récupérer tout l'historique
        repo = git.Repo.clone_from(repo_url, local_path, depth=None)
        
        # Vérifier si le clonage a réussi
        if not os.path.exists(local_path):
            return {"status": "error", "message": "Échec du clonage du repository"}
        
        # Récupérer la branche principale
        try:
            repo.git.checkout('main')
        except:
            try:
                repo.git.checkout('master')
            except:
                print("Impossible de changer de branche")
        
        print(f"Contenu du dossier {local_path}:")
        for root, dirs, files in os.walk(local_path):
            # Ignorer le dossier .git
            if '.git' in root:
                continue
                
            print(f"\nDossier: {root}")
            if files:
                print("Fichiers:", files)
                # Afficher les extensions des fichiers
                extensions = set(os.path.splitext(f)[1] for f in files)
                if extensions:
                    print("Extensions trouvées:", extensions)
        
        # Analyser la structure du projet
        analysis = {
            "language": detect_language(local_path),
            "framework": detect_framework(local_path),
            "dependencies": detect_dependencies(local_path),
            "suggested_pipeline": generate_pipeline_config(local_path)
        }
        
        print(f"Analyse terminée: {analysis}")
        
        # Nettoyage
        shutil.rmtree(local_path)
        
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        print(f"Erreur lors de l'analyse: {str(e)}")
        return {"status": "error", "message": str(e)}

def detect_language(path):
    print(f"\nDétection du langage dans {path}")
    
    # Dictionnaire des extensions par langage
    language_extensions = {
        'Python': ['.py', '.pyc', '.pyo', '.pyd', '.pyw', '.pyi'],
        'JavaScript/TypeScript': ['.js', '.jsx', '.ts', '.tsx'],
        'Java': ['.java', '.class', '.jar'],
        'Go': ['.go'],
        'Ruby': ['.rb', '.rbw'],
        'PHP': ['.php', '.phtml', '.php3', '.php4', '.php5', '.php7'],
        'Rust': ['.rs'],
        'C/C++': ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp'],
        'C#': ['.cs'],
        'HTML/CSS': ['.html', '.htm', '.css', '.scss', '.sass'],
    }
    
    # Compter les fichiers par extension
    extension_count = {}
    for root, _, files in os.walk(path):
        if '.git' in root:
            continue
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            extension_count[ext] = extension_count.get(ext, 0) + 1
    
    print(f"Extensions trouvées: {extension_count}")
    
    # Détecter le langage principal
    for lang, exts in language_extensions.items():
        count = sum(extension_count.get(ext, 0) for ext in exts)
        if count > 0:
            print(f"Langage détecté: {lang} ({count} fichiers)")
            return lang
    
    # Vérifier les fichiers de configuration spécifiques
    config_files = {
        'Python': ['requirements.txt', 'setup.py', 'Pipfile', 'pyproject.toml'],
        'JavaScript/TypeScript': ['package.json', 'yarn.lock', 'package-lock.json'],
        'Java': ['pom.xml', 'build.gradle'],
        'Go': ['go.mod', 'go.sum'],
        'Ruby': ['Gemfile', 'Gemfile.lock'],
        'PHP': ['composer.json', 'composer.lock'],
        'Rust': ['Cargo.toml', 'Cargo.lock'],
    }
    
    for lang, files in config_files.items():
        for file in files:
            if os.path.exists(os.path.join(path, file)):
                print(f"Fichier de configuration trouvé pour {lang}: {file}")
                return lang
    
    print("Aucun langage détecté")
    return "Unknown"

def detect_framework(path):
    print(f"\nDétection du framework dans {path}")
    # Logique améliorée de détection de framework
    if os.path.exists(os.path.join(path, "requirements.txt")):
        print("Analyse du fichier requirements.txt")
        with open(os.path.join(path, "requirements.txt")) as f:
            content = f.read().lower()
            if "django" in content:
                return "Django"
            elif "flask" in content:
                return "Flask"
            elif "fastapi" in content:
                return "FastAPI"
            elif "pyramid" in content:
                return "Pyramid"
            elif "tornado" in content:
                return "Tornado"
    
    if os.path.exists(os.path.join(path, "package.json")):
        print("Analyse du fichier package.json")
        with open(os.path.join(path, "package.json")) as f:
            content = f.read().lower()
            if "react" in content:
                return "React"
            elif "vue" in content:
                return "Vue.js"
            elif "angular" in content:
                return "Angular"
            elif "next" in content:
                return "Next.js"
            elif "express" in content:
                return "Express.js"
    
    if os.path.exists(os.path.join(path, "pom.xml")):
        print("Analyse du fichier pom.xml")
        with open(os.path.join(path, "pom.xml")) as f:
            content = f.read().lower()
            if "spring-boot" in content:
                return "Spring Boot"
            elif "quarkus" in content:
                return "Quarkus"
    
    # Vérification des dossiers spécifiques aux frameworks
    if os.path.exists(os.path.join(path, "src", "main", "java")):
        return "Spring Boot"
    elif os.path.exists(os.path.join(path, "src", "app")):
        return "Angular"
    elif os.path.exists(os.path.join(path, "src", "components")):
        return "React"
    
    print("Aucun framework détecté")
    return "Unknown"

def detect_dependencies(path):
    dependencies = []
    
    # Python dependencies
    if os.path.exists(os.path.join(path, "requirements.txt")):
        with open(os.path.join(path, "requirements.txt")) as f:
            dependencies.extend([line.strip() for line in f if line.strip() and not line.startswith("#")])
    
    # Node.js dependencies
    if os.path.exists(os.path.join(path, "package.json")):
        with open(os.path.join(path, "package.json")) as f:
            try:
                package_data = json.load(f)
                if "dependencies" in package_data:
                    dependencies.extend([f"{pkg}@{ver}" for pkg, ver in package_data["dependencies"].items()])
                if "devDependencies" in package_data:
                    dependencies.extend([f"{pkg}@{ver} (dev)" for pkg, ver in package_data["devDependencies"].items()])
            except json.JSONDecodeError:
                pass
    
    # Java dependencies
    if os.path.exists(os.path.join(path, "pom.xml")):
        with open(os.path.join(path, "pom.xml")) as f:
            content = f.read()
            # Simple regex pour extraire les dépendances Maven
            import re
            deps = re.findall(r'<dependency>.*?<artifactId>(.*?)</artifactId>.*?<version>(.*?)</version>.*?</dependency>', content, re.DOTALL)
            dependencies.extend([f"{dep[0]}@{dep[1]}" for dep in deps])
    
    return dependencies

def generate_pipeline_config(path):
    language = detect_language(path)
    framework = detect_framework(path)
    
    # Configuration de base
    config = {
        "name": "CI/CD Pipeline",
        "on": {
            "push": {
                "branches": ["main"]
            },
            "pull_request": {
                "branches": ["main"]
            }
        },
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {
                        "uses": "actions/checkout@v3"
                    }
                ]
            }
        }
    }
    
    # Ajout des étapes spécifiques selon le langage
    if language == "Python":
        config["jobs"]["build"]["steps"].extend([
            {
                "name": "Set up Python",
                "uses": "actions/setup-python@v4",
                "with": {
                    "python-version": "3.9"
                }
            },
            {
                "name": "Install dependencies",
                "run": "pip install -r requirements.txt"
            },
            {
                "name": "Run tests",
                "run": "python -m pytest"
            }
        ])
    elif language == "JavaScript/TypeScript":
        config["jobs"]["build"]["steps"].extend([
            {
                "name": "Set up Node.js",
                "uses": "actions/setup-node@v3",
                "with": {
                    "node-version": "16"
                }
            },
            {
                "name": "Install dependencies",
                "run": "npm install"
            },
            {
                "name": "Run tests",
                "run": "npm test"
            }
        ])
    elif language == "Java":
        config["jobs"]["build"]["steps"].extend([
            {
                "name": "Set up JDK",
                "uses": "actions/setup-java@v3",
                "with": {
                    "java-version": "11",
                    "distribution": "adopt"
                }
            },
            {
                "name": "Build with Maven",
                "run": "mvn -B package --file pom.xml"
            }
        ])
    
    # Ajout d'une étape de build Docker si un Dockerfile est présent
    if os.path.exists(os.path.join(path, "Dockerfile")):
        config["jobs"]["build"]["steps"].extend([
            {
                "name": "Build Docker image",
                "run": "docker build -t app:latest ."
            }
        ])
    
    return config

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
