"""
Testing Framework for DeepSeek Integration

This module provides tests for the DeepSeek integration components
to ensure they work correctly together.
"""

import os
import json
import unittest
from unittest.mock import MagicMock, patch
import logging
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('deepseek_tests')

class TestDeepSeekClient(unittest.TestCase):
    """Tests for the DeepSeekAIClient class."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variable
        self.api_key_patcher = patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test_api_key'})
        self.api_key_patcher.start()
        
        # Import after patching environment
        from deepseek_client import DeepSeekAIClient
        
        # Mock OpenAI client
        self.openai_patcher = patch('openai.OpenAI')
        self.mock_openai = self.openai_patcher.start()
        
        # Create mock response for chat completions
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        
        # Set up mock client
        self.mock_client = MagicMock()
        self.mock_client.chat.completions.create.return_value = mock_response
        self.mock_openai.return_value = self.mock_client
        
        # Create client instance
        self.client = DeepSeekAIClient()
    
    def tearDown(self):
        """Clean up after tests."""
        self.api_key_patcher.stop()
        self.openai_patcher.stop()
    
    def test_initialization(self):
        """Test client initialization."""
        self.assertEqual(self.client.api_key, 'test_api_key')
        self.assertEqual(self.client.base_url, 'https://api.deepseek.com')
        self.mock_openai.assert_called_once_with(
            api_key='test_api_key',
            base_url='https://api.deepseek.com'
        )
    
    def test_ask_question(self):
        """Test asking a question."""
        response = self.client.ask_question("Test question")
        
        self.assertEqual(response, "Test response")
        self.mock_client.chat.completions.create.assert_called_once()
        call_args = self.mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_args['model'], 'deepseek-chat')
        self.assertEqual(call_args['messages'][-1]['content'], 'Test question')
    
    def test_analyze_document(self):
        """Test document analysis."""
        response = self.client.analyze_document("Test document")
        
        self.assertEqual(response, "Test response")
        self.mock_client.chat.completions.create.assert_called_once()
        call_args = self.mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_args['model'], 'deepseek-chat')
        self.assertIn('Test document', call_args['messages'][-1]['content'])
    
    def test_generate_decision(self):
        """Test decision generation."""
        # Mock JSON response
        self.mock_client.chat.completions.create.return_value.choices[0].message.content = '{"test": "value"}'
        
        response = self.client.generate_decision(
            campaign_data={"name": "Test Campaign"},
            performance_metrics={"impressions": 1000},
            knowledge_base_rules=[{"rule": "Test rule"}]
        )
        
        self.assertEqual(response, '{"test": "value"}')
        self.mock_client.chat.completions.create.assert_called_once()
        call_args = self.mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_args['model'], 'deepseek-chat')
        self.assertIn('Test Campaign', call_args['messages'][-1]['content'])


class TestAPIConnection(unittest.TestCase):
    """Tests for the DeepSeekAPIConnection class."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock DeepSeekAIClient
        self.client_patcher = patch('api_connection.DeepSeekAIClient')
        self.mock_client_class = self.client_patcher.start()
        self.mock_client = MagicMock()
        self.mock_client_class.return_value = self.mock_client
        
        # Import after patching
        from api_connection import DeepSeekAPIConnection
        
        # Create connection instance
        self.connection = DeepSeekAPIConnection(api_key='test_api_key')
    
    def tearDown(self):
        """Clean up after tests."""
        self.client_patcher.stop()
    
    def test_initialization(self):
        """Test connection initialization."""
        self.mock_client_class.assert_called_once_with(api_key='test_api_key')
        self.assertEqual(self.connection.client, self.mock_client)
    
    def test_process_document(self):
        """Test document processing."""
        # Set up mock responses
        self.mock_client.analyze_document.return_value = "Test analysis"
        self.mock_client.extract_knowledge_items.return_value = [
            {"category": "budget", "rule": "Test rule"}
        ]
        
        result = self.connection.process_document("Test document", "test_doc.pdf")
        
        self.mock_client.analyze_document.assert_called_once_with("Test document")
        self.mock_client.extract_knowledge_items.assert_called_once_with("Test analysis")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "budget")
        self.assertEqual(result[0]["rule"], "Test rule")
        self.assertEqual(result[0]["source"], "test_doc.pdf")
    
    def test_evaluate_campaign(self):
        """Test campaign evaluation."""
        # Set up mock response
        self.mock_client.generate_decision.return_value = '{"budget_adjustment": {"action": "increase", "amount": 0.2}}'
        
        result = self.connection.evaluate_campaign(
            campaign_data={"name": "Test Campaign"},
            performance_metrics={"impressions": 1000},
            knowledge_base_rules=[{"rule": "Test rule"}]
        )
        
        self.mock_client.generate_decision.assert_called_once()
        self.assertEqual(result["budget_adjustment"]["action"], "increase")
        self.assertEqual(result["budget_adjustment"]["amount"], 0.2)


