"""
Main module for the knowledge base component of the AI-driven media buying agent.
This module provides functionality for storing and retrieving knowledge extracted from documents.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, Query

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./knowledge_base.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Initialize FastAPI app
app = FastAPI(title="Knowledge Base API", 
              description="API for storing and retrieving knowledge for the media buying agent")

# Database Models
class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    
    id = Column(String, primary_key=True)
    document_id = Column(String, nullable=False)
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source_page = Column(Integer, nullable=True)
    confidence_score = Column(Float, default=1.0)
    embedding = Column(Text)  # Store as JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    tags = relationship("KnowledgeTag", back_populates="knowledge_entry", cascade="all, delete-orphan")

class KnowledgeTag(Base):
    __tablename__ = "knowledge_tags"
    
    id = Column(String, primary_key=True)
    entry_id = Column(String, ForeignKey("knowledge_entries.id"), nullable=False)
    tag = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    knowledge_entry = relationship("KnowledgeEntry", back_populates="tags")

class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"
    
    id = Column(String, primary_key=True)
    source_id = Column(String, ForeignKey("knowledge_entries.id"), nullable=False)
    target_id = Column(String, ForeignKey("knowledge_entries.id"), nullable=False)
    relation_type = Column(String, nullable=False)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class RuleEntry(Base):
    __tablename__ = "rule_entries"
    
    id = Column(String, primary_key=True)
    knowledge_id = Column(String, ForeignKey("knowledge_entries.id"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    conditions = relationship("RuleCondition", back_populates="rule", cascade="all, delete-orphan")
    actions = relationship("RuleAction", back_populates="rule", cascade="all, delete-orphan")

class RuleCondition(Base):
    __tablename__ = "rule_conditions"
    
    id = Column(String, primary_key=True)
    rule_id = Column(String, ForeignKey("rule_entries.id"), nullable=False)
    condition_type = Column(String, nullable=False)
    operator = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    rule = relationship("RuleEntry", back_populates="conditions")

class RuleAction(Base):
    __tablename__ = "rule_actions"
    
    id = Column(String, primary_key=True)
    rule_id = Column(String, ForeignKey("rule_entries.id"), nullable=False)
    action_type = Column(String, nullable=False)
    action_value = Column(String, nullable=False)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    rule = relationship("RuleEntry", back_populates="actions")

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
class KnowledgeEntryBase(BaseModel):
    category: str
    title: str
    content: str
    source_page: Optional[int] = None
    confidence_score: float = 1.0

class KnowledgeEntryCreate(KnowledgeEntryBase):
    document_id: str
    tags: List[str] = []

class KnowledgeEntryResponse(KnowledgeEntryBase):
    id: str
    document_id: str
    created_at: datetime
    updated_at: datetime
    tags: List[str] = []
    
    class Config:
        orm_mode = True

class KnowledgeRelationCreate(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    confidence: float = 1.0

class KnowledgeRelationResponse(KnowledgeRelationCreate):
    id: str
    created_at: datetime
    
    class Config:
        orm_mode = True

class RuleConditionBase(BaseModel):
    condition_type: str
    operator: str
    value: float

class RuleActionBase(BaseModel):
    action_type: str
    action_value: str
    priority: int = 0

class RuleEntryCreate(BaseModel):
    knowledge_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    priority: int = 0
    is_active: bool = True
    conditions: List[RuleConditionBase]
    actions: List[RuleActionBase]

class RuleConditionResponse(RuleConditionBase):
    id: str
    rule_id: str
    created_at: datetime
    
    class Config:
        orm_mode = True

class RuleActionResponse(RuleActionBase):
    id: str
    rule_id: str
    created_at: datetime
    
    class Config:
        orm_mode = True

class RuleEntryResponse(BaseModel):
    id: str
    knowledge_id: Optional[str]
    name: str
    description: Optional[str]
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    conditions: List[RuleConditionResponse]
    actions: List[RuleActionResponse]
    
    class Config:
        orm_mode = True

# API endpoints for knowledge entries
@app.post("/knowledge/", response_model=KnowledgeEntryResponse)
def create_knowledge_entry(entry: KnowledgeEntryCreate, db: Session = Depends(get_db)):
    """
    Create a new knowledge entry.
    
    Args:
        entry: Knowledge entry data
        
    Returns:
        Created knowledge entry
    """
    import uuid
    
    # Create knowledge entry
    db_entry = KnowledgeEntry(
        id=str(uuid.uuid4()),
        document_id=entry.document_id,
        category=entry.category,
        title=entry.title,
        content=entry.content,
        source_page=entry.source_page,
        confidence_score=entry.confidence_score
    )
    db.add(db_entry)
    db.flush()
    
    # Create tags
    for tag_name in entry.tags:
        tag = KnowledgeTag(
            id=str(uuid.uuid4()),
            entry_id=db_entry.id,
            tag=tag_name
        )
        db.add(tag)
    
    db.commit()
    db.refresh(db_entry)
    
    # Convert to response model
    response = KnowledgeEntryResponse(
        id=db_entry.id,
        document_id=db_entry.document_id,
        category=db_entry.category,
        title=db_entry.title,
        content=db_entry.content,
        source_page=db_entry.source_page,
        confidence_score=db_entry.confidence_score,
        created_at=db_entry.created_at,
        updated_at=db_entry.updated_at,
        tags=[tag.tag for tag in db_entry.tags]
    )
    
    return response

@app.get("/knowledge/", response_model=List[KnowledgeEntryResponse])
def get_knowledge_entries(
    document_id: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get knowledge entries with optional filtering.
    
    Args:
        document_id: Filter by document ID
        category: Filter by category
        tag: Filter by tag
        skip: Number of entries to skip
        limit: Maximum number of entries to return
        
    Returns:
        List of knowledge entries
    """
    query = db.query(KnowledgeEntry)
    
    if document_id:
        query = query.filter(KnowledgeEntry.document_id == document_id)
    
    if category:
        query = query.filter(KnowledgeEntry.category == category)
    
    if tag:
        query = query.join(KnowledgeTag).filter(KnowledgeTag.tag == tag)
    
    entries = query.offset(skip).limit(limit).all()
    
    # Convert to response models
    responses = []
    for entry in entries:
        responses.append(KnowledgeEntryResponse(
            id=entry.id,
            document_id=entry.document_id,
            category=entry.category,
            title=entry.title,
            content=entry.content,
            source_page=entry.source_page,
            confidence_score=entry.confidence_score,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            tags=[tag.tag for tag in entry.tags]
        ))
    
    return responses

