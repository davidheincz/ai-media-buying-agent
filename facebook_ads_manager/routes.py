import os
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime

from models import db, Campaign, AdSet, Ad, AdPerformance, Document, KnowledgeItem, FacebookAccount
from facebook_ads_manager.enhanced_manager import MetaMarketingAPIClient
from facebook_ads_manager.autonomous_engine import AutonomousDecisionEngine
from deepseek_integration.integration import AIMediaBuyingAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Blueprint
meta_api_bp = Blueprint('meta_api', __name__)

# Initialize Meta API client and Autonomous Engine
def get_meta_api_client():
    """Get or create Meta API client for the current user"""
    if not current_user or not current_user.is_authenticated:
        return None
        
    # Get user's Facebook accounts
    fb_accounts = FacebookAccount.query.filter_by(user_id=current_user.id).all()
    if not fb_accounts:
        return None
        
    # Use the first account's credentials
    account = fb_accounts[0]
    
    # Create Meta API client
    client = MetaMarketingAPIClient(
        access_token=account.access_token,
        ad_account_id=account.account_id,
        app_id=os.environ.get('FACEBOOK_APP_ID'),
        app_secret=os.environ.get('FACEBOOK_APP_SECRET')
    )
    
    return client

def get_autonomous_engine():
    """Get or create Autonomous Decision Engine for the current user"""
    client = get_meta_api_client()
    if not client:
        return None
        
    # Get AI Media Buying Agent for knowledge base
    ai_agent = get_ai_agent()
    
    # Create Autonomous Engine
    engine = AutonomousDecisionEngine(
        meta_api_client=client,
        knowledge_base=ai_agent.knowledge_processor if ai_agent else None
    )
    
    return engine

def get_ai_agent():
    """Get or create AI Media Buying Agent for the current user"""
    if not current_user or not current_user.is_authenticated:
        return None
        
    # Create AI Media Buying Agent
    agent = AIMediaBuyingAgent(
        deepseek_api_key=os.environ.get('DEEPSEEK_API_KEY')
    )
    
    return agent

# Routes for Meta API integration
@meta_api_bp.route('/connect_facebook')
@login_required
def connect_facebook():
    """Connect to Facebook Ads"""
    # Check if user already has Facebook accounts
    fb_accounts = FacebookAccount.query.filter_by(user_id=current_user.id).all()
    
    return render_template('connect_facebook.html', accounts=fb_accounts)

@meta_api_bp.route('/facebook_callback')
@login_required
def facebook_callback():
    """Handle Facebook OAuth callback"""
    # Get authorization code from query parameters
    code = request.args.get('code')
    if not code:
        flash('Failed to connect to Facebook: No authorization code received', 'danger')
        return redirect(url_for('meta_api.connect_facebook'))
    
    # Exchange code for access token
    client = MetaMarketingAPIClient(
        app_id=os.environ.get('FACEBOOK_APP_ID'),
        app_secret=os.environ.get('FACEBOOK_APP_SECRET')
    )
    
    try:
        # Exchange code for access token
        token_data = client.exchange_code_for_token(code)
        if not token_data or 'access_token' not in token_data:
            flash('Failed to connect to Facebook: Could not obtain access token', 'danger')
            return redirect(url_for('meta_api.connect_facebook'))
            
        # Get user's ad accounts
        ad_accounts = client.get_ad_accounts(token_data['access_token'])
        if not ad_accounts:
            flash('No ad accounts found for this Facebook user', 'warning')
            return redirect(url_for('meta_api.connect_facebook'))
            
        # Save each ad account
        for account in ad_accounts:
            # Check if account already exists
            existing_account = FacebookAccount.query.filter_by(
                account_id=account['id'],
                user_id=current_user.id
            ).first()
            
            if existing_account:
                # Update existing account
                existing_account.access_token = token_data['access_token']
                existing_account.token_expires_at = datetime.now() + datetime.timedelta(seconds=token_data.get('expires_in', 3600))
                existing_account.name = account.get('name', 'Unknown')
                db.session.commit()
            else:
                # Create new account
                new_account = FacebookAccount(
                    user_id=current_user.id,
                    account_id=account['id'],
                    name=account.get('name', 'Unknown'),
                    access_token=token_data['access_token'],
                    token_expires_at=datetime.now() + datetime.timedelta(seconds=token_data.get('expires_in', 3600))
                )
                db.session.add(new_account)
                db.session.commit()
                
        flash(f'Successfully connected {len(ad_accounts)} Facebook ad accounts', 'success')
        return redirect(url_for('meta_api.accounts'))
        
    except Exception as e:
        logger.error(f"Error connecting to Facebook: {str(e)}")
        flash(f'Error connecting to Facebook: {str(e)}', 'danger')
        return redirect(url_for('meta_api.connect_facebook'))

