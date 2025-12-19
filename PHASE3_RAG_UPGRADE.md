# Phase 3: Enterprise RAG Upgrade

## Overview

This document describes the enterprise RAG (Retrieval-Augmented Generation) system upgrade implemented for SmartBite. The new system provides:

1. **Clean KB Document Processing** - Structured JSONL output with metadata extraction
2. **Improved RAG Index** - Enhanced ingestion with better metadata support
3. **Advanced Retrieval** - Hybrid search, metadata filtering, semantic reranking, and TTL caching
4. **Service Integration** - RAG integrated into inspection advisor and facility profile services

## Architecture

### 1. KB Document Cleaner (`scripts/kb_cleaner.py`)

**Purpose:** Preprocess KB documents to extract structured metadata.

**Features:**
- Reads `.txt`, `.md`, and `.pdf` files from `kb/` directory
- Extracts article numbers (e.g., "Article 81")
- Extracts violation codes (e.g., "04L", "02A")
- Categorizes content (pest, hygiene, temperature, equipment, storage, cleaning, documentation)
- Splits documents into semantic sections
- Outputs structured JSONL files to `kb_clean/`

**Usage:**
```bash
# Process all KB files
python scripts/kb_cleaner.py

# Process single file
python scripts/kb_cleaner.py --file kb/article81_cleaning.md.txt

# Custom directories
python scripts/kb_cleaner.py --kb_dir kb --output_dir kb_clean
```

**Output Format:**
Each line in the JSONL file is a JSON object:
```json
{
  "chunk_id": "article81_cleaning_section_0",
  "text": "Full text content...",
  "header": "Cleaning Requirements",
  "article": "Article 81",
  "violation_code": "08A, 10F",
  "violation_codes": ["08A", "10F"],
  "category": "cleaning",
  "source_file": "article81_cleaning.md.txt",
  "section_index": 0
}
```

### 2. RAG Ingestion (`backend/rag/ingest.py`)

**Purpose:** Build and maintain the ChromaDB knowledge base index.

**Features:**
- Loads cleaned JSONL files from `kb_clean/`
- Falls back to legacy `.txt/.md` files if JSONL not available
- Incremental updates (only rebuilds when files change)
- Metadata extraction (article, violation codes, categories)
- Violation risk scoring
- Persistent ChromaDB storage

**Key Functions:**
- `build_rag(jsonl_dir, use_legacy_files, force_rebuild)` - Main ingestion function
- `get_chroma_client()` - Get cached ChromaDB client
- `get_embedding_model()` - Get cached SentenceTransformer model
- `load_cleaned_jsonl(jsonl_path)` - Load JSONL chunks

**Usage:**
```python
from backend.rag.ingest import build_rag

# Build RAG index from cleaned JSONL files
collection = build_rag(jsonl_dir="kb_clean", use_legacy_files=True)

# Force rebuild
collection = build_rag(force_rebuild=True)
```

### 3. RAG Retrieval (`backend/rag/retriever.py`)

**Purpose:** Advanced retrieval with hybrid search, filtering, and reranking.

**Features:**
- **Hybrid Search:** Query expansion with synonyms and related terms
- **Metadata Filtering:** Filter by category or violation code
- **Semantic Reranking:** Score-based reranking with metadata boosting
- **TTL Caching:** 6-hour cache with automatic expiration
- **Violation-Specific Retrieval:** `get_policy_for_violation(code)`
- **Category Best Practices:** `get_best_practices_for_category(category)`

**Key Functions:**
- `kb_search(query, k, collection, category_filter, violation_code_filter, use_reranking, use_hybrid_search)` - Main search function
- `get_policy_for_violation(violation_code, collection, k)` - Get policies for specific violation
- `get_best_practices_for_category(category, collection, k)` - Get best practices by category
- `clear_cache()` - Clear search cache
- `get_cache_stats()` - Get cache statistics

**Usage:**
```python
from backend.rag.retriever import kb_search, get_policy_for_violation, get_best_practices_for_category

# Basic search
results = kb_search("pest control", k=5, collection=collection)

# Filter by category
results = kb_search(
    "temperature control",
    k=5,
    collection=collection,
    category_filter="temperature"
)

# Get policy for specific violation
policies = get_policy_for_violation("04L", collection=collection, k=3)

# Get best practices for category
practices = get_best_practices_for_category("hygiene", collection=collection, k=5)
```

**Query Expansion:**
The system automatically expands queries with related terms:
- **Pest queries** → "pest control, vermin activity, mice, rats, roaches, rodents"
- **Temperature queries** → "food temperature control, hot holding, cold holding, cooling rules, reheating"
- **Hygiene queries** → "handwashing sinks, soap, paper towels, bare-hand contact, sanitization"

