"""
Meta Ads Reporting API Service
File: app/services/meta_ads_service.py
"""

import requests
from datetime import date
from typing import Dict, Any, List

from app.core.config import settings


class MetaAdsService:
    def __init__(self):
        self.access_token = settings.META_ACCESS_TOKEN
        self.ad_account_id = getattr(settings, 'META_AD_ACCOUNT_ID', None)
        self.base_url = "https://graph.facebook.com/v18.0"
    
    async def get_campaign_insights(
        self,
        start_date: date,
        end_date: date,
        campaign_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get Meta Ads campaign insights
        """
        if not self.access_token or not self.ad_account_id:
            return self._get_mock_data()
        
        try:
            url = f"{self.base_url}/{self.ad_account_id}/insights"
            
            params = {
                "access_token": self.access_token,
                "time_range": json.dumps({
                    "since": start_date.isoformat(),
                    "until": end_date.isoformat()
                }),
                "fields": ",".join([
                    "campaign_id",
                    "campaign_name",
                    "impressions",
                    "clicks",
                    "spend",
                    "conversions",
                    "ctr",
                    "cpc",
                    "cpp",
                    "actions",
                    "cost_per_action_type"
                ]),
                "level": "campaign",
                "limit": 100
            }
            
            if campaign_ids:
                params["filtering"] = json.dumps([{
                    "field": "campaign.id",
                    "operator": "IN",
                    "value": campaign_ids
                }])
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            return self._parse_insights(data)
            
        except Exception as e:
            print(f"Meta Ads API error: {e}")
            return self._get_mock_data()
    
    def _parse_insights(self, data: Dict) -> Dict[str, Any]:
        """Parse Meta Ads API response"""
        campaigns = []
        
        for insight in data.get('data', []):
            # Extract conversions from actions
            conversions = 0
            if 'actions' in insight:
                for action in insight['actions']:
                    if action.get('action_type') in ['purchase', 'lead', 'complete_registration']:
                        conversions += int(action.get('value', 0))
            
            # Calculate ROAS
            spend = float(insight.get('spend', 0))
            roas = (conversions * 100 / spend) if spend > 0 else 0  # Assuming $100 per conversion
            
            campaigns.append({
                "campaign_id": insight.get('campaign_id'),
                "campaign_name": insight.get('campaign_name'),
                "impressions": int(insight.get('impressions', 0)),
                "clicks": int(insight.get('clicks', 0)),
                "spend": spend,
                "conversions": conversions,
                "ctr": float(insight.get('ctr', 0)),
                "cpc": float(insight.get('cpc', 0)),
                "roas": round(roas, 2)
            })
        
        return {
            "success": True,
            "campaigns": campaigns
        }
    
    def _get_mock_data(self) -> Dict[str, Any]:
        """Return mock data when API is not configured"""
        return {
            "success": False,
            "campaigns": [],
            "message": "Meta Ads API not configured"
        }


# Create singleton instance
meta_ads_service = MetaAdsService()