@meta_api_bp.route('/accounts')
@login_required
def accounts():
    """View and manage Facebook ad accounts"""
    # Get user's Facebook accounts
    fb_accounts = FacebookAccount.query.filter_by(user_id=current_user.id).all()
    
    # Get performance data for each account
    account_data = []
    for account in fb_accounts:
        # Create Meta API client
        client = MetaMarketingAPIClient(
            access_token=account.access_token,
            ad_account_id=account.account_id,
            app_id=os.environ.get('FACEBOOK_APP_ID'),
            app_secret=os.environ.get('FACEBOOK_APP_SECRET')
        )
        
        # Get account insights
        insights = client.get_account_insights(account.account_id)
        
        account_data.append({
            'account': account,
            'insights': insights
        })
    
    return render_template('accounts.html', account_data=account_data)

@meta_api_bp.route('/campaigns')
@login_required
def campaigns():
    """View and manage Facebook ad campaigns"""
    # Get Meta API client
    client = get_meta_api_client()
    if not client:
        flash('Please connect to Facebook Ads first', 'warning')
        return redirect(url_for('meta_api.connect_facebook'))
    
    # Get account ID
    account_id = request.args.get('account_id')
    if not account_id:
        # Get first account
        fb_account = FacebookAccount.query.filter_by(user_id=current_user.id).first()
        if fb_account:
            account_id = fb_account.account_id
        else:
            flash('No Facebook ad accounts found', 'warning')
            return redirect(url_for('meta_api.connect_facebook'))
    
    # Get campaigns
    campaigns = client.get_campaigns_by_account(account_id)
    
    # Get insights for each campaign
    campaign_data = []
    for campaign in campaigns:
        # Get campaign insights
        insights = client.get_campaign_insights(campaign['id'])
        
        # Get campaign from database or create if not exists
        db_campaign = Campaign.query.filter_by(
            campaign_id=campaign['id'],
            user_id=current_user.id
        ).first()
        
        if not db_campaign:
            db_campaign = Campaign(
                user_id=current_user.id,
                campaign_id=campaign['id'],
                name=campaign.get('name', 'Unknown'),
                status=campaign.get('status', 'UNKNOWN'),
                objective=campaign.get('objective', 'UNKNOWN')
            )
            db.session.add(db_campaign)
            db.session.commit()
        
        campaign_data.append({
            'campaign': campaign,
            'insights': insights,
            'db_campaign': db_campaign
        })
    
    return render_template('campaigns.html', campaign_data=campaign_data, account_id=account_id)

@meta_api_bp.route('/campaign/<campaign_id>')
@login_required
def campaign_details(campaign_id):
    """View campaign details"""
    # Get Meta API client
    client = get_meta_api_client()
    if not client:
        flash('Please connect to Facebook Ads first', 'warning')
        return redirect(url_for('meta_api.connect_facebook'))
    
    # Get campaign
    campaign = client.get_campaign(campaign_id)
    if not campaign:
        flash('Campaign not found', 'danger')
        return redirect(url_for('meta_api.campaigns'))
    
    # Get campaign insights
    insights = client.get_campaign_insights(campaign_id)
    
    # Get ad sets
    ad_sets = client.get_ad_sets_by_campaign(campaign_id)
    
    # Get ads
    ads = client.get_ads_by_campaign(campaign_id)
    
    return render_template(
        'campaign_details.html',
        campaign=campaign,
        insights=insights,
        ad_sets=ad_sets,
        ads=ads
    )

