"""
Test module for the AI Integration application.
"""

import os
import pytest
import json
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app, Base, get_db, AIDecision, AIQuery
from app import process_document, create_rule_from_knowledge, evaluate_and_execute_rules, execute_decision

# Create test database
TEST_DATABASE_URL = "sqlite:///./test_ai_integration.db"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test client
client = TestClient(app)

# Override the get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Setup and teardown
@pytest.fixture(scope="function")
def setup_database():
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def mock_requests():
    with patch('app.requests') as mock_req:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "test_document_id", "processing_status": "completed"}
        mock_req.post.return_value = mock_response
        mock_req.get.return_value = mock_response
        mock_req.put.return_value = mock_response
        yield mock_req

@pytest.fixture
def mock_asyncio_sleep():
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        yield mock_sleep

@pytest.fixture
def sample_decision(setup_database):
    # Create a sample AI decision for testing
    db = TestingSessionLocal()
    decision = AIDecision(
        id="test_decision_id",
        user_id="test_user_id",
        campaign_id="test_campaign_id",
        adset_id="test_adset_id",
        decision_type="adjust_budget",
        decision_details=json.dumps({
            "action_value": "+20%",
            "metrics": {"CPA": 5.0, "CTR": 2.5}
        }),
        reasoning="Test reasoning",
        status="pending_approval"
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    db.close()
    return decision

@pytest.fixture
def sample_query(setup_database):
    # Create a sample AI query for testing
    db = TestingSessionLocal()
    query = AIQuery(
        id="test_query_id",
        user_id="test_user_id",
        query_text="How can I improve my ad performance?",
        response_text=None
    )
    db.add(query)
    db.commit()
    db.refresh(query)
    db.close()
    return query

# Unit tests for helper functions
@pytest.mark.asyncio
async def test_process_document(setup_database, mock_requests, mock_asyncio_sleep):
    """Test document processing."""
    # Mock knowledge entries
    mock_requests.get.return_value.json.return_value = [
        {
            "id": "knowledge_1",
            "category": "budget_rule",
            "title": "Budget Rule 1",
            "content": "Decrease budget when CPA is high"
        }
    ]
    
    # Call function
    db = TestingSessionLocal()
    await process_document("test_user", "test_document_id", db)
    db.close()
    
    # Verify requests were made
    mock_requests.get.assert_called()
    mock_asyncio_sleep.assert_not_called()  # Document was already completed

@pytest.mark.asyncio
async def test_create_rule_from_knowledge(setup_database, mock_requests):
    """Test rule creation from knowledge entry."""
    # Test data
    knowledge_entry = {
        "id": "knowledge_1",
        "category": "budget_rule",
        "title": "Budget Rule 1",
        "content": "Decrease budget when CPA is high"
    }
    
    # Call function
    db = TestingSessionLocal()
    await create_rule_from_knowledge(knowledge_entry, db)
    db.close()
    
    # Verify request was made
    mock_requests.post.assert_called_once()
    
    # Verify request data
    call_args = mock_requests.post.call_args
    assert "rules" in call_args[0][0]
    
    # Check rule data
    rule_data = call_args[1]["json"]
    assert rule_data["knowledge_id"] == "knowledge_1"
    assert rule_data["name"] == "Budget Rule 1"
    assert len(rule_data["conditions"]) > 0
    assert len(rule_data["actions"]) > 0

@pytest.mark.asyncio
async def test_execute_decision(setup_database, mock_requests, sample_decision):
    """Test decision execution."""
    # Call function
    db = TestingSessionLocal()
    await execute_decision(sample_decision.id, db)
    
    # Verify decision was updated
    decision = db.query(AIDecision).filter(AIDecision.id == sample_decision.id).first()
    assert decision.status == "executed"
    assert decision.executed_at is not None
    db.close()
    
    # Verify request was made
    mock_requests.get.assert_called()
    mock_requests.put.assert_called()

# Integration tests for API endpoints
def test_upload_document(setup_database, mock_requests):
    """Test document upload endpoint."""
    # Create test file
    with open("test_document.pdf", "wb") as f:
        f.write(b"Test PDF content")
    
    # Test upload
    with open("test_document.pdf", "rb") as f:
        response = client.post(
            "/documents/upload",
            params={"user_id": "test_user", "title": "Test Document"},
            files={"file": ("test_document.pdf", f, "application/pdf")}
        )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == "test_document_id"
    assert data["status"] == "processing"
    
    # Clean up
    os.remove("test_document.pdf")

def test_create_query(setup_database, mock_requests):
    """Test query creation endpoint."""
    # Mock knowledge search response
    mock_requests.get.return_value.json.return_value = [
        {
            "id": "knowledge_1",
            "title": "Budget Rule 1",
            "content": "Decrease budget when CPA is high"
        }
    ]
    
    # Test query creation
    response = client.post(
        "/query",
        json={
            "user_id": "test_user",
            "query_text": "How can I improve my ad performance?"
        }
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test_user"
    assert data["query_text"] == "How can I improve my ad performance?"
    assert data["response_text"] is not None

def test_get_decisions(setup_database, sample_decision):
    """Test getting AI decisions."""
    # Test get decisions
    response = client.get("/decisions/", params={"user_id": sample_decision.user_id})
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == sample_decision.id
    assert data[0]["decision_type"] == sample_decision.decision_type
    assert isinstance(data[0]["decision_details"], dict)  # Should be converted from JSON string

def test_approve_decision(setup_database, mock_requests, sample_decision):
    """Test approving an AI decision."""
    # Test approve decision
    response = client.post(f"/decisions/{sample_decision.id}/approve")
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Decision approved and executed"
    assert data["decision_id"] == sample_decision.id
    
    # Verify decision was updated
    db = TestingSessionLocal()
    decision = db.query(AIDecision).filter(AIDecision.id == sample_decision.id).first()
    assert decision.status == "executed"
    db.close()

def test_reject_decision(setup_database, sample_decision):
    """Test rejecting an AI decision."""
    # Test reject decision
    response = client.post(f"/decisions/{sample_decision.id}/reject")
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Decision rejected"
    assert data["decision_id"] == sample_decision.id
    
    # Verify decision was updated
    db = TestingSessionLocal()
    decision = db.query(AIDecision).filter(AIDecision.id == sample_decision.id).first()
    assert decision.status == "rejected"
    db.close()

def test_run_automation(setup_database, mock_requests):
    """Test running automation."""
    # Test run automation
    response = client.post(
        "/automation/run",
        json={
            "user_id": "test_user",
            "account_id": "test_account",
            "automation_level": "hybrid",
            "metrics_threshold": {"CPA": 10.0, "CPL": 5.0}
        }
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Automation started"
    assert data["user_id"] == "test_user"
    assert data["account_id"] == "test_account"
    assert data["automation_level"] == "hybrid"

if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
