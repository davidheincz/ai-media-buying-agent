"""
Test module for the Facebook Ads Manager application.
"""

import os
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import app, Base, get_db, FacebookAccount, CampaignModel, AdSetModel, PerformanceMetric
from app import initialize_facebook_api, get_ad_account, handle_facebook_error

# Create test database
TEST_DATABASE_URL = "sqlite:///./test_facebook.db"
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
def mock_facebook_api():
    with patch('app.FacebookAdsApi') as mock_api:
        mock_instance = MagicMock()
        mock_api.init.return_value = mock_instance
        yield mock_api

@pytest.fixture
def mock_ad_account():
    with patch('app.AdAccount') as mock_account:
        mock_instance = MagicMock()
        mock_account.return_value = mock_instance
        yield mock_account, mock_instance

@pytest.fixture
def mock_campaign():
    with patch('app.Campaign') as mock_campaign:
        mock_instance = MagicMock()
        mock_campaign.return_value = mock_instance
        yield mock_campaign, mock_instance

@pytest.fixture
def mock_adset():
    with patch('app.AdSet') as mock_adset:
        mock_instance = MagicMock()
        mock_adset.return_value = mock_instance
        yield mock_adset, mock_instance

@pytest.fixture
def sample_facebook_account(setup_database):
    # Create a sample Facebook account for testing
    db = TestingSessionLocal()
    account = FacebookAccount(
        id="test_account_id",
        user_id="test_user_id",
        fb_account_id="act_123456789",
        name="Test Ad Account",
        access_token="test_access_token",
        token_expiry=datetime.utcnow() + timedelta(days=60)
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    db.close()
    return account

@pytest.fixture
def sample_campaign(setup_database, sample_facebook_account):
    # Create a sample campaign for testing
    db = TestingSessionLocal()
    campaign = CampaignModel(
        id="test_campaign_id",
        account_id=sample_facebook_account.id,
        fb_campaign_id="123456789",
        name="Test Campaign",
        objective="CONVERSIONS",
        status="ACTIVE",
        daily_budget=100.0
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    db.close()
    return campaign

@pytest.fixture
def sample_adset(setup_database, sample_campaign):
    # Create a sample ad set for testing
    db = TestingSessionLocal()
    adset = AdSetModel(
        id="test_adset_id",
        campaign_id=sample_campaign.id,
        fb_adset_id="987654321",
        name="Test Ad Set",
        targeting=json.dumps({"age_min": 18, "age_max": 65}),
        budget=50.0,
        status="ACTIVE",
        billing_event="IMPRESSIONS",
        optimization_goal="REACH"
    )
    db.add(adset)
    db.commit()
    db.refresh(adset)
    db.close()
    return adset

# Unit tests for utility functions
def test_initialize_facebook_api(mock_facebook_api):
    """Test Facebook API initialization."""
    initialize_facebook_api("test_token")
    mock_facebook_api.init.assert_called_once()

def test_get_ad_account(mock_facebook_api, mock_ad_account):
    """Test getting an ad account."""
    mock_account, mock_instance = mock_ad_account
    result = get_ad_account("test_token", "123456789")
    mock_account.assert_called_once()
    assert result == mock_instance

def test_handle_facebook_error_decorator():
    """Test the error handling decorator."""
    @handle_facebook_error
    def test_function():
        return "success"
    
    result = test_function()
    assert result == "success"

# Integration tests for API endpoints
def test_create_facebook_account(setup_database):
    """Test creating a Facebook account."""
    response = client.post(
        "/accounts/",
        json={
            "user_id": "test_user",
            "fb_account_id": "act_123456789",
            "name": "Test Account",
            "access_token": "test_token"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test_user"
    assert data["fb_account_id"] == "act_123456789"
    assert data["name"] == "Test Account"

def test_get_facebook_accounts(setup_database, sample_facebook_account):
    """Test getting Facebook accounts for a user."""
    response = client.get("/accounts/", params={"user_id": sample_facebook_account.user_id})
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == sample_facebook_account.id
    assert data[0]["fb_account_id"] == sample_facebook_account.fb_account_id

def test_get_facebook_account(setup_database, sample_facebook_account):
    """Test getting a specific Facebook account."""
    response = client.get(f"/accounts/{sample_facebook_account.id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_facebook_account.id
    assert data["fb_account_id"] == sample_facebook_account.fb_account_id

def test_create_campaign(setup_database, sample_facebook_account, mock_ad_account):
    """Test creating a campaign."""
    mock_account, mock_instance = mock_ad_account
    mock_instance.create_campaign.return_value = {"id": "new_campaign_id"}
    
    response = client.post(
        f"/accounts/{sample_facebook_account.id}/campaigns/",
        json={
            "name": "New Test Campaign",
            "objective": "CONVERSIONS",
            "status": "PAUSED",
            "daily_budget": 100.0
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Test Campaign"
    assert data["objective"] == "CONVERSIONS"
    assert data["status"] == "PAUSED"
    assert data["daily_budget"] == 100.0
    assert data["fb_campaign_id"] == "new_campaign_id"

def test_get_campaigns(setup_database, sample_facebook_account, sample_campaign, mock_ad_account):
    """Test getting campaigns for an account."""
    mock_account, mock_instance = mock_ad_account
    mock_instance.get_campaigns.return_value = [
        {
            "id": sample_campaign.fb_campaign_id,
            "name": sample_campaign.name,
            "objective": sample_campaign.objective,
            "status": sample_campaign.status,
            "daily_budget": int(sample_campaign.daily_budget * 100)
        }
    ]
    
    response = client.get(f"/accounts/{sample_facebook_account.id}/campaigns/")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == sample_campaign.id
    assert data[0]["name"] == sample_campaign.name
    assert data[0]["objective"] == sample_campaign.objective

def test_update_campaign_status(setup_database, sample_campaign, mock_campaign):
    """Test updating a campaign's status."""
    mock_campaign_class, mock_campaign_instance = mock_campaign
    
    response = client.put(
        f"/campaigns/{sample_campaign.id}/status",
        params={"status": "PAUSED"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Campaign status updated to PAUSED"
    assert data["campaign_id"] == sample_campaign.id
    
    # Verify database update
    db = TestingSessionLocal()
    updated_campaign = db.query(CampaignModel).filter(CampaignModel.id == sample_campaign.id).first()
    assert updated_campaign.status == "PAUSED"
    db.close()

def test_create_ad_set(setup_database, sample_campaign, mock_ad_account):
    """Test creating an ad set."""
    mock_account, mock_instance = mock_ad_account
    mock_instance.create_ad_set.return_value = {"id": "new_adset_id"}
    
    response = client.post(
        f"/campaigns/{sample_campaign.id}/adsets/",
        json={
            "name": "New Test Ad Set",
            "targeting": {"age_min": 18, "age_max": 65},
            "budget": 50.0,
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "REACH",
            "status": "PAUSED"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Test Ad Set"
    assert data["targeting"] == {"age_min": 18, "age_max": 65}
    assert data["budget"] == 50.0
    assert data["status"] == "PAUSED"
    assert data["fb_adset_id"] == "new_adset_id"

def test_get_ad_sets(setup_database, sample_campaign, sample_adset, mock_campaign):
    """Test getting ad sets for a campaign."""
    mock_campaign_class, mock_campaign_instance = mock_campaign
    mock_campaign_instance.get_ad_sets.return_value = [
        {
            "id": sample_adset.fb_adset_id,
            "name": sample_adset.name,
            "status": sample_adset.status,
            "targeting": json.loads(sample_adset.targeting),
            "daily_budget": int(sample_adset.budget * 100)
        }
    ]
    
    response = client.get(f"/campaigns/{sample_campaign.id}/adsets/")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == sample_adset.id
    assert data[0]["name"] == sample_adset.name
    assert data[0]["status"] == sample_adset.status

def test_update_ad_set_status(setup_database, sample_adset, mock_adset):
    """Test updating an ad set's status."""
    mock_adset_class, mock_adset_instance = mock_adset
    
    response = client.put(
        f"/adsets/{sample_adset.id}/status",
        params={"status": "PAUSED"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Ad set status updated to PAUSED"
    assert data["adset_id"] == sample_adset.id
    
    # Verify database update
    db = TestingSessionLocal()
    updated_adset = db.query(AdSetModel).filter(AdSetModel.id == sample_adset.id).first()
    assert updated_adset.status == "PAUSED"
    db.close()

def test_get_ad_set_metrics(setup_database, sample_adset, mock_adset):
    """Test getting performance metrics for an ad set."""
    mock_adset_class, mock_adset_instance = mock_adset
    mock_adset_instance.get_insights.return_value = [
        {
            "date_start": "2025-04-01",
            "impressions": "1000",
            "clicks": "50",
            "spend": "25.50",
            "actions": [
                {"action_type": "offsite_conversion", "value": "10"},
                {"action_type": "lead", "value": "5"}
            ]
        }
    ]
    
    response = client.get(
        f"/adsets/{sample_adset.id}/metrics",
        params={"start_date": "2025-04-01", "end_date": "2025-04-03"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["impressions"] == 1000
    assert data[0]["clicks"] == 50
    assert data[0]["spend"] == 25.5
    assert data[0]["conversions"] == 10
    assert data[0]["cpa"] == 25.5 / 10  # spend / conversions

def test_get_campaign_metrics(setup_database, sample_campaign, mock_campaign):
    """Test getting aggregated metrics for a campaign."""
    mock_campaign_class, mock_campaign_instance = mock_campaign
    mock_campaign_instance.get_insights.return_value = [
        {
            "impressions": "5000",
            "clicks": "250",
            "spend": "125.75",
            "actions": [
                {"action_type": "offsite_conversion", "value": "30"},
                {"action_type": "lead", "value": "15"}
            ]
        }
    ]
    
    response = client.get(
        f"/campaigns/{sample_campaign.id}/metrics",
        params={"start_date": "2025-04-01", "end_date": "2025-04-03"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["impressions"] == 5000
    assert data["clicks"] == 250
    assert data["spend"] == 125.75
    assert data["conversions"] == 45  # offsite_conversion + lead
    assert data["leads"] == 15
    assert data["cpa"] == 125.75 / 45  # spend / conversions
    assert data["cpl"] == 125.75 / 15  # spend / leads
    assert data["ctr"] == (250 / 5000) * 100  # (clicks / impressions) * 100

if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