@meta_api_bp.route('/evaluate_campaign/<campaign_id>')
@login_required
def evaluate_campaign(campaign_id):
    """Evaluate campaign with AI"""
    # Get Autonomous Engine
    engine = get_autonomous_engine()
    if not engine:
        flash('Please connect to Facebook Ads first', 'warning')
        return redirect(url_for('meta_api.connect_facebook'))
    
    # Analyze campaign
    analysis = engine.analyze_campaign(campaign_id)
    if 'error' in analysis:
        flash(f'Error analyzing campaign: {analysis["error"]}', 'danger')
        return redirect(url_for('meta_api.campaign_details', campaign_id=campaign_id))
    
    # Store recommendations in session for execution
    if 'recommendations' in analysis:
        session['campaign_recommendations'] = {
            'campaign_id': campaign_id,
            'recommendations': analysis['recommendations'],
            'timestamp': datetime.now().isoformat()
        }
    
    return render_template(
        'campaign_recommendations.html',
        campaign_id=campaign_id,
        campaign=analysis.get('campaign', {}),
        insights=analysis.get('insights', {}),
        recommendations=analysis.get('recommendations', [])
    )

@meta_api_bp.route('/execute_recommendations/<campaign_id>', methods=['POST'])
@login_required
def execute_recommendations(campaign_id):
    """Execute AI recommendations for a campaign"""
    # Get Autonomous Engine
    engine = get_autonomous_engine()
    if not engine:
        flash('Please connect to Facebook Ads first', 'warning')
        return redirect(url_for('meta_api.connect_facebook'))
    
    # Get recommendations from session
    recommendations = session.get('campaign_recommendations', {})
    if not recommendations or recommendations.get('campaign_id') != campaign_id:
        flash('No recommendations found for this campaign', 'warning')
        return redirect(url_for('meta_api.evaluate_campaign', campaign_id=campaign_id))
    
    # Get selected recommendations from form
    selected_recommendations = request.form.getlist('recommendation')
    if not selected_recommendations:
        flash('No recommendations selected', 'warning')
        return redirect(url_for('meta_api.evaluate_campaign', campaign_id=campaign_id))
    
    # Filter recommendations to only include selected ones
    filtered_recommendations = [
        rec for rec in recommendations.get('recommendations', [])
        if rec.get('id') in selected_recommendations
    ]
    
    # Execute recommendations
    result = engine.execute_recommendations(
        campaign_id,
        filtered_recommendations,
        approval_required=False  # Execute immediately
    )
    
    # Clear recommendations from session
    session.pop('campaign_recommendations', None)
    
    if result.get('status') == 'executed':
        flash('Successfully executed recommendations', 'success')
    else:
        flash(f'Error executing recommendations: {result.get("message", "Unknown error")}', 'danger')
    
    return redirect(url_for('meta_api.campaign_details', campaign_id=campaign_id))

@meta_api_bp.route('/optimize_account/<account_id>')
@login_required
def optimize_account(account_id):
    """Optimize all campaigns in an account"""
    # Get Autonomous Engine
    engine = get_autonomous_engine()
    if not engine:
        flash('Please connect to Facebook Ads first', 'warning')
        return redirect(url_for('meta_api.connect_facebook'))
    
    # Optimize account
    result = engine.optimize_account(account_id, approval_required=True)
    
    # Store optimization results in session
    session['account_optimization'] = result
    
    return render_template(
        'account_optimization.html',
        account_id=account_id,
        optimization_results=result.get('optimization_results', [])
    )

