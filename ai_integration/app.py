"""
AI Integration Module for AI-Driven Media Buying Agent

This module handles the integration with Poe.com API, providing functionality
for document processing, knowledge retrieval, and decision-making based on
performance metrics from Facebook Ads.
"""

import os
import logging
import json
import uuid
import asyncio
from typing import List, Dict, Any, Optional, AsyncIterable
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import requests
import httpx
import fastapi_poe as fp
from fastapi_poe import PoeBot, PartialResponse, QueryRequest, SettingsRequest, SettingsResponse

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
POE_API_KEY = os.getenv("POE_API_KEY")
POE_BOT_NAME = os.getenv("POE_BOT_NAME", "MediaBuyingAgent")
DOCUMENT_PROCESSOR_URL = os.getenv("DOCUMENT_PROCESSOR_URL", "http://localhost:8000")
KNOWLEDGE_BASE_URL = os.getenv("KNOWLEDGE_BASE_URL", "http://localhost:8001")
FACEBOOK_ADS_MANAGER_URL = os.getenv("FACEBOOK_ADS_MANAGER_URL", "http://localhost:8002")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ai_integration.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Initialize FastAPI app
app = FastAPI(title="AI Integration API", 
              description="API for integrating Poe.com with document processing and Facebook Ads")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Models
class AIDecision(Base):
    __tablename__ = "ai_decisions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    campaign_id = Column(String, nullable=True)
    adset_id = Column(String, nullable=True)
    decision_type = Column(String, nullable=False)  # budget_adjustment, campaign_creation, adset_toggle
    decision_details = Column(Text, nullable=False)  # JSON string
    reasoning = Column(Text, nullable=True)
    status = Column(String, nullable=False)  # pending, approved, rejected, executed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)

class AIQuery(Base):
    __tablename__ = "ai_queries"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    query_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
class AIDecisionCreate(BaseModel):
    user_id: str
    campaign_id: Optional[str] = None
    adset_id: Optional[str] = None
    decision_type: str
    decision_details: Dict[str, Any]
    reasoning: Optional[str] = None

class AIDecisionResponse(BaseModel):
    id: str
    user_id: str
    campaign_id: Optional[str]
    adset_id: Optional[str]
    decision_type: str
    decision_details: Dict[str, Any]
    reasoning: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    executed_at: Optional[datetime]
    
    class Config:
        orm_mode = True

class AIQueryCreate(BaseModel):
    user_id: str
    query_text: str

class AIQueryResponse(BaseModel):
    id: str
    user_id: str
    query_text: str
    response_text: Optional[str]
    created_at: datetime
    
    class Config:
        orm_mode = True

class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    message: str

class AutomationRequest(BaseModel):
    user_id: str
    account_id: str
    automation_level: str = "hybrid"  # autonomous, hybrid, approval_required
    metrics_threshold: Dict[str, float] = {}  # e.g., {"CPA": 10.0, "CPL": 5.0}

