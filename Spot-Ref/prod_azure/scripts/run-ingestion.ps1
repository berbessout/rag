# =============================================================================
# RUN INGESTION JOB ON AZURE CONTAINER APPS
# =============================================================================
# This script runs the ingestion job to populate the vector database

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$false)]
    [string]$IngestionMode = "5"
)

Write-Host "Starting ingestion job..." -ForegroundColor Green
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Green
Write-Host "Ingestion Mode: $IngestionMode" -ForegroundColor Green

# Start the ingestion job
Write-Host "Starting ingestion container app..." -ForegroundColor Green
az containerapp job start --name spot-ref-ingestion --resource-group $ResourceGroupName

# Monitor the job
Write-Host "Monitoring ingestion job..." -ForegroundColor Green
$jobStatus = "Running"
$timeout = 3600  # 1 hour timeout
$elapsed = 0
$interval = 30   # Check every 30 seconds

while ($jobStatus -eq "Running" -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds $interval
    $elapsed += $interval
    
    $jobStatus = az containerapp job show --name spot-ref-ingestion --resource-group $ResourceGroupName --query properties.status -o tsv
    
    Write-Host "Job status: $jobStatus (Elapsed: $elapsed seconds)" -ForegroundColor Yellow
    
    if ($jobStatus -eq "Succeeded") {
        Write-Host "Ingestion job completed successfully!" -ForegroundColor Green
        break
    } elseif ($jobStatus -eq "Failed") {
        Write-Host "Ingestion job failed!" -ForegroundColor Red
        break
    }
}

if ($elapsed -ge $timeout) {
    Write-Host "Ingestion job timed out after $timeout seconds" -ForegroundColor Red
}

# Get job logs
Write-Host "Getting ingestion job logs..." -ForegroundColor Green
az containerapp job logs show --name spot-ref-ingestion --resource-group $ResourceGroupName

Write-Host "`n==============================================================================" -ForegroundColor Yellow
Write-Host "INGESTION JOB COMPLETE" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Yellow
Write-Host "Final Status: $jobStatus" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Yellow 