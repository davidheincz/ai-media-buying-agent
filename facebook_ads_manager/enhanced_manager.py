"""
Enhanced Meta API Client for AI Media Buying Agent

This module provides a robust client for interacting with the Meta Marketing API,
including comprehensive authentication, error handling, and rate limit management.
"""

import os
import time
import json
import logging
import requests
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.adobjects.customaudience import CustomAudience
from facebook_business.adobjects.targetingsearch import TargetingSearch
from facebook_business.exceptions import FacebookRequestError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('meta_api_client')

class MetaAPIError(Exception):
    """Custom exception for Meta API errors with enhanced information."""
    
    def __init__(self, message: str, error_code: Optional[int] = None, 
                 error_subcode: Optional[int] = None, is_transient: bool = False,
                 retry_after: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.is_transient = is_transient
        self.retry_after = retry_after
        super().__init__(self.message)
    
    def __str__(self):
        return f"Meta API Error {self.error_code}.{self.error_subcode}: {self.message}"

class TokenManager:
    """Manages Meta API access tokens, including refresh and validation."""
    
    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None,
                 access_token: Optional[str] = None, token_file_path: Optional[str] = None):
        """
        Initialize the token manager.
        
        Args:
            app_id: Facebook App ID
            app_secret: Facebook App Secret
            access_token: Initial access token
            token_file_path: Path to store token information
        """
        self.app_id = app_id or os.environ.get('FACEBOOK_APP_ID')
        self.app_secret = app_secret or os.environ.get('FACEBOOK_APP_SECRET')
        self.access_token = access_token or os.environ.get('FACEBOOK_ACCESS_TOKEN')
        self.token_file_path = token_file_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'token_info.json'
        )
        self.token_expiry = None
        self.load_token_info()
    
    def load_token_info(self) -> None:
        """Load token information from file if available."""
        try:
            if os.path.exists(self.token_file_path):
                with open(self.token_file_path, 'r') as f:
                    token_info = json.load(f)
                    self.access_token = token_info.get('access_token', self.access_token)
                    expiry_str = token_info.get('expiry')
                    if expiry_str:
                        self.token_expiry = datetime.fromisoformat(expiry_str)
                    logger.info("Loaded token information from file")
        except Exception as e:
            logger.warning(f"Failed to load token information: {str(e)}")
    
    def save_token_info(self) -> None:
        """Save token information to file."""
        try:
            token_info = {
                'access_token': self.access_token,
                'expiry': self.token_expiry.isoformat() if self.token_expiry else None
            }
            with open(self.token_file_path, 'w') as f:
                json.dump(token_info, f)
            logger.info("Saved token information to file")
        except Exception as e:
            logger.warning(f"Failed to save token information: {str(e)}")
    
    def get_long_lived_token(self, short_lived_token: Optional[str] = None) -> str:
        """
        Exchange a short-lived token for a long-lived token.
        
        Args:
            short_lived_token: Short-lived access token
            
        Returns:
            Long-lived access token
        """
        token_to_exchange = short_lived_token or self.access_token
        if not token_to_exchange:
            raise MetaAPIError("No access token available for exchange")
        
        if not self.app_id or not self.app_secret:
            raise MetaAPIError("App ID and App Secret are required for token exchange")
        
        try:
            url = f"https://graph.facebook.com/v18.0/oauth/access_token"
            params = {
                'grant_type': 'fb_exchange_token',
                'client_id': self.app_id,
                'client_secret': self.app_secret,
                'fb_exchange_token': token_to_exchange
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'access_token' not in data:
                raise MetaAPIError("Failed to get long-lived token: No token in response")
            
            self.access_token = data['access_token']
            # Long-lived tokens typically last 60 days
            self.token_expiry = datetime.now() + timedelta(days=60)
            self.save_token_info()
            
            logger.info("Successfully obtained long-lived token")
            return self.access_token
        
        except requests.RequestException as e:
            logger.error(f"Failed to exchange token: {str(e)}")
            raise MetaAPIError(f"Failed to exchange token: {str(e)}")
    
    def is_token_valid(self) -> bool:
        """Check if the current token is valid and not expired."""
        if not self.access_token:
            return False
        
        if self.token_expiry and self.token_expiry > datetime.now() + timedelta(days=5):
            # Token is still valid for more than 5 days
            return True
        
        try:
            # Verify token by making a simple API call
            url = f"https://graph.facebook.com/v18.0/debug_token"
            params = {
                'input_token': self.access_token,
                'access_token': f"{self.app_id}|{self.app_secret}"
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('data', {}).get('is_valid', False):
                expires_at = data.get('data', {}).get('expires_at')
                if expires_at:
                    self.token_expiry = datetime.fromtimestamp(expires_at)
                    self.save_token_info()
                return True
            return False
        
        except Exception as e:
            logger.warning(f"Failed to verify token: {str(e)}")
            return False
    
    def get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if not self.is_token_valid():
            if self.access_token:
                logger.info("Token invalid or expiring soon, attempting to refresh")
                return self.get_long_lived_token()
            else:
                raise MetaAPIError("No access token available and no way to obtain one")
        
        return self.access_token

class MetaAPIClient:
    """
    Enhanced client for interacting with the Meta Marketing API.
    
    Features:
    - Robust authentication with token management
    - Comprehensive error handling and retry logic
    - Rate limit management
    - Support for all required API endpoints
    """
    
    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None,
                 access_token: Optional[str] = None, token_file_path: Optional[str] = None,
                 max_retries: int = 5, retry_delay: int = 30):
        """
        Initialize the Meta API client.
        
        Args:
            app_id: Facebook App ID
            app_secret: Facebook App Secret
            access_token: Initial access token
            token_file_path: Path to store token information
            max_retries: Maximum number of retries for API calls
            retry_delay: Base delay between retries in seconds
        """
        self.token_manager = TokenManager(
            app_id=app_id,
            app_secret=app_secret,
            access_token=access_token,
            token_file_path=token_file_path
        )
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.api_instance = None
        self.initialize_api()
    
    def initialize_api(self) -> None:
        """Initialize the Facebook Ads API with a valid token."""
        try:
            access_token = self.token_manager.get_valid_token()
            self.api_instance = FacebookAdsApi.init(access_token=access_token)
            logger.info("Successfully initialized Facebook Ads API")
        except Exception as e:
            logger.error(f"Failed to initialize Facebook Ads API: {str(e)}")
            raise MetaAPIError(f"Failed to initialize Facebook Ads API: {str(e)}")
    
    def handle_api_error(self, error: FacebookRequestError, retry_count: int) -> bool:
        """
        Handle Facebook API errors and determine if retry is appropriate.
        
        Args:
            error: The Facebook request error
            retry_count: Current retry count
            
        Returns:
            True if should retry, False otherwise
        """
        error_code = error.api_error_code()
        error_subcode = error.api_error_subcode()
        error_message = error.api_error_message()
        
        # Check if we've exceeded max retries
        if retry_count >= self.max_retries:
            logger.warning(f"Max retries ({self.max_retries}) exceeded for API call")
            return False
        
        # Handle rate limiting errors
        if error_code == 4 or error_code == 17 or error_code == 32 or error_code == 613:
            retry_after = error.headers().get('Retry-After', self.retry_delay)
            try:
                retry_after = int(retry_after)
            except (ValueError, TypeError):
                retry_after = self.retry_delay
            
            logger.info(f"Rate limited. Waiting {retry_after} seconds before retry.")
            time.sleep(retry_after)
            return True
        
        # Handle authentication errors
        if error_code == 190:  # Invalid OAuth access token
            logger.info("Invalid access token. Attempting to refresh.")
            try:
                self.token_manager.get_long_lived_token()
                self.initialize_api()
                return True
            except Exception as e:
                logger.error(f"Failed to refresh token: {str(e)}")
                return False
        
        # Handle transient errors
        transient_error_codes = [1, 2, 4, 17, 341, 368]
        if error_code in transient_error_codes:
            wait_time = self.retry_delay * (2 ** retry_count)  # Exponential backoff
            logger.info(f"Transient error {error_code}. Waiting {wait_time} seconds before retry.")
            time.sleep(wait_time)
            return True
        
        # Non-retryable errors
        logger.error(f"Non-retryable error {error_code}.{error_subcode}: {error_message}")
        return False
    
    def api_call(self, func, *args, **kwargs):
        """
        Make an API call with retry logic.
        
        Args:
            func: Function to call
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            API call result
        """
        retry_count = 0
        
        while True:
            try:
                return func(*args, **kwargs)
            
            except FacebookRequestError as e:
                logger.warning(f"API error: {e.api_error_code()}.{e.api_error_subcode()} - {e.api_error_message()}")
                
                if self.handle_api_error(e, retry_count):
                    retry_count += 1
                    continue
                
                # Convert to our custom error format
                raise MetaAPIError(
                    message=e.api_error_message(),
                    error_code=e.api_error_code(),
                    error_subcode=e.api_error_subcode(),
                    is_transient=e.api_error_code() in [1, 2, 4, 17, 341, 368]
                )
            
            except Exception as e:
                logger.error(f"Unexpected error in API call: {str(e)}")
                raise MetaAPIError(f"Unexpected error in API call: {str(e)}")
    
    def get_ad_account(self, ad_account_id: str) -> AdAccount:
        """
        Get an Ad Account object.
        
        Args:
            ad_account_id: Ad Account ID (with or without 'act_' prefix)
            
        Returns:
            AdAccount object
        """
        # Ensure ad_account_id has 'act_' prefix
        if not ad_account_id.startswith('act_'):
            ad_account_id = f'act_{ad_account_id}'
        
        return self.api_call(lambda: AdAccount(ad_account_id))
    
    def get_ad_accounts(self, user_id: str = 'me') -> List[Dict[str, Any]]:
        """
        Get all Ad Accounts accessible to a user.
        
        Args:
            user_id: User ID or 'me' for the current user
            
        Returns:
            List of Ad Account information
        """
        from facebook_business.adobjects.user import User
        
        user = User(user_id)
        fields = [
            'id',
            'name',
            'account_id',
            'account_status',
            'age',
            'amount_spent',
            'balance',
            'currency',
            'business_name',
            'timezone_name'
        ]
        
        accounts = self.api_call(
            lambda: user.get_ad_accounts(fields=fields)
        )
        
        return [account.export_all_data() for account in accounts]
    
    def get_campaigns(self, ad_account_id: str, 
                     status_filter: Optional[List[str]] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get campaigns for an Ad Account.
        
        Args:
            ad_account_id: Ad Account ID
            status_filter: Optional list of statuses to filter by
            limit: Maximum number of campaigns to return
            
        Returns:
            List of campaign information
        """
        ad_account = self.get_ad_account(ad_account_id)
        
        params = {
            'limit': limit
        }
        
        if status_filter:
            params['effective_status'] = status_filter
        
        fields = [
            'id',
            'name',
            'objective',
            'status',
            'effective_status',
            'daily_budget',
            'lifetime_budget',
            'budget_remaining',
            'buying_type',
            'bid_strategy',
            'pacing_type',
            'special_ad_categories',
            'start_time',
            'stop_time',
            'created_time',
            'updated_time'
        ]
        
        campaigns = self.api_call(
            lambda: ad_account.get_campaigns(fields=fields, params=params)
        )
        
        return [campaign.export_all_data() for campaign in campaigns]
    
    def get_campaign(self, ad_account_id: str, campaign_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific campaign.
        
        Args:
            ad_account_id: Ad Account ID
            campaign_id: Campaign ID
            
        Returns:
            Campaign information
        """
        campaign = Campaign(campaign_id)
        
        fields = [
            'id',
            'name',
            'objective',
            'status',
            'effective_status',
            'daily_budget',
            'lifetime_budget',
            'budget_remaining',
            'buying_type',
            'bid_strategy',
            'pacing_type',
            'special_ad_categories',
            'start_time',
            'stop_time',
            'created_time',
            'updated_time',
            'spend_cap',
            'source_campaign_id'
        ]
        
        campaign_data = self.api_call(
            lambda: campaign.api_get(fields=fields)
        )
        
        return campaign_data.export_all_data()
    
    def create_campaign(self, ad_account_id: str, name: str, objective: str,
                       status: str = 'PAUSED', daily_budget: Optional[float] = None,
                       lifetime_budget: Optional[float] = None,
                       bid_strategy: Optional[str] = None,
                       special_ad_categories: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a new campaign.
        
        Args:
            ad_account_id: Ad Account ID
            name: Campaign name
            objective: Campaign objective (e.g., 'CONVERSIONS', 'REACH')
            status: Initial campaign status
            daily_budget: Daily budget in account currency
            lifetime_budget: Lifetime budget in account currency
            bid_strategy: Bid strategy (e.g., 'LOWEST_COST_WITHOUT_CAP')
            special_ad_categories: List of special ad categories
            
        Returns:
            Created campaign information
        """
        ad_account = self.get_ad_account(ad_account_id)
        
        params = {
            'name': name,
            'objective': objective,
            'status': status,
            'special_ad_categories': special_ad_categories or []
        }
        
        if daily_budget:
            # Convert to cents/smallest currency unit
            params['daily_budget'] = int(daily_budget * 100)
        
        if lifetime_budget:
            # Convert to cents/smallest currency unit
            params['lifetime_budget'] = int(lifetime_budget * 100)
        
        if bid_strategy:
            params['bid_strategy'] = bid_strategy
        
        campaign = self.api_call(
            lambda: ad_account.create_campaign(params=params)
        )
        
        # Get the created campaign details
        return self.get_campaign(ad_account_id, campaign['id'])
    
    def update_campaign(self, campaign_id: str, 
                       name: Optional[str] = None,
                       status: Optional[str] = None,
                       daily_budget: Optional[float] = None,
                       lifetime_budget: Optional[float] = None,
                       bid_strategy: Optional[str] = None) -> Dict[str, Any]:
        """
        Update an existing campaign.
        
        Args:
            campaign_id: Campaign ID
            name: New campaign name
            status: New campaign status
            daily_budget: New daily budget in account currency
            lifetime_budget: New lifetime budget in account currency
            bid_strategy: New bid strategy
            
        Returns:
            Updated campaign information
        """
        campaign = Campaign(campaign_id)
        
        params = {}
        
        if name:
            params['name'] = name
        
        if status:
            params['status'] = status
        
        if daily_budget:
            # Convert to cents/smallest currency unit
            params['daily_budget'] = int(daily_budget * 100)
        
        if lifetime_budget:
            # Convert to cents/smallest currency unit
            params['lifetime_budget'] = int(lifetime_budget * 100)
        
        if bid_strategy:
            params['bid_strategy'] = bid_strategy
        
        self.api_call(
            lambda: campaign.api_update(params=params)
        )
        
        # Get the updated campaign details
        return self.get_campaign('', campaign_id)  # Ad account ID not needed for getting campaign by ID
    
    def get_ad_sets(self, campaign_id: str, 
                   status_filter: Optional[List[str]] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get ad sets for a campaign.
        
        Args:
            campaign_id: Campaign ID
            status_filter: Optional list of statuses to filter by
            limit: Maximum number of ad sets to return
            
        Returns:
            List of ad set information
        """
        campaign = Campaign(campaign_id)
        
        params = {
            'limit': limit
        }
        
        if status_filter:
            params['effective_status'] = status_filter
        
        fields = [
            'id',
            'name',
            'status',
            'effective_status',
            'daily_budget',
            'lifetime_budget',
            'budget_remaining',
            'bid_amount',
            'bid_strategy',
            'billing_event',
            'optimization_goal',
            'targeting',
            'promoted_object',
            'pacing_type',
            'start_time',
            'end_time',
            'created_time',
            'updated_time'
        ]
        
        ad_sets = self.api_call(
            lambda: campaign.get_ad_sets(fields=fields, params=params)
        )
        
        return [ad_set.export_all_data() for ad_set in ad_sets]
    
    def get_ad_set(self, ad_set_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific ad set.
        
        Args:
            ad_set_id: Ad Set ID
            
        Returns:
            Ad Set information
        """
        ad_set = AdSet(ad_set_id)
        
        fields = [
            'id',
            'name',
            'status',
            'effective_status',
            'daily_budget',
            'lifetime_budget',
            'budget_remaining',
            'bid_amount',
            'bid_strategy',
            'billing_event',
            'optimization_goal',
            'targeting',
            'promoted_object',
            'pacing_type',
            'start_time',
            'end_time',
            'created_time',
            'updated_time',
            'campaign_id',
            'source_adset_id'
        ]
        
        ad_set_data = self.api_call(
            lambda: ad_set.api_get(fields=fields)
        )
        
        return ad_set_data.export_all_data()
    
    def create_ad_set(self, ad_account_id: str, campaign_id: str, name: str,
                     optimization_goal: str, billing_event: str,
                     bid_amount: Optional[float] = None,
                     daily_budget: Optional[float] = None,
                     lifetime_budget: Optional[float] = None,
                     targeting: Optional[Dict[str, Any]] = None,
                     status: str = 'PAUSED',
                     start_time: Optional[str] = None,
                     end_time: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new ad set.
        
        Args:
            ad_account_id: Ad Account ID
            campaign_id: Campaign ID
            name: Ad Set name
            optimization_goal: Optimization goal (e.g., 'REACH', 'LINK_CLICKS')
            billing_event: Billing event (e.g., 'IMPRESSIONS', 'LINK_CLICKS')
            bid_amount: Bid amount in account currency
            daily_budget: Daily budget in account currency
            lifetime_budget: Lifetime budget in account currency
            targeting: Targeting specification
            status: Initial ad set status
            start_time: Start time in ISO format
            end_time: End time in ISO format
            
        Returns:
            Created ad set information
        """
        ad_account = self.get_ad_account(ad_account_id)
        
        params = {
            'name': name,
            'campaign_id': campaign_id,
            'optimization_goal': optimization_goal,
            'billing_event': billing_event,
            'status': status
        }
        
        if bid_amount:
            # Convert to cents/smallest currency unit
            params['bid_amount'] = int(bid_amount * 100)
        
        if daily_budget:
            # Convert to cents/smallest currency unit
            params['daily_budget'] = int(daily_budget * 100)
        
        if lifetime_budget:
            # Convert to cents/smallest currency unit
            params['lifetime_budget'] = int(lifetime_budget * 100)
        
        if targeting:
            params['targeting'] = targeting
        
        if start_time:
            params['start_time'] = start_time
        
        if end_time:
            params['end_time'] = end_time
        
        ad_set = self.api_call(
            lambda: ad_account.create_ad_set(params=params)
        )
        
        # Get the created ad set details
        return self.get_ad_set(ad_set['id'])
    
    def update_ad_set(self, ad_set_id: str,
                     name: Optional[str] = None,
                     status: Optional[str] = None,
                     daily_budget: Optional[float] = None,
                     lifetime_budget: Optional[float] = None,
                     bid_amount: Optional[float] = None,
                     targeting: Optional[Dict[str, Any]] = None,
                     end_time: Optional[str] = None) -> Dict[str, Any]:
        """
        Update an existing ad set.
        
        Args:
            ad_set_id: Ad Set ID
            name: New ad set name
            status: New ad set status
            daily_budget: New daily budget in account currency
            lifetime_budget: New lifetime budget in account currency
            bid_amount: New bid amount in account currency
            targeting: New targeting specification
            end_time: New end time in ISO format
            
        Returns:
            Updated ad set information
        """
        ad_set = AdSet(ad_set_id)
        
        params = {}
        
        if name:
            params['name'] = name
        
        if status:
            params['status'] = status
        
        if daily_budget:
            # Convert to cents/smallest currency unit
            params['daily_budget'] = int(daily_budget * 100)
        
        if lifetime_budget:
            # Convert to cents/smallest currency unit
            params['lifetime_budget'] = int(lifetime_budget * 100)
        
        if bid_amount:
            # Convert to cents/smallest currency unit
            params['bid_amount'] = int(bid_amount * 100)
        
        if targeting:
            params['targeting'] = targeting
        
        if end_time:
            params['end_time'] = end_time
        
        self.api_call(
            lambda: ad_set.api_update(params=params)
        )
        
        # Get the updated ad set details
        return self.get_ad_set(ad_set_id)
    
    def get_ads(self, ad_set_id: str,
               status_filter: Optional[List[str]] = None,
               limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get ads for an ad set.
        
        Args:
            ad_set_id: Ad Set ID
            status_filter: Optional list of statuses to filter by
            limit: Maximum number of ads to return
            
        Returns:
            List of ad information
        """
        ad_set = AdSet(ad_set_id)
        
        params = {
            'limit': limit
        }
        
        if status_filter:
            params['effective_status'] = status_filter
        
        fields = [
            'id',
            'name',
            'status',
            'effective_status',
            'adset_id',
            'campaign_id',
            'creative',
            'created_time',
            'updated_time'
        ]
        
        ads = self.api_call(
            lambda: ad_set.get_ads(fields=fields, params=params)
        )
        
        return [ad.export_all_data() for ad in ads]
    
    def get_ad(self, ad_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific ad.
        
        Args:
            ad_id: Ad ID
            
        Returns:
            Ad information
        """
        ad = Ad(ad_id)
        
        fields = [
            'id',
            'name',
            'status',
            'effective_status',
            'adset_id',
            'campaign_id',
            'creative',
            'created_time',
            'updated_time',
            'tracking_specs',
            'conversion_domain',
            'adlabels'
        ]
        
        ad_data = self.api_call(
            lambda: ad.api_get(fields=fields)
        )
        
        return ad_data.export_all_data()
    
    def create_ad(self, ad_account_id: str, ad_set_id: str, name: str,
                 creative_id: str, status: str = 'PAUSED',
                 tracking_specs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Create a new ad.
        
        Args:
            ad_account_id: Ad Account ID
            ad_set_id: Ad Set ID
            name: Ad name
            creative_id: Creative ID
            status: Initial ad status
            tracking_specs: Tracking specifications
            
        Returns:
            Created ad information
        """
        ad_account = self.get_ad_account(ad_account_id)
        
        params = {
            'name': name,
            'adset_id': ad_set_id,
            'creative': {'creative_id': creative_id},
            'status': status
        }
        
        if tracking_specs:
            params['tracking_specs'] = tracking_specs
        
        ad = self.api_call(
            lambda: ad_account.create_ad(params=params)
        )
        
        # Get the created ad details
        return self.get_ad(ad['id'])
    
    def update_ad(self, ad_id: str,
                 name: Optional[str] = None,
                 status: Optional[str] = None,
                 creative_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Update an existing ad.
        
        Args:
            ad_id: Ad ID
            name: New ad name
            status: New ad status
            creative_id: New creative ID
            
        Returns:
            Updated ad information
        """
        ad = Ad(ad_id)
        
        params = {}
        
        if name:
            params['name'] = name
        
        if status:
            params['status'] = status
        
        if creative_id:
            params['creative'] = {'creative_id': creative_id}
        
        self.api_call(
            lambda: ad.api_update(params=params)
        )
        
        # Get the updated ad details
        return self.get_ad(ad_id)
    
    def get_campaign_insights(self, campaign_id: str,
                             time_range: Optional[Dict[str, str]] = None,
                             time_increment: Optional[int] = None,
                             fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get performance insights for a campaign.
        
        Args:
            campaign_id: Campaign ID
            time_range: Time range dictionary with 'since' and 'until' dates in YYYY-MM-DD format
            time_increment: Time increment in days (1, 7, etc.)
            fields: List of fields to retrieve
            
        Returns:
            List of insight data
        """
        campaign = Campaign(campaign_id)
        
        if not fields:
            fields = [
                'campaign_id',
                'campaign_name',
                'impressions',
                'clicks',
                'spend',
                'reach',
                'frequency',
                'cpc',
                'cpm',
                'ctr',
                'cost_per_inline_link_click',
                'cost_per_inline_post_engagement',
                'actions',
                'action_values',
                'conversions',
                'cost_per_action_type',
                'cost_per_conversion'
            ]
        
        params = {}
        
        if time_range:
            params['time_range'] = time_range
        
        if time_increment:
            params['time_increment'] = time_increment
        
        insights = self.api_call(
            lambda: campaign.get_insights(fields=fields, params=params)
        )
        
        return [insight.export_all_data() for insight in insights]
    
    def get_ad_set_insights(self, ad_set_id: str,
                           time_range: Optional[Dict[str, str]] = None,
                           time_increment: Optional[int] = None,
                           fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get performance insights for an ad set.
        
        Args:
            ad_set_id: Ad Set ID
            time_range: Time range dictionary with 'since' and 'until' dates in YYYY-MM-DD format
            time_increment: Time increment in days (1, 7, etc.)
            fields: List of fields to retrieve
            
        Returns:
            List of insight data
        """
        ad_set = AdSet(ad_set_id)
        
        if not fields:
            fields = [
                'adset_id',
                'adset_name',
                'campaign_id',
                'campaign_name',
                'impressions',
                'clicks',
                'spend',
                'reach',
                'frequency',
                'cpc',
                'cpm',
                'ctr',
                'cost_per_inline_link_click',
                'cost_per_inline_post_engagement',
                'actions',
                'action_values',
                'conversions',
                'cost_per_action_type',
                'cost_per_conversion'
            ]
        
        params = {}
        
        if time_range:
            params['time_range'] = time_range
        
        if time_increment:
            params['time_increment'] = time_increment
        
        insights = self.api_call(
            lambda: ad_set.get_insights(fields=fields, params=params)
        )
        
        return [insight.export_all_data() for insight in insights]
    
    def get_ad_insights(self, ad_id: str,
                       time_range: Optional[Dict[str, str]] = None,
                       time_increment: Optional[int] = None,
                       fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get performance insights for an ad.
        
        Args:
            ad_id: Ad ID
            time_range: Time range dictionary with 'since' and 'until' dates in YYYY-MM-DD format
            time_increment: Time increment in days (1, 7, etc.)
            fields: List of fields to retrieve
            
        Returns:
            List of insight data
        """
        ad = Ad(ad_id)
        
        if not fields:
            fields = [
                'ad_id',
                'ad_name',
                'adset_id',
                'adset_name',
                'campaign_id',
                'campaign_name',
                'impressions',
                'clicks',
                'spend',
                'reach',
                'frequency',
                'cpc',
                'cpm',
                'ctr',
                'cost_per_inline_link_click',
                'cost_per_inline_post_engagement',
                'actions',
                'action_values',
                'conversions',
                'cost_per_action_type',
                'cost_per_conversion'
            ]
        
        params = {}
        
        if time_range:
            params['time_range'] = time_range
        
        if time_increment:
            params['time_increment'] = time_increment
        
        insights = self.api_call(
            lambda: ad.get_insights(fields=fields, params=params)
        )
        
        return [insight.export_all_data() for insight in insights]
    
    def create_custom_audience(self, ad_account_id: str, name: str, description: str,
                              customer_file_source: str = 'USER_PROVIDED_ONLY',
                              subtype: str = 'CUSTOM',
                              retention_days: int = 180) -> Dict[str, Any]:
        """
        Create a new custom audience.
        
        Args:
            ad_account_id: Ad Account ID
            name: Audience name
            description: Audience description
            customer_file_source: Source of the customer file
            subtype: Audience subtype
            retention_days: Number of days to retain audience
            
        Returns:
            Created audience information
        """
        ad_account = self.get_ad_account(ad_account_id)
        
        params = {
            'name': name,
            'description': description,
            'customer_file_source': customer_file_source,
            'subtype': subtype,
            'retention_days': retention_days
        }
        
        audience = self.api_call(
            lambda: ad_account.create_custom_audience(params=params)
        )
        
        return audience.export_all_data()
    
    def add_users_to_custom_audience(self, audience_id: str, schema: List[str],
                                    data: List[List[str]]) -> Dict[str, Any]:
        """
        Add users to a custom audience.
        
        Args:
            audience_id: Custom Audience ID
            schema: List of field types (e.g., ['EMAIL', 'PHONE', 'FIRST_NAME'])
            data: List of user data rows matching the schema
            
        Returns:
            Result of the operation
        """
        audience = CustomAudience(audience_id)
        
        params = {
            'schema': schema,
            'data': data
        }
        
        result = self.api_call(
            lambda: audience.add_users(params=params)
        )
        
        return result
    
    def create_lookalike_audience(self, ad_account_id: str, name: str, 
                                 source_audience_id: str, description: str = '',
                                 lookalike_spec: Optional[Dict[str, Any]] = None,
                                 retention_days: int = 180) -> Dict[str, Any]:
        """
        Create a lookalike audience based on a source audience.
        
        Args:
            ad_account_id: Ad Account ID
            name: Audience name
            source_audience_id: Source Custom Audience ID
            description: Audience description
            lookalike_spec: Lookalike specification
            retention_days: Number of days to retain audience
            
        Returns:
            Created audience information
        """
        ad_account = self.get_ad_account(ad_account_id)
        
        if not lookalike_spec:
            lookalike_spec = {
                'origin_audience_id': source_audience_id,
                'type': 'similarity',
                'starting_ratio': 0.01,
                'ratio': 0.05,
                'country': 'US'
            }
        
        params = {
            'name': name,
            'description': description,
            'subtype': 'LOOKALIKE',
            'lookalike_spec': lookalike_spec,
            'retention_days': retention_days
        }
        
        audience = self.api_call(
            lambda: ad_account.create_custom_audience(params=params)
        )
        
        return audience.export_all_data()
    
    def search_targeting(self, q: str, type: str, 
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search for targeting options.
        
        Args:
            q: Search query
            type: Type of targeting (e.g., 'adinterest', 'adeducationschool')
            limit: Maximum number of results to return
            
        Returns:
            List of targeting options
        """
        params = {
            'q': q,
            'type': type,
            'limit': limit
        }
        
        results = self.api_call(
            lambda: TargetingSearch.search(params=params)
        )
        
        return results
    
    def get_targeting_browse(self, type: str) -> List[Dict[str, Any]]:
        """
        Browse targeting categories.
        
        Args:
            type: Type of targeting category
            
        Returns:
            List of targeting categories
        """
        params = {
            'type': type
        }
        
        results = self.api_call(
            lambda: TargetingSearch.browse(params=params)
        )
        
        return results