@meta_api_bp.route('/execute_account_optimization/<account_id>', methods=['POST'])
@login_required
def execute_account_optimization(account_id):
    """Execute account optimization recommendations"""
    # Get Autonomous Engine
    engine = get_autonomous_engine()
    if not engine:
        flash('Please connect to Facebook Ads first', 'warning')
        return redirect(url_for('meta_api.connect_facebook'))
    
    # Get optimization results from session
    optimization = session.get('account_optimization', {})
    if not optimization or optimization.get('account_id') != account_id:
        flash('No optimization results found for this account', 'warning')
        return redirect(url_for('meta_api.optimize_account', account_id=account_id))
    
    # Get selected campaigns from form
    selected_campaigns = request.form.getlist('campaign')
    if not selected_campaigns:
        flash('No campaigns selected', 'warning')
        return redirect(url_for('meta_api.optimize_account', account_id=account_id))
    
    # Execute optimization for each selected campaign
    success_count = 0
    for result in optimization.get('optimization_results', []):
        if result.get('campaign_id') in selected_campaigns:
            # Execute recommendations
            execution = engine.execute_recommendations(
                result.get('campaign_id'),
                result.get('analysis', {}).get('recommendations', []),
                approval_required=False  # Execute immediately
            )
            
            if execution.get('status') == 'executed':
                success_count += 1
    
    # Clear optimization from session
    session.pop('account_optimization', None)
    
    flash(f'Successfully executed optimization for {success_count} campaigns', 'success')
    return redirect(url_for('meta_api.accounts'))

