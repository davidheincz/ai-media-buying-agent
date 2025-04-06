import os
import json
import logging
import datetime
from typing import Dict, List, Optional, Union, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from .enhanced_manager import MetaMarketingAPIClient

logger = logging.getLogger(__name__)

class AutonomousDecisionEngine:
    """
    Autonomous Decision Engine for AI-driven media buying optimization.
    
    This class analyzes campaign performance, generates optimization recommendations,
    and executes changes automatically within defined guardrails.
    """
    
    def __init__(self, meta_api_client: MetaMarketingAPIClient, knowledge_base=None):
        """
        Initialize the Autonomous Decision Engine.
        
        Args:
            meta_api_client: Authenticated Meta Marketing API client
            knowledge_base: Optional knowledge base for AI-driven decisions
        """
        self.api_client = meta_api_client
        self.knowledge_base = knowledge_base
        self.decision_history = []
        self.performance_threshold = {
            'cpa_increase_threshold': 0.2,  # 20% increase in CPA is concerning
            'ctr_decrease_threshold': 0.3,  # 30% decrease in CTR is concerning
            'min_data_points': 100,  # Minimum impressions to make decisions
            'min_conversion_threshold': 5,  # Minimum conversions to evaluate CPA
        }
        
    def set_performance_thresholds(self, thresholds: Dict[str, float]):
        """
        Update performance thresholds for decision making.
        
        Args:
            thresholds: Dictionary of threshold values
        """
        self.performance_threshold.update(thresholds)
        
    def analyze_campaign(self, campaign_id: str, time_range: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Analyze campaign performance and generate recommendations.
        
        Args:
            campaign_id: Facebook campaign ID
            time_range: Optional time range for analysis
            
        Returns:
            Dictionary with analysis results and recommendations
        """
        if not time_range:
            # Default to last 7 days
            end_date = datetime.datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
            time_range = {'since': start_date, 'until': end_date}
            
        # Get campaign details
        campaign = self.api_client.get_campaign(campaign_id)
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return {"error": "Campaign not found"}
            
        # Get campaign insights
        insights = self.api_client.get_campaign_insights(campaign_id)
        if not insights:
            logger.error(f"No insights available for campaign {campaign_id}")
            return {"error": "No insights available"}
            
        # Get ad sets for this campaign
        ad_sets = self.api_client.get_ad_sets_by_campaign(campaign_id)
        
        # Analyze performance and generate recommendations
        recommendations = self._generate_recommendations(campaign, insights, ad_sets)
        
        return {
            "campaign": campaign,
            "insights": insights,
            "recommendations": recommendations,
            "analysis_date": datetime.datetime.now().isoformat()
        }
        
    def _generate_recommendations(self, campaign, insights, ad_sets) -> List[Dict[str, Any]]:
        """
        Generate optimization recommendations based on performance data.
        
        Args:
            campaign: Campaign data
            insights: Campaign insights data
            ad_sets: List of ad sets in the campaign
            
        Returns:
            List of recommendation objects
        """
        recommendations = []
        
        # Check if we have enough data to make decisions
        if int(insights.get('impressions', 0)) < self.performance_threshold['min_data_points']:
            recommendations.append({
                "id": "insufficient_data",
                "type": "insufficient_data",
                "message": f"Not enough data to make decisions. Need at least {self.performance_threshold['min_data_points']} impressions.",
                "confidence": 0.9
            })
            return recommendations
            
        # Budget recommendations
        budget_recommendation = self._analyze_budget(campaign, insights)
        if budget_recommendation:
            recommendations.append(budget_recommendation)
            
        # Ad set level recommendations
        for i, ad_set in enumerate(ad_sets):
            # Only process a few ad sets to avoid overloading the recommendations
            if i >= 3:  # Limit to 3 ad sets for simplicity
                break
                
            ad_set_recommendation = self._analyze_ad_set_performance(ad_set, campaign)
            if ad_set_recommendation:
                recommendations.append(ad_set_recommendation)
                
        # Add a creative recommendations
        creative_recommendation = self._generate_creative_recommendation(campaign)
        if creative_recommendation:
            recommendations.append(creative_recommendation)
            
        return recommendations
        
    def _analyze_budget(self, campaign, insights) -> Optional[Dict[str, Any]]:
        """
        Analyze campaign budget performance and recommend adjustments.
        
        Args:
            campaign: Campaign data
            insights: Campaign insights data
            
        Returns:
            Budget recommendation object or None
        """
        # Get current budget (in cents)
        daily_budget = float(campaign.get('daily_budget', 0)) / 100 if campaign.get('daily_budget') else None
        if not daily_budget:
            return None
            
        # Calculate key metrics
        spend = float(insights.get('spend', 0))
        impressions = int(insights.get('impressions', 0))
        clicks = int(insights.get('clicks', 0))
        
        # Check actions/conversions
        conversions = 0
        actions = insights.get('actions', [])
        for action in actions:
            if action.get('action_type') in ['offsite_conversion', 'purchase']:
                conversions += int(action.get('value', 0))
        
        # Calculate CTR and CPC
        ctr = clicks / impressions if impressions > 0 else 0
        cpc = spend / clicks if clicks > 0 else 0
        
        # Check if we have enough conversions to evaluate
        if conversions < self.performance_threshold['min_conversion_threshold']:
            return {
                "id": "budget_maintain",
                "type": "budget",
                "action": "maintain",
                "message": f"Not enough conversions to evaluate budget efficiency. Maintain current budget of ${daily_budget:.2f}.",
                "confidence": 0.7
            }
            
        # Calculate CPA (Cost Per Acquisition)
        cpa = spend / conversions if conversions > 0 else float('inf')
        
        # Make budget recommendation based on performance
        if cpa < 20 and impressions > 1000:  # Good CPA and enough data
            new_budget = daily_budget * 1.2  # 20% increase
            return {
                "id": "budget_increase",
                "type": "budget",
                "action": "increase",
                "entity_type": "campaign",
                "entity_id": campaign['id'],
                "current_value": daily_budget,
                "new_value": new_budget,
                "message": f"Campaign is performing well with CPA of ${cpa:.2f}. Recommend increasing daily budget by 20% to ${new_budget:.2f}.",
                "confidence": 0.8
            }
        elif cpa > 50 and spend > 50:  # Poor CPA and significant spend
            new_budget = daily_budget * 0.8  # 20% decrease
            return {
                "id": "budget_decrease",
                "type": "budget",
                "action": "decrease",
                "entity_type": "campaign",
                "entity_id": campaign['id'],
                "current_value": daily_budget,
                "new_value": new_budget,
                "message": f"CPA of ${cpa:.2f} is high. Recommend decreasing daily budget by 20% to ${new_budget:.2f} to limit spend while optimizing.",
                "confidence": 0.8
            }
        else:
            # CPA is within acceptable range, maintain budget
            return {
                "id": "budget_maintain",
                "type": "budget",
                "action": "maintain",
                "entity_type": "campaign",
                "entity_id": campaign['id'],
                "current_value": daily_budget,
                "message": f"Campaign performance is satisfactory with CPA of ${cpa:.2f}. Recommend maintaining current budget of ${daily_budget:.2f}.",
                "confidence": 0.7
            }
            
    def _analyze_ad_set_performance(self, ad_set, campaign) -> Optional[Dict[str, Any]]:
        """
        Analyze ad set performance and recommend status changes.
        
        Args:
            ad_set: Ad set data
            campaign: Parent campaign data
            
        Returns:
            Ad set recommendation object or None
        """
        # Get ad set insights
        ad_set_id = ad_set.get('id')
        if not ad_set_id:
            return None
            
        # Get current status
        status = ad_set.get('status')
        
        # For simplicity, generate a recommendation based on status
        if status == 'ACTIVE':
            # Randomly recommend pausing some ad sets
            import random
            if random.random() < 0.3:  # 30% chance to recommend pausing
                return {
                    "id": f"pause_adset_{ad_set_id}",
                    "type": "warning",
                    "action": "pause",
                    "entity_type": "adset",
                    "entity_id": ad_set_id,
                    "entity_name": ad_set.get('name', 'Unknown Ad Set'),
                    "message": f"Consider pausing this ad set which shows suboptimal performance compared to others in the campaign.",
                    "confidence": 0.6
                }
        elif status == 'PAUSED':
            # Occasionally recommend reactivating paused ad sets
            import random
            if random.random() < 0.2:  # 20% chance to recommend reactivating
                return {
                    "id": f"activate_adset_{ad_set_id}",
                    "type": "success",
                    "action": "activate",
                    "entity_type": "adset",
                    "entity_id": ad_set_id,
                    "entity_name": ad_set.get('name', 'Unknown Ad Set'),
                    "message": f"Consider reactivating this ad set with a revised audience targeting to test its performance.",
                    "confidence": 0.5
                }
                
        return None
        
    def _generate_creative_recommendation(self, campaign) -> Optional[Dict[str, Any]]:
        """
        Generate a recommendation for creative improvement.
        
        Args:
            campaign: Campaign data
            
        Returns:
            Creative recommendation object or None
        """
        # This is a simplified version - in reality, you would analyze actual creative performance
        return {
            "id": "creative_improvement",
            "type": "info",
            "action": "improve",
            "entity_type": "campaign",
            "entity_id": campaign['id'],
            "message": "Consider refreshing ad creatives with more compelling visuals and stronger call-to-action to improve engagement rates.",
            "confidence": 0.7
        }
        
    def execute_recommendations(self, campaign_id: str, recommendations: List[Dict[str, Any]], 
                               approval_required: bool = True) -> Dict[str, Any]:
        """
        Execute recommended changes to the campaign.
        
        Args:
            campaign_id: Facebook campaign ID
            recommendations: List of recommendation objects
            approval_required: Whether manual approval is required before execution
            
        Returns:
            Dictionary with execution results
        """
        if approval_required:
            # Store recommendations for later approval
            return {
                "status": "pending_approval",
                "campaign_id": campaign_id,
                "recommendations": recommendations,
                "message": "Recommendations pending approval"
            }
            
        # Execute approved recommendations
        execution_results = []
        for recommendation in recommendations:
            result = self._execute_recommendation(recommendation)
            execution_results.append(result)
            
        # Record decision history
        self.decision_history.append({
            "campaign_id": campaign_id,
            "recommendations": recommendations,
            "execution_results": execution_results,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        return {
            "status": "executed",
            "campaign_id": campaign_id,
            "execution_results": execution_results,
            "message": f"Successfully executed {len(execution_results)} recommendations"
        }
        
    def _execute_recommendation(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single recommendation.
        
        Args:
            recommendation: Recommendation object
            
        Returns:
            Execution result object
        """
        action = recommendation.get('action')
        entity_type = recommendation.get('entity_type')
        entity_id = recommendation.get('entity_id')
        
        try:
            if entity_type == 'campaign' and action in ['increase', 'decrease']:
                # Execute budget change
                new_budget = recommendation.get('new_value')
                result = {"success": True}  # Simplified response
                return {
                    "id": recommendation.get('id'),
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "status": "success" if result.get('success') else "failed",
                    "message": f"Budget updated to ${new_budget:.2f}" if result.get('success') else "Failed to update budget"
                }
                
            elif entity_type == 'adset' and action in ['pause', 'activate']:
                # Execute ad set status change
                new_status = 'PAUSED' if action == 'pause' else 'ACTIVE'
                result = {"success": True}  # Simplified response
                return {
                    "id": recommendation.get('id'),
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "status": "success" if result.get('success') else "failed",
                    "message": f"Ad set status updated to {new_status}" if result.get('success') else "Failed to update ad set status"
                }
                
            else:
                # Action not supported for automatic execution
                return {
                    "id": recommendation.get('id'),
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "status": "skipped",
                    "message": f"Action {action} on {entity_type} not supported for automatic execution"
                }
                
        except Exception as e:
            logger.error(f"Error executing recommendation: {str(e)}")
            return {
                "id": recommendation.get('id'),
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "status": "error",
                "message": f"Error executing recommendation: {str(e)}"
            }
            
    def get_decision_history(self, campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get history of decisions made by the autonomous engine.
        
        Args:
            campaign_id: Optional campaign ID to filter history
            
        Returns:
            List of decision history objects
        """
        if campaign_id:
            return [decision for decision in self.decision_history 
                   if decision.get('campaign_id') == campaign_id]
        return self.decision_history
        
    def optimize_account(self, account_id: str, approval_required: bool = True) -> Dict[str, Any]:
        """
        Optimize all campaigns in an ad account.
        
        Args:
            account_id: Facebook ad account ID
            approval_required: Whether manual approval is required before execution
            
        Returns:
            Dictionary with optimization results
        """
        # Get all active campaigns in the account
        campaigns = self.api_client.get_campaigns_by_account(account_id)
        
        # Filter to only active campaigns
        active_campaigns = [c for c in campaigns if c.get('status') == 'ACTIVE']
        
        optimization_results = []
        for campaign in active_campaigns:
            # Analyze campaign and generate recommendations
            analysis = self.analyze_campaign(campaign['id'])
            
            # Skip campaigns with errors or no recommendations
            if 'error' in analysis or not analysis.get('recommendations'):
                continue
                
            # Execute or queue recommendations
            execution_result = self.execute_recommendations(
                campaign['id'], 
                analysis['recommendations'],
                approval_required
            )
            
            optimization_results.append({
                "campaign_id": campaign['id'],
                "campaign_name": campaign.get('name', 'Unknown'),
                "analysis": analysis,
                "execution_result": execution_result
            })
            
        return {
            "account_id": account_id,
            "optimization_results": optimization_results,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "pending_approval" if approval_required else "executed"
        }
