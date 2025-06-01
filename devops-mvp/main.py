import os
import shutil
import tempfile
import subprocess
from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import git
import yaml
import json
from pathlib import Path
from fastapi.templating import Jinja2Templates
import time
import re

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
    temp_dir = None
    try:
        # Créer un dossier temporaire unique
        temp_dir = tempfile.mkdtemp(prefix="repo_analysis_")
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        local_path = os.path.join(temp_dir, repo_name)
        
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
            "port": detect_port(local_path),
            "suggested_pipeline": generate_pipeline_config(local_path),
            "health_score": calculate_health_score(local_path),
            "cloud_costs": analyze_cloud_costs(local_path)
        }
        
        print(f"Analyse terminée: {analysis}")
        
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        print(f"Erreur lors de l'analyse: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        # Nettoyage du dossier temporaire
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"Dossier temporaire {temp_dir} supprimé avec succès")
            except Exception as e:
                print(f"Erreur lors de la suppression du dossier temporaire: {str(e)}")

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
    
    # Détection basée sur les fichiers de configuration
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
    
    # Détection basée sur la structure des fichiers
    for root, _, files in os.walk(path):
        if '.git' in root:
            continue
            
        # Détection FastAPI
        if any(f.endswith('.py') for f in files):
            for file in files:
                if file.endswith('.py'):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                            if 'fastapi' in content and 'app = fastapi' in content:
                                return "FastAPI"
                            elif 'flask' in content and 'app = flask' in content:
                                return "Flask"
                            elif 'django' in content and 'django.setup()' in content:
                                return "Django"
                    except Exception as e:
                        print(f"Erreur lors de la lecture du fichier {file}: {str(e)}")
    
    # Détection basée sur la structure des dossiers
    if os.path.exists(os.path.join(path, "manage.py")):
        return "Django"
    elif os.path.exists(os.path.join(path, "app.py")) or os.path.exists(os.path.join(path, "main.py")):
        # Vérifier le contenu pour déterminer le framework
        try:
            with open(os.path.join(path, "main.py"), 'r', encoding='utf-8') as f:
                content = f.read().lower()
                if 'fastapi' in content:
                    return "FastAPI"
                elif 'flask' in content:
                    return "Flask"
        except:
            pass
    
    print("Aucun framework détecté")
    return "Unknown"

def detect_dependencies(path):
    print(f"\nDétection des dépendances dans {path}")
    dependencies = []
    
    # Python dependencies
    if os.path.exists(os.path.join(path, "requirements.txt")):
        print("Analyse du fichier requirements.txt")
        try:
            with open(os.path.join(path, "requirements.txt")) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extraire le nom et la version
                        if '==' in line:
                            name, version = line.split('==')
                            dependencies.append(f"{name}=={version}")
                        elif '>=' in line:
                            name, version = line.split('>=')
                            dependencies.append(f"{name}>={version}")
                        elif '<=' in line:
                            name, version = line.split('<=')
                            dependencies.append(f"{name}<={version}")
                        else:
                            dependencies.append(line)
        except Exception as e:
            print(f"Erreur lors de la lecture de requirements.txt: {str(e)}")
    
    # Node.js dependencies
    if os.path.exists(os.path.join(path, "package.json")):
        print("Analyse du fichier package.json")
        try:
            with open(os.path.join(path, "package.json")) as f:
                package_data = json.load(f)
                if "dependencies" in package_data:
                    for pkg, ver in package_data["dependencies"].items():
                        dependencies.append(f"{pkg}@{ver}")
                if "devDependencies" in package_data:
                    for pkg, ver in package_data["devDependencies"].items():
                        dependencies.append(f"{pkg}@{ver} (dev)")
        except json.JSONDecodeError as e:
            print(f"Erreur lors de la lecture de package.json: {str(e)}")
    
    # Java dependencies
    if os.path.exists(os.path.join(path, "pom.xml")):
        print("Analyse du fichier pom.xml")
        try:
            with open(os.path.join(path, "pom.xml")) as f:
                content = f.read()
                # Simple regex pour extraire les dépendances Maven
                import re
                deps = re.findall(r'<dependency>.*?<artifactId>(.*?)</artifactId>.*?<version>(.*?)</version>.*?</dependency>', content, re.DOTALL)
                dependencies.extend([f"{dep[0]}@{dep[1]}" for dep in deps])
        except Exception as e:
            print(f"Erreur lors de la lecture de pom.xml: {str(e)}")
    
    # Détection des dépendances dans le code Python
    for root, _, files in os.walk(path):
        if '.git' in root or 'venv' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Détecter les imports
                        import_lines = re.findall(r'^(?:from|import)\s+([\w\.]+)', content, re.MULTILINE)
                        for imp in import_lines:
                            if imp not in ['os', 'sys', 're', 'json', 'datetime', 'time']:  # Ignorer les imports standards
                                dependencies.append(f"{imp} (importé dans {file})")
                except Exception as e:
                    print(f"Erreur lors de la lecture du fichier {file}: {str(e)}")
    
    print(f"Dépendances trouvées: {dependencies}")
    return dependencies

