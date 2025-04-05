from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from document_processor.knowledge_base import KnowledgeBase
from facebook_ads_manager.app import FacebookAdsManager
from deepseek_integration.app import AIMediaBuyingAgent

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')

# Initialize components
knowledge_base = KnowledgeBase()
facebook_ads_manager = FacebookAdsManager()
ai_agent = AIMediaBuyingAgent(
    deepseek_api_key=os.environ.get('DEEPSEEK_API_KEY'),
    knowledge_base=knowledge_base,
    facebook_ads_manager=facebook_ads_manager
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    # Get connected accounts
    accounts = facebook_ads_manager.get_accounts()
    # Get recent decisions
    decisions = ai_agent.get_recent_decisions()
    return render_template('dashboard.html', accounts=accounts, decisions=decisions)

@app.route('/campaigns')
def campaigns():
    account_id = request.args.get('account_id')
    if not account_id:
        flash('Please select an account first')
        return redirect(url_for('dashboard'))
    
    campaigns = facebook_ads_manager.get_campaigns(account_id)
    return render_template('campaigns.html', campaigns=campaigns, account_id=account_id)

@app.route('/documents')
def documents():
    documents = knowledge_base.get_documents()
    return render_template('documents.html', documents=documents)

@app.route('/upload_document', methods=['POST'])
def upload_document():
    if 'document' not in request.files:
        flash('No file part')
        return redirect(url_for('documents'))
    
    file = request.files['document']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('documents'))
    
    if file and file.filename.endswith('.pdf'):
        # Process the document
        document_text = "Sample document text"  # In a real app, extract text from PDF
        document_name = file.filename
        
        # Use AI to analyze document and extract knowledge
        knowledge_items = ai_agent.process_document(document_text, document_name)
        
        flash(f'Document uploaded and processed: {len(knowledge_items)} knowledge items extracted')
    else:
        flash('Only PDF files are allowed')
    
    return redirect(url_for('documents'))

@app.route('/evaluate_campaign', methods=['POST'])
def evaluate_campaign():
    campaign_id = request.form.get('campaign_id')
    ad_account_id = request.form.get('ad_account_id')
    
    if not campaign_id or not ad_account_id:
        return jsonify({'error': 'Missing campaign_id or ad_account_id'}), 400
    
    # Use AI to evaluate campaign and generate recommendations
    recommendations = ai_agent.evaluate_campaign(campaign_id, ad_account_id)
    
    return jsonify(recommendations)

@app.route('/execute_decision', methods=['POST'])
def execute_decision():
    campaign_id = request.form.get('campaign_id')
    ad_account_id = request.form.get('ad_account_id')
    decision = request.json.get('decision')
    auto_apply = request.form.get('auto_apply', 'false').lower() == 'true'
    
    if not campaign_id or not ad_account_id or not decision:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    # Execute the decision
    result = ai_agent.execute_decision(campaign_id, ad_account_id, decision, auto_apply)
    
    return jsonify(result)

@app.route('/connect_facebook', methods=['GET', 'POST'])
def connect_facebook():
    if request.method == 'POST':
        # In a real app, this would handle OAuth flow
        access_token = request.form.get('access_token')
        if access_token:
            facebook_ads_manager.set_access_token(access_token)
            flash('Facebook Ads account connected successfully')
            return redirect(url_for('dashboard'))
    
    return render_template('connect_facebook.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # In a real app, this would create a user account
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            flash('Account created successfully')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # In a real app, this would authenticate the user
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            flash('Logged in successfully')
            return redirect(url_for('dashboard'))
    
    return render_template('login.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
