"""
Quick test script for conversation endpoints.

Run with: python test_conversation_endpoints.py
Assumes uvicorn server is running on http://localhost:8000
"""

import requests
import json
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"

# Test credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpass123"

def test_flow():
    """Test the conversation endpoints."""
    
    print("=== RailYatri Conversation History API Test ===\n")
    
    # Step 1: Register
    print("1. Registering user...")
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    print(f"   Status: {resp.status_code}")
    if resp.status_code not in [201, 409]:  # 409 if already exists
        print(f"   Error: {resp.json()}")
        return
    print()
    
    # Step 2: Login
    print("2. Logging in...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    if resp.status_code != 200:
        print(f"   Error: {resp.json()}")
        return
    
    token = resp.json()["access_token"]
    print(f"   Token: {token[:30]}...")
    print()
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 3: Send a query to create a conversation
    print("3. Sending a query (creates conversation)...")
    resp = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"query": "Hello!"},
        headers=headers,
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"   Error: {resp.json()}")
        return
    print(f"   Response: {resp.json()['message'][:50]}...")
    print()
    
    # Step 4: List conversations
    print("4. Listing conversations...")
    resp = requests.get(f"{BASE_URL}/api/v1/conversations", headers=headers)
    print(f"   Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"   Error: {resp.json()}")
        return
    
    convs = resp.json()["conversations"]
    print(f"   Found {len(convs)} conversation(s)")
    if not convs:
        print("   ERROR: No conversations returned!")
        return
    
    conv_id = convs[0]["id"]
    print(f"   Latest: {convs[0]['created_at']}")
    print()
    
    # Step 5: Fetch messages for the conversation
    print(f"5. Fetching messages for conversation {conv_id[:8]}...")
    resp = requests.get(
        f"{BASE_URL}/api/v1/conversations/{conv_id}/messages",
        headers=headers,
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"   Error: {resp.json()}")
        return
    
    messages = resp.json()["messages"]
    print(f"   Found {len(messages)} message(s)")
    for i, msg in enumerate(messages, 1):
        print(f"   [{i}] {msg['role'].upper()}: {msg['content'][:50]}...")
    print()
    
    # Step 6: Send another query to add more messages
    print("6. Sending another query...")
    resp = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"query": "Trains from Delhi to Mumbai tomorrow"},
        headers=headers,
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"   Error: {resp.json()}")
        return
    print(f"   Response: {resp.json()['message'][:50]}...")
    print()
    
    # Step 7: Fetch messages again (should have more now)
    print(f"7. Fetching messages again...")
    resp = requests.get(
        f"{BASE_URL}/api/v1/conversations/{conv_id}/messages",
        headers=headers,
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"   Error: {resp.json()}")
        return
    
    messages = resp.json()["messages"]
    print(f"   Found {len(messages)} message(s)")
    for i, msg in enumerate(messages, 1):
        print(f"   [{i}] {msg['role'].upper()}: {msg['content'][:50]}...")
    print()
    
    print("=== All tests passed! ===")


if __name__ == "__main__":
    try:
        test_flow()
    except requests.ConnectionError:
        print("ERROR: Cannot connect to http://localhost:8000")
        print("Make sure the uvicorn server is running:")
        print("  uvicorn app.main:app --reload")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
