"""
Facebook Ads Manager Module for AI-Driven Media Buying Agent

This module handles the integration with Facebook Ads API, providing functionality
for authentication, campaign management, ad set management, and budget adjustments.
"""

import os
import logging
import time
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
from facebook_business.exceptions import FacebookRequestError
import requests
import json

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
APP_ID = os.getenv("FACEBOOK_APP_ID")
APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI")
API_VERSION = os.getenv("FACEBOOK_API_VERSION", "v18.0")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./facebook_ads_manager.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Initialize FastAPI app
app = FastAPI(title="Facebook Ads Manager API", 
              description="API for managing Facebook Ads campaigns, ad sets, and budgets")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Models
class FacebookAccount(Base):
    __tablename__ = "facebook_accounts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    fb_account_id = Column(String, nullable=False)
    name = Column(String, nullable=True)
    access_token = Column(String, nullable=False)
    token_expiry = Column(DateTime, nullable=True)
    refresh_token = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    campaigns = relationship("Campaign", back_populates="account", cascade="all, delete-orphan")

class CampaignModel(Base):
    __tablename__ = "campaigns"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("facebook_accounts.id"), nullable=False)
    fb_campaign_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    objective = Column(String, nullable=True)
    status = Column(String, nullable=False)
    daily_budget = Column(Float, nullable=True)
    lifetime_budget = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    account = relationship("FacebookAccount", back_populates="campaigns")
    ad_sets = relationship("AdSetModel", back_populates="campaign", cascade="all, delete-orphan")

