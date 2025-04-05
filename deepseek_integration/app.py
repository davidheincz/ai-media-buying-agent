import os
from .deepseek_client import DeepSeekAIClient
from document_processor.knowledge_base import KnowledgeBase
from facebook_ads_manager.app import FacebookAdsManager

class AIMediaBuyingAgent:
    """AI-driven media buying agent that connects DeepSeek AI with Facebook Ads."""
    
    def __init__(self, deepseek_api_key=None, knowledge_base=None, facebook_ads_manager=None):
        """Initialize the AI media buying agent.
        
        Args:
            deepseek_api_key: DeepSeek API key. If None, will try to get from environment variable.
            knowledge_base: KnowledgeBase instance. If None, will create a new one.
            facebook_ads_manager: FacebookAdsManager instance. If None, will create a new one.
        """
        self.ai_client = DeepSeekAIClient(api_key=deepseek_api_key)
        self.knowledge_base = knowledge_base or KnowledgeBase()
        self.facebook_ads_manager = facebook_ads_manager or FacebookAdsManager()
    
    def process_document(self, document_text, document_name):
        """Process a document and extract knowledge.
        
        Args:
            document_text: The text content of the document
            document_name: Name of the document
            
        Returns:
            Extracted knowledge items
        """
        # Use DeepSeek AI to analyze the document
        analysis = self.ai_client.analyze_document(document_text)
        
        # Extract knowledge items from the analysis
        knowledge_items = self._extract_knowledge_items(analysis, document_name)
        
        # Store knowledge items in the knowledge base
        for item in knowledge_items:
            self.knowledge_base.add_knowledge_item(item)
        
        return knowledge_items
    
    def _extract_knowledge_items(self, analysis, document_name):
        """Extract structured knowledge items from AI analysis.
        
        Args:
            analysis: AI analysis of document
            document_name: Name of the document
            
        Returns:
            List of knowledge items
        """
        # Ask DeepSeek to structure the knowledge items
        prompt = f"""
        Based on the following analysis of a media buying document, please extract structured knowledge items.
        Each knowledge item should have:
        1. A category (budget, targeting, creative, bidding, etc.)
        2. A rule or guideline
        3. Conditions for applying the rule
        4. Expected outcome
        
        Analysis:
        {analysis}
        
        Format each knowledge item as a JSON object.
        """
        
        structured_items = self.ai_client.ask_question(prompt)
        
        # Process the structured items (in a real implementation, this would parse JSON)
        # For simplicity, we'll return a mock list
        return [
            {
                "source": document_name,
                "category": "budget",
                "rule": "Increase budget by 20% when ROAS exceeds target for 3 consecutive days",
                "conditions": "ROAS > target for 3 days",
                "outcome": "Improved scale while maintaining efficiency"
            },
            {
                "source": document_name,
                "category": "targeting",
                "rule": "Exclude users who have not engaged with ads in the past 30 days",
                "conditions": "No engagement in 30 days",
                "outcome": "Improved relevance score and reduced wasted spend"
            }
        ]
    
    def evaluate_campaign(self, campaign_id, ad_account_id):
        """Evaluate a campaign and generate recommendations.
        
        Args:
            campaign_id: Facebook campaign ID
            ad_account_id: Facebook ad account ID
            
        Returns:
            Recommendations for the campaign
        """
        # Get campaign data from Facebook
        campaign_data = self.facebook_ads_manager.get_campaign(ad_account_id, campaign_id)
        
        # Get performance metrics
        performance_metrics = self.facebook_ads_manager.get_campaign_performance(ad_account_id, campaign_id)
        
        # Get relevant knowledge base rules
        knowledge_base_rules = self.knowledge_base.get_rules_for_campaign_type(campaign_data.get("objective"))
        
        # Generate decision using DeepSeek AI
        decision = self.ai_client.generate_decision(
            campaign_data=campaign_data,
            performance_metrics=performance_metrics,
            knowledge_base_rules=knowledge_base_rules
        )
        
        return self._parse_decision(decision)
    
    def _parse_decision(self, decision):
        """Parse the decision from AI into structured actions.
        
        Args:
            decision: Decision text from AI
            
        Returns:
            Structured actions to take
        """
        # In a real implementation, this would parse the decision text
        # For simplicity, we'll return a mock structure
        return {
            "budget_adjustment": {"action": "increase", "amount": 0.2, "reason": "ROAS above target"},
            "ad_set_actions": [
                {"ad_set_id": "123456", "action": "pause", "reason": "High CPA"},
                {"ad_set_id": "789012", "action": "increase_budget", "amount": 0.3, "reason": "Strong performance"}
            ],
            "targeting_recommendations": [
                "Expand to lookalike audiences based on recent purchasers",
                "Exclude users who haven't engaged in 30 days"
            ],
            "creative_recommendations": [
                "Test new ad creative with product benefits highlighted",
                "Add user testimonials to existing ads"
            ]
        }
    
    def execute_decision(self, campaign_id, ad_account_id, decision, auto_apply=False):
        """Execute a decision for a campaign.
        
        Args:
            campaign_id: Facebook campaign ID
            ad_account_id: Facebook ad account ID
            decision: Decision structure
            auto_apply: Whether to automatically apply changes
            
        Returns:
            Results of execution
        """
        if not auto_apply:
            # Just return the decision for manual review
            return {"status": "pending_approval", "decision": decision}
        
        results = {"applied_changes": [], "errors": []}
        
        # Apply budget adjustment if present
        if "budget_adjustment" in decision:
            adjustment = decision["budget_adjustment"]
            try:
                if adjustment["action"] == "increase":
                    self.facebook_ads_manager.increase_campaign_budget(
                        ad_account_id, campaign_id, adjustment["amount"]
                    )
                    results["applied_changes"].append(f"Increased budget by {adjustment['amount']*100}%")
                elif adjustment["action"] == "decrease":
                    self.facebook_ads_manager.decrease_campaign_budget(
                        ad_account_id, campaign_id, adjustment["amount"]
                    )
                    results["applied_changes"].append(f"Decreased budget by {adjustment['amount']*100}%")
            except Exception as e:
                results["errors"].append(f"Failed to adjust budget: {str(e)}")
        
        # Apply ad set actions if present
        if "ad_set_actions" in decision:
            for ad_set_action in decision["ad_set_actions"]:
                try:
                    ad_set_id = ad_set_action["ad_set_id"]
                    action = ad_set_action["action"]
                    
                    if action == "pause":
                        self.facebook_ads_manager.pause_ad_set(ad_account_id, ad_set_id)
                        results["applied_changes"].append(f"Paused ad set {ad_set_id}")
                    elif action == "enable":
                        self.facebook_ads_manager.enable_ad_set(ad_account_id, ad_set_id)
                        results["applied_changes"].append(f"Enabled ad set {ad_set_id}")
                    elif action == "increase_budget" and "amount" in ad_set_action:
                        self.facebook_ads_manager.increase_ad_set_budget(
                            ad_account_id, ad_set_id, ad_set_action["amount"]
                        )
                        results["applied_changes"].append(
                            f"Increased ad set {ad_set_id} budget by {ad_set_action['amount']*100}%"
                        )
                    elif action == "decrease_budget" and "amount" in ad_set_action:
                        self.facebook_ads_manager.decrease_ad_set_budget(
                            ad_account_id, ad_set_id, ad_set_action["amount"]
                        )
                        results["applied_changes"].append(
                            f"Decreased ad set {ad_set_id} budget by {ad_set_action['amount']*100}%"
                        )
                except Exception as e:
                    results["errors"].append(f"Failed to execute action for ad set {ad_set_id}: {str(e)}")
        
        return results
