# =============================================================================
# SPOT-REF AZURE CONTAINER APPS DEPLOYMENT SCRIPT
# =============================================================================
# This script sets up the Azure infrastructure for deploying Spot-Ref

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$true)]
    [string]$Location,
    
    [Parameter(Mandatory=$true)]
    [string]$ContainerRegistryName,
    
    [Parameter(Mandatory=$true)]
    [string]$ContainerAppsEnvironmentName,
    
    [Parameter(Mandatory=$false)]
    [string]$SubscriptionId
)

# Check if Azure CLI is installed
if (-not (Get-Command "az" -ErrorAction SilentlyContinue)) {
    Write-Error "Azure CLI is not installed. Please install it from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
}

# Set subscription if provided
if ($SubscriptionId) {
    Write-Host "Setting subscription to $SubscriptionId..." -ForegroundColor Green
    az account set --subscription $SubscriptionId
}

# Get current subscription
$currentSubscription = az account show --query "name" -o tsv
Write-Host "Using subscription: $currentSubscription" -ForegroundColor Green

# Create resource group
Write-Host "Creating resource group: $ResourceGroupName in $Location..." -ForegroundColor Green
az group create --name $ResourceGroupName --location $Location

# Create Azure Container Registry
Write-Host "Creating Azure Container Registry: $ContainerRegistryName..." -ForegroundColor Green
az acr create --resource-group $ResourceGroupName --name $ContainerRegistryName --sku Standard --admin-enabled true

# Get ACR login server
$acrLoginServer = az acr show --name $ContainerRegistryName --resource-group $ResourceGroupName --query loginServer -o tsv
Write-Host "ACR Login Server: $acrLoginServer" -ForegroundColor Green

# Create Log Analytics workspace
$logAnalyticsName = "$ContainerAppsEnvironmentName-logs"
Write-Host "Creating Log Analytics workspace: $logAnalyticsName..." -ForegroundColor Green
az monitor log-analytics workspace create --resource-group $ResourceGroupName --workspace-name $logAnalyticsName --location $Location

# Get Log Analytics workspace ID and key
$logAnalyticsId = az monitor log-analytics workspace show --resource-group $ResourceGroupName --workspace-name $logAnalyticsName --query customerId -o tsv
$logAnalyticsKey = az monitor log-analytics workspace get-shared-keys --resource-group $ResourceGroupName --workspace-name $logAnalyticsName --query primarySharedKey -o tsv

# Create Container Apps environment
Write-Host "Creating Container Apps environment: $ContainerAppsEnvironmentName..." -ForegroundColor Green
az containerapp env create `
    --name $ContainerAppsEnvironmentName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --logs-workspace-id $logAnalyticsId `
    --logs-workspace-key $logAnalyticsKey

# Create Azure Storage Account for Qdrant persistence
$storageAccountName = "$($ContainerRegistryName)storage"
Write-Host "Creating Storage Account: $storageAccountName..." -ForegroundColor Green
az storage account create `
    --name $storageAccountName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --sku Standard_LRS

# Get storage account key
$storageKey = az storage account keys list --resource-group $ResourceGroupName --account-name $storageAccountName --query "[0].value" -o tsv

# Create storage share for Qdrant
Write-Host "Creating storage share for Qdrant..." -ForegroundColor Green
az storage share create --name qdrant-storage --account-name $storageAccountName --account-key $storageKey

# Output deployment information
Write-Host "`n==============================================================================" -ForegroundColor Yellow
Write-Host "AZURE INFRASTRUCTURE SETUP COMPLETE" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Green
Write-Host "Location: $Location" -ForegroundColor Green
Write-Host "Container Registry: $ContainerRegistryName" -ForegroundColor Green
Write-Host "ACR Login Server: $acrLoginServer" -ForegroundColor Green
Write-Host "Container Apps Environment: $ContainerAppsEnvironmentName" -ForegroundColor Green
Write-Host "Storage Account: $storageAccountName" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Build and push Docker images to ACR" -ForegroundColor White
Write-Host "2. Deploy Container Apps using deploy-containers.ps1" -ForegroundColor White
Write-Host "3. Configure environment variables" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Yellow 