# Poe.com Bot Implementation
class MediaBuyingBot(PoeBot):
    """
    Poe.com bot for media buying agent.
    """
    
    async def get_settings(self, setting: SettingsRequest) -> SettingsResponse:
        """
        Configure bot settings.
        """
        return SettingsResponse(
            allow_attachments=True,
            server_bot_dependencies={"GPT-3.5-Turbo": 1}
        )
    
    async def get_response(self, request: QueryRequest) -> AsyncIterable[PartialResponse]:
        """
        Process user queries and generate responses.
        """
        # Check if there's an attachment (PDF document)
        for message in reversed(request.query):
            for attachment in message.attachments:
                if attachment.content_type == "application/pdf":
                    # Process PDF document
                    document_id = await self._process_document(attachment.url, attachment.name)
                    yield PartialResponse(text=f"I've processed your document '{attachment.name}' and extracted media buying knowledge from it. This knowledge will be used to inform decisions about your Facebook ad campaigns.")
                    return
        
        # If no attachment, process the query
        query = request.query[-1].content
        
        # Check if it's a request for campaign recommendations
        if "campaign" in query.lower() and ("recommend" in query.lower() or "suggestion" in query.lower()):
            recommendations = await self._get_campaign_recommendations()
            yield PartialResponse(text=f"Based on your media buying knowledge base, here are my recommendations for your campaigns:\n\n{recommendations}")
            return
        
        # Check if it's a request for ad set optimization
        if "ad set" in query.lower() and ("optimize" in query.lower() or "adjustment" in query.lower()):
            optimizations = await self._get_adset_optimizations()
            yield PartialResponse(text=f"Based on performance metrics and your media buying knowledge base, here are my recommended ad set optimizations:\n\n{optimizations}")
            return
        
        # For general queries, use GPT-3.5-Turbo with context from knowledge base
        knowledge_context = await self._get_relevant_knowledge(query)
        
        # Prepare prompt with context
        prompt = f"As an AI media buying agent, use the following knowledge to answer the query. If the knowledge doesn't contain relevant information, use your general knowledge about media buying.\n\nKnowledge: {knowledge_context}\n\nQuery: {query}"
        
        # Forward to GPT-3.5-Turbo
        async for msg in fp.stream_request(
            request, "GPT-3.5-Turbo", request.access_key, override_content=prompt
        ):
            yield msg
    
    async def _process_document(self, url: str, filename: str) -> str:
        """
        Process a PDF document by sending it to the document processor.
        
        Args:
            url: URL of the PDF document
            filename: Name of the document
            
        Returns:
            Document ID
        """
        try:
            # Download the document
            response = requests.get(url)
            if response.status_code != 200:
                raise Exception(f"Failed to download document: {response.status_code}")
            
            # Save document temporarily
            temp_path = f"/tmp/{filename}"
            with open(temp_path, "wb") as f:
                f.write(response.content)
            
            # Upload to document processor
            with open(temp_path, "rb") as f:
                files = {"file": (filename, f, "application/pdf")}
                data = {"user_id": "poe_user", "title": filename}
                upload_response = requests.post(
                    f"{DOCUMENT_PROCESSOR_URL}/documents/",
                    files=files,
                    params=data
                )
            
            if upload_response.status_code != 200:
                raise Exception(f"Failed to upload document to processor: {upload_response.status_code}")
            
            document_data = upload_response.json()
            return document_data["id"]
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            raise
    
    async def _get_relevant_knowledge(self, query: str) -> str:
        """
        Get relevant knowledge from the knowledge base for a query.
        
        Args:
            query: User query
            
        Returns:
            Relevant knowledge as text
        """
        try:
            response = requests.get(
                f"{KNOWLEDGE_BASE_URL}/knowledge/search",
                params={"query": query}
            )
            
            if response.status_code != 200:
                return "No relevant knowledge found."
            
            results = response.json()
            
            if not results:
                return "No relevant knowledge found."
            
            # Format knowledge entries
            knowledge_text = ""
            for i, entry in enumerate(results[:5]):  # Limit to top 5 results
                knowledge_text += f"{i+1}. {entry['title']}: {entry['content']}\n\n"
            
            return knowledge_text
            
        except Exception as e:
            logger.error(f"Error getting relevant knowledge: {str(e)}")
            return "Error retrieving knowledge."
    
    async def _get_campaign_recommendations(self) -> str:
        """
        Get campaign recommendations based on knowledge base and performance metrics.
        
        Returns:
            Campaign recommendations as text
        """
        try:
            # Get rules for campaign creation
            rules_response = requests.get(
                f"{KNOWLEDGE_BASE_URL}/rules/",
                params={"is_active": True, "condition_type": "campaign_creation"}
            )
            
            if rules_response.status_code != 200:
                return "No campaign recommendations available."
            
            rules = rules_response.json()
            
            if not rules:
                return "No campaign recommendations available."
            
            # Format recommendations
            recommendations = "Campaign Recommendations:\n\n"
            for rule in rules:
                recommendations += f"- {rule['name']}: {rule['description']}\n"
                recommendations += "  Actions:\n"
                for action in rule['actions']:
                    recommendations += f"  * {action['action_type']}: {action['action_value']}\n"
                recommendations += "\n"
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting campaign recommendations: {str(e)}")
            return "Error retrieving campaign recommendations."
    
    async def _get_adset_optimizations(self) -> str:
        """
        Get ad set optimization recommendations based on knowledge base and performance metrics.
        
        Returns:
            Ad set optimization recommendations as text
        """
        try:
            # Get rules for ad set optimization
            rules_response = requests.get(
                f"{KNOWLEDGE_BASE_URL}/rules/",
                params={"is_active": True, "condition_type": "adset_optimization"}
            )
            
            if rules_response.status_code != 200:
                return "No ad set optimization recommendations available."
            
            rules = rules_response.json()
            
            if not rules:
                return "No ad set optimization recommendations available."
            
            # Format recommendations
            optimizations = "Ad Set Optimization Recommendations:\n\n"
            for rule in rules:
                optimizations += f"- {rule['name']}: {rule['description']}\n"
                optimizations += "  Conditions:\n"
                for condition in rule['conditions']:
                    optimizations += f"  * When {condition['condition_type']} {condition['operator']} {condition['value']}\n"
                optimizations += "  Actions:\n"
                for action in rule['actions']:
                    optimizations += f"  * {action['action_type']}: {action['action_value']}\n"
                optimizations += "\n"
            
            return optimizations
            
        except Exception as e:
            logger.error(f"Error getting ad set optimizations: {str(e)}")
            return "Error retrieving ad set optimization recommendations."

