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
        insights = self.api_client.get_campaign_insights(campaign_id, time_range)
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
        if insights.get('impressions', 0) < self.performance_threshold['min_data_points']:
            recommendations.append({
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
        for ad_set in ad_sets:
            ad_set_insights = self.api_client.get_ad_set_insights(ad_set['id'])
            
            # Skip if not enough data
            if ad_set_insights.get('impressions', 0) < self.performance_threshold['min_data_points'] / 2:
                continue
                
            # Check performance and status
            ad_set_recommendation = self._analyze_ad_set(ad_set, ad_set_insights)
            if ad_set_recommendation:
                recommendations.append(ad_set_recommendation)
                
        # Targeting recommendations
        targeting_recommendation = self._analyze_targeting(campaign, insights, ad_sets)
        if targeting_recommendation:
            recommendations.append(targeting_recommendation)
            
        # Bidding recommendations
        bidding_recommendation = self._analyze_bidding(campaign, insights)
        if bidding_recommendation:
            recommendations.append(bidding_recommendation)
            
        # Creative recommendations
        creative_recommendation = self._analyze_creatives(campaign)
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
        # Get current budget
        daily_budget = campaign.get('daily_budget')
        if not daily_budget:
            return None
            
        # Calculate key metrics
        spend = insights.get('spend', 0)
        conversions = insights.get('actions', [])
        conversion_count = sum(action.get('value', 0) for action in conversions 
                              if action.get('action_type') == 'offsite_conversion')
        
        # Check if we have enough conversions to evaluate
        if conversion_count < self.performance_threshold['min_conversion_threshold']:
            return {
                "type": "budget",
                "action": "maintain",
                "message": f"Not enough conversions to evaluate budget efficiency. Maintain current budget of {daily_budget}.",
                "confidence": 0.7
            }
            
        # Calculate CPA
        cpa = float(spend) / conversion_count if conversion_count > 0 else float('inf')
        
        # Get campaign objective and target CPA if available
        objective = campaign.get('objective')
        target_cpa = self._get_target_cpa(campaign)
        
        # Make budget recommendation
        if target_cpa and cpa <= target_cpa * 0.8:
            # CPA is significantly better than target, increase budget
            new_budget = float(daily_budget) * 1.2  # 20% increase
            return {
                "type": "budget",
                "action": "increase",
                "current_value": daily_budget,
                "recommended_value": new_budget,
                "message": f"CPA of ${cpa:.2f} is below target of ${target_cpa:.2f}. Recommend increasing daily budget by 20% to ${new_budget:.2f}.",
                "confidence": 0.8
            }
        elif target_cpa and cpa >= target_cpa * 1.2:
            # CPA is significantly worse than target, decrease budget
            new_budget = float(daily_budget) * 0.8  # 20% decrease
            return {
                "type": "budget",
                "action": "decrease",
                "current_value": daily_budget,
                "recommended_value": new_budget,
                "message": f"CPA of ${cpa:.2f} is above target of ${target_cpa:.2f}. Recommend decreasing daily budget by 20% to ${new_budget:.2f}.",
                "confidence": 0.8
            }
        else:
            # CPA is within acceptable range of target
            return {
                "type": "budget",
                "action": "maintain",
                "current_value": daily_budget,
                "message": f"CPA of ${cpa:.2f} is within acceptable range of target. Maintain current budget.",
                "confidence": 0.7
            }
            
    def _analyze_ad_set(self, ad_set, insights) -> Optional[Dict[str, Any]]:
        """
        Analyze ad set performance and recommend status changes.
        
        Args:
            ad_set: Ad set data
            insights: Ad set insights data
            
        Returns:
            Ad set recommendation object or None
        """
        # Check current status
        status = ad_set.get('status')
        
        # Calculate key metrics
        spend = insights.get('spend', 0)
        conversions = insights.get('actions', [])
        conversion_count = sum(action.get('value', 0) for action in conversions 
                              if action.get('action_type') == 'offsite_conversion')
        
        # Calculate CPA
        cpa = float(spend) / conversion_count if conversion_count > 0 else float('inf')
        
        # Get target CPA
        target_cpa = self._get_target_cpa(ad_set)
        
        # Make ad set recommendation
        if status == 'ACTIVE' and (cpa > target_cpa * 2 or (spend > target_cpa * 3 and conversion_count == 0)):
            # Ad set is significantly underperforming, recommend pausing
            return {
                "type": "ad_set",
                "ad_set_id": ad_set['id'],
                "ad_set_name": ad_set.get('name', 'Unknown'),
                "action": "pause",
                "current_status": status,
                "message": f"Ad set is significantly underperforming with CPA of ${cpa:.2f} vs target of ${target_cpa:.2f}. Recommend pausing.",
                "confidence": 0.8
            }
        elif status == 'PAUSED' and ad_set.get('recommendations', []):
            # Ad set has recommendations from Facebook, consider reactivating
            return {
                "type": "ad_set",
                "ad_set_id": ad_set['id'],
                "ad_set_name": ad_set.get('name', 'Unknown'),
                "action": "activate",
                "current_status": status,
                "message": f"Ad set has recommendations from Facebook. Consider reactivating with suggested changes.",
                "confidence": 0.6
            }
        
        return None
        
    def _analyze_targeting(self, campaign, insights, ad_sets) -> Optional[Dict[str, Any]]:
        """
        Analyze targeting performance and recommend adjustments.
        
        Args:
            campaign: Campaign data
            insights: Campaign insights data
            ad_sets: List of ad sets in the campaign
            
        Returns:
            Targeting recommendation object or None
        """
        # Get breakdown reports if available
        age_gender_breakdown = self.api_client.get_campaign_insights(
            campaign['id'], 
            breakdown=['age', 'gender']
        )
        
        # If we don't have breakdown data, return None
        if not age_gender_breakdown:
            return None
            
        # Find top performing demographics
        top_demographics = []
        for item in age_gender_breakdown:
            if item.get('ctr') and float(item.get('ctr', 0)) > 0.02:  # CTR threshold
                top_demographics.append({
                    'age': item.get('age'),
                    'gender': item.get('gender'),
                    'ctr': item.get('ctr'),
                    'cpa': float(item.get('spend', 0)) / float(item.get('conversions', 1)) if item.get('conversions') else None
                })
                
        # Sort by CTR
        top_demographics.sort(key=lambda x: float(x['ctr']), reverse=True)
        
        # If we have identified top performing demographics
        if top_demographics:
            return {
                "type": "targeting",
                "action": "refine",
                "top_demographics": top_demographics[:3],  # Top 3 demographics
                "message": f"Consider refining targeting to focus on top performing demographics: {', '.join([f'{d['age']}/{d['gender']}' for d in top_demographics[:3]])}",
                "confidence": 0.7
            }
            
        return None
        
    def _analyze_bidding(self, campaign, insights) -> Optional[Dict[str, Any]]:
        """
        Analyze bidding strategy and recommend adjustments.
        
        Args:
            campaign: Campaign data
            insights: Campaign insights data
            
        Returns:
            Bidding recommendation object or None
        """
        # Get current bid strategy
        bid_strategy = campaign.get('bid_strategy')
        
        # Calculate key metrics
        spend = insights.get('spend', 0)
        conversions = insights.get('actions', [])
        conversion_count = sum(action.get('value', 0) for action in conversions 
                              if action.get('action_type') == 'offsite_conversion')
        
        # Calculate CPA
        cpa = float(spend) / conversion_count if conversion_count > 0 else float('inf')
        
        # Get target CPA
        target_cpa = self._get_target_cpa(campaign)
        
        # Make bidding recommendation
        if bid_strategy == 'LOWEST_COST_WITHOUT_CAP' and conversion_count >= 10:
            # We have enough conversion data to consider cost cap
            return {
                "type": "bidding",
                "action": "change_strategy",
                "current_strategy": bid_strategy,
                "recommended_strategy": "COST_CAP",
                "recommended_value": min(cpa * 1.1, target_cpa),
                "message": f"Consider changing bid strategy to cost cap with target of ${min(cpa * 1.1, target_cpa):.2f} to maintain efficient CPA.",
                "confidence": 0.7
            }
        elif bid_strategy == 'COST_CAP' and cpa > target_cpa * 1.2:
            # Cost cap is not working well, consider adjusting
            current_cap = campaign.get('bid_amount', 0)
            new_cap = current_cap * 0.9  # 10% decrease
            return {
                "type": "bidding",
                "action": "adjust_cap",
                "current_value": current_cap,
                "recommended_value": new_cap,
                "message": f"Current cost cap of ${current_cap:.2f} is not achieving target CPA. Recommend decreasing to ${new_cap:.2f}.",
                "confidence": 0.7
            }
            
        return None
        
    def _analyze_creatives(self, campaign) -> Optional[Dict[str, Any]]:
        """
        Analyze ad creatives and recommend improvements.
        
        Args:
            campaign: Campaign data
            
        Returns:
            Creative recommendation object or None
        """
        # Get ads for this campaign
        ads = self.api_client.get_ads_by_campaign(campaign['id'])
        
        # Get ad insights
        ad_insights = []
        for ad in ads:
            insights = self.api_client.get_ad_insights(ad['id'])
            if insights:
                ad_insights.append({
                    'ad': ad,
                    'insights': insights
                })
                
        # If we don't have enough ads with insights, return None
        if len(ad_insights) < 2:
            return None
            
        # Sort by CTR
        ad_insights.sort(key=lambda x: float(x['insights'].get('ctr', 0)), reverse=True)
        
        # Compare top and bottom performers
        top_performer = ad_insights[0]
        bottom_performer = ad_insights[-1]
        
        # If there's a significant difference in CTR
        top_ctr = float(top_performer['insights'].get('ctr', 0))
        bottom_ctr = float(bottom_performer['insights'].get('ctr', 0))
        
        if top_ctr > bottom_ctr * 2:  # Top performer has 2x better CTR
            return {
                "type": "creative",
                "action": "optimize",
                "top_ad_id": top_performer['ad']['id'],
                "bottom_ad_id": bottom_performer['ad']['id'],
                "message": f"Significant performance difference between ads. Consider pausing underperforming ad {bottom_performer['ad'].get('name', 'Unknown')} and creating variations of top performer {top_performer['ad'].get('name', 'Unknown')}.",
                "confidence": 0.8
            }
            
        return None
        
    def _get_target_cpa(self, campaign_or_ad_set) -> float:
        """
        Get target CPA for a campaign or ad set.
        
        Args:
            campaign_or_ad_set: Campaign or ad set data
            
        Returns:
            Target CPA value
        """
        # Try to get from campaign/ad set data
        target_cpa = campaign_or_ad_set.get('target_cpa')
        if target_cpa:
            return float(target_cpa)
            
        # Default target CPA
        return 50.0  # $50 default target CPA
        
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
            "execution_results": execution_results
        }
        
    def _execute_recommendation(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single recommendation.
        
        Args:
            recommendation: Recommendation object
            
        Returns:
            Execution result object
        """
        rec_type = recommendation.get('type')
        action = recommendation.get('action')
        
        try:
            if rec_type == 'budget' and action in ['increase', 'decrease']:
                # Execute budget change
                campaign_id = recommendation.get('campaign_id')
                new_budget = recommendation.get('recommended_value')
                result = self.api_client.update_campaign_budget(campaign_id, new_budget)
                return {
                    "type": rec_type,
                    "action": action,
                    "status": "success" if result else "failed",
                    "message": f"Budget updated to {new_budget}" if result else "Failed to update budget"
                }
                
            elif rec_type == 'ad_set' and action in ['pause', 'activate']:
                # Execute ad set status change
                ad_set_id = recommendation.get('ad_set_id')
                new_status = 'PAUSED' if action == 'pause' else 'ACTIVE'
                result = self.api_client.update_ad_set_status(ad_set_id, new_status)
                return {
                    "type": rec_type,
                    "action": action,
                    "status": "success" if result else "failed",
                    "message": f"Ad set status updated to {new_status}" if result else "Failed to update ad set status"
                }
                
            elif rec_type == 'bidding' and action in ['change_strategy', 'adjust_cap']:
                # Execute bidding change
                campaign_id = recommendation.get('campaign_id')
                if action == 'change_strategy':
                    new_strategy = recommendation.get('recommended_strategy')
                    new_value = recommendation.get('recommended_value')
                    result = self.api_client.update_campaign_bid_strategy(campaign_id, new_strategy, new_value)
                else:
                    new_cap = recommendation.get('recommended_value')
                    result = self.api_client.update_campaign_bid_amount(campaign_id, new_cap)
                    
                return {
                    "type": rec_type,
                    "action": action,
                    "status": "success" if result else "failed",
                    "message": f"Bidding strategy updated" if result else "Failed to update bidding strategy"
                }
                
            elif rec_type == 'creative' and action == 'optimize':
                # Execute creative optimization
                bottom_ad_id = recommendation.get('bottom_ad_id')
                # Pause underperforming ad
                result = self.api_client.update_ad_status(bottom_ad_id, 'PAUSED')
                return {
                    "type": rec_type,
                    "action": action,
                    "status": "success" if result else "failed",
                    "message": f"Paused underperforming ad" if result else "Failed to pause underperforming ad"
                }
                
            else:
                # Recommendation type or action not supported for automatic execution
                return {
                    "type": rec_type,
                    "action": action,
                    "status": "skipped",
                    "message": f"Recommendation type {rec_type} with action {action} not supported for automatic execution"
                }
                
        except Exception as e:
            logger.error(f"Error executing recommendation: {str(e)}")
            return {
                "type": rec_type,
                "action": action,
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
        campaigns = self.api_client.get_campaigns_by_account(account_id, ['ACTIVE'])
        
        optimization_results = []
        for campaign in campaigns:
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
