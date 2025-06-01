#!/usr/bin/env python3
"""
Portable RAG System for Spiritual Texts - Enhanced with Debugging
Supports PDFs containing Puranas, Bhagavad Gita, Mahabharata, Sastras, and Sai Baba's works
Enhanced with dynamic source retrieval and intelligent context management
FIXED: Weaviate batch insertion compatibility
"""

import os
import sys
import argparse
from pathlib import Path
import weaviate
import requests
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Weaviate
from tqdm import tqdm
import json
import time

class RAGSystem:
    def __init__(self):
        self.weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8080')
        self.ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.data_path = Path('/app/data')
        
        # Initialize Weaviate client
        self.weaviate_client = weaviate.Client(url=self.weaviate_url)
        
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            cache_folder="/app/models"
        )
        
        # Text splitter for chunking documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # Auto-detect optimal model based on hardware
        self.optimal_model = self.detect_optimal_model()
        
        # Dynamic retrieval settings
        self.default_limit = 5  # Default number of sources
        self.max_limit = 15     # Maximum sources to prevent overwhelming context
        self.similarity_threshold = 0.3  # LOWERED - was 0.7, now more permissive
        
    def detect_optimal_model(self):
        """Detect GPU availability and choose optimal model"""
        try:
            # Check if we're running with GPU support by looking at nvidia-smi
            import subprocess
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
            
            if result.returncode == 0:
                # GPU detected
                vram_info = result.stdout
                if 'MiB' in vram_info:
                    print("🎮 GPU detected! Using Gemma3 27B model for better performance.")
                    return "gemma3:27b"
            
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        # No GPU detected, use CPU model
        print("💻 CPU-only mode detected. Using Gemma3 9B model for CPU.")
        return "gemma3:12b"
    
    def ensure_model_available(self):
        """Ensure the optimal model is pulled and available"""
        try:
            # Check what models are available
            response = requests.get(f"{self.ollama_url}/api/tags")
            if response.status_code == 200:
                available_models = [model['name'] for model in response.json().get('models', [])]
                
                if self.optimal_model not in available_models:
                    print(f"📥 Pulling {self.optimal_model} model...")
                    pull_response = requests.post(
                        f"{self.ollama_url}/api/pull",
                        json={"name": self.optimal_model}
                    )
                    
                    if pull_response.status_code == 200:
                        print(f"✅ Successfully pulled {self.optimal_model}")
                    else:
                        print(f"❌ Failed to pull {self.optimal_model}, falling back to smaller model")
                        self.optimal_model = "gemma2:2b"  # Fallback to available smaller model
                else:
                    print(f"✅ Model {self.optimal_model} is already available")
            
        except Exception as e:
            print(f"⚠️ Model check failed: {e}. Using fallback model.")
            self.optimal_model = "gemma2:2b"  # Use available model as fallback
    
    def check_services(self):
        """Check if required services are running"""
        try:
            # Check Weaviate
            print("🔍 Checking Weaviate...")
            response = requests.get(f"{self.weaviate_url}/v1/meta")
            if response.status_code != 200:
                print("❌ Weaviate is not accessible")
                return False
                
            # Check Ollama
            print("🔍 Checking Ollama...")
            response = requests.get(f"{self.ollama_url}/api/tags")
            if response.status_code != 200:
                print("❌ Ollama is not accessible")
                return False
                
            print("✅ All services are running")
            
            # Ensure optimal model is available
            self.ensure_model_available()
            return True
            
        except Exception as e:
            print(f"❌ Service check failed: {e}")
            return False
    
    def debug_weaviate_data(self):
        """Debug function to check what's in Weaviate"""
        try:
            # Check if class exists
            schema = self.weaviate_client.schema.get()
            classes = [cls['class'] for cls in schema.get('classes', [])]
            print(f"🔍 Available classes: {classes}")
            
            if 'SpiritualText' not in classes:
                print("❌ SpiritualText class does not exist!")
                return False
            
            # Count total objects
            result = (
                self.weaviate_client.query
                .aggregate("SpiritualText")
                .with_meta_count()
                .do()
            )
            
            count = result['data']['Aggregate']['SpiritualText'][0]['meta']['count']
            print(f"📊 Total documents in database: {count}")
            
            if count == 0:
                print("❌ No documents found in database! Run ingestion first.")
                return False
            
            # Get a few sample documents
            sample_result = (
                self.weaviate_client.query
                .get("SpiritualText", ["content", "source", "page", "category"])
                .with_limit(3)
                .do()
            )
            
            sample_docs = sample_result["data"]["Get"]["SpiritualText"]
            #print(f"📋 Sample documents:")
            #for i, doc in enumerate(sample_docs):
            #    print(f"  {i+1}. Source: {doc['source']}, Page: {doc['page']}, Category: {doc['category']}")
            #    print(f"     Content preview: {doc['content'][:100]}...")
            
            return True
            
        except Exception as e:
            print(f"❌ Debug error: {e}")
            return False
    
    def create_schema(self):
        """Create Weaviate schema for spiritual texts"""
        schema = {
            "class": "SpiritualText",
            "description": "Texts on Indian Culture and Spirituality",
            "properties": [
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "The text content"
                },
                {
                    "name": "source",
                    "dataType": ["string"],
                    "description": "Source document name"
                },
                {
                    "name": "page",
                    "dataType": ["int"],
                    "description": "Page number"
                },
                {
                    "name": "category",
                    "dataType": ["string"],
                    "description": "Category: Purana, Gita, Sastra, SaiBaba, etc."
                }
            ],
            # Add vectorizer configuration
            "vectorizer": "none",  # We'll provide our own vectors
            "moduleConfig": {}
        }
        
        try:
            # Delete existing class if it exists
            if self.weaviate_client.schema.exists("SpiritualText"):
                print("🗑️ Deleting existing schema...")
                self.weaviate_client.schema.delete_class("SpiritualText")
            
            # Create new class
            self.weaviate_client.schema.create_class(schema)
            print("✅ Schema created successfully")
            
        except Exception as e:
            print(f"❌ Schema creation failed: {e}")
            raise
    
    def categorize_document(self, filename):
        """Categorize document based on filename"""
        filename_lower = filename.lower()
        
        if any(word in filename_lower for word in ['purana', 'bhagavata', 'vishnu', 'shiva', 'devi']):
            return "Purana"
        elif any(word in filename_lower for word in ['gita', 'bhagavad']):
            return "Gita"
        elif any(word in filename_lower for word in ['mahabharata', 'mahabharat']):
            return "Mahabharata"
        elif any(word in filename_lower for word in ['sastra', 'shastra', 'artha', 'kama', 'dharma']):
            return "Sastra"
        elif any(word in filename_lower for word in ['sai', 'baba', 'vahini', 'sathya', 'sathyam', 'shivam', 'sundaram']):
            return "SaiBaba"
        else:
            return "Spiritual"
    
    def ingest_documents(self):
        """Ingest all PDFs from the data directory with fixed batch insertion"""
        if not self.data_path.exists():
            print(f"❌ Data directory not found: {self.data_path}")
            return
        
        pdf_files = list(self.data_path.glob("*.pdf"))
        if not pdf_files:
            print("❌ No PDF files found in data directory")
            return
        
        print(f"📚 Found {len(pdf_files)} PDF files to process")
        
        # Create schema
        self.create_schema()
        
        total_chunks = 0
        
        for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
            try:
                print(f"\n📖 Processing: {pdf_file.name}")
                
                # Load PDF
                loader = PyPDFLoader(str(pdf_file))
                pages = loader.load()
                print(f"   Loaded {len(pages)} pages")
                
                # Split into chunks
                chunks = self.text_splitter.split_documents(pages)
                print(f"   Created {len(chunks)} chunks")
                
                # Categorize document
                category = self.categorize_document(pdf_file.name)
                print(f"   Category: {category}")
                
                # Process chunks in batches for better performance
                batch_size = 50
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    
                    # Use the correct batch context manager approach
                    try:
                        with self.weaviate_client.batch as batch_client:
                            # Configure batch settings
                            batch_client.batch_size = len(batch)
                            batch_client.dynamic = True
                            batch_client.creation_time = 10
                            batch_client.timeout_retries = 3
                            
                            for chunk in batch:
                                try:
                                    # Create embedding
                                    embedding = self.embeddings.embed_query(chunk.page_content)
                                    
                                    # Add object to batch
                                    batch_client.add_data_object(
                                        data_object={
                                            "content": chunk.page_content,
                                            "source": pdf_file.name,
                                            "page": chunk.metadata.get('page', 0),
                                            "category": category
                                        },
                                        class_name="SpiritualText",
                                        vector=embedding
                                    )
                                    
                                except Exception as e:
                                    print(f"   ⚠️ Error processing chunk: {e}")
                                    continue
                        
                        print(f"   ✅ Inserted batch of {len(batch)} chunks")
                        
                    except Exception as e:
                        print(f"   ❌ Batch insert failed: {e}")
                        print("   🔄 Falling back to individual inserts...")
                        
                        # Fall back to individual inserts
                        success_count = 0
                        for chunk in batch:
                            try:
                                # Create embedding
                                embedding = self.embeddings.embed_query(chunk.page_content)
                                
                                # Individual insert
                                self.weaviate_client.data_object.create(
                                    data_object={
                                        "content": chunk.page_content,
                                        "source": pdf_file.name,
                                        "page": chunk.metadata.get('page', 0),
                                        "category": category
                                    },
                                    class_name="SpiritualText",
                                    vector=embedding
                                )
                                success_count += 1
                                
                            except Exception as e2:
                                print(f"   ❌ Individual insert failed: {e2}")
                        
                        print(f"   ✅ Individual inserts: {success_count}/{len(batch)} successful")
                
                total_chunks += len(chunks)
                print(f"✅ Completed {pdf_file.name}: {len(chunks)} chunks total")
                
            except Exception as e:
                print(f"❌ Error processing {pdf_file.name}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n🎉 Ingestion complete! Total chunks: {total_chunks}")
        
        # Verify ingestion
        self.debug_weaviate_data()
    
    def determine_search_complexity(self, query):
        """Determine how many sources to retrieve based on query complexity"""
        query_lower = query.lower()
        
        # Complex topics that need many sources
        complex_keywords = [
            'compare', 'comparison', 'different', 'various', 'all', 'complete',
            'comprehensive', 'detailed', 'explain', 'describe', 'overview',
            'history', 'evolution', 'development', 'significance', 'importance',
            'relationship', 'connection', 'between', 'among', 'multiple'
        ]
        
        # Specific topics that might need fewer sources
        specific_keywords = [
            'what is', 'who is', 'when', 'where', 'definition', 'meaning',
            'quote', 'verse', 'chapter', 'specific', 'particular'
        ]
        
        # Broad philosophical topics
        broad_keywords = [
            'dharma', 'karma', 'moksha', 'liberation', 'enlightenment',
            'consciousness', 'divine', 'god', 'brahman', 'atman', 'soul',
            'meditation', 'yoga', 'devotion', 'bhakti', 'wisdom', 'knowledge'
        ]
        
        complexity_score = 0
        
        # Check for complex keywords
        for keyword in complex_keywords:
            if keyword in query_lower:
                complexity_score += 2
        
        # Check for broad keywords
        for keyword in broad_keywords:
            if keyword in query_lower:
                complexity_score += 1
        
        # Check for specific keywords (reduces complexity)
        for keyword in specific_keywords:
            if keyword in query_lower:
                complexity_score -= 1
        
        # Determine number of sources based on complexity
        if complexity_score >= 4:
            return min(self.max_limit, 12)  # Very complex - up to 12 sources
        elif complexity_score >= 2:
            return min(self.max_limit, 8)   # Moderately complex - up to 8 sources
        elif complexity_score >= 0:
            return self.default_limit       # Normal - 5 sources
        else:
            return 3                        # Simple/specific - 3 sources
    
    def query_ollama(self, prompt, model=None):
        """Query Ollama model with better error handling"""
        # Use optimal model if none specified
        if model is None:
            model = self.optimal_model
            
        try:
            print(f"🤖 Using model: {model}")
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "max_tokens": 4096  # Increased for longer responses with more sources
                    }
                },
                timeout=180  # 3 minute timeout for complex queries
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "No response generated")
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"
                
                print(f"❌ Ollama error: {error_msg}")
                
                # Try fallback model if main model fails
                if model == "gemma3:27b":
                    print("🔄 Gemma3 27B failed, trying Gemma3 12B...")
                    return self.query_ollama(prompt, "gemma3:12b")
                elif model == "gemma3:12b":
                    print("🔄 Gemma3 12B failed, trying Gemma2 2B...")
                    return self.query_ollama(prompt, "gemma2:2b")
                else:
                    # Final fallback failed
                    return f"All models failed. Error: {error_msg}"
                
                return f"Error querying Ollama: {error_msg}"
                
        except requests.exceptions.Timeout:
            print("⏰ Request timed out. The model might be processing a complex query.")
            return "Request timed out. Please try a simpler question or check if the model is loaded."
        except Exception as e:
            print(f"❌ Exception querying Ollama: {e}")
            return f"Error querying Ollama: {e}"
    
    def search_documents(self, query, limit=None, min_similarity=None):
        """Search for relevant documents with dynamic limits and enhanced debugging"""
        try:
            # Use dynamic limit if not specified
            if limit is None:
                limit = self.determine_search_complexity(query)
            
            if min_similarity is None:
                min_similarity = self.similarity_threshold
            
            print(f"🔍 Searching for {limit} sources (complexity-based)")
            print(f"🎯 Minimum similarity threshold: {min_similarity}")
            
            # First, check if we have any data
            if not self.debug_weaviate_data():
                return []
            
            # Create query embedding
            print("🧮 Creating query embedding...")
            query_embedding = self.embeddings.embed_query(query)
            print(f"   Embedding dimension: {len(query_embedding)}")
            
            # Search in Weaviate with higher limit to filter later
            search_limit = limit * 3  # Get more results to filter
            print(f"📋 Searching with limit {search_limit} (will filter to {limit})")
            
            result = (
                self.weaviate_client.query
                .get("SpiritualText", ["content", "source", "page", "category"])
                .with_near_vector({"vector": query_embedding})
                .with_limit(search_limit)
                .with_additional(["distance", "certainty"])  # Get both metrics
                .do()
            )
            
            print(f"🔍 Raw search result structure: {result.keys()}")
            
            if "data" not in result or "Get" not in result["data"] or "SpiritualText" not in result["data"]["Get"]:
                print(f"❌ Unexpected result structure: {result}")
                return []
            
            documents = result["data"]["Get"]["SpiritualText"]
            print(f"📊 Found {len(documents)} initial results")
            
            if not documents:
                print("❌ No documents returned from search")
                # Try a broader search without vector similarity
                print("🔄 Trying keyword-based fallback search...")
                fallback_result = (
                    self.weaviate_client.query
                    .get("SpiritualText", ["content", "source", "page", "category"])
                    .with_bm25(query=query)
                    .with_limit(limit)
                    .do()
                )
                
                if "data" in fallback_result and "Get" in fallback_result["data"]:
                    fallback_docs = fallback_result["data"]["Get"]["SpiritualText"]
                    print(f"📊 Fallback search found {len(fallback_docs)} results")
                    return fallback_docs[:limit]
                else:
                    return []
            
            # Filter by similarity and remove duplicates from same source/page
            filtered_docs = []
            seen_sources = set()
            
            print("🔍 Filtering results:")
            for i, doc in enumerate(documents):
                # Convert distance to similarity (lower distance = higher similarity)
                distance = doc["_additional"].get("distance", 1.0)
                certainty = doc["_additional"].get("certainty", 0.0)
                similarity = 1 - distance if distance is not None else certainty
                
                #print(f"  {i+1}. {doc['source']} (Page {doc['page']}) - Similarity: {similarity:.3f}, Distance: {distance:.3f}")
                
                # Create unique identifier for source+page
                source_key = f"{doc['source']}-{doc['page']}"
                
                # Include if similarity is high enough and not duplicate
                if similarity >= min_similarity and source_key not in seen_sources:
                    doc["similarity"] = similarity
                    filtered_docs.append(doc)
                    seen_sources.add(source_key)
                    #print(f"    ✅ Added to results")
                    
                    if len(filtered_docs) >= limit:
                        break
                else:
                    reason = "low similarity" if similarity < min_similarity else "duplicate source"
                    #print(f"    ❌ Filtered out ({reason})")
            
            # Sort by similarity (highest first)
            filtered_docs.sort(key=lambda x: x["similarity"], reverse=True)
            
            #print(f"✅ Returning {len(filtered_docs)} filtered results")
            return filtered_docs[:limit]
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def ask_question(self, question, max_sources=None):
        """Ask a question using RAG with dynamic source retrieval"""
        print(f"\n🔍 Analyzing question: {question}")
        
        # Check services first
        if not self.check_services():
            print("❌ Services are not available. Please check Docker containers.")
            return
        
        # Search for relevant documents
        relevant_docs = self.search_documents(question, limit=max_sources)
        
        if not relevant_docs:
            print("❌ No relevant documents found")
            # Try to answer without context
            print("🤔 Attempting to answer from general knowledge...")
            answer = self.query_ollama(f"Question: {question}\n\nPlease provide a helpful answer based on your knowledge of spiritual and religious texts.")
            print(f"\n💡 Answer:\n{answer}")
            return
        
        print(f"\n📊 Retrieved {len(relevant_docs)} relevant sources:")
        
        # Group sources by category for better organization
        sources_by_category = {}
        for doc in relevant_docs:
            category = doc['category']
            if category not in sources_by_category:
                sources_by_category[category] = []
            sources_by_category[category].append(doc)
        
        # Display sources grouped by category
        for category, docs in sources_by_category.items():
            print(f"\n📚 {category} sources:")
            for doc in docs:
                similarity_pct = round(doc.get("similarity", 0) * 100, 1)
                print(f"  • {doc['source']} (Page {doc['page']}) - {similarity_pct}% match")
        
        # Prepare context with better organization
        context_parts = []
        for category, docs in sources_by_category.items():
            context_parts.append(f"\n=== {category.upper()} SOURCES ===")
            for doc in docs:
                context_parts.append(f"\nFrom {doc['source']} (Page {doc['page']}):\n{doc['content']}")
        
        context = "\n".join(context_parts)
        
        # Create enhanced prompt
        prompt = f"""Based on the following spiritual texts from various sources, please provide a comprehensive answer to the question.

CONTEXT FROM SPIRITUAL TEXTS:
{context}

QUESTION: {question}

Please provide a detailed, well-structured answer that:
1. Synthesizes information from multiple sources when available
2. Notes any differences or variations between sources
3. Provides specific references to the texts when making claims
4. Acknowledges if certain aspects need more sources for complete coverage

If the provided context doesn't fully answer the question, please indicate what additional information would be helpful.

COMPREHENSIVE ANSWER:"""
        
        print(f"\n🤔 Generating comprehensive answer using {len(relevant_docs)} sources...")
        answer = self.query_ollama(prompt)
        print(f"\n💡 Answer:\n{answer}")

