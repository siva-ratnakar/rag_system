#!/bin/bash

# RAG System Deployment Script
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

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if we have the required Docker Compose files
if [ ! -f "docker-compose-adaptive.yml" ]; then
    print_error "docker-compose-adaptive.yml not found. Please ensure the file exists in the current directory."
    exit 1
fi

print_status "Starting RAG System deployment..."

# Detect GPU availability
GPU_AVAILABLE=false
COMPOSE_FILE=""

if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        GPU_AVAILABLE=true
        print_status "🎮 NVIDIA GPU detected! Using GPU-optimized configuration."
        
        # Check if GPU compose file exists
        if [ -f "docker-compose.gpu.yml" ]; then
            COMPOSE_FILE="docker-compose.gpu.yml"
        else
            print_warning "GPU detected but docker-compose.gpu.yml not found. Using adaptive configuration."
            COMPOSE_FILE="docker-compose-adaptive.yml"
        fi
    else
        print_status "💻 No GPU detected. Using CPU-optimized configuration."
        COMPOSE_FILE="docker-compose-adaptive.yml"
    fi
else
    print_status "💻 No NVIDIA drivers detected. Using CPU-optimized configuration."
    COMPOSE_FILE="docker-compose-adaptive.yml"
fi

print_status "Using Docker Compose file: ${COMPOSE_FILE}"

# Create necessary directories
print_status "Creating directories..."
mkdir -p weaviate/weaviate_data
mkdir -p ollama/models
mkdir -p data
mkdir -p app/models

# Set proper permissions and ownership
print_status "Setting permissions and ownership..."
chmod -R 755 weaviate 2>/dev/null || true
chmod -R 755 ollama 2>/dev/null || true
chmod -R 755 data 2>/dev/null || true
chmod -R 755 app 2>/dev/null || true

# Fix ownership for ollama directory (ollama runs as user 1000 typically)
sudo chown -R 1000:1000 ollama 2>/dev/null || true
sudo chown -R $USER:$USER . 2>/dev/null || true

print_status "Directory structure created:"
ls -la ollama/
ls -la ollama/models/ 2>/dev/null || print_status "ollama/models directory created but empty"

# Set environment variables for adaptive configuration
export OLLAMA_NUM_PARALLEL=4
if [ "$GPU_AVAILABLE" = true ]; then
    export OLLAMA_NUM_PARALLEL=8
    print_status "Setting parallel processing to 8 for GPU configuration"
else
    print_status "Setting parallel processing to 4 for CPU configuration"
fi

print_status "Building and starting containers..."
if [ "$GPU_AVAILABLE" = true ] && [ -f "docker-compose.gpu.yml" ]; then
    # Use GPU-specific configuration with adaptive base
    docker-compose -f docker-compose-adaptive.yml -f docker-compose.gpu.yml up -d
else
    # Use adaptive configuration only
    docker-compose -f "${COMPOSE_FILE}" up -d
fi

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 15

# Additional wait and check for Ollama to be fully ready
print_status "Waiting for Ollama to initialize..."
for i in {1..30}; do
    if docker exec rag_ollama ollama list >/dev/null 2>&1; then
        print_status "✅ Ollama is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_warning "⚠️ Ollama took longer than expected to start"
        print_status "Checking Ollama logs:"
        docker logs rag_ollama --tail 10
    fi
    sleep 2
done

# Check if Ollama is ready and pull the appropriate model
print_status "Setting up optimal model based on hardware..."
if [ "$GPU_AVAILABLE" = true ]; then
    print_status "Pulling Gemma3 27B model for GPU..."
    docker exec rag_ollama ollama pull gemma3:27b || {
        print_warning "Failed to pull gemma3:27b, trying gemma2:27b..."
        docker exec rag_ollama ollama pull gemma2:27b || {
            print_warning "Failed to pull gemma2:27b, using gemma2:9b as fallback..."
            docker exec rag_ollama ollama pull gemma2:9b
        }
    }
else
    print_status "Pulling Gemma3 12B model for CPU..."
    docker exec rag_ollama ollama pull gemma3:12b || {
        print_warning "Failed to pull gemma3:12b, trying gemma2:9b..."
        docker exec rag_ollama ollama pull gemma2:9b || {
            print_warning "Failed to pull gemma2:9b, using gemma2:2b as fallback..."
            docker exec rag_ollama ollama pull gemma2:2b
        }
    }
fi

print_status "Checking service health..."
# Check Weaviate
if curl -s http://localhost:8080/v1/meta > /dev/null; then
    print_status "✅ Weaviate is running on http://localhost:8080"
else
    print_warning "⚠️  Weaviate may not be ready yet"
fi

# Check Ollama
if curl -s http://localhost:11434/api/tags > /dev/null; then
    print_status "✅ Ollama is running on http://localhost:11434"
else
    print_warning "⚠️  Ollama may not be ready yet"
fi

# Check RAG Application
if docker ps | grep -q rag_application; then
    print_status "✅ RAG Application container is running"
else
    print_warning "⚠️  RAG Application container may not be ready yet"
fi

print_status "RAG System deployed successfully!"
print_status "Configuration used: ${COMPOSE_FILE}"
if [ "$GPU_AVAILABLE" = true ]; then
    print_status "🎮 GPU acceleration enabled"
else
    print_status "💻 CPU-only mode"
fi

print_status ""
print_status "Next steps:"
print_status "1. Copy your PDF files to the 'data' directory"
print_status "2. Run: docker exec -it rag_application python main.py --ingest"
print_status "3. Start querying: docker exec -it rag_application python main.py"

print_status ""
print_status "Useful commands:"
print_status "- Check services: docker exec -it rag_application python main.py --check"
print_status "- Interactive mode: docker exec -it rag_application python main.py"
print_status "- Stop system: docker-compose -f ${COMPOSE_FILE} down"
print_status "- View logs: docker-compose -f ${COMPOSE_FILE} logs -f"
print_status "- View specific service logs: docker-compose -f ${COMPOSE_FILE} logs -f [ollama|weaviate|rag_app]"