# Helper functions
async def process_document(user_id: str, document_id: str, db: Session):
    """
    Process a document and extract knowledge.
    
    Args:
        user_id: ID of the user
        document_id: ID of the document
        db: Database session
    """
    try:
        # Wait for document processing to complete
        status = "processing"
        max_retries = 30
        retry_count = 0
        
        while status == "processing" and retry_count < max_retries:
            # Check document status
            response = requests.get(f"{DOCUMENT_PROCESSOR_URL}/documents/{document_id}")
            
            if response.status_code != 200:
                logger.error(f"Error checking document status: {response.status_code}")
                break
            
            document_data = response.json()
            status = document_data["processing_status"]
            
            if status == "completed":
                break
            
            # Wait before retrying
            await asyncio.sleep(2)
            retry_count += 1
        
        if status != "completed":
            logger.error(f"Document processing did not complete: {status}")
            return
        
        # Get knowledge entries from document
        knowledge_response = requests.get(
            f"{DOCUMENT_PROCESSOR_URL}/documents/{document_id}/knowledge"
        )
        
        if knowledge_response.status_code != 200:
            logger.error(f"Error getting knowledge entries: {knowledge_response.status_code}")
            return
        
        knowledge_entries = knowledge_response.json()
        
        # Process each knowledge entry
        for entry in knowledge_entries:
            # Create rule if it's a rule-type entry
            if entry["category"] in ["budget_rule", "campaign_rule", "adset_rule"]:
                await create_rule_from_knowledge(entry, db)
        
        logger.info(f"Document processing completed: {len(knowledge_entries)} entries processed")
        
    except Exception as e:
        logger.error(f"Error in document processing: {str(e)}")

async def create_rule_from_knowledge(knowledge_entry: Dict[str, Any], db: Session):
    """
    Create a rule in the knowledge base from a knowledge entry.
    
    Args:
        knowledge_entry: Knowledge entry data
        db: Database session
    """
    try:
        # Determine rule type and parameters based on category
        rule_type = knowledge_entry["category"]
        content = knowledge_entry["content"]
        
        # Simple rule extraction logic (would be more sophisticated in production)
        conditions = []
        actions = []
        
        if rule_type == "budget_rule":
            if "decrease" in content.lower():
                conditions.append({
                    "condition_type": "CPA",
                    "operator": ">",
                    "value": 10.0  # Default threshold
                })
                actions.append({
                    "action_type": "adjust_budget",
                    "action_value": "-20%",  # Default adjustment
                    "priority": 1
                })
            elif "increase" in content.lower():
                conditions.append({
                    "condition_type": "CPA",
                    "operator": "<",
                    "value": 5.0  # Default threshold
                })
                actions.append({
                    "action_type": "adjust_budget",
                    "action_value": "+15%",  # Default adjustment
                    "priority": 1
                })
        
        elif rule_type == "adset_rule":
            if "off" in content.lower() or "pause" in content.lower():
                conditions.append({
                    "condition_type": "CTR",
                    "operator": "<",
                    "value": 1.0  # Default threshold (%)
                })
                actions.append({
                    "action_type": "toggle_adset",
                    "action_value": "PAUSED",
                    "priority": 1
                })
            elif "on" in content.lower() or "activate" in content.lower():
                conditions.append({
                    "condition_type": "CPL",
                    "operator": "<",
                    "value": 5.0  # Default threshold
                })
                actions.append({
                    "action_type": "toggle_adset",
                    "action_value": "ACTIVE",
                    "priority": 1
                })
        
        elif rule_type == "campaign_rule":
            if "create" in content.lower() or "launch" in content.lower():
                conditions.append({
                    "condition_type": "campaign_creation",
                    "operator": "=",
                    "value": 1.0
                })
                actions.append({
                    "action_type": "create_campaign",
                    "action_value": "CONVERSIONS",  # Default campaign objective
                    "priority": 1
                })
        
        # Skip if no conditions or actions were extracted
        if not conditions or not actions:
            return
        
        # Create rule in knowledge base
        rule_data = {
            "knowledge_id": knowledge_entry["id"],
            "name": knowledge_entry["title"],
            "description": content,
            "priority": 1,
            "is_active": True,
            "conditions": conditions,
            "actions": actions
        }
        
        response = requests.post(
            f"{KNOWLEDGE_BASE_URL}/rules/",
            json=rule_data
        )
        
        if response.status_code != 200:
            logger.error(f"Error creating rule: {response.status_code}")
            return
        
        logger.info(f"Rule created from knowledge entry: {knowledge_entry['id']}")
        
    except Exception as e:
        logger.error(f"Error creating rule from knowledge: {str(e)}")