def detect_port(path):
    print(f"\nDétection du port dans {path}")
    port = None
    
    # Chercher dans les fichiers Python
    for root, _, files in os.walk(path):
        if '.git' in root or 'venv' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Chercher les patterns courants de définition de port
                        port_patterns = [
                            r'port\s*=\s*(\d+)',
                            r'PORT\s*=\s*(\d+)',
                            r'port\s*:\s*(\d+)',
                            r'PORT\s*:\s*(\d+)',
                            r'listen\(.*?,\s*(\d+)\)',
                            r'bind\(.*?,\s*(\d+)\)',
                            r'run\(.*?port\s*=\s*(\d+)',
                            r'uvicorn\.run\(.*?port\s*=\s*(\d+)',
                            r'flask\.run\(.*?port\s*=\s*(\d+)',
                            r'django\.runserver\(.*?port\s*=\s*(\d+)'
                        ]
                        for pattern in port_patterns:
                            matches = re.findall(pattern, content)
                            if matches:
                                port = int(matches[0])
                                print(f"Port trouvé dans {file}: {port}")
                                return port
                except Exception as e:
                    print(f"Erreur lors de la lecture du fichier {file}: {str(e)}")
    
    # Chercher dans les fichiers de configuration
    config_files = [
        'config.py', 'settings.py', '.env', 'docker-compose.yml', 'docker-compose.yaml',
        'dockerfile', 'Dockerfile', 'nginx.conf', 'apache.conf'
    ]
    
    for config_file in config_files:
        config_path = os.path.join(path, config_file)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Chercher les patterns de port dans les fichiers de configuration
                    port_patterns = [
                        r'PORT\s*=\s*(\d+)',
                        r'port\s*=\s*(\d+)',
                        r'port:\s*(\d+)',
                        r'expose\s*(\d+)',
                        r'EXPOSE\s*(\d+)',
                        r'listen\s*(\d+)',
                        r'LISTEN\s*(\d+)'
                    ]
                    for pattern in port_patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            port = int(matches[0])
                            print(f"Port trouvé dans {config_file}: {port}")
                            return port
            except Exception as e:
                print(f"Erreur lors de la lecture de {config_file}: {str(e)}")
    
    # Port par défaut selon le framework détecté
    framework = detect_framework(path)
    default_ports = {
        'FastAPI': 8000,
        'Flask': 5000,
        'Django': 8000,
        'Node.js': 3000,
        'React': 3000,
        'Vue.js': 8080,
        'Angular': 4200
    }
    
    if framework in default_ports:
        port = default_ports[framework]
        print(f"Port par défaut pour {framework}: {port}")
    else:
        port = 8000  # Port par défaut générique
        print(f"Port par défaut générique: {port}")
    
    return port

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

def calculate_health_score(path):
    print(f"\nCalcul du Health Score pour {path}")
    score = 0
    max_score = 100
    details = {}
    
    # 1. Vérification des tests (20 points)
    test_score = check_tests(path)
    score += test_score
    details['tests'] = {
        'score': test_score,
        'max': 20,
        'details': check_test_details(path)
    }
    
    # 2. Vérification de la documentation (15 points)
    doc_score = check_documentation(path)
    score += doc_score
    details['documentation'] = {
        'score': doc_score,
        'max': 15,
        'details': check_doc_details(path)
    }
    
    # 3. Vérification de la structure du projet (15 points)
    structure_score = check_project_structure(path)
    score += structure_score
    details['structure'] = {
        'score': structure_score,
        'max': 15,
        'details': check_structure_details(path)
    }
    
    # 4. Vérification des bonnes pratiques (20 points)
    practices_score = check_best_practices(path)
    score += practices_score
    details['best_practices'] = {
        'score': practices_score,
        'max': 20,
        'details': check_practices_details(path)
    }
    
    # 5. Vérification de la sécurité (15 points)
    security_score = check_security(path)
    score += security_score
    details['security'] = {
        'score': security_score,
        'max': 15,
        'details': check_security_details(path)
    }
    
    # 6. Vérification des dépendances (15 points)
    deps_score = check_dependencies_health(path)
    score += deps_score
    details['dependencies'] = {
        'score': deps_score,
        'max': 15,
        'details': check_deps_details(path)
    }
    
    return {
        'total_score': score,
        'max_score': max_score,
        'percentage': (score / max_score) * 100,
        'details': details
    }

