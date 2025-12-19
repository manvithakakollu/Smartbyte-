# Phase 5: Multi-Agent Intelligence System

## Overview

Deterministic multi-agent pipeline for the AI Inspection Advisor that routes queries, aggregates data, retrieves policies, and generates structured advisory responses.

## Architecture

The system consists of 5 main components:

1. **RouterAgent** - Classifies user queries into intent types
2. **DataAggregatorAgent** - Fetches and unifies data from various sources
3. **PolicyRAGAgent** - Retrieves relevant knowledge base documents
4. **AdvisoryAgent** - Generates structured advisory responses
5. **AgentOrchestrator** - Coordinates all agents in the pipeline

## Agent Details

### 1. RouterAgent

**Purpose:** Classify user queries into specific intent types.

**Query Types:**
- `GRADE_FORECAST` - Questions about future grades, scores, predictions
- `RISK_EXPLANATION` - Questions about risks, problems, concerns
- `SOP_REQUEST` - Questions about procedures, how-to, processes
- `CHECKLIST_REQUEST` - Questions asking for lists, checklists, action items
- `VIOLATION_EXPLANATION` - Questions about specific violations
- `SYSTEM_META` - Questions about the system itself, capabilities, help
- `GENERAL_ADVICE` - General restaurant inspection advice

**Methods:**
- `classify(query)` - Keyword-based classification (fast)
- `classify_with_llm(query)` - LLM-based classification (more accurate)

**Example:**
```python
router = RouterAgent()
query_type = router.classify("What grade will I get next?")
# Returns: QueryType.GRADE_FORECAST
```

### 2. DataAggregatorAgent

**Purpose:** Aggregate all relevant data for a restaurant.

**Data Sources:**
- Restaurant inspection history
- ML predictions (if available)
- Violation clusters
- Trend analysis
- Grade probabilities

**Output Structure:**
```json
{
  "restaurant_name": "...",
  "current_state": {
    "grade": "A|B|C",
    "score": number,
    "risk_level": "Low|Medium|High",
    "total_inspections": number,
    "latest_inspection_date": "YYYY-MM-DD"
  },
  "trend_analysis": {
    "direction": "improving|worsening|stable",
    "velocity": number,
    "trend": "...",
    "predicted_next_score": number
  },
  "grade_probabilities": {
    "A": percentage,
    "B": percentage,
    "C": percentage
  },
  "violation_clusters": {
    "pest": {...},
    "temperature": {...},
    ...
  },
  "top_violations": [...],
  "recent_violations": [...]
}
```

**Methods:**
- `aggregate(restaurant_name, hist, kb_collection)` - Main aggregation method
- `_cluster_violations(hist)` - Cluster violations by category
- `_get_top_violations(hist)` - Get top violations by frequency
- `_get_recent_violations(hist, n)` - Get recent violations

### 3. PolicyRAGAgent

**Purpose:** Retrieve relevant knowledge base documents.

**Retrieval Types:**
- General policy chunks (semantic search)
- Category-specific best practices
- SOP templates (for procedure requests)
- Violation-specific policies

**Output Structure:**
```json
{
  "policy_chunks": [
    {"text": "...", "source": "...", "metadata": {...}}
  ],
  "best_practices": [
    {"text": "...", "category": "...", "metadata": {...}}
  ],
  "sop_templates": [...],
  "violation_policies": [...]
}
```

**Methods:**
- `retrieve(query, query_type, violation_clusters, kb_collection)` - Main retrieval method
- `_extract_violation_codes(query)` - Extract violation codes from query
- `_deduplicate(items)` - Remove duplicate items

### 4. AdvisoryAgent

**Purpose:** Generate structured advisory responses based on full context.

**Response Types:**

**Grade Forecast:**
```json
{
  "grade_prediction": {
    "most_likely": "A|B|C",
    "confidence": "high|medium|low",
    "probability_A": 0-100,
    "probability_B": 0-100,
    "probability_C": 0-100,
    "predicted_score": number,
    "reasoning": "..."
  },
  "inspection_forecast": {
    "days_until_next": number,
    "expected_date": "YYYY-MM-DD",
    "risk_factors": [...]
  },
  "narrative": "..."
}
```

**Risk Explanation:**
```json
{
  "risks": [
    {
      "category": "pest|temperature|...",
      "severity": "high|medium|low",
      "description": "...",
      "impact": "..."
    }
  ],
  "actions": [
    {
      "priority": "high|medium|low",
      "action": "...",
      "timeframe": "..."
    }
  ],
  "narrative": "..."
}
```

