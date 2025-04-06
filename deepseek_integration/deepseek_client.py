"""
DeepSeek AI Client Module

This module provides a client for interacting with the DeepSeek AI API.
It includes functionality for asking questions, analyzing documents,
and generating decisions based on campaign data and knowledge base rules.
"""

import os
import time
import logging
import json
from typing import Dict, List, Optional, Union, Any

import openai
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('deepseek_client')

class DeepSeekAPIError(Exception):
    """Exception raised for DeepSeek API errors."""
    pass

class DeepSeekAIClient:
    """Client for interacting with DeepSeek AI API."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.deepseek.com"):
        """Initialize the DeepSeek AI client.
        
        Args:
            api_key: DeepSeek API key. If None, will try to get from environment variable.
            base_url: Base URL for the DeepSeek API.
        """
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API key is required. Set DEEPSEEK_API_KEY environment variable or pass api_key parameter.")
        
        self.base_url = base_url
        logger.info(f"Initializing DeepSeek AI client with base URL: {self.base_url}")
        
        # Initialize OpenAI client with DeepSeek base URL
        try:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info("Successfully initialized OpenAI client with DeepSeek base URL")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise DeepSeekAPIError(f"Failed to initialize client: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((openai.APIError, openai.APIConnectionError, openai.RateLimitError)),
        reraise=True
    )
    def ask_question(
        self, 
        question: str, 
        context: Optional[str] = None, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Ask a question to DeepSeek AI.
        
        Args:
            question: The question to ask
            context: Optional context to provide additional information
            system_prompt: Optional system prompt to guide the model
            temperature: Controls randomness. Higher values mean more random completions.
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            The response from DeepSeek AI
            
        Raises:
            DeepSeekAPIError: If there's an error calling the API
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
        
        logger.info(f"Asking question to DeepSeek AI: {question[:50]}...")
        
        try:
            # Call DeepSeek API
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            logger.info("Successfully received response from DeepSeek AI")
            return response.choices[0].message.content
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {str(e)}. Retrying...")
            raise
        except openai.APIConnectionError as e:
            logger.warning(f"API connection error: {str(e)}. Retrying...")
            raise
        except openai.APIError as e:
            logger.warning(f"API error: {str(e)}. Retrying...")
            raise
        except Exception as e:
            logger.error(f"Error asking question to DeepSeek AI: {str(e)}")
            raise DeepSeekAPIError(f"Error asking question: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((openai.APIError, openai.APIConnectionError, openai.RateLimitError)),
        reraise=True
    )
    def analyze_document(
        self, 
        document_text: str, 
        question: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4000
    ) -> str:
        """Analyze a document and extract relevant information.
        
        Args:
            document_text: The text content of the document
            question: Optional specific question about the document
            temperature: Controls randomness. Lower values for more deterministic outputs.
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Analysis results from DeepSeek AI
            
        Raises:
            DeepSeekAPIError: If there's an error calling the API
        """
        prompt = """
        Please analyze this media buying document and extract key information including:
        1. Budget management rules
        2. Campaign optimization strategies
        3. Target KPI thresholds
        4. Audience targeting recommendations
        5. Ad creative best practices
        
        Document: {document_text}
        """.format(document_text=document_text)
        
        if question:
            prompt += f"\n\nSpecific question: {question}"
        
        messages = [
            {"role": "system", "content": "You are a media buying expert who can extract structured information from documents."},
            {"role": "user", "content": prompt}
        ]
        
        logger.info(f"Analyzing document with DeepSeek AI. Document length: {len(document_text)} characters")
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            logger.info("Successfully received document analysis from DeepSeek AI")
            return response.choices[0].message.content
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {str(e)}. Retrying...")
            raise
        except openai.APIConnectionError as e:
            logger.warning(f"API connection error: {str(e)}. Retrying...")
            raise
        except openai.APIError as e:
            logger.warning(f"API error: {str(e)}. Retrying...")
            raise
        except Exception as e:
            logger.error(f"Error analyzing document with DeepSeek AI: {str(e)}")
            raise DeepSeekAPIError(f"Error analyzing document: {str(e)}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((openai.APIError, openai.APIConnectionError, openai.RateLimitError)),
        reraise=True
    )
    def generate_decision(
        self, 
        campaign_data: Dict[str, Any], 
        performance_metrics: Dict[str, Any], 
        knowledge_base_rules: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 2000
    ) -> str:
        """Generate a decision about campaign management based on data and rules.
        
        Args:
            campaign_data: Data about the campaign
            performance_metrics: Performance metrics for the campaign
            knowledge_base_rules: Rules from the knowledge base
            temperature: Controls randomness. Lower values for more deterministic outputs.
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Decision recommendation from DeepSeek AI
            
        Raises:
            DeepSeekAPIError: If there's an error calling the API
        """
        # Convert inputs to JSON strings for better formatting in the prompt
        campaign_data_str = json.dumps(campaign_data, indent=2)
        performance_metrics_str = json.dumps(performance_metrics, indent=2)
        knowledge_base_rules_str = json.dumps(knowledge_base_rules, indent=2)
        
        prompt = f"""
        Based on the following campaign data, performance metrics, and knowledge base rules, 
        please recommend actions to take for this campaign.
        
        Campaign Data:
        {campaign_data_str}
        
        Performance Metrics:
        {performance_metrics_str}
        
        Knowledge Base Rules:
        {knowledge_base_rules_str}
        
        Please provide specific recommendations for:
        1. Budget adjustments (increase, decrease, or maintain)
        2. Ad set status changes (enable, pause, or no change)
        3. Audience targeting modifications
        4. Creative optimizations
        5. Bidding strategy adjustments
        
        For each recommendation, explain your reasoning based on the knowledge base rules.
        Format your response as a JSON object with the following structure:
        {
            "budget_adjustment": {"action": "increase|decrease|maintain", "amount": 0.2, "reason": "explanation"},
            "ad_set_actions": [
                {"ad_set_id": "id", "action": "pause|enable|increase_budget|decrease_budget", "amount": 0.3, "reason": "explanation"}
            ],
            "targeting_recommendations": ["recommendation1", "recommendation2"],
            "creative_recommendations": ["recommendation1", "recommendation2"],
            "bidding_recommendations": ["recommendation1", "recommendation2"]
        }
        """
        
        messages = [
            {"role": "system", "content": "You are a media buying expert who makes data-driven decisions based on established rules."},
            {"role": "user", "content": prompt}
        ]
        
        logger.info(f"Generating decision with DeepSeek AI for campaign: {campaign_data.get('name', 'Unknown')}")
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            logger.info("Successfully received decision from DeepSeek AI")
            
            # Try to parse the response as JSON
            decision_text = response.choices[0].message.content
            try:
                # Validate that the response is proper JSON
                json.loads(decision_text)
                return decision_text
            except json.JSONDecodeError:
                # If not JSON, ask DeepSeek to fix the format
                logger.warning("Decision response was not valid JSON. Requesting reformatting...")
                return self._reformat_as_json(decision_text)
                
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {str(e)}. Retrying...")
            raise
        except openai.APIConnectionError as e:
            logger.warning(f"API connection error: {str(e)}. Retrying...")
            raise
        except openai.APIError as e:
            logger.warning(f"API error: {str(e)}. Retrying...")
            raise
        except Exception as e:
            logger.error(f"Error generating decision with DeepSeek AI: {str(e)}")
            raise DeepSeekAPIError(f"Error generating decision: {str(e)}")
    
    def _reformat_as_json(self, text: str) -> str:
        """Ask DeepSeek to reformat text as valid JSON.
        
        Args:
            text: The text to reformat
            
        Returns:
            Reformatted text as valid JSON
        """
        prompt = f"""
        The following text should be formatted as a valid JSON object, but it may not be.
        Please reformat it as a valid JSON object:
        
        {text}
        
        Return ONLY the valid JSON with no additional text or explanation.
        """
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that reformats text as valid JSON."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
                stream=False
            )
            reformatted = response.choices[0].message.content
            
            # Validate that it's now proper JSON
            try:
                json.loads(reformatted)
                return reformatted
            except json.JSONDecodeError:
                # If still not valid JSON, return a basic valid JSON structure
                logger.error("Failed to reformat response as valid JSON")
                return json.dumps({
                    "error": "Could not generate valid JSON response",
                    "original_text": text
                })
                
        except Exception as e:
            logger.error(f"Error reformatting as JSON: {str(e)}")
            return json.dumps({
                "error": "Could not generate valid JSON response",
                "original_text": text
            })
    
    def extract_knowledge_items(self, analysis: str) -> List[Dict[str, Any]]:
        """Extract structured knowledge items from AI analysis.
        
        Args:
            analysis: AI analysis of document
            
        Returns:
            List of knowledge items as dictionaries
        """
        prompt = f"""
        Based on the following analysis of a media buying document, please extract structured knowledge items.
        Each knowledge item should have:
        1. A category (budget, targeting, creative, bidding, etc.)
        2. A rule or guideline
        3. Conditions for applying the rule
        4. Expected outcome
        
        Analysis:
        {analysis}
        
        Format each knowledge item as a JSON object in an array. For example:
        [
            {{
                "category": "budget",
                "rule": "Increase budget by 20% when ROAS exceeds target for 3 consecutive days",
                "conditions": "ROAS > target for 3 days",
                "outcome": "Improved scale while maintaining efficiency"
            }},
            {{
                "category": "targeting",
                "rule": "Exclude users who have not engaged with ads in the past 30 days",
                "conditions": "No engagement in 30 days",
                "outcome": "Improved relevance score and reduced wasted spend"
            }}
        ]
        
        Return ONLY the JSON array with no additional text or explanation.
        """
        
        logger.info("Extracting knowledge items from analysis")
        
        try:
            structured_items = self.ask_question(
                question=prompt,
                temperature=0.1,
                max_tokens=4000
            )
            
            # Try to parse the response as JSON
            try:
                items = json.loads(structured_items)
                logger.info(f"Successfully extracted {len(items)} knowledge items")
                return items
            except json.JSONDecodeError:
                # If not JSON, ask DeepSeek to fix the format
                logger.warning("Knowledge items response was not valid JSON. Requesting reformatting...")
                reformatted = self._reformat_as_json(structured_items)
                return json.loads(reformatted)
                
        except Exception as e:
            logger.error(f"Error extracting knowledge items: {str(e)}")
            return []