async def evaluate_and_execute_rules(user_id: str, account_id: str, automation_level: str, db: Session):
    """
    Evaluate rules against performance metrics and execute actions.
    
    Args:
        user_id: ID of the user
        account_id: ID of the Facebook account
        automation_level: Level of automation (autonomous, hybrid, approval_required)
        db: Database session
    """
    try:
        # Get Facebook account
        account_response = requests.get(f"{FACEBOOK_ADS_MANAGER_URL}/accounts/{account_id}")
        
        if account_response.status_code != 200:
            logger.error(f"Error getting Facebook account: {account_response.status_code}")
            return
        
        account = account_response.json()
        
        # Get campaigns
        campaigns_response = requests.get(
            f"{FACEBOOK_ADS_MANAGER_URL}/accounts/{account_id}/campaigns/"
        )
        
        if campaigns_response.status_code != 200:
            logger.error(f"Error getting campaigns: {campaigns_response.status_code}")
            return
        
        campaigns = campaigns_response.json()
        
        # Process each campaign
        for campaign in campaigns:
            # Get campaign metrics
            metrics_response = requests.get(
                f"{FACEBOOK_ADS_MANAGER_URL}/campaigns/{campaign['id']}/metrics"
            )
            
            if metrics_response.status_code != 200:
                logger.error(f"Error getting campaign metrics: {metrics_response.status_code}")
                continue
            
            campaign_metrics = metrics_response.json()
            
            # Get ad sets
            adsets_response = requests.get(
                f"{FACEBOOK_ADS_MANAGER_URL}/campaigns/{campaign['id']}/adsets/"
            )
            
            if adsets_response.status_code != 200:
                logger.error(f"Error getting ad sets: {adsets_response.status_code}")
                continue
            
            adsets = adsets_response.json()
            
            # Process each ad set
            for adset in adsets:
                # Get ad set metrics
                adset_metrics_response = requests.get(
                    f"{FACEBOOK_ADS_MANAGER_URL}/adsets/{adset['id']}/metrics"
                )
                
                if adset_metrics_response.status_code != 200:
                    logger.error(f"Error getting ad set metrics: {adset_metrics_response.status_code}")
                    continue
                
                adset_metrics = adset_metrics_response.json()
                
                # Prepare metrics for rule evaluation
                metrics = {}
                
                if adset_metrics:
                    # Calculate average metrics across days
                    impressions = 0
                    clicks = 0
                    conversions = 0
                    spend = 0
                    
                    for metric in adset_metrics:
                        impressions += metric.get("impressions", 0)
                        clicks += metric.get("clicks", 0)
                        conversions += metric.get("conversions", 0)
                        spend += metric.get("spend", 0)
                    
                    # Add metrics
                    if impressions > 0:
                        metrics["impressions"] = impressions
                    
                    if clicks > 0:
                        metrics["clicks"] = clicks
                        if impressions > 0:
                            metrics["CTR"] = (clicks / impressions) * 100  # As percentage
                    
                    if conversions > 0:
                        metrics["conversions"] = conversions
                        if spend > 0:
                            metrics["CPA"] = spend / conversions
                    
                    if spend > 0:
                        metrics["spend"] = spend
                
                # Skip if no metrics
                if not metrics:
                    continue
                
                # Evaluate rules
                rules_response = requests.post(
                    f"{KNOWLEDGE_BASE_URL}/rules/evaluate",
                    json={"metrics": metrics}
                )
                
                if rules_response.status_code != 200:
                    logger.error(f"Error evaluating rules: {rules_response.status_code}")
                    continue
                
                rules_result = rules_response.json()
                
                # Process triggered rules
                for rule in rules_result.get("triggered_rules", []):
                    for action in rule.get("actions", []):
                        # Create decision
                        decision = AIDecision(
                            user_id=user_id,
                            campaign_id=campaign["id"],
                            adset_id=adset["id"],
                            decision_type=action["action_type"],
                            decision_details=json.dumps({
                                "action_value": action["action_value"],
                                "metrics": metrics
                            }),
                            reasoning=f"Rule: {rule['name']} - Based on metrics: {json.dumps(metrics)}",
                            status="pending"
                        )
                        db.add(decision)
                        db.commit()
                        
                        # Execute or request approval based on automation level
                        if automation_level == "autonomous":
                            await execute_decision(decision.id, db)
                        elif automation_level == "hybrid":
                            # Automatically execute low-risk actions, request approval for high-risk
                            if action["action_type"] == "adjust_budget" and not action["action_value"].startswith("+"):
                                # Budget decrease is low-risk
                                await execute_decision(decision.id, db)
                            else:
                                # Other actions require approval
                                decision.status = "pending_approval"
                                db.commit()
                        else:  # approval_required
                            decision.status = "pending_approval"
                            db.commit()
        
        logger.info(f"Rule evaluation completed for account: {account_id}")
        
    except Exception as e:
        logger.error(f"Error in rule evaluation: {str(e)}")