**SOP Request:**
```json
{
  "sop": {
    "title": "...",
    "steps": [...],
    "requirements": [...],
    "compliance_notes": "..."
  },
  "checklist": [...],
  "narrative": "..."
}
```

**Checklist:**
```json
{
  "checklist": [
    {
      "item": "...",
      "category": "...",
      "priority": "high|medium|low",
      "notes": "..."
    }
  ],
  "timeframe": "...",
  "narrative": "..."
}
```

**Methods:**
- `advise(query, query_type, data_context, rag_context, restaurant_name, hist)` - Main advisory method
- `_generate_grade_forecast(...)` - Generate grade forecast response
- `_generate_risk_explanation(...)` - Generate risk explanation
- `_generate_sop_response(...)` - Generate SOP response
- `_generate_checklist(...)` - Generate checklist
- `_generate_violation_explanation(...)` - Generate violation explanation
- `_generate_general_advice(...)` - Generate general advice

### 5. AgentOrchestrator

**Purpose:** Coordinate all agents in the pipeline.

**Pipeline Flow:**
1. **Route** - Classify query type
2. **Aggregate** - Gather all relevant data
3. **Retrieve** - Get RAG documents
4. **Advise** - Generate structured response

**Methods:**
- `run(query, restaurant_name, hist)` - Execute complete pipeline

**Example:**
```python
orchestrator = AgentOrchestrator(kb_collection=collection)
response = orchestrator.run(
    query="What grade will I get next?",
    restaurant_name="My Restaurant",
    hist=inspection_history
)

print(response["grade_prediction"])
print(response["narrative"])
```

## Usage

### Basic Usage

```python
from backend.llm.agent_orchestrator import AgentOrchestrator
from backend.rag.ingest import build_rag
import pandas as pd

# Initialize
kb_collection = build_rag()
orchestrator = AgentOrchestrator(kb_collection=kb_collection)

# Run query
hist = get_restaurant_history(df, "Restaurant Name")
response = orchestrator.run(
    query="How do I prevent pest violations?",
    restaurant_name="Restaurant Name",
    hist=hist
)

# Access structured response
print(response["narrative"])
if "risks" in response:
    for risk in response["risks"]:
        print(f"{risk['category']}: {risk['description']}")
```

### Individual Agent Usage

```python
from backend.llm.agent_orchestrator import RouterAgent, DataAggregatorAgent

# Use router separately
router = RouterAgent()
query_type = router.classify("What should I do in the next 7 days?")

# Use data aggregator separately
aggregator = DataAggregatorAgent()
context = aggregator.aggregate("Restaurant", hist, kb_collection)
```

## Integration

### With Existing Services

The orchestrator can be integrated into the existing inspection advisor:

```python
from backend.llm.agent_orchestrator import AgentOrchestrator

def run_smartbite_answer_with_agents(
    query: str,
    restaurant_name: str,
    hist: pd.DataFrame,
    kb_collection
):
    orchestrator = AgentOrchestrator(kb_collection=kb_collection)
    response = orchestrator.run(query, restaurant_name, hist)
    
    # Format for existing UI
    return format_agent_response(response)

def format_agent_response(response: Dict) -> Tuple[str, Dict]:
    """Format agent response for existing UI components."""
    query_type = response.get("metadata", {}).get("query_type", "general")
    
    if query_type == "grade_forecast":
        return ("grade_forecast", response.get("grade_prediction", {}))
    elif query_type == "risk_explanation":
        return ("risk_explanation", response)
    else:
        return ("general", response)
```

## Error Handling

All agents include error handling:
- Router falls back to keyword matching if LLM fails
- Data aggregator returns empty structures if data unavailable
- Policy RAG gracefully handles missing collection
- Advisory agent has JSON parsing fallbacks

## Performance

- **Router**: ~50ms (keyword) or ~200ms (LLM)
- **Data Aggregator**: ~100-300ms (depending on data size)
- **Policy RAG**: ~200-500ms (depending on collection size)
- **Advisory**: ~500-2000ms (LLM response time)
- **Total Pipeline**: ~1-3 seconds typical

## Future Enhancements

- [ ] Caching of agent outputs
- [ ] Parallel execution where possible
- [ ] Confidence scoring for routing
- [ ] Multi-turn conversation support
- [ ] Agent-specific fine-tuning
- [ ] Performance monitoring and analytics

