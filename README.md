# Spiritual Texts RAG System

A comprehensive Retrieval-Augmented Generation (RAG) system designed for spiritual and religious texts, including Puranas, Bhagavad Gita, Mahabharata, Sastras, and Sai Baba's works. This system combines OCR capabilities for PDF processing with intelligent document retrieval and AI-powered question answering.

## 🌟 Features

### Core Capabilities
- **Intelligent Document Processing**: OCR conversion of spiritual PDFs with automatic categorization
- **Advanced RAG System**: Vector-based document retrieval with similarity filtering
- **Dynamic Source Retrieval**: Automatically adjusts number of sources based on query complexity
- **Multi-Model Support**: GPU/CPU adaptive configuration with automatic model optimization
- **Dockerized Architecture**: Portable deployment with Weaviate, Ollama, and custom RAG application

### Text Categories Supported
- **Puranas**: Bhagavata, Vishnu, Shiva, Devi Puranas
- **Sacred Texts**: Bhagavad Gita, Mahabharata
- **Sastras**: Dharma, Artha, Kama Sastras
- **Sai Baba Works**: Vahinis, Sathya Sai Speaks, Summer Courses, Sathyam Shivam Sundaram
- **General Spiritual**: Other spiritual and philosophical texts

## 🏗️ Architecture

```
RAG_SYSTEM/
├── docker-compose-adaptive.yml    # Main Docker configuration
├── docker-compose.gpu.yml         # GPU-specific overrides
├── deploy.sh                      # Automated deployment script
├── fix-permissions.sh             # Permission repair utility
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py                    # Core RAG application
├── data/                          # Input PDFs directory
├── weaviate/
│   └── weaviate_data/            # Vector database storage
└── ollama/
    └── models/                   # LLM models storage
```

## 🚀 Quick Start

### Prerequisites
- **Windows with WSL2** (for Linux environment)
- **Docker and Docker Compose** installed in WSL
- **External storage device** (recommended for large datasets)

### 1. Initial Setup

#### Mount External Storage (Optional but Recommended)
```bash
# Format external drive to ext4 using MiniTool Partition Wizard
# Mount the drive in WSL
wsl --mount \\.\PHYSICALDRIVE1 --partition 1 --type ext4
sudo mkdir /mnt/ragdisk
lsblk  # Find your drive (e.g., /dev/sdd1)
sudo mount -t ext4 /dev/sdd1 /mnt/ragdisk
```

#### Install Docker in WSL
First, enable systemd in WSL:
```bash
# Follow Microsoft's systemd guide
# https://learn.microsoft.com/en-us/windows/wsl/systemd#how-to-enable-systemd
```

Then install Docker:
```bash
sudo apt install ca-certificates curl gnupg lsb-release
sudo mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
sudo systemctl enable docker.service
sudo systemctl enable containerd.service
sudo systemctl start docker.service
```

### 2. Deploy the System

```bash
# Navigate to your RAG system directory
cd /mnt/ragdisk/RAG_SYSTEM  # or your chosen location

# Fix permissions after mounting
./fix-permissions.sh

# Deploy the system (auto-detects GPU/CPU)
./deploy.sh
```

The deployment script will:
- 🔍 Auto-detect GPU availability
- 📦 Pull appropriate models (Gemma3 27B for GPU, 12B for CPU)
- 🚀 Start all services (Weaviate, Ollama, RAG app)
- ✅ Verify system health

### 3. Process Your Documents

#### Option A: OCR Processing (for scanned PDFs)
The system includes OCR capabilities using Tesseract and Ghostscript:

```bash
# Requirements (install on Windows):
# - Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
# - Ghostscript: https://www.ghostscript.com/download/gsdnld.html
# - Poppler: https://github.com/oschwartz10612/poppler-windows/releases

# Use the provided batch script to convert scanned PDFs to searchable text
# (See OCR script in the documentation)
```

#### Option B: Direct PDF Ingestion
```bash
# Copy your spiritual PDFs to the data directory
cp /path/to/your/pdfs/* data/

# Ingest documents into the vector database
docker exec -it rag_application python main.py --ingest
```

### 4. Start Querying

```bash
# Interactive mode
docker exec -it rag_application python main.py

# Direct query
docker exec -it rag_application python main.py --query "What is dharma according to the Bhagavad Gita?"

# Check system status
docker exec -it rag_application python main.py --check
```

## 🎛️ Advanced Usage

### Model Configuration
The system automatically selects optimal models:
- **GPU Systems**: Gemma3 27B → Gemma2 27B → Gemma2 9B (fallback)
- **CPU Systems**: Gemma3 12B → Gemma2 9B → Gemma2 2B (fallback)