async def execute_decision(decision_id: str, db: Session):
    """
    Execute an AI decision.
    
    Args:
        decision_id: ID of the decision
        db: Database session
    """
    try:
        # Get decision
        decision = db.query(AIDecision).filter(AIDecision.id == decision_id).first()
        
        if not decision:
            logger.error(f"Decision not found: {decision_id}")
            return
        
        # Parse decision details
        details = json.loads(decision.decision_details)
        action_value = details.get("action_value")
        
        # Execute based on decision type
        if decision.decision_type == "adjust_budget":
            if decision.adset_id:
                # Ad set budget adjustment
                if action_value.startswith("+") or action_value.startswith("-"):
                    # Percentage adjustment
                    # Get current budget
                    adset_response = requests.get(f"{FACEBOOK_ADS_MANAGER_URL}/adsets/{decision.adset_id}")
                    
                    if adset_response.status_code != 200:
                        logger.error(f"Error getting ad set: {adset_response.status_code}")
                        decision.status = "failed"
                        db.commit()
                        return
                    
                    adset = adset_response.json()
                    current_budget = adset.get("budget", 0)
                    
                    # Calculate new budget
                    percentage = float(action_value.replace("%", "")) / 100
                    if action_value.startswith("+"):
                        new_budget = current_budget * (1 + percentage)
                    else:  # Starts with "-"
                        new_budget = current_budget * (1 - percentage)
                    
                    # Update budget
                    update_response = requests.put(
                        f"{FACEBOOK_ADS_MANAGER_URL}/adsets/{decision.adset_id}/budget",
                        params={"budget": new_budget}
                    )
                    
                    if update_response.status_code != 200:
                        logger.error(f"Error updating ad set budget: {update_response.status_code}")
                        decision.status = "failed"
                        db.commit()
                        return
                else:
                    # Absolute budget
                    update_response = requests.put(
                        f"{FACEBOOK_ADS_MANAGER_URL}/adsets/{decision.adset_id}/budget",
                        params={"budget": float(action_value)}
                    )
                    
                    if update_response.status_code != 200:
                        logger.error(f"Error updating ad set budget: {update_response.status_code}")
                        decision.status = "failed"
                        db.commit()
                        return
            
            elif decision.campaign_id:
                # Campaign budget adjustment
                if action_value.startswith("+") or action_value.startswith("-"):
                    # Percentage adjustment
                    # Get current budget
                    campaign_response = requests.get(f"{FACEBOOK_ADS_MANAGER_URL}/campaigns/{decision.campaign_id}")
                    
                    if campaign_response.status_code != 200:
                        logger.error(f"Error getting campaign: {campaign_response.status_code}")
                        decision.status = "failed"
                        db.commit()
                        return
                    
                    campaign = campaign_response.json()
                    current_budget = campaign.get("daily_budget", 0)
                    
                    # Calculate new budget
                    percentage = float(action_value.replace("%", "")) / 100
                    if action_value.startswith("+"):
                        new_budget = current_budget * (1 + percentage)
                    else:  # Starts with "-"
                        new_budget = current_budget * (1 - percentage)
                    
                    # Update budget
                    update_response = requests.put(
                        f"{FACEBOOK_ADS_MANAGER_URL}/campaigns/{decision.campaign_id}/budget",
                        params={"daily_budget": new_budget}
                    )
                    
                    if update_response.status_code != 200:
                        logger.error(f"Error updating campaign budget: {update_response.status_code}")
                        decision.status = "failed"
                        db.commit()
                        return
                else:
                    # Absolute budget
                    update_response = requests.put(
                        f"{FACEBOOK_ADS_MANAGER_URL}/campaigns/{decision.campaign_id}/budget",
                        params={"daily_budget": float(action_value)}
                    )
                    
                    if update_response.status_code != 200:
                        logger.error(f"Error updating campaign budget: {update_response.status_code}")
                        decision.status = "failed"
                        db.commit()
                        return
        
        elif decision.decision_type == "toggle_adset":
            # Toggle ad set status
            update_response = requests.put(
                f"{FACEBOOK_ADS_MANAGER_URL}/adsets/{decision.adset_id}/status",
                params={"status": action_value}
            )
            
            if update_response.status_code != 200:
                logger.error(f"Error updating ad set status: {update_response.status_code}")
                decision.status = "failed"
                db.commit()
                return
        
        elif decision.decision_type == "create_campaign":
            # Get Facebook account ID from an existing campaign
            campaign_response = requests.get(f"{FACEBOOK_ADS_MANAGER_URL}/campaigns/{decision.campaign_id}")
            
            if campaign_response.status_code != 200:
                logger.error(f"Error getting campaign: {campaign_response.status_code}")
                decision.status = "failed"
                db.commit()
                return
            
            campaign = campaign_response.json()
            account_id = campaign.get("account_id")
            
            if not account_id:
                logger.error("Account ID not found in campaign")
                decision.status = "failed"
                db.commit()
                return
            
            # Create new campaign
            new_campaign_data = {
                "name": f"Auto-created Campaign - {datetime.utcnow().strftime('%Y-%m-%d')}",
                "objective": action_value,
                "status": "PAUSED",  # Start as paused for safety
                "daily_budget": 50.0  # Default budget
            }
            
            create_response = requests.post(
                f"{FACEBOOK_ADS_MANAGER_URL}/accounts/{account_id}/campaigns/",
                json=new_campaign_data
            )
            
            if create_response.status_code != 200:
                logger.error(f"Error creating campaign: {create_response.status_code}")
                decision.status = "failed"
                db.commit()
                return
        
        # Update decision status
        decision.status = "executed"
        decision.executed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Decision executed: {decision_id}")
        
    except Exception as e:
        logger.error(f"Error executing decision: {str(e)}")
        
        # Update decision status
        decision = db.query(AIDecision).filter(AIDecision.id == decision_id).first()
        if decision:
            decision.status = "failed"
            db.commit()

