# scripts/deploy-cloud-run.ps1
# One-command deployment for StadiumIQ to Google Cloud Run
# Fill in PROJECT_ID before running.

$PROJECT_ID   = "electionguide-ai-7c996"
$SERVICE_NAME = "stadium-iq"
$REGION       = "us-central1"
$IMAGE        = "gcr.io/$PROJECT_ID/$SERVICE_NAME"
$VERSION      = "1.0.0"

# Load GEMINI_API_KEY from .env if not set in shell environment
if (-not $env:GEMINI_API_KEY -and (Test-Path ".env")) {
    $env:GEMINI_API_KEY = (Get-Content ".env" | Select-String -Pattern "^GEMINI_API_KEY=(.+)$" | ForEach-Object { $_.Matches.Groups[1].Value }).Trim()
}

Write-Host "=== StadiumIQ Cloud Run Deployment ===" -ForegroundColor Cyan
Write-Host "Project:  $PROJECT_ID"
Write-Host "Service:  $SERVICE_NAME"
Write-Host "Region:   $REGION"
Write-Host "Image:    $IMAGE"
Write-Host ""

# Build and push container image
Write-Host "Building image..." -ForegroundColor Yellow
gcloud builds submit --tag "$IMAGE" --project "$PROJECT_ID"
if ($LASTEXITCODE -ne 0) { Write-Error "Build failed"; exit 1 }

# Deploy to Cloud Run
Write-Host "Deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --image      "$IMAGE" `
    --region     $REGION `
    --project    $PROJECT_ID `
    --platform   managed `
    --allow-unauthenticated `
    --set-env-vars (
        "GEMINI_API_KEY=$env:GEMINI_API_KEY," +
        "GOOGLE_CLOUD_PROJECT=$PROJECT_ID," +
        "GOOGLE_CLOUD_REGION=$REGION," +
        "FIRESTORE_ENABLED=true," +
        "MAX_CONCURRENT_LLM_CALLS=3," +
        "LOG_LEVEL=INFO," +
        "CROWD_AMBER_THRESHOLD=70.0," +
        "CROWD_RED_THRESHOLD=85.0"
    ) `
    --memory     512Mi `
    --cpu        1 `
    --min-instances 1 `
    --max-instances 5

if ($LASTEXITCODE -ne 0) { Write-Error "Deployment failed"; exit 1 }

# Fetch the live URL
$URL = gcloud run services describe $SERVICE_NAME --region $REGION --project $PROJECT_ID --format "value(status.url)"
Write-Host ""
Write-Host "Deployed to: $URL" -ForegroundColor Green

# ── Post-deployment smoke tests ────────────────────────────────────────────────
Write-Host ""
Write-Host "Running smoke tests..." -ForegroundColor Yellow

# 1. Health check
$health = Invoke-RestMethod "$URL/health"
if ($health.status -ne "ok") { Write-Error "Health check FAILED"; exit 1 }
Write-Host "✅ Health: OK (version=$($health.version), cache=$($health.cache_entries))" -ForegroundColor Green

# 2. Frontend
$front = Invoke-WebRequest "$URL/" -UseBasicParsing
if ($front.StatusCode -ne 200) { Write-Error "Frontend FAILED"; exit 1 }
Write-Host "✅ Frontend: OK (HTTP 200)" -ForegroundColor Green

# 3. API endpoint
$payload = @{
    profile    = @{ name="SmokeTest"; role="fan"; language="en"; mobility_aid="none"; visual_impairment=$false; hearing_impairment=$false; party_size=1 }
    venue      = @{ venue="sofi_stadium"; section="100"; current_zone="Gate A"; match_phase="arrival"; crowd_density_pct=60.0 }
    navigation = @{ destination="seat"; destination_detail=""; requires_elevator=$false; requires_accessible_route=$false }
    transport  = @{ transport_mode="shuttle"; direction="arriving"; distance_km=3.0 }
} | ConvertTo-Json -Depth 5

$apiResp = Invoke-RestMethod "$URL/api/assist" -Method Post -Body $payload -ContentType "application/json"
if (-not $apiResp.navigation) { Write-Error "API FAILED - missing navigation field"; exit 1 }
Write-Host "✅ API /api/assist: OK" -ForegroundColor Green

Write-Host ""
Write-Host "=== All smoke tests passed ===" -ForegroundColor Green
Write-Host "Live URL: $URL" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS:"
Write-Host "1. Update README.md with live URL: $URL"
Write-Host "2. Verify Firestore console shows at least 1 record in 'stadium_assists' collection"
Write-Host "3. Check security headers: curl -I $URL"