def check_tests(path):
    print(f"\nVérification des tests dans {path}")
    score = 0
    test_files = []
    ignored_dirs = ['venv', '.git', '__pycache__', 'site-packages']
    
    # Vérifier la présence de dossiers de test
    if os.path.exists(os.path.join(path, "tests")):
        score += 10
        print("Dossier tests/ trouvé")
    if os.path.exists(os.path.join(path, "test")):
        score += 10
        print("Dossier test/ trouvé")
    
    # Parcourir les fichiers en ignorant les dossiers spécifiés
    for root, dirs, files in os.walk(path):
        # Ignorer les dossiers spécifiés
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, path)
                
                # Vérifier si c'est un fichier de test
                is_test_file = (
                    file.startswith('test_') or 
                    file.endswith('_test.py') or 
                    'tests/' in relative_path or 
                    'test/' in relative_path
                )
                
                if is_test_file:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Vérifier si le fichier contient des fonctions de test
                            if 'def test_' in content:
                                test_files.append(relative_path)
                                print(f"Fichier de test trouvé: {relative_path}")
                    except Exception as e:
                        print(f"Erreur lors de la lecture du fichier {file_path}: {str(e)}")
    
    # Calculer le score basé sur le nombre de fichiers de test
    if test_files:
        score += min(len(test_files) * 2, 10)  # Maximum 10 points pour les fichiers de test
        print(f"Nombre de fichiers de test trouvés: {len(test_files)}")
    
    return min(score, 20)

def check_test_details(path):
    print(f"\nDétails des tests dans {path}")
    details = []
    test_files = []
    ignored_dirs = ['venv', '.git', '__pycache__', 'site-packages']
    
    # Vérifier les dossiers de test
    if os.path.exists(os.path.join(path, "tests")):
        details.append("Dossier tests/ présent")
    if os.path.exists(os.path.join(path, "test")):
        details.append("Dossier test/ présent")
    
    # Parcourir les fichiers en ignorant les dossiers spécifiés
    for root, dirs, files in os.walk(path):
        # Ignorer les dossiers spécifiés
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, path)
                
                # Vérifier si c'est un fichier de test
                is_test_file = (
                    file.startswith('test_') or 
                    file.endswith('_test.py') or 
                    'tests/' in relative_path or 
                    'test/' in relative_path
                )
                
                if is_test_file:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Vérifier si le fichier contient des fonctions de test
                            if 'def test_' in content:
                                test_files.append(relative_path)
                                details.append(f"Fichier de test trouvé: {relative_path}")
                                # Compter le nombre de fonctions de test
                                test_functions = content.count('def test_')
                                if test_functions > 0:
                                    details.append(f"  - Contient {test_functions} fonction(s) de test")
                    except Exception as e:
                        print(f"Erreur lors de la lecture du fichier {file_path}: {str(e)}")
    
    if not test_files:
        details.append("Aucun fichier de test trouvé")
    
    return details

def check_documentation(path):
    score = 0
    # Vérifier la présence de README
    if os.path.exists(os.path.join(path, "README.md")):
        score += 5
    if os.path.exists(os.path.join(path, "docs")):
        score += 5
    
    # Vérifier la documentation dans le code
    doc_files = []
    for root, _, files in os.walk(path):
        if '.git' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        content = f.read()
                        if '"""' in content or "'''" in content:
                            doc_files.append(file)
                except:
                    pass
    
    if doc_files:
        score += 5
    
    return min(score, 15)

def check_doc_details(path):
    details = []
    
    if os.path.exists(os.path.join(path, "README.md")):
        details.append("README.md présent")
    if os.path.exists(os.path.join(path, "docs")):
        details.append("Dossier docs présent")
    
    doc_files = []
    for root, _, files in os.walk(path):
        if '.git' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        content = f.read()
                        if '"""' in content or "'''" in content:
                            doc_files.append(file)
                except:
                    pass
    
    if doc_files:
        details.append(f"Fichiers avec documentation: {len(doc_files)}")
    
    return details

