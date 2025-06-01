# Vérifier si Docker est en cours d'exécution
Write-Host "Vérification de Docker..." -ForegroundColor Yellow
try {
    docker info | Out-Null
} catch {
    Write-Host "Erreur: Docker n'est pas en cours d'exécution. Veuillez démarrer Docker Desktop." -ForegroundColor Red
    exit 1
}

# Nettoyer les dossiers temporaires
Write-Host "Nettoyage des dossiers temporaires..." -ForegroundColor Yellow
Get-ChildItem -Path "temp" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path "repo_analysis_*" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

# Arrêter et supprimer tous les conteneurs en cours d'exécution
Write-Host "Arrêt et suppression des conteneurs en cours..." -ForegroundColor Yellow
docker ps -aq | ForEach-Object { docker stop $_ }
docker ps -aq | ForEach-Object { docker rm $_ }

# Supprimer toutes les images
Write-Host "Suppression des images Docker..." -ForegroundColor Yellow
docker images -q | ForEach-Object { docker rmi -f $_ }

# Construire la nouvelle image
Write-Host "Construction de la nouvelle image..." -ForegroundColor Green
try {
    docker build -t devops-mvp .
} catch {
    Write-Host "Erreur lors de la construction de l'image: $_" -ForegroundColor Red
    exit 1
}

# Lancer le nouveau conteneur
Write-Host "Démarrage du nouveau conteneur..." -ForegroundColor Green
try {
    docker run -d `
        --name devops-mvp `
        -p 8000:8000 `
        -v ${PWD}:/app `
        devops-mvp
} catch {
    Write-Host "Erreur lors du démarrage du conteneur: $_" -ForegroundColor Red
    exit 1
}

# Vérifier si le conteneur est en cours d'exécution
Start-Sleep -Seconds 2
$containerStatus = docker ps -q -f name=devops-mvp
if (-not $containerStatus) {
    Write-Host "Erreur: Le conteneur n'a pas démarré correctement" -ForegroundColor Red
    docker logs devops-mvp
    exit 1
}

# Afficher les logs du conteneur
Write-Host "Logs du conteneur:" -ForegroundColor Cyan
docker logs -f devops-mvp 