**Reranking:**
Results are reranked based on:
- ChromaDB similarity distance (converted to similarity score)
- Violation risk score (from metadata)
- Category match (boosts matching categories)
- Violation code match (boosts matching codes)

### 4. Service Integration

#### Inspection Advisor Service (`backend/services/inspection_advisor.py`)

**New Functions:**
- `get_rag_context_for_question(question, hist, kb_collection, k)` - Get comprehensive RAG context
  - Returns policy chunks, best practices, and violation-specific policies
- `format_rag_context_for_prompt(rag_context)` - Format RAG context for LLM prompts

**Usage:**
```python
from backend.services.inspection_advisor import get_rag_context_for_question, format_rag_context_for_prompt

# Get RAG context for a question
rag_context = get_rag_context_for_question(
    question="How do I prevent pest infestations?",
    hist=restaurant_history,
    kb_collection=collection,
    k=3
)

# Format for prompt
formatted_context = format_rag_context_for_prompt(rag_context)
```

#### Facility Profile Service (`backend/services/facility_profile.py`)

**Enhancements:**
- `build_facility_profile()` now accepts `kb_collection` parameter
- Automatically detects problem categories from violations
- Retrieves relevant best practices and violation policies
- Adds `rag_recommendations` to profile output

**Usage:**
```python
from backend.services.facility_profile import build_facility_profile

# Build profile with RAG recommendations
profile = build_facility_profile(
    hist=restaurant_history,
    restaurant_name="My Restaurant",
    kb_collection=collection
)

# Access RAG recommendations
rag_recs = profile.get("rag_recommendations", {})
category_recs = rag_recs.get("category_recommendations", [])
violation_policies = rag_recs.get("violation_policies", [])
```

## Workflow

### Step 1: Clean KB Documents
```bash
python scripts/kb_cleaner.py
```
This creates structured JSONL files in `kb_clean/` directory.

### Step 2: Build RAG Index
```python
from backend.rag.ingest import build_rag

collection = build_rag(jsonl_dir="kb_clean")
```

### Step 3: Use in Services
```python
from backend.rag.retriever import kb_search
from backend.services.inspection_advisor import get_rag_context_for_question

# In your application code
rag_context = get_rag_context_for_question(
    question=user_question,
    hist=restaurant_history,
    kb_collection=collection
)
```

## Configuration

Configuration is managed in `utils/config.py`:

- `KB_FOLDER` - KB source directory (default: "kb")
- `CHROMA_DB_PATH` - ChromaDB storage path (default: "chroma_db")
- `RAG_COLLECTION_NAME` - Collection name (default: "nyc_inspections_kb")
- `EMBEDDING_MODEL_NAME` - SentenceTransformer model (default: "all-MiniLM-L6-v2")
- `MAX_CACHE_SIZE` - Maximum cache entries (default: 100)
- `CHUNK_SIZE` - Text chunk size (default: 1600)
- `CHUNK_OVERLAP` - Chunk overlap (default: 200)

## Performance Optimizations

1. **Caching:**
   - Embedding model cached globally
   - ChromaDB client cached
   - Search results cached with 6-hour TTL

2. **Incremental Updates:**
   - Only rebuilds index when files change
   - Uses file hashes to detect changes

3. **Query Optimization:**
   - Hybrid search fetches more results for reranking
   - Metadata filtering reduces search space
   - Result limiting (top-k) prevents over-processing

## Error Handling

- Graceful fallback to legacy files if JSONL not found
- Empty results if collection is None
- Logging for debugging and monitoring
- Exception handling prevents crashes

## Future Enhancements

- Cross-encoder reranking (currently metadata-based)
- Multi-vector search (separate embeddings for titles/headers)
- Document versioning and history
- User feedback loop for result relevance
- Analytics dashboard for RAG performance

## Testing

To test the RAG system:

```python
# Test KB cleaner
python scripts/kb_cleaner.py --file kb/article81_cleaning.md.txt

# Test ingestion
from backend.rag.ingest import build_rag
collection = build_rag(force_rebuild=True)
print(f"Indexed {collection.count()} documents")

# Test retrieval
from backend.rag.retriever import kb_search
results = kb_search("pest control", k=3, collection=collection)
for r in results:
    print(f"Source: {r['source']}\n{r['text'][:200]}...\n")
```

## Notes

- PDF support requires `pypdf` package (optional)
- Cross-encoder reranking requires `sentence-transformers` with cross-encoder models (optional)
- ChromaDB is persistent - data survives application restarts
- Cache is in-memory and resets on application restart