def check_project_structure(path):
    score = 0
    # Vérifier la structure du projet
    if os.path.exists(os.path.join(path, "src")):
        score += 5
    if os.path.exists(os.path.join(path, "tests")):
        score += 5
    if os.path.exists(os.path.join(path, "docs")):
        score += 5
    
    return min(score, 15)

def check_structure_details(path):
    details = []
    
    if os.path.exists(os.path.join(path, "src")):
        details.append("Dossier src présent")
    if os.path.exists(os.path.join(path, "tests")):
        details.append("Dossier tests présent")
    if os.path.exists(os.path.join(path, "docs")):
        details.append("Dossier docs présent")
    
    return details

def check_best_practices(path):
    score = 0
    # Vérifier les bonnes pratiques
    if os.path.exists(os.path.join(path, ".gitignore")):
        score += 5
    if os.path.exists(os.path.join(path, "requirements.txt")):
        score += 5
    if os.path.exists(os.path.join(path, "setup.py")):
        score += 5
    if os.path.exists(os.path.join(path, "Dockerfile")):
        score += 5
    
    return min(score, 20)

def check_practices_details(path):
    details = []
    
    if os.path.exists(os.path.join(path, ".gitignore")):
        details.append(".gitignore présent")
    if os.path.exists(os.path.join(path, "requirements.txt")):
        details.append("requirements.txt présent")
    if os.path.exists(os.path.join(path, "setup.py")):
        details.append("setup.py présent")
    if os.path.exists(os.path.join(path, "Dockerfile")):
        details.append("Dockerfile présent")
    
    return details

def check_security(path):
    score = 0
    # Vérifier la sécurité
    if os.path.exists(os.path.join(path, ".env.example")):
        score += 5
    if os.path.exists(os.path.join(path, "requirements.txt")):
        try:
            with open(os.path.join(path, "requirements.txt")) as f:
                content = f.read().lower()
                if "cryptography" in content or "pyjwt" in content:
                    score += 5
        except:
            pass
    
    return min(score, 15)

def check_security_details(path):
    details = []
    
    if os.path.exists(os.path.join(path, ".env.example")):
        details.append(".env.example présent")
    
    if os.path.exists(os.path.join(path, "requirements.txt")):
        try:
            with open(os.path.join(path, "requirements.txt")) as f:
                content = f.read().lower()
                if "cryptography" in content:
                    details.append("cryptography présent")
                if "pyjwt" in content:
                    details.append("pyjwt présent")
        except:
            pass
    
    return details

def check_dependencies_health(path):
    score = 0
    # Vérifier la santé des dépendances
    if os.path.exists(os.path.join(path, "requirements.txt")):
        try:
            with open(os.path.join(path, "requirements.txt")) as f:
                content = f.read()
                # Vérifier si les versions sont spécifiées
                if "==" in content:
                    score += 5
                # Vérifier si les dépendances sont à jour
                if "fastapi" in content.lower():
                    score += 5
                if "pytest" in content.lower():
                    score += 5
        except:
            pass
    
    return min(score, 15)

def check_deps_details(path):
    details = []
    
    if os.path.exists(os.path.join(path, "requirements.txt")):
        try:
            with open(os.path.join(path, "requirements.txt")) as f:
                content = f.read()
                if "==" in content:
                    details.append("Versions spécifiées")
                if "fastapi" in content.lower():
                    details.append("FastAPI présent")
                if "pytest" in content.lower():
                    details.append("pytest présent")
        except:
            pass
    
    return details

def analyze_cloud_costs(path):
    print(f"\nAnalyse des coûts cloud pour {path}")
    costs = {
        "compute": analyze_compute_costs(path),
        "storage": analyze_storage_costs(path),
        "network": analyze_network_costs(path),
        "database": analyze_database_costs(path),
        "recommendations": []
    }
    
    # Générer des recommandations basées sur l'analyse
    costs["recommendations"] = generate_cost_recommendations(costs, path)
    
    return costs

