"""
API Connection Module for DeepSeek Integration

This module provides functions to connect the DeepSeek AI client with
the rest of the application, including document processing and Facebook Ads integration.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union

from .deepseek_client import DeepSeekAIClient, DeepSeekAPIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('deepseek_api_connection')

class DeepSeekAPIConnection:
    """Connection class for integrating DeepSeek AI with the application."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the DeepSeek API connection.
        
        Args:
            api_key: DeepSeek API key. If None, will try to get from environment variable.
        """
        try:
            self.client = DeepSeekAIClient(api_key=api_key)
            logger.info("Successfully initialized DeepSeek API connection")
        except Exception as e:
            logger.error(f"Failed to initialize DeepSeek API connection: {str(e)}")
            raise
    
    def process_document(self, document_text: str, document_name: str) -> List[Dict[str, Any]]:
        """Process a document and extract knowledge items.
        
        Args:
            document_text: The text content of the document
            document_name: Name of the document
            
        Returns:
            List of extracted knowledge items
        """
        logger.info(f"Processing document: {document_name}")
        
        try:
            # Use DeepSeek AI to analyze the document
            analysis = self.client.analyze_document(document_text)
            logger.info(f"Document analysis completed for: {document_name}")
            
            # Extract knowledge items from the analysis
            knowledge_items = self.client.extract_knowledge_items(analysis)
            
            # Add source information to each knowledge item
            for item in knowledge_items:
                item['source'] = document_name
            
            logger.info(f"Extracted {len(knowledge_items)} knowledge items from document: {document_name}")
            return knowledge_items
            
        except DeepSeekAPIError as e:
            logger.error(f"DeepSeek API error while processing document: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return []
    
    def evaluate_campaign(
        self, 
        campaign_data: Dict[str, Any], 
        performance_metrics: Dict[str, Any], 
        knowledge_base_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Evaluate a campaign and generate recommendations.
        
        Args:
            campaign_data: Data about the campaign
            performance_metrics: Performance metrics for the campaign
            knowledge_base_rules: Rules from the knowledge base
            
        Returns:
            Dictionary containing recommendations for the campaign
        """
        campaign_name = campaign_data.get('name', 'Unknown campaign')
        logger.info(f"Evaluating campaign: {campaign_name}")
        
        try:
            # Generate decision using DeepSeek AI
            decision_json = self.client.generate_decision(
                campaign_data=campaign_data,
                performance_metrics=performance_metrics,
                knowledge_base_rules=knowledge_base_rules
            )
            
            # Parse the decision JSON
            try:
                decision = json.loads(decision_json)
                logger.info(f"Successfully generated decision for campaign: {campaign_name}")
                return decision
            except json.JSONDecodeError:
                logger.error(f"Failed to parse decision JSON for campaign: {campaign_name}")
                return {
                    "error": "Failed to parse decision",
                    "raw_response": decision_json
                }
                
        except DeepSeekAPIError as e:
            logger.error(f"DeepSeek API error while evaluating campaign: {str(e)}")
            return {"error": f"DeepSeek API error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error evaluating campaign: {str(e)}")
            return {"error": f"Error: {str(e)}"}
    
    def get_optimization_suggestions(
        self, 
        ad_account_id: str,
        campaign_ids: List[str],
        performance_data: Dict[str, Any],
        kpi_targets: Dict[str, float],
        knowledge_base_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get optimization suggestions for multiple campaigns.
        
        Args:
            ad_account_id: Facebook ad account ID
            campaign_ids: List of Facebook campaign IDs
            performance_data: Performance data for the campaigns
            kpi_targets: Target KPIs for the ad account
            knowledge_base_rules: Rules from the knowledge base
            
        Returns:
            Dictionary containing optimization suggestions for each campaign
        """
        logger.info(f"Getting optimization suggestions for {len(campaign_ids)} campaigns in account {ad_account_id}")
        
        suggestions = {
            "account_id": ad_account_id,
            "campaigns": {},
            "account_level_suggestions": [],
            "errors": []
        }
        
        try:
            # Prepare context for the AI
            context = {
                "ad_account_id": ad_account_id,
                "kpi_targets": kpi_targets,
                "performance_summary": performance_data.get("account_summary", {})
            }
            
            context_json = json.dumps(context, indent=2)
            
            # Get account-level suggestions
            account_prompt = f"""
            Based on the following ad account information and KPI targets,
            provide 3-5 high-level optimization suggestions for the entire account.
            
            Account Information:
            {context_json}
            
            Focus on overall budget allocation, campaign structure, and account-level strategies.
            Provide specific, actionable recommendations based on the performance data and KPI targets.
            """
            
            account_suggestions = self.client.ask_question(
                question=account_prompt,
                temperature=0.3
            )
            
            suggestions["account_level_suggestions"] = account_suggestions.split("\n")
            
            # Evaluate each campaign
            for campaign_id in campaign_ids:
                campaign_data = performance_data.get("campaigns", {}).get(campaign_id, {})
                
                if not campaign_data:
                    suggestions["errors"].append(f"No data found for campaign {campaign_id}")
                    continue
                
                campaign_decision = self.evaluate_campaign(
                    campaign_data=campaign_data,
                    performance_metrics=performance_data.get("metrics", {}).get(campaign_id, {}),
                    knowledge_base_rules=knowledge_base_rules
                )
                
                suggestions["campaigns"][campaign_id] = campaign_decision
            
            logger.info(f"Successfully generated optimization suggestions for account {ad_account_id}")
            return suggestions
            
        except DeepSeekAPIError as e:
            logger.error(f"DeepSeek API error while getting optimization suggestions: {str(e)}")
            suggestions["errors"].append(f"DeepSeek API error: {str(e)}")
            return suggestions
        except Exception as e:
            logger.error(f"Error getting optimization suggestions: {str(e)}")
            suggestions["errors"].append(f"Error: {str(e)}")
            return suggestions
    
    def analyze_ad_creative(self, creative_text: str, creative_image_url: Optional[str] = None) -> Dict[str, Any]:
        """Analyze ad creative and provide improvement suggestions.
        
        Args:
            creative_text: The text content of the ad
            creative_image_url: Optional URL to the ad image
            
        Returns:
            Dictionary containing analysis and suggestions
        """
        logger.info("Analyzing ad creative")
        
        try:
            prompt = f"""
            Analyze the following Facebook ad creative and provide specific improvement suggestions:
            
            Ad Text:
            {creative_text}
            """
            
            if creative_image_url:
                prompt += f"\nImage URL: {creative_image_url}"
            
            prompt += """
            
            Please provide:
            1. Overall assessment (strengths and weaknesses)
            2. Specific suggestions to improve the headline
            3. Specific suggestions to improve the body text
            4. Specific suggestions to improve the call-to-action
            5. Recommendations for A/B testing variations
            
            Format your response as a JSON object with the following structure:
            {
                "overall_assessment": "text",
                "headline_suggestions": ["suggestion1", "suggestion2"],
                "body_text_suggestions": ["suggestion1", "suggestion2"],
                "cta_suggestions": ["suggestion1", "suggestion2"],
                "ab_testing_recommendations": ["recommendation1", "recommendation2"]
            }
            """
            
            analysis_json = self.client.ask_question(
                question=prompt,
                temperature=0.4
            )
            
            # Parse the analysis JSON
            try:
                analysis = json.loads(analysis_json)
                logger.info("Successfully analyzed ad creative")
                return analysis
            except json.JSONDecodeError:
                logger.error("Failed to parse ad creative analysis JSON")
                return {
                    "error": "Failed to parse analysis",
                    "raw_response": analysis_json
                }
                
        except DeepSeekAPIError as e:
            logger.error(f"DeepSeek API error while analyzing ad creative: {str(e)}")
            return {"error": f"DeepSeek API error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error analyzing ad creative: {str(e)}")
            return {"error": f"Error: {str(e)}"}
    
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
            Dictionary containing generated ad creative
        """
        logger.info(f"Generating ad creative for campaign objective: {campaign_objective}")
        
        try:
            # Convert inputs to JSON strings for better formatting in the prompt
            product_info_str = json.dumps(product_info, indent=2)
            target_audience_str = json.dumps(target_audience, indent=2)
            brand_guidelines_str = json.dumps(brand_guidelines, indent=2) if brand_guidelines else "No specific brand guidelines provided."
            
            prompt = f"""
            Generate Facebook ad creative based on the following information:
            
            Product Information:
            {product_info_str}
            
            Target Audience:
            {target_audience_str}
            
            Campaign Objective:
            {campaign_objective}
            
            Brand Guidelines:
            {brand_guidelines_str}
            
            Please generate:
            1. 3 headline options (max 40 characters each)
            2. 3 primary text options (max 125 characters each)
            3. 3 description options (max 30 characters each)
            4. 3 call-to-action options
            5. Image description for what should be shown in the ad image
            
            Format your response as a JSON object with the following structure:
            {{
                "headlines": ["headline1", "headline2", "headline3"],
                "primary_text": ["text1", "text2", "text3"],
                "descriptions": ["description1", "description2", "description3"],
                "cta_options": ["cta1", "cta2", "cta3"],
                "image_description": "description of what the ad image should show"
            }}
            """
            
            creative_json = self.client.ask_question(
                question=prompt,
                temperature=0.7
            )
            
            # Parse the creative JSON
            try:
                creative = json.loads(creative_json)
                logger.info("Successfully generated ad creative")
                return creative
            except json.JSONDecodeError:
                logger.error("Failed to parse generated ad creative JSON")
                return {
                    "error": "Failed to parse generated creative",
                    "raw_response": creative_json
                }
                
        except DeepSeekAPIError as e:
            logger.error(f"DeepSeek API error while generating ad creative: {str(e)}")
            return {"error": f"DeepSeek API error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error generating ad creative: {str(e)}")
            return {"error": f"Error: {str(e)}"}
