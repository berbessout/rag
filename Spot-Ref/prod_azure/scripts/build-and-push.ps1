# =============================================================================
# BUILD AND PUSH DOCKER IMAGES TO AZURE CONTAINER REGISTRY
# =============================================================================
# This script builds the Docker images and pushes them to ACR

param(
    [Parameter(Mandatory=$true)]
    [string]$ContainerRegistryName,
    
    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "latest"
)

# Check if Docker is running
if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
    Write-Error "Docker Desktop is not running. Please start Docker Desktop and try again."
    exit 1
}

# Navigate to project root (assuming script is in prod_azure/scripts/)
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $projectRoot

# Get ACR login server
$acrLoginServer = az acr show --name $ContainerRegistryName --query loginServer -o tsv
if (-not $acrLoginServer) {
    Write-Error "Could not get ACR login server. Please check if the ACR exists and you have access."
    exit 1
}

Write-Host "ACR Login Server: $acrLoginServer" -ForegroundColor Green
Write-Host "Building from directory: $projectRoot" -ForegroundColor Green

# Login to ACR
Write-Host "Logging in to Azure Container Registry..." -ForegroundColor Green
az acr login --name $ContainerRegistryName

# Build and push Chainlit image
Write-Host "Building Chainlit image..." -ForegroundColor Green
docker build -f prod_azure/Dockerfile.chainlit.prod -t "$acrLoginServer/spot-ref-chainlit:$ImageTag" .

Write-Host "Pushing Chainlit image to ACR..." -ForegroundColor Green
docker push "$acrLoginServer/spot-ref-chainlit:$ImageTag"

# Build and push Ingestion image
Write-Host "Building Ingestion image..." -ForegroundColor Green
docker build -f prod_azure/Dockerfile.ingestion.prod -t "$acrLoginServer/spot-ref-ingestion:$ImageTag" .

Write-Host "Pushing Ingestion image to ACR..." -ForegroundColor Green
docker push "$acrLoginServer/spot-ref-ingestion:$ImageTag"

# Build and push Qdrant image
Write-Host "Building Qdrant image..." -ForegroundColor Green
docker build -f prod_azure/Dockerfile.qdrant.prod -t "$acrLoginServer/spot-ref-qdrant:$ImageTag" .

Write-Host "Pushing Qdrant image to ACR..." -ForegroundColor Green
docker push "$acrLoginServer/spot-ref-qdrant:$ImageTag"

# List all images in ACR
Write-Host "`nImages in ACR:" -ForegroundColor Yellow
az acr repository list --name $ContainerRegistryName --output table

Write-Host "`n==============================================================================" -ForegroundColor Yellow
Write-Host "DOCKER IMAGES BUILD AND PUSH COMPLETE" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "Registry: $acrLoginServer" -ForegroundColor Green
Write-Host "Images:" -ForegroundColor Green
Write-Host "  - spot-ref-chainlit:$ImageTag" -ForegroundColor White
Write-Host "  - spot-ref-ingestion:$ImageTag" -ForegroundColor White
Write-Host "  - spot-ref-qdrant:$ImageTag" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Yellow 