def main():
    parser = argparse.ArgumentParser(description="Portable RAG System for Spiritual Texts")
    parser.add_argument("--ingest", action="store_true", help="Ingest documents from data directory")
    parser.add_argument("--query", type=str, help="Ask a question")
    parser.add_argument("--sources", type=int, default=None, help="Maximum number of sources to retrieve (default: auto-detect)")
    parser.add_argument("--check", action="store_true", help="Check service status")
    parser.add_argument("--debug", action="store_true", help="Debug Weaviate data")
    
    args = parser.parse_args()
    
    rag = RAGSystem()
    
    if args.check:
        rag.check_services()
    elif args.debug:
        rag.debug_weaviate_data()
    elif args.ingest:
        if rag.check_services():
            rag.ingest_documents()
        else:
            print("❌ Cannot ingest documents - services are not available")
    elif args.query:
        rag.ask_question(args.query, max_sources=args.sources)
    else:
        # Interactive mode
        print("🕉️  Welcome to the Enhanced Spiritual Texts RAG System")
        print("Enhanced Features:")
        print("  • Dynamic source retrieval based on query complexity")
        print("  • Similarity-based filtering")
        print("  • Organized output by text category")
        print("  • Enhanced debugging capabilities")
        print("  • FIXED: Weaviate batch insertion compatibility")
        print("\nCommands:")
        print("  • Type 'quit' to exit")
        print("  • Type 'ingest' to process documents")
        print("  • Type 'debug' to check database contents")
        print("  • Type 'sources <number>' to set max sources (e.g., 'sources 10')")
        print("  • Ask any question for intelligent source retrieval")
        
        max_sources_override = None
        
        while True:
            try:
                user_input = input("\n> ").strip()
                
                if user_input.lower() == 'quit':
                    break
                elif user_input.lower() == 'ingest':
                    if rag.check_services():
                        rag.ingest_documents()
                    else:
                        print("❌ Cannot ingest documents - services are not available")
                elif user_input.lower() == 'check':
                    rag.check_services()
                elif user_input.lower() == 'debug':
                    rag.debug_weaviate_data()
                elif user_input.lower().startswith('sources '):
                    try:
                        num = int(user_input.split()[1])
                        if 1 <= num <= rag.max_limit:
                            max_sources_override = num
                            print(f"✅ Max sources set to {num}")
                        else:
                            print(f"❌ Sources must be between 1 and {rag.max_limit}")
                    except (IndexError, ValueError):
                        print("❌ Invalid format. Use: sources <number>")
                elif user_input:
                    rag.ask_question(user_input, max_sources=max_sources_override)
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break

if __name__ == "__main__":
    main()