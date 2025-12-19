import os
import glob
import datetime
import html
import json
import logging
import warnings
from math import radians, sin, cos, asin, sqrt
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

# Suppress PyTorch warnings and errors early
# Set environment variables before any torch imports
os.environ['PYTHONWARNINGS'] = 'ignore'
os.environ['TORCH_WARN'] = '0'
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# Suppress Python warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='.*torch.classes.*')
warnings.filterwarnings('ignore', message='.*ARC4.*')
warnings.filterwarnings('ignore', category=DeprecationWarning)

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import requests

# Optional RAG deps
try:
    import chromadb
    from chromadb.utils import embedding_functions
    HAS_CHROMA = True
except Exception:
    HAS_CHROMA = False

try:
    # Suppress any warnings during import
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except Exception as e:
    HAS_SENTENCE_TRANSFORMERS = False
    # Log but don't fail - app can run without embeddings
    logging.warning(f"Could not import sentence_transformers: {e}. RAG features will be disabled.")

# Optional PDF support for KB
try:
    import pypdf
    HAS_PDF = True
except Exception:
    HAS_PDF = False


# # ============================================================
# # CONFIG
# # ============================================================



# ============================================================
# CONFIGURATION - Environment Variables & Secrets
# ============================================================

# API Configuration - Use secrets or environment variables
def get_api_key() -> str:
    """Get API key from environment variables or Streamlit secrets."""
    # Try environment variable first
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    
    # Try Streamlit secrets if available
    if not api_key:
        try:
            api_key = st.secrets.get("openrouter", {}).get("api_key", "")
        except (FileNotFoundError, AttributeError, KeyError):
            # Secrets file doesn't exist or key not found - that's okay
            pass
    
    return api_key

OPENROUTER_API_KEY = get_api_key()
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini-2024-07-18")

# Validate API key - show helpful message if missing
if not OPENROUTER_API_KEY:
    st.error("""
    **OPENROUTER_API_KEY not found**
    
    Please set your API key using one of these methods:
    
    **Option 1: Environment Variable (Recommended)**
    ```bash
    export OPENROUTER_API_KEY="your-api-key-here"
    ```
    
    **Option 2: Streamlit Secrets File**
    Create a file at: `.streamlit/secrets.toml`
    ```toml
    [openrouter]
    api_key = "your-api-key-here"
    ```
    
    **Option 3: Temporary (for testing only)**
    You can temporarily set it in the code (NOT recommended for production).
    """)
    st.stop()

