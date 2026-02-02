# =============================================================================
# CONFIGURE ENVIRONMENT VARIABLES FOR CONTAINER APPS
# =============================================================================
# This script configures environment variables for the deployed Container Apps

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIApiKey,
    
    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIEndpoint,
    
    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIDeployment,
    
    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIEmbeddingDeployment,
    
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
    [string]$SharePointLibraryName
)

# Get Qdrant FQDN
$qdrantFqdn = az containerapp show --name spot-ref-qdrant --resource-group $ResourceGroupName --query properties.configuration.ingress.fqdn -o tsv

# Configure Chainlit Container App environment variables
Write-Host "Configuring Chainlit Container App environment variables..." -ForegroundColor Green

$chainlitEnvVars = @(
    "PYTHONPATH=/app",
    "AZURE_OPENAI_API_KEY=$AzureOpenAIApiKey",
    "AZURE_OPENAI_ENDPOINT=$AzureOpenAIEndpoint",
    "AZURE_OPENAI_DEPLOYMENT=$AzureOpenAIDeployment",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=$AzureOpenAIEmbeddingDeployment",
    "AZURE_FINAL_MODEL_DEPLOYMENT=gpt-4.1-mini",
    "AZURE_AGENT_DEPLOYMENT=gpt-4o",
    "OPENAI_API_VERSION=2023-05-15",
    "QDRANT_HOST=$qdrantFqdn",
    "QDRANT_PORT=443",
    "QDRANT_COLLECTION=spot-ref-docs"
)

# Add Langfuse variables if provided
if ($LangfuseSecretKey -and $LangfusePublicKey) {
    $chainlitEnvVars += "LANGFUSE_SECRET_KEY=$LangfuseSecretKey"
    $chainlitEnvVars += "LANGFUSE_PUBLIC_KEY=$LangfusePublicKey"
    $chainlitEnvVars += "LANGFUSE_HOST=https://cloud.langfuse.com"
}

az containerapp update `
    --name spot-ref-chainlit `
    --resource-group $ResourceGroupName `
    --set-env-vars $chainlitEnvVars

# Configure Ingestion Container App environment variables
Write-Host "Configuring Ingestion Container App environment variables..." -ForegroundColor Green

$ingestionEnvVars = @(
    "PYTHONPATH=/app",
    "AZURE_OPENAI_API_KEY=$AzureOpenAIApiKey",
    "AZURE_OPENAI_ENDPOINT=$AzureOpenAIEndpoint",
    "AZURE_OPENAI_DEPLOYMENT=$AzureOpenAIDeployment",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=$AzureOpenAIEmbeddingDeployment",
    "OPENAI_API_VERSION=2023-05-15",
    "QDRANT_HOST=$qdrantFqdn",
    "QDRANT_PORT=443",
    "QDRANT_COLLECTION=spot-ref-docs",
    "INGESTION_MODE=5",
    "BATCH_SIZE=64",
    "DATA_DIR=Customer_txt",
    "DOWNLOAD_WORKERS=10",
    "CONVERSION_WORKERS=10",
    "TRANSLATION_WORKERS=10",
    "SPLITTING_WORKERS=10",
    "EMBEDDING_WORKERS=10",
    "MAX_MEMORY_GB=4.0",
    "RETRY_MAX_ATTEMPTS=3",
    "RETRY_BACKOFF_FACTOR=2.0",
    "RETRY_INITIAL_DELAY=1.0",
    "RETRY_MAX_DELAY=60.0",
    "API_RATE_LIMIT_OPENAI=10",
    "API_RATE_LIMIT_SP=50",
    "ENABLE_PROGRESS_TRACKING=true"
)

# Add SharePoint variables if provided
if ($SharePointSiteUrl -and $SharePointUsername -and $SharePointPassword -and $SharePointLibraryName) {
    $ingestionEnvVars += "SHAREPOINT_SITE_URL=$SharePointSiteUrl"
    $ingestionEnvVars += "SHAREPOINT_USERNAME=$SharePointUsername"
    $ingestionEnvVars += "SHAREPOINT_PASSWORD=$SharePointPassword"
    $ingestionEnvVars += "SHAREPOINT_LIBRARY_NAME=$SharePointLibraryName"
}

az containerapp update `
    --name spot-ref-ingestion `
    --resource-group $ResourceGroupName `
    --set-env-vars $ingestionEnvVars

Write-Host "`n==============================================================================" -ForegroundColor Yellow
Write-Host "ENVIRONMENT VARIABLES CONFIGURATION COMPLETE" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "Chainlit Container App: Configured with Azure OpenAI and Qdrant settings" -ForegroundColor Green
Write-Host "Ingestion Container App: Configured with all required environment variables" -ForegroundColor Green
Write-Host "Qdrant Host: $qdrantFqdn" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Yellow 