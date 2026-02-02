# 🚀 Spot-Ref Azure Container Apps Deployment Guide

This directory contains all the necessary scripts and configurations for deploying Spot-Ref to Azure Container Apps in production.

## 📋 Overview

The deployment architecture consists of:
- **Azure Container Registry (ACR)** for storing Docker images
- **Azure Container Apps** for hosting the application containers
- **Azure Log Analytics** for monitoring and observability
- **Azure Storage** for persistent Qdrant data

## 🏗️ Infrastructure Components

### Container Applications
1. **spot-ref-chainlit** - Main chat interface (Chainlit)
2. **spot-ref-qdrant** - Vector database (Qdrant)
3. **spot-ref-ingestion** - Document ingestion job (on-demand)

### Production Docker Images
- **Dockerfile.chainlit.prod** - Optimized Chainlit container
- **Dockerfile.ingestion.prod** - Document ingestion container
- **Dockerfile.qdrant.prod** - Custom Qdrant container
- **docker-compose.prod.yml** - Production Docker Compose reference

## 🚀 Quick Deployment

### Prerequisites
- Azure CLI installed and authenticated
- Docker Desktop running
- PowerShell (Windows) or Bash (Linux/macOS)
- Azure subscription with appropriate permissions

### One-Command Deployment

```powershell
.\deploy\quick-deploy.ps1 `
    -ResourceGroupName "spot-ref-prod" `
    -Location "France Central" `
    -ContainerRegistryName "spotrefacr" `
    -ContainerAppsEnvironmentName "spot-ref-env" `
    -AzureOpenAIApiKey "your-api-key" `
    -AzureOpenAIEndpoint "https://your-resource.openai.azure.com/" `
    -AzureOpenAIDeployment "gpt4o" `
    -AzureOpenAIEmbeddingDeployment "text-embedding-ada-002"
```

## 📝 Step-by-Step Deployment

### Step 1: Azure Infrastructure Setup

```powershell
.\deploy\azure-setup.ps1 `
    -ResourceGroupName "spot-ref-prod" `
    -Location "France Central" `
    -ContainerRegistryName "spotrefacr" `
    -ContainerAppsEnvironmentName "spot-ref-env"
```

**What this creates:**
- Resource Group
- Azure Container Registry
- Log Analytics Workspace
- Container Apps Environment
- Storage Account (for Qdrant persistence)

### Step 2: Build and Push Docker Images

```powershell
.\deploy\build-and-push.ps1 `
    -ContainerRegistryName "spotrefacr" `
    -ImageTag "latest"
```

**What this does:**
- Builds production-optimized Docker images
- Pushes images to Azure Container Registry
- Tags images with specified version

### Step 3: Deploy Container Apps

```powershell
.\deploy\deploy-containers.ps1 `
    -ResourceGroupName "spot-ref-prod" `
    -ContainerRegistryName "spotrefacr" `
    -ContainerAppsEnvironmentName "spot-ref-env"
```

**What this creates:**
- Qdrant Container App (persistent vector database)
- Chainlit Container App (web interface)
- Ingestion Container App (document processing)

### Step 4: Configure Environment Variables

```powershell
.\deploy\configure-env.ps1 `
    -ResourceGroupName "spot-ref-prod" `
    -AzureOpenAIApiKey "your-api-key" `
    -AzureOpenAIEndpoint "https://your-resource.openai.azure.com/" `
    -AzureOpenAIDeployment "gpt4o" `
    -AzureOpenAIEmbeddingDeployment "text-embedding-ada-002"
```

**Optional parameters:**
- `-LangfuseSecretKey` and `-LangfusePublicKey` for observability
- `-SharePointSiteUrl`, `-SharePointUsername`, `-SharePointPassword`, `-SharePointLibraryName` for document ingestion

### Step 5: Run Data Ingestion

```powershell
.\deploy\run-ingestion.ps1 `
    -ResourceGroupName "spot-ref-prod" `
    -IngestionMode "5"
```

## 📊 Monitoring and Management

### View Application Logs

```bash
# Chainlit application logs
az containerapp logs show --name spot-ref-chainlit --resource-group spot-ref-prod

# Qdrant database logs
az containerapp logs show --name spot-ref-qdrant --resource-group spot-ref-prod

# Ingestion job logs
az containerapp logs show --name spot-ref-ingestion --resource-group spot-ref-prod
```

### Check Application Status

```bash
# List all container apps
az containerapp list --resource-group spot-ref-prod --output table

# Get specific app details
az containerapp show --name spot-ref-chainlit --resource-group spot-ref-prod
```

### Scaling Operations

```bash
# Scale Chainlit app
az containerapp update --name spot-ref-chainlit --resource-group spot-ref-prod --min-replicas 2 --max-replicas 10

# Scale Qdrant (keep at 1 for data consistency)
az containerapp update --name spot-ref-qdrant --resource-group spot-ref-prod --min-replicas 1 --max-replicas 1
```

## 🔧 Configuration Details

### Environment Variables

The following environment variables are configured automatically:

#### Core Application Variables
```
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
AZURE_FINAL_MODEL_DEPLOYMENT=gpt-4.1-mini
AZURE_AGENT_DEPLOYMENT=gpt-4o
OPENAI_API_VERSION=2023-05-15
```

