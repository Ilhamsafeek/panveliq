"""
Test script to test proposal generation
Run this to see if it works
"""

import requests
import json

# Your API base URL
API_BASE = "http://localhost:8000/api/v1"

# Login first to get token
login_data = {
    "email": "admin@panveliq.com",
    "password": "password"
}

print("="*60)
print("TESTING AI PROJECT PLANNER")
print("="*60)

print("\nStep 1: Logging in...")
print(f"Trying to login with: {login_data['email']}")
login_response = requests.post(f"{API_BASE}/auth/login", json=login_data)
print(f"Login Status: {login_response.status_code}")

if login_response.status_code == 200:
    token = login_response.json()["access_token"]
    print(f"✅ Got token: {token[:30]}...")
    
    # Now test the proposal generation
    print("\nStep 2: Testing proposal generation...")
    print("-"*60)
    
    proposal_data = {
        "lead_name": "John Doe",
        "lead_email": "john.doe@example.com",
        "company_name": "Test Company Inc",
        "business_type": "E-commerce",
        "budget": 5000.0,
        "challenges": "Need to increase online sales and improve brand visibility",
        "target_audience": "Young professionals aged 25-40, interested in tech products",
        "existing_presence": {
            "platforms": ["website", "instagram", "facebook"]
        }
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"Sending request with data:")
    print(json.dumps(proposal_data, indent=2))
    
    response = requests.post(
        f"{API_BASE}/project-planner/generate-proposal",
        json=proposal_data,
        headers=headers
    )
    
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 422:
        print("\n❌ VALIDATION ERROR - Check the field requirements!")
        print("The API is expecting different fields than what we're sending.")
    elif response.status_code == 200:
        print("\n✅ SUCCESS! Proposal generated.")
    else:
        print(f"\n⚠️ Unexpected status code: {response.status_code}")
        
else:
    print(f"❌ Login failed: {login_response.json()}")