def analyze_compute_costs(path):
    costs = {
        "estimated_monthly": 0,
        "details": [],
        "optimization_potential": 0
    }
    
    # Analyser les fichiers de configuration pour détecter les ressources de calcul
    if os.path.exists(os.path.join(path, "Dockerfile")):
        try:
            with open(os.path.join(path, "Dockerfile"), 'r') as f:
                content = f.read().lower()
                # Détecter les ressources CPU/RAM
                if "cpu" in content or "memory" in content:
                    costs["details"].append("Configuration Docker détectée")
                    costs["estimated_monthly"] += 50  # Estimation de base
        except Exception as e:
            print(f"Erreur lors de la lecture du Dockerfile: {str(e)}")
    
    # Vérifier les fichiers de configuration cloud
    cloud_configs = {
        "aws": ["serverless.yml", "template.yaml"],
        "azure": ["azure-pipelines.yml", "host.json"],
        "gcp": ["app.yaml", "cloudbuild.yaml"]
    }
    
    for provider, configs in cloud_configs.items():
        for config in configs:
            if os.path.exists(os.path.join(path, config)):
                costs["details"].append(f"Configuration {provider} détectée")
                costs["estimated_monthly"] += 100  # Estimation de base
    
    # Si aucune configuration n'est détectée, estimer les coûts basés sur le type de projet
    if not costs["details"]:
        if os.path.exists(os.path.join(path, "main.py")) or os.path.exists(os.path.join(path, "app.py")):
            costs["details"].append("Application Python détectée")
            costs["estimated_monthly"] = 30  # Coût estimé pour une petite application Python
        elif os.path.exists(os.path.join(path, "package.json")):
            costs["details"].append("Application Node.js détectée")
            costs["estimated_monthly"] = 25  # Coût estimé pour une petite application Node.js
    
    return costs

def analyze_storage_costs(path):
    costs = {
        "estimated_monthly": 0,
        "details": [],
        "optimization_potential": 0
    }
    
    # Analyser la taille du projet
    total_size = 0
    for root, _, files in os.walk(path):
        if '.git' in root:
            continue
        for file in files:
            try:
                total_size += os.path.getsize(os.path.join(root, file))
            except:
                pass
    
    # Convertir en GB et estimer les coûts
    size_gb = total_size / (1024 * 1024 * 1024)
    costs["estimated_monthly"] = size_gb * 0.023  # Coût moyen par GB
    costs["details"].append(f"Taille du projet: {size_gb:.2f} GB")
    
    return costs

def analyze_network_costs(path):
    costs = {
        "estimated_monthly": 0,
        "details": [],
        "optimization_potential": 0
    }
    
    # Vérifier les configurations réseau
    if os.path.exists(os.path.join(path, "nginx.conf")):
        costs["details"].append("Configuration Nginx détectée")
        costs["estimated_monthly"] += 20
    
    # Vérifier les fichiers de configuration cloud pour les règles de réseau
    cloud_configs = {
        "aws": ["security-group.json", "vpc-config.json"],
        "azure": ["network-config.json"],
        "gcp": ["network-config.yaml"]
    }
    
    for provider, configs in cloud_configs.items():
        for config in configs:
            if os.path.exists(os.path.join(path, config)):
                costs["details"].append(f"Configuration réseau {provider} détectée")
                costs["estimated_monthly"] += 30
    
    return costs

def analyze_database_costs(path):
    costs = {
        "estimated_monthly": 0,
        "details": [],
        "optimization_potential": 0
    }
    
    # Vérifier les configurations de base de données
    db_configs = {
        "postgresql": ["postgresql.conf", "pg_hba.conf"],
        "mysql": ["my.cnf", "my.ini"],
        "mongodb": ["mongod.conf"],
        "redis": ["redis.conf"]
    }
    
    for db, configs in db_configs.items():
        for config in configs:
            if os.path.exists(os.path.join(path, config)):
                costs["details"].append(f"Configuration {db} détectée")
                costs["estimated_monthly"] += 50
    
    return costs

