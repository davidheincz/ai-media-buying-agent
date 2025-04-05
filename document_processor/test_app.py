"""
Test module for the document processor application.
"""

import os
import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app, Base, get_db, Document, DocumentChunk, KnowledgeEntry
from app import extract_text_from_pdf, chunk_text, create_embeddings, extract_knowledge

# Create test database
TEST_DATABASE_URL = "sqlite:///./test.db"
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
def sample_pdf_path():
    # Create a sample PDF for testing
    # In a real test, you would use a pre-created test PDF file
    sample_path = "test_sample.pdf"
    # For this example, we'll just check if the file exists
    if not os.path.exists(sample_path):
        pytest.skip(f"Test PDF file {sample_path} not found")
    return sample_path

# Unit tests for utility functions
def test_chunk_text():
    """Test the text chunking functionality."""
    text = "This is a test sentence. This is another test sentence. " * 20
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    
    # Check that chunks were created
    assert len(chunks) > 1
    
    # Check that each chunk is under the max size
    for chunk in chunks:
        assert len(chunk) <= 100 + 20  # Allow for some flexibility due to sentence boundaries

def test_extract_knowledge():
    """Test knowledge extraction from text."""
    # Test with text containing budget rules
    text = "If CPA exceeds $10, decrease the budget by 20%. When performance improves, increase campaign budget."
    knowledge = extract_knowledge(text, 1)
    
    # Check that knowledge was extracted
    assert len(knowledge) > 0
    assert any(entry["category"] == "budget_rule" for entry in knowledge)
    
    # Test with text containing ad set rules
    text = "Toggle ad set off when CTR drops below 1%."
    knowledge = extract_knowledge(text, 2)
    
    # Check that knowledge was extracted
    assert len(knowledge) > 0
    assert any(entry["category"] == "adset_rule" for entry in knowledge)

# Integration tests for API endpoints
def test_upload_document(setup_database, monkeypatch):
    """Test document upload endpoint."""
    # Mock the background task to avoid actual processing
    def mock_process_document(document_id, file_path, db):
        pass
    
    monkeypatch.setattr("app.process_document", mock_process_document)
    
    # Create test directory
    os.makedirs("uploads", exist_ok=True)
    
    # Create a simple test file
    test_file_path = "uploads/test.pdf"
    with open(test_file_path, "wb") as f:
        f.write(b"Test PDF content")
    
    # Test file upload
    with open(test_file_path, "rb") as f:
        response = client.post(
            "/documents/",
            params={"user_id": "test_user", "title": "Test Document"},
            files={"file": ("test.pdf", f, "application/pdf")}
        )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Document"
    assert data["user_id"] == "test_user"
    assert data["processing_status"] == "pending"
    
    # Clean up
    os.remove(test_file_path)

def test_get_documents(setup_database):
    """Test get documents endpoint."""
    # Create a test document in the database
    db = TestingSessionLocal()
    document = Document(
        user_id="test_user",
        title="Test Document",
        filename="test.pdf",
        file_path="uploads/test.pdf",
        file_size=100,
        content_type="application/pdf",
        processing_status="completed"
    )
    db.add(document)
    db.commit()
    
    # Test get documents
    response = client.get("/documents/", params={"user_id": "test_user"})
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Test Document"
    assert data[0]["user_id"] == "test_user"
    
    # Clean up
    db.close()

def test_get_document_knowledge(setup_database):
    """Test get document knowledge endpoint."""
    # Create a test document and knowledge entries in the database
    db = TestingSessionLocal()
    
    document = Document(
        id="test_doc_id",
        user_id="test_user",
        title="Test Document",
        filename="test.pdf",
        file_path="uploads/test.pdf",
        file_size=100,
        content_type="application/pdf",
        processing_status="completed"
    )
    db.add(document)
    
    knowledge_entry = KnowledgeEntry(
        document_id="test_doc_id",
        category="budget_rule",
        title="Test Rule",
        content="Decrease budget when CPA is high",
        source_page=1,
        confidence_score=0.9
    )
    db.add(knowledge_entry)
    db.commit()
    
    # Test get document knowledge
    response = client.get(f"/documents/test_doc_id/knowledge")
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "budget_rule"
    assert data[0]["title"] == "Test Rule"
    
    # Clean up
    db.close()

def test_search_knowledge(setup_database, monkeypatch):
    """Test knowledge search endpoint."""
    # Mock the embedding model to avoid actual encoding
    def mock_encode(text):
        import numpy as np
        return np.zeros(384)  # Return dummy embedding
    
    monkeypatch.setattr("app.model.encode", mock_encode)
    
    # Create test knowledge entries
    db = TestingSessionLocal()
    
    document = Document(
        id="test_doc_id",
        user_id="test_user",
        title="Test Document",
        filename="test.pdf",
        file_path="uploads/test.pdf",
        file_size=100,
        content_type="application/pdf",
        processing_status="completed"
    )
    db.add(document)
    
    knowledge_entry1 = KnowledgeEntry(
        document_id="test_doc_id",
        category="budget_rule",
        title="Budget Rule",
        content="Decrease budget when CPA is high",
        source_page=1,
        confidence_score=0.9
    )
    db.add(knowledge_entry1)
    
    knowledge_entry2 = KnowledgeEntry(
        document_id="test_doc_id",
        category="campaign_rule",
        title="Campaign Rule",
        content="Create new campaign for high-performing audiences",
        source_page=2,
        confidence_score=0.8
    )
    db.add(knowledge_entry2)
    
    db.commit()
    
    # Test search knowledge
    response = client.get("/knowledge/search", params={"query": "budget CPA"})
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert any("budget" in entry["content"].lower() for entry in data)
    
    # Clean up
    db.close()

if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
