import unittest
import json
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

from facebook_ads_manager.enhanced_manager import MetaMarketingAPIClient
from facebook_ads_manager.ad_management import AdManagement
from facebook_ads_manager.autonomous_engine import AutonomousDecisionEngine

class TestMetaMarketingAPIClient(unittest.TestCase):
    """Test cases for the Meta Marketing API Client"""
    
    def setUp(self):
        """Set up test environment"""
        self.access_token = "test_access_token"
        self.ad_account_id = "act_123456789"
        self.app_id = "test_app_id"
        self.app_secret = "test_app_secret"
        
        # Create client with test credentials
        self.client = MetaMarketingAPIClient(
            access_token=self.access_token,
            ad_account_id=self.ad_account_id,
            app_id=self.app_id,
            app_secret=self.app_secret
        )
        
    @patch('facebook_ads_manager.enhanced_manager.requests.get')
    def test_get_ad_accounts(self, mock_get):
        """Test getting ad accounts"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "act_123456789",
                    "name": "Test Ad Account"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Call method
        result = self.client.get_ad_accounts(self.access_token)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "act_123456789")
        self.assertEqual(result[0]["name"], "Test Ad Account")
        
        # Verify API call
        mock_get.assert_called_once()
        
    @patch('facebook_ads_manager.enhanced_manager.requests.get')
    def test_get_campaigns_by_account(self, mock_get):
        """Test getting campaigns by account"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "123456789",
                    "name": "Test Campaign",
                    "status": "ACTIVE",
                    "objective": "CONVERSIONS"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Call method
        result = self.client.get_campaigns_by_account(self.ad_account_id)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "123456789")
        self.assertEqual(result[0]["name"], "Test Campaign")
        self.assertEqual(result[0]["status"], "ACTIVE")
        self.assertEqual(result[0]["objective"], "CONVERSIONS")
        
        # Verify API call
        mock_get.assert_called_once()
        
    @patch('facebook_ads_manager.enhanced_manager.requests.get')
    def test_get_campaign_insights(self, mock_get):
        """Test getting campaign insights"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "campaign_id": "123456789",
                    "impressions": "1000",
                    "clicks": "50",
                    "spend": "100.00",
                    "actions": [
                        {
                            "action_type": "offsite_conversion",
                            "value": "10"
                        }
                    ]
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Call method
        result = self.client.get_campaign_insights("123456789")
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["impressions"], "1000")
        self.assertEqual(result["clicks"], "50")
        self.assertEqual(result["spend"], "100.00")
        self.assertEqual(len(result["actions"]), 1)
        self.assertEqual(result["actions"][0]["action_type"], "offsite_conversion")
        self.assertEqual(result["actions"][0]["value"], "10")
        
        # Verify API call
        mock_get.assert_called_once()
        
    @patch('facebook_ads_manager.enhanced_manager.requests.post')
    def test_create_campaign(self, mock_post):
        """Test creating a campaign"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "123456789"
        }
        mock_post.return_value = mock_response
        
        # Call method
        result = self.client.create_campaign(
            name="Test Campaign",
            objective="CONVERSIONS",
            status="PAUSED",
            daily_budget=100.00
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "123456789")
        
        # Verify API call
        mock_post.assert_called_once()
        
    @patch('facebook_ads_manager.enhanced_manager.requests.post')
    def test_update_campaign_budget(self, mock_post):
        """Test updating campaign budget"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True
        }
        mock_post.return_value = mock_response
        
        # Call method
        result = self.client.update_campaign_budget("123456789", 200.00)
        
        # Assertions
        self.assertTrue(result)
        
        # Verify API call
        mock_post.assert_called_once()
        
    @patch('facebook_ads_manager.enhanced_manager.requests.post')
    def test_update_ad_set_status(self, mock_post):
        """Test updating ad set status"""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True
        }
        mock_post.return_value = mock_response
        
        # Call method
        result = self.client.update_ad_set_status("123456789", "PAUSED")
        
        # Assertions
        self.assertTrue(result)
        
        # Verify API call
        mock_post.assert_called_once()
        
    def test_handle_api_error(self):
        """Test handling API errors"""
        # Mock error response
        error_response = {
            "error": {
                "message": "Invalid parameter",
                "type": "OAuthException",
                "code": 100,
                "error_subcode": 1487188
            }
        }
        
        # Call method
        result = self.client._handle_api_error(error_response)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Invalid parameter")
        self.assertEqual(result["error_type"], "OAuthException")
        self.assertEqual(result["error_code"], 100)


class TestAutonomousDecisionEngine(unittest.TestCase):
    """Test cases for the Autonomous Decision Engine"""
    
    def setUp(self):
        """Set up test environment"""
        # Create mock Meta API client
        self.mock_client = MagicMock()
        
        # Create engine with mock client
        self.engine = AutonomousDecisionEngine(meta_api_client=self.mock_client)
        
    def test_analyze_campaign_insufficient_data(self):
        """Test analyzing campaign with insufficient data"""
        # Mock client methods
        self.mock_client.get_campaign.return_value = {
            "id": "123456789",
            "name": "Test Campaign",
            "status": "ACTIVE",
            "objective": "CONVERSIONS"
        }
        self.mock_client.get_campaign_insights.return_value = {
            "impressions": "50",  # Below threshold
            "clicks": "5",
            "spend": "10.00",
            "actions": []
        }
        self.mock_client.get_ad_sets_by_campaign.return_value = []
        
        # Call method
        result = self.engine.analyze_campaign("123456789")
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("recommendations", result)
        self.assertEqual(len(result["recommendations"]), 1)
        self.assertEqual(result["recommendations"][0]["type"], "insufficient_data")
        
    def test_analyze_campaign_with_data(self):
        """Test analyzing campaign with sufficient data"""
        # Mock client methods
        self.mock_client.get_campaign.return_value = {
            "id": "123456789",
            "name": "Test Campaign",
            "status": "ACTIVE",
            "objective": "CONVERSIONS",
            "daily_budget": "100.00"
        }
        self.mock_client.get_campaign_insights.return_value = {
            "impressions": "1000",
            "clicks": "50",
            "spend": "100.00",
            "actions": [
                {
                    "action_type": "offsite_conversion",
                    "value": "5"
                }
            ]
        }
        self.mock_client.get_ad_sets_by_campaign.return_value = [
            {
                "id": "987654321",
                "name": "Test Ad Set",
                "status": "ACTIVE"
            }
        ]
        self.mock_client.get_ad_set_insights.return_value = {
            "impressions": "500",
            "clicks": "25",
            "spend": "50.00",
            "actions": [
                {
                    "action_type": "offsite_conversion",
                    "value": "2"
                }
            ]
        }
        
        # Call method
        result = self.engine.analyze_campaign("123456789")
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("recommendations", result)
        self.assertGreater(len(result["recommendations"]), 0)
        
    def test_execute_recommendations_with_approval(self):
        """Test executing recommendations with approval required"""
        # Create test recommendations
        recommendations = [
            {
                "type": "budget",
                "action": "increase",
                "current_value": 100.00,
                "recommended_value": 120.00
            }
        ]
        
        # Call method
        result = self.engine.execute_recommendations("123456789", recommendations, approval_required=True)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "pending_approval")
        self.assertEqual(result["campaign_id"], "123456789")
        self.assertEqual(result["recommendations"], recommendations)
        
    def test_execute_recommendations_without_approval(self):
        """Test executing recommendations without approval required"""
        # Create test recommendations
        recommendations = [
            {
                "type": "budget",
                "action": "increase",
                "campaign_id": "123456789",
                "current_value": 100.00,
                "recommended_value": 120.00
            }
        ]
        
        # Mock client methods
        self.mock_client.update_campaign_budget.return_value = True
        
        # Call method
        result = self.engine.execute_recommendations("123456789", recommendations, approval_required=False)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["campaign_id"], "123456789")
        self.assertIn("execution_results", result)
        
    def test_optimize_account(self):
        """Test optimizing an account"""
        # Mock client methods
        self.mock_client.get_campaigns_by_account.return_value = [
            {
                "id": "123456789",
                "name": "Test Campaign",
                "status": "ACTIVE",
                "objective": "CONVERSIONS"
            }
        ]
        self.mock_client.get_campaign.return_value = {
            "id": "123456789",
            "name": "Test Campaign",
            "status": "ACTIVE",
            "objective": "CONVERSIONS",
            "daily_budget": "100.00"
        }
        self.mock_client.get_campaign_insights.return_value = {
            "impressions": "1000",
            "clicks": "50",
            "spend": "100.00",
            "actions": [
                {
                    "action_type": "offsite_conversion",
                    "value": "5"
                }
            ]
        }
        self.mock_client.get_ad_sets_by_campaign.return_value = []
        
        # Call method
        result = self.engine.optimize_account("act_123456789", approval_required=True)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["account_id"], "act_123456789")
        self.assertEqual(result["status"], "pending_approval")
        self.assertIn("optimization_results", result)


if __name__ == '__main__':
    unittest.main()
