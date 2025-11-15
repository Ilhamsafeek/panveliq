"""
Meta Ads Reporting Service - REST API Version (Python 3.13 Compatible)
File: app/services/meta_ads_reporting.py

Replace your existing meta_ads_reporting.py with this version
"""

import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class MetaAdsReportingService:
    """Meta Ads reporting using direct REST API calls - No SDK required"""
    
    def __init__(self):
        self.access_token = settings.META_ACCESS_TOKEN
        self.base_url = "https://graph.facebook.com/v18.0"
        
    
    def get_campaign_performance(
        self,
        ad_account_id: str,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Fetch campaign performance from Meta Ads API
        
        Args:
            ad_account_id: Format 'act_123456789'
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
        """
        if not self.access_token:
            logger.error("Meta access token not configured")
            return self._get_empty_response()
        
        try:
            url = f"{self.base_url}/{ad_account_id}/insights"
            
            params = {
                'access_token': self.access_token,
                'time_range': f'{{"since":"{start_date}","until":"{end_date}"}}',
                'fields': 'campaign_name,campaign_id,impressions,clicks,spend,actions,ctr,cpc',
                'level': 'campaign',
                'limit': 100
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            campaigns = data.get('data', [])
            
            # Calculate summary
            summary = self._calculate_summary(campaigns)
            
            return {
                'success': True,
                'platform': 'meta_ads',
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'summary': summary,
                'campaigns': campaigns
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Meta Ads API error: {str(e)}")
            return self._get_empty_response()
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return self._get_empty_response()
    
    
    def get_daily_metrics(
        self,
        ad_account_id: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Get daily aggregated metrics"""
        try:
            url = f"{self.base_url}/{ad_account_id}/insights"
            
            params = {
                'access_token': self.access_token,
                'time_range': f'{{"since":"{start_date}","until":"{end_date}"}}',
                'fields': 'impressions,clicks,spend,actions,ctr,cpc',
                'time_increment': 1,  # Daily breakdown
                'level': 'account',
                'limit': 100
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            daily_data = []
            
            for day in data.get('data', []):
                conversions = 0
                if 'actions' in day:
                    for action in day['actions']:
                        if action.get('action_type') in ['purchase', 'lead', 'complete_registration']:
                            conversions += int(action.get('value', 0))
                
                spend = float(day.get('spend', 0))
                revenue = conversions * 50  # Assume $50 per conversion
                roas = (revenue / spend) if spend > 0 else 0
                
                daily_data.append({
                    'date': day.get('date_start'),
                    'impressions': int(day.get('impressions', 0)),
                    'clicks': int(day.get('clicks', 0)),
                    'spend': round(spend, 2),
                    'conversions': conversions,
                    'ctr': round(float(day.get('ctr', 0)), 2),
                    'cpc': round(float(day.get('cpc', 0)), 2),
                    'roas': round(roas, 2)
                })
            
            return daily_data
            
        except Exception as e:
            logger.error(f"Error fetching daily metrics: {str(e)}")
            return []
    
    
    def _calculate_summary(self, campaigns: List[Dict]) -> Dict[str, Any]:
        """Calculate summary metrics from campaigns"""
        total_spend = 0
        total_impressions = 0
        total_clicks = 0
        total_conversions = 0
        
        for campaign in campaigns:
            total_spend += float(campaign.get('spend', 0))
            total_impressions += int(campaign.get('impressions', 0))
            total_clicks += int(campaign.get('clicks', 0))
            
            # Extract conversions from actions
            if 'actions' in campaign:
                for action in campaign['actions']:
                    if action.get('action_type') in ['purchase', 'lead', 'complete_registration']:
                        total_conversions += int(action.get('value', 0))
        
        # Calculate derived metrics
        average_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        
        # Calculate ROAS (assuming $50 per conversion for demo)
        revenue = total_conversions * 50
        roas = (revenue / total_spend) if total_spend > 0 else 0
        
        return {
            'total_spend': round(total_spend, 2),
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_conversions': total_conversions,
            'average_ctr': round(average_ctr, 2),
            'conversion_rate': round(conversion_rate, 2),
            'roas': round(roas, 2)
        }
    
    
    def _get_empty_response(self) -> Dict[str, Any]:
        """Return empty response structure"""
        return {
            'success': False,
            'platform': 'meta_ads',
            'error': 'Failed to fetch Meta Ads data',
            'summary': {
                'total_spend': 0,
                'total_impressions': 0,
                'total_clicks': 0,
                'total_conversions': 0,
                'average_ctr': 0,
                'conversion_rate': 0,
                'roas': 0
            },
            'campaigns': []
        }