class AdSetModel(Base):
    __tablename__ = "ad_sets"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    fb_adset_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    targeting = Column(Text, nullable=True)  # JSON string
    budget = Column(Float, nullable=True)
    bid_amount = Column(Float, nullable=True)
    billing_event = Column(String, nullable=True)
    optimization_goal = Column(String, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    campaign = relationship("CampaignModel", back_populates="ad_sets")
    performance_metrics = relationship("PerformanceMetric", back_populates="ad_set", cascade="all, delete-orphan")

class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    adset_id = Column(String, ForeignKey("ad_sets.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    conversions = Column(Integer, nullable=True)
    spend = Column(Float, nullable=True)
    cpa = Column(Float, nullable=True)
    cpl = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ad_set = relationship("AdSetModel", back_populates="performance_metrics")

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
class FacebookAccountCreate(BaseModel):
    user_id: str
    fb_account_id: str
    name: Optional[str] = None
    access_token: str
    token_expiry: Optional[datetime] = None
    refresh_token: Optional[str] = None

class FacebookAccountResponse(BaseModel):
    id: str
    user_id: str
    fb_account_id: str
    name: Optional[str]
    token_expiry: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class CampaignCreate(BaseModel):
    name: str
    objective: str
    status: str = "PAUSED"  # Default to PAUSED for safety
    daily_budget: Optional[float] = None
    lifetime_budget: Optional[float] = None

class CampaignResponse(BaseModel):
    id: str
    fb_campaign_id: str
    name: str
    objective: Optional[str]
    status: str
    daily_budget: Optional[float]
    lifetime_budget: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class AdSetCreate(BaseModel):
    name: str
    targeting: Dict[str, Any]
    budget: float
    bid_amount: Optional[float] = None
    billing_event: str
    optimization_goal: str
    status: str = "PAUSED"  # Default to PAUSED for safety

class AdSetResponse(BaseModel):
    id: str
    fb_adset_id: str
    name: str
    targeting: Dict[str, Any]
    budget: Optional[float]
    bid_amount: Optional[float]
    billing_event: Optional[str]
    optimization_goal: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class PerformanceMetricResponse(BaseModel):
    id: str
    adset_id: str
    date: datetime
    impressions: Optional[int]
    clicks: Optional[int]
    conversions: Optional[int]
    spend: Optional[float]
    cpa: Optional[float]
    cpl: Optional[float]
    
    class Config:
        orm_mode = True

# Helper functions
def initialize_facebook_api(access_token: str):
    """
    Initialize the Facebook Ads API with the provided access token.
    
    Args:
        access_token: Facebook access token
        
    Returns:
        Initialized FacebookAdsApi instance
    """
    try:
        api = FacebookAdsApi.init(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            access_token=access_token,
            api_version=API_VERSION
        )
        return api
    except Exception as e:
        logger.error(f"Error initializing Facebook Ads API: {str(e)}")
        raise

def get_ad_account(access_token: str, account_id: str):
    """
    Get an AdAccount object for the specified account ID.
    
    Args:
        access_token: Facebook access token
        account_id: Facebook ad account ID
        
    Returns:
        AdAccount object
    """
    try:
        initialize_facebook_api(access_token)
        # Make sure account_id has 'act_' prefix
        if not account_id.startswith('act_'):
            account_id = f'act_{account_id}'
        return AdAccount(account_id)
    except Exception as e:
        logger.error(f"Error getting ad account: {str(e)}")
        raise

def handle_facebook_error(func):
    """
    Decorator to handle Facebook API errors.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                return func(*args, **kwargs)
            except FacebookRequestError as e:
                # Handle rate limiting
                if e.api_error_code() == 17 or e.api_error_code() == 4:  # Rate limiting error codes
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # Exponential backoff
                        logger.warning(f"Rate limited by Facebook API. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Facebook API rate limit exceeded after {max_retries} retries")
                        raise HTTPException(status_code=429, detail="Facebook API rate limit exceeded")
                # Handle token expiration
                elif e.api_error_code() == 190:  # Invalid/expired token
                    logger.error("Facebook access token is invalid or expired")
                    raise HTTPException(status_code=401, detail="Facebook access token is invalid or expired")
                # Handle other errors
                else:
                    logger.error(f"Facebook API error: {e.api_error_message()}")
                    raise HTTPException(status_code=400, detail=f"Facebook API error: {e.api_error_message()}")
            except Exception as e:
                logger.error(f"Error in Facebook API call: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error in Facebook API call: {str(e)}")
    
    return wrapper

# Authentication endpoints
@app.get("/auth/facebook")
def facebook_auth():
    """
    Initiate Facebook OAuth flow.
    
    Returns:
        Redirect to Facebook login
    """
    if not APP_ID or not APP_SECRET or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Facebook App credentials not configured")
    
    # Construct Facebook OAuth URL
    oauth_url = f"https://www.facebook.com/{API_VERSION}/dialog/oauth"
    params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "ads_management,ads_read",
        "response_type": "code",
        "state": "state123"  # Use a secure random state in production
    }
    
    # Convert params to URL query string
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    auth_url = f"{oauth_url}?{query_string}"
    
    return RedirectResponse(auth_url)

@app.get("/auth/facebook/callback")
async def facebook_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    Handle Facebook OAuth callback.
    
    Args:
        code: Authorization code from Facebook
        state: State parameter for security validation
        
    Returns:
        Access token information
    """
    if not APP_ID or not APP_SECRET or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Facebook App credentials not configured")
    
    # Exchange code for access token
    token_url = f"https://graph.facebook.com/{API_VERSION}/oauth/access_token"
    params = {
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }
    
    try:
        response = requests.get(token_url, params=params)
        response.raise_for_status()
        token_data = response.json()
        
        # Get long-lived token
        long_lived_url = f"https://graph.facebook.com/{API_VERSION}/oauth/access_token"
        long_lived_params = {
            "grant_type": "fb_exchange_token",
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "fb_exchange_token": token_data["access_token"]
        }
        
        long_lived_response = requests.get(long_lived_url, params=long_lived_params)
        long_lived_response.raise_for_status()
        long_lived_data = long_lived_response.json()
        
        # Get user's ad accounts
        access_token = long_lived_data["access_token"]
        accounts_url = f"https://graph.facebook.com/{API_VERSION}/me/adaccounts"
        accounts_params = {
            "access_token": access_token,
            "fields": "id,name,account_id"
        }
        
        accounts_response = requests.get(accounts_url, params=accounts_params)
        accounts_response.raise_for_status()
        accounts_data = accounts_response.json()
        
        # For now, just return the token and accounts data
        # In a real implementation, you would store this in the database
        return {
            "access_token": access_token,
            "token_type": long_lived_data.get("token_type", "bearer"),
            "expires_in": long_lived_data.get("expires_in"),
            "ad_accounts": accounts_data.get("data", [])
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error exchanging code for token: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error exchanging code for token: {str(e)}")

# Facebook account management endpoints
@app.post("/accounts/", response_model=FacebookAccountResponse)
def create_facebook_account(account: FacebookAccountCreate, db: Session = Depends(get_db)):
    """
    Create a new Facebook account connection.
    
    Args:
        account: Facebook account data
        
    Returns:
        Created account
    """
    # Check if account already exists
    existing_account = db.query(FacebookAccount).filter(
        FacebookAccount.user_id == account.user_id,
        FacebookAccount.fb_account_id == account.fb_account_id
    ).first()
    
    if existing_account:
        # Update existing account
        existing_account.access_token = account.access_token
        existing_account.token_expiry = account.token_expiry
        existing_account.refresh_token = account.refresh_token
        existing_account.name = account.name
        existing_account.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_account)
        return existing_account
    
    # Create new account
    db_account = FacebookAccount(
        user_id=account.user_id,
        fb_account_id=account.fb_account_id,
        name=account.name,
        access_token=account.access_token,
        token_expiry=account.token_expiry,
        refresh_token=account.refresh_token
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    
    return db_account

@app.get("/accounts/", response_model=List[FacebookAccountResponse])
def get_facebook_accounts(user_id: str, db: Session = Depends(get_db)):
    """
    Get all Facebook accounts for a user.
    
    Args:
        user_id: ID of the user
        
    Returns:
        List of Facebook accounts
    """
    accounts = db.query(FacebookAccount).filter(FacebookAccount.user_id == user_id).all()
    return accounts

@app.get("/accounts/{account_id}", response_model=FacebookAccountResponse)
def get_facebook_account(account_id: str, db: Session = Depends(get_db)):
    """
    Get a Facebook account by ID.
    
    Args:
        account_id: ID of the account
        
    Returns:
        Facebook account
    """
    account = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    return account

@app.delete("/accounts/{account_id}")
def delete_facebook_account(account_id: str, db: Session = Depends(get_db)):
    """
    Delete a Facebook account connection.
    
    Args:
        account_id: ID of the account
        
    Returns:
        Success message
    """
    account = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    db.delete(account)
    db.commit()
    
    return {"message": "Facebook account deleted successfully"}

# Campaign management endpoints
@app.post("/accounts/{account_id}/campaigns/", response_model=CampaignResponse)
@handle_facebook_error
def create_campaign(
    account_id: str,
    campaign: CampaignCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new campaign in Facebook Ads.
    
    Args:
        account_id: ID of the Facebook account
        campaign: Campaign data
        
    Returns:
        Created campaign
    """
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Initialize Facebook API
    ad_account = get_ad_account(account.access_token, account.fb_account_id)
    
    # Create campaign on Facebook
    params = {
        'name': campaign.name,
        'objective': campaign.objective,
        'status': campaign.status,
        'special_ad_categories': []
    }
    
    if campaign.daily_budget:
        params['daily_budget'] = int(campaign.daily_budget * 100)  # Convert to cents
    
    if campaign.lifetime_budget:
        params['lifetime_budget'] = int(campaign.lifetime_budget * 100)  # Convert to cents
    
    fb_campaign = ad_account.create_campaign(params=params)
    
    # Store campaign in database
    db_campaign = CampaignModel(
        account_id=account_id,
        fb_campaign_id=fb_campaign['id'],
        name=campaign.name,
        objective=campaign.objective,
        status=campaign.status,
        daily_budget=campaign.daily_budget,
        lifetime_budget=campaign.lifetime_budget
    )
    db.add(db_campaign)
    db.commit()
    db.refresh(db_campaign)
    
    return db_campaign

@app.get("/accounts/{account_id}/campaigns/", response_model=List[CampaignResponse])
@handle_facebook_error
def get_campaigns(account_id: str, db: Session = Depends(get_db)):
    """
    Get all campaigns for a Facebook account.
    
    Args:
        account_id: ID of the Facebook account
        
    Returns:
        List of campaigns
    """
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Initialize Facebook API
    ad_account = get_ad_account(account.access_token, account.fb_account_id)
    
    # Get campaigns from Facebook
    fields = [
        'id',
        'name',
        'objective',
        'status',
        'daily_budget',
        'lifetime_budget'
    ]
    fb_campaigns = ad_account.get_campaigns(fields=fields)
    
    # Update local database with latest data
    for fb_campaign in fb_campaigns:
        # Check if campaign exists in database
        db_campaign = db.query(CampaignModel).filter(
            CampaignModel.account_id == account_id,
            CampaignModel.fb_campaign_id == fb_campaign['id']
        ).first()
        
        if db_campaign:
            # Update existing campaign
            db_campaign.name = fb_campaign.get('name', db_campaign.name)
            db_campaign.objective = fb_campaign.get('objective', db_campaign.objective)
            db_campaign.status = fb_campaign.get('status', db_campaign.status)
            
            if 'daily_budget' in fb_campaign:
                db_campaign.daily_budget = float(fb_campaign['daily_budget']) / 100  # Convert from cents
            
            if 'lifetime_budget' in fb_campaign:
                db_campaign.lifetime_budget = float(fb_campaign['lifetime_budget']) / 100  # Convert from cents
            
            db_campaign.updated_at = datetime.utcnow()
        else:
            # Create new campaign record
            daily_budget = None
            if 'daily_budget' in fb_campaign:
                daily_budget = float(fb_campaign['daily_budget']) / 100  # Convert from cents
            
            lifetime_budget = None
            if 'lifetime_budget' in fb_campaign:
                lifetime_budget = float(fb_campaign['lifetime_budget']) / 100  # Convert from cents
            
            db_campaign = CampaignModel(
                account_id=account_id,
                fb_campaign_id=fb_campaign['id'],
                name=fb_campaign.get('name', ''),
                objective=fb_campaign.get('objective'),
                status=fb_campaign.get('status', 'UNKNOWN'),
                daily_budget=daily_budget,
                lifetime_budget=lifetime_budget
            )
            db.add(db_campaign)
    
    db.commit()
    
    # Return campaigns from database
    campaigns = db.query(CampaignModel).filter(CampaignModel.account_id == account_id).all()
    return campaigns

@app.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    """
    Get a campaign by ID.
    
    Args:
        campaign_id: ID of the campaign
        
    Returns:
        Campaign
    """
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

@app.put("/campaigns/{campaign_id}/status")
@handle_facebook_error
def update_campaign_status(
    campaign_id: str,
    status: str,
    db: Session = Depends(get_db)
):
    """
    Update a campaign's status.
    
    Args:
        campaign_id: ID of the campaign
        status: New status (ACTIVE, PAUSED, ARCHIVED)
        
    Returns:
        Updated campaign
    """
    # Validate status
    valid_statuses = ['ACTIVE', 'PAUSED', 'ARCHIVED']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
    
    # Get campaign
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == campaign.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Initialize Facebook API
    initialize_facebook_api(account.access_token)
    
    # Update campaign on Facebook
    fb_campaign = Campaign(campaign.fb_campaign_id)
    fb_campaign.api_update(params={'status': status})
    
    # Update campaign in database
    campaign.status = status
    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    
    return {"message": f"Campaign status updated to {status}", "campaign_id": campaign_id}

@app.put("/campaigns/{campaign_id}/budget")
@handle_facebook_error
def update_campaign_budget(
    campaign_id: str,
    daily_budget: Optional[float] = None,
    lifetime_budget: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    Update a campaign's budget.
    
    Args:
        campaign_id: ID of the campaign
        daily_budget: New daily budget in currency units
        lifetime_budget: New lifetime budget in currency units
        
    Returns:
        Updated campaign
    """
    if daily_budget is None and lifetime_budget is None:
        raise HTTPException(status_code=400, detail="Either daily_budget or lifetime_budget must be provided")
    
    # Get campaign
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == campaign.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Initialize Facebook API
    initialize_facebook_api(account.access_token)
    
    # Update campaign on Facebook
    fb_campaign = Campaign(campaign.fb_campaign_id)
    params = {}
    
    if daily_budget is not None:
        params['daily_budget'] = int(daily_budget * 100)  # Convert to cents
        campaign.daily_budget = daily_budget
    
    if lifetime_budget is not None:
        params['lifetime_budget'] = int(lifetime_budget * 100)  # Convert to cents
        campaign.lifetime_budget = lifetime_budget
    
    fb_campaign.api_update(params=params)
    
    # Update campaign in database
    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    
    return {"message": "Campaign budget updated", "campaign_id": campaign_id}

# Ad set management endpoints
@app.post("/campaigns/{campaign_id}/adsets/", response_model=AdSetResponse)
@handle_facebook_error
def create_ad_set(
    campaign_id: str,
    ad_set: AdSetCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new ad set in a campaign.
    
    Args:
        campaign_id: ID of the campaign
        ad_set: Ad set data
        
    Returns:
        Created ad set
    """
    # Get campaign
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == campaign.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Initialize Facebook API
    ad_account = get_ad_account(account.access_token, account.fb_account_id)
    
    # Create ad set on Facebook
    params = {
        'name': ad_set.name,
        'campaign_id': campaign.fb_campaign_id,
        'targeting': ad_set.targeting,
        'status': ad_set.status,
        'billing_event': ad_set.billing_event,
        'optimization_goal': ad_set.optimization_goal,
        'daily_budget': int(ad_set.budget * 100)  # Convert to cents
    }
    
    if ad_set.bid_amount:
        params['bid_amount'] = int(ad_set.bid_amount * 100)  # Convert to cents
    
    fb_adset = ad_account.create_ad_set(params=params)
    
    # Store ad set in database
    db_adset = AdSetModel(
        campaign_id=campaign_id,
        fb_adset_id=fb_adset['id'],
        name=ad_set.name,
        targeting=json.dumps(ad_set.targeting),
        budget=ad_set.budget,
        bid_amount=ad_set.bid_amount,
        billing_event=ad_set.billing_event,
        optimization_goal=ad_set.optimization_goal,
        status=ad_set.status
    )
    db.add(db_adset)
    db.commit()
    db.refresh(db_adset)
    
    # Convert targeting JSON string back to dict for response
    response = AdSetResponse(
        id=db_adset.id,
        fb_adset_id=db_adset.fb_adset_id,
        name=db_adset.name,
        targeting=json.loads(db_adset.targeting),
        budget=db_adset.budget,
        bid_amount=db_adset.bid_amount,
        billing_event=db_adset.billing_event,
        optimization_goal=db_adset.optimization_goal,
        status=db_adset.status,
        created_at=db_adset.created_at,
        updated_at=db_adset.updated_at
    )
    
    return response

@app.get("/campaigns/{campaign_id}/adsets/", response_model=List[AdSetResponse])
@handle_facebook_error
def get_ad_sets(campaign_id: str, db: Session = Depends(get_db)):
    """
    Get all ad sets for a campaign.
    
    Args:
        campaign_id: ID of the campaign
        
    Returns:
        List of ad sets
    """
    # Get campaign
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == campaign.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Initialize Facebook API
    initialize_facebook_api(account.access_token)
    
    # Get ad sets from Facebook
    fb_campaign = Campaign(campaign.fb_campaign_id)
    fields = [
        'id',
        'name',
        'status',
        'daily_budget',
        'targeting',
        'bid_amount',
        'billing_event',
        'optimization_goal'
    ]
    fb_adsets = fb_campaign.get_ad_sets(fields=fields)
    
    # Update local database with latest data
    for fb_adset in fb_adsets:
        # Check if ad set exists in database
        db_adset = db.query(AdSetModel).filter(
            AdSetModel.campaign_id == campaign_id,
            AdSetModel.fb_adset_id == fb_adset['id']
        ).first()
        
        if db_adset:
            # Update existing ad set
            db_adset.name = fb_adset.get('name', db_adset.name)
            db_adset.status = fb_adset.get('status', db_adset.status)
            
            if 'targeting' in fb_adset:
                db_adset.targeting = json.dumps(fb_adset['targeting'])
            
            if 'daily_budget' in fb_adset:
                db_adset.budget = float(fb_adset['daily_budget']) / 100  # Convert from cents
            
            if 'bid_amount' in fb_adset:
                db_adset.bid_amount = float(fb_adset['bid_amount']) / 100  # Convert from cents
            
            db_adset.billing_event = fb_adset.get('billing_event', db_adset.billing_event)
            db_adset.optimization_goal = fb_adset.get('optimization_goal', db_adset.optimization_goal)
            db_adset.updated_at = datetime.utcnow()
        else:
            # Create new ad set record
            targeting = {}
            if 'targeting' in fb_adset:
                targeting = fb_adset['targeting']
            
            budget = None
            if 'daily_budget' in fb_adset:
                budget = float(fb_adset['daily_budget']) / 100  # Convert from cents
            
            bid_amount = None
            if 'bid_amount' in fb_adset:
                bid_amount = float(fb_adset['bid_amount']) / 100  # Convert from cents
            
            db_adset = AdSetModel(
                campaign_id=campaign_id,
                fb_adset_id=fb_adset['id'],
                name=fb_adset.get('name', ''),
                targeting=json.dumps(targeting),
                budget=budget,
                bid_amount=bid_amount,
                billing_event=fb_adset.get('billing_event'),
                optimization_goal=fb_adset.get('optimization_goal'),
                status=fb_adset.get('status', 'UNKNOWN')
            )
            db.add(db_adset)
    
    db.commit()
    
    # Return ad sets from database
    adsets = db.query(AdSetModel).filter(AdSetModel.campaign_id == campaign_id).all()
    
    # Convert targeting JSON string to dict for each ad set
    responses = []
    for adset in adsets:
        responses.append(AdSetResponse(
            id=adset.id,
            fb_adset_id=adset.fb_adset_id,
            name=adset.name,
            targeting=json.loads(adset.targeting),
            budget=adset.budget,
            bid_amount=adset.bid_amount,
            billing_event=adset.billing_event,
            optimization_goal=adset.optimization_goal,
            status=adset.status,
            created_at=adset.created_at,
            updated_at=adset.updated_at
        ))
    
    return responses

@app.get("/adsets/{adset_id}", response_model=AdSetResponse)
def get_ad_set(adset_id: str, db: Session = Depends(get_db)):
    """
    Get an ad set by ID.
    
    Args:
        adset_id: ID of the ad set
        
    Returns:
        Ad set
    """
    adset = db.query(AdSetModel).filter(AdSetModel.id == adset_id).first()
    if not adset:
        raise HTTPException(status_code=404, detail="Ad set not found")
    
    # Convert targeting JSON string to dict
    response = AdSetResponse(
        id=adset.id,
        fb_adset_id=adset.fb_adset_id,
        name=adset.name,
        targeting=json.loads(adset.targeting),
        budget=adset.budget,
        bid_amount=adset.bid_amount,
        billing_event=adset.billing_event,
        optimization_goal=adset.optimization_goal,
        status=adset.status,
        created_at=adset.created_at,
        updated_at=adset.updated_at
    )
    
    return response

@app.put("/adsets/{adset_id}/status")
@handle_facebook_error
def update_ad_set_status(
    adset_id: str,
    status: str,
    db: Session = Depends(get_db)
):
    """
    Update an ad set's status.
    
    Args:
        adset_id: ID of the ad set
        status: New status (ACTIVE, PAUSED, ARCHIVED)
        
    Returns:
        Updated ad set
    """
    # Validate status
    valid_statuses = ['ACTIVE', 'PAUSED', 'ARCHIVED']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
    
    # Get ad set
    adset = db.query(AdSetModel).filter(AdSetModel.id == adset_id).first()
    if not adset:
        raise HTTPException(status_code=404, detail="Ad set not found")
    
    # Get campaign
    campaign = db.query(CampaignModel).filter(CampaignModel.id == adset.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == campaign.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Initialize Facebook API
    initialize_facebook_api(account.access_token)
    
    # Update ad set on Facebook
    fb_adset = AdSet(adset.fb_adset_id)
    fb_adset.api_update(params={'status': status})
    
    # Update ad set in database
    adset.status = status
    adset.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(adset)
    
    return {"message": f"Ad set status updated to {status}", "adset_id": adset_id}

@app.put("/adsets/{adset_id}/budget")
@handle_facebook_error
def update_ad_set_budget(
    adset_id: str,
    budget: float,
    db: Session = Depends(get_db)
):
    """
    Update an ad set's budget.
    
    Args:
        adset_id: ID of the ad set
        budget: New budget in currency units
        
    Returns:
        Updated ad set
    """
    # Get ad set
    adset = db.query(AdSetModel).filter(AdSetModel.id == adset_id).first()
    if not adset:
        raise HTTPException(status_code=404, detail="Ad set not found")
    
    # Get campaign
    campaign = db.query(CampaignModel).filter(CampaignModel.id == adset.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == campaign.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Initialize Facebook API
    initialize_facebook_api(account.access_token)
    
    # Update ad set on Facebook
    fb_adset = AdSet(adset.fb_adset_id)
    fb_adset.api_update(params={'daily_budget': int(budget * 100)})  # Convert to cents
    
    # Update ad set in database
    adset.budget = budget
    adset.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(adset)
    
    return {"message": "Ad set budget updated", "adset_id": adset_id}

# Performance metrics endpoints
@app.get("/adsets/{adset_id}/metrics", response_model=List[PerformanceMetricResponse])
@handle_facebook_error
def get_ad_set_metrics(
    adset_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get performance metrics for an ad set.
    
    Args:
        adset_id: ID of the ad set
        start_date: Start date for metrics (YYYY-MM-DD)
        end_date: End date for metrics (YYYY-MM-DD)
        
    Returns:
        List of performance metrics
    """
    # Get ad set
    adset = db.query(AdSetModel).filter(AdSetModel.id == adset_id).first()
    if not adset:
        raise HTTPException(status_code=404, detail="Ad set not found")
    
    # Get campaign
    campaign = db.query(CampaignModel).filter(CampaignModel.id == adset.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == campaign.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Set default date range if not provided
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    if not end_date:
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    # Initialize Facebook API
    initialize_facebook_api(account.access_token)
    
    # Get metrics from Facebook
    fb_adset = AdSet(adset.fb_adset_id)
    params = {
        'time_range': {
            'since': start_date,
            'until': end_date
        },
        'time_increment': 1,  # Daily breakdown
        'fields': [
            'impressions',
            'clicks',
            'actions',
            'spend'
        ]
    }
    
    insights = fb_adset.get_insights(params=params)
    
    # Process and store metrics
    metrics = []
    
    for insight in insights:
        date = datetime.strptime(insight.get('date_start'), '%Y-%m-%d')
        impressions = int(insight.get('impressions', 0))
        clicks = int(insight.get('clicks', 0))
        spend = float(insight.get('spend', 0))
        
        # Extract conversions from actions
        conversions = 0
        if 'actions' in insight:
            for action in insight['actions']:
                if action['action_type'] in ['offsite_conversion', 'lead']:
                    conversions += int(action['value'])
        
        # Calculate CPA and CPL
        cpa = None
        if conversions > 0 and spend > 0:
            cpa = spend / conversions
        
        cpl = None
        if 'actions' in insight:
            leads = 0
            for action in insight['actions']:
                if action['action_type'] == 'lead':
                    leads += int(action['value'])
            
            if leads > 0 and spend > 0:
                cpl = spend / leads
        
        # Check if metric already exists in database
        db_metric = db.query(PerformanceMetric).filter(
            PerformanceMetric.adset_id == adset_id,
            PerformanceMetric.date == date
        ).first()
        
        if db_metric:
            # Update existing metric
            db_metric.impressions = impressions
            db_metric.clicks = clicks
            db_metric.conversions = conversions
            db_metric.spend = spend
            db_metric.cpa = cpa
            db_metric.cpl = cpl
        else:
            # Create new metric
            db_metric = PerformanceMetric(
                adset_id=adset_id,
                date=date,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                spend=spend,
                cpa=cpa,
                cpl=cpl
            )
            db.add(db_metric)
        
        metrics.append(db_metric)
    
    db.commit()
    
    # Refresh metrics from database
    for i, metric in enumerate(metrics):
        db.refresh(metric)
    
    return metrics

@app.get("/campaigns/{campaign_id}/metrics")
@handle_facebook_error
def get_campaign_metrics(
    campaign_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get aggregated performance metrics for a campaign.
    
    Args:
        campaign_id: ID of the campaign
        start_date: Start date for metrics (YYYY-MM-DD)
        end_date: End date for metrics (YYYY-MM-DD)
        
    Returns:
        Aggregated metrics
    """
    # Get campaign
    campaign = db.query(CampaignModel).filter(CampaignModel.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get Facebook account
    account = db.query(FacebookAccount).filter(FacebookAccount.id == campaign.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Facebook account not found")
    
    # Set default date range if not provided
    if not start_date:
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    if not end_date:
        end_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    # Initialize Facebook API
    initialize_facebook_api(account.access_token)
    
    # Get metrics from Facebook
    fb_campaign = Campaign(campaign.fb_campaign_id)
    params = {
        'time_range': {
            'since': start_date,
            'until': end_date
        },
        'fields': [
            'impressions',
            'clicks',
            'actions',
            'spend'
        ]
    }
    
    insights = fb_campaign.get_insights(params=params)
    
    if not insights:
        return {
            "campaign_id": campaign_id,
            "start_date": start_date,
            "end_date": end_date,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "spend": 0,
            "cpa": None,
            "cpl": None,
            "ctr": None
        }
    
    # Process metrics
    insight = insights[0]  # Aggregate metrics
    
    impressions = int(insight.get('impressions', 0))
    clicks = int(insight.get('clicks', 0))
    spend = float(insight.get('spend', 0))
    
    # Extract conversions and leads from actions
    conversions = 0
    leads = 0
    if 'actions' in insight:
        for action in insight['actions']:
            if action['action_type'] == 'offsite_conversion':
                conversions += int(action['value'])
            elif action['action_type'] == 'lead':
                leads += int(action['value'])
                conversions += int(action['value'])  # Count leads as conversions too
    
    # Calculate metrics
    cpa = None
    if conversions > 0 and spend > 0:
        cpa = spend / conversions
    
    cpl = None
    if leads > 0 and spend > 0:
        cpl = spend / leads
    
    ctr = None
    if impressions > 0 and clicks > 0:
        ctr = (clicks / impressions) * 100  # As percentage
    
    return {
        "campaign_id": campaign_id,
        "start_date": start_date,
        "end_date": end_date,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "leads": leads,
        "spend": spend,
        "cpa": cpa,
        "cpl": cpl,
        "ctr": ctr
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