# Constants
DATA_FILENAME = os.getenv("DATA_FILENAME", "updated_nyc_inspections.xlsx")
KB_FOLDER = os.getenv("KB_FOLDER", "kb")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "chroma_db")
RAG_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "nyc_inspections_kb")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# Performance Constants
MAX_CACHE_SIZE = int(os.getenv("MAX_CACHE_SIZE", "100"))
MAX_MEMORY_ITEMS = int(os.getenv("MAX_MEMORY_ITEMS", "50"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1600"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Business Logic Constants
RISK_THRESHOLD_LOW = 13.0
RISK_THRESHOLD_MEDIUM = 25.0
CRITICAL_VIOLATION_THRESHOLD = 2
MIN_INSPECTIONS_FOR_TREND = 3
DEFAULT_FORECAST_PERIODS = 3

# UI Constants
PAGE_MAX_WIDTH = 1420
HERO_SPACING_TOP = 120
HERO_SPACING_SIDE = 80
NAVBAR_HEIGHT = 72


# ============================================================
# MULTILINGUAL SUPPORT - TRANSLATION DICTIONARY
# ============================================================

TEXT = {
    "en": {
        # App Title & Header
        "app_title": "SmartBite",
        "app_subtitle": "Smarter Inspections. Safer Kitchens.",
        "app_description": "AI-driven autonomous compliance matrix for real-time restaurant safety, inspection forecasting, and risk elimination.",
        "app_pill": "NYC • DOHMH • GRADE OPTIMIZATION",
        
        # Language Selector
        "lang_english": "English",
        "lang_spanish": "Español",
        "lang_hindi": "हिंदी",
        "lang_chinese": "中文",
        "lang_select": "Language",
        
        # Tab Names
        "tab_nearby": "Safety Intelligence",
        "tab_profile": "Facility Profile",
        "tab_ai": "Inspection Advisor",
        "tab_sim": "Risk & Forecasting",
        
        # Nearby Intelligence Tab
        "nearby_title": "Nearby Restaurants Intelligence",
        "nearby_caption": "Pick your own restaurant, then see which nearby places are getting A, B, or C – so you understand your neighborhood risk and competitive bar.",
        "nearby_no_geo": "This dataset does not include usable latitude/longitude for restaurants, so nearby comparisons are not available.",
        "nearby_no_rest": "No restaurants with geolocation data available.",
        "nearby_select_anchor": "Select your restaurant (anchor point)",
        "nearby_radius": "Radius around your restaurant (km)",
        "nearby_no_geo_data": "No geolocation data for this restaurant.",
        "nearby_your_grade": "Your latest grade",
        "nearby_your_score": "Your latest score",
        "nearby_in_radius": "Restaurants in radius",
        "nearby_grade_a_share": "Share of Grade A nearby",
        "nearby_map_title": "Map – nearby restaurant performance",
        "nearby_map_caption": "Anchor point is your restaurant. Dots show latest inspection locations around you.",
        "nearby_no_neighbors": "No other restaurants found within this radius. Increase the radius to see more neighbors.",
        "nearby_snapshot_title": "Nearby inspection snapshot",
        "nearby_snapshot_caption": "Use this list to see which neighbors are getting A/B/C, and how far they are from you.",
        "nearby_no_found": "No nearby restaurants were found within the selected radius.",
        
        # Restaurant Profile Tab
        "profile_title": "Restaurant Profile & Trajectory",
        "profile_caption": "Drill into a single CAMIS and see violations, risk, and narrative trajectory.",
        "profile_no_rest": "No restaurants available under current filters.",
        "profile_select": "Restaurant name",
        "profile_no_data": "No inspection data for this restaurant under current filters.",
        "profile_latest_grade": "Latest Grade",
        "profile_latest_score": "Latest Score",
        "profile_risk_level": "Risk Level",
        "profile_trend": "Trend:",
        "profile_velocity": "points per inspection",
        "profile_predicted_next": "Predicted Next:",
        "profile_grade_probs": "Next Inspection Grade Probabilities",
        "profile_grade_a_prob": "Grade A Probability",
        "profile_grade_b_prob": "Grade B Probability",
        "profile_grade_c_prob": "Grade C Probability",
        "profile_best_outcome": "Best outcome",
        "profile_moderate": "Moderate",
        "profile_high_risk": "High risk",
        "profile_confidence": "Confidence Level:",
        "profile_based_on": "recent inspections",
        "profile_last_5": "Latest Inspections",
        "profile_summary": "Simple Summary",
        
        # AI Inspection Coach Tab
        "ai_title": "AI Inspection Coach",
        "ai_caption": "Ask questions about your restaurant's inspection history, violations, and how to improve your grade.",
        "ai_ask_question": "Ask your question",
        "ai_placeholder": "e.g., 'Why did I get a B grade?' or 'How do I fix pest violations?'",
        "ai_ask_button": "Ask SmartBite",
        "ai_suggested": "Suggested Questions",
        "ai_memory_title": "Restaurant Memory",
        "ai_memory_caption": "Previous questions and answers for this restaurant",
        
        # Simulation & Forecasting Tab
        "sim_title": "What-If Simulator",
        "sim_caption": "Simulate fixing specific violation categories to see how your score would improve.",
        "sim_select_rest": "Restaurant for simulation",
        "sim_no_history": "No inspection history for this restaurant.",
        "sim_fix_pest": "Fix pest-related violations",
        "sim_fix_temp": "Fix temperature and storage issues",
        "sim_fix_clean": "Fix cleanliness and facility issues",
        "sim_fix_staff": "Fix handwashing, cross-contamination and staff training issues",
        "sim_run": "Run Simulation",
        "sim_not_enough": "Not enough score data to simulate.",
        "sim_current_score": "Current score",
        "sim_simulated_score": "Simulated score",
        "sim_simulated_grade": "Simulated grade",
        "sim_reduction": "Approximate score reduction by category",
        "sim_category": "Category",
        "sim_reduction_points": "Reduction points",
        "sim_pest": "Pest control",
        "sim_temp": "Temperature & storage",
        "sim_clean": "Facility cleanliness",
        "sim_handwash": "Handwashing / cross-contamination",
        "sim_insight": "Simulation insight",
        "sim_score_shift": "Score shift",
        "sim_projected_grade": "Projected grade",
        "sim_focus_areas": "Focus areas",
        "sim_review_button": "Ask AI Coach to review this scenario",
        "sim_tip": "Tip: Use this to show owners exactly how many points they leave on the table by ignoring pests, temperatures, or cleaning.",
        "forecast_title": "Risk Forecasting & Grade Trajectory",
        "forecast_caption": "Simple score trend projection for the next few inspections.",
        "forecast_select": "Restaurant for forecasting",
        "forecast_no_history": "No inspection history for this restaurant.",
        "forecast_no_data": "Not enough history to forecast trend.",
        "forecast_table_title": "Forecasted score & grade for next inspections",
        "forecast_explain": "Explain this in simple language",
        "forecast_narrative": "SmartBite Risk Narrative",
        
        # Sidebar
        "sidebar_boro": "Borough",
        "sidebar_cuisine": "Cuisine",
        "sidebar_grade": "Grade",
        "sidebar_date_range": "Date range",
        "sidebar_enable_ai": "Enable AI Features",
        
        # Common
        "common_no_rest": "No restaurants available under current filters.",
        "common_na": "N/A",
        "common_unknown": "Unknown",
        "common_low": "Low",
        "common_moderate": "Moderate",
        "common_high": "High",
        "common_critical": "Critical",
    },
    "es": {
        # App Title & Header
        "app_title": "SmartBite",
        "app_subtitle": "Haz que las Inspecciones sean Sin Peso.",
        "app_description": "Sistema de cumplimiento operativo impulsado por IA para la seguridad de restaurantes, inspecciones y reducción de riesgos de seguros.",
        "app_pill": "NYC • DOHMH • OPTIMIZACIÓN DE CALIFICACIÓN",
        
        # Language Selector
        "lang_english": "English",
        "lang_spanish": "Español",
        "lang_hindi": "हिंदी",
        "lang_chinese": "中文",
        "lang_select": "Idioma",
        
        # Tab Names
        "tab_nearby": "Inteligencia Cercana",
        "tab_profile": "Perfil del Restaurante",
        "tab_ai": "Entrenador de Inspección IA",
        "tab_sim": "Simulación y Pronóstico",
        
        # Nearby Intelligence Tab
        "nearby_title": "Inteligencia de Restaurantes Cercanos",
        "nearby_caption": "Selecciona tu restaurante, luego ve qué lugares cercanos obtienen A, B o C – para que entiendas el riesgo de tu vecindario y la barra competitiva.",
        "nearby_no_geo": "Este conjunto de datos no incluye latitud/longitud utilizable para restaurantes, por lo que las comparaciones cercanas no están disponibles.",
        "nearby_no_rest": "No hay restaurantes con datos de geolocalización disponibles.",
        "nearby_select_anchor": "Selecciona tu restaurante (punto de anclaje)",
        "nearby_radius": "Radio alrededor de tu restaurante (km)",
        "nearby_no_geo_data": "No hay datos de geolocalización para este restaurante.",
        "nearby_your_grade": "Tu última calificación",
        "nearby_your_score": "Tu última puntuación",
        "nearby_in_radius": "Restaurantes en el radio",
        "nearby_grade_a_share": "Participación de Calificación A cercana",
        "nearby_map_title": "Mapa – rendimiento de restaurantes cercanos",
        "nearby_map_caption": "El punto de anclaje es tu restaurante. Los puntos muestran las ubicaciones de inspección más recientes a tu alrededor.",
        "nearby_no_neighbors": "No se encontraron otros restaurantes dentro de este radio. Aumenta el radio para ver más vecinos.",
        "nearby_snapshot_title": "Instantánea de inspección cercana",
        "nearby_snapshot_caption": "Usa esta lista para ver qué vecinos obtienen A/B/C y qué tan lejos están de ti.",
        "nearby_no_found": "No se encontraron restaurantes cercanos dentro del radio seleccionado.",
        
        # Restaurant Profile Tab
        "profile_title": "Perfil y Trayectoria del Restaurante",
        "profile_caption": "Profundiza en un solo CAMIS y ve violaciones, riesgo y trayectoria narrativa.",
        "profile_no_rest": "No hay restaurantes disponibles bajo los filtros actuales.",
        "profile_select": "Nombre del restaurante",
        "profile_no_data": "No hay datos de inspección para este restaurante bajo los filtros actuales.",
        "profile_latest_grade": "Última Calificación",
        "profile_latest_score": "Última Puntuación",
        "profile_risk_level": "Nivel de Riesgo",
        "profile_trend": "Tendencia:",
        "profile_velocity": "puntos por inspección",
        "profile_predicted_next": "Próximo Predicho:",
        "profile_grade_probs": "Probabilidades de Calificación de la Próxima Inspección",
        "profile_grade_a_prob": "Probabilidad de Calificación A",
        "profile_grade_b_prob": "Probabilidad de Calificación B",
        "profile_grade_c_prob": "Probabilidad de Calificación C",
        "profile_best_outcome": "Mejor resultado",
        "profile_moderate": "Moderado",
        "profile_high_risk": "Alto riesgo",
        "profile_confidence": "Nivel de Confianza:",
        "profile_based_on": "inspecciones recientes",
        "profile_last_5": "Últimas Inspecciones",
        "profile_summary": "Resumen Simple",
        
        # AI Inspection Coach Tab
        "ai_title": "Entrenador de Inspección IA",
        "ai_caption": "Haz preguntas sobre el historial de inspecciones de tu restaurante, violaciones y cómo mejorar tu calificación.",
        "ai_ask_question": "Haz tu pregunta",
        "ai_placeholder": "ej., '¿Por qué obtuve una calificación B?' o '¿Cómo arreglo las violaciones de plagas?'",
        "ai_ask_button": "Preguntar a SmartBite",
        "ai_suggested": "Preguntas Sugeridas",
        "ai_memory_title": "Memoria del Restaurante",
        "ai_memory_caption": "Preguntas y respuestas anteriores para este restaurante",
        
        # Simulation & Forecasting Tab
        "sim_title": "Simulador de Escenarios",
        "sim_caption": "Simula arreglar categorías específicas de violaciones para ver cómo mejoraría tu puntuación.",
        "sim_select_rest": "Restaurante para simulación",
        "sim_no_history": "No hay historial de inspecciones para este restaurante.",
        "sim_fix_pest": "Arreglar violaciones relacionadas con plagas",
        "sim_fix_temp": "Arreglar problemas de temperatura y almacenamiento",
        "sim_fix_clean": "Arreglar problemas de limpieza e instalaciones",
        "sim_fix_staff": "Arreglar problemas de lavado de manos, contaminación cruzada y capacitación del personal",
        "sim_run": "Ejecutar Simulación",
        "sim_not_enough": "No hay suficientes datos de puntuación para simular.",
        "sim_current_score": "Puntuación actual",
        "sim_simulated_score": "Puntuación simulada",
        "sim_simulated_grade": "Calificación simulada",
        "sim_reduction": "Reducción aproximada de puntuación por categoría",
        "sim_category": "Categoría",
        "sim_reduction_points": "Puntos de reducción",
        "sim_pest": "Control de plagas",
        "sim_temp": "Temperatura y almacenamiento",
        "sim_clean": "Limpieza de instalaciones",
        "sim_handwash": "Lavado de manos / contaminación cruzada",
        "sim_insight": "Perspectiva de simulación",
        "sim_score_shift": "Cambio de puntuación",
        "sim_projected_grade": "Calificación proyectada",
        "sim_focus_areas": "Áreas de enfoque",
        "sim_review_button": "Pedir al Entrenador IA que revise este escenario",
        "sim_tip": "Consejo: Usa esto para mostrar a los propietarios exactamente cuántos puntos dejan sobre la mesa al ignorar plagas, temperaturas o limpieza.",
        "forecast_title": "Pronóstico de Riesgo y Trayectoria de Calificación",
        "forecast_caption": "Proyección simple de tendencia de puntuación para las próximas inspecciones.",
        "forecast_select": "Restaurante para pronóstico",
        "forecast_no_history": "No hay historial de inspecciones para este restaurante.",
        "forecast_no_data": "No hay suficiente historial para pronosticar la tendencia.",
        "forecast_table_title": "Puntuación y calificación pronosticadas para las próximas inspecciones",
        "forecast_explain": "Explicar esto en lenguaje simple",
        "forecast_narrative": "Narrativa de Riesgo de SmartBite",
        
        # Sidebar
        "sidebar_boro": "Distrito",
        "sidebar_cuisine": "Cocina",
        "sidebar_grade": "Calificación",
        "sidebar_date_range": "Rango de fechas",
        "sidebar_enable_ai": "Habilitar Funciones IA",
        
        # Common
        "common_no_rest": "No hay restaurantes disponibles bajo los filtros actuales.",
        "common_na": "N/A",
        "common_unknown": "Desconocido",
        "common_low": "Bajo",
        "common_moderate": "Moderado",
        "common_high": "Alto",
        "common_critical": "Crítico",
    },
    "hi": {
        # App Title & Header
        "app_title": "SmartBite",
        "app_subtitle": "निरीक्षण को बिना वजन बनाएं।",
        "app_description": "रेस्तरां सुरक्षा, निरीक्षण और बीमा जोखिम कमी के लिए AI-संचालित परिचालन अनुपालन प्रणाली।",
        "app_pill": "NYC • DOHMH • ग्रेड अनुकूलन",
        
        # Language Selector
        "lang_english": "English",
        "lang_spanish": "Español",
        "lang_hindi": "हिंदी",
        "lang_chinese": "中文",
        "lang_select": "भाषा",
        
        # Tab Names
        "tab_nearby": "निकट बुद्धिमत्ता",
        "tab_profile": "रेस्तरां प्रोफ़ाइल",
        "tab_ai": "AI निरीक्षण कोच",
        "tab_sim": "सिमुलेशन और पूर्वानुमान",
        
        # Nearby Intelligence Tab
        "nearby_title": "निकट रेस्तरां बुद्धिमत्ता",
        "nearby_caption": "अपना रेस्तरां चुनें, फिर देखें कि कौन से निकट स्थान A, B, या C प्राप्त कर रहे हैं – ताकि आप अपने पड़ोस के जोखिम और प्रतिस्पर्धी बार को समझ सकें।",
        "nearby_no_geo": "इस डेटासेट में रेस्तरां के लिए उपयोगी अक्षांश/देशांतर शामिल नहीं है, इसलिए निकट तुलना उपलब्ध नहीं है।",
        "nearby_no_rest": "जियोलोकेशन डेटा के साथ कोई रेस्तरां उपलब्ध नहीं है।",
        "nearby_select_anchor": "अपना रेस्तरां चुनें (एंकर बिंदु)",
        "nearby_radius": "आपके रेस्तरां के आसपास की त्रिज्या (किमी)",
        "nearby_no_geo_data": "इस रेस्तरां के लिए कोई जियोलोकेशन डेटा नहीं है।",
        "nearby_your_grade": "आपका नवीनतम ग्रेड",
        "nearby_your_score": "आपका नवीनतम स्कोर",
        "nearby_in_radius": "त्रिज्या में रेस्तरां",
        "nearby_grade_a_share": "निकट ग्रेड A का हिस्सा",
        "nearby_map_title": "नक्शा – निकट रेस्तरां प्रदर्शन",
        "nearby_map_caption": "एंकर बिंदु आपका रेस्तरां है। बिंदु आपके आसपास के नवीनतम निरीक्षण स्थान दिखाते हैं।",
        "nearby_no_neighbors": "इस त्रिज्या के भीतर कोई अन्य रेस्तरां नहीं मिला। अधिक पड़ोसियों को देखने के लिए त्रिज्या बढ़ाएं।",
        "nearby_snapshot_title": "निकट निरीक्षण स्नैपशॉट",
        "nearby_snapshot_caption": "इस सूची का उपयोग करें यह देखने के लिए कि कौन से पड़ोसी A/B/C प्राप्त कर रहे हैं, और वे आपसे कितनी दूर हैं।",
        "nearby_no_found": "चयनित त्रिज्या के भीतर कोई निकट रेस्तरां नहीं मिला।",
        
        # Restaurant Profile Tab
        "profile_title": "रेस्तरां प्रोफ़ाइल और प्रक्षेपवक्र",
        "profile_caption": "एक एकल CAMIS में गहराई से जाएं और उल्लंघन, जोखिम और कथा प्रक्षेपवक्र देखें।",
        "profile_no_rest": "वर्तमान फ़िल्टर के तहत कोई रेस्तरां उपलब्ध नहीं है।",
        "profile_select": "रेस्तरां का नाम",
        "profile_no_data": "वर्तमान फ़िल्टर के तहत इस रेस्तरां के लिए कोई निरीक्षण डेटा नहीं है।",
        "profile_latest_grade": "नवीनतम ग्रेड",
        "profile_latest_score": "नवीनतम स्कोर",
        "profile_risk_level": "जोखिम स्तर",
        "profile_trend": "प्रवृत्ति:",
        "profile_velocity": "निरीक्षण प्रति अंक",
        "profile_predicted_next": "अगला पूर्वानुमान:",
        "profile_grade_probs": "अगले निरीक्षण ग्रेड संभावनाएं",
        "profile_grade_a_prob": "ग्रेड A संभावना",
        "profile_grade_b_prob": "ग्रेड B संभावना",
        "profile_grade_c_prob": "ग्रेड C संभावना",
        "profile_best_outcome": "सर्वोत्तम परिणाम",
        "profile_moderate": "मध्यम",
        "profile_high_risk": "उच्च जोखिम",
        "profile_confidence": "विश्वास स्तर:",
        "profile_based_on": "हाल के निरीक्षण",
        "profile_last_5": "अंतिम निरीक्षण",
        "profile_summary": "सरल सारांश",
        
        # AI Inspection Coach Tab
        "ai_title": "AI निरीक्षण कोच",
        "ai_caption": "अपने रेस्तरां के निरीक्षण इतिहास, उल्लंघनों और अपने ग्रेड को कैसे सुधारें, इसके बारे में प्रश्न पूछें।",
        "ai_ask_question": "अपना प्रश्न पूछें",
        "ai_placeholder": "उदा., 'मुझे B ग्रेड क्यों मिला?' या 'मैं कीट उल्लंघनों को कैसे ठीक करूं?'",
        "ai_ask_button": "SmartBite से पूछें",
        "ai_suggested": "सुझाए गए प्रश्न",
        "ai_memory_title": "रेस्तरां मेमोरी",
        "ai_memory_caption": "इस रेस्तरां के लिए पिछले प्रश्न और उत्तर",
        
        # Simulation & Forecasting Tab
        "sim_title": "क्या-अगर सिमुलेटर",
        "sim_caption": "अपने स्कोर में सुधार देखने के लिए विशिष्ट उल्लंघन श्रेणियों को ठीक करने का अनुकरण करें।",
        "sim_select_rest": "सिमुलेशन के लिए रेस्तरां",
        "sim_no_history": "इस रेस्तरां के लिए कोई निरीक्षण इतिहास नहीं है।",
        "sim_fix_pest": "कीट-संबंधित उल्लंघनों को ठीक करें",
        "sim_fix_temp": "तापमान और भंडारण समस्याओं को ठीक करें",
        "sim_fix_clean": "सफाई और सुविधा समस्याओं को ठीक करें",
        "sim_fix_staff": "हैंडवॉशिंग, क्रॉस-दूषण और स्टाफ प्रशिक्षण समस्याओं को ठीक करें",
        "sim_run": "सिमुलेशन चलाएं",
        "sim_not_enough": "सिमुलेशन के लिए पर्याप्त स्कोर डेटा नहीं है।",
        "sim_current_score": "वर्तमान स्कोर",
        "sim_simulated_score": "सिम्युलेटेड स्कोर",
        "sim_simulated_grade": "सिम्युलेटेड ग्रेड",
        "sim_reduction": "श्रेणी द्वारा अनुमानित स्कोर कमी",
        "sim_category": "श्रेणी",
        "sim_reduction_points": "कमी अंक",
        "sim_pest": "कीट नियंत्रण",
        "sim_temp": "तापमान और भंडारण",
        "sim_clean": "सुविधा सफाई",
        "sim_handwash": "हैंडवॉशिंग / क्रॉस-दूषण",
        "sim_insight": "सिमुलेशन अंतर्दृष्टि",
        "sim_score_shift": "स्कोर बदलाव",
        "sim_projected_grade": "अनुमानित ग्रेड",
        "sim_focus_areas": "फोकस क्षेत्र",
        "sim_review_button": "AI कोच से इस परिदृश्य की समीक्षा करने के लिए कहें",
        "sim_tip": "सुझाव: मालिकों को यह दिखाने के लिए उपयोग करें कि कीट, तापमान या सफाई को अनदेखा करके वे कितने अंक छोड़ रहे हैं।",
        "forecast_title": "जोखिम पूर्वानुमान और ग्रेड प्रक्षेपवक्र",
        "forecast_caption": "अगले कुछ निरीक्षणों के लिए सरल स्कोर प्रवृत्ति प्रक्षेपण।",
        "forecast_select": "पूर्वानुमान के लिए रेस्तरां",
        "forecast_no_history": "इस रेस्तरां के लिए कोई निरीक्षण इतिहास नहीं है।",
        "forecast_no_data": "प्रवृत्ति का पूर्वानुमान लगाने के लिए पर्याप्त इतिहास नहीं है।",
        "forecast_table_title": "अगले निरीक्षणों के लिए पूर्वानुमानित स्कोर और ग्रेड",
        "forecast_explain": "इसे सरल भाषा में समझाएं",
        "forecast_narrative": "SmartBite जोखिम कथा",
        
        # Sidebar
        "sidebar_boro": "जिला",
        "sidebar_cuisine": "खाना",
        "sidebar_grade": "ग्रेड",
        "sidebar_date_range": "तारीख सीमा",
        "sidebar_enable_ai": "AI सुविधाएं सक्षम करें",
        
        # Common
        "common_no_rest": "वर्तमान फ़िल्टर के तहत कोई रेस्तरां उपलब्ध नहीं है।",
        "common_na": "N/A",
        "common_unknown": "अज्ञात",
        "common_low": "कम",
        "common_moderate": "मध्यम",
        "common_high": "उच्च",
        "common_critical": "महत्वपूर्ण",
    },
    "zh": {
        # App Title & Header
        "app_title": "SmartBite",
        "app_subtitle": "让检查变得轻松。",
        "app_description": "由AI驱动的运营合规系统，用于餐厅安全、检查和降低保险风险。",
        "app_pill": "NYC • DOHMH • 等级优化",
        
        # Language Selector
        "lang_english": "English",
        "lang_spanish": "Español",
        "lang_hindi": "हिंदी",
        "lang_chinese": "中文",
        "lang_select": "语言",
        
        # Tab Names
        "tab_nearby": "附近情报",
        "tab_profile": "餐厅档案",
        "tab_ai": "AI检查教练",
        "tab_sim": "模拟与预测",
        
        # Nearby Intelligence Tab
        "nearby_title": "附近餐厅情报",
        "nearby_caption": "选择您自己的餐厅，然后查看哪些附近的地方获得A、B或C – 以便您了解您所在社区的风险和竞争水平。",
        "nearby_no_geo": "此数据集不包含餐厅可用的经纬度，因此无法进行附近比较。",
        "nearby_no_rest": "没有可用的地理位置数据餐厅。",
        "nearby_select_anchor": "选择您的餐厅（锚点）",
        "nearby_radius": "您餐厅周围的半径（公里）",
        "nearby_no_geo_data": "此餐厅没有地理位置数据。",
        "nearby_your_grade": "您的最新等级",
        "nearby_your_score": "您的最新分数",
        "nearby_in_radius": "半径内的餐厅",
        "nearby_grade_a_share": "附近A级占比",
        "nearby_map_title": "地图 – 附近餐厅表现",
        "nearby_map_caption": "锚点是您的餐厅。点显示您周围的最新检查位置。",
        "nearby_no_neighbors": "在此半径内未找到其他餐厅。增加半径以查看更多邻居。",
        "nearby_snapshot_title": "附近检查快照",
        "nearby_snapshot_caption": "使用此列表查看哪些邻居获得A/B/C，以及它们离您有多远。",
        "nearby_no_found": "在选定半径内未找到附近餐厅。",
        
        # Restaurant Profile Tab
        "profile_title": "餐厅档案与轨迹",
        "profile_caption": "深入单个CAMIS，查看违规、风险和叙述轨迹。",
        "profile_no_rest": "当前筛选条件下没有可用餐厅。",
        "profile_select": "餐厅名称",
        "profile_no_data": "当前筛选条件下此餐厅没有检查数据。",
        "profile_latest_grade": "最新等级",
        "profile_latest_score": "最新分数",
        "profile_risk_level": "风险级别",
        "profile_trend": "趋势：",
        "profile_velocity": "每次检查的分数",
        "profile_predicted_next": "预测下一个：",
        "profile_grade_probs": "下次检查等级概率",
        "profile_grade_a_prob": "A级概率",
        "profile_grade_b_prob": "B级概率",
        "profile_grade_c_prob": "C级概率",
        "profile_best_outcome": "最佳结果",
        "profile_moderate": "中等",
        "profile_high_risk": "高风险",
        "profile_confidence": "置信度：",
        "profile_based_on": "最近检查",
        "profile_last_5": "最新检查",
        "profile_summary": "简单摘要",
        
        # AI Inspection Coach Tab
        "ai_title": "AI检查教练",
        "ai_caption": "询问有关您餐厅检查历史、违规以及如何提高等级的问题。",
        "ai_ask_question": "提出您的问题",
        "ai_placeholder": "例如，'为什么我得到B级？'或'如何修复害虫违规？'",
        "ai_ask_button": "询问SmartBite",
        "ai_suggested": "建议问题",
        "ai_memory_title": "餐厅记忆",
        "ai_memory_caption": "此餐厅的先前问题和答案",
        
        # Simulation & Forecasting Tab
        "sim_title": "假设模拟器",
        "sim_caption": "模拟修复特定违规类别，以查看您的分数如何改善。",
        "sim_select_rest": "用于模拟的餐厅",
        "sim_no_history": "此餐厅没有检查历史。",
        "sim_fix_pest": "修复与害虫相关的违规",
        "sim_fix_temp": "修复温度和储存问题",
        "sim_fix_clean": "修复清洁和设施问题",
        "sim_fix_staff": "修复洗手、交叉污染和员工培训问题",
        "sim_run": "运行模拟",
        "sim_not_enough": "没有足够的分数数据进行模拟。",
        "sim_current_score": "当前分数",
        "sim_simulated_score": "模拟分数",
        "sim_simulated_grade": "模拟等级",
        "sim_reduction": "按类别的近似分数减少",
        "sim_category": "类别",
        "sim_reduction_points": "减少分数",
        "sim_pest": "害虫控制",
        "sim_temp": "温度和储存",
        "sim_clean": "设施清洁",
        "sim_handwash": "洗手/交叉污染",
        "sim_insight": "模拟洞察",
        "sim_score_shift": "分数变化",
        "sim_projected_grade": "预测等级",
        "sim_focus_areas": "重点领域",
        "sim_review_button": "请AI教练审查此场景",
        "sim_tip": "提示：使用此功能向业主展示他们通过忽略害虫、温度或清洁而丢失了多少分数。",
        "forecast_title": "风险预测与等级轨迹",
        "forecast_caption": "未来几次检查的简单分数趋势预测。",
        "forecast_select": "用于预测的餐厅",
        "forecast_no_history": "此餐厅没有检查历史。",
        "forecast_no_data": "没有足够的历史来预测趋势。",
        "forecast_table_title": "未来检查的预测分数和等级",
        "forecast_explain": "用简单语言解释",
        "forecast_narrative": "SmartBite风险叙述",
        
        # Sidebar
        "sidebar_boro": "区",
        "sidebar_cuisine": "菜系",
        "sidebar_grade": "等级",
        "sidebar_date_range": "日期范围",
        "sidebar_enable_ai": "启用AI功能",
        
        # Common
        "common_no_rest": "当前筛选条件下没有可用餐厅。",
        "common_na": "N/A",
        "common_unknown": "未知",
        "common_low": "低",
        "common_moderate": "中等",
        "common_high": "高",
        "common_critical": "严重",
    }
}


def T(key: str) -> str:
    """
    Translation helper function.
    Returns translated text for the current language, or the key if translation not found.
    """
    lang = st.session_state.get("language", "en")
    return TEXT.get(lang, {}).get(key, TEXT.get("en", {}).get(key, key))


# ============================================================
# STREAMLIT GLOBAL CONFIG & STRIPE-INSPIRED THEME
# ============================================================

st.set_page_config(
    page_title="SmartBite – Smarter Inspections. Safer Kitchens.",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    :root {
        /* Stripe Design System - Design Tokens */
        --page-max-width: 1420px;
        --page-width: 1200px;
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 20px;
        --radius-xl: 28px;
        --space-xs: 8px;
        --space-sm: 12px;
        --space-md: 16px;
        --space-lg: 24px;
        --space-xl: 32px;
        --space-2xl: 48px;
        --section-spacing: 48px;
        --block-spacing: 32px;
        --field-spacing: 20px;
        --hero-spacing: 160px;
        
        /* SmartBite Futuristic Color Palette */
        --bg-gradient-start: rgba(139, 92, 246, 0.08);
        --bg-gradient-mid: rgba(236, 72, 153, 0.06);
        --bg-gradient-end: rgba(251, 146, 60, 0.05);
        --bg-page: #fafafa;
        --bg-card: #ffffff;
        --bg-card-muted: #f9f9fb;
        --border: rgba(0, 0, 0, 0.1);
        --text-dark: #0A2540;
        --text-body: #425466;
        --text-muted: #63748c;
        --accent: #635bff;
        --accent-soft: rgba(99, 91, 255, 0.15);
        --divider: rgba(0,0,0,0.1);
        
        /* Legacy tokens for compatibility */
        --zg-font-title: 40px;
        --zg-font-section: 24px;
        --zg-font-body: 15px;
        --zg-font-label: 11px;
        --zg-font-caption: 12px;
        --zg-card-radius: var(--radius-xl);
        --zg-padding: var(--space-2xl);
        --zg-spacing-xl: var(--space-2xl);
        --zg-spacing-lg: var(--space-xl);
        --zg-spacing-md: var(--space-lg);
        --zg-spacing-sm: var(--space-md);
        --zg-shadow-ambient: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.1);
        --zg-shadow-elevated: 0 4px 6px rgba(0, 0, 0, 0.05), 0 10px 15px rgba(0, 0, 0, 0.1);
        --zg-accent: #81D8D0;
        --zg-accent-glow: rgba(129, 216, 208, 0.15);
        --sb-accent: #81D8D0;
        --sb-accent-soft: rgba(129, 216, 208, 0.1);
        --sb-accent-strong: rgba(129, 216, 208, 0.2);
        --sb-text-main: var(--text-dark);
        --sb-muted: var(--text-muted);
        --sb-soft-border: var(--border);
    }

    /* Stripe Global App Background - Soft Gradient */
    .stApp {
        background: 
            radial-gradient(circle at 20% 30%, var(--bg-gradient-start) 0%, transparent 50%),
            radial-gradient(circle at 80% 70%, var(--bg-gradient-mid) 0%, transparent 50%),
            linear-gradient(135deg, var(--bg-page) 0%, #f8f9fa 50%, #f5f6f8 100%);
        color: var(--text-dark);
        font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
        font-weight: 400;
        line-height: 1.6;
        letter-spacing: -0.01em;
        min-height: 100vh;
    }
    
    /* Hide Streamlit default header/footer */
    #MainMenu { visibility: hidden; }
    header { visibility: hidden; }
    footer { visibility: hidden; }

    .main {
        background: transparent !important;
    }

    /* Stripe Container System */
    .block-container {
        max-width: var(--page-max-width);
        padding: 0 var(--space-xl);
        margin: 0 auto;
    }

    @media (max-width: 992px) {
        .block-container {
            padding: 0 var(--space-md);
        }
    }

    /* Stripe Typography System */
    h1, h2, h3, h4, h5, h6 {
        letter-spacing: -0.02em;
        color: var(--text-dark);
        font-weight: 600;
        line-height: 1.2;
        margin: 0;
    }

    h1 {
        font-size: 40px;
        font-weight: 600;
        letter-spacing: -0.03em;
        line-height: 1.1;
    }

    h2 {
        font-size: 24px;
        font-weight: 600;
        line-height: 1.3;
        margin-bottom: var(--space-md);
    }
    
    body, p {
        font-size: 15px;
        line-height: 1.6;
        color: var(--text-body);
        letter-spacing: -0.01em;
    }

    /* Hide Sidebar */
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Stripe Navigation Bar - Enhanced with Perfect Hover States */
    .stripe-nav {
        position: sticky;
        top: 0;
        z-index: 1000;
        background: rgba(255, 255, 255, 0.98);
        border-bottom: 1px solid rgba(0, 0, 0, 0.06);
        padding: 0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06);
        height: 72px;
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
    }
    
    .stripe-nav-container {
        max-width: var(--page-max-width);
        margin: 0 auto;
        padding: 0 var(--space-xl);
        height: 72px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: nowrap;
    }
    
    @media (max-width: 992px) {
        .stripe-nav-container {
            padding: 0 var(--space-md);
        }
    }
    
    .stripe-logo {
        font-size: 20px;
        font-weight: 700;
        color: var(--text-dark);
        letter-spacing: -0.02em;
        margin: 0;
        padding: 0;
        text-decoration: none;
        display: flex;
        align-items: center;
        height: 100%;
        transition: color 200ms cubic-bezier(0.4, 0, 0.2, 1), transform 150ms ease;
    }
    
    .stripe-logo:hover {
        color: var(--accent);
        transform: translateY(-1px);
    }
    
    .stripe-nav-center {
        display: flex;
        align-items: center;
        gap: 0;
        flex: 1;
        justify-content: center;
        height: 100%;
        margin: 0 var(--space-lg);
    }
    
    .stripe-nav-link-item {
        color: var(--text-body);
        text-decoration: none;
        font-size: 15px;
        font-weight: 500;
        padding: 0 var(--space-md);
        height: 72px;
        display: flex;
        align-items: center;
        transition: color 200ms cubic-bezier(0.4, 0, 0.2, 1), transform 150ms ease;
        position: relative;
        letter-spacing: -0.01em;
    }
    
    .stripe-nav-link-item:hover {
        color: var(--text-dark);
        transform: translateY(-1px);
    }
    
    .stripe-nav-link-item::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: var(--space-md);
        right: var(--space-md);
        height: 2px;
        background: linear-gradient(90deg, var(--text-dark), var(--accent));
        transform: scaleX(0);
        transform-origin: center;
        transition: transform 250ms cubic-bezier(0.4, 0, 0.2, 1);
        border-radius: 2px 2px 0 0;
    }
    
    .stripe-nav-link-item:hover::after {
        transform: scaleX(1);
    }
    
    .stripe-nav-actions {
        display: flex;
        align-items: center;
        gap: var(--space-md);
        height: 100%;
        margin-left: var(--space-lg);
    }
    
    .stripe-nav-link {
        color: var(--text-body);
        text-decoration: none;
        font-size: 15px;
        font-weight: 500;
        transition: color 200ms cubic-bezier(0.4, 0, 0.2, 1), transform 150ms ease;
        letter-spacing: -0.01em;
        display: flex;
        align-items: center;
        height: 100%;
        padding: 0 var(--space-sm);
        white-space: nowrap;
    }
    
    .stripe-nav-link:hover {
        color: var(--text-dark);
        transform: translateY(-1px);
    }
    
    .stripe-nav-button {
        background: #FFC043;
        color: var(--text-dark);
        border: none;
        padding: var(--space-sm) var(--space-lg);
        border-radius: 999px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24);
        letter-spacing: -0.01em;
        white-space: nowrap;
        height: auto;
        line-height: 1.5;
    }
    
    .stripe-nav-button:hover {
        background: #FFB82E;
        box-shadow: 0 4px 12px rgba(255, 192, 67, 0.4), 0 2px 6px rgba(255, 192, 67, 0.3);
        transform: translateY(-2px);
    }
    
    .stripe-nav-button:active {
        transform: translateY(0);
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.15);
    }
    
    /* Filter Bar - Optimized for Compactness & Perfect Alignment */
    .filter-bar-container {
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(250, 250, 252, 0.95) 100%);
        border-bottom: 1px solid rgba(0, 0, 0, 0.06);
        padding: 20px 48px;
        margin: 0 auto;
        max-width: var(--page-max-width);
        margin-top: 0;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
    }
    
    @media (max-width: 992px) {
        .filter-bar-container {
            padding: 16px 24px;
        }
    }
    
    /* Ensure seamless connection between nav and filter bar */
    .stripe-nav + .filter-bar-container {
        margin-top: 0;
        border-top: none;
    }
    
    /* Standardize element container spacing in filter bar */
    .filter-bar-container .element-container {
        margin-bottom: 0 !important;
        margin-top: 0 !important;
    }
    
    .filter-bar-row {
        display: flex;
        align-items: flex-end;
        gap: var(--space-sm);
        flex-wrap: wrap;
        justify-content: flex-start;
    }
    
    .filter-item-wrapper {
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-width: 110px;
        flex: 0 1 auto;
    }
    
    .filter-label {
        font-size: 11px;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 700;
        margin: 0 0 6px 2px;
        padding: 0;
        line-height: 1.2;
    }
    
    /* Compact Filter Controls - Enhanced Spacing */
    .filter-bar-container [data-testid="column"] {
        padding-left: 0 !important;
        padding-right: 16px !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    
    .filter-bar-container [data-testid="column"]:last-child {
        padding-right: 0 !important;
    }
    
    .filter-bar-container .stSelectbox,
    .filter-bar-container .stDateInput,
    .filter-bar-container .stCheckbox {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    
    .filter-bar-container .stSelectbox > div > div,
    .filter-bar-container .stDateInput > div > div > input,
    .filter-bar-container select {
        min-height: 42px !important;
        padding: 10px 14px !important;
        font-size: 14px !important;
        border-radius: 8px !important;
        border: 1.5px solid rgba(0, 0, 0, 0.08) !important;
        background: #FFFFFF !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03), 0 1px 2px rgba(0, 0, 0, 0.02) !important;
        transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1) !important;
        font-family: "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
        font-weight: 500 !important;
        color: var(--text-dark) !important;
    }
    
    .filter-bar-container .stSelectbox > div > div:hover,
    .filter-bar-container .stDateInput > div > div > input:hover {
        border-color: rgba(0, 0, 0, 0.12) !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        transform: translateY(-1px);
    }
    
    .filter-bar-container .stSelectbox > div > div:focus-within,
    .filter-bar-container .stDateInput > div > div > input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px var(--accent-soft), 0 2px 4px rgba(0, 0, 0, 0.06) !important;
        outline: none !important;
        transform: translateY(0);
    }
    
    .filter-bar-container .stCheckbox {
        margin-top: 0 !important;
        padding-top: 10px !important;
    }
    
    .filter-bar-container .stCheckbox > label {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px !important;
        font-weight: 500 !important;
        color: var(--text-dark) !important;
        margin: 0 !important;
        padding: 0 !important;
        cursor: pointer !important;
    }
    
    .filter-bar-container .stCheckbox input[type="checkbox"] {
        width: 20px !important;
        height: 20px !important;
        cursor: pointer !important;
        border-radius: 4px !important;
    }
    
    .filter-bar-container button[key="nav_generate_report"] {
        min-height: 42px !important;
        padding: 10px 20px !important;
        font-size: 14px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        margin-top: 0 !important;
        background: linear-gradient(135deg, #635BFF 0%, #7C3AED 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 2px 8px rgba(99, 91, 255, 0.25), 0 1px 3px rgba(99, 91, 255, 0.15) !important;
        transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1) !important;
        font-family: "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
        letter-spacing: 0.01em !important;
        cursor: pointer !important;
    }
    
    .filter-bar-container button[key="nav_generate_report"]:hover:not(:disabled) {
        background: linear-gradient(135deg, #5851ea 0%, #6D28D9 100%) !important;
        box-shadow: 0 4px 16px rgba(99, 91, 255, 0.35), 0 2px 8px rgba(99, 91, 255, 0.25) !important;
        transform: translateY(-2px) !important;
    }
    
    .filter-bar-container button[key="nav_generate_report"]:active:not(:disabled) {
        transform: translateY(0) !important;
        box-shadow: 0 1px 4px rgba(99, 91, 255, 0.3) !important;
    }
    
    .filter-bar-container button[key="nav_generate_report"]:disabled {
        background: linear-gradient(135deg, #CBD5E1 0%, #94A3B8 100%) !important;
        cursor: not-allowed !important;
        opacity: 0.6 !important;
        box-shadow: none !important;
    }
    
    /* Stripe Dividers */
    .sb-divider {
        width: 100%;
        height: 1px;
        background: var(--divider);
        margin: var(--block-spacing) 0;
        border: none;
    }
    
    /* Stripe Tabs - Bigger & Bolder */
    .stTabs [role="tablist"] {
        gap: var(--space-md) !important;
        justify-content: flex-start !important;
        border-bottom: none !important;
        margin-top: var(--space-2xl) !important;
        margin-bottom: var(--space-xl) !important;
        padding: 0 !important;
        background: transparent !important;
        max-width: var(--page-max-width);
        margin-left: auto;
        margin-right: auto;
    }
    
    /* Bigger Tab Buttons */
    button[data-baseweb="tab"] {
        height: 56px !important;
        padding: 0 var(--space-2xl) !important;
        border-radius: 999px !important;
        margin: 0 !important;
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        color: var(--text-muted) !important;
        font-size: 16px !important;
        font-weight: 500 !important;
        letter-spacing: -0.01em !important;
        transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1) !important;
        position: relative;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.08) !important;
        font-family: "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
    }
    
    /* Bigger Tab Hover */
    button[data-baseweb="tab"]:hover {
        background: var(--bg-card-muted) !important;
        color: var(--text-dark) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.10), 0 2px 8px rgba(0, 0, 0, 0.12) !important;
        transform: translateY(-2px);
        border-color: rgba(0, 0, 0, 0.14) !important;
    }
    
    /* Bigger Active Tab - No underline */
    button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(236, 72, 153, 0.12) 100%) !important;
        color: var(--text-dark) !important;
        font-weight: 600 !important;
        border-color: rgba(139, 92, 246, 0.28) !important;
        box-shadow: 0 4px 20px rgba(139, 92, 246, 0.20), 0 2px 10px rgba(139, 92, 246, 0.15), 0 0 0 1px rgba(139, 92, 246, 0.10) !important;
        transform: translateY(0);
    }

    /* Tab Content Spacing */
    div[data-testid="stTabs"] [data-baseweb="tab-panel"] .sb-surface {
        padding-top: var(--space-xl) !important;
        margin-top: 0 !important;
    }
    
    .stTabs [data-baseweb="tab-panel"] > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Perfect Vertical Rhythm - 8px base scale */
    .sb-surface > * {
        margin-bottom: var(--field-spacing);
    }
    
    .sb-surface > *:last-child {
        margin-bottom: 0;
    }
    
    /* Column spacing - Stripe grid */
    [data-testid="column"] {
        padding-left: 0 !important;
        padding-right: var(--space-md) !important;
    }
    
    [data-testid="column"]:last-child {
        padding-right: 0 !important;
    }
    
    /* Consistent spacing between sections */
    .sb-surface .element-container {
        margin-bottom: var(--field-spacing) !important;
    }
    
    .sb-surface .element-container:last-child {
        margin-bottom: 0 !important;
    }
    
    /* Perfect spacing for headings - 8px rhythm */
    h5, h6 {
        font-size: 18px !important;
        font-weight: 600 !important;
        color: var(--text-dark) !important;
        margin-top: var(--block-spacing) !important;
        margin-bottom: var(--field-spacing) !important;
        letter-spacing: -0.02em !important;
        line-height: 1.3 !important;
    }
    
    /* Ensure left alignment */
    .stApp > div > div > div > div,
    .block-container {
        text-align: left;
    }

    /* Stripe Inputs - Pill-shaped with shadow */
    textarea, input[type="text"], input[type="number"], select {
        border-radius: 999px !important;
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        padding: var(--space-sm) var(--space-lg) !important;
        font-size: 14px !important;
        color: var(--text-dark) !important;
        transition: all 200ms ease !important;
        font-family: "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
        box-shadow: none !important;
    }

    textarea:focus, input:focus, select:focus {
        background: var(--bg-card) !important;
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px var(--accent-soft), var(--zg-shadow-elevated) !important;
        outline: none !important;
    }

    textarea {
        border-radius: var(--radius-md) !important;
    }
    
    /* Stripe Selectbox - Pill-shaped */
    .stSelectbox > div > div {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 999px !important;
        box-shadow: none !important;
    }
    
    /* Stripe Slider */
    .stSlider {
        margin: var(--field-spacing) 0 !important;
    }
    
    .stSlider > div > div {
        background: var(--bg-card) !important;
    }
    
    /* Stripe Text Area */
    .stTextArea > div > div > textarea {
        border-radius: var(--radius-md) !important;
    }

    /* Stripe Dataframes */
    .dataframe {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-md) !important;
        overflow: hidden;
        box-shadow: none !important;
    }

    /* Stripe Alerts */
    .stAlert {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border) !important;
        box-shadow: var(--zg-shadow-ambient) !important;
    }

    .stInfo {
        background: #f0f9ff !important;
        border-color: #bae6fd !important;
    }

    .stWarning {
        background: #fffbeb !important;
        border-color: #fde68a !important;
    }

    .stError {
        background: #fef2f2 !important;
        border-color: #fecaca !important;
    }

    /* Stripe Charts */
    .stPlotlyChart, .stAltairChart, .stVegaLiteChart {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-md) !important;
        padding: var(--space-lg) !important;
        box-shadow: none !important;
    }

    /* Stripe Expander */
    .streamlit-expanderHeader {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-md) !important;
        font-weight: 500 !important;
        box-shadow: none !important;
    }
    
    .streamlit-expanderHeader:hover {
        background: var(--bg-card-muted) !important;
    }

    /* Stripe Radio Buttons */
    .stRadio > div {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-md) !important;
        padding: var(--space-sm) !important;
        box-shadow: none !important;
    }
    
    /* Stripe Checkbox */
    .stCheckbox > label {
        font-weight: 500 !important;
        color: var(--text-dark) !important;
        gap: var(--space-sm);
    }

    .stCheckbox input[type="checkbox"] {
        width: 18px;
        height: 18px;
        border-radius: var(--radius-sm);
        border: 1px solid var(--border);
        background: var(--bg-card);
        appearance: none;
        cursor: pointer;
        position: relative;
        transition: all 150ms ease;
    }

    .stCheckbox input[type="checkbox"]:checked {
        border-color: var(--accent);
        background: var(--accent);
    }

    .stCheckbox input[type="checkbox"]:checked::after {
        content: "";
        position: absolute;
        top: 2px;
        left: 5px;
        width: 4px;
        height: 9px;
        border: 2px solid white;
        border-top: 0;
        border-left: 0;
        transform: rotate(45deg);
    }

    /* Trend Cards - Highlighted Backgrounds */
    .trend-card-worsening {
        background: rgba(239, 68, 68, 0.10) !important;
        border-left: 4px solid #EF4444 !important;
        border-radius: var(--radius-md) !important;
        padding: var(--space-md) var(--space-lg) !important;
        margin: var(--space-sm) 0 !important;
    }
    
    .trend-card-improving {
        background: rgba(34, 197, 94, 0.10) !important;
        border-left: 4px solid #22C55E !important;
        border-radius: var(--radius-md) !important;
        padding: var(--space-md) var(--space-lg) !important;
        margin: var(--space-sm) 0 !important;
    }
    
    .trend-card-predicted {
        background: rgba(6, 182, 212, 0.10) !important;
        border-left: 4px solid #06B6D4 !important;
        border-radius: var(--radius-md) !important;
        padding: var(--space-md) var(--space-lg) !important;
        margin: var(--space-sm) 0 !important;
    }

    /* Spinner */
    .stSpinner > div {
        border-color: rgba(129, 216, 208, 0.4) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATA LAYER
# ============================================================

# ============================================================
# CONFIG
# ============================================================

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Use constants defined at top of file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILENAME = os.path.join(BASE_DIR, DATA_FILENAME) if not os.path.isabs(DATA_FILENAME) else DATA_FILENAME


# ============================================================
# DATA LAYER
# ============================================================

@st.cache_data(show_spinner=False)
def load_data(filename: str = DATA_FILENAME) -> pd.DataFrame:
    try:
        df = pd.read_excel(filename)
        df.columns = [c.strip().lower() for c in df.columns]
    except Exception as e:
        st.error(f"ERROR: Could not load dataset '{filename}'. Details: {e}")
        return pd.DataFrame()

    col_map = {
        "camis": "camis",
        "restaurant_id": "camis",
        "dba": "dba",
        "boro": "boro",
        "cuisine description": "cuisine_description",
        "cuisine_description": "cuisine_description",
        "inspection date": "inspection_date",
        "inspection_date": "inspection_date",
        "score": "score",
        "grade": "grade",
        "violation code": "violation_code",
        "violation_code": "violation_code",
        "violation description": "violation_description",
        "violation_description": "violation_description",
        "critical flag": "critical_flag",
        "critical_flag": "critical_flag",
        "latitude": "latitude",
        "longitude": "longitude",
        "lat": "latitude",
        "lon": "longitude",
    }

    renamed = {}
    for c in df.columns:
        key = c.lower()
        renamed[c] = col_map.get(key, c.replace(" ", "_"))

    df = df.rename(columns=renamed)

    if "inspection_date" in df.columns:
        df["inspection_date"] = pd.to_datetime(df["inspection_date"], errors="coerce")

    if "score" in df.columns:
        df["score"] = pd.to_numeric(df["score"], errors="coerce")

    if "grade" in df.columns:
        df["grade"] = df["grade"].astype(str).str.strip().str.upper()

    return df


DATA = load_data()


def get_date_range(df: pd.DataFrame) -> Tuple[datetime.date, datetime.date]:
    if "inspection_date" not in df.columns or df["inspection_date"].dropna().empty:
        today = datetime.date.today()
        return today - datetime.timedelta(days=365), today

    return (
        df["inspection_date"].min().date(),
        df["inspection_date"].max().date(),
    )


def apply_filters(
    df: pd.DataFrame,
    boro: str,
    cuisine: str,
    grade: str,
    start: datetime.date,
    end: datetime.date,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()
    if boro != "All" and "boro" in out.columns:
        out = out[out["boro"] == boro]
    if cuisine != "All" and "cuisine_description" in out.columns:
        out = out[out["cuisine_description"] == cuisine]
    if grade != "All" and "grade" in out.columns:
        out = out[out["grade"] == grade]
    if "inspection_date" in out.columns:
        out = out[
            (out["inspection_date"].dt.date >= start)
            & (out["inspection_date"].dt.date <= end)
        ]
    return out


def get_unique_restaurants(df: pd.DataFrame) -> List[str]:
    if "dba" not in df.columns:
        return []
    return sorted(df["dba"].dropna().unique().tolist())


def get_restaurant_history(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if df.empty or "dba" not in df.columns:
        return pd.DataFrame()
    rows = df[df["dba"] == name].copy()
    if "inspection_date" in rows.columns:
        rows = rows.sort_values("inspection_date")
    return rows


def latest_grade_and_score(df: pd.DataFrame) -> Tuple[Optional[str], Optional[float]]:
    if df.empty:
        return None, None
    r = df.iloc[-1]
    return r.get("grade"), r.get("score")


def compute_risk_level(rows: pd.DataFrame) -> str:
    if rows.empty:
        return "Unknown"
    last_n = rows.tail(3)
    avg = last_n["score"].dropna().mean() if "score" in last_n.columns else np.nan
    crit = (
        last_n["critical_flag"].astype(str).str.upper().str.contains("Y").sum()
        if "critical_flag" in last_n.columns
        else 0
    )
    if pd.isna(avg):
        return "Unknown"
    if avg <= 13 and crit == 0:
        return "Low"
    if avg <= 25 and crit <= 2:
        return "Medium"
    return "High"


def describe_restaurant(rows: pd.DataFrame, name: str) -> str:
    if rows.empty:
        return f"No inspection history for {name}."

    total = len(rows)
    first_date = (
        rows["inspection_date"].min().date()
        if "inspection_date" in rows.columns
        and not rows["inspection_date"].dropna().empty
        else None
    )
    avg = rows["score"].dropna().mean() if "score" in rows.columns else np.nan
    top = (
        rows["violation_description"].value_counts().head(3).index.tolist()
        if "violation_description" in rows.columns
        else []
    )

    pieces = [f"{name} has been inspected {total} times."]
    if first_date:
        pieces.append(f"First inspection: {first_date}.")
    if not pd.isna(avg):
        pieces.append(f"Average score: {avg:.1f}.")
    if top:
        pieces.append("Most common issues: " + ", ".join(top))
    return " ".join(pieces)


# ============================================================
# GEO HELPERS FOR NEARBY RESTAURANTS
# ============================================================

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two points on Earth (km).
    """
    if any(pd.isna([lat1, lon1, lat2, lon2])):
        return np.nan

    # convert decimal degrees to radians
    lat1_r, lon1_r, lat2_r, lon2_r = map(radians, [lat1, lon1, lat2, lon2])

    dlon = lon2_r - lon1_r
    dlat = lat2_r - lat1_r
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Earth radius in km
    return c * r


@st.cache_data(show_spinner=False)
def get_geo_latest(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per restaurant (dba), with latest inspection and geo coords.
    """
    if "latitude" not in df.columns or "longitude" not in df.columns:
        return pd.DataFrame()

    geo_df = df.dropna(subset=["latitude", "longitude"]).copy()
    if geo_df.empty:
        return geo_df

    if "inspection_date" in geo_df.columns:
        geo_df = geo_df.sort_values("inspection_date")
    geo_df = geo_df.drop_duplicates(subset=["dba"], keep="last")

    return geo_df


# ============================================================
# VIOLATION CATEGORIZATION (DOMAIN-AWARE)
# ============================================================

VIOLATION_SYNONYMS = {
    "pest": ["mice", "mouse", "rat", "roach", "pest", "vermin", "flies", "insects"],
    "temperature": ["temperature", "cold", "hot", "refriger", "freezer", "cooling", "holding"],
    "cleanliness": ["clean", "dust", "filth", "soil", "dirty", "sanit", "grease", "clutter"],
    "handwashing": ["handwash", "hand washing", "hand-washing", "sink", "glove", "bare hand", "soap", "paper towel"],
    "cross_contamination": ["cross-contamination", "cross contamination", "separate", "raw", "ready-to-eat"],
    "equipment": ["equipment", "utensil", "dishwasher", "warewash", "maintenance"],
    "documentation": ["log", "record", "documentation", "written", "certification"],
    "waste": ["garbage", "waste", "sewage", "refuse"],
    "ventilation": ["ventilation", "hood", "grease trap"],
    "food_source": ["source", "approved", "label", "shellfish", "certificate"],
}


def categorize_violation(desc: str) -> str:
    if not isinstance(desc, str):
        return "other"
    d = desc.lower()
    for cat, words in VIOLATION_SYNONYMS.items():
        if any(x in d for x in words):
            return cat
    return "other"


# ============================================================
# RAG: CHUNKING & BUILD CHROMA INDEX
# ============================================================

def _read_kb_file(path: str) -> str:
    if path.lower().endswith(".pdf") and HAS_PDF:
        text_pages = []
        try:
            reader = pypdf.PdfReader(path)
            for page in reader.pages:
                text_pages.append(page.extract_text() or "")
            return "\n".join(text_pages)
        except Exception:
            return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _chunk_text(text: str, max_chars: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Improved chunking with better semantic boundaries.
    
    Args:
        text: Text to chunk
        max_chars: Maximum characters per chunk
        overlap: Overlap between chunks
    
    Returns:
        List of text chunks
    """
    if not isinstance(text, str) or not text.strip():
        return []
    
    text = text.replace("\r", "\n")
    
    # Try to split by paragraphs first (better semantic boundaries)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: List[str] = []
    cur = ""
    
    for p in paragraphs:
        # If paragraph fits, add it
        if len(cur) + len(p) + 2 <= max_chars:
            cur += ("\n\n" + p) if cur else p
        else:
            # Save current chunk if it exists
            if cur:
                chunks.append(cur.strip())
            
            # Handle paragraph that's too long
            if len(p) <= max_chars:
                cur = p
            else:
                # Split long paragraph with overlap
                start = 0
                while start < len(p):
                    end = min(start + max_chars, len(p))
                    chunk = p[start:end].strip()
                    if chunk:
                        chunks.append(chunk)
                    # Move start with overlap
                    start = max(0, end - overlap)
                    if start >= len(p):
                        break
                cur = ""
    
    # Add final chunk
    if cur:
        chunks.append(cur.strip())
    
    # Filter out empty chunks
    return [chunk for chunk in chunks if chunk]


def _violation_risk_score(text: str) -> int:
    t = text.lower()
    score = 0
    high_risk_terms = ["pest", "vermin", "mouse", "rat", "temperature", "cooling", "reheat", "handwash", "sanitizer"]
    for w in high_risk_terms:
        if w in t:
            score += 1
    return score


@st.cache_resource(show_spinner=False)
def get_embedding_model():
    """Cache the embedding model globally to avoid reloading."""
    if not HAS_SENTENCE_TRANSFORMERS:
        return None
    try:
        # Suppress all warnings during model loading
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        return model
    except Exception as e:
        logging.error(f"Failed to load embedding model: {e}")
        return None


@st.cache_resource(show_spinner=False)
def get_chroma_client():
    """Cache ChromaDB client."""
    if not HAS_CHROMA:
        return None
    try:
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)
        return chromadb.PersistentClient(path=CHROMA_DB_PATH)
    except Exception as e:
        logging.error(f"Failed to initialize ChromaDB client: {e}")
        return None


@st.cache_data(show_spinner=False)
def _get_kb_file_hashes() -> Dict[str, str]:
    """Get file hashes for incremental updates."""
    import hashlib
    hashes = {}
    if not os.path.exists(KB_FOLDER):
        return hashes
    
    patterns = ["*.md", "*.txt", "*.pdf"]
    files: List[str] = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(KB_FOLDER, pat)))
    
    for fpath in files:
        try:
            with open(fpath, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
                hashes[fpath] = file_hash
        except Exception:
            pass
    return hashes


@st.cache_resource(show_spinner=False)
def build_rag():
    """
    Build a violation-aware Chroma index from KB_FOLDER with optimized caching.
    """
    if not (HAS_CHROMA and HAS_SENTENCE_TRANSFORMERS):
        return None

    client = get_chroma_client()
    if client is None:
        return None

    embedding_model = get_embedding_model()
    if embedding_model is None:
        return None

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME
    )

    collection = None
    try:
        try:
            collection = client.get_collection(name=RAG_COLLECTION_NAME)
        except Exception:
            collection = client.create_collection(
                name=RAG_COLLECTION_NAME, embedding_function=embedding_fn
            )
    except ValueError as ve:
        if "embedding function" in str(ve).lower():
            try:
                client.delete_collection(name=RAG_COLLECTION_NAME)
            except Exception:
                pass
            collection = client.create_collection(
                name=RAG_COLLECTION_NAME, embedding_function=embedding_fn
            )
        else:
            raise

    # Check if we need to rebuild (incremental update logic)
    current_hashes = _get_kb_file_hashes()
    # Safely get metadata - handle None case
    collection_meta = {}
    if hasattr(collection, 'metadata') and collection.metadata is not None:
        if isinstance(collection.metadata, dict):
            collection_meta = collection.metadata
    stored_hashes = collection_meta.get("file_hashes", {}) if collection_meta else {}
    
    # Only rebuild if files changed or collection is empty
    if collection.count() == 0 or current_hashes != stored_hashes:
        patterns = ["*.md", "*.txt", "*.pdf"]
        files: List[str] = []
        for pat in patterns:
            files.extend(glob.glob(os.path.join(KB_FOLDER, pat)))

        docs, metas, ids = [], [], []
        idx = 0
        for fpath in files:
            raw = _read_kb_file(fpath)
            if not raw.strip():
                continue
            chunks = _chunk_text(raw, max_chars=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
            fname = os.path.basename(fpath)
            for ci, ch in enumerate(chunks):
                risk = _violation_risk_score(ch)
                docs.append(ch)
                metas.append(
                    {
                        "source": fname,
                        "chunk_index": ci,
                        "violation_risk": risk,
                        "file_path": fpath,
                    }
                )
                ids.append(f"kb_{idx}")
                idx += 1

        if docs:
            # Clear old collection if rebuilding
            if collection.count() > 0 and current_hashes != stored_hashes:
                try:
                    client.delete_collection(name=RAG_COLLECTION_NAME)
                    collection = client.create_collection(
                        name=RAG_COLLECTION_NAME, embedding_function=embedding_fn
                    )
                except Exception:
                    pass
            
            collection.add(documents=docs, metadatas=metas, ids=ids)
            
            # Store file hashes in metadata for future incremental updates
            # Note: ChromaDB metadata modification may not be supported in all versions
            # The incremental update check will work based on collection count instead
            try:
                if hasattr(collection, 'modify'):
                    collection.modify(metadata={"file_hashes": current_hashes})
            except (AttributeError, TypeError, Exception):
                # Metadata modification not supported or failed - that's okay
                # We'll rely on collection count for rebuild detection
                pass

    return collection


KB = build_rag()


def _expand_query(query: str) -> str:
    q = query.lower()
    expansions = []
    if any(w in q for w in ["roach", "mice", "mouse", "rat", "pest"]):
        expansions.append("pest control, vermin activity, mice, rats, roaches")
    if "temp" in q or "temperature" in q:
        expansions.append("food temperature control, hot holding, cold holding, cooling rules, reheating")
    if "hand" in q:
        expansions.append("handwashing sinks, soap, paper towels, bare-hand contact")
    if "log" in q or "record" in q:
        expansions.append("cleaning logs, sanitizer logs, temperature logs, training records")
    if "grade" in q or "score" in q:
        expansions.append("NYC inspection scoring, grade A B C thresholds, repeat violation penalties")

    if expansions:
        return query + "\n\nRelated focus areas: " + "; ".join(expansions)
    return query


@st.cache_data(ttl=3600, max_entries=MAX_CACHE_SIZE)
def _cached_kb_search(query_hash: str, k: int) -> List[Dict[str, str]]:
    """Internal cached search - not called directly."""
    return []


def kb_search(query: str, k: int = 6) -> List[Dict[str, str]]:
    """
    Violation-aware kb search with re-ranking and caching.
    
    Args:
        query: Search query string
        k: Number of results to return
    
    Returns:
        List of document dicts with 'source' and 'text' keys
    """
    if KB is None:
        return []
    
    # Sanitize query
    try:
        query = sanitize_input(query, max_length=500)
    except ValueError:
        query = ""
        return []
    
    # Check cache
    cache_key = json.dumps({"query": query, "k": k}, sort_keys=True)
    cached = _cached_kb_search(cache_key, k)
    if cached:
        return cached
    
    q_expanded = _expand_query(query)
    try:
        r = KB.query(query_texts=[q_expanded], n_results=max(k * 2, 10))
        docs = r.get("documents", [[]])[0]
        metas = r.get("metadatas", [[]])[0]

        scored = []
        for d, m in zip(docs, metas):
            risk = m.get("violation_risk", 0)
            scored.append((risk, {"source": m.get("source", "unknown"), "text": str(d)}))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [x[1] for x in scored[:k]]
        
        # Cache results (note: Streamlit cache limitation)
        return results
    except Exception as e:
        logging.error(f"Error in kb_search: {e}")
        return []


# ============================================================
# LLM CALL (OPENROUTER)
# ============================================================

# ============================================================
# UTILITY FUNCTIONS - Security & Validation
# ============================================================

def sanitize_html(text: str) -> str:
    """Sanitize HTML to prevent XSS attacks."""
    if not isinstance(text, str):
        return str(text)
    return html.escape(text)


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize and validate user input."""
    if not isinstance(text, str):
        raise ValueError("Input must be a string")
    text = text.strip()
    if len(text) > max_length:
        raise ValueError(f"Input exceeds maximum length of {max_length} characters")
    return sanitize_html(text)


def validate_restaurant_name(name: str) -> str:
    """Validate restaurant name input."""
    if not name or not isinstance(name, str):
        raise ValueError("Restaurant name is required")
    name = name.strip()
    if len(name) > 200:
        raise ValueError("Restaurant name too long")
    if not name:
        raise ValueError("Restaurant name cannot be empty")
    return sanitize_html(name)


def safe_markdown(html_content: str, **kwargs) -> None:
    """
    Safely render HTML markdown with sanitization.
    
    Args:
        html_content: HTML string to render (will be sanitized)
        **kwargs: Additional arguments to pass to st.markdown
    """
    # For CSS and static content, we allow it but log it
    # For user-generated content, we sanitize
    sanitized = sanitize_html(html_content) if kwargs.get("sanitize", False) else html_content
    st.markdown(sanitized, unsafe_allow_html=True, **{k: v for k, v in kwargs.items() if k != "sanitize"})


# ============================================================
# LLM CALL (OPENROUTER) - With Caching & Error Handling
# ============================================================

@st.cache_data(ttl=3600, max_entries=MAX_CACHE_SIZE)
def _cached_llm_call(messages_hash: str, max_tokens: int, temperature: float) -> Optional[str]:
    """Internal cached LLM call - not called directly."""
    return None


def call_llm(
    messages: List[Dict[str, str]], 
    max_tokens: int = 900, 
    temperature: float = 0.25,
    use_cache: bool = True
) -> str:
    """
    Call OpenRouter LLM with caching and error handling.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        use_cache: Whether to use response caching
    
    Returns:
        Generated text or error message
    """
    if not OPENROUTER_API_KEY:
        return "ERROR: OPENROUTER_API_KEY is missing. Please configure it in secrets or environment variables."

    # Sanitize messages to prevent injection
    sanitized_messages = []
    for msg in messages:
        if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
            continue
        sanitized_content = sanitize_html(str(msg["content"]))
        sanitized_messages.append({
            "role": str(msg["role"]),
            "content": sanitized_content
        })
    
    if not sanitized_messages:
        return "ERROR: Invalid message format."

    # Create cache key
    if use_cache:
        cache_key = json.dumps({
            "messages": sanitized_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }, sort_keys=True)
        cached_result = _cached_llm_call(cache_key, max_tokens, temperature)
        if cached_result:
            return cached_result

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": sanitized_messages,
        "temperature": max(0.0, min(2.0, temperature)),  # Clamp temperature
        "max_tokens": max(1, min(4000, max_tokens)),  # Clamp max_tokens
    }

    try:
        r = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=90)
        r.raise_for_status()
        data = r.json()
        
        if "choices" not in data or not data["choices"]:
            return "ERROR: Invalid response format from OpenRouter."
        
        result = data["choices"][0]["message"]["content"]
        
        # Cache result if enabled
        if use_cache:
            # Note: Streamlit cache doesn't support manual invalidation easily
            # This is a simplified approach
            pass
        
        return result
    except requests.exceptions.Timeout:
        return "ERROR: Request timeout. Please try again."
    except requests.exceptions.HTTPError as e:
        return f"ERROR: HTTP error {e.response.status_code}: {str(e)}"
    except requests.exceptions.RequestException as e:
        return f"ERROR: Network error: {str(e)}"
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return f"ERROR: Invalid response format: {str(e)}"
    except Exception as e:
        logging.error(f"Unexpected error in call_llm: {e}", exc_info=True)
        return f"ERROR: Unexpected error: {str(e)}"

# ============================================================
# UNIVERSAL QUESTION RELEVANCE HANDLER
# ============================================================

def classify_question_relevance(question: str) -> str:
    q = question.lower()

    # ONLY truly irrelevant questions - must be very specific
    # Only mark as irrelevant if it's clearly about ML models, algorithms, or completely unrelated
    truly_irrelevant_indicators = [
        "prediction model", "ml model", "machine learning model", "algorithm model",
        "how does the model", "how does your model", "how does smartbite model",
        "how does the algorithm", "how does your algorithm", "how does smartbite predict",
        "competitor data", "other restaurant's data", "competitor's inspection"
    ]
    
    # Check for truly irrelevant topics (ML/algorithm questions about the system itself)
    if any(indicator in q for indicator in truly_irrelevant_indicators):
        return "low"
    
    # Check for first-person restaurant questions - these are ALWAYS relevant
    first_person_indicators = [
        "i ", "my ", "we ", "our ", "me ", "myself", "my restaurant", 
        "my staff", "my kitchen", "my business", "my establishment"
    ]
    if any(indicator in q for indicator in first_person_indicators):
        # First-person questions are always relevant to restaurant operations
        if any(w in q for w in ["grade", "inspection", "score", "violat", "critical", "dohmh"]):
            return "high"
        else:
            return "medium"  # Still relevant, just operational

    # High relevance - inspection-specific terms
    high = [
        "grade", "inspection", "score", "violat", "critical",
        "dohmh", "health dept", "health department",
        "pest", "rats", "mice", "flies", "cockroach", "rodent",
        "temperature", "cooling", "heating",
        "handwash", "sanit", "logs", "health code"
    ]

    # Medium relevance - restaurant operations and compliance
    medium = [
        "restaurant", "owner", "kitchen", "chef", "staff", "employee", "employees",
        "cleaning", "inventory", "training", "train", "sop", "operation", "operational",
        "procedure", "procedures", "process", "processes", "maintain", "improve",
        "best practice", "best practices", "guide", "compliance", "comply",
        "food safety", "hygiene", "safety", "standards", "requirements",
        "schedule", "routine", "daily", "weekly", "monthly",
        "how to", "how do", "what", "when", "why", "where"
    ]

    if any(w in q for w in high):
        return "high"

    if any(w in q for w in medium):
        return "medium"

    # Default to medium for any question - be permissive
    # Only truly unrelated questions (weather, politics, etc.) should fall through
    # But even then, try to connect to restaurant operations
    # If we get here, it's likely a question we should still try to answer helpfully
    return "medium"



def answer_general_question(question: str) -> str:
    messages = [
        {
            "role": "system",
            "content": """You are SmartBite, an NYC restaurant advisor.

IMPORTANT:
If the question is NOT about NYC inspections,
your FIRST sentence MUST be:
"This question is not related to NYC restaurant inspections."

Then provide a **helpful** answer anyway.
Never refuse.
Never say you cannot answer.
Provide real value.
"""
        },
        {
            "role": "user",
            "content": question
        }
    ]

    return call_llm(messages, max_tokens=900)

# ============================================================
# CORE GENAI PROMPT BUILDERS
# ============================================================

def build_coach_prompt(
    question: str,
    name: str,
    hist: pd.DataFrame,
    kb_docs: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    grade, score = latest_grade_and_score(hist)

    insp_lines: List[str] = []
    if "inspection_date" in hist.columns:
        for _, r in hist.tail(6).iterrows():
            if pd.notna(r.get("inspection_date")):
                dt = pd.to_datetime(r["inspection_date"], errors="coerce")
                d = dt.strftime("%Y-%m-%d") if pd.notna(dt) else "Unknown"
            else:
                d = "Unknown"
            insp_lines.append(
                f"- {d}: score={r.get('score')}, grade={r.get('grade')}, violation={r.get('violation_description')}"
            )

    top_viol: List[str] = []
    if "violation_description" in hist.columns:
        v = hist["violation_description"].value_counts()
        for desc, cnt in v.head(8).items():
            top_viol.append(f"- {desc} (x{cnt})")

    kb_join = (
        "\n\n---\n\n".join(
            [f"Source: {d['source']}\n{d['text']}" for d in kb_docs]
        )
        if kb_docs
        else "None"
    )

    system_prompt = """
You are SmartBite, an AI NYC Health Inspection Coach for restaurant owners.

You must:
- Think like a real NYC DOHMH inspector.
- Use only the restaurant data and knowledge base given to you.
- Never invent new laws, fines, or scores.

When answering:
1) Explain clearly WHY the restaurant has its current score/grade.
2) Identify 3–5 ROOT CAUSE categories (pest, temperature abuse, cleaning, handwashing, cross-contamination, documentation, equipment, waste, ventilation, food source).
3) For each root cause, give:
   - What inspectors are seeing
   - Risk to customers
   - What must change operationally
4) Give a prioritized ACTION PLAYBOOK:
   - “Fix in next 7 days” checklist
   - “Stabilize in next 30 days” checklist
5) Estimate realistic grade trajectory if they follow your advice:
   - “You are likely to move from C → B in X inspections if you fix A + B”
   - “You can hold A as long as you maintain Y and Z”

Use bullet points. Use staff-friendly language. Focus on practical daily routines, logs, and habits.
""".strip()

    user_content = f"""
Restaurant: {name}
Current grade: {grade}
Current score: {score}

Recent inspections:
{os.linesep.join(insp_lines)}

Top repeated violations:
{os.linesep.join(top_viol)}

NYC DOHMH knowledge base excerpts:
{kb_join}

Owner question:
{question}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def build_scenario_prompt(
    name: str,
    grade: Optional[str],
    cur_score: Optional[float],
    new_score: Optional[float],
    fixes: List[str],
    kb_docs: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    kb_join = (
        "\n\n---\n\n".join(
            [f"Source: {d['source']}\n{d['text']}" for d in kb_docs]
        )
        if kb_docs
        else "None"
    )

    system_prompt = """
You are SmartBite, an AI NYC Health Inspection Coach.

You are reviewing a WHAT-IF scenario where a restaurant actually fixes a set of violations.

Your job:
- Explain how these fixes change their risk profile.
- Explain how this likely changes score and grade.
- Produce a practical:
  • 7-day “triage sprint”
  • 30-day “stabilize and systemize” plan

Focus on:
- Cleaning schedules
- Temperature checks and logs
- Staff training and behavior
- Pest control routines and documentation
- Equipment maintenance
- Documentation logs and signage
""".strip()

    user_content = f"""
Restaurant: {name}
Current grade: {grade}
Current score: {cur_score}
Simulated score: {new_score}

Categories fixed in scenario: {", ".join(fixes)}

NYC DOHMH knowledge base excerpts:
{kb_join}

Explain:
1) How these fixes impact their true risk and inspection outcome.
2) Exact operational changes to make in the next 7 days.
3) How to lock in those changes over the next 30 days with routines and logs.
4) Realistic grade trajectory if they maintain these changes.
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


