#!/bin/bash

# Azure Deployment Script
# This script automates the deployment of your application to Azure Container Apps

set -e  # Exit on error

# Configuration - UPDATE THESE VALUES
RESOURCE_GROUP="your-resource-group"  # ← UPDATE: Your existing resource group name
LOCATION="eastus"  # ← UPDATE: Location of your resource group (or leave as is)
ACR_NAME="yourregistryname"  # ← UPDATE: Must be globally unique, lowercase, alphanumeric
ENV_NAME="your-env-name"  # ← UPDATE: Choose a name for Container Apps environment
BACKEND_APP_NAME="backend-app"
FRONTEND_APP_NAME="frontend-app"
FETCH_WEBSITE_APP_NAME="fetch-website-app"
TREND_KEYWORDS_APP_NAME="trend-keywords-app"

# Database configuration (already on Azure)
DB_HOST="eece798.mysql.database.azure.com"
DB_PORT="3306"
DB_NAME="nextgenai"
DB_USER="aline"
DB_PASSWORD="Jaz-agent"  # Consider using Azure Key Vault

# API Keys - Set these as environment variables before running the script
OPENAI_API_KEY="${OPENAI_API_KEY:-your-openai-key}"
FIRECRAWL_API_KEY="${FIRECRAWL_API_KEY:-your-firecrawl-key}"
PHANTOMBUSTER_API_KEY="${PHANTOMBUSTER_API_KEY:-your-phantombuster-key}"
LINKEDIN_SESSION_COOKIE="${LINKEDIN_SESSION_COOKIE:-your-linkedin-session-cookie}"
USER_AGENT="${USER_AGENT:-Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36}"
GOOGLE_CREDENTIALS_JSON="${GOOGLE_CREDENTIALS_JSON:-}"

echo "Starting Azure deployment..."

# Step 1: Check if Resource Group exists, create if it doesn't
echo "Checking resource group..."
if az group show --name $RESOURCE_GROUP &>/dev/null; then
    echo "Resource group '$RESOURCE_GROUP' already exists. Using existing resource group."
    # Get the location of existing resource group
    LOCATION=$(az group show --name $RESOURCE_GROUP --query location -o tsv)
    echo "Resource group location: $LOCATION"
else
    echo "Creating resource group..."
    az group create --name $RESOURCE_GROUP --location $LOCATION
fi

# Step 2: Create Azure Container Registry
echo "Creating Azure Container Registry..."
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --admin-enabled true

# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# Login to ACR
echo "Logging into ACR..."
az acr login --name $ACR_NAME

# Step 3: Build and push images
echo "Building and pushing images to ACR..."

echo "Building frontend..."
cd frontend
az acr build --registry $ACR_NAME --image frontend:latest .
cd ..

echo "Building backend..."
cd backend
az acr build --registry $ACR_NAME --image backend:latest .
cd ..

echo "Building fetch-website..."
cd Fetch_Website
az acr build --registry $ACR_NAME --image fetch-website:latest .
cd ..

echo "Building trend-keywords..."
cd trend_keywords
az acr build --registry $ACR_NAME --image trend-keywords:latest .
cd ..

# Step 4: Create Container Apps Environment
echo "Creating Container Apps environment..."
az containerapp env create \
  --name $ENV_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Step 5: Create Backend Container App
echo "Creating backend container app..."
az containerapp create \
  --name $BACKEND_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image "$ACR_NAME.azurecr.io/backend:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --target-port 5000 \
  --ingress external \
  --env-vars \
    "FLASK_ENV=production" \
    "DB_HOST=$DB_HOST" \
    "DB_PORT=$DB_PORT" \
    "DB_NAME=$DB_NAME" \
    "DB_USER=$DB_USER" \
    "DB_PASSWORD=$DB_PASSWORD" \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 3

# Store secrets for backend
echo "Setting secrets for backend..."
SECRETS=(
  "openai-api-key=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"
  "firecrawl-api-key=fc-798e3d8da9bf4560a320ca55cfa483a9"
  "phantombuster-api-key=Pyu5VsElIJ58AGePW6gK68pwEDTNlHPYNCWOOmxccX4"
  "linkedin-session-cookie=AQEDAV_V5FYAgsPWAAABmeNAxoYAAAGav4JyV04AB0dHLZkJjmEOeY1v6oXTpJ6RPG2DbJU1WdcuQ6cdrExVBfA6BQ-CCTlxVhi66n91WNscgAeMW67mXNgv333Jk9IqYuvZ8RqhqXU-3imYKQF0LDeX"
)
if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then
  SECRETS+=("google-credentials-json=$GOOGLE_CREDENTIALS_JSON")
