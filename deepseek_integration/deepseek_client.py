import os
import openai

class DeepSeekAIClient:
    """Client for interacting with DeepSeek AI API."""
    
    def __init__(self, api_key=None):
        """Initialize the DeepSeek AI client.
        
        Args:
            api_key: DeepSeek API key. If None, will try to get from environment variable.
        """
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API key is required. Set DEEPSEEK_API_KEY environment variable or pass api_key parameter.")
        
        # Initialize OpenAI client with DeepSeek base URL
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )
    
    def ask_question(self, question, context=None, system_prompt=None):
        """Ask a question to DeepSeek AI.
        
        Args:
            question: The question to ask
            context: Optional context to provide additional information
            system_prompt: Optional system prompt to guide the model
            
        Returns:
            The response from DeepSeek AI
        """
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({"role": "system", "content": "You are a helpful assistant specialized in media buying."})
        
        # Add context if provided
        if context:
            messages.append({"role": "system", "content": f"Context information: {context}"})
        
        # Add user question
        messages.append({"role": "user", "content": question})
        
        # Call DeepSeek API
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
            stream=False
        )
        
        return response.choices[0].message.content
    
    def analyze_document(self, document_text, question=None):
        """Analyze a document and extract relevant information.
        
        Args:
            document_text: The text content of the document
            question: Optional specific question about the document
            
        Returns:
            Analysis results from DeepSeek AI
        """
        prompt = """
        Please analyze this media buying document and extract key information including:
        1. Budget management rules
        2. Campaign optimization strategies
        3. Target KPI thresholds
        4. Audience targeting recommendations
        5. Ad creative best practices
        
        Document:
        {document_text}
        """.format(document_text=document_text)
        
        if question:
            prompt += f"\n\nSpecific question: {question}"
        
        messages = [
            {"role": "system", "content": "You are a media buying expert who can extract structured information from documents."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=4000,
            stream=False
        )
        
        return response.choices[0].message.content
    
    def generate_decision(self, campaign_data, performance_metrics, knowledge_base_rules):
        """Generate a decision about campaign management based on data and rules.
        
        Args:
            campaign_data: Data about the campaign
            performance_metrics: Performance metrics for the campaign
            knowledge_base_rules: Rules from the knowledge base
            
        Returns:
            Decision recommendation from DeepSeek AI
        """
        prompt = f"""
        Based on the following campaign data, performance metrics, and knowledge base rules,
        please recommend actions to take for this campaign.
        
        Campaign Data:
        {campaign_data}
        
        Performance Metrics:
        {performance_metrics}
        
        Knowledge Base Rules:
        {knowledge_base_rules}
        
        Please provide specific recommendations for:
        1. Budget adjustments (increase, decrease, or maintain)
        2. Ad set status changes (enable, pause, or no change)
        3. Audience targeting modifications
        4. Creative optimizations
        5. Bidding strategy adjustments
        
        For each recommendation, explain your reasoning based on the knowledge base rules.
        """
        
        messages = [
            {"role": "system", "content": "You are a media buying expert who makes data-driven decisions based on established rules."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.2,
            max_tokens=2000,
            stream=False
        )
        
        return response.choices[0].message.content
