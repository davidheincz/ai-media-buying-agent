from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import json
from models import db, User, AdAccount, Campaign, AdSet, CampaignMetric, Document, KnowledgeItem, Decision
import os
from deepseek_integration.integration import AIMediaBuyingAgent
from facebook_ads_manager.routes import register_meta_api_blueprint

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
# Fix for Heroku PostgreSQL URL
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///app.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables
from flask.cli import with_appcontext
import click

@click.command('init-db')
@with_appcontext
def init_db_command():
    db.create_all(checkfirst=True)
    click.echo('Initialized the database.')

app.cli.add_command(init_db_command)

# Then add this to ensure tables are created when the app starts
with app.app_context():
    db.create_all()

# Initialize the AI Media Buying Agent
try:
    ai_agent = AIMediaBuyingAgent(
        deepseek_api_key=os.environ.get('DEEPSEEK_API_KEY')
    )
except Exception as e:
    app.logger.error(f"Error initializing AI Media Buying Agent: {str(e)}")
    ai_agent = None

# Register Meta API Blueprint
register_meta_api_blueprint(app)

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user exists
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists')
            return redirect(url_for('register'))
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    accounts = AdAccount.query.filter_by(user_id=current_user.id).all()
    recent_decisions = Decision.query.join(AdAccount).filter(
        AdAccount.user_id == current_user.id
    ).order_by(Decision.created_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', accounts=accounts, decisions=recent_decisions)

@app.route('/accounts')
@login_required
def accounts():
    accounts = AdAccount.query.filter_by(user_id=current_user.id).all()
    return render_template('accounts.html', accounts=accounts)

@app.route('/connect_facebook', methods=['GET', 'POST'])
@login_required
def connect_facebook():
    if request.method == 'POST':
        account_id = request.form.get('account_id')
        name = request.form.get('name')
        access_token = request.form.get('access_token')
        target_cpa = request.form.get('target_cpa')
        target_cpl = request.form.get('target_cpl')
        
        # Create new account
        new_account = AdAccount(
            facebook_account_id=account_id,
            name=name,
            access_token=access_token,
            target_cpa=float(target_cpa) if target_cpa else None,
            target_cpl=float(target_cpl) if target_cpl else None,
            user_id=current_user.id
        )
        
        db.session.add(new_account)
        db.session.commit()
        
        flash('Facebook Ads account connected successfully!')
        return redirect(url_for('accounts'))
    
    return render_template('connect_facebook.html')

@app.route('/campaigns')
@login_required
def campaigns():
    account_id = request.args.get('account_id')
    if not account_id:
        flash('Please select an account')
        return redirect(url_for('accounts'))
    
    account = AdAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    campaigns = Campaign.query.filter_by(account_id=account.id).all()
    
    return render_template('campaigns.html', account=account, campaigns=campaigns)

@app.route('/evaluate_campaign/<campaign_id>', methods=['GET'])
@login_required
def evaluate_campaign(campaign_id):
    if not ai_agent:
        flash('AI agent not initialized')
        return redirect(url_for('campaigns'))
        
    # Get ad account ID from session or database
    ad_account_id = session.get('ad_account_id', 'act_123456789')  # Default or from session
    
    # Evaluate campaign with AI
    recommendations = ai_agent.evaluate_campaign(campaign_id, ad_account_id)
    
    return render_template(
        'campaign_recommendations.html',
        campaign_id=campaign_id,
        recommendations=recommendations
    )

@app.route('/documents')
@login_required
def documents():
    documents = Document.query.filter_by(user_id=current_user.id).all()
    return render_template('documents.html', documents=documents)

@app.route('/upload_document', methods=['POST'])
@login_required
def upload_document():
    if 'document' not in request.files:
        flash('No file part')
        return redirect(url_for('documents'))
    
    file = request.files['document']
    title = request.form.get('title', 'Untitled Document')
    
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('documents'))
    
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Create document record
        new_document = Document(
            title=title,
            file_path=file_path,
            user_id=current_user.id
        )
        
        db.session.add(new_document)
        db.session.commit()
        
        flash('Document uploaded successfully!')
        
        # In a real implementation, we would process the document here
        # and extract knowledge items
        
    return redirect(url_for('documents'))

@app.route('/process_document', methods=['POST'])
@login_required
def process_document():
    if 'document' not in request.files:
        flash('No document part')
        return redirect(request.url)
    
    file = request.files['document']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
        
    if file and ai_agent:
        # Read document content
        document_text = file.read().decode('utf-8')
        document_name = file.filename
        
        # Process document with AI
        knowledge_items = ai_agent.process_document(document_text, document_name)
        
        # Save document to database
        document = Document(
            title=document_name,
            content=document_text,
            user_id=current_user.id
        )
        db.session.add(document)
        db.session.commit()
        
        flash(f'Document processed successfully. Extracted {len(knowledge_items)} knowledge items.')
    else:
        flash('AI agent not initialized or file error')
        
    return redirect(url_for('documents'))

@app.route('/decisions')
@login_required
def decisions():
    account_id = request.args.get('account_id')
    if not account_id:
        flash('Please select an account')
        return redirect(url_for('accounts'))
    
    account = AdAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    decisions = Decision.query.filter_by(account_id=account.id).order_by(Decision.created_at.desc()).all()
    
    return render_template('decisions.html', account=account, decisions=decisions)

@app.route('/approve_decision/<int:decision_id>', methods=['POST'])
@login_required
def approve_decision(decision_id):
    decision = Decision.query.join(AdAccount).filter(
        Decision.id == decision_id,
        AdAccount.user_id == current_user.id
    ).first_or_404()
    
    decision.status = 'approved'
    db.session.commit()
    
    # In a real implementation, we would execute the decision here
    # by calling the Facebook Ads API
    
    flash('Decision approved and executed!')
    return redirect(url_for('decisions', account_id=decision.account_id))

@app.route('/reject_decision/<int:decision_id>', methods=['POST'])
@login_required
def reject_decision(decision_id):
    decision = Decision.query.join(AdAccount).filter(
        Decision.id == decision_id,
        AdAccount.user_id == current_user.id
    ).first_or_404()
    
    decision.status = 'rejected'
    db.session.commit()
    
    flash('Decision rejected!')
    return redirect(url_for('decisions', account_id=decision.account_id))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