fi
az containerapp secret set \
  --name $BACKEND_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --secrets "${SECRETS[@]}"

# Update backend to use secrets
ENV_VARS=(
  "OPENAI_API_KEY=secretref:openai-api-key"
  "FIRECRAWL_API_KEY=secretref:firecrawl-api-key"
  "PHANTOMBUSTER_API_KEY=secretref:phantombuster-api-key"
  "LINKEDIN_SESSION_COOKIE=secretref:linkedin-session-cookie"
  "USER_AGENT=$USER_AGENT"
)
if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then
  ENV_VARS+=("GOOGLE_CREDENTIALS_JSON=secretref:google-credentials-json")
fi
az containerapp update \
  --name $BACKEND_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars "${ENV_VARS[@]}"

# Get backend URL
BACKEND_URL=$(az containerapp show --name $BACKEND_APP_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv)
echo "Backend URL: https://$BACKEND_URL"

# Step 6: Create Fetch Website Container App
echo "Creating fetch-website container app..."
az containerapp create \
  --name $FETCH_WEBSITE_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image "$ACR_NAME.azurecr.io/fetch-website:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --target-port 3001 \
  --ingress internal \
  --env-vars "PORT=3001" \
  --cpu 0.25 \
  --memory 0.5Gi \
  --min-replicas 1 \
  --max-replicas 2

# Store secrets for fetch-website
az containerapp secret set \
  --name $FETCH_WEBSITE_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --secrets "firecrawl-api-key=$FIRECRAWL_API_KEY"

az containerapp update \
  --name $FETCH_WEBSITE_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars "FIRECRAWL_API_KEY=secretref:firecrawl-api-key"

# Step 7: Create Trend Keywords Container App
echo "Creating trend-keywords container app..."
az containerapp create \
  --name $TREND_KEYWORDS_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image "$ACR_NAME.azurecr.io/trend-keywords:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --target-port 3002 \
  --ingress internal \
  --env-vars "PORT=3002" \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 2

# Store secrets for trend-keywords
az containerapp secret set \
  --name $TREND_KEYWORDS_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --secrets "openai-api-key=$OPENAI_API_KEY" "firecrawl-api-key=$FIRECRAWL_API_KEY"

az containerapp update \
  --name $TREND_KEYWORDS_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars \
    "OPENAI_API_KEY=secretref:openai-api-key" \
    "FIRECRAWL_API_KEY=secretref:firecrawl-api-key"

# Get trend-keywords URL (for public access if needed)
TREND_KEYWORDS_URL=$(az containerapp show --name $TREND_KEYWORDS_APP_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv)

# Step 8: Create Frontend Container App
echo "Creating frontend container app..."
az containerapp create \
  --name $FRONTEND_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image "$ACR_NAME.azurecr.io/frontend:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --target-port 3000 \
  --ingress external \
  --env-vars \
    "FLASK_ENV=production" \
    "BACKEND_URL=http://$BACKEND_APP_NAME" \
    "PUBLIC_BACKEND_URL=https://$BACKEND_URL" \
    "FETCH_WEBSITE_URL=http://$FETCH_WEBSITE_APP_NAME" \
    "LLM_API_URL=http://$TREND_KEYWORDS_APP_NAME" \
    "PUBLIC_LLM_API_URL=https://$TREND_KEYWORDS_URL" \
  --cpu 0.5 \
  --memory 0.5Gi \
  --min-replicas 1 \
  --max-replicas 3

# Get frontend URL
FRONTEND_URL=$(az containerapp show --name $FRONTEND_APP_NAME --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv)

echo ""
echo "========================================="
echo "Deployment completed successfully!"
echo "========================================="
echo "Frontend URL: https://$FRONTEND_URL"
echo "Backend URL: https://$BACKEND_URL"
echo ""
echo "Next steps:"
echo "1. Update CORS settings in backend to allow $FRONTEND_URL"
echo "2. Configure custom domain (optional)"
echo "3. Set up SSL certificates"
echo "4. Configure monitoring and alerts"