# API endpoints
@app.post("/documents/upload", response_model=DocumentUploadResponse)
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
        user_id: ID of the user
        title: Title of the document
        file: PDF file to upload
        
    Returns:
        Document upload status
    """
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Upload to document processor
        files = {"file": (file.filename, await file.read(), file.content_type)}
        data = {"user_id": user_id, "title": title}
        
        response = requests.post(
            f"{DOCUMENT_PROCESSOR_URL}/documents/",
            files=files,
            params=data
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error uploading document to processor")
        
        document_data = response.json()
        document_id = document_data["id"]
        
        # Process document in background
        background_tasks.add_task(process_document, user_id, document_id, db)
        
        return DocumentUploadResponse(
            document_id=document_id,
            status="processing",
            message="Document uploaded and processing started"
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")

@app.post("/query", response_model=AIQueryResponse)
async def create_query(
    query: AIQueryCreate,
    db: Session = Depends(get_db)
):
    """
    Create a query to the AI.
    
    Args:
        query: Query data
        
    Returns:
        Query response
    """
    try:
        # Create query record
        db_query = AIQuery(
            user_id=query.user_id,
            query_text=query.query_text
        )
        db.add(db_query)
        db.commit()
        db.refresh(db_query)
        
        # Get relevant knowledge
        knowledge_response = requests.get(
            f"{KNOWLEDGE_BASE_URL}/knowledge/search",
            params={"query": query.query_text}
        )
        
        knowledge_context = ""
        if knowledge_response.status_code == 200:
            results = knowledge_response.json()
            
            if results:
                # Format knowledge entries
                for i, entry in enumerate(results[:5]):  # Limit to top 5 results
                    knowledge_context += f"{i+1}. {entry['title']}: {entry['content']}\n\n"
        
        # Prepare prompt with context
        prompt = f"As an AI media buying agent, use the following knowledge to answer the query. If the knowledge doesn't contain relevant information, use your general knowledge about media buying.\n\nKnowledge: {knowledge_context}\n\nQuery: {query.query_text}"
        
        # Call Poe.com API (simplified for this example)
        # In a real implementation, this would use the Poe.com API client
        response_text = f"Based on the available knowledge, here's my response to your query: '{query.query_text}'\n\n"
        response_text += "This is a placeholder response. In a real implementation, this would be generated by Poe.com API."
        
        # Update query with response
        db_query.response_text = response_text
        db.commit()
        db.refresh(db_query)
        
        return db_query
        
    except Exception as e:
        logger.error(f"Error creating query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating query: {str(e)}")

@app.get("/decisions/", response_model=List[AIDecisionResponse])
def get_decisions(
    user_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get AI decisions for a user.
    
    Args:
        user_id: ID of the user
        status: Filter by status
        
    Returns:
        List of AI decisions
    """
    query = db.query(AIDecision).filter(AIDecision.user_id == user_id)
    
    if status:
        query = query.filter(AIDecision.status == status)
    
    decisions = query.order_by(AIDecision.created_at.desc()).all()
    
    # Convert decision_details from JSON string to dict
    for decision in decisions:
        decision.decision_details = json.loads(decision.decision_details)
    
    return decisions