@app.get("/knowledge/{entry_id}", response_model=KnowledgeEntryResponse)
def get_knowledge_entry(entry_id: str, db: Session = Depends(get_db)):
    """
    Get a knowledge entry by ID.
    
    Args:
        entry_id: ID of the knowledge entry
        
    Returns:
        Knowledge entry
    """
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    # Convert to response model
    response = KnowledgeEntryResponse(
        id=entry.id,
        document_id=entry.document_id,
        category=entry.category,
        title=entry.title,
        content=entry.content,
        source_page=entry.source_page,
        confidence_score=entry.confidence_score,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        tags=[tag.tag for tag in entry.tags]
    )
    
    return response

@app.delete("/knowledge/{entry_id}")
def delete_knowledge_entry(entry_id: str, db: Session = Depends(get_db)):
    """
    Delete a knowledge entry.
    
    Args:
        entry_id: ID of the knowledge entry
        
    Returns:
        Success message
    """
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    db.delete(entry)
    db.commit()
    
    return {"message": "Knowledge entry deleted successfully"}

# API endpoints for knowledge relations
@app.post("/knowledge/relations/", response_model=KnowledgeRelationResponse)
def create_knowledge_relation(relation: KnowledgeRelationCreate, db: Session = Depends(get_db)):
    """
    Create a relation between two knowledge entries.
    
    Args:
        relation: Relation data
        
    Returns:
        Created relation
    """
    import uuid
    
    # Check if source and target entries exist
    source = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == relation.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source knowledge entry not found")
    
    target = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == relation.target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target knowledge entry not found")
    
    # Create relation
    db_relation = KnowledgeRelation(
        id=str(uuid.uuid4()),
        source_id=relation.source_id,
        target_id=relation.target_id,
        relation_type=relation.relation_type,
        confidence=relation.confidence
    )
    db.add(db_relation)
    db.commit()
    db.refresh(db_relation)
    
    return db_relation

