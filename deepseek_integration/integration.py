"""
Main Integration Module for DeepSeek AI Media Buying Agent

This module integrates the DeepSeek client, API connection, and knowledge processor
with the existing application to create a complete AI media buying agent.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from .deepseek_client import DeepSeekAIClient, DeepSeekAPIError
from .api_connection import DeepSeekAPIConnection
from .knowledge_processor import KnowledgeProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('deepseek_integration')

class AIMediaBuyingAgent:
    """AI-driven media buying agent that connects DeepSeek AI with Facebook Ads."""
    
    def __init__(
        self, 
        deepseek_api_key: Optional[str] = None,
        knowledge_base_path: Optional[str] = None,
        facebook_ads_manager: Optional[Any] = None
    ):
        """Initialize the AI media buying agent.
        
        Args:
            deepseek_api_key: DeepSeek API key. If None, will try to get from environment variable.
            knowledge_base_path: Path to the knowledge base file. If None, will use default path.
            facebook_ads_manager: FacebookAdsManager instance. If None, will try to import and create one.
        """
        logger.info("Initializing AI Media Buying Agent")
        
        try:
            # Initialize DeepSeek API connection
            self.api_connection = DeepSeekAPIConnection(api_key=deepseek_api_key)
            logger.info("Successfully initialized DeepSeek API connection")
            
            # Initialize knowledge processor
            self.knowledge_processor = KnowledgeProcessor(knowledge_base_path=knowledge_base_path)
            logger.info("Successfully initialized knowledge processor")
            
            # Initialize Facebook Ads manager
            if facebook_ads_manager:
                self.facebook_ads_manager = facebook_ads_manager
            else:
                try:
                    # Try to import FacebookAdsManager
                    from facebook_ads_manager.app import FacebookAdsManager
                    self.facebook_ads_manager = FacebookAdsManager()
                    logger.info("Successfully initialized Facebook Ads manager")
                except ImportError:
                    logger.warning("Could not import FacebookAdsManager. Facebook Ads functionality will be limited.")
                    self.facebook_ads_manager = None
            
            logger.info("AI Media Buying Agent initialization complete")
        except Exception as e:
            logger.error(f"Error initializing AI Media Buying Agent: {str(e)}")
            raise
    
    def process_document(self, document_text: str, document_name: str) -> List[Dict[str, Any]]:
        """Process a document and extract knowledge.
        
        Args:
            document_text: The text content of the document
            document_name: Name of the document
            
        Returns:
            Extracted knowledge items
        """
        logger.info(f"Processing document: {document_name}")
        
        try:
            # Use DeepSeek API connection to process document
            knowledge_items = self.api_connection.process_document(document_text, document_name)
            
            if knowledge_items:
                # Add knowledge items to knowledge base
                added_count = self.knowledge_processor.add_knowledge_items(knowledge_items, document_name)
                logger.info(f"Added {added_count} knowledge items to knowledge base from document: {document_name}")
            else:
                logger.warning(f"No knowledge items extracted from document: {document_name}")
            
            return knowledge_items
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return []
    
    def evaluate_campaign(self, campaign_id: str, ad_account_id: str) -> Dict[str, Any]:
        """Evaluate a campaign and generate recommendations.
        
        Args:
            campaign_id: Facebook campaign ID
            ad_account_id: Facebook ad account ID
            
        Returns:
            Recommendations for the campaign
        """
        logger.info(f"Evaluating campaign {campaign_id} in account {ad_account_id}")
        
        try:
            if not self.facebook_ads_manager:
                logger.error("Facebook Ads manager not initialized")
                return {"error": "Facebook Ads manager not initialized"}
            
            # Get campaign data from Facebook
            campaign_data = self.facebook_ads_manager.get_campaign(ad_account_id, campaign_id)
            
            # Get performance metrics
            performance_metrics = self.facebook_ads_manager.get_campaign_performance(ad_account_id, campaign_id)
            
            # Get relevant knowledge base rules
            knowledge_base_rules = self.knowledge_processor.get_rules_for_campaign_type(
                campaign_data.get("objective", "")
            )
            
            # Generate decision using DeepSeek AI
            decision = self.api_connection.evaluate_campaign(
                campaign_data=campaign_data,
                performance_metrics=performance_metrics,
                knowledge_base_rules=knowledge_base_rules
            )
            
            logger.info(f"Successfully evaluated campaign {campaign_id}")
            return decision
        except Exception as e:
            logger.error(f"Error evaluating campaign: {str(e)}")
            return {"error": f"Error evaluating campaign: {str(e)}"}
    
    def execute_decision(
        self, 
        campaign_id: str, 
        ad_account_id: str, 
        decision: Dict[str, Any], 
        auto_apply: bool = False
    ) -> Dict[str, Any]:
        """Execute a decision for a campaign.
        
        Args:
            campaign_id: Facebook campaign ID
            ad_account_id: Facebook ad account ID
            decision: Decision structure
            auto_apply: Whether to automatically apply changes
            
        Returns:
            Results of execution
        """
        logger.info(f"Executing decision for campaign {campaign_id} in account {ad_account_id}")
        
        if not auto_apply:
            logger.info("Auto-apply is disabled. Returning decision for manual review.")
            return {"status": "pending_approval", "decision": decision}
        
        try:
            if not self.facebook_ads_manager:
                logger.error("Facebook Ads manager not initialized")
                return {"error": "Facebook Ads manager not initialized"}
            
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
            
            logger.info(f"Executed decision for campaign {campaign_id} with {len(results['applied_changes'])} changes and {len(results['errors'])} errors")
            return results
        except Exception as e:
            logger.error(f"Error executing decision: {str(e)}")
            return {"error": f"Error executing decision: {str(e)}"}
    
    def get_account_optimization(self, ad_account_id: str) -> Dict[str, Any]:
        """Get optimization suggestions for an entire ad account.
        
        Args:
            ad_account_id: Facebook ad account ID
            
        Returns:
            Optimization suggestions for the account
        """
        logger.info(f"Getting optimization suggestions for account {ad_account_id}")
        
        try:
            if not self.facebook_ads_manager:
                logger.error("Facebook Ads manager not initialized")
                return {"error": "Facebook Ads manager not initialized"}
            
            # Get account data
            account_data = self.facebook_ads_manager.get_account(ad_account_id)
            
            # Get all campaigns in the account
            campaigns = self.facebook_ads_manager.get_campaigns(ad_account_id)
            campaign_ids = [campaign["id"] for campaign in campaigns]
            
            # Get performance data for all campaigns
            performance_data = self.facebook_ads_manager.get_account_performance(ad_account_id)
            
            # Get KPI targets for the account
            kpi_targets = account_data.get("kpi_targets", {})
            
            # Get all knowledge base rules
            knowledge_base_rules = self.knowledge_processor.get_knowledge_items()
            
            # Get optimization suggestions
            suggestions = self.api_connection.get_optimization_suggestions(
                ad_account_id=ad_account_id,
                campaign_ids=campaign_ids,
                performance_data=performance_data,
                kpi_targets=kpi_targets,
                knowledge_base_rules=knowledge_base_rules
            )
            
            logger.info(f"Successfully generated optimization suggestions for account {ad_account_id}")
            return suggestions
        except Exception as e:
            logger.error(f"Error getting account optimization: {str(e)}")
            return {"error": f"Error getting account optimization: {str(e)}"}
    
    def analyze_ad_creative(self, creative_text: str, creative_image_url: Optional[str] = None) -> Dict[str, Any]:
        """Analyze ad creative and provide improvement suggestions.
        
        Args:
            creative_text: The text content of the ad
            creative_image_url: Optional URL to the ad image
            
        Returns:
            Analysis and suggestions for the ad creative
        """
        logger.info("Analyzing ad creative")
        
        try:
            # Use DeepSeek API connection to analyze ad creative
            analysis = self.api_connection.analyze_ad_creative(creative_text, creative_image_url)
            
            logger.info("Successfully analyzed ad creative")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing ad creative: {str(e)}")
            return {"error": f"Error analyzing ad creative: {str(e)}"}
    
    def generate_ad_creative(
        self, 
        product_info: Dict[str, Any], 
        target_audience: Dict[str, Any],
        campaign_objective: str,
        brand_guidelines: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate ad creative based on product information and target audience.
        
        Args:
            product_info: Information about the product
            target_audience: Information about the target audience
            campaign_objective: Objective of the campaign
            brand_guidelines: Optional brand guidelines
            
        Returns:
            Generated ad creative
        """
        logger.info(f"Generating ad creative for campaign objective: {campaign_objective}")
        
        try:
            # Use DeepSeek API connection to generate ad creative
            creative = self.api_connection.generate_ad_creative(
                product_info=product_info,
                target_audience=target_audience,
                campaign_objective=campaign_objective,
                brand_guidelines=brand_guidelines
            )
            
            logger.info("Successfully generated ad creative")
            return creative
        except Exception as e:
            logger.error(f"Error generating ad creative: {str(e)}")
            return {"error": f"Error generating ad creative: {str(e)}"}
    
    def get_knowledge_base_summary(self) -> Dict[str, Any]:
        """Get a summary of the knowledge base.
        
        Returns:
            Summary of the knowledge base
        """
        logger.info("Getting knowledge base summary")
        
        try:
            # Use knowledge processor to get summary
            summary = self.knowledge_processor.get_knowledge_base_summary()
            
            logger.info("Successfully retrieved knowledge base summary")
            return summary
        except Exception as e:
            logger.error(f"Error getting knowledge base summary: {str(e)}")
            return {"error": f"Error getting knowledge base summary: {str(e)}"}
    
    def search_knowledge_base(self, query: str) -> List[Dict[str, Any]]:
        """Search the knowledge base for items matching the query.
        
        Args:
            query: Search query
            
        Returns:
            List of matching knowledge items
        """
        logger.info(f"Searching knowledge base for: {query}")
        
        try:
            # Use knowledge processor to search
            items = self.knowledge_processor.search_knowledge_base(query)
            
            logger.info(f"Found {len(items)} items matching query: {query}")
            return items
        except Exception as e:
            logger.error(f"Error searching knowledge base: {str(e)}")
            return []
