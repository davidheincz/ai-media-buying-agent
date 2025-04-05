"""
Document Processor Module for AI-Driven Media Buying Agent

This module handles the processing of PDF documents, extracting text and knowledge,
and storing the information in the knowledge base.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import uuid

import PyPDF2
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sentence_transformers import SentenceTransformer
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from datetime import datetime
import json

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Download NLTK resources
nltk.download('punkt')
nltk.download('stopwords')

# Initialize FastAPI app
app = FastAPI(title="Document Processor API", 
              description="API for processing PDF documents and extracting knowledge")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./document_processor.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Initialize sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Database Models
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Text)  # Store as JSON string for now
    metadata = Column(Text)  # Store as JSON string for now
    created_at = Column(DateTime, default=datetime.utcnow)

class DocumentTag(Base):
    __tablename__ = "document_tags"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    tag = Column(String, nullable=False)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_id = Column(String, ForeignKey("document_chunks.id"), nullable=True)
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source_page = Column(Integer, nullable=True)
    confidence_score = Column(Float, default=1.0)
    embedding = Column(Text)  # Store as JSON string for now
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create database tables
Base.metadata.create_all(bind=engine)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models for API
class DocumentCreate(BaseModel):
    user_id: str
    title: str

class DocumentResponse(BaseModel):
    id: str
    user_id: str
    title: str
    filename: str
    file_size: int
    content_type: str
    upload_date: datetime
    processing_status: str
    
    class Config:
        orm_mode = True

class KnowledgeEntryResponse(BaseModel):
    id: str
    document_id: str
    category: str
    title: str
    content: str
    source_page: Optional[int]
    confidence_score: float
    
    class Config:
        orm_mode = True

# Document processing functions
def extract_text_from_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract text from a PDF file, returning a list of pages with text content.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        List of dictionaries with page number and text content
    """
    pages = []
    
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append({
                        "page_number": i + 1,
                        "content": text
                    })
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise
        
    return pages

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Split text into chunks of specified size with overlap.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum size of each chunk
        overlap: Number of characters to overlap between chunks
        
    Returns:
        List of text chunks
    """
    chunks = []
    sentences = sent_tokenize(text)
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence_size = len(sentence)
        
        if current_size + sentence_size <= chunk_size:
            current_chunk.append(sentence)
            current_size += sentence_size
        else:
            # Add current chunk to list
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            
            # Start new chunk with overlap
            overlap_size = 0
            overlap_chunk = []
            
            # Add sentences from the end of the previous chunk for overlap
            for s in reversed(current_chunk):
                if overlap_size + len(s) <= overlap:
                    overlap_chunk.insert(0, s)
                    overlap_size += len(s)
                else:
                    break
            
            current_chunk = overlap_chunk + [sentence]
            current_size = sum(len(s) for s in current_chunk)
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def create_embeddings(chunks: List[str]) -> List[List[float]]:
    """
    Create embeddings for text chunks using sentence transformer.
    
    Args:
        chunks: List of text chunks
        
    Returns:
        List of embeddings (as lists of floats)
    """
    embeddings = []
    
    try:
        embeddings = model.encode(chunks)
        # Convert numpy arrays to lists for JSON serialization
        embeddings = [embedding.tolist() for embedding in embeddings]
    except Exception as e:
        logger.error(f"Error creating embeddings: {str(e)}")
        raise
        
    return embeddings

def extract_knowledge(text: str, page_number: int) -> List[Dict[str, Any]]:
    """
    Extract structured knowledge from text.
    This is a simplified version - in a real implementation, 
    this would use more sophisticated NLP techniques.
    
    Args:
        text: Text to extract knowledge from
        page_number: Page number in the source document
        
    Returns:
        List of knowledge entries
    """
    knowledge_entries = []
    
    # Simple rule-based extraction for demonstration
    # In a real implementation, this would use NER, relation extraction, etc.
    
    # Look for sections that might contain media buying rules
    if "budget" in text.lower() or "campaign" in text.lower() or "ad set" in text.lower():
        # Extract sentences that might contain rules
        sentences = sent_tokenize(text)
        for sentence in sentences:
            lower_sentence = sentence.lower()
            
            # Check for budget-related rules
            if "budget" in lower_sentence and ("increase" in lower_sentence or "decrease" in lower_sentence):
                knowledge_entries.append({
                    "category": "budget_rule",
                    "title": "Budget Adjustment Rule",
                    "content": sentence,
                    "source_page": page_number,
                    "confidence_score": 0.8
                })
            
            # Check for campaign-related rules
            elif "campaign" in lower_sentence and ("create" in lower_sentence or "launch" in lower_sentence):
                knowledge_entries.append({
                    "category": "campaign_rule",
                    "title": "Campaign Creation Rule",
                    "content": sentence,
                    "source_page": page_number,
                    "confidence_score": 0.8
                })
            
            # Check for ad set-related rules
            elif "ad set" in lower_sentence and ("on" in lower_sentence or "off" in lower_sentence or "toggle" in lower_sentence):
                knowledge_entries.append({
                    "category": "adset_rule",
                    "title": "Ad Set Toggle Rule",
                    "content": sentence,
                    "source_page": page_number,
                    "confidence_score": 0.8
                })
    
    return knowledge_entries

async def process_document(document_id: str, file_path: str, db: Session):
    """
    Process a document, extract text, create chunks, and store knowledge.
    
    Args:
        document_id: ID of the document in the database
        file_path: Path to the document file
        db: Database session
    """
    try:
        # Update document status to processing
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document not found: {document_id}")
            return
        
        document.processing_status = "processing"
        db.commit()
        
        # Extract text from PDF
        pages = extract_text_from_pdf(file_path)
        
        # Process each page
        for page in pages:
            page_number = page["page_number"]
            text = page["content"]
            
            # Create chunks
            chunks = chunk_text(text)
            
            # Create embeddings
            embeddings = create_embeddings(chunks)
            
            # Store chunks in database
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_obj = DocumentChunk(
                    document_id=document_id,
                    content=chunk,
                    chunk_index=i,
                    embedding=json.dumps(embedding),
                    metadata=json.dumps({"page_number": page_number})
                )
                db.add(chunk_obj)
            
            # Extract knowledge
            knowledge_entries = extract_knowledge(text, page_number)
            
            # Store knowledge entries in database
            for entry in knowledge_entries:
                knowledge_obj = KnowledgeEntry(
                    document_id=document_id,
                    category=entry["category"],
                    title=entry["title"],
                    content=entry["content"],
                    source_page=entry["source_page"],
                    confidence_score=entry["confidence_score"]
                )
                db.add(knowledge_obj)
        
        # Add document tags based on content
        all_text = " ".join([page["content"] for page in pages])
        
        if "budget" in all_text.lower():
            db.add(DocumentTag(document_id=document_id, tag="budget", confidence=0.9))
        
        if "campaign" in all_text.lower():
            db.add(DocumentTag(document_id=document_id, tag="campaign", confidence=0.9))
        
        if "ad set" in all_text.lower():
            db.add(DocumentTag(document_id=document_id, tag="ad_set", confidence=0.9))
        
        # Update document status to completed
        document.processing_status = "completed"
        db.commit()
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        
        # Update document status to failed
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.processing_status = "failed"
            db.commit()

# API endpoints
@app.post("/documents/", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    user_id: str,
    title: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a document for processing.
    
    Args:
        user_id: ID of the user uploading the document
        title: Title of the document
        file: PDF file to upload
        
    Returns:
        Document object with metadata
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Create document record
    document = Document(
        user_id=user_id,
        title=title,
        filename=file.filename,
        file_path=f"uploads/{file.filename}",
        file_size=0,  # Will be updated after saving
        content_type=file.content_type,
        processing_status="pending"
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    
    # Save file
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
        document.file_size = len(content)
    
    db.commit()
    
    # Process document in background
    background_tasks.add_task(process_document, document.id, file_path, db)
    
    return document

@app.get("/documents/", response_model=List[DocumentResponse])
def get_documents(user_id: str, db: Session = Depends(get_db)):
    """
    Get all documents for a user.
    
    Args:
        user_id: ID of the user
        
    Returns:
        List of document objects
    """
    documents = db.query(Document).filter(Document.user_id == user_id).all()
    return documents

@app.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """
    Get a document by ID.
    
    Args:
        document_id: ID of the document
        
    Returns:
        Document object
    """
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@app.get("/documents/{document_id}/knowledge", response_model=List[KnowledgeEntryResponse])
def get_document_knowledge(document_id: str, db: Session = Depends(get_db)):
    """
    Get knowledge entries extracted from a document.
    
    Args:
        document_id: ID of the document
        
    Returns:
        List of knowledge entry objects
    """
    entries = db.query(KnowledgeEntry).filter(KnowledgeEntry.document_id == document_id).all()
    return entries

@app.get("/knowledge/search")
def search_knowledge(query: str, db: Session = Depends(get_db)):
    """
    Search knowledge entries using semantic search.
    
    Args:
        query: Search query
        
    Returns:
        List of matching knowledge entries
    """
    # Create embedding for query
    query_embedding = model.encode(query).tolist()
    
    # In a real implementation, this would use vector similarity search
    # For now, we'll use a simple keyword search
    entries = db.query(KnowledgeEntry).all()
    
    # Filter entries that contain the query keywords
    keywords = query.lower().split()
    results = []
    
    for entry in entries:
        content_lower = entry.content.lower()
        if any(keyword in content_lower for keyword in keywords):
            results.append({
                "id": entry.id,
                "document_id": entry.document_id,
                "category": entry.category,
                "title": entry.title,
                "content": entry.content,
                "source_page": entry.source_page,
                "confidence_score": entry.confidence_score,
                "relevance": 0.8  # Placeholder for actual relevance score
            })
    
    # Sort by relevance
    results.sort(key=lambda x: x["relevance"], reverse=True)
    
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