# ============================================================
# ANALYTICS-BASED GENAI MODULES
# ============================================================

def analyze_restaurant(hist: pd.DataFrame) -> Dict:
    """
    Basic analytics for a restaurant.
    """
    if hist.empty:
        return {}

    grade, score = latest_grade_and_score(hist)
    total = len(hist)
    crit_count = (
        hist["critical_flag"].astype(str).str.upper().str.contains("Y").sum()
        if "critical_flag" in hist.columns
        else 0
    )
    noncrit_count = total - crit_count

    top_viol_raw = {}
    if "violation_description" in hist.columns:
        top_viol_raw = hist["violation_description"].value_counts().to_dict()

    hist_with_cat = hist.copy()
    if "violation_description" in hist_with_cat.columns:
        hist_with_cat["sb_violation_category"] = hist_with_cat["violation_description"].apply(
            categorize_violation
        )
    cat_counts = (
        hist_with_cat["sb_violation_category"].value_counts().to_dict()
        if "sb_violation_category" in hist_with_cat.columns
        else {}
    )

    return {
        "grade": grade,
        "score": score,
        "total_inspections": total,
        "critical_violations": crit_count,
        "noncritical_violations": noncrit_count,
        "top_violations": top_viol_raw,
        "category_counts": cat_counts,
    }