class TestKnowledgeProcessor(unittest.TestCase):
    """Tests for the KnowledgeProcessor class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temp directory for knowledge base
        self.test_dir = os.path.join(os.getcwd(), 'test_data')
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_kb_path = os.path.join(self.test_dir, 'test_kb.json')
        
        # Import
        from knowledge_processor import KnowledgeProcessor
        
        # Create processor instance
        self.processor = KnowledgeProcessor(knowledge_base_path=self.test_kb_path)
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove test knowledge base file
        if os.path.exists(self.test_kb_path):
            os.remove(self.test_kb_path)
    
    def test_initialization(self):
        """Test processor initialization."""
        self.assertEqual(self.processor.knowledge_base_path, self.test_kb_path)
        self.assertIn("items", self.processor.knowledge_base)
        self.assertIn("categories", self.processor.knowledge_base)
        self.assertIn("documents", self.processor.knowledge_base)
    
    def test_add_knowledge_items(self):
        """Test adding knowledge items."""
        items = [
            {
                "category": "budget",
                "rule": "Increase budget by 20% when ROAS exceeds target",
                "conditions": "ROAS > target",
                "outcome": "Improved scale"
            },
            {
                "category": "targeting",
                "rule": "Exclude non-converting audiences",
                "conditions": "No conversions in 14 days",
                "outcome": "Improved efficiency"
            }
        ]
        
        added_count = self.processor.add_knowledge_items(items, "test_doc.pdf")
        
        self.assertEqual(added_count, 2)
        self.assertEqual(len(self.processor.knowledge_base["items"]), 2)
        self.assertEqual(len(self.processor.knowledge_base["categories"]), 2)
        self.assertEqual(len(self.processor.knowledge_base["documents"]), 1)
        
        # Check that items were added correctly
        self.assertEqual(self.processor.knowledge_base["items"][0]["category"], "budget")
        self.assertEqual(self.processor.knowledge_base["items"][1]["category"], "targeting")
        
        # Check that categories were updated
        self.assertEqual(self.processor.knowledge_base["categories"]["budget"]["item_count"], 1)
        self.assertEqual(self.processor.knowledge_base["categories"]["targeting"]["item_count"], 1)
        
        # Check that document was added
        self.assertEqual(self.processor.knowledge_base["documents"]["test_doc.pdf"]["item_count"], 2)
    
    def test_get_knowledge_items(self):
        """Test getting knowledge items."""
        # Add test items
        items = [
            {"category": "budget", "rule": "Test budget rule"},
            {"category": "targeting", "rule": "Test targeting rule"},
            {"category": "budget", "rule": "Another budget rule"}
        ]
        self.processor.add_knowledge_items(items, "test_doc.pdf")
        
        # Get all items
        all_items = self.processor.get_knowledge_items()
        self.assertEqual(len(all_items), 3)
        
        # Get items by category
        budget_items = self.processor.get_knowledge_items(category="budget")
        self.assertEqual(len(budget_items), 2)
        
        # Get items by document
        doc_items = self.processor.get_knowledge_items(document_name="test_doc.pdf")
        self.assertEqual(len(doc_items), 3)
        
        # Get items with limit
        limited_items = self.processor.get_knowledge_items(limit=2)
        self.assertEqual(len(limited_items), 2)


class TestIntegration(unittest.TestCase):
    """Tests for the AIMediaBuyingAgent class."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock dependencies
        self.api_connection_patcher = patch('integration.DeepSeekAPIConnection')
        self.mock_api_connection_class = self.api_connection_patcher.start()
        self.mock_api_connection = MagicMock()
        self.mock_api_connection_class.return_value = self.mock_api_connection
        
        self.knowledge_processor_patcher = patch('integration.KnowledgeProcessor')
        self.mock_knowledge_processor_class = self.knowledge_processor_patcher.start()
        self.mock_knowledge_processor = MagicMock()
        self.mock_knowledge_processor_class.return_value = self.mock_knowledge_processor
        
        # Mock Facebook Ads manager
        self.mock_facebook_ads_manager = MagicMock()
        
        # Import after patching
        from integration import AIMediaBuyingAgent
        
        # Create agent instance
        self.agent = AIMediaBuyingAgent(
            deepseek_api_key='test_api_key',
            knowledge_base_path='test_kb.json',
            facebook_ads_manager=self.mock_facebook_ads_manager
        )
    
    def tearDown(self):
        """Clean up after tests."""
        self.api_connection_patcher.stop()
        self.knowledge_processor_patcher.stop()
    
    def test_initialization(self):
        """Test agent initialization."""
        self.mock_api_connection_class.assert_called_once_with(api_key='test_api_key')
        self.mock_knowledge_processor_class.assert_called_once_with(knowledge_base_path='test_kb.json')
        
        self.assertEqual(self.agent.api_connection, self.mock_api_connection)
        self.assertEqual(self.agent.knowledge_processor, self.mock_knowledge_processor)
        self.assertEqual(self.agent.facebook_ads_manager, self.mock_facebook_ads_manager)
    
    def test_process_document(self):
        """Test document processing."""
        # Set up mock response
        self.mock_api_connection.process_document.return_value = [
            {"category": "budget", "rule": "Test rule"}
        ]
        
        result = self.agent.process_document("Test document", "test_doc.pdf")
        
        self.mock_api_connection.process_document.assert_called_once_with("Test document", "test_doc.pdf")
        self.mock_knowledge_processor.add_knowledge_items.assert_called_once()
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "budget")
        self.assertEqual(result[0]["rule"], "Test rule")
    
    def test_evaluate_campaign(self):
        """Test campaign evaluation."""
        # Set up mock responses
        self.mock_facebook_ads_manager.get_campaign.return_value = {
            "id": "123",
            "name": "Test Campaign",
            "objective": "conversions"
        }
        self.mock_facebook_ads_manager.get_campaign_performance.return_value = {
            "impressions": 1000,
            "clicks": 100,
            "conversions": 10
        }
        self.mock_knowledge_processor.get_rules_for_campaign_type.return_value = [
            {"category": "budget", "rule": "Test rule"}
        ]
        self.mock_api_connection.evaluate_campaign.return_value = {
            "budget_adjustment": {"action": "increase", "amount": 0.2}
        }
        
        result = self.agent.evaluate_campaign("123", "act_123")
        
        self.mock_facebook_ads_manager.get_campaign.assert_called_once_with("act_123", "123")
        self.mock_facebook_ads_manager.get_campaign_performance.assert_called_once_with("act_123", "123")
        self.mock_knowledge_processor.get_rules_for_campaign_type.assert_called_once_with("conversions")
        self.mock_api_connection.evaluate_campaign.assert_called_once()
        
        self.assertEqual(result["budget_adjustment"]["action"], "increase")
        self.assertEqual(result["budget_adjustment"]["amount"], 0.2)


if __name__ == '__main__':
    unittest.main()