#### Qdrant Configuration
```
QDRANT_HOST=spot-ref-qdrant.{region}.azurecontainerapps.io
QDRANT_PORT=443
QDRANT_COLLECTION=spot-ref-docs
```

#### Ingestion Configuration
```
INGESTION_MODE=5
BATCH_SIZE=64
DATA_DIR=Customer_txt
DOWNLOAD_WORKERS=10
CONVERSION_WORKERS=10
TRANSLATION_WORKERS=10
SPLITTING_WORKERS=10
EMBEDDING_WORKERS=10
```

### Resource Allocation

#### Chainlit Container App
- **CPU**: 1.0 vCPU
- **Memory**: 2.0 GB
- **Replicas**: 1-3 (auto-scaling)
- **Port**: 8000

#### Qdrant Container App
- **CPU**: 1.0 vCPU
- **Memory**: 2.0 GB
- **Replicas**: 1 (fixed)
- **Port**: 6333

#### Ingestion Container App
- **CPU**: 2.0 vCPU
- **Memory**: 4.0 GB
- **Replicas**: 0-1 (on-demand)

## 🛠️ Troubleshooting

### Common Issues

1. **Image Build Failures**
   ```bash
   # Check Docker daemon
   docker info
   
   # Verify ACR access
   az acr show --name spotrefacr --resource-group spot-ref-prod
   ```

2. **Container App Deployment Issues**
   ```bash
   # Check environment status
   az containerapp env show --name spot-ref-env --resource-group spot-ref-prod
   
   # View deployment logs
   az containerapp logs show --name spot-ref-chainlit --resource-group spot-ref-prod
   ```

3. **Application Runtime Errors**
   ```bash
   # Check environment variables
   az containerapp show --name spot-ref-chainlit --resource-group spot-ref-prod --query properties.template.containers[0].env
   
   # Restart application
   az containerapp restart --name spot-ref-chainlit --resource-group spot-ref-prod
   ```

### Performance Optimization

#### Auto-scaling Configuration
```bash
# Configure HTTP-based scaling
az containerapp update --name spot-ref-chainlit --resource-group spot-ref-prod \
    --min-replicas 1 --max-replicas 5 \
    --scale-rule-name http-rule \
    --scale-rule-http-concurrency 10
```

#### Resource Monitoring
```bash
# View resource metrics
az monitor metrics list \
    --resource /subscriptions/{subscription-id}/resourceGroups/spot-ref-prod/providers/Microsoft.App/containerApps/spot-ref-chainlit \
    --metric "CpuPercentage,MemoryPercentage"
```

## 💰 Cost Optimization

### Estimated Monthly Costs (France Central)
- **Container Apps**: ~€40-80/month (depends on usage)
- **Container Registry**: ~€5-15/month (image storage)
- **Log Analytics**: ~€10-30/month (log retention)
- **Storage Account**: ~€2-5/month (Qdrant data)

### Cost Reduction Strategies
1. **Scale to Zero**: Configure minimum replicas to 0 for development
2. **Right-sizing**: Monitor CPU/memory usage and adjust resources
3. **Log Retention**: Adjust Log Analytics retention period
4. **Image Cleanup**: Regularly clean old images from ACR

## 🔒 Security Considerations

### Network Security
- All Container Apps use HTTPS by default
- Internal communication uses service discovery
- No public access to Qdrant unless explicitly configured

### Secrets Management
- API keys stored as Container App environment variables
- Consider using Azure Key Vault for production secrets
- Rotate credentials regularly

### Access Control
- Use Azure RBAC for deployment permissions
- Implement authentication for the Chainlit interface
- Monitor access logs in Azure Monitor

## 📈 Maintenance and Updates

### Updating Application
```powershell
# Build new version
.\deploy\build-and-push.ps1 -ContainerRegistryName "spotrefacr" -ImageTag "v1.1.0"

# Update Container Apps
az containerapp update --name spot-ref-chainlit --resource-group spot-ref-prod \
    --image spotrefacr.azurecr.io/spot-ref-chainlit:v1.1.0
```

### Backup and Disaster Recovery
- Qdrant data is persisted in Azure Storage
- Container images are stored in ACR with geo-replication
- Application configuration is version-controlled

### Health Monitoring
- Built-in health checks for all containers
- Azure Monitor alerts for failures
- Log aggregation in Azure Log Analytics

## 🎯 Production Readiness Checklist

- [ ] Azure infrastructure created
- [ ] Docker images built and pushed
- [ ] Container Apps deployed
- [ ] Environment variables configured
- [ ] Data ingestion completed
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] SSL certificates validated
- [ ] Performance testing completed
- [ ] Security review completed
- [ ] Backup procedures verified
- [ ] Documentation updated

## 📞 Support

For deployment issues or questions:
1. Check the troubleshooting section above
2. Review Azure Container Apps documentation
3. Check application logs for specific error messages
4. Monitor Azure service health status

## 🔗 Useful Links

- [Azure Container Apps Documentation](https://docs.microsoft.com/en-us/azure/container-apps/)
- [Azure Container Registry Documentation](https://docs.microsoft.com/en-us/azure/container-registry/)
- [Azure Monitor Documentation](https://docs.microsoft.com/en-us/azure/azure-monitor/)
- [Chainlit Documentation](https://docs.chainlit.io/)
- [Qdrant Documentation](https://qdrant.tech/documentation/) 