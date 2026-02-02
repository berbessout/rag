# =============================================================================
# DEPLOY CONTAINER APPS TO AZURE
# =============================================================================
# This script deploys the Spot-Ref application to Azure Container Apps

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$true)]
    [string]$ContainerRegistryName,
    
    [Parameter(Mandatory=$true)]
    [string]$ContainerAppsEnvironmentName,
    
    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "latest"
)

# Get ACR login server
$acrLoginServer = az acr show --name $ContainerRegistryName --query loginServer -o tsv
$acrUsername = az acr credential show --name $ContainerRegistryName --query username -o tsv
$acrPassword = az acr credential show --name $ContainerRegistryName --query passwords[0].value -o tsv

Write-Host "ACR Login Server: $acrLoginServer" -ForegroundColor Green

# Deploy Qdrant Container App
Write-Host "Deploying Qdrant Container App..." -ForegroundColor Green
az containerapp create `
    --name spot-ref-qdrant `
    --resource-group $ResourceGroupName `
    --environment $ContainerAppsEnvironmentName `
    --image "$acrLoginServer/spot-ref-qdrant:$ImageTag" `
    --registry-server $acrLoginServer `
    --registry-username $acrUsername `
    --registry-password $acrPassword `
    --target-port 6333 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 1 `
    --cpu 1.0 `
    --memory 2.0Gi `
    --env-vars QDRANT__SERVICE__HTTP_PORT=6333 QDRANT__SERVICE__GRPC_PORT=6334 QDRANT__LOG_LEVEL=INFO

# Get Qdrant FQDN
$qdrantFqdn = az containerapp show --name spot-ref-qdrant --resource-group $ResourceGroupName --query properties.configuration.ingress.fqdn -o tsv
Write-Host "Qdrant FQDN: $qdrantFqdn" -ForegroundColor Green

# Deploy Chainlit Container App
Write-Host "Deploying Chainlit Container App..." -ForegroundColor Green
az containerapp create `
    --name spot-ref-chainlit `
    --resource-group $ResourceGroupName `
    --environment $ContainerAppsEnvironmentName `
    --image "$acrLoginServer/spot-ref-chainlit:$ImageTag" `
    --registry-server $acrLoginServer `
    --registry-username $acrUsername `
    --registry-password $acrPassword `
    --target-port 8000 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 3 `
    --cpu 1.0 `
    --memory 2.0Gi `
    --env-vars PYTHONPATH=/app QDRANT_HOST=$qdrantFqdn QDRANT_PORT=443 QDRANT_COLLECTION=spot-ref-docs

# Get Chainlit FQDN
$chainlitFqdn = az containerapp show --name spot-ref-chainlit --resource-group $ResourceGroupName --query properties.configuration.ingress.fqdn -o tsv
Write-Host "Chainlit FQDN: $chainlitFqdn" -ForegroundColor Green

# Deploy Ingestion Container App (on-demand)
Write-Host "Deploying Ingestion Container App..." -ForegroundColor Green
az containerapp create `
    --name spot-ref-ingestion `
    --resource-group $ResourceGroupName `
    --environment $ContainerAppsEnvironmentName `
    --image "$acrLoginServer/spot-ref-ingestion:$ImageTag" `
    --registry-server $acrLoginServer `
    --registry-username $acrUsername `
    --registry-password $acrPassword `
    --min-replicas 0 `
    --max-replicas 1 `
    --cpu 2.0 `
    --memory 4.0Gi `
    --env-vars PYTHONPATH=/app QDRANT_HOST=$qdrantFqdn QDRANT_PORT=443 QDRANT_COLLECTION=spot-ref-docs INGESTION_MODE=5 BATCH_SIZE=64

Write-Host "`n==============================================================================" -ForegroundColor Yellow
Write-Host "CONTAINER APPS DEPLOYMENT COMPLETE" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "Chainlit URL: https://$chainlitFqdn" -ForegroundColor Green
Write-Host "Qdrant URL: https://$qdrantFqdn" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Configure environment variables using configure-env.ps1" -ForegroundColor White
Write-Host "2. Run ingestion job to populate the vector database" -ForegroundColor White
Write-Host "3. Test the application" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Yellow 