@app.get("/knowledge/relations/", response_model=List[KnowledgeRelationResponse])
def get_knowledge_relations(
    source_id: Optional[str] = None,
    target_id: Optional[str] = None,
    relation_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get knowledge relations with optional filtering.
    
    Args:
        source_id: Filter by source entry ID
        target_id: Filter by target entry ID
        relation_type: Filter by relation type
        
    Returns:
        List of relations
    """
    query = db.query(KnowledgeRelation)
    
    if source_id:
        query = query.filter(KnowledgeRelation.source_id == source_id)
    
    if target_id:
        query = query.filter(KnowledgeRelation.target_id == target_id)
    
    if relation_type:
        query = query.filter(KnowledgeRelation.relation_type == relation_type)
    
    relations = query.all()
    return relations

# API endpoints for rules
@app.post("/rules/", response_model=RuleEntryResponse)
def create_rule(rule: RuleEntryCreate, db: Session = Depends(get_db)):
    """
    Create a new rule with conditions and actions.
    
    Args:
        rule: Rule data
        
    Returns:
        Created rule
    """
    import uuid
    
    # Check if knowledge entry exists if provided
    if rule.knowledge_id:
        knowledge = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == rule.knowledge_id).first()
        if not knowledge:
            raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    # Create rule
    db_rule = RuleEntry(
        id=str(uuid.uuid4()),
        knowledge_id=rule.knowledge_id,
        name=rule.name,
        description=rule.description,
        priority=rule.priority,
        is_active=rule.is_active
    )
    db.add(db_rule)
    db.flush()
    
    # Create conditions
    for condition in rule.conditions:
        db_condition = RuleCondition(
            id=str(uuid.uuid4()),
            rule_id=db_rule.id,
            condition_type=condition.condition_type,
            operator=condition.operator,
            value=condition.value
        )
        db.add(db_condition)
    
    # Create actions
    for action in rule.actions:
        db_action = RuleAction(
            id=str(uuid.uuid4()),
            rule_id=db_rule.id,
            action_type=action.action_type,
            action_value=action.action_value,
            priority=action.priority
        )
        db.add(db_action)
    
    db.commit()
    db.refresh(db_rule)
    
    return db_rule

@app.get("/rules/", response_model=List[RuleEntryResponse])
def get_rules(
    is_active: Optional[bool] = None,
    condition_type: Optional[str] = None,
    action_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get rules with optional filtering.
    
    Args:
        is_active: Filter by active status
        condition_type: Filter by condition type
        action_type: Filter by action type
        
    Returns:
        List of rules
    """
    query = db.query(RuleEntry)
    
    if is_active is not None:
        query = query.filter(RuleEntry.is_active == is_active)
    
    if condition_type:
        query = query.join(RuleCondition).filter(RuleCondition.condition_type == condition_type)
    
    if action_type:
        query = query.join(RuleAction).filter(RuleAction.action_type == action_type)
    
    rules = query.order_by(RuleEntry.priority.desc()).all()
    return rules

@app.get("/rules/{rule_id}", response_model=RuleEntryResponse)
def get_rule(rule_id: str, db: Session = Depends(get_db)):
    """
    Get a rule by ID.
    
    Args:
        rule_id: ID of the rule
        
    Returns:
        Rule
    """
    rule = db.query(RuleEntry).filter(RuleEntry.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return rule

@app.put("/rules/{rule_id}/toggle", response_model=RuleEntryResponse)
def toggle_rule(rule_id: str, is_active: bool, db: Session = Depends(get_db)):
    """
    Toggle a rule's active status.
    
    Args:
        rule_id: ID of the rule
        is_active: New active status
        
    Returns:
        Updated rule
    """
    rule = db.query(RuleEntry).filter(RuleEntry.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.is_active = is_active
    db.commit()
    db.refresh(rule)
    
    return rule

@app.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    """
    Delete a rule.
    
    Args:
        rule_id: ID of the rule
        
    Returns:
        Success message
    """
    rule = db.query(RuleEntry).filter(RuleEntry.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(rule)
    db.commit()
    
    return {"message": "Rule deleted successfully"}

# API endpoints for rule evaluation
@app.post("/rules/evaluate")
def evaluate_rules(
    metrics: Dict[str, float],
    condition_types: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Evaluate rules against provided metrics.
    
    Args:
        metrics: Dictionary of metric values (e.g., {"CPA": 10.5, "CTR": 0.02})
        condition_types: Optional list of condition types to filter rules
        
    Returns:
        List of triggered rules and their actions
    """
    # Get active rules
    query = db.query(RuleEntry).filter(RuleEntry.is_active == True)
    
    # Filter by condition types if provided
    if condition_types:
        query = query.join(RuleCondition).filter(RuleCondition.condition_type.in_(condition_types))
    
    rules = query.all()
    
    # Evaluate rules
    triggered_rules = []
    
    for rule in rules:
        # Check if all conditions are met
        conditions_met = True
        
        for condition in rule.conditions:
            # Skip if metric not provided
            if condition.condition_type not in metrics:
                conditions_met = False
                break
            
            metric_value = metrics[condition.condition_type]
            
            # Evaluate condition
            if condition.operator == ">" and not (metric_value > condition.value):
                conditions_met = False
                break
            elif condition.operator == ">=" and not (metric_value >= condition.value):
                conditions_met = False
                break
            elif condition.operator == "<" and not (metric_value < condition.value):
                conditions_met = False
                break
            elif condition.operator == "<=" and not (metric_value <= condition.value):
                conditions_met = False
                break
            elif condition.operator == "=" and not (metric_value == condition.value):
                conditions_met = False
                break
        
        # If all conditions are met, add rule to triggered rules
        if conditions_met:
            triggered_rules.append({
                "rule_id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "priority": rule.priority,
                "actions": [
                    {
                        "action_type": action.action_type,
                        "action_value": action.action_value,
                        "priority": action.priority
                    }
                    for action in sorted(rule.actions, key=lambda a: a.priority, reverse=True)
                ]
            })
    
    # Sort triggered rules by priority
    triggered_rules.sort(key=lambda r: r["priority"], reverse=True)
    
    return {
        "triggered_rules": triggered_rules,
        "metrics": metrics
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