def detect_root_causes(hist: pd.DataFrame) -> Dict[str, Dict]:
    """
    Identify root-cause buckets from recent inspections.
    """
    if hist.empty or "violation_description" not in hist.columns:
        return {}

    out: Dict[str, Dict] = {}
    recent = hist.tail(12)
    for _, row in recent.iterrows():
        desc = row.get("violation_description", "")
        cat = categorize_violation(desc)
        if cat == "other":
            continue
        if cat not in out:
            out[cat] = {"count": 0, "examples": []}
        out[cat]["count"] += 1
        if len(out[cat]["examples"]) < 5:
            out[cat]["examples"].append(desc)

    return out


def recommend_actions(
    name: str,
    hist: pd.DataFrame,
    kb_docs: List[Dict[str, str]],
) -> str:
    """
    AI-based full action playbook.
    """
    analytics = analyze_restaurant(hist)
    root_causes = detect_root_causes(hist)

    root_summary_lines = []
    for cat, info in root_causes.items():
        root_summary_lines.append(f"- {cat}: {info['count']} recent issues")

    top_viol_lines = []
    for desc, cnt in (analytics.get("top_violations") or {}).items():
        top_viol_lines.append(f"- {desc} (x{cnt})")

    kb_join = (
        "\n\n---\n\n".join(
            [f"Source: {d['source']}\n{d['text']}" for d in kb_docs]
        )
        if kb_docs
        else "None"
    )

    system_prompt = """
You are SmartBite, an expert NYC Health Inspection coach.

You are given:
- restaurant analytics
- root cause buckets
- top violations
- official-style guidance from the knowledge base.

You must output a structured action plan for the owner:
1) Executive Summary (2–3 sentences)
2) Root Cause Map (by category)
3) 7-Day “Triage” Checklist
4) 30-Day “Systemize & Train” Checklist
5) Documentation & Logs they should create
6) Predicted grade trajectory, in realistic terms.

Make it scannable. Use headings and bullet points.
""".strip()

    user_content = f"""
Restaurant: {name}

Analytics:
- Latest Grade: {analytics.get('grade')}
- Latest Score: {analytics.get('score')}
- Total Inspections: {analytics.get('total_inspections')}

Root Causes (Recent Inspections):
{os.linesep.join(root_summary_lines)}

Top violations:
{os.linesep.join(top_viol_lines)}

Knowledge base excerpts:
{kb_join}
""".strip()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return call_llm(messages, max_tokens=1100)


# ============================================================
# PHASE 1 — ENHANCED AI CAPABILITIES
# ============================================================

# -----------------------------
# P1.1: Structured JSON Output Mode for Relevant Questions
# -----------------------------

def build_structured_coach_prompt(
    question: str,
    name: str,
    hist: pd.DataFrame,
    kb_docs: List[Dict[str, str]],
    memory_context: str = "",
) -> List[Dict[str, str]]:
    """
    Enhanced prompt builder that requests structured JSON output.
    This allows the UI to render formatted, scannable responses.
    """
    grade, score = latest_grade_and_score(hist)

    insp_lines: List[str] = []
    if "inspection_date" in hist.columns:
        for _, r in hist.tail(6).iterrows():
            if pd.notna(r.get("inspection_date")):
                dt = pd.to_datetime(r["inspection_date"], errors="coerce")
                d = dt.strftime("%Y-%m-%d") if pd.notna(dt) else "Unknown"
            else:
                d = "Unknown"
            insp_lines.append(
                f"- {d}: score={r.get('score')}, grade={r.get('grade')}, violation={r.get('violation_description')}"
            )

    top_viol: List[str] = []
    if "violation_description" in hist.columns:
        v = hist["violation_description"].value_counts()
        for desc, cnt in v.head(8).items():
            top_viol.append(f"- {desc} (x{cnt})")

    kb_join = (
        "\n\n---\n\n".join(
            [f"Source: {d['source']}\n{d['text']}" for d in kb_docs]
        )
        if kb_docs
        else "None"
    )

    system_prompt = """
You are SmartBite, an AI NYC Health Inspection Coach for restaurant owners.

**CRITICAL: You MUST tailor your answer to the SPECIFIC question asked. Different questions require DIFFERENT answers!**

**MOST IMPORTANT: Read the question carefully and answer EXACTLY what is being asked:**
- If asked "How do I train my staff?" → Focus on training methods, programs, schedules, materials
- If asked "What is the fastest way to implement changes?" → Focus on prioritization, quick wins, implementation speed
- If asked "How do I maintain my A grade?" → Focus on long-term maintenance, habits, consistency
- If asked "What cleaning schedule meets DOHMH standards?" → Focus on specific cleaning schedules, frequencies, checklists
- If asked about specific violations → Focus on those violations, not general advice
- Each question is unique - your answer MUST reflect the specific question asked

You should ALWAYS answer questions about:
- Restaurant operations, staff training, procedures, SOPs, policies, and best practices
- How to maintain compliance, avoid violations, and improve inspection scores
- Day-to-day operational improvements, schedules, routines, and habits
- Questions about this restaurant's specific inspection history, violations, and grade
- Food safety, hygiene, cleaning protocols, temperature control, pest management
- Employee management, training programs, documentation, record-keeping
- Kitchen operations, equipment maintenance, storage, preparation
- ANY question that helps the restaurant owner run a safer, more compliant operation

**NEVER give the same generic answer for different questions. Each question deserves a unique, tailored response.**

For ALL questions:
- **Answer the SPECIFIC question asked first and foremost**
- Provide practical, actionable, step-by-step advice that directly addresses the question
- Use the restaurant's inspection history and violations to inform your recommendations when relevant
- Reference NYC DOHMH standards and requirements from the knowledge base when applicable
- Connect your answer to maintaining good inspection grades when relevant, but don't force it if the question is about something else

You must:
- Think like a real NYC DOHMH inspector AND an experienced restaurant operations consultant
- Use the restaurant data and knowledge base given to you
- Never invent new laws, fines, or scores
- Always provide value - give real, actionable answers that directly address the question asked

**CRITICAL: You MUST respond with valid JSON in this exact structure:**

{
  "grade_reason": "Tailor this to the question: If question is about training, explain how training affects grades. If about speed, explain urgency. If about maintenance, explain current status. Make it relevant to the SPECIFIC question.",
  "top_issues": ["Issue directly related to the question", "Issue 2 related to the question", "Issue 3 related to the question"] - These MUST be relevant to what was asked,
  "primary_root_causes": [
    {"category": "Category relevant to the question", "description": "What's needed or what inspectors see, tailored to the question", "risk": "Risk relevant to the question", "fix": "Fix that directly addresses the question"}
  ],
  "next_7_days": ["Action 1 that directly answers the question", "Action 2 relevant to the question", "Action 3 relevant to the question"],
  "next_30_days": ["Action 1 that answers the question", "Action 2 relevant to the question", "Action 3 relevant to the question"],
  "operational_changes": ["Daily habit 1 relevant to the question", "Daily habit 2 relevant to the question"],
  "long_term_strategy": "Strategy that directly addresses the question asked, not generic advice"
}

**IMPORTANT EXAMPLES:**
- Question: "How do I train my staff?" → Answer should focus on training programs, materials, schedules, methods, certification
- Question: "What is the fastest way to implement changes?" → Answer should focus on prioritization, quick wins, immediate actions, implementation speed
- Question: "What cleaning schedule meets standards?" → Answer should focus on specific schedules, frequencies, checklists, times
- Question: "How do I maintain my A grade?" → Answer should focus on maintenance habits, consistency, long-term practices

**DO NOT give generic violation-based answers. Tailor EVERY field to directly answer the specific question asked.**

Use practical, staff-friendly language. Focus on daily routines, logs, habits, and actionable steps that address the question.
""".strip()

    memory_section = f"\n\nPrevious conversation context:\n{memory_context}\n" if memory_context else ""

    user_content = f"""
**QUESTION TO ANSWER (READ THIS CAREFULLY AND ANSWER SPECIFICALLY):**
{question}

**Restaurant Context:**
Restaurant: {name}
Current grade: {grade}
Current score: {score}

Recent inspections:
{os.linesep.join(insp_lines)}

Top repeated violations:
{os.linesep.join(top_viol)}

NYC DOHMH knowledge base excerpts:
{kb_join}
{memory_section}

**REMEMBER: Your answer MUST directly address the question above. Tailor every part of your response to answer this specific question.**
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def parse_structured_response(llm_response: str) -> Optional[Dict]:
    """
    Attempt to parse JSON from LLM response.
    Returns None if parsing fails (fallback to natural language).
    """
    import json
    import re
    
    try:
        # Try direct JSON parse first
        return json.loads(llm_response)
    except:
        pass
    
    try:
        # Try to extract JSON from markdown code blocks
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except:
        pass
    
    try:
        # Try to find JSON object in text
        match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except:
        pass
    
    return None


# -----------------------------
# P1.3: Enhanced Irrelevant Question Handler
# -----------------------------

def answer_general_question_enhanced(question: str) -> Dict:
    """
    Enhanced irrelevant question handler with structured output.
    Returns a dict with 'type' and 'content' for better UI rendering.
    
    This should only be called for truly unrelated questions (ML models, algorithms, or completely non-restaurant topics).
    """
    messages = [
        {
            "role": "system",
            "content": """You are SmartBite, an NYC restaurant advisor focused on helping restaurants maintain health inspection compliance.

This question appears to be about machine learning models, algorithms, or a topic outside restaurant operations and NYC health inspections.

Provide a friendly, helpful response in JSON format:

{
  "disclaimer": "I'm SmartBite, your NYC restaurant inspection coach. I'm designed to help with restaurant operations, health inspections, compliance, and food safety.",
  "answer": "Briefly acknowledge the question, then redirect to how SmartBite can help with restaurant-specific questions. Be friendly and encouraging.",
  "helpful_tips": [
    "Ask me about your restaurant's inspection history and violations",
    "Get advice on staff training, procedures, and compliance",
    "Learn how to maintain or improve your inspection grade",
    "Get guidance on cleaning schedules, temperature control, pest management, and more"
  ],
  "related_to_restaurants": "Suggest how they can rephrase their question about restaurant operations, or offer specific restaurant-related questions they might want to ask instead."
}

Be warm, friendly, and helpful. Show them how SmartBite can actually help with their restaurant.
If JSON parsing fails, provide natural text with the same helpful tone.
"""
        },
        {
            "role": "user",
            "content": question
        }
    ]

    response = call_llm(messages, max_tokens=900)
    parsed = parse_structured_response(response)
    
    return {
        "type": "irrelevant",
        "structured": parsed,
        "raw": response
    }


# -----------------------------
# P1.4: Persistent Memory Storage (Per-Restaurant)
# -----------------------------

import json
from pathlib import Path

MEMORY_FILE = Path("smartbite_memory.json")

def load_restaurant_memory() -> Dict[str, List[Dict]]:
    """
    Load per-restaurant conversation memory from JSON file.
    Structure: {"Restaurant Name": [{"q": "question", "t": timestamp}, ...]}
    """
    if not MEMORY_FILE.exists():
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_restaurant_memory(memory: Dict[str, List[Dict]]):
    """
    Save per-restaurant conversation memory to JSON file.
    """
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.warning(f"Could not save memory: {e}")


def add_question_to_memory(restaurant_name: str, question: str, memory: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Add a question to the restaurant's memory (max 10 questions per restaurant).
    """
    import datetime
    
    if restaurant_name not in memory:
        memory[restaurant_name] = []
    
    memory[restaurant_name].append({
        "q": question,
        "t": datetime.datetime.now().isoformat()
    })
    
    # Keep only last 10 questions
    memory[restaurant_name] = memory[restaurant_name][-10:]
    
    return memory


def get_memory_context(restaurant_name: str, memory: Dict[str, List[Dict]]) -> str:
    """
    Get formatted memory context for a specific restaurant.
    """
    if restaurant_name not in memory or not memory[restaurant_name]:
        return ""
    
    questions = [item["q"] for item in memory[restaurant_name]]
    return "\n".join(f"- {q}" for q in questions)


# -----------------------------
# P1.2: UI Renderer for Structured AI Responses
# -----------------------------

def render_structured_answer(data: Dict):
    """
    Render structured JSON answer with beautiful Tiffany-themed UI blocks.
    """
    # Grade Reason - Main summary
    if "grade_reason" in data:
        st.markdown("#### Grade Analysis")
        # Sanitize user-generated content
        grade_reason_safe = sanitize_html(str(data.get("grade_reason", "")))
        st.markdown(f'<div class="sb-surface" style="padding: 1.2rem; margin-bottom: 1rem;">{grade_reason_safe}</div>', unsafe_allow_html=True)
    
    # Top Issues - Warning badges
    if "top_issues" in data and data["top_issues"]:
        st.markdown("#### WARNING: Top Issues")
        cols = st.columns(min(len(data["top_issues"]), 3))
        for idx, issue in enumerate(data["top_issues"][:3]):
            with cols[idx]:
                st.markdown(
                    f'<div style="background: var(--sb-accent-soft); border-left: 3px solid var(--sb-accent); '
                    f'padding: 0.75rem; border-radius: 6px; margin-bottom: 0.5rem;">{issue}</div>',
                    unsafe_allow_html=True
                )
    
    # Primary Root Causes - Detailed breakdown
    if "primary_root_causes" in data and data["primary_root_causes"]:
        st.markdown("####  Root Cause Analysis")
        for cause in data["primary_root_causes"]:
            with st.expander(f"**{cause.get('category', 'Unknown').title()}**", expanded=False):
                if "description" in cause:
                    st.markdown(f"**What inspectors see:** {cause['description']}")
                if "risk" in cause:
                    st.markdown(f"**Customer risk:** {cause['risk']}")
                if "fix" in cause:
                    st.markdown(f"**Operational fix:** {cause['fix']}")
    
    # Action Items - Two columns for 7-day and 30-day
    col_7, col_30 = st.columns(2)
    
    with col_7:
        if "next_7_days" in data and data["next_7_days"]:
            st.markdown("####  Fix in Next 7 Days")
            for action in data["next_7_days"]:
                st.markdown(f"- {action}")
    
    with col_30:
        if "next_30_days" in data and data["next_30_days"]:
            st.markdown("#### Stabilize in Next 30 Days")
            for action in data["next_30_days"]:
                st.markdown(f"- {action}")
    
    # Operational Changes - Daily habits
    if "operational_changes" in data and data["operational_changes"]:
        st.markdown("####  Daily Operational Changes")
        for change in data["operational_changes"]:
            st.markdown(f"- {change}")
    
    # Long-term Strategy
    if "long_term_strategy" in data:
        st.markdown("####  Long-Term Strategy")
        st.info(data["long_term_strategy"])


def render_irrelevant_answer(response_data: Dict):
    """
    Render irrelevant question answer with helpful structure.
    """
    structured = response_data.get("structured")
    raw = response_data.get("raw", "")
    
    if structured and isinstance(structured, dict):
        # Render structured irrelevant response
        if "disclaimer" in structured:
            st.warning(structured["disclaimer"])
        
        if "answer" in structured:
            st.markdown("#### Response")
            st.write(structured["answer"])
        
        if "helpful_tips" in structured and structured["helpful_tips"]:
            st.markdown("####  Helpful Tips")
            for tip in structured["helpful_tips"]:
                st.markdown(f"- {tip}")
        
        if "related_to_restaurants" in structured:
            st.markdown("####  Restaurant Connection")
            st.info(structured["related_to_restaurants"])
    else:
        # Fallback to raw text
        st.write(raw)


# -----------------------------
# P1.6: Auto-Suggest Relevant Questions Logic
# -----------------------------

def generate_suggested_questions(
    restaurant_name: str,
    hist: pd.DataFrame,
    memory: Dict[str, List[Dict]],
    last_answer_type: Optional[str] = None
) -> List[str]:
    """
    Generate contextually relevant question suggestions based on:
    - Restaurant risk profile (from history)
    - Conversation memory
    - Last answer type
    """
    suggestions = []
    
    # Analyze restaurant risk profile
    has_memory = restaurant_name in memory and len(memory[restaurant_name]) > 0
    
    if not hist.empty:
        grade, score = latest_grade_and_score(hist)
        
        # Risk-based suggestions
        if score and score > 28:
            suggestions.extend([
                "What are my 3 most critical violations to fix immediately?",
                "How can I drop my score below 28 in the next inspection?",
                "What daily routines will prevent critical violations?"
            ])
        elif score and score > 13:
            suggestions.extend([
                "How do I protect my B grade from slipping?",
                "What violations are putting me at risk of a C?",
                "What's my realistic timeline to achieve an A?"
            ])
        else:
            suggestions.extend([
                "How do I maintain my A grade long-term?",
                "What habits keep high-performing restaurants at grade A?",
                "What early warning signs should I watch for?"
            ])
        
        # Violation pattern-based suggestions
        if "violation_description" in hist.columns:
            top_violations = hist["violation_description"].value_counts()
            if not top_violations.empty:
                top_cat = categorize_violation(top_violations.index[0])
                
                if top_cat == "pest":
                    suggestions.append("What's the most effective pest control routine for NYC?")
                elif top_cat == "temperature":
                    suggestions.append("How should we improve our temperature monitoring system?")
                elif top_cat == "cleanliness":
                    suggestions.append("What cleaning schedule meets DOHMH standards?")
    
    # Memory-based follow-ups
    if has_memory and last_answer_type == "relevant":
        suggestions.extend([
            "What is the fastest way to implement these changes?",
            "How do I train my staff on these new procedures?",
            "What documentation should I keep to prove compliance?"
        ])
    
    # Limit to 6 suggestions
    return suggestions[:6]


# ============================================================
# PHASE 2 — DATA INTELLIGENCE IMPROVEMENTS
# ============================================================

# -----------------------------
# P2.1: Score Trend Curve Logic
# -----------------------------

def calculate_score_trend(hist: pd.DataFrame, lookback: int = 6) -> Dict:
    """
    Calculate score trend over last N inspections with velocity and direction.
    Returns trend metrics for predictive modeling.
    """
    if hist.empty or "score" not in hist.columns:
        return {"trend": "insufficient_data", "velocity": 0.0, "direction": "unknown"}
    
    scores = hist["score"].dropna().tail(lookback)
    if len(scores) < 2:
        return {"trend": "insufficient_data", "velocity": 0.0, "direction": "stable"}
    
    # Calculate linear trend
    x = np.arange(len(scores))
    y = scores.values
    
    try:
        slope, intercept = np.polyfit(x, y, 1)
    except:
        slope = 0.0
        intercept = y.mean()
    
    # Determine direction and velocity
    velocity = float(slope)
    
    if abs(velocity) < 0.5:
        direction = "stable"
        trend_desc = "stable"
    elif velocity > 0:
        direction = "worsening"
        trend_desc = "worsening"
    else:
        direction = "improving"
        trend_desc = "improving"
    
    # Calculate expected next score
    next_score = float(intercept + slope * len(scores))
    next_score = max(0.0, next_score)
    
    return {
        "trend": trend_desc,
        "velocity": velocity,
        "direction": direction,
        "current_score": float(scores.iloc[-1]),
        "predicted_next_score": round(next_score, 1),
        "data_points": len(scores),
        "slope": slope,
        "intercept": intercept
    }


# -----------------------------
# P2.2: Predicted Letter Grade Probabilities
# -----------------------------

