# SmartBite Refactoring Guide - Phase 1

## Status: Foundation Created ✅

This document tracks the refactoring progress from monolithic `app.py` to modular architecture.

## Completed Steps

1. ✅ Created folder structure
2. ✅ Created `__init__.py` files
3. ✅ Created `utils/config.py` - Configuration module
4. 🔄 In Progress: CSS extraction and module creation

## Next Steps

### 1. Extract CSS (Priority: HIGH)
- Extract CSS from `app.py` lines 667-1413 to `frontend/styles/styles.css`
- Create utility function to load CSS in Streamlit

### 2. Create Data Layer Modules
- `backend/data/loader.py` - Extract `load_data()`, `load_raw_dataset()`, normalization
- `backend/data/filters.py` - Extract `apply_filters()`, `get_unique_restaurants()`, `get_restaurant_history()`

### 3. Create Domain Modules  
- `backend/domain/risk_scoring.py` - Extract risk calculation functions
- `backend/domain/forecasting.py` - Extract forecasting logic
- `backend/domain/neighbor_analysis.py` - Extract haversine and neighbor logic
- `backend/domain/features.py` - Extract feature engineering functions

### 4. Create RAG Modules
- `backend/rag/ingest.py` - Extract `build_rag()` and chunking logic
- `backend/rag/retriever.py` - Extract `kb_search()` functions

### 5. Create LLM Modules
- `backend/llm/client.py` - Extract `call_llm()` and caching
- `backend/llm/prompts.py` - Extract all prompt builders
- `backend/llm/agent_orchestrator.py` - Placeholder for Phase 5

### 6. Create Service Modules
- `backend/services/facility_profile.py` - Profile assembly logic
- `backend/services/inspection_advisor.py` - AI advisor logic
- `backend/services/risk_forecast.py` - Risk forecast orchestrator
- `backend/services/safety_intel.py` - Neighbor intelligence

### 7. Create Frontend Pages
- `frontend/pages/facility_profile.py`
- `frontend/pages/inspection_advisor.py`
- `frontend/pages/risk_forecasting.py`
- `frontend/pages/safety_intel.py`

### 8. Refactor app.py
- Make it a thin controller
- Import all modules
- Handle navigation only

## Function Mapping Reference

See `FUNCTION_MAPPING.md` (to be created) for detailed mapping of functions from `app.py` to new modules.

## Testing Strategy

After each module extraction:
1. Update imports in `app.py`
2. Test that functionality still works
3. Run linting checks
4. Commit progress

