# Phase 4: UI/UX Redesign

## Overview

Complete redesign of SmartBite's UI using a professional dark-themed design system with modern components, animations, and responsive layouts.

## Design System

### Design Tokens

**Colors:**
- `--sb-bg: #020617` - Primary background
- `--sb-bg-elevated: rgba(15, 23, 42, 0.92)` - Elevated surfaces
- `--sb-accent: #81D8D0` - Primary accent (Tiffany)
- `--sb-accent-alt: #6366F1` - Alternative accent (Indigo)
- `--sb-text-main: #F9FAFB` - Primary text
- `--sb-text-muted: #9CA3AF` - Muted text
- `--sb-border-subtle: rgba(148, 163, 184, 0.25)` - Subtle borders

**Spacing Scale:**
- 4px, 8px, 12px, 16px, 24px, 32px, 40px, 56px

**Typography:**
- Font: Inter (Google Fonts)
- Modular type scale: xs, sm, base, lg, xl, 2xl, 3xl, 4xl
- Line height: 1.6 (body), 1.2 (headings)

## Components Created

### 1. Core Components (`frontend/components/`)

**Cards (`cards.py`):**
- `render_card()` - Card component with optional glow effect
- `render_metric()` - Metric display with label, value, and change indicator
- `render_badge()` - Badge component with variants (primary, success, warning, danger, info)
- `render_loading_skeleton()` - Loading skeleton for async content
- `render_error()` - Error state with retry functionality

**Chat (`chat.py`):**
- `render_chat_message()` - Individual chat message bubble
- `render_chat_container()` - Chat container with scrolling

### 2. CSS Design System (`frontend/styles/styles.css`)

**Features:**
- Complete design token system
- Card components with hover effects (lift + glow)
- Metric components with change indicators
- Badge system with 5 variants
- Section components with accent bars
- Grid layouts (2, 3, 4 columns)
- Loading skeletons with animation
- Error states with icons
- Chat components with message bubbles
- Responsive breakpoints (640px, 768px, 1024px)
- Streamlit component overrides

**Animations:**
- Subtle lift on card hover (translateY -2px)
- Glowing accent borders on hover
- Skeleton loading animation
- Fade-in for chat messages

## Page Components

### 1. Facility Profile (`frontend/pages/facility_profile.py`)

**Features:**
- **Hero Section:** Restaurant name, grade badge, metadata
- **Metrics Strip:** Current grade, score, risk level, predicted next grade (4-column grid)
- **Score Timeline:** Interactive Plotly chart with grade thresholds
- **SHAP Feature Explanation:** Key risk factors affecting grade and critical violations
- **Top Actions Panel:** RAG-powered recommendations by category

**Design Highlights:**
- Grade-based color coding (A=green, B=yellow, C=red)
- Animated score trend visualization
- Responsive grid layouts

### 2. Inspection Advisor (`frontend/pages/inspection_advisor.py`)

**Features:**
- **Chat Interface:** 
  - Message bubbles (user/assistant)
  - Timestamps
  - Smooth animations
  - Scrolling container
- **Memory Sidebar:** 
  - Recent conversation history
  - Question tracking
- **Document Viewer:** 
  - RAG policy chunks
  - Best practices
  - Violation-specific policies
  - Expandable cards

**Design Highlights:**
- Two-column layout (chat 2:1 sidebar)
- Distinct styling for user vs assistant messages
- Document cards with badges for categories

### 3. Risk & Forecasting (`frontend/pages/risk_forecasting.py`)

**Features:**
- **ML Forecast Graph:**
  - Historical scores line
  - Forecast line with confidence intervals
  - Grade threshold markers
  - Interactive Plotly chart
- **Scenario Simulator:**
  - Action selection dropdown
  - Timeframe selection
  - Simulation results display

**Design Highlights:**
- Dark-themed Plotly charts
- Confidence interval shading
- Color-coded grade zones

### 4. Safety Intelligence (`frontend/pages/safety_intel.py`)

**Features:**
- **Neighborhood Map:**
  - Interactive map with grade-based coloring
  - Hover tooltips
  - Plotly scatter mapbox
- **Neighborhood Badges:**
  - Total neighbors metric
  - Grade A percentage
  - Average score
  - Risk level indicator
- **Peer Comparison Chart:**
  - Your score vs neighborhood
  - Best/worst neighbor comparison
  - Bar chart visualization

**Design Highlights:**
- Map integration with color coding
- Neighborhood statistics at a glance
- Comparative visualizations

## Loading States & Error Handling

### Loading Skeletons
- Card skeletons with animated backgrounds
- Text line skeletons
- Title skeletons
- Multiple skeleton lines for complex content

### Error States
- Icon-based error display
- Clear error titles and messages
- Retry button functionality
- Graceful fallbacks

## Responsive Design

**Breakpoints:**
- **Mobile (< 640px):**
  - Single column layouts
  - Reduced padding
  - Larger touch targets
  - Stacked metrics

- **Tablet (640px - 1024px):**
  - 2-column grids
  - Adjusted spacing
  - Optimized charts

- **Desktop (> 1024px):**
  - Full 3-4 column grids
  - Maximum spacing
  - Full feature set

## Usage

### Loading CSS

```python
from frontend.pages.facility_profile import render_facility_profile_page

# The page components automatically load CSS
render_facility_profile_page(
    restaurant_name="My Restaurant",
    hist=inspection_history,
    profile_data=profile_service_data
)
```

### Using Components

```python
from frontend.components.cards import render_card, render_metric, render_badge

# Render a card
render_card(
    content="<p>Card content</p>",
    title="Card Title",
    glow=True  # Optional glow effect
)

# Render a metric
render_metric(
    label="Current Score",
    value="85",
    change="+5",
    change_type="positive"
)

# Render a badge
render_badge("Grade A", variant="success")
```

## Integration Notes

1. **CSS Loading:** Each page component automatically loads `frontend/styles/styles.css`
2. **Component Dependencies:** Components are self-contained and can be used independently
3. **Streamlit Integration:** All components work with Streamlit's rendering system
4. **Plotly Charts:** Dark theme configured for consistency
5. **Error Handling:** Graceful fallbacks for missing data

## File Structure

```
frontend/
├── components/
│   ├── __init__.py
│   ├── cards.py          # Card, metric, badge, skeleton, error components
│   └── chat.py           # Chat message and container components
├── pages/
│   ├── __init__.py
│   ├── facility_profile.py    # Facility profile page
│   ├── inspection_advisor.py  # AI coach with chat
│   ├── risk_forecasting.py    # ML forecasts and scenarios
│   └── safety_intel.py        # Neighborhood analysis
└── styles/
    └── styles.css        # Complete design system
```

## Future Enhancements

- [ ] Custom Streamlit theme configuration
- [ ] Additional animation variants
- [ ] Theme switcher (light/dark)
- [ ] More chart types
- [ ] Accessibility improvements (ARIA labels)
- [ ] Performance optimizations (CSS-in-JS alternative)

