#!/bin/bash

# Fix permissions for RAG system after disk remount
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_status "Fixing permissions for RAG system..."

# Stop containers first
print_status "Stopping existing containers..."
docker-compose -f docker-compose-adaptive.yml down 2>/dev/null || true

# Remove any existing containers
print_status "Cleaning up containers..."
docker rm -f rag_ollama rag_weaviate rag_application 2>/dev/null || true

# Create directories with proper structure
print_status "Creating directory structure..."
mkdir -p ollama/models
mkdir -p weaviate/weaviate_data  
mkdir -p data
mkdir -p app/models

# Fix ownership and permissions
print_status "Setting ownership and permissions..."
sudo chown -R $USER:$USER .
chmod -R 755 .

# Special handling for ollama directory (needs to be accessible by container user)
chmod -R 777 ollama/
chmod -R 777 weaviate/

print_status "Current directory structure:"
ls -la
print_status "Ollama directory:"
ls -la ollama/
print_status "Weaviate directory:"
ls -la weaviate/

print_status "✅ Permissions fixed! You can now run ./deploy.sh"