@app.post("/decisions/{decision_id}/approve")
async def approve_decision(
    decision_id: str,
    db: Session = Depends(get_db)
):
    """
    Approve an AI decision.
    
    Args:
        decision_id: ID of the decision
        
    Returns:
        Success message
    """
    decision = db.query(AIDecision).filter(AIDecision.id == decision_id).first()
    
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    if decision.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Decision is not pending approval: {decision.status}")
    
    # Execute decision
    await execute_decision(decision_id, db)
    
    return {"message": "Decision approved and executed", "decision_id": decision_id}

@app.post("/decisions/{decision_id}/reject")
def reject_decision(
    decision_id: str,
    db: Session = Depends(get_db)
):
    """
    Reject an AI decision.
    
    Args:
        decision_id: ID of the decision
        
    Returns:
        Success message
    """
    decision = db.query(AIDecision).filter(AIDecision.id == decision_id).first()
    
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    if decision.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Decision is not pending approval: {decision.status}")
    
    # Update decision status
    decision.status = "rejected"
    db.commit()
    
    return {"message": "Decision rejected", "decision_id": decision_id}

@app.post("/automation/run")
async def run_automation(
    request: AutomationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Run automation for a Facebook account.
    
    Args:
        request: Automation request data
        
    Returns:
        Success message
    """
    # Run automation in background
    background_tasks.add_task(
        evaluate_and_execute_rules,
        request.user_id,
        request.account_id,
        request.automation_level,
        db
    )
    
    return {
        "message": "Automation started",
        "user_id": request.user_id,
        "account_id": request.account_id,
        "automation_level": request.automation_level
    }

# Poe.com bot endpoint
@app.post("/poe/bot")
async def poe_bot_endpoint(request: Request):
    """
    Endpoint for Poe.com bot integration.
    
    Args:
        request: HTTP request
        
    Returns:
        Bot response
    """
    bot = MediaBuyingBot()
    app = fp.make_app(bot, allow_without_key=True)
    
    # Forward request to Poe.com bot app
    return await app(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
