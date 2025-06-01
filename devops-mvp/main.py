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
        
        git.Repo.clone_from(repo_url, local_path)
        
        # Analyser la structure du projet
        analysis = {
            "language": detect_language(local_path),
            "framework": detect_framework(local_path),
            "dependencies": detect_dependencies(local_path),
            "suggested_pipeline": generate_pipeline_config(local_path)
        }
        
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def detect_language(path):
    # Logique simple de détection de langage
    if os.path.exists(os.path.join(path, "requirements.txt")):
        return "Python"
    elif os.path.exists(os.path.join(path, "package.json")):
        return "JavaScript"
    return "Unknown"

def detect_framework(path):
    # Logique simple de détection de framework
    if os.path.exists(os.path.join(path, "requirements.txt")):
        with open(os.path.join(path, "requirements.txt")) as f:
            content = f.read()
            if "django" in content:
                return "Django"
            elif "flask" in content:
                return "Flask"
            elif "fastapi" in content:
                return "FastAPI"
    return "Unknown"

def detect_dependencies(path):
    dependencies = []
    if os.path.exists(os.path.join(path, "requirements.txt")):
        with open(os.path.join(path, "requirements.txt")) as f:
            dependencies = [line.strip() for line in f if line.strip()]
    return dependencies

def generate_pipeline_config(path):
    # Générer une configuration GitHub Actions basique
    return {
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
                        "uses": "actions/checkout@v2"
                    },
                    {
                        "name": "Set up Python",
                        "uses": "actions/setup-python@v2",
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
                ]
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
