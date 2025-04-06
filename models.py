from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'  # Change from default "user" to "users"
    id = db.Column(db.Integer, primary_key=True)
    #id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    accounts = db.relationship('AdAccount', backref='user', lazy=True)
    documents = db.relationship('Document', backref='user', lazy=True)

class AdAccount(db.Model):
    __tablename__ = 'ad_account'  # Added explicit table name
    id = db.Column(db.Integer, primary_key=True)
    facebook_account_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    access_token = db.Column(db.String(500), nullable=False)
    target_cpa = db.Column(db.Float, nullable=True)
    target_cpl = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    campaigns = db.relationship('Campaign', backref='account', lazy=True)

class Campaign(db.Model):
    __tablename__ = 'campaign'  # Added explicit table name
    id = db.Column(db.Integer, primary_key=True)
    facebook_campaign_id = db.Column(db.String(100), nullable=False)
    # Add campaign_id as an alias to match what routes.py expects
    campaign_id = db.Column(db.String(100), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    objective = db.Column(db.String(50), nullable=True)  # Added objective field
    daily_budget = db.Column(db.Float, nullable=True)
    lifetime_budget = db.Column(db.Float, nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey('ad_account.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    ad_sets = db.relationship('AdSet', backref='campaign', lazy=True)
    metrics = db.relationship('CampaignMetric', backref='campaign', lazy=True)

class AdSet(db.Model):
    __tablename__ = 'ad_set'  # Added explicit table name
    id = db.Column(db.Integer, primary_key=True)
    facebook_adset_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    daily_budget = db.Column(db.Float, nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ad(db.Model):
    __tablename__ = 'ad'  # Added explicit table name
    id = db.Column(db.Integer, primary_key=True)
    facebook_ad_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    headline = db.Column(db.String(100), nullable=True)
    primary_text = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(200), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    call_to_action = db.Column(db.String(50), nullable=True)
    adset_id = db.Column(db.Integer, db.ForeignKey('ad_set.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    performance = db.relationship('AdPerformance', backref='ad', lazy=True)

# Added missing AdPerformance model
class AdPerformance(db.Model):
    __tablename__ = 'ad_performance'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    impressions = db.Column(db.Integer, nullable=True)
    clicks = db.Column(db.Integer, nullable=True)
    spend = db.Column(db.Float, nullable=True)
    conversions = db.Column(db.Integer, nullable=True)
    ctr = db.Column(db.Float, nullable=True)  # Click-through rate
    cpc = db.Column(db.Float, nullable=True)  # Cost per click
    cpm = db.Column(db.Float, nullable=True)  # Cost per thousand impressions
    ad_id = db.Column(db.Integer, db.ForeignKey('ad.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CampaignMetric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    impressions = db.Column(db.Integer, nullable=True)
    clicks = db.Column(db.Integer, nullable=True)
    spend = db.Column(db.Float, nullable=True)
    conversions = db.Column(db.Integer, nullable=True)
    cpa = db.Column(db.Float, nullable=True)
    cpl = db.Column(db.Float, nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    knowledge_items = db.relationship('KnowledgeItem', backref='document', lazy=True)

class KnowledgeItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Decision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)  # budget_increase, budget_decrease, pause, activate
    entity_type = db.Column(db.String(50), nullable=False)  # campaign, adset
    entity_id = db.Column(db.String(100), nullable=False)
    entity_name = db.Column(db.String(200), nullable=False)
    current_value = db.Column(db.Float, nullable=True)
    new_value = db.Column(db.Float, nullable=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # pending, approved, rejected, executed
    account_id = db.Column(db.Integer, db.ForeignKey('ad_account.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FacebookAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=True)
    access_token = db.Column(db.Text, nullable=False)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('facebook_accounts', lazy=True))
