# =============================================================================
# SPOT-REF QUICK DEPLOYMENT SCRIPT
# =============================================================================
# This script runs the complete deployment process in sequence

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$true)]
    [string]$Location,
    
    [Parameter(Mandatory=$true)]
    [string]$ContainerRegistryName,
    
    [Parameter(Mandatory=$true)]
    [string]$ContainerAppsEnvironmentName,
    
    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIApiKey,
    
    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIEndpoint,
    
    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIDeployment,
    
    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIEmbeddingDeployment,
    
    [Parameter(Mandatory=$false)]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory=$false)]
    [string]$LangfuseSecretKey,
    
    [Parameter(Mandatory=$false)]
    [string]$LangfusePublicKey,
    
    [Parameter(Mandatory=$false)]
    [string]$SharePointSiteUrl,
    
    [Parameter(Mandatory=$false)]
    [string]$SharePointUsername,
    
    [Parameter(Mandatory=$false)]
    [string]$SharePointPassword,
    
    [Parameter(Mandatory=$false)]
    [string]$SharePointLibraryName,
    
    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "latest"
)

Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "SPOT-REF QUICK DEPLOYMENT STARTING" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Yellow

# Step 1: Setup Azure Infrastructure
Write-Host "`n🏗️  STEP 1: Setting up Azure Infrastructure..." -ForegroundColor Green
$azureSetupParams = @{
    ResourceGroupName = $ResourceGroupName
    Location = $Location
    ContainerRegistryName = $ContainerRegistryName
    ContainerAppsEnvironmentName = $ContainerAppsEnvironmentName
}

if ($SubscriptionId) {
    $azureSetupParams.SubscriptionId = $SubscriptionId
}

& "$PSScriptRoot\azure-setup.ps1" @azureSetupParams

if ($LASTEXITCODE -ne 0) {
    Write-Error "Azure setup failed!"
    exit 1
}

# Step 2: Build and Push Docker Images
Write-Host "`n🐳 STEP 2: Building and pushing Docker images..." -ForegroundColor Green
& "$PSScriptRoot\build-and-push.ps1" -ContainerRegistryName $ContainerRegistryName -ImageTag $ImageTag

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build and push failed!"
    exit 1
}

# Step 3: Deploy Container Apps
Write-Host "`n🚀 STEP 3: Deploying Container Apps..." -ForegroundColor Green
& "$PSScriptRoot\deploy-containers.ps1" -ResourceGroupName $ResourceGroupName -ContainerRegistryName $ContainerRegistryName -ContainerAppsEnvironmentName $ContainerAppsEnvironmentName -ImageTag $ImageTag

if ($LASTEXITCODE -ne 0) {
    Write-Error "Container Apps deployment failed!"
    exit 1
}

# Step 4: Configure Environment Variables
Write-Host "`n⚙️  STEP 4: Configuring environment variables..." -ForegroundColor Green
$configParams = @{
    ResourceGroupName = $ResourceGroupName
    AzureOpenAIApiKey = $AzureOpenAIApiKey
    AzureOpenAIEndpoint = $AzureOpenAIEndpoint
    AzureOpenAIDeployment = $AzureOpenAIDeployment
    AzureOpenAIEmbeddingDeployment = $AzureOpenAIEmbeddingDeployment
}

if ($LangfuseSecretKey) { $configParams.LangfuseSecretKey = $LangfuseSecretKey }
if ($LangfusePublicKey) { $configParams.LangfusePublicKey = $LangfusePublicKey }
if ($SharePointSiteUrl) { $configParams.SharePointSiteUrl = $SharePointSiteUrl }
if ($SharePointUsername) { $configParams.SharePointUsername = $SharePointUsername }
if ($SharePointPassword) { $configParams.SharePointPassword = $SharePointPassword }
if ($SharePointLibraryName) { $configParams.SharePointLibraryName = $SharePointLibraryName }

& "$PSScriptRoot\configure-env.ps1" @configParams

if ($LASTEXITCODE -ne 0) {
    Write-Error "Environment configuration failed!"
    exit 1
}

# Step 5: Get deployment URLs
$chainlitFqdn = az containerapp show --name spot-ref-chainlit --resource-group $ResourceGroupName --query properties.configuration.ingress.fqdn -o tsv
$qdrantFqdn = az containerapp show --name spot-ref-qdrant --resource-group $ResourceGroupName --query properties.configuration.ingress.fqdn -o tsv

Write-Host "`n==============================================================================" -ForegroundColor Yellow
Write-Host "🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Green
Write-Host "Container Registry: $ContainerRegistryName" -ForegroundColor Green
Write-Host "Container Apps Environment: $ContainerAppsEnvironmentName" -ForegroundColor Green
Write-Host "`nApplication URLs:" -ForegroundColor Yellow
Write-Host "  🌐 Chainlit Interface: https://$chainlitFqdn" -ForegroundColor Green
Write-Host "  🔍 Qdrant API: https://$qdrantFqdn" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Run ingestion to populate the database:" -ForegroundColor White
Write-Host "     .\prod_azure\scripts\run-ingestion.ps1 -ResourceGroupName '$ResourceGroupName'" -ForegroundColor Gray
Write-Host "  2. Test the application at: https://$chainlitFqdn" -ForegroundColor White
Write-Host "  3. Monitor logs and metrics in Azure Portal" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Yellow 