@meta_api_bp.route('/create_campaign', methods=['GET', 'POST'])
@login_required
def create_campaign():
    """Create a new Facebook ad campaign"""
    # Get Meta API client
    client = get_meta_api_client()
    if not client:
        flash('Please connect to Facebook Ads first', 'warning')
        return redirect(url_for('meta_api.connect_facebook'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        objective = request.form.get('objective')
        status = request.form.get('status', 'PAUSED')
        daily_budget = request.form.get('daily_budget')
        
        if not name or not objective or not daily_budget:
            flash('Please fill out all required fields', 'danger')
            return redirect(url_for('meta_api.create_campaign'))
        
        # Create campaign
        result = client.create_campaign(
            name=name,
            objective=objective,
            status=status,
            daily_budget=float(daily_budget)
        )
        
        if result and 'id' in result:
            flash(f'Successfully created campaign: {name}', 'success')
            
            # Create campaign in database
            db_campaign = Campaign(
                user_id=current_user.id,
                campaign_id=result['id'],
                name=name,
                status=status,
                objective=objective
            )
            db.session.add(db_campaign)
            db.session.commit()
            
            return redirect(url_for('meta_api.campaign_details', campaign_id=result['id']))
        else:
            flash(f'Error creating campaign: {result.get("error", "Unknown error")}', 'danger')
            return redirect(url_for('meta_api.create_campaign'))
    
    # GET request - show form
    return render_template('create_campaign.html')

@meta_api_bp.route('/create_ad_set/<campaign_id>', methods=['GET', 'POST'])
@login_required
def create_ad_set(campaign_id):
    """Create a new ad set in a campaign"""
    # Get Meta API client
    client = get_meta_api_client()
    if not client:
        flash('Please connect to Facebook Ads first', 'warning')
        return redirect(url_for('meta_api.connect_facebook'))
    
    # Get campaign
    campaign = client.get_campaign(campaign_id)
    if not campaign:
        flash('Campaign not found', 'danger')
        return redirect(url_for('meta_api.campaigns'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        status = request.form.get('status', 'PAUSED')
        daily_budget = request.form.get('daily_budget')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
        # Targeting data
        countries = request.form.get('countries', '').split(',')
        age_min = request.form.get('age_min')
        age_max = request.form.get('age_max')
        genders = request.form.getlist('genders')
        
        if not name or not daily_budget or not countries:
            flash('Please fill out all required fields', 'danger')
            return redirect(url_for('meta_api.create_ad_set', campaign_id=campaign_id))
        
        # Create targeting spec
        targeting = {
            'geo_locations': {
                'countries': [c.strip() for c in countries if c.strip()]
            }
        }
        
        if age_min:
            targeting['age_min'] = int(age_min)
        if age_max:
            targeting['age_max'] = int(age_max)
        if genders:
            targeting['genders'] = [int(g) for g in genders]
        
        # Create ad set
        result = client.create_ad_set(
            name=name,
            campaign_id=campaign_id,
            status=status,
            daily_budget=float(daily_budget),
            targeting=targeting,
            start_time=start_time,
            end_time=end_time
        )
        
        if result and 'id' in result:
            flash(f'Successfully created ad set: {name}', 'success')
            return redirect(url_for('meta_api.campaign_details', campaign_id=campaign_id))
        else:
            flash(f'Error creating ad set: {result.get("error", "Unknown error")}', 'danger')
            return redirect(url_for('meta_api.create_ad_set', campaign_id=campaign_id))
    
    # GET request - show form
    return render_template('create_ad_set.html', campaign=campaign)

@meta_api_bp.route('/create_ad/<ad_set_id>', methods=['GET', 'POST'])
@login_required
def create_ad(ad_set_id):
    """Create a new ad in an ad set"""
    # Get Meta API client
    client = get_meta_api_client()
    if not client:
        flash('Please connect to Facebook Ads first', 'warning')
        return redirect(url_for('meta_api.connect_facebook'))
    
    # Get ad set
    ad_set = client.get_ad_set(ad_set_id)
    if not ad_set:
        flash('Ad set not found', 'danger')
        return redirect(url_for('meta_api.campaigns'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        status = request.form.get('status', 'PAUSED')
        
        # Creative data
        headline = request.form.get('headline')
        body = request.form.get('body')
        website_url = request.form.get('website_url')
        
        if not name or not headline or not body or not website_url:
            flash('Please fill out all required fields', 'danger')
            return redirect(url_for('meta_api.create_ad', ad_set_id=ad_set_id))
        
        # Handle image upload
        image_hash = None
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file.filename:
                # Upload image to Facebook
                image_result = client.upload_image(image_file)
                if image_result and 'hash' in image_result:
                    image_hash = image_result['hash']
                else:
                    flash(f'Error uploading image: {image_result.get("error", "Unknown error")}', 'danger')
                    return redirect(url_for('meta_api.create_ad', ad_set_id=ad_set_id))
        
        # Create ad creative
        creative_result = client.create_ad_creative(
            name=f"{name} Creative",
            headline=headline,
            body=body,
            website_url=website_url,
            image_hash=image_hash
        )
        
        if not creative_result or 'id' not in creative_result:
            flash(f'Error creating ad creative: {creative_result.get("error", "Unknown error")}', 'danger')
            return redirect(url_for('meta_api.create_ad', ad_set_id=ad_set_id))
        
        # Create ad
        result = client.create_ad(
            name=name,
            ad_set_id=ad_set_id,
            status=status,
            creative_id=creative_result['id']
        )
        
        if result and 'id' in result:
            flash(f'Successfully created ad: {name}', 'success')
            
            # Get campaign ID
            campaign_id = ad_set.get('campaign_id')
            
            return redirect(url_for('meta_api.campaign_details', campaign_id=campaign_id))
        else:
            flash(f'Error creating ad: {result.get("error", "Unknown error")}', 'danger')
            return redirect(url_for('meta_api.create_ad', ad_set_id=ad_set_id))
    
    # GET request - show form
    return render_template('create_ad.html', ad_set=ad_set)

# Register blueprint
def register_meta_api_blueprint(app):
    app.register_blueprint(meta_api_bp, url_prefix='/meta_api')
