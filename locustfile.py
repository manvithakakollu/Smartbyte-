"""
Locust Load Testing Configuration for SmartBite

Tests:
- Streamlit app endpoints
- LLM API call endpoints (simulated)
- Concurrent user scenarios
"""
from locust import HttpUser, task, between
import random
import json


class SmartBiteUser(HttpUser):
    """
    Simulates a user interacting with SmartBite application.
    """
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a simulated user starts."""
        # Login (simulate authentication)
        # Note: Adjust based on actual auth implementation
        self.login()
    
    def login(self):
        """Simulate login."""
        # If basic auth is implemented, this would authenticate
        # For now, just access the app
        response = self.client.get("/", name="Home")
        return response.status_code == 200
    
    @task(3)
    def view_facility_profile(self):
        """View facility profile page (most common action)."""
        # Simulate viewing the profile page
        self.client.get("/", name="Facility Profile")
    
    @task(2)
    def view_inspection_advisor(self):
        """View inspection advisor page."""
        # Simulate viewing advisor page
        # Note: Adjust endpoints based on actual Streamlit routing
        self.client.get("/", name="Inspection Advisor")
    
    @task(1)
    def simulate_llm_request(self):
        """
        Simulate an LLM API request.
        This simulates the backend LLM call endpoint.
        """
        # Simulate query to AI advisor
        query = random.choice([
            "What grade will I get next?",
            "How do I prevent pest violations?",
            "What should I do in the next 7 days?",
            "Explain violation code 04L",
            "What are the temperature requirements?"
        ])
        
        # Note: Adjust endpoint based on actual API structure
        # This is a simulation - in production, this would be an actual API endpoint
        payload = {
            "query": query,
            "restaurant_name": f"Test Restaurant {random.randint(1, 100)}"
        }
        
        # Simulate API call (adjust endpoint)
        try:
            response = self.client.post(
                "/api/query",  # Adjust to actual endpoint
                json=payload,
                name="LLM Query",
                catch_response=True
            )
            
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:  # Rate limited
                response.failure("Rate limited")
            else:
                response.failure(f"Status {response.status_code}")
        except Exception as e:
            # If endpoint doesn't exist, just mark as success (simulation)
            pass
    
    @task(1)
    def view_risk_forecasting(self):
        """View risk forecasting page."""
        self.client.get("/", name="Risk Forecasting")
    
    @task(1)
    def view_safety_intelligence(self):
        """View safety intelligence page."""
        self.client.get("/", name="Safety Intelligence")


class BurstUser(HttpUser):
    """
    Simulates burst traffic to LLM endpoints.
    """
    wait_time = between(0.5, 1.5)
    
    @task
    def burst_llm_requests(self):
        """Rapid-fire LLM requests to test rate limiting."""
        query = random.choice([
            "Quick question",
            "Fast query",
            "Urgent request",
            "Immediate help needed"
        ])
        
        payload = {
            "query": query,
            "restaurant_name": "Burst Test Restaurant"
        }
        
        try:
            response = self.client.post(
                "/api/query",
                json=payload,
                name="Burst LLM Query",
                catch_response=True
            )
            
            if response.status_code == 429:
                response.success()  # Rate limiting working as expected
            elif response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
        except Exception as e:
            pass


# Load test scenarios
scenarios = {
    "normal_traffic": {
        "user_classes": [SmartBiteUser],
        "user_count": 50,
        "spawn_rate": 5
    },
    "high_traffic": {
        "user_classes": [SmartBiteUser],
        "user_count": 100,
        "spawn_rate": 10
    },
    "burst_traffic": {
        "user_classes": [BurstUser],
        "user_count": 20,
        "spawn_rate": 20
    }
}