def generate_cost_recommendations(costs, path):
    recommendations = []
    
    # Recommandations générales pour les projets locaux
    if not any(costs[category]["details"] for category in ["compute", "network", "database"]):
        recommendations.extend([
            {
                "category": "compute",
                "title": "Migration vers le cloud",
                "description": "Envisagez de migrer votre application vers le cloud pour bénéficier d'une meilleure scalabilité et disponibilité. Commencez par un environnement de développement sur AWS/Azure/GCP.",
                "potential_savings": "Flexibilité des coûts"
            },
            {
                "category": "storage",
                "title": "Optimisation du stockage local",
                "description": "Mettez en place une stratégie de sauvegarde et de versioning pour vos données locales. Considérez l'utilisation de stockage cloud pour les sauvegardes.",
                "potential_savings": "Sécurité accrue"
            }
        ])
    
    # Recommandations spécifiques basées sur le type de projet
    if os.path.exists(os.path.join(path, "main.py")) or os.path.exists(os.path.join(path, "app.py")):
        recommendations.append({
            "category": "compute",
            "title": "Containerisation",
            "description": "Containerisez votre application Python avec Docker pour faciliter le déploiement et la scalabilité. Cela permettra une transition plus facile vers le cloud.",
            "potential_savings": "Réduction des coûts de déploiement"
        })
    
    # Recommandations pour le calcul
    if costs["compute"]["estimated_monthly"] > 0:
        recommendations.append({
            "category": "compute",
            "title": "Optimisation des ressources de calcul",
            "description": "Envisagez d'utiliser des instances spot ou de réduire la taille des instances pendant les périodes de faible charge.",
            "potential_savings": "20-40%"
        })
    
    # Recommandations pour le stockage
    if costs["storage"]["estimated_monthly"] > 0:
        recommendations.append({
            "category": "storage",
            "title": "Optimisation du stockage",
            "description": "Utilisez le stockage à froid pour les données rarement accédées et mettez en place une politique de rétention.",
            "potential_savings": "30-50%"
        })
    
    # Recommandations pour le réseau
    if costs["network"]["estimated_monthly"] > 0:
        recommendations.append({
            "category": "network",
            "title": "Optimisation du réseau",
            "description": "Mettez en place un CDN et optimisez les règles de pare-feu pour réduire les coûts de transfert de données.",
            "potential_savings": "15-25%"
        })
    
    # Recommandations pour la base de données
    if costs["database"]["estimated_monthly"] > 0:
        recommendations.append({
            "category": "database",
            "title": "Optimisation de la base de données",
            "description": "Envisagez d'utiliser des instances réservées et optimisez les requêtes pour réduire la consommation de ressources.",
            "potential_savings": "25-35%"
        })
    
    return recommendations

@app.get("/docker", response_class=HTMLResponse)
async def docker_page(request: Request):
    return templates.TemplateResponse("docker.html", {"request": request})

@app.post("/simulate-docker")
async def simulate_docker(repo_url: str = Form(...), port: int = Form(...)):
    async def generate_logs():
        temp_dir = None
        try:
            # Créer un dossier temporaire
            temp_dir = tempfile.mkdtemp(prefix="docker_sim_")
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            local_path = os.path.join(temp_dir, repo_name)
            
            yield f"Clonage du repository {repo_url}...\n"
            repo = git.Repo.clone_from(repo_url, local_path)
            
            # Vérifier si un Dockerfile existe
            dockerfile_path = os.path.join(local_path, "Dockerfile")
            if not os.path.exists(dockerfile_path):
                yield "Création d'un Dockerfile par défaut...\n"
                with open(dockerfile_path, "w") as f:
                    f.write("""FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
""")
            
            # Construire l'image Docker
            yield "Construction de l'image Docker...\n"
            image_name = f"{repo_name.lower()}:latest"
            build_process = subprocess.Popen(
                ["docker", "build", "-t", image_name, "."],
                cwd=local_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Lire la sortie du build en temps réel
            for line in build_process.stdout:
                yield f"Build: {line}"
            
            build_process.wait()
            if build_process.returncode != 0:
                yield "Erreur lors de la construction de l'image Docker\n"
                return
            
            # Lancer le conteneur
            yield f"Lancement du conteneur sur le port {port}...\n"
            container_name = f"{repo_name.lower()}-container"
            run_process = subprocess.Popen(
                ["docker", "run", "-d", "-p", f"{port}:8000", "--name", container_name, image_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Lire la sortie du run
            for line in run_process.stdout:
                yield f"Run: {line}"
            
            run_process.wait()
            if run_process.returncode != 0:
                yield "Erreur lors du lancement du conteneur\n"
                return
            
            # Afficher les logs du conteneur
            yield "Récupération des logs du conteneur...\n"
            log_process = subprocess.Popen(
                ["docker", "logs", "-f", container_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Lire les logs pendant 30 secondes
            start_time = time.time()
            while time.time() - start_time < 30:
                line = log_process.stdout.readline()
                if not line:
                    break
                yield f"Log: {line}"
            
            yield "\nSimulation terminée. Le conteneur continue de tourner en arrière-plan.\n"
            yield f"L'application est accessible sur http://localhost:{port}\n"
            
        except Exception as e:
            yield f"Erreur: {str(e)}\n"
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
    
    return StreamingResponse(generate_logs(), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
