"""
Google Ads Reporting Service - REST API Version (Python 3.13 Compatible)
File: app/services/google_ads_reporting.py

Replace your existing google_ads_reporting.py with this version
"""

import requests
from typing import Dict, List, Any, Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleAdsReportingService:
    """Google Ads reporting using direct REST API calls - No SDK required"""
    
    def __init__(self):
        self.developer_token = settings.GOOGLE_ADS_DEVELOPER_TOKEN
        self.client_id = settings.GOOGLE_ADS_CLIENT_ID
        self.client_secret = settings.GOOGLE_ADS_CLIENT_SECRET
        self.refresh_token = settings.GOOGLE_ADS_REFRESH_TOKEN
        self.customer_id = settings.GOOGLE_ADS_CUSTOMER_ID
        self.base_url = "https://googleads.googleapis.com/v16"
        
    
    def _get_access_token(self) -> Optional[str]:
        """Get OAuth access token from refresh token"""
        try:
            url = "https://oauth2.googleapis.com/token"
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            
            return response.json().get('access_token')
            
        except Exception as e:
            logger.error(f"Failed to get Google Ads access token: {str(e)}")
            return None
    
    
    def get_campaign_performance(
        self,
        start_date: str,
        end_date: str,
        campaign_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch campaign performance from Google Ads API
        
        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            campaign_id: Optional specific campaign
        """
        if not all([self.developer_token, self.client_id, self.customer_id]):
            logger.error("Google Ads credentials not configured")
            return self._get_empty_response()
        
        access_token = self._get_access_token()
        if not access_token:
            return self._get_empty_response()
        
        try:
            customer_id_formatted = self.customer_id.replace('-', '')
            url = f"{self.base_url}/customers/{customer_id_formatted}/googleAds:searchStream"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'developer-token': self.developer_token,
                'Content-Type': 'application/json'
            }
            
            # Build query
            campaign_filter = f"AND campaign.id = {campaign_id}" if campaign_id else ""
            
            query = f"""
                SELECT 
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.conversions,
                    metrics.cost_micros,
                    metrics.ctr,
                    metrics.average_cpc,
                    metrics.conversions_value,
                    segments.date
                FROM campaign
                WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                {campaign_filter}
            """
            
            payload = {'query': query}
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            campaigns = self._process_response(data)
            summary = self._calculate_summary(campaigns)
            
            return {
                'success': True,
                'platform': 'google_ads',
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'summary': summary,
                'campaigns': campaigns
            }
            
        except Exception as e:
            logger.error(f"Google Ads API error: {str(e)}")
            return self._get_empty_response()
    
    
    def get_daily_metrics(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Get daily aggregated metrics"""
        access_token = self._get_access_token()
        if not access_token:
            return []
        
        try:
            customer_id_formatted = self.customer_id.replace('-', '')
            url = f"{self.base_url}/customers/{customer_id_formatted}/googleAds:searchStream"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'developer-token': self.developer_token,
                'Content-Type': 'application/json'
            }
            
            query = f"""
                SELECT 
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.conversions,
                    metrics.cost_micros,
                    metrics.conversions_value
                FROM campaign
                WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            """
            
            payload = {'query': query}
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return self._process_daily_data(data)
            
        except Exception as e:
            logger.error(f"Error fetching daily Google Ads metrics: {str(e)}")
            return []
    
    
    def _process_response(self, data: Dict) -> List[Dict[str, Any]]:
        """Process API response into campaign list"""
        campaigns = []
        
        for result in data.get('results', []):
            campaign = result.get('campaign', {})
            metrics = result.get('metrics', {})
            
            campaigns.append({
                'campaign_id': campaign.get('id'),
                'campaign_name': campaign.get('name'),
                'status': campaign.get('status'),
                'impressions': int(metrics.get('impressions', 0)),
                'clicks': int(metrics.get('clicks', 0)),
                'conversions': float(metrics.get('conversions', 0)),
                'cost': float(metrics.get('costMicros', 0)) / 1_000_000,
                'ctr': float(metrics.get('ctr', 0)) * 100,
                'avg_cpc': float(metrics.get('averageCpc', 0)) / 1_000_000,
                'conversions_value': float(metrics.get('conversionsValue', 0))
            })
        
        return campaigns
    
    
    def _process_daily_data(self, data: Dict) -> List[Dict[str, Any]]:
        """Process daily metrics from API response"""
        daily_metrics = {}
        
        for result in data.get('results', []):
            date = result.get('segments', {}).get('date')
            metrics = result.get('metrics', {})
            
            if date not in daily_metrics:
                daily_metrics[date] = {
                    'date': date,
                    'impressions': 0,
                    'clicks': 0,
                    'conversions': 0,
                    'cost': 0,
                    'conversions_value': 0
                }
            
            daily_metrics[date]['impressions'] += int(metrics.get('impressions', 0))
            daily_metrics[date]['clicks'] += int(metrics.get('clicks', 0))
            daily_metrics[date]['conversions'] += float(metrics.get('conversions', 0))
            daily_metrics[date]['cost'] += float(metrics.get('costMicros', 0)) / 1_000_000
            daily_metrics[date]['conversions_value'] += float(metrics.get('conversionsValue', 0))
        
        # Calculate rates
        result = []
        for date, day_data in sorted(daily_metrics.items()):
            ctr = (day_data['clicks'] / day_data['impressions'] * 100) if day_data['impressions'] > 0 else 0
            conv_rate = (day_data['conversions'] / day_data['clicks'] * 100) if day_data['clicks'] > 0 else 0
            roas = (day_data['conversions_value'] / day_data['cost']) if day_data['cost'] > 0 else 0
            
            result.append({
                'date': date,
                'impressions': day_data['impressions'],
                'clicks': day_data['clicks'],
                'conversions': int(day_data['conversions']),
                'cost': round(day_data['cost'], 2),
                'conversions_value': round(day_data['conversions_value'], 2),
                'ctr': round(ctr, 2),
                'conversion_rate': round(conv_rate, 2),
                'roas': round(roas, 2)
            })
        
        return result
    
    
    def _calculate_summary(self, campaigns: List[Dict]) -> Dict[str, Any]:
        """Calculate summary metrics"""
        total_cost = sum(c.get('cost', 0) for c in campaigns)
        total_impressions = sum(c.get('impressions', 0) for c in campaigns)
        total_clicks = sum(c.get('clicks', 0) for c in campaigns)
        total_conversions = sum(c.get('conversions', 0) for c in campaigns)
        total_value = sum(c.get('conversions_value', 0) for c in campaigns)
        
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        conv_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        roas = (total_value / total_cost) if total_cost > 0 else 0
        
        return {
            'total_cost': round(total_cost, 2),
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_conversions': int(total_conversions),
            'total_conversions_value': round(total_value, 2),
            'average_ctr': round(avg_ctr, 2),
            'conversion_rate': round(conv_rate, 2),
            'roas': round(roas, 2)
        }
    
    
    def _get_empty_response(self) -> Dict[str, Any]:
        """Return empty response structure"""
        return {
            'success': False,
            'platform': 'google_ads',
            'error': 'Failed to fetch Google Ads data',
            'summary': {
                'total_cost': 0,
                'total_impressions': 0,
                'total_clicks': 0,
                'total_conversions': 0,
                'total_conversions_value': 0,
                'average_ctr': 0,
                'conversion_rate': 0,
                'roas': 0
            },
            'campaigns': []
        }