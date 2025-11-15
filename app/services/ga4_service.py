"""
Google Analytics 4 API Service
File: app/services/ga4_service.py
"""

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account
from datetime import date, timedelta
from typing import Dict, Any
import json

from app.core.config import settings


class GA4Service:
    def __init__(self):
        self.property_id = settings.GA4_PROPERTY_ID
        self.credentials_path = settings.GA4_CREDENTIALS_JSON
        self.client = None
        
        if self.credentials_path:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                self.client = BetaAnalyticsDataClient(credentials=credentials)
            except Exception as e:
                print(f"GA4 initialization error: {e}")
    
    async def get_metrics(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Get Google Analytics 4 metrics
        """
        if not self.client or not self.property_id:
            return self._get_mock_data()
        
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat()
                )],
                dimensions=[
                    Dimension(name="date"),
                ],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="totalUsers"),
                    Metric(name="newUsers"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="conversions"),
                ],
            )
            
            response = self.client.run_report(request)
            
            return self._parse_response(response)
            
        except Exception as e:
            print(f"GA4 API error: {e}")
            return self._get_mock_data()
    
    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse GA4 API response"""
        metrics_data = []
        
        for row in response.rows:
            date_val = row.dimension_values[0].value
            metrics = row.metric_values
            
            metrics_data.append({
                "metric_date": date_val,
                "page_views": int(metrics[0].value) if metrics[0].value else 0,
                "unique_visitors": int(metrics[1].value) if metrics[1].value else 0,
                "new_users": int(metrics[2].value) if metrics[2].value else 0,
                "bounce_rate": float(metrics[3].value) if metrics[3].value else 0.0,
                "avg_session_duration": float(metrics[4].value) if metrics[4].value else 0.0,
                "conversion_events": int(metrics[5].value) if metrics[5].value else 0,
            })
        
        return {
            "success": True,
            "data": metrics_data
        }
    
    def _get_mock_data(self) -> Dict[str, Any]:
        """Return mock data when API is not configured"""
        return {
            "success": False,
            "data": [],
            "message": "GA4 API not configured"
        }


# Create singleton instance
ga4_service = GA4Service()