### Dynamic Source Retrieval
The system intelligently adjusts the number of sources based on query complexity:
- **Simple queries** (definitions): 3 sources
- **Normal queries**: 5 sources  
- **Complex queries** (comparisons, overviews): 8-12 sources
- **Maximum limit**: 15 sources

### Query Examples
```bash
# Simple definition query (uses ~3 sources)
"What is moksha?"

# Complex comparative query (uses ~8-12 sources)
"Compare the concept of dharma across different Puranas and the Bhagavad Gita"

# Specific reference query (uses ~5 sources)
"What does Sai Baba say about meditation in the Vahinis?"
```

### Manual Source Control
```bash
# Set maximum sources in interactive mode
> sources 10

# Or specify in command line
docker exec -it rag_application python main.py --query "your question" --sources 8
```

## 🔧 Troubleshooting

### Common Issues

#### Services Not Starting
```bash
# Check Docker status
docker ps

# View logs
docker-compose -f docker-compose-adaptive.yml logs -f

# Restart services
docker-compose -f docker-compose-adaptive.yml down
./deploy.sh
```

#### Permission Issues After Remounting
```bash
# Fix permissions
./fix-permissions.sh
./deploy.sh
```

#### No Search Results
```bash
# Debug database contents
docker exec -it rag_application python main.py --debug

# Check if documents are ingested
docker exec -it rag_application python main.py --check
```

#### Model Loading Issues
The system includes automatic fallback:
1. Primary model fails → Secondary model
2. Secondary fails → Smallest available model
3. Provides clear error messages for debugging

### Maintenance Commands

```bash
# Daily restart after remounting external drive
wsl --mount \\.\PHYSICALDRIVE1 --partition 1 --type ext4
sudo mkdir /mnt/ragdisk
sudo mount -t ext4 /dev/sdd1 /mnt/ragdisk
cd /mnt/ragdisk/RAG_SYSTEM
./fix-permissions.sh
./deploy.sh

# Stop system
docker-compose -f docker-compose-adaptive.yml down

# Clean restart
docker-compose -f docker-compose-adaptive.yml down
docker system prune -f
./deploy.sh

# Update models
docker exec -it rag_ollama ollama pull gemma3:latest
```

## 📊 System Requirements

### Minimum Requirements
- **RAM**: 8GB (CPU mode)
- **Storage**: 20GB free space
- **CPU**: Multi-core processor (4+ cores recommended)

### Recommended Requirements
- **RAM**: 16GB+ (GPU mode)
- **GPU**: NVIDIA GPU with 8GB+ VRAM
- **Storage**: 50GB+ (for large document collections)
- **CPU**: 8+ cores for optimal parallel processing

## 🔍 Technical Details

### Document Processing Pipeline
1. **PDF Loading**: PyPDFLoader extracts text and metadata
2. **Text Chunking**: RecursiveCharacterTextSplitter (1000 chars, 200 overlap)
3. **Embedding**: Sentence-BERT (all-MiniLM-L6-v2)
4. **Storage**: Weaviate vector database with metadata
5. **Retrieval**: Hybrid vector + keyword search with similarity filtering

### AI Model Pipeline
1. **Query Analysis**: Complexity scoring determines source count
2. **Vector Search**: Embedding-based similarity matching
3. **Context Assembly**: Organized by source category
4. **Generation**: Ollama with adaptive model selection
5. **Response**: Structured answer with source attribution

### Vector Database Schema
```json
{
  "class": "SpiritualText",
  "properties": [
    {"name": "content", "dataType": ["text"]},
    {"name": "source", "dataType": ["string"]},
    {"name": "page", "dataType": ["int"]},
    {"name": "category", "dataType": ["string"]}
  ]
}
```

## 🤝 Contributing

### Adding New Document Categories
1. Update `categorize_document()` in `main.py`
2. Add keywords for automatic categorization
3. Test with sample documents

### Model Integration
1. Update `detect_optimal_model()` for new models
2. Add fallback chains in `query_ollama()`
3. Test performance across different hardware

### OCR Enhancement
1. Modify OCR batch script for new document types
2. Adjust quality settings for different scan qualities
3. Add language support for non-English texts

## 📜 License

This project is designed for educational and personal spiritual study. Please respect copyright laws when using religious and spiritual texts.

## 🙏 Acknowledgments

- **Weaviate**: Vector database technology
- **Ollama**: Local LLM serving
- **LangChain**: Document processing framework
- **Tesseract**: OCR capabilities
- **HuggingFace**: Embedding models

---

*"The goal is not to see the light, but to be the light."* - Spiritual wisdom for the digital age.