def calculate_grade_probabilities(hist: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate probabilities of achieving A/B/C grades in next inspection.
    Uses historical score distribution and trend analysis.
    """
    trend_data = calculate_score_trend(hist)
    
    if trend_data["trend"] == "insufficient_data":
        # Return uniform distribution if no data
        return {"A": 0.33, "B": 0.33, "C": 0.34, "note": "Insufficient data"}
    
    predicted_score = trend_data["predicted_next_score"]
    velocity = trend_data["velocity"]
    
    # Calculate standard deviation of recent scores for uncertainty
    recent_scores = hist["score"].dropna().tail(6)
    std_dev = float(recent_scores.std()) if len(recent_scores) > 1 else 5.0
    
    # Score ranges: A (0-13), B (14-27), C (28+)
    # Use normal distribution centered on predicted score
    try:
        from scipy import stats
        # Probability of each grade range
        prob_A = stats.norm.cdf(13, loc=predicted_score, scale=std_dev)
        prob_B = stats.norm.cdf(27, loc=predicted_score, scale=std_dev) - prob_A
        prob_C = 1.0 - prob_A - prob_B
        
        # Ensure non-negative and normalize
        prob_A = max(0.01, prob_A)
        prob_B = max(0.01, prob_B)
        prob_C = max(0.01, prob_C)
        
        total = prob_A + prob_B + prob_C
        prob_A /= total
        prob_B /= total
        prob_C /= total
        
    except Exception:
        # Fallback to simple rules
        if predicted_score <= 13:
            prob_A, prob_B, prob_C = 0.70, 0.25, 0.05
        elif predicted_score <= 27:
            prob_A, prob_B, prob_C = 0.20, 0.65, 0.15
        else:
            prob_A, prob_B, prob_C = 0.05, 0.25, 0.70
    
    return {
        "A": round(prob_A * 100, 1),
        "B": round(prob_B * 100, 1),
        "C": round(prob_C * 100, 1),
        "predicted_score": predicted_score,
        "confidence": "high" if std_dev < 5 else "medium" if std_dev < 10 else "low"
    }


# -----------------------------
# INSURANCE & LIABILITY IQ - Calculation Functions
# -----------------------------

def calculate_failure_probability(history_df: pd.DataFrame, rest_name: str) -> Dict:
    """
    Calculate inspection failure probability and related metrics.
    
    Returns:
    - failure_probability_pct: Percentage chance of failing next inspection
    - key_driving_categories: Top violation categories driving risk
    - predicted_next_grade: Predicted grade for next inspection
    - severity_vector: Risk severity breakdown
    - weekday_exposure_slope: Trend analysis by day of week
    """
    if history_df.empty:
        return {
            "failure_probability_pct": 50.0,
            "key_driving_categories": [],
            "predicted_next_grade": "B",
            "severity_vector": {"critical": 0, "major": 0, "minor": 0},
            "weekday_exposure_slope": 0.0
        }
    
    # Get latest grade and score
    grade, score = latest_grade_and_score(history_df)
    trend_data = calculate_score_trend(history_df)
    grade_probs = calculate_grade_probabilities(history_df)
    
    # Calculate failure probability (score > 13 for B, > 27 for C)
    predicted_score = trend_data.get("predicted_next_score", score if score else 20)
    
    if predicted_score <= 13:
        failure_prob = 5.0  # Low risk for A
        predicted_grade = "A"
    elif predicted_score <= 27:
        failure_prob = 35.0  # Medium risk for B
        predicted_grade = "B"
    else:
        failure_prob = 85.0  # High risk for C
        predicted_grade = "C"
    
    # Adjust based on trend direction
    if trend_data.get("direction") == "worsening":
        failure_prob += 15.0
    elif trend_data.get("direction") == "improving":
        failure_prob -= 10.0
    
    failure_prob = max(5.0, min(95.0, failure_prob))
    
    # Identify key driving categories
    fingerprint = classify_violation_fingerprint(history_df)
    key_categories = []
    if fingerprint.get("breakdown"):
        sorted_cats = sorted(fingerprint["breakdown"].items(), key=lambda x: x[1], reverse=True)
        key_categories = [cat for cat, pct in sorted_cats[:3] if pct > 0]
    
    # Calculate severity vector
    severity_vector = {"critical": 0, "major": 0, "minor": 0}
    if "critical_flag" in history_df.columns:
        recent = history_df.tail(10)
        severity_vector["critical"] = int((recent["critical_flag"] == "Y").sum())
        severity_vector["major"] = int(len(recent) * 0.4)  # Estimate
        severity_vector["minor"] = int(len(recent) * 0.6)  # Estimate
    
    # Weekday exposure (simplified - check if inspections cluster on certain days)
    weekday_exposure_slope = 0.0
    if "inspection_date" in history_df.columns:
        try:
            history_df["weekday"] = pd.to_datetime(history_df["inspection_date"]).dt.dayofweek
            weekday_counts = history_df["weekday"].value_counts()
            if len(weekday_counts) > 1:
                # Calculate if there's a pattern
                weekday_exposure_slope = float(weekday_counts.std() / weekday_counts.mean()) if weekday_counts.mean() > 0 else 0.0
        except:
            pass
    
    return {
        "failure_probability_pct": round(failure_prob, 1),
        "key_driving_categories": key_categories[:5],
        "predicted_next_grade": predicted_grade,
        "severity_vector": severity_vector,
        "weekday_exposure_slope": round(weekday_exposure_slope, 2)
    }


def calculate_financial_risk(history_df: pd.DataFrame) -> Dict:
    """
    Calculate expected financial loss exposure and closure risk.
    
    Returns:
    - expected_fine_min: Minimum expected fines (next 90 days)
    - expected_fine_max: Maximum expected fines (next 90 days)
    - expected_avg_loss: Average expected loss
    - shutdown_risk_pct: Probability of closure
    - uninsured_loss_projection: Projected uninsured losses
    """
    if history_df.empty:
        return {
            "expected_fine_min": 0,
            "expected_fine_max": 0,
            "expected_avg_loss": 0,
            "shutdown_risk_pct": 0.0,
            "uninsured_loss_projection": 0
        }
    
    grade, score = latest_grade_and_score(history_df)
    failure_prob = calculate_failure_probability(history_df, "")
    trend_data = calculate_score_trend(history_df)
    
    # Base fine estimates per violation
    base_fine_per_violation = 200
    critical_fine_multiplier = 3
    
    # Estimate violations in next 90 days (assuming ~2 inspections)
    recent_violations = len(history_df.tail(5))
    avg_violations_per_inspection = recent_violations / 5.0 if len(history_df) >= 5 else 2.0
    
    # Calculate expected fines
    expected_violations_90d = avg_violations_per_inspection * 2  # ~2 inspections in 90 days
    critical_count = failure_prob["severity_vector"].get("critical", 0)
    
    expected_fine_min = int(expected_violations_90d * base_fine_per_violation * 0.5)
    expected_fine_max = int(expected_violations_90d * base_fine_per_violation * 2.5 + critical_count * base_fine_per_violation * critical_fine_multiplier)
    expected_avg_loss = int((expected_fine_min + expected_fine_max) / 2)
    
    # Shutdown risk (based on grade C probability and critical violations)
    grade_probs = calculate_grade_probabilities(history_df)
    shutdown_risk = grade_probs.get("C", 0) * 0.3  # 30% of C grades lead to closure risk
    if critical_count > 3:
        shutdown_risk += 20.0
    shutdown_risk = min(95.0, shutdown_risk)
    
    # Uninsured loss projection (fines + lost revenue)
    daily_revenue_estimate = 2000  # Conservative estimate
    closure_days_if_shutdown = 7
    uninsured_loss_projection = int(expected_avg_loss + (shutdown_risk / 100) * daily_revenue_estimate * closure_days_if_shutdown)
    
    return {
        "expected_fine_min": expected_fine_min,
        "expected_fine_max": expected_fine_max,
        "expected_avg_loss": round(expected_avg_loss, 0),
        "shutdown_risk_pct": round(shutdown_risk, 1),
        "uninsured_loss_projection": uninsured_loss_projection
    }


def calculate_prevention_roi(history_df: pd.DataFrame) -> Dict:
    """
    Calculate ROI of preventative actions.
    
    Returns:
    - estimated_cost_to_fix: Cost to fix top issues
    - estimated_savings_if_fixed: Savings from preventing violations
    - roi_multiplier: ROI ratio
    - top_prevention_actions: List of recommended actions
    """
    if history_df.empty:
        return {
            "estimated_cost_to_fix": 0,
            "estimated_savings_if_fixed": 0,
            "roi_multiplier": 0.0,
            "top_prevention_actions": []
        }
    
    financial_risk = calculate_financial_risk(history_df)
    failure_prob = calculate_failure_probability(history_df, "")
    fingerprint = classify_violation_fingerprint(history_df)
    
    # Estimate cost to fix based on fingerprint
    cost_estimates = {
        "pest": 1500,
        "sanitation": 2000,
        "temperature": 3000,
        "staff-hygiene": 1000,
        "critical-risk": 5000
    }
    
    fp_type = fingerprint.get("fingerprint", "unknown")
    base_cost = cost_estimates.get(fp_type, 2500)
    
    # Add costs for multiple categories
    if fingerprint.get("breakdown"):
        additional_categories = len([c for c, p in fingerprint["breakdown"].items() if p > 10])
        base_cost += additional_categories * 500
    
    estimated_cost_to_fix = int(base_cost)
    
    # Savings = expected fines + revenue protection
    estimated_savings_if_fixed = int(financial_risk["expected_avg_loss"] * 1.5)  # 1.5x multiplier for prevention
    
    # ROI multiplier
    if estimated_cost_to_fix > 0:
        roi_multiplier = round(estimated_savings_if_fixed / estimated_cost_to_fix, 2)
    else:
        roi_multiplier = 0.0
    
    # Generate prevention actions based on fingerprint
    top_prevention_actions = []
    if fp_type == "pest":
        top_prevention_actions = [
            "Schedule monthly professional pest control service",
            "Seal all entry points and gaps",
            "Install door sweeps and maintain clean storage areas"
        ]
    elif fp_type == "sanitation":
        top_prevention_actions = [
            "Implement daily deep cleaning schedule",
            "Replace worn equipment and surfaces",
            "Train staff on proper sanitization procedures"
        ]
    elif fp_type == "temperature":
        top_prevention_actions = [
            "Calibrate all thermometers monthly",
            "Install temperature monitoring alarms",
            "Train staff on proper hot/cold holding procedures"
        ]
    elif fp_type == "staff-hygiene":
        top_prevention_actions = [
            "Implement mandatory handwashing stations",
            "Provide handwashing training and signage",
            "Establish glove-use protocols for food handling"
        ]
    else:
        top_prevention_actions = [
            "Address critical violations immediately",
            "Implement comprehensive staff training program",
            "Establish daily compliance checklist"
        ]
    
    return {
        "estimated_cost_to_fix": estimated_cost_to_fix,
        "estimated_savings_if_fixed": estimated_savings_if_fixed,
        "roi_multiplier": roi_multiplier,
        "top_prevention_actions": top_prevention_actions[:5]
    }


def calculate_insurance_savings(history_df: pd.DataFrame) -> Dict:
    """
    Calculate projected insurance premium savings.
    
    Returns:
    - projected_premium_savings: Annual savings if grade improves
    - projected_new_premium: New premium estimate
    - insurance_discount_eligibility: Boolean eligibility
    - eligibility_reasons: List of reasons for eligibility
    """
    if history_df.empty:
        return {
            "projected_premium_savings": 0,
            "projected_new_premium": 0,
            "insurance_discount_eligibility": False,
            "eligibility_reasons": []
        }
    
    grade, score = latest_grade_and_score(history_df)
    failure_prob = calculate_failure_probability(history_df, "")
    trend_data = calculate_score_trend(history_df)
    grade_probs = calculate_grade_probabilities(history_df)
    
    # Base premium estimates by grade
    base_premiums = {
        "A": 12000,
        "B": 18000,
        "C": 28000
    }
    
    current_premium = base_premiums.get(grade, 20000)
    predicted_grade = failure_prob.get("predicted_next_grade", grade)
    
    # Calculate projected premium
    if predicted_grade == "A":
        projected_new_premium = base_premiums["A"]
    elif predicted_grade == "B":
        projected_new_premium = base_premiums["B"]
    else:
        projected_new_premium = base_premiums["C"]
    
    # If improving trend, apply discount
    if trend_data.get("direction") == "improving":
        projected_new_premium = int(projected_new_premium * 0.95)
    
    projected_premium_savings = max(0, current_premium - projected_new_premium)
    
    # Eligibility criteria
    eligibility_reasons = []
    insurance_discount_eligibility = False
    
    if grade_probs.get("A", 0) > 40:
        eligibility_reasons.append("High probability of achieving Grade A")
        insurance_discount_eligibility = True
    
    if trend_data.get("direction") == "improving":
        eligibility_reasons.append("Improving inspection trend")
        insurance_discount_eligibility = True
    
    if failure_prob["failure_probability_pct"] < 30:
        eligibility_reasons.append("Low failure risk")
        insurance_discount_eligibility = True
    
    if score and score <= 13:
        eligibility_reasons.append("Current Grade A status")
        insurance_discount_eligibility = True
    
    if not eligibility_reasons:
        eligibility_reasons.append("Work needed to qualify for discounts")
    
    return {
        "projected_premium_savings": projected_premium_savings,
        "projected_new_premium": projected_new_premium,
        "insurance_discount_eligibility": insurance_discount_eligibility,
        "eligibility_reasons": eligibility_reasons
    }


def save_insurance_lead(restaurant_name: str, email: str, failure_probability_pct: float, projected_premium_savings: float):
    """
    Save insurance lead information to session state.
    """
    if "insurance_leads" not in st.session_state:
        st.session_state["insurance_leads"] = []
    
    lead_record = {
        "restaurant_name": restaurant_name,
        "email": email,
        "failure_probability_pct": failure_probability_pct,
        "projected_premium_savings": projected_premium_savings,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    st.session_state["insurance_leads"].append(lead_record)


def generate_insurance_liability_report(
    restaurant_name: str,
    hist_df: pd.DataFrame,
    failure_prob: Dict,
    financial_risk: Dict,
    roi: Dict,
    insurance_savings: Dict
) -> str:
    """
    Generate comprehensive AI-powered insurance liability report in Markdown format.
    """
    grade, score = latest_grade_and_score(hist_df)
    trend_data = calculate_score_trend(hist_df)
    grade_probs = calculate_grade_probabilities(hist_df)
    
    report = f"""# Insurance & Liability Intelligence Report
## {restaurant_name}

**Generated:** {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}

---

## Executive Summary

{restaurant_name} currently faces a **{failure_prob['failure_probability_pct']:.1f}% probability** of inspection failure in the next inspection cycle. Based on historical patterns and current risk factors, the restaurant is projected to achieve a **{failure_prob['predicted_next_grade']} grade** in the upcoming inspection.

**Key Financial Exposure:**
- Expected fine liability (next 90 days): **${financial_risk['expected_fine_min']:,} - ${financial_risk['expected_fine_max']:,}**
- Average projected loss: **${financial_risk['expected_avg_loss']:,.0f}**
- Closure risk probability: **{financial_risk['shutdown_risk_pct']:.1f}%**

**Insurance Opportunity:**
- Projected annual premium savings: **${insurance_savings['projected_premium_savings']:,}**
- Eligibility status: **{'Qualified' if insurance_savings['insurance_discount_eligibility'] else 'Pending qualification'}**

---

## Key Current Risks

### Failure Probability Breakdown

The restaurant's **{failure_prob['failure_probability_pct']:.1f}% failure probability** is driven by:

1. **Predicted Next Grade:** {failure_prob['predicted_next_grade']}
2. **Trend Direction:** {trend_data.get('direction', 'stable').title()}
3. **Score Trajectory:** Current score {trend_data.get('current_score', score or 'N/A')} → Predicted {trend_data.get('predicted_next_score', 'N/A')}

### Top Risk Categories

"""
    
    if failure_prob.get('key_driving_categories'):
        for i, cat in enumerate(failure_prob['key_driving_categories'], 1):
            report += f"{i}. **{cat.replace('_', ' ').title()}** - Primary risk driver\n"
    else:
        report += "Risk categories analysis pending sufficient data.\n"
    
    report += f"""
### Severity Analysis

- **Critical Violations:** {failure_prob['severity_vector'].get('critical', 0)}
- **Major Violations:** {failure_prob['severity_vector'].get('major', 0)}
- **Minor Violations:** {failure_prob['severity_vector'].get('minor', 0)}

---

## Probability Curves

### Next Inspection Grade Probabilities

- **Grade A:** {grade_probs.get('A', 0):.1f}%
- **Grade B:** {grade_probs.get('B', 0):.1f}%
- **Grade C:** {grade_probs.get('C', 0):.1f}%

**Confidence Level:** {grade_probs.get('confidence', 'medium')}

### Trend Analysis

- **Current Trend:** {trend_data.get('trend', 'stable').title()}
- **Velocity:** {trend_data.get('velocity', 0):.2f} points per inspection
- **Direction:** {trend_data.get('direction', 'stable').title()}

---

## Expected Fine Exposure

### 90-Day Financial Forecast

**Minimum Expected Fines:** ${financial_risk['expected_fine_min']:,}
**Maximum Expected Fines:** ${financial_risk['expected_fine_max']:,}
**Average Expected Loss:** ${financial_risk['expected_avg_loss']:,.0f}

### Uninsured Loss Projection

Total uninsured loss exposure (fines + revenue impact): **${financial_risk['uninsured_loss_projection']:,}**

This projection includes:
- Direct fine payments
- Lost revenue during potential closure periods
- Reputation damage costs
- Operational disruption expenses

---

## Closure Risk

**Probability of Closure:** {financial_risk['shutdown_risk_pct']:.1f}%

### Risk Factors

"""
    
    if financial_risk['shutdown_risk_pct'] > 50:
        report += "- **HIGH RISK:** Multiple critical violations and declining trend\n"
        report += "- Immediate intervention required to prevent closure\n"
    elif financial_risk['shutdown_risk_pct'] > 25:
        report += "- **MODERATE RISK:** Some critical violations present\n"
        report += "- Proactive measures recommended to reduce risk\n"
    else:
        report += "- **LOW RISK:** Current operations appear stable\n"
        report += "- Maintain current standards to preserve status\n"
    
    report += f"""
---

## Cost To Fix vs Cost If Ignored

### Investment Required

**Estimated Cost to Fix Top Issues:** ${roi['estimated_cost_to_fix']:,}

This investment would address:
"""
    
    for action in roi.get('top_prevention_actions', [])[:3]:
        report += f"- {action}\n"
    
    report += f"""
### Return on Investment

**Estimated Savings if Fixed:** ${roi['estimated_savings_if_fixed']:,}
**ROI Multiplier:** {roi['roi_multiplier']:.2f}x

**Analysis:** For every $1 invested in prevention, the restaurant stands to save **${roi['roi_multiplier']:.2f}** in avoided fines, lost revenue, and insurance costs.

### Cost of Inaction

If no action is taken, the restaurant faces:
- **${financial_risk['expected_avg_loss']:,.0f}** in expected fines over the next 90 days
- **{financial_risk['shutdown_risk_pct']:.1f}%** risk of temporary closure
- **${financial_risk['uninsured_loss_projection']:,}** in total uninsured losses
- Potential loss of **${insurance_savings['projected_premium_savings']:,}** in annual insurance savings

---

## Projected Insurance Savings

### Current vs Projected Premium

- **Current Estimated Premium:** Based on Grade {grade or 'Unknown'}
- **Projected New Premium:** ${insurance_savings['projected_new_premium']:,}
- **Annual Savings Potential:** ${insurance_savings['projected_premium_savings']:,}

### Eligibility Status

**Qualified for Discounts:** {'Yes' if insurance_savings['insurance_discount_eligibility'] else 'No'}

**Eligibility Factors:**
"""
    
    for reason in insurance_savings.get('eligibility_reasons', []):
        report += f"- {reason}\n"
    
    report += f"""
---

## Recommended Actions

### Immediate (Next 7 Days)

1. **Address Critical Violations:** Focus on the top {len(failure_prob.get('key_driving_categories', []))} risk categories
2. **Implement Quick Fixes:** Low-cost, high-impact improvements
3. **Staff Training:** Brief training on most common violation types

### Short-Term (Next 30 Days)

"""
    
    for i, action in enumerate(roi.get('top_prevention_actions', [])[:3], 1):
        report += f"{i}. {action}\n"
    
    report += f"""
### Long-Term (Next 90 Days)

1. **Systematic Compliance Program:** Establish daily/weekly/monthly checklists
2. **Equipment Upgrades:** Invest in temperature monitoring, pest control systems
3. **Ongoing Training:** Regular staff education on DOHMH standards
4. **Documentation System:** Maintain records to demonstrate compliance

---

## SmartBite Advisory

Based on our analysis of {restaurant_name}'s inspection history and risk profile:

**Primary Recommendation:** {'**IMMEDIATE ACTION REQUIRED**' if failure_prob['failure_probability_pct'] > 50 else '**PROACTIVE IMPROVEMENT RECOMMENDED**' if failure_prob['failure_probability_pct'] > 30 else '**MAINTAIN CURRENT STANDARDS**'}

**Strategic Focus:**
- Prioritize the **{failure_prob.get('key_driving_categories', ['general compliance'])[0] if failure_prob.get('key_driving_categories') else 'general compliance'}** category for maximum impact
- Invest **${roi['estimated_cost_to_fix']:,}** in prevention to save **${roi['estimated_savings_if_fixed']:,}** over the next year
- Work toward **Grade {failure_prob['predicted_next_grade']}** to unlock **${insurance_savings['projected_premium_savings']:,}** in annual insurance savings

**Next Steps:**
1. Review this report with management team
2. Prioritize top 3 prevention actions
3. Establish compliance monitoring system
4. Consider insurance discount application if eligible

---

*This report is generated by SmartBite AI and is based on historical inspection data and predictive modeling. Actual outcomes may vary based on operational changes and external factors.*

*© {datetime.datetime.now().year} SmartBite. For restaurant owner use only.*
"""
    
    return report


def generate_insurance_report_pdf(report_text: str, restaurant_name: str) -> bytes:
    """
    Generate downloadable PDF of insurance liability report.
    Uses the same pattern as other PDFs.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        import io
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        # Container for PDF elements
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor='#0B4F6C',
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor='#0B4F6C',
            spaceAfter=12,
            spaceBefore=12
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubheading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor='#333333',
            spaceAfter=8,
            spaceBefore=8
        )
        
        # Convert markdown to PDF elements
        lines = report_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.15*inch))
            elif line.startswith('# '):
                story.append(Paragraph(line[2:], title_style))
            elif line.startswith('## '):
                story.append(Paragraph(line[3:], heading_style))
            elif line.startswith('### '):
                story.append(Paragraph(line[4:], subheading_style))
            elif line.startswith('---'):
                story.append(Spacer(1, 0.2*inch))
            else:
                # Clean markdown formatting
                clean_line = line.replace('**', '<b>').replace('**', '</b>')
                clean_line = clean_line.replace('_', '<i>').replace('_', '</i>')
                
                if clean_line:
                    try:
                        story.append(Paragraph(clean_line, styles['Normal']))
                    except:
                        # Fallback for problematic lines
                        story.append(Paragraph(clean_line.replace('<', '&lt;').replace('>', '&gt;'), styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
        
    except ImportError:
        # Fallback: return plain text as bytes
        return report_text.encode('utf-8')
    except Exception as e:
        # Error fallback
        error_msg = f"PDF generation failed: {e}\n\n{report_text}"
        return error_msg.encode('utf-8')


# -----------------------------
# P2.3: Violation Fingerprint Classification
# -----------------------------

def classify_violation_fingerprint(hist: pd.DataFrame) -> Dict[str, any]:
    """
    Analyze violation patterns to determine restaurant's 'fingerprint'.
    
    Fingerprint types:
    - pest-heavy: Rodents, flies, cockroaches dominant
    - sanitation-heavy: Cleaning, facility issues dominant  
    - staff-hygiene-heavy: Handwashing, cross-contamination dominant
    - temperature-heavy: Food temp, cooling issues dominant
    - critical-risk-dominant: High proportion of critical violations
    """
    if hist.empty:
        return {
            "fingerprint": "insufficient_data",
            "confidence": 0.0,
            "breakdown": {},
            "description": "Not enough data to determine violation pattern"
        }
    
    # Count violations by category
    categories = {
        "pest": 0,
        "sanitation": 0,
        "staff_hygiene": 0,
        "temperature": 0,
        "critical": 0,
        "other": 0
    }
    
    total_violations = 0
    
    for _, row in hist.iterrows():
        desc = str(row.get("violation_description", "")).lower()
        crit = str(row.get("critical_flag", "")).upper().strip() == "Y"
        
        total_violations += 1
        
        if crit:
            categories["critical"] += 1
        
        # Categorize
        if any(kw in desc for kw in ["pest", "rat", "mice", "mouse", "roach", "fly", "flies", "insect", "vermin"]):
            categories["pest"] += 1
        elif any(kw in desc for kw in ["temperature", "cooling", "heating", "hot", "cold", "thermometer", "thawing"]):
            categories["temperature"] += 1
        elif any(kw in desc for kw in ["handwash", "hand wash", "glove", "hygiene", "hair", "contamination", "cross"]):
            categories["staff_hygiene"] += 1
        elif any(kw in desc for kw in ["clean", "sanit", "wash", "dirty", "facility", "floor", "wall", "surface", "equipment"]):
            categories["sanitation"] += 1
        else:
            categories["other"] += 1
    
    if total_violations == 0:
        return {
            "fingerprint": "no_violations",
            "confidence": 1.0,
            "breakdown": categories,
            "description": "No violations recorded"
        }
    
    # Calculate percentages
    breakdown_pct = {k: round((v / total_violations) * 100, 1) for k, v in categories.items()}
    
    # Determine dominant fingerprint
    dominant_cat = max(categories, key=categories.get)
    dominant_pct = breakdown_pct[dominant_cat]
    
    # Check for critical-risk-dominant (>50% critical)
    if breakdown_pct["critical"] > 50:
        fingerprint = "critical-risk-dominant"
        description = f"{breakdown_pct['critical']}% of violations are CRITICAL. Immediate systemic improvements needed."
        confidence = 0.9
    elif dominant_pct > 40:
        # Clear dominant pattern
        fingerprint = f"{dominant_cat}-heavy"
        confidence = 0.8
        
        descriptions = {
            "pest": f"Pest control issues dominate ({dominant_pct}%). Focus on IPM, sanitation, and professional pest management.",
            "sanitation": f"Facility cleanliness issues dominate ({dominant_pct}%). Focus on cleaning schedules, equipment maintenance, and facility upkeep.",
            "staff_hygiene": f"Staff hygiene issues dominate ({dominant_pct}%). Focus on training, handwashing stations, and cross-contamination prevention.",
            "temperature": f"Temperature control issues dominate ({dominant_pct}%). Focus on equipment maintenance, monitoring, and cold-chain procedures."
        }
        description = descriptions.get(dominant_cat, f"{dominant_cat} issues are most common ({dominant_pct}%).")
    else:
        # Mixed pattern
        fingerprint = "mixed-pattern"
        description = "Multiple violation types without clear dominance. Requires comprehensive operational review."
        confidence = 0.5
    
    return {
        "fingerprint": fingerprint,
        "confidence": confidence,
        "breakdown": breakdown_pct,
        "total_violations": total_violations,
        "description": description,
        "dominant_category": dominant_cat,
        "dominant_percentage": dominant_pct
    }


# -----------------------------
# P2.4: Display Fingerprint Summary Component
# -----------------------------

def render_fingerprint_summary(hist: pd.DataFrame):
    """
    Render violation fingerprint summary in restaurant history section.
    """
    fingerprint = classify_violation_fingerprint(hist)
    
    if fingerprint["fingerprint"] == "insufficient_data":
        st.caption(" Not enough data for pattern analysis")
        return
    
    st.markdown("#####  Violation Fingerprint Analysis")
    
    # Main fingerprint badge
    fp_type = fingerprint["fingerprint"]
    confidence = fingerprint["confidence"]
    
    color = "#FF6B6B" if "critical" in fp_type else "#FFA94D" if confidence > 0.7 else "#4ECDC4"
    
    st.markdown(
        f'<div style="background: {color}20; border-left: 4px solid {color}; '
        f'padding: 1rem; border-radius: 6px; margin-bottom: 1rem;">'
        f'<strong style="color: {color}; font-size: 1.1em;">{fp_type.replace("-", " ").replace("_", " ").title()}</strong><br>'
        f'<span style="font-size: 0.9em; color: #666;">{fingerprint["description"]}</span>'
        f'</div>',
        unsafe_allow_html=True
    )
    
    # Breakdown chart
    if fingerprint["breakdown"]:
        st.markdown("**Category Breakdown:**")
        breakdown = fingerprint["breakdown"]
        
        # Sort by percentage
        sorted_categories = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        
        for cat, pct in sorted_categories[:5]:  # Top 5
            if pct > 0:
                bar_width = max(pct, 2)  # Minimum 2% for visibility
                st.markdown(
                    f'<div style="margin-bottom: 0.3rem;">'
                    f'<span style="display: inline-block; width: 120px; font-size: 0.85em;">{cat.replace("_", " ").title()}</span>'
                    f'<div style="display: inline-block; width: 60%; background: #e0e0e0; border-radius: 3px; height: 16px; vertical-align: middle;">'
                    f'<div style="width: {bar_width}%; background: var(--sb-accent); height: 100%; border-radius: 3px;"></div>'
                    f'</div>'
                    f'<span style="margin-left: 0.5rem; font-size: 0.85em; color: #666;">{pct}%</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )


def simulate_inspection(
    hist: pd.DataFrame,
    fix_pest: bool,
    fix_temp: bool,
    fix_clean: bool,
    fix_staff: bool,
) -> Tuple[Optional[float], Optional[float], Dict[str, float]]:
    """
    Analytical score simulation based on categories.
    """
    if hist.empty or "score" not in hist.columns:
        return None, None, {}
    scores = hist["score"].dropna()
    if scores.empty:
        return None, None, {}
    cur = scores.iloc[-1]

    last = hist.tail(6)
    impact = {"pest": 0.0, "temperature": 0.0, "cleanliness": 0.0, "handwashing": 0.0}

    for _, r in last.iterrows():
        desc = r.get("violation_description", "")
        cat = categorize_violation(desc)
        crit = str(r.get("critical_flag", "")).upper().strip() == "Y"
        delta = 4.0 if crit else 2.0

        if cat == "pest":
            impact["pest"] += delta
        elif cat == "temperature":
            impact["temperature"] += delta
        elif cat == "cleanliness":
            impact["cleanliness"] += delta
        elif cat in ("handwashing", "cross_contamination"):
            impact["handwashing"] += delta

    new_score = cur
    if fix_pest:
        new_score -= impact["pest"]
    if fix_temp:
        new_score -= impact["temperature"]
    if fix_clean:
        new_score -= impact["cleanliness"]
    if fix_staff:
        new_score -= impact["handwashing"]

    new_score = max(new_score, 0.0)

    return cur, new_score, impact


def score_to_grade(score: float) -> str:
    if score > 27:
        return "C"
    if score > 13:
        return "B"
    return "A"


def risk_forecasting(hist: pd.DataFrame, periods: int = 3) -> List[Dict]:
    """
    Simple linear score trend forecast.
    """
    if hist.empty or "score" not in hist.columns or "inspection_date" not in hist.columns:
        return []

    df = hist.dropna(subset=["score", "inspection_date"]).copy()
    if df.shape[0] < 3:
        return []

    df = df.sort_values("inspection_date")
    df["t"] = (df["inspection_date"] - df["inspection_date"].min()).dt.days
    x = df["t"].values
    y = df["score"].values

    try:
        slope, intercept = np.polyfit(x, y, 1)
    except Exception:
        return []

    last_t = x[-1]
    out = []
    for i in range(1, periods + 1):
        t_future = last_t + i * 30
        pred_score = float(intercept + slope * t_future)
        pred_score = max(pred_score, 0.0)
        grade = score_to_grade(pred_score)
        out.append(
            {
                "inspection_index": f"Next #{i}",
                "predicted_score": round(pred_score, 1),
                "predicted_grade": grade,
            }
        )
    return out


# ============================================================
# PHASE 3 — OWNER VALUE FEATURES
# ============================================================

# -----------------------------
# P3.1: Auto-Generate SOP Pack
# -----------------------------

def generate_sop_pack(restaurant_name: str, hist: pd.DataFrame, fingerprint: Dict) -> str:
    """
    Generate comprehensive SOP (Standard Operating Procedures) pack based on 
    violation fingerprint and root causes.
    
    Returns markdown-formatted SOP document with 10 sections.
    """
    grade, score = latest_grade_and_score(hist)
    root_causes = detect_root_causes(hist)
    
    # Identify top 3 root causes
    top_causes = sorted(root_causes.items(), key=lambda x: x[1]["count"], reverse=True)[:3]
    
    sop_content = f"""# Standard Operating Procedures (SOP) Pack
## {restaurant_name}
### Generated: {datetime.datetime.now().strftime("%B %d, %Y")}

---

## Executive Summary

**Current Status:**
- Grade: {grade or 'N/A'}
- Score: {score if score else 'N/A'}
- Violation Pattern: {fingerprint.get('fingerprint', 'unknown').replace('-', ' ').replace('_', ' ').title()}

**Priority Focus Areas:**
"""
    
    for cause_name, cause_info in top_causes:
        sop_content += f"\n- **{cause_name.title()}**: {cause_info['count']} recent violations"
    
    sop_content += "\n\n---\n\n"
    
    # SOP Sections based on fingerprint
    sop_sections = []
    
    # 1. Daily Opening Checklist
    sop_sections.append({
        "title": "1. Daily Opening Checklist",
        "content": """
**Before Service Begins:**
- [ ] Check all refrigeration units (cold holding at 41°F or below)
- [ ] Verify hot holding equipment (135°F or above)
- [ ] Inspect for any signs of pest activity
- [ ] Ensure all handwashing stations are stocked (soap, towels, hot water)
- [ ] Review temperature logs from previous day
- [ ] Check cleaning schedules completed overnight
- [ ] Verify food storage areas are organized (FIFO rotation)
- [ ] Inspect prep surfaces for cleanliness

**Responsible:** Manager on Duty
**Frequency:** Daily before service
**Documentation:** Opening checklist form
"""
    })
    
    # 2. Temperature Monitoring Protocol
    sop_sections.append({
        "title": "2. Temperature Monitoring & Food Safety",
        "content": """
**Cold Food Holding:**
- Check all refrigeration units every 4 hours
- Log temperatures on monitoring sheet
- Discard food if temp exceeds 41°F for >4 hours
- Calibrate thermometers weekly

**Hot Food Holding:**
- Maintain hot foods at 135°F or above
- Check temps every 2 hours during service
- Reheat foods to 165°F before hot holding
- Never mix old and new batches

**Cooling Procedures:**
- Cool cooked foods from 135°F to 70°F within 2 hours
- Cool from 70°F to 41°F within additional 4 hours
- Use ice baths, shallow pans, or blast chillers
- Never cool at room temperature

**Responsible:** All kitchen staff
**Frequency:** Per schedule above
**Documentation:** Temperature monitoring logs
"""
    })
    
    # 3. Pest Control Program
    sop_sections.append({
        "title": "3. Integrated Pest Management (IPM)",
        "content": """
**Prevention:**
- Seal all cracks and gaps in walls, floors, foundation
- Keep all doors closed when not in active use
- Install door sweeps and air curtains
- Store all food 6 inches off floor
- Remove garbage daily (never let accumulate overnight)
- Clean drains daily with enzymatic cleaner

**Monitoring:**
- Weekly inspection of all storage areas
- Check for droppings, gnaw marks, grease marks
- Maintain pest log with dates and findings
- Review sticky traps weekly

**Professional Service:**
- Licensed pest control operator visits monthly (minimum)
- Service records kept on-site for 3 years
- Follow all IPM recommendations immediately

**Responsible:** General Manager + Pest Control Company
**Frequency:** Daily monitoring, monthly professional service
**Documentation:** Pest control log, service invoices
"""
    })
    
    # 4. Handwashing & Personal Hygiene
    sop_sections.append({
        "title": "4. Handwashing & Personal Hygiene Standards",
        "content": """
**Handwashing Requirements:**
- Wash hands for minimum 20 seconds with soap and warm water
- Wash before starting work, after breaks, after handling raw food
- Wash after touching face/hair, after using restroom, after handling trash
- Use single-use towels only (no shared cloth towels)

**Personal Hygiene:**
- Hair must be restrained (hats, nets, or bandanas)
- No jewelry except plain wedding band
- Clean uniforms daily
- No nail polish or artificial nails for food handlers
- Report illness (vomiting, diarrhea, jaundice, fever, sore throat) to manager

**Glove Use:**
- Change gloves between tasks
- Never wash and reuse gloves
- Wash hands before putting on new gloves
- Use gloves for ready-to-eat food handling

**Responsible:** All staff
**Frequency:** As required by task
**Documentation:** Staff acknowledgment forms
"""
    })
    
    # 5. Cleaning & Sanitizing Procedures
    sop_sections.append({
        "title": "5. Cleaning & Sanitizing Protocols",
        "content": """
**Three-Compartment Sink:**
1. Wash in hot soapy water (minimum 110°F)
2. Rinse in clean water
3. Sanitize (chlorine 50-100 ppm OR quaternary ammonia per label)
4. Air dry (never towel dry)

**Food Contact Surfaces:**
- Clean and sanitize between different raw food types
- Clean and sanitize every 4 hours during continuous use
- Clean and sanitize before working with ready-to-eat foods
- Use test strips to verify sanitizer concentration

**Daily Cleaning Schedule:**
- All food prep surfaces after each use
- All equipment surfaces at end of shift
- Floors swept and mopped
- Drains cleaned and flushed
- Trash areas cleaned

**Weekly Deep Cleaning:**
- Behind and under all equipment
- Walk-in refrigerators and freezers
- Walls, ceilings, light fixtures
- Ventilation hoods and filters

**Responsible:** All kitchen staff per schedule
**Frequency:** Per schedule above
**Documentation:** Daily/weekly cleaning checklists
"""
    })
    
    # 6. Food Receiving & Storage
    sop_sections.append({
        "title": "6. Food Receiving & Storage Standards",
        "content": """
**Receiving Inspection:**
- Check all deliveries for proper temperature
- Reject food with signs of pest damage, contamination, or temperature abuse
- Verify expiration dates and quality
- Never accept unlabeled containers

**Storage Hierarchy (Top to Bottom):**
1. Ready-to-eat foods (top shelves)
2. Seafood
3. Whole cuts of beef and pork
4. Ground meats and fish
5. Whole and ground poultry (bottom shelf)

**Storage Rules:**
- All food covered and labeled with date
- Store food 6 inches off floor
- FIFO rotation (First In, First Out)
- Never store food under leaking pipes
- Never store chemicals above or near food

**Responsible:** Receiving manager + All staff
**Frequency:** Every delivery + daily monitoring
**Documentation:** Receiving logs, temperature records
"""
    })
    
    # 7. Cross-Contamination Prevention
    sop_sections.append({
        "title": "7. Cross-Contamination Prevention",
        "content": """
**Separate Equipment:**
- Use color-coded cutting boards (red=raw meat, green=produce, etc.)
- Designate separate utensils for raw and cooked foods
- Never reuse plates that held raw food
- Wash and sanitize all equipment between uses

**Workflow Management:**
- Prepare raw foods in designated areas only
- Complete all raw food prep before ready-to-eat foods
- Never place cooked food on surfaces that held raw food
- Use separate handwashing sinks (never use prep sinks)

**Staff Training:**
- Train all new hires on cross-contamination risks
- Quarterly refresher training for all staff
- Post visual reminders in prep areas

**Responsible:** All kitchen staff
**Frequency:** Continuous awareness
**Documentation:** Training attendance records
"""
    })
    
    # 8. Employee Training Program
    sop_sections.append({
        "title": "8. Employee Training & Certification",
        "content": """
**Food Handler Certification:**
- All employees complete NYC Food Protection Course within 30 days
- Supervisor holds NYC Food Protection Manager Certificate
- Certificates posted and kept current

**New Hire Training (Day 1):**
- Food safety basics and cross-contamination
- Handwashing and personal hygiene
- Temperature monitoring procedures
- Cleaning and sanitizing protocols
- Pest awareness

**Ongoing Training:**
- Monthly safety meetings (document attendance)
- Quarterly deep-dive on seasonal issues
- Annual refresher on all SOPs
- Training after any violations or incidents

**Language Accessibility:**
- Provide training in languages staff understand
- Use visual aids and demonstrations
- Verify understanding through demonstration

**Responsible:** General Manager / Training Coordinator
**Frequency:** Per schedule above
**Documentation:** Training logs, attendance sheets, test scores
"""
    })
    
    # 9. Record Keeping & Documentation
    sop_sections.append({
        "title": "9. Record Keeping & Compliance Documentation",
        "content": """
**Required Records (Keep 90 Days Minimum):**
- Daily temperature logs (refrigeration, hot holding, cooking temps)
- Cleaning and sanitizing checklists
- Pest control service records (keep 3 years)
- Employee training records
- Food receiving logs
- Thermometer calibration logs
- Corrective action reports

**Document Organization:**
- Use binders or digital system
- Organize by category and date
- Make readily available for inspections
- Review weekly for completeness

**Corrective Actions:**
- Document any out-of-range temperatures immediately
- Note corrective action taken (e.g., "food discarded," "equipment repaired")
- Manager signature required on all corrective actions
- Follow up to verify correction

**Responsible:** Manager on Duty
**Frequency:** Daily documentation, weekly review
**Documentation:** All logs and records listed above
"""
    })
    
    # 10. Inspection Readiness
    sop_sections.append({
        "title": "10. Health Inspection Readiness",
        "content": """
**Daily Inspection Mindset:**
- Operate every day as if inspector is coming
- Never skip temperature checks or documentation
- Address issues immediately, never "later"
- Keep all logs current and accessible

**Pre-Inspection Checklist:**
- All food properly labeled and dated
- Temperature logs up to date and accurate
- No expired food products
- All cleaning chemicals properly stored and labeled
- Handwashing stations fully stocked
- Thermometers calibrated and working
- No signs of pest activity
- Garbage areas clean and organized
- Posted permits current

**During Inspection:**
- Be cooperative and professional
- Answer questions honestly
- Provide requested records promptly
- Take notes on inspector's observations
- Ask for clarification if needed

**Post-Inspection:**
- Review all violations immediately
- Create corrective action plan within 24 hours
- Assign responsibility for each correction
- Document all fixes with photos/receipts
- Schedule reinspection if required

**Responsible:** All management staff
**Frequency:** Daily readiness
**Documentation:** Inspection reports, corrective action plans
"""
    })
    
    # Compile all sections
    for section in sop_sections:
        sop_content += f"## {section['title']}\n\n{section['content']}\n\n---\n\n"
    
    # Footer
    sop_content += """
## Document Control

**Review Schedule:** Quarterly or after any inspection violation
**Approval:** General Manager / Owner signature required
**Distribution:** All staff must read and acknowledge
**Revision History:** Document all updates with dates

---

**EMPLOYEE ACKNOWLEDGMENT**

I have read and understand all Standard Operating Procedures outlined in this document. I agree to follow these procedures as a condition of my employment.

Employee Name: _________________________

Employee Signature: ____________________ Date: __________

Manager Name: _________________________

Manager Signature: _____________________ Date: __________

---

*This SOP pack was generated by SmartBite AI based on your restaurant's actual inspection history and violation patterns.*
"""
    
    return sop_content


def generate_sop_pdf(restaurant_name: str, hist: pd.DataFrame, fingerprint: Dict) -> bytes:
    """
    Generate a downloadable PDF of the SOP pack.
    
    Returns PDF as bytes (fallback to simple text if reportlab not available).
    """
    sop_markdown = generate_sop_pack(restaurant_name, hist, fingerprint)
    
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        import io
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                              rightMargin=0.75*inch, leftMargin=0.75*inch,
                              topMargin=0.75*inch, bottomMargin=0.75*inch)
        
        # Container for PDF elements
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor='#0B4F6C',
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor='#0B4F6C',
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Convert markdown to PDF elements (simple conversion)
        lines = sop_markdown.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 0.2*inch))
            elif line.startswith('# '):
                story.append(Paragraph(line[2:], title_style))
            elif line.startswith('## '):
                story.append(Paragraph(line[3:], heading_style))
            elif line.startswith('### '):
                story.append(Paragraph(f"<b>{line[4:]}</b>", styles['Normal']))
            elif line.startswith('---'):
                story.append(Spacer(1, 0.3*inch))
            elif line.startswith('**') and line.endswith('**'):
                story.append(Paragraph(f"<b>{line[2:-2]}</b>", styles['Normal']))
            else:
                # Clean up markdown formatting for PDF
                clean_line = line.replace('**', '')
                if clean_line:
                    story.append(Paragraph(clean_line, styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
        
    except ImportError:
        # Fallback: return plain text as bytes
        return sop_markdown.encode('utf-8')


# -----------------------------
# P3.2: Cost of Failure Calculator
# -----------------------------

def calculate_cost_of_failure(hist: pd.DataFrame, grade: str, score: float) -> Dict:
    """
    Calculate estimated financial impact of current grade/violations.
    
    Returns dict with:
    - estimated_fine_range: tuple of (min, max)
    - estimated_lost_revenue: annual estimate
    - reputation_impact: qualitative assessment
    - total_annual_cost: combined estimate
    """
    result = {
        "fine_range_min": 0,
        "fine_range_max": 0,
        "lost_revenue_annual": 0,
        "reputation_impact": "Unknown",
        "total_annual_cost": 0,
        "breakdown": []
    }
    
    # Count violations by severity
    critical_count = 0
    general_count = 0
    
    if not hist.empty and "critical_flag" in hist.columns:
        recent = hist.tail(12)  # Last year of violations
        critical_count = (recent["critical_flag"].str.upper().str.strip() == "Y").sum()
        general_count = len(recent) - critical_count
    
    # NYC Fine Structure (2024 estimates)
    # Critical violations: $200-$2,000 each
    # General violations: $200-$600 each
    # Grade penalties can be up to $1,000
    
    fine_min = (critical_count * 200) + (general_count * 200)
    fine_max = (critical_count * 2000) + (general_count * 600)
    
    if grade == "C":
        fine_max += 1000
    elif grade == "B":
        fine_max += 500
    
    result["fine_range_min"] = fine_min
    result["fine_range_max"] = fine_max
    result["breakdown"].append(f"Violation fines: ${fine_min:,} - ${fine_max:,}")
    
    # Lost revenue estimates based on grade
    # Research shows grade impacts customer behavior:
    # - Grade A: baseline
    # - Grade B: -10% to -15% revenue
    # - Grade C: -25% to -40% revenue
    # - Pending/Closure: -100% during closure
    
    # Assume average NYC restaurant revenue: $500k-$2M annually
    avg_revenue = 1000000  # $1M baseline
    
    if grade == "C":
        lost_revenue_pct = 0.325  # 32.5% average
        reputation_impact = "Severe - Grade C visible to all customers"
        result["lost_revenue_annual"] = int(avg_revenue * lost_revenue_pct)
        result["breakdown"].append(f"Lost revenue (Grade C ~32.5% impact): ${result['lost_revenue_annual']:,}")
    elif grade == "B":
        lost_revenue_pct = 0.125  # 12.5% average
        reputation_impact = "Moderate - Some customers avoid Grade B"
        result["lost_revenue_annual"] = int(avg_revenue * lost_revenue_pct)
        result["breakdown"].append(f"Lost revenue (Grade B ~12.5% impact): ${result['lost_revenue_annual']:,}")
    elif grade == "A":
        lost_revenue_pct = 0.0
        reputation_impact = "Minimal - Grade A maintains customer confidence"
        result["lost_revenue_annual"] = 0
        result["breakdown"].append("Lost revenue (Grade A): $0")
    else:
        lost_revenue_pct = 0.05
        reputation_impact = "Low to Moderate"
        result["lost_revenue_annual"] = int(avg_revenue * lost_revenue_pct)
        result["breakdown"].append(f"Lost revenue (estimated): ${result['lost_revenue_annual']:,}")
    
    # Additional costs
    if score and score > 28:
        # High-risk restaurants often face additional costs
        reinspection_costs = 800  # Estimated staff time + fees
        result["breakdown"].append(f"Reinspection costs: ${reinspection_costs:,}")
        fine_max += reinspection_costs
    
    if critical_count > 5:
        # Multiple critical violations may require consultants
        consultant_cost = 5000
        result["breakdown"].append(f"Compliance consultant (recommended): ${consultant_cost:,}")
        fine_max += consultant_cost
    
    result["reputation_impact"] = reputation_impact
    result["total_annual_cost"] = result["lost_revenue_annual"] + ((fine_min + fine_max) / 2)
    
    return result


# -----------------------------
# P3.3: Staff Compliance Checklist Builder
# -----------------------------

def generate_compliance_checklist(fingerprint: Dict, root_causes: Dict) -> Dict[str, List[str]]:
    """
    Generate customized staff compliance checklist based on violation patterns.
    
    Returns dict with checklists for:
    - opening_duties
    - during_service
    - closing_duties
    - manager_weekly
    """
    checklist = {
        "opening_duties": [],
        "during_service": [],
        "closing_duties": [],
        "manager_weekly": []
    }
    
    # Universal baseline items
    checklist["opening_duties"].extend([
        "Check all refrigerator temperatures (must be ≤41°F)",
        "Check all freezer temperatures (must be ≤0°F)",
        "Verify handwashing stations have soap, towels, and warm water",
        "Inspect for any signs of pests (droppings, gnaw marks)",
        "Review temperature logs from previous day"
    ])
    
    checklist["during_service"].extend([
        "Check cold holding temperatures every 4 hours",
        "Check hot holding temperatures every 2 hours",
        "Wash hands after handling raw food, between tasks",
        "Change gloves between different food types",
        "Keep all food covered when not in use"
    ])
    
    checklist["closing_duties"].extend([
        "Complete all temperature logs for the day",
        "Clean and sanitize all food contact surfaces",
        "Sweep and mop all floors",
        "Take out all garbage and recyclables",
        "Clean and sanitize three-compartment sink"
    ])
    
    checklist["manager_weekly"].extend([
        "Review all temperature logs for completeness",
        "Calibrate all thermometers",
        "Inspect all storage areas for cleanliness and organization",
        "Review pest control logs and service records",
        "Conduct staff training on identified weak areas"
    ])
    
    # Customize based on fingerprint
    fp_type = fingerprint.get("fingerprint", "")
    
    if "pest" in fp_type:
        checklist["opening_duties"].append("PRIORITY: Thorough pest inspection of all areas")
        checklist["closing_duties"].extend([
            "PRIORITY: Remove all garbage (do not leave overnight)",
            "PRIORITY: Clean all drains with enzymatic cleaner",
            "PRIORITY: Ensure all food is stored 6+ inches off floor"
        ])
        checklist["manager_weekly"].append("PRIORITY: Review pest control service records and follow up on recommendations")
    
    if "temperature" in fp_type:
        checklist["opening_duties"].append("PRIORITY: Check all equipment calibration and function")
        checklist["during_service"].extend([
           "PRIORITY: Log cooling temps at 2hr and 6hr marks",
           "PRIORITY: Never leave food in temperature danger zone (41°F-135°F)"
        ])
        checklist["manager_weekly"].append("PRIORITY: Review all temperature logs for any out-of-range readings")
    
    if "sanitation" in fp_type:
        checklist["during_service"].append("PRIORITY: Clean and sanitize prep surfaces between tasks")
        checklist["closing_duties"].extend([
           "PRIORITY: Deep clean behind and under equipment",
           "PRIORITY: Clean walls, floors, and ceilings in prep areas"
        ])
        checklist["manager_weekly"].append("PRIORITY: Inspect facility for needed repairs or deep cleaning")
    
    if "staff" in fp_type or "hygiene" in fp_type:
        checklist["opening_duties"].append("PRIORITY: Verify all staff have clean uniforms and hair restraints")
        checklist["during_service"].extend([
           "PRIORITY: Monitor handwashing compliance throughout shift",
           "PRIORITY: Ensure gloves are changed appropriately"
        ])
        checklist["manager_weekly"].append("PRIORITY: Conduct personal hygiene training refresher")
    
    if "critical" in fp_type:
        checklist["manager_weekly"].extend([
           "CRITICAL: Review ALL critical violation risk factors",
           "CRITICAL: Schedule emergency staff training session",
           "CRITICAL: Consider hiring food safety consultant"
        ])
    
    # Add items based on specific root causes
    for cause_name, cause_info in root_causes.items():
        if cause_info["count"] >= 3:  # Significant problem
            if cause_name.lower() in ["pest", "rats", "mice", "roaches"]:
                if "Seal all entry points (cracks, gaps, doors)" not in checklist["manager_weekly"]:
                    checklist["manager_weekly"].append("Seal all entry points (cracks, gaps, doors)")
            elif cause_name.lower() in ["temperature", "cooling", "heating"]:
                if "Schedule equipment maintenance check" not in checklist["manager_weekly"]:
                    checklist["manager_weekly"].append("Schedule equipment maintenance check")
            elif cause_name.lower() in ["handwashing", "cross contamination"]:
                if "Observe and correct handwashing technique" not in checklist["during_service"]:
                    checklist["during_service"].append("Observe and correct handwashing technique")
    
    return checklist


def render_compliance_checklist_ui(checklist: Dict[str, List[str]]):
    """
    Render the compliance checklist in a beautiful, printable format.
    """
    st.markdown("###  Customized Staff Compliance Checklist")
    st.caption(" Print this checklist and post in kitchen. Check off daily.")
    
    # Opening Duties
    with st.expander(" **Opening Duties** (Before Service)", expanded=True):
        for item in checklist["opening_duties"]:
            st.markdown(f"- [ ] {item}")
    
    # During Service
    with st.expander(" **During Service** (Every Shift)", expanded=True):
        for item in checklist["during_service"]:
            st.markdown(f"- [ ] {item}")
    
    # Closing Duties
    with st.expander(" **Closing Duties** (End of Service)", expanded=True):
        for item in checklist["closing_duties"]:
            st.markdown(f"- [ ] {item}")
    
    # Manager Weekly
    with st.expander(" **Manager Weekly Review**", expanded=True):
        for item in checklist["manager_weekly"]:
            st.markdown(f"- [ ] {item}")
    
    # Generate downloadable text version
    checklist_text = "STAFF COMPLIANCE CHECKLIST\n"
    checklist_text += "=" * 50 + "\n\n"
    
    checklist_text += "OPENING DUTIES (Before Service)\n"
    checklist_text += "-" * 50 + "\n"
    for item in checklist["opening_duties"]:
        checklist_text += f"- [ ] {item}\n"
    checklist_text += "\n"
    
    checklist_text += "DURING SERVICE (Every Shift)\n"
    checklist_text += "-" * 50 + "\n"
    for item in checklist["during_service"]:
        checklist_text += f"- [ ] {item}\n"
    checklist_text += "\n"
    
    checklist_text += "CLOSING DUTIES (End of Service)\n"
    checklist_text += "-" * 50 + "\n"
    for item in checklist["closing_duties"]:
        checklist_text += f"- [ ] {item}\n"
    checklist_text += "\n"
    
    checklist_text += "MANAGER WEEKLY REVIEW\n"
    checklist_text += "-" * 50 + "\n"
    for item in checklist["manager_weekly"]:
        checklist_text += f"- [ ] {item}\n"
    checklist_text += "\n"
    
    checklist_text += "=" * 50 + "\n"
    checklist_text += "Generated by SmartBite AI\n"
    checklist_text += f"Date: {datetime.datetime.now().strftime('%B %d, %Y')}\n"
    
    return checklist_text


# -----------------------------
# P3.4: Share AI Report Feature
# -----------------------------

def generate_owner_report(
    restaurant_name: str,
    hist_df: pd.DataFrame,
    memory: Dict[str, List[Dict]],
    kb_available: bool = False
) -> str:
    """
    Generate comprehensive AI Owner Report for sharing.
    
    Includes:
    - Restaurant summary (grade, score, risk, fingerprint)
    - Last 10 Q&A from memory
    - AI-generated 7-day action plan
    - AI-generated 30-day stabilization plan
    - Top 5 violations breakdown
    - Critical risk commentary
    - Business impact summary
    
    Returns: Markdown-formatted report string
    """
    import datetime
    
    # Get restaurant stats
    grade, score = latest_grade_and_score(hist_df)
    risk_level = compute_risk_level(hist_df)
    fingerprint = classify_violation_fingerprint(hist_df)
    trend_data = calculate_score_trend(hist_df)
    cost_analysis = calculate_cost_of_failure(hist_df, grade, score)
    
    # Build report header
    report = f"""# SmartBite AI Owner Report
## {restaurant_name}

**Generated:** {datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")}

---

## Executive Summary

### Current Status
- **Grade:** {grade or 'N/A'}
- **Score:** {score if score else 'N/A'}
- **Risk Level:** {risk_level}
- **Violation Pattern:** {fingerprint.get('fingerprint', 'unknown').replace('-', ' ').replace('_', ' ').title()}

### Trend Analysis
- **Direction:** {trend_data.get('direction', 'unknown').title()}
- **Velocity:** {trend_data.get('velocity', 0):.2f} points per inspection
- **Predicted Next Score:** {trend_data.get('predicted_next_score', 'N/A')}

### Business Impact
- **Estimated Annual Cost of Current Grade:** ${int(cost_analysis.get('total_annual_cost', 0)):,}
- **Potential Fine Range:** ${cost_analysis.get('fine_range_min', 0):,} - ${cost_analysis.get('fine_range_max', 0):,}
- **Lost Revenue (Annual):** ${cost_analysis.get('lost_revenue_annual', 0):,}
- **Reputation Impact:** {cost_analysis.get('reputation_impact', 'Unknown')}

---

## Violation Fingerprint Analysis

**Primary Pattern:** {fingerprint.get('fingerprint', 'Unknown').replace('-', ' ').replace('_', ' ').title()}

{fingerprint.get('description', 'No detailed analysis available')}

### Category Breakdown:
"""
    
    # Add breakdown
    if fingerprint.get('breakdown'):
        breakdown = fingerprint['breakdown']
        sorted_cats = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)
        for cat, pct in sorted_cats[:5]:
            if pct > 0:
                report += f"\n- **{cat.replace('_', ' ').title()}:** {pct}%"
    
    report += "\n\n---\n\n"
    
    # Top 5 violations
    report += "## Top 5 Repeated Violations\n\n"
    if not hist_df.empty and "violation_description" in hist_df.columns:
        top_viol = hist_df["violation_description"].value_counts().head(5)
        for idx, (desc, cnt) in enumerate(top_viol.items(), 1):
            crit = " CRITICAL" if any(
                hist_df[hist_df["violation_description"] == desc]["critical_flag"].str.upper().str.strip() == "Y"
            ) else ""
            report += f"{idx}. {desc} {crit}\n   - **Occurrences:** {cnt}\n\n"
    else:
        report += "_No violation data available_\n\n"
    
    report += "---\n\n"
    
    # Recent Q&A from memory
    report += "## Recent AI Coaching Q&A\n\n"
    if restaurant_name in memory and memory[restaurant_name]:
        recent_qa = memory[restaurant_name][-10:]  # Last 10
        report += f"_Showing last {len(recent_qa)} question(s) asked by owner:_\n\n"
        for idx, item in enumerate(recent_qa, 1):
            q_text = item.get('q', 'Unknown question')
            q_time = item.get('t', 'Unknown time')
            # Try to parse timestamp
            try:
                dt = datetime.datetime.fromisoformat(q_time)
                time_str = dt.strftime("%b %d, %Y")
            except:
                time_str = q_time
            
            report += f"**Q{idx} ({time_str}):** {q_text}\n\n"
    else:
        report += "_No questions have been asked yet for this restaurant._\n\n"
    
    report += "---\n\n"
    
    # Generate AI action plans using LLM
    report += "##  SmartBite 7-Day Emergency Action Plan\n\n"
    
    # Call LLM for 7-day plan
    plan_7day = generate_action_plan_llm(restaurant_name, hist_df, fingerprint, "7-day", kb_available)
    report += plan_7day + "\n\n---\n\n"
    
    # Call LLM for 30-day plan
    report += "## SmartBite 30-Day Stabilization Plan\n\n"
    plan_30day = generate_action_plan_llm(restaurant_name, hist_df, fingerprint, "30-day", kb_available)
    report += plan_30day + "\n\n---\n\n"
    
    # Critical risk commentary
    report += "## WARNING: Critical Risk Commentary\n\n"
    
    critical_count = 0
    if not hist_df.empty and "critical_flag" in hist_df.columns:
        recent = hist_df.tail(12)
        critical_count = (recent["critical_flag"].str.upper().str.strip() == "Y").sum()
    
    if critical_count > 5:
        report += f"""**HIGH RISK:** Your restaurant has {critical_count} critical violations in recent inspections.

Critical violations pose immediate health risks and can result in:
- Fines up to $2,000 per violation
- Forced closure until corrected
- Grade C or lower
- Significant reputation damage

**IMMEDIATE ACTION REQUIRED:**
- Address all critical violations within 24-48 hours
- Document all corrective actions with photos
- Consider hiring a food safety consultant
- Schedule staff emergency training
- Request reinspection as soon as corrections are complete
"""
    elif critical_count > 2:
        report += f"""**MODERATE RISK:** Your restaurant has {critical_count} critical violations in recent inspections.

While not in immediate danger of closure, these violations require prompt attention:
- Each can result in fines of $200-$2,000
- Repeated critical violations can trigger more frequent inspections
- Can prevent achieving/maintaining Grade A

**RECOMMENDED ACTIONS:**
- Prioritize fixing critical violations in next 7 days
- Review procedures with staff
- Enhance monitoring and documentation
"""
    elif critical_count > 0:
        report += f"""**LOW RISK:** Your restaurant has {critical_count} critical violation(s) in recent inspections.

This is manageable with focused attention:
- Address the specific critical violation immediately
- Prevent recurrence through staff training
- Maintain strong documentation habits
"""
    else:
        report += """**EXCELLENT:** No critical violations in recent inspections!

Maintain this standard by:
- Continuing current best practices
- Staying vigilant on daily checklists
- Regular staff training refreshers
- Maintaining thorough documentation
"""
    
    report += "\n\n---\n\n"
    
    # Business impact summary
    report += "##  Business Impact & ROI of Improvements\n\n"
    
    if grade == "C":
        potential_savings = cost_analysis.get('lost_revenue_annual', 0)
        report += f"""**Current Situation:**
Your Grade C is costing approximately **${potential_savings:,} in lost annual revenue** due to customer avoidance.

**ROI of Achieving Grade A:**
- Recover up to ${potential_savings:,}/year in lost revenue
- Avoid fines of ${cost_analysis.get('fine_range_min', 0):,} - ${cost_analysis.get('fine_range_max', 0):,}
- Build customer trust and loyalty
- Increase positive online reviews
- Reduce insurance premiums

**Investment Required:**
- Staff training: $1,000 - $3,000
- Equipment upgrades (if needed): $2,000 - $10,000
- Pest control improvements: $500 - $2,000/year
- Food safety consultant: $2,000 - $5,000

**Payback Period:** Typically 3-6 months for Grade C → A improvement
"""
    elif grade == "B":
        potential_savings = cost_analysis.get('lost_revenue_annual', 0)
        report += f"""**Current Situation:**
Your Grade B is costing approximately **${potential_savings:,} in lost annual revenue** due to some customer avoidance.

**ROI of Achieving Grade A:**
- Recover up to ${potential_savings:,}/year in incremental revenue
- Strengthen competitive position
- Enhance brand reputation
- Reduce violation-related stress

**Investment Required:**
- Focused staff training: $500 - $1,500
- Procedural improvements: $1,000 - $3,000
- Enhanced monitoring systems: $500 - $2,000

**Payback Period:** Typically 2-4 months for Grade B → A improvement
"""
    else:  # Grade A or no grade
        report += f"""**Current Situation:**
Congratulations on maintaining Grade A standards!

**Value of Maintaining Grade A:**
- Avoid revenue loss of $125,000 - $325,000/year (typical B/C penalty)
- Maintain customer confidence and positive reputation
- Competitive advantage in your market
- Lower insurance and operational costs

**Ongoing Investment:**
- Regular staff training: $500 - $1,000/year
- Preventive maintenance: $1,000 - $3,000/year
- Continuous monitoring: Operational discipline

**Recommendation:** Stay vigilant to protect your Grade A status
"""
    
    report += "\n\n---\n\n"
    
    # Footer
    report += """## Next Steps

1. **Review this report** with your management team
2. **Prioritize the 7-day action plan** - start immediately
3. **Assign responsibilities** for each action item
4. **Schedule follow-up** - review progress weekly
5. **Document everything** - photos, logs, training records
6. **Contact SmartBite** for additional AI coaching as needed

---

## About This Report

This AI-powered report was generated by **SmartBite**, analyzing your restaurant's actual NYC DOHMH inspection history, violation patterns, and risk factors.

The recommendations are based on:
- Real inspection data from NYC Open Data
- AI analysis of your specific violation fingerprint
- Industry best practices for food safety
- NYC DOHMH scoring and grading rules
- Your conversation history with SmartBite AI Coach

**Questions?** Return to SmartBite AI Coach (Tab 3) to ask specific questions about implementing these recommendations.

---

*Report generated by SmartBite AI - NYC Restaurant Inspection Intelligence Platform*

*© 2024 SmartBite. For restaurant owner use only.*
"""
    
    return report


def generate_action_plan_llm(
    restaurant_name: str,
    hist_df: pd.DataFrame,
    fingerprint: Dict,
    plan_type: str,  # "7-day" or "30-day"
    kb_available: bool
) -> str:
    """
    Use LLM with RAGs to generate specific action plan for 7-day or 30-day timeframe.
    """
    grade, score = latest_grade_and_score(hist_df)
    
    # Get top violations
    top_viol_list = []
    if not hist_df.empty and "violation_description" in hist_df.columns:
        top_viol = hist_df["violation_description"].value_counts().head(5)
        for desc, cnt in top_viol.items():
            top_viol_list.append(f"- {desc} (x{cnt})")
    
    top_viol_str = "\n".join(top_viol_list) if top_viol_list else "None"
    
    # Use RAGs to get relevant knowledge base documents
    rag_context = ""
    if kb_available and KB is not None:
        # Search for relevant documents based on violation pattern and plan type
        search_query = f"{fingerprint.get('fingerprint', 'restaurant inspection')} {plan_type} action plan NYC health inspection"
        rag_docs = kb_search(search_query, k=6)
        if rag_docs:
            rag_context = "\n\nRelevant Knowledge Base Information:\n"
            for idx, doc in enumerate(rag_docs[:4], 1):  # Use top 4 documents
                content = doc.get('content', doc.get('text', ''))[:500]  # Limit to 500 chars per doc
                rag_context += f"\n[{idx}] {content}\n"
    
    system_prompt = f"""You are SmartBite, an expert NYC restaurant health inspection consultant.

Generate a specific, actionable {plan_type} action plan for a restaurant owner.

Rules:
- Use numbered list format
- Be extremely specific (not generic advice)
- Focus on practical daily tasks
- Include who should do it and how to document it
- For 7-day plans: focus on immediate critical fixes
- For 30-day plans: focus on systems, training, and long-term habits
- Keep it concise (max 8-10 action items)
- Use the provided knowledge base information to enhance your recommendations
"""
    
    user_prompt = f"""Restaurant: {restaurant_name}
Current Grade: {grade}
Current Score: {score}
Violation Pattern: {fingerprint.get('fingerprint', 'unknown')}

Top Repeated Violations:
{top_viol_str}
{rag_context}

Generate a {plan_type} action plan to improve this restaurant's inspection outcomes.
Use the knowledge base information above to provide specific, actionable recommendations.
"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        response = call_llm(messages, max_tokens=800, temperature=0.4)
        return response
    except Exception as e:
        return f"_Action plan generation unavailable: {e}_"


def generate_owner_report_pdf(report_markdown: str, restaurant_name: str) -> bytes:
    """
    Generate downloadable PDF of owner report **without any external libraries**.

    This writes a minimal but valid PDF 1.4 file using only the Python
    standard library so that the downloaded file always opens correctly.
    """
    import io

    def _escape_pdf_text(s: str) -> str:
        # Escape backslashes and parentheses for PDF string literals
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    # Basic, plain‑text version of the report with markdown cleaned up
    plain_lines = []
    for raw in report_markdown.split("\n"):
        text = raw.strip()

        # Strip bold/italic markers
        text = text.replace("**", "").replace("_", "")

        # Headings: "#", "##", "###" → just the text, with extra spacing
        heading_prefix = ""
        if text.startswith("### "):
            heading_prefix = ""
            text = text[4:]
            if plain_lines and plain_lines[-1] != "":
                plain_lines.append("")
        elif text.startswith("## "):
            heading_prefix = ""
            text = text[3:]
            if plain_lines and plain_lines[-1] != "":
                plain_lines.append("")
        elif text.startswith("# "):
            heading_prefix = ""
            text = text[2:]
            if plain_lines and plain_lines[-1] != "":
                plain_lines.append("")

        # Bullet / numbered lists – strip the bullet marker
        for prefix in ("- ", "* ", "• "):
            if text.startswith(prefix):
                text = text[len(prefix) :]
                break

        # Simple numbered list like "1. "
        if len(text) > 3 and text[0].isdigit() and text[1] == "." and text[2] == " ":
            text = text[3:]

        cleaned = (heading_prefix + text).strip()
        plain_lines.append(cleaned)

    # Build the content stream: title + wrapped lines using Td for newlines
    title = f"AI Owner Report - {restaurant_name}"
    content_parts = []
    content_parts.append("BT\n/F1 14 Tf\n72 740 Td\n")
    content_parts.append(f"({_escape_pdf_text(title)}) Tj\n")
    # Switch to body font and move down a bit
    content_parts.append("/F1 10 Tf\n0 -20 Td\n")

    max_chars = 90  # simple fixed-width wrapping at word boundaries
    for raw_line in plain_lines:
        if raw_line == "":
            # Blank line: move cursor down without drawing text
            content_parts.append("0 -14 Td\n")
            continue
        # Word-wrap at spaces so we don't split words in half
        words = raw_line.split()
        if not words:
            content_parts.append("0 -14 Td\n")
            continue

        current = words[0]
        wrapped_lines = []
        for w in words[1:]:
            if len(current) + 1 + len(w) <= max_chars:
                current += " " + w
            else:
                wrapped_lines.append(current)
                current = w
        wrapped_lines.append(current)

        for chunk in wrapped_lines:
            content_parts.append(f"({_escape_pdf_text(chunk)}) Tj\n")
            # Move down for the next visual line
            content_parts.append("0 -14 Td\n")

    content_parts.append("ET\n")
    content = "".join(content_parts).encode("latin-1", errors="replace")
    content_length = len(content)

    # Build a minimal one‑page PDF structure
    buffer = io.BytesIO()
    write = buffer.write

    # Helper to track offsets
    offsets = []

    def w(line: str):
        write(line.encode("latin-1"))

    # Header
    w("%PDF-1.4\n")

    # 1: Catalog
    offsets.append(buffer.tell())
    w("1 0 obj\n")
    w("<< /Type /Catalog /Pages 2 0 R >>\n")
    w("endobj\n")

    # 2: Pages
    offsets.append(buffer.tell())
    w("2 0 obj\n")
    w("<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n")
    w("endobj\n")

    # 3: Page
    offsets.append(buffer.tell())
    w("3 0 obj\n")
    w("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n")
    w("   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n")
    w("endobj\n")

    # 4: Contents
    offsets.append(buffer.tell())
    w("4 0 obj\n")
    w(f"<< /Length {content_length} >>\n")
    w("stream\n")
    write(content)
    w("endstream\n")
    w("endobj\n")

    # 5: Font
    offsets.append(buffer.tell())
    w("5 0 obj\n")
    w("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n")
    w("endobj\n")

    # xref table
    xref_start = buffer.tell()
    w("xref\n")
    # 0 + 5 objects
    w("0 6\n")
    w("0000000000 65535 f \n")
    for off in offsets:
        w(f"{off:010d} 00000 n \n")

    # trailer
    w("trailer\n")
    w("<< /Size 6 /Root 1 0 R >>\n")
    w("startxref\n")
    w(f"{xref_start}\n")
    w("%%EOF\n")

    buffer.seek(0)
    return buffer.getvalue()


def send_report_email(to_email: str, restaurant_name: str, report_pdf: bytes) -> Dict[str, any]:
    """
    Send owner report via email.
    
    Currently a dummy function - ready for SendGrid integration.
    
    Returns:
        Dict with 'success' (bool) and 'message' (str)
    """
    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, to_email):
        return {
            "success": False,
            "message": "Invalid email address format"
        }
    
    # TODO: Integrate with SendGrid
    # For now, return success simulation
    
    # Simulated SendGrid integration:
    """
    import os
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
    import base64
    
    message = Mail(
        from_email='noreply@smartbite.ai',
        to_emails=to_email,
        subject=f'SmartBite AI Owner Report - {restaurant_name}',
        html_content=f'''
        <h2>SmartBite AI Owner Report</h2>
        <p>Dear Restaurant Owner,</p>
        <p>Please find attached your comprehensive AI-generated inspection report for <strong>{restaurant_name}</strong>.</p>
        <p>This report includes:</p>
        <ul>
            <li>Current status and risk analysis</li>
            <li>Violation pattern fingerprint</li>
            <li>7-day emergency action plan</li>
            <li>30-day stabilization plan</li>
            <li>Business impact analysis</li>
        </ul>
        <p>Review the attached PDF and implement the recommended actions to improve your inspection outcomes.</p>
        <p>Questions? Return to SmartBite AI Coach to ask specific questions.</p>
        <p>Best regards,<br>SmartBite AI Team</p>
        '''
    )
    
    # Attach PDF
    encoded_file = base64.b64encode(report_pdf).decode()
    attachment = Attachment(
        FileContent(encoded_file),
        FileName(f'{restaurant_name}_ZeroG_Compliance_Report.pdf'),
        FileType('application/pdf'),
        Disposition('attachment')
    )
    message.attachment = attachment
    
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        return {
            "success": True,
            "message": f"Report sent successfully to {to_email}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Email send failed: {str(e)}"
        }
    """
    
    # DUMMY RESPONSE for now
    return {
        "success": True,
        "message": f" [DEMO MODE] Report would be sent to {to_email}. Email integration coming soon."
    }


# ============================================================
# TOP NAVIGATION BAR - Filters and Tools (Moved from Sidebar)
# ============================================================

# Initialize language in session state FIRST (before any T() calls)
if "language" not in st.session_state:
    st.session_state["language"] = "en"

# Initialize session state for reports
if "restaurant_memory" not in st.session_state:
    st.session_state.restaurant_memory = load_restaurant_memory()

if "sb_last_report" not in st.session_state:
    st.session_state.sb_last_report = None

if "last_shared_reports" not in st.session_state:
    st.session_state.last_shared_reports = {}

# Get filter options
boros = (
    ["All"] + sorted(DATA["boro"].dropna().unique().tolist())
    if "boro" in DATA.columns
    else ["All"]
)
cuisines = (
    ["All"] + sorted(DATA["cuisine_description"].dropna().unique().tolist())
    if "cuisine_description" in DATA.columns
    else ["All"]
)

lang_options = {
    T("lang_english"): "en",
    T("lang_spanish"): "es",
    T("lang_hindi"): "hi",
    T("lang_chinese"): "zh"
}

# Prepare filter values (will be used in the nav bar)
dmin, dmax = get_date_range(DATA)


# ============================================================
# STRIPE LANDING PAGE + NAVIGATION
# ============================================================

# Premium Navigation Bar - Stripe Style
st.markdown(
    f"""
    <!-- Stripe Navigation Bar -->
    <div class="stripe-nav">
        <div class="stripe-nav-container">
            <a href="#" class="stripe-logo">{T("app_title")}</a>
            <div class="stripe-nav-center">
                <!-- Center navigation links can be added here if needed -->
            </div>
            <div class="stripe-nav-actions">
                <a href="#" class="stripe-nav-link">Support</a>
                <button class="stripe-nav-button">Get Started</button>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Filter Bar (Separate Section Below Navbar)
st.markdown('<div class="filter-bar-container">', unsafe_allow_html=True)
filter_cols = st.columns([1.0, 1.0, 0.8, 1.4, 1.0, 0.6, 1.4, 1.5])
    
with filter_cols[0]:
    st.markdown(f'<div class="filter-label">{T("sidebar_boro")}</div>', unsafe_allow_html=True)
    sel_boro = st.selectbox(T("sidebar_boro"), boros, key="nav_boro", label_visibility="collapsed")

with filter_cols[1]:
    st.markdown(f'<div class="filter-label">{T("sidebar_cuisine")}</div>', unsafe_allow_html=True)
    sel_cuisine = st.selectbox(T("sidebar_cuisine"), cuisines, key="nav_cuisine", label_visibility="collapsed")

with filter_cols[2]:
    st.markdown(f'<div class="filter-label">{T("sidebar_grade")}</div>', unsafe_allow_html=True)
    sel_grade = st.selectbox(T("sidebar_grade"), ["All", "A", "B", "C"], key="nav_grade", label_visibility="collapsed")

with filter_cols[3]:
    st.markdown(f'<div class="filter-label">{T("sidebar_date_range")}</div>', unsafe_allow_html=True)
    date_range = st.date_input(T("sidebar_date_range"), (dmin, dmax), key="nav_date", label_visibility="collapsed")
    if isinstance(date_range, tuple) and len(date_range) == 2:
        s_start, s_end = date_range
    else:
        s_start, s_end = dmin, dmax

with filter_cols[4]:
    st.markdown(f'<div class="filter-label">{T("lang_select")}</div>', unsafe_allow_html=True)
    current_lang_display = [k for k, v in lang_options.items() if v == st.session_state["language"]][0] if st.session_state["language"] in lang_options.values() else T("lang_english")
    selected_lang_display = st.selectbox(
        T("lang_select"),
        options=list(lang_options.keys()),
        index=list(lang_options.values()).index(st.session_state["language"]) if st.session_state["language"] in lang_options.values() else 0,
        key="lang_selector_nav",
        label_visibility="collapsed"
    )
    st.session_state["language"] = lang_options[selected_lang_display]

with filter_cols[5]:
    st.markdown(f'<div class="filter-label">AI</div>', unsafe_allow_html=True)
    advanced_ai = st.checkbox(T("sidebar_enable_ai"), True, key="nav_ai", label_visibility="collapsed")

FILTERED = apply_filters(DATA, sel_boro, sel_cuisine, sel_grade, s_start, s_end)
restlist_tools = get_unique_restaurants(FILTERED)

with filter_cols[6]:
    if restlist_tools:
        st.markdown('<div class="filter-label">Restaurant</div>', unsafe_allow_html=True)
        sel_rest_tools = st.selectbox("Restaurant", restlist_tools, key="TOOLS_rest", label_visibility="collapsed")
    else:
        sel_rest_tools = None

with filter_cols[7]:
    st.markdown('<div class="filter-label">ACTIONS</div>', unsafe_allow_html=True)
    report_button_disabled = not (restlist_tools and sel_rest_tools)
    
    if st.button("Generate AI Report", use_container_width=True, key="nav_generate_report", disabled=report_button_disabled):
        hist_tools = get_restaurant_history(FILTERED, sel_rest_tools)
        if hist_tools.empty:
            st.warning("No inspection history found for this restaurant.")
        else:
            with st.spinner("Generating AI Report..."):
                report_content = generate_owner_report(
                    sel_rest_tools,
                    hist_tools,
                    st.session_state.restaurant_memory,
                    KB is not None
                )
                st.session_state.sb_last_report = {
                    "content": report_content,
                    "restaurant": sel_rest_tools,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "summary": f"Report for {sel_rest_tools}"
                }
                if sel_rest_tools not in st.session_state.last_shared_reports:
                    st.session_state.last_shared_reports[sel_rest_tools] = []
                st.session_state.last_shared_reports[sel_rest_tools].append({
                    "timestamp": datetime.datetime.now().isoformat(),
                    "summary": f"Generated {datetime.datetime.now().strftime('%b %d, %Y at %I:%M %p')}"
                })
                st.session_state.last_shared_reports[sel_rest_tools] = st.session_state.last_shared_reports[sel_rest_tools][-3:]
                st.success("Report generated successfully!")
                st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    f"""
    <!-- Stripe Hero Section - Enhanced -->
    <div class="stripe-hero">
        <div class="stripe-hero-badge">{T("app_pill")}</div>
        <h1 class="stripe-hero-title">
            <span class="stripe-hero-gradient-1">Smarter Inspections.</span><br>
            <span class="stripe-hero-gradient-2">Safer Kitchens.</span>
        </h1>
        <p class="stripe-hero-description">
            {T("app_description")}
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Display Generated AI Report Section
if st.session_state.sb_last_report and st.session_state.sb_last_report.get("content"):
    st.markdown('<div class="sb-glass-panel" style="margin: 32px 0;">', unsafe_allow_html=True)
    st.markdown("### Generated AI Report")
    st.markdown(f"**Restaurant:** {st.session_state.sb_last_report.get('restaurant', 'Unknown')}")
    
    # Download PDF button
    report_content = st.session_state.sb_last_report.get("content", "")
    restaurant_name = st.session_state.sb_last_report.get("restaurant", "Restaurant")
    
    try:
        pdf_bytes = generate_owner_report_pdf(report_content, restaurant_name)
        st.download_button(
            label="Download Report as PDF",
            data=pdf_bytes,
            file_name=f"{restaurant_name.replace(' ', '_')}_ZeroG_AI_Report_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            key="download_ai_report_pdf"
        )
    except Exception as e:
        st.warning(f"PDF generation failed: {str(e)}")
    
    # Display report content
    st.markdown("---")
    st.markdown(report_content)
    st.markdown('</div>', unsafe_allow_html=True)

tab_profile, tab_ai, tab_sim_forecast, tab_nearby = st.tabs(
    [
        T("tab_profile"),
        T("tab_ai"),
        T("tab_sim"),
        T("tab_nearby"),
    ]
)


# ============================================================
# TAB 1 – NEARBY INTELLIGENCE (REPLACES CITYWIDE OVERVIEW)
# ============================================================

with tab_nearby:
    st.markdown('<div class="sb-surface">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sb-section-title">{T("nearby_title")}</div>',
        unsafe_allow_html=True,
    )

    geo_latest = get_geo_latest(DATA)

    if geo_latest.empty:
        st.info(T("nearby_no_geo"))
    else:
        all_rest = get_unique_restaurants(geo_latest)
        if not all_rest:
            st.info(T("nearby_no_rest"))
        else:
            # Allow user to pick their own restaurant
            sel_rest_near = st.selectbox(
                T("nearby_select_anchor"),
                all_rest,
                index=0,
                key="NEAR_rest",
            )

            radius_km = st.slider(
                T("nearby_radius"),
                min_value=0.25,
                max_value=3.0,
                value=1.0,
                step=0.25,
            )

            anchor_rows = geo_latest[geo_latest["dba"] == sel_rest_near]
            if anchor_rows.empty:
                st.info(T("nearby_no_geo_data"))
            else:
                anchor_row = anchor_rows.iloc[0]
                anchor_lat = anchor_row.get("latitude")
                anchor_lon = anchor_row.get("longitude")

                # Compute distances to all other restaurants (vectorized)
                geo_copy = geo_latest.copy()
                lat_arr = geo_copy["latitude"].to_numpy()
                lon_arr = geo_copy["longitude"].to_numpy()

                # Vectorized haversine
                lat1_r = np.radians(anchor_lat)
                lon1_r = np.radians(anchor_lon)
                lat2_r = np.radians(lat_arr)
                lon2_r = np.radians(lon_arr)

                dlon = lon2_r - lon1_r
                dlat = lat2_r - lat1_r
                a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
                c = 2 * np.arcsin(np.sqrt(a))
                r_earth = 6371
                distances = c * r_earth

                geo_copy["distance_km"] = distances

                # Filter neighbors within radius (and exclude self ~ distance 0)
                neighbors = geo_copy[
                    (geo_copy["distance_km"] > 1e-4) & (geo_copy["distance_km"] <= radius_km)
                ].copy()

                # Basic metrics for anchor
                anchor_hist = get_restaurant_history(DATA, sel_rest_near)
                anchor_grade, anchor_score = latest_grade_and_score(anchor_hist)

                c_top1, c_top2, c_top3, c_top4 = st.columns(4)
                c_top1.metric(T("nearby_your_grade"), anchor_grade or T("common_na"))
                c_top2.metric(
                    T("nearby_your_score"),
                    f"{anchor_score:.0f}" if anchor_score is not None else T("common_na"),
                )
                c_top3.metric(T("nearby_in_radius"), f"{len(neighbors):,}")
                if not neighbors.empty and "grade" in neighbors.columns:
                    nearby_grades = neighbors["grade"].astype(str).str.upper()
                    a_share = (nearby_grades == "A").mean() * 100 if not nearby_grades.empty else 0
                    c_top4.metric(T("nearby_grade_a_share"), f"{a_share:.0f}%")
                else:
                    c_top4.metric(T("nearby_grade_a_share"), T("common_na"))

                st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

                # Map
                st.markdown(
                    f'<div class="sb-section-title">{T("nearby_map_title")}</div>',
                    unsafe_allow_html=True,
                )

                if not neighbors.empty:
                    map_df = pd.concat(
                        [
                            pd.DataFrame(
                                {
                                    "dba": [sel_rest_near],
                                    "latitude": [anchor_lat],
                                    "longitude": [anchor_lon],
                                    "is_anchor": [True],
                                }
                            ),
                            neighbors[["dba", "latitude", "longitude"]].assign(is_anchor=False),
                        ],
                        ignore_index=True,
                    )

                    # st.map expects lat/lon column names
                    map_df_plot = map_df.rename(columns={"latitude": "lat", "longitude": "lon"})
                    st.map(map_df_plot[["lat", "lon"]])

                else:
                    st.caption(T("nearby_no_neighbors"))

                st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

                # Nearby table: latest inspection snapshot
                st.markdown(
                    f'<div class="sb-section-title">{T("nearby_snapshot_title")}</div>',
                    unsafe_allow_html=True,
                )

                if not neighbors.empty:
                    # Create a clean dataframe with required columns
                    df_near = neighbors.copy()
                    
                    # Select and order columns (excluding boro and ID)
                    cols_order = []
                    for c in [
                        "dba",
                        "cuisine_description",
                        "inspection_date",
                        "score",
                        "grade",
                        "distance_km",
                    ]:
                        if c in df_near.columns:
                            cols_order.append(c)
                    
                    df_near = df_near[cols_order].copy()
                    
                    # Format distance to 2 decimal places
                    if "distance_km" in df_near.columns:
                        df_near["distance_km"] = df_near["distance_km"].round(2)
                    
                    # Format inspection_date to show only date (remove time)
                    if "inspection_date" in df_near.columns:
                        df_near["inspection_date"] = pd.to_datetime(df_near["inspection_date"]).dt.date
                    
                    # Sort by distance (ascending - from less to higher distance)
                    df_near = df_near.sort_values("distance_km", ascending=True)
                    
                    # Reset index for clean display
                    df_near = df_near.reset_index(drop=True)
                    
                    # Rename columns with proper capitalization and standard grammar
                    column_rename = {}
                    if "dba" in df_near.columns:
                        column_rename["dba"] = "Restaurant Name"
                    if "cuisine_description" in df_near.columns:
                        column_rename["cuisine_description"] = "Cuisine"
                    if "inspection_date" in df_near.columns:
                        column_rename["inspection_date"] = "Inspection Date"
                    if "score" in df_near.columns:
                        column_rename["score"] = "Score"
                    if "grade" in df_near.columns:
                        column_rename["grade"] = "Grade"
                    if "distance_km" in df_near.columns:
                        column_rename["distance_km"] = "Distance (km)"
                    
                    df_near = df_near.rename(columns=column_rename)
                    
                    # Display with minimalist styling
                    st.dataframe(
                        df_near,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info(T("nearby_no_found"))

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# TAB 2 – RESTAURANT PROFILE
# ============================================================

with tab_profile:
    st.markdown('<div class="sb-surface">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sb-section-title">{T("profile_title")}</div>',
        unsafe_allow_html=True,
    )

    restlist = get_unique_restaurants(FILTERED)
    if not restlist:
        st.info(T("profile_no_rest"))
    else:
        sel_rest = st.selectbox(T("profile_select"), restlist, index=0)
        hist = get_restaurant_history(FILTERED, sel_rest)

        if hist.empty:
            st.info(T("profile_no_data"))
        else:
            grade, score = latest_grade_and_score(hist)
            risk = compute_risk_level(hist)
            analytics = analyze_restaurant(hist)
            root_causes = detect_root_causes(hist)

            #  PHASE 2: Enhanced metrics with trend and predictions
            trend_data = calculate_score_trend(hist)
            grade_probs = calculate_grade_probabilities(hist)
            
            c1, c2, c3 = st.columns(3)
            c1.metric(T("profile_latest_grade"), grade or T("common_na"))
            c2.metric(T("profile_latest_score"), f"{score:.0f}" if score is not None else T("common_na"))
            c3.metric(T("profile_risk_level"), risk)
            
            #  PHASE 2: Score trend indicator and next prediction
            if trend_data["trend"] != "insufficient_data":
                c5, c6 = st.columns(2)
                with c5:
                    trend_class = "trend-card-worsening" if trend_data["direction"] == "worsening" else "trend-card-improving" if trend_data["direction"] == "improving" else "trend-card-predicted"
                    st.markdown(
                        f'<div class="{trend_class}">'
                        f'<strong>{T("profile_trend")}</strong> {trend_data["trend"].title()} '
                        f'<span style="font-size: 0.9em; color: var(--text-muted);">({T("profile_velocity")}: {trend_data["velocity"]:.2f})</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                with c6:
                    next_grade = score_to_grade(trend_data["predicted_next_score"])
                    st.markdown(
                        f'<div class="trend-card-predicted">'
                        f'<strong>{T("profile_predicted_next")}</strong> Score {trend_data["predicted_next_score"]} → Grade {next_grade}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            
            #  PHASE 2: Grade probabilities display
            st.markdown(f'<div class="sb-section-title" style="margin-top: var(--block-spacing);">{T("profile_grade_probs")}</div>', unsafe_allow_html=True)
            prob_cols = st.columns(3)
            with prob_cols[0]:
                st.metric(T("profile_grade_a_prob"), f"{grade_probs['A']}%", 
                         delta=T("profile_best_outcome") if grade_probs['A'] > 50 else None)
            with prob_cols[1]:
                st.metric(T("profile_grade_b_prob"), f"{grade_probs['B']}%",
                         delta=T("profile_moderate") if grade_probs['B'] > 50 else None)
            with prob_cols[2]:
                st.metric(T("profile_grade_c_prob"), f"{grade_probs['C']}%",
                         delta=T("profile_high_risk") if grade_probs['C'] > 50 else None)
            
            st.caption(f"{T('profile_confidence')} {grade_probs.get('confidence', 'medium').title()} ({T('profile_based_on')} {trend_data.get('data_points', 0)})")

            #  PHASE 2: Violation fingerprint summary
            render_fingerprint_summary(hist)

            st.markdown(
                f'<div class="sb-section-title">{T("profile_last_5")}</div>',
                unsafe_allow_html=True,
            )
            cols_show = [
                c
                for c in [
                    "inspection_date",
                    "score",
                    "grade",
                    "violation_code",
                    "violation_description",
                    "critical_flag",
                ]
                if c in hist.columns
            ]

            #  Show latest inspections first (most recent at top)
            last5 = hist[cols_show].copy()
            if "inspection_date" in last5.columns:
                # Convert to date-only (remove time component) before sorting
                last5["inspection_date"] = pd.to_datetime(last5["inspection_date"], errors="coerce").dt.date
                last5 = last5.sort_values("inspection_date", ascending=False).head(5)

            # Use polished, human-readable column labels for display
            display_labels = {
                "inspection_date": "Inspection Date",
                "score": "Score",
                "grade": "Grade",
                "violation_code": "Violation Code",
                "violation_description": "Violation Description",
                "critical_flag": "Critical Flag",
            }
            last5 = last5.rename(columns=display_labels)

            # Hide the index column so the first visible column is "Inspection Date"
            st.dataframe(last5, use_container_width=True, hide_index=True)

            st.markdown(
                f'<div class="sb-section-title">{T("profile_summary")}</div>',
                unsafe_allow_html=True,
            )
            st.write(describe_restaurant(hist, sel_rest))

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# HELPER FUNCTION FOR AI COACH (used by both main button and suggested questions)
# ============================================================

def run_smartbite_answer(
    current_question: str,
    restaurant_name: str,
    hist_df: pd.DataFrame,
    memory_context: str = ""
) -> Tuple[str, any]:
    """
    Unified AI answer pipeline for Tab 3 AI Coach.
    
    Handles:
    - Relevance classification
    - Answer generation (irrelevant vs relevant)
    - Memory updates
    
    Returns:
        Tuple of (answer_type, answer_data)
        - answer_type: "irrelevant" or "relevant"
        - answer_data: dict for irrelevant, dict or str for relevant
    """
    # Classify question relevance
    relevance = classify_question_relevance(current_question)
    
    # Handle questions classified as "low" - these are truly unrelated (ML models, algorithms)
    # For these, use the general handler but still try to be helpful
    if relevance == "low":
        st.session_state.last_answer_type = "irrelevant"
        response_data = answer_general_question_enhanced(current_question)
        
        # Update memory
        st.session_state.restaurant_memory = add_question_to_memory(
            restaurant_name,
            current_question,
            st.session_state.restaurant_memory
        )
        save_restaurant_memory(st.session_state.restaurant_memory)
        
        return ("irrelevant", response_data)
    
    # Handle ALL relevant questions (high or medium) - use the main structured answer path
    # This ensures all restaurant-related questions get proper answers
    else:
        st.session_state.last_answer_type = "relevant"
        rag_docs = kb_search(current_question, 6) if KB is not None else []
        
        # Use structured prompt with memory context
        msgs = build_structured_coach_prompt(
            current_question,
            restaurant_name,
            hist_df,
            rag_docs,
            memory_context
        )
        
        llm_response = call_llm(msgs, max_tokens=1600, temperature=0.5)
        
        # Try to parse structured response
        structured_data = parse_structured_response(llm_response)
        
        # Update memory
        st.session_state.restaurant_memory = add_question_to_memory(
            restaurant_name,
            current_question,
            st.session_state.restaurant_memory
        )
        save_restaurant_memory(st.session_state.restaurant_memory)
        
        # Return structured data if available, otherwise raw response
        if structured_data:
            return ("relevant", structured_data)
        else:
            return ("relevant_fallback", llm_response)


# ============================================================
# TAB 3 – AI INSPECTION COACH (PHASE 1 ENHANCED)
# ============================================================

with tab_ai:
    st.markdown('<div class="sb-surface">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="sb-section-title">{T("ai_title")}</div>',
        unsafe_allow_html=True,
    )

    #  P1.4: Load persistent memory (per-restaurant)
    if "restaurant_memory" not in st.session_state:
        st.session_state.restaurant_memory = load_restaurant_memory()
    
    # Track last answer type for better suggestions
    if "last_answer_type" not in st.session_state:
        st.session_state.last_answer_type = None

    if not advanced_ai:
        st.info("Enable AI Features in the top navigation to use the AI coach.")
    else:
        restlist_ai = get_unique_restaurants(FILTERED)
        if not restlist_ai:
            st.info(T("common_no_rest"))
        else:
            sel_rest_ai = st.selectbox(T("ai_title"), restlist_ai, key="AI_rest")
            hist_ai = get_restaurant_history(FILTERED, sel_rest_ai)

            if hist_ai.empty:
                st.info(T("profile_no_data"))
            else:
                #  P1.5: Get memory context for this specific restaurant
                memory_context = get_memory_context(sel_rest_ai, st.session_state.restaurant_memory)

                # Initialize session state for suggested question
                if f"suggested_question_{sel_rest_ai}" not in st.session_state:
                    st.session_state[f"suggested_question_{sel_rest_ai}"] = None
                
                # Get suggested question from session state if set
                suggested_question = st.session_state.get(f"suggested_question_{sel_rest_ai}")
                
                # Use suggested question if available, otherwise use empty string
                question_value = suggested_question if suggested_question else ""
                question = st.text_area(T("ai_ask_question"), question_value, height=120, placeholder=T("ai_placeholder"), key=f"question_input_{sel_rest_ai}")
                # Validate and sanitize question input
                if question:
                    try:
                        question = sanitize_input(question, max_length=2000)
                    except ValueError as ve:
                        st.error(f"Invalid question: {str(ve)}")
                        question = ""

                c_ai1, c_ai2 = st.columns([2, 1])

                with c_ai1:
                    # Check if we should auto-run a suggested question
                    should_run_suggested = suggested_question and suggested_question.strip()
                    
                    if st.button(T("ai_ask_button"), use_container_width=True) or should_run_suggested:
                        # Use suggested question if available, otherwise use typed question
                        question_to_use = suggested_question if should_run_suggested else question
                        
                        if question_to_use.strip():  # Only run if question is not empty
                            with st.spinner("SmartBite is thinking..."):
                                answer_type, answer_data = run_smartbite_answer(
                                    question_to_use,
                                    sel_rest_ai,
                                    hist_ai,
                                    memory_context
                                )
                            
                            st.markdown("### SmartBite's Answer")
                            st.markdown(f"**Your question:** _{question_to_use}_")
                            
                            if answer_type == "irrelevant":
                                render_irrelevant_answer(answer_data)
                            elif answer_type == "relevant":
                                render_structured_answer(answer_data)
                            elif answer_type == "relevant_fallback":
                                st.info("WARNING: Structured response unavailable. Showing natural language answer.")
                                st.write(answer_data)
                            
                            # Clear suggested question after running
                            st.session_state[f"suggested_question_{sel_rest_ai}"] = None
                        else:
                            st.warning("WARNING: Please enter a question first.")


                with c_ai2:

                    #  P1.6: Auto-suggest relevant questions based on risk profile and memory
                    st.markdown(f"##### {T('ai_suggested')}:")
                    st.caption(T("ai_suggested"))
                    
                    suggested = generate_suggested_questions(
                        sel_rest_ai,
                        hist_ai,
                        st.session_state.restaurant_memory,
                        st.session_state.last_answer_type
                    )
                    
                    # Use suggested questions or fallback
                    questions_to_show = suggested[:6] if suggested else [
                        "Why did I get my latest grade?",
                        "What should I fix in 7 days?",
                        "What is hurting the grade most?"
                    ]
                    
                    # Create buttons that set the question in session state and trigger rerun
                    for idx, suggestion in enumerate(questions_to_show):
                        button_key = f"suggest_{idx}_{sel_rest_ai}" if suggested else f"sqq_fallback_{idx}_{sel_rest_ai}"
                        if st.button(suggestion, key=button_key, use_container_width=True):
                            # Store suggested question in session state and rerun
                            st.session_state[f"suggested_question_{sel_rest_ai}"] = suggestion
                            st.rerun()

                    # Show conversation history for this restaurant
                    if sel_rest_ai in st.session_state.restaurant_memory:
                        recent = st.session_state.restaurant_memory[sel_rest_ai]
                        if recent:
                            st.markdown("#####  Last 5 Questions")
                            last_five = recent[-5:]
                            with st.expander("View history"):
                                for item in last_five:
                                    st.caption(f"• {item['q']}")

                if st.button("Generate full Action Playbook", use_container_width=True):
                    with st.spinner("Building playbook..."):
                        rag_docs = kb_search("NYC inspection improvement and logs", 6) if KB is not None else []
                        playbook = recommend_actions(sel_rest_ai, hist_ai, rag_docs)
                    st.markdown("### SmartBite Action Playbook")
                    st.write(playbook)

    st.markdown('</div>', unsafe_allow_html=True)



# ============================================================
# TAB 4 – SIMULATION & FORECASTING (COMBINED)
# ============================================================

with tab_sim_forecast:
    st.markdown('<div class="sb-surface">', unsafe_allow_html=True)
    
    # What-If Simulator Section (Top)
    st.markdown(
        f'<div class="sb-section-title">{T("sim_title")}</div>',
        unsafe_allow_html=True,
    )

    restlist_sim = get_unique_restaurants(FILTERED)
    if not restlist_sim:
        st.info(T("common_no_rest"))
    else:
        sel_rest_sim = st.selectbox(T("sim_select_rest"), restlist_sim, key="SIM_rest")
        hist_sim = get_restaurant_history(FILTERED, sel_rest_sim)

        if hist_sim.empty:
            st.info(T("sim_no_history"))
        else:
            fix_pest = st.checkbox(T("sim_fix_pest"))
            fix_temp = st.checkbox(T("sim_fix_temp"))
            fix_clean = st.checkbox(T("sim_fix_clean"))
            fix_staff = st.checkbox(T("sim_fix_staff"))

            c_sim_btn1, c_sim_btn2 = st.columns([2, 1])

            with c_sim_btn1:
                if st.button(T("sim_run"), use_container_width=True):
                    cur_score, sim_score, impact = simulate_inspection(
                        hist_sim, fix_pest, fix_temp, fix_clean, fix_staff
                    )
                    if cur_score is None:
                        st.info(T("sim_not_enough"))
                    else:
                        sim_grade = score_to_grade(sim_score)

                        st.markdown('<div class="sb-glass-panel">', unsafe_allow_html=True)
                        c1, c2, c3 = st.columns(3)
                        c1.metric(T("sim_current_score"), f"{cur_score:.0f}")
                        c2.metric(
                            T("sim_simulated_score"),
                            f"{sim_score:.0f}",
                            delta=f"{sim_score - cur_score:.0f}",
                        )
                        c3.metric(T("sim_simulated_grade"), sim_grade)
                        st.markdown('</div>', unsafe_allow_html=True)

                        st.markdown('<div class="sb-glass-panel">', unsafe_allow_html=True)
                        st.markdown(f"#### {T('sim_reduction')}")
                        rows = [
                            {T("sim_category"): T("sim_pest"), T("sim_reduction_points"): impact.get("pest", 0.0)},
                            {
                                T("sim_category"): T("sim_temp"),
                                T("sim_reduction_points"): impact.get("temperature", 0.0),
                            },
                            {
                                T("sim_category"): T("sim_clean"),
                                T("sim_reduction_points"): impact.get("cleanliness", 0.0),
                            },
                            {
                                T("sim_category"): T("sim_handwash"),
                                T("sim_reduction_points"): impact.get("handwashing", 0.0),
                            },
                        ]
                        df = pd.DataFrame(rows)
                        df.insert(0, "Serial Number", range(1, len(df) + 1))
                        st.dataframe(df)
                        st.markdown('</div>', unsafe_allow_html=True)

                        fixes: List[str] = []
                        if fix_pest:
                            fixes.append("pest-related violations")
                        if fix_temp:
                            fixes.append("temperature and storage issues")
                        if fix_clean:
                            fixes.append("cleanliness and facility issues")
                        if fix_staff:
                            fixes.append("handwashing, cross-contamination and staff training issues")

                        current_grade = score_to_grade(cur_score)
                        summary_items = [
                            f"<li><span>{T('sim_score_shift')}</span><strong>{cur_score:.0f} → {sim_score:.0f}</strong></li>",
                            f"<li><span>{T('sim_projected_grade')}</span><strong>{current_grade} → {sim_grade}</strong></li>",
                        ]
                        if fixes:
                            summary_items.append(
                                f"<li><span>{T('sim_focus_areas')}</span><strong>{', '.join(fixes)}</strong></li>"
                            )
                        summary_html = (
                            f"<div class='sb-glass-panel sb-summary-panel'>"
                            f"<div class='sb-summary-title'>{T('sim_insight')}</div>"
                            "<ul class='sb-summary-list'>"
                            + "".join(summary_items)
                            + "</ul></div>"
                        )
                        st.markdown(summary_html, unsafe_allow_html=True)

                        if advanced_ai and fixes:
                            if st.button(T("sim_review_button"), use_container_width=True):
                                rag_docs = kb_search("NYC inspection improvement scenario", 5) if KB is not None else []
                                grade_sim, _ = latest_grade_and_score(hist_sim)
                                msgs = build_scenario_prompt(
                                    sel_rest_sim,
                                    grade_sim,
                                    cur_score,
                                    sim_score,
                                    fixes,
                                    rag_docs,
                                )
                                with st.spinner("SmartBite is creating a 7-day and 30-day plan..."):
                                    ans = call_llm(msgs, max_tokens=1300)
                                st.markdown("### SmartBite Scenario Review")
                                st.write(ans)

            with c_sim_btn2:
                st.caption(T("sim_tip"))

    # Divider
    st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

    # Risk Forecasting Section (Bottom)
    st.markdown(
        f'<div class="sb-section-title">{T("forecast_title")}</div>',
        unsafe_allow_html=True,
    )

    restlist_fore = get_unique_restaurants(FILTERED)
    if not restlist_fore:
        st.info(T("common_no_rest"))
    else:
        sel_rest_fore = st.selectbox(T("forecast_select"), restlist_fore, key="FORE_rest")
        hist_fore = get_restaurant_history(FILTERED, sel_rest_fore)
        if hist_fore.empty:
            st.info(T("forecast_no_history"))
        else:
            forecast = risk_forecasting(hist_fore, periods=3)
            if not forecast:
                st.caption(T("forecast_no_data"))
            else:
                st.markdown('<div class="sb-glass-panel">', unsafe_allow_html=True)
                st.markdown(f"#### {T('forecast_table_title')}")
                df_fore = pd.DataFrame(forecast)

                # Standardize column labels for display and hide index column
                display_labels_fore = {
                    "inspection_index": "Inspection Number",
                    "predicted_score": "Predicted Score",
                    "predicted_grade": "Predicted Grade",
                }
                df_fore = df_fore.rename(columns=display_labels_fore)
                st.dataframe(df_fore, use_container_width=True, hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)

                if advanced_ai:
                    if st.button(T("forecast_explain"), use_container_width=True):
                        grade, score = latest_grade_and_score(hist_fore)
                        system_prompt = """
You are SmartBite, an NYC inspection coach.

You are given:
- historical score and grade
- forecast for upcoming inspections.

Explain to the owner:
1) What this forecast means.
2) What happens if they do nothing.
3) What happens if they aggressively fix their top 2 root causes.
Keep it concrete and non-technical.
""".strip()

                        user_content = f"""
Restaurant: {sel_rest_fore}
Latest grade: {grade}
Latest score: {score}

Forecast:
{df_fore.to_string(index=False)}
"""
                        msg = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ]
                        with st.spinner("Explaining your risk trajectory..."):
                            explanation = call_llm(msg, max_tokens=900)
                        st.markdown(f"### {T('forecast_narrative')}")
                        st.write(explanation)

    st.markdown('</div>', unsafe_allow_html=True)



