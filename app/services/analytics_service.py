"""
Google Analytics 4 Service
File: app/services/google_analytics_service.py
Fetches real analytics data from GA4 using service account authentication
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    OrderBy
)
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class GoogleAnalyticsService:
    """Service for fetching data from Google Analytics 4"""
    
    def __init__(self, credentials_path: str = None, property_id: str = None):
        """
        Initialize GA4 service with credentials
        
        Args:
            credentials_path: Path to service account JSON file
            property_id: GA4 Property ID (e.g., "507575931")
        """
        self.credentials_path = credentials_path or os.getenv(
            'GA4_CREDENTIALS_PATH', 
            'app/config/ga4_credentials.json'
        )
        self.property_id = property_id or os.getenv('GA4_PROPERTY_ID', '507575931')
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the GA4 API client with service account credentials"""
        try:
            if os.path.exists(self.credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/analytics.readonly']
                )
                self.client = BetaAnalyticsDataClient(credentials=credentials)
                logger.info("GA4 client initialized successfully")
            else:
                logger.warning(f"GA4 credentials file not found: {self.credentials_path}")
                self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize GA4 client: {str(e)}")
            self.client = None
    
    def get_analytics_data(
        self,
        property_id: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive analytics data from GA4
        
        Args:
            property_id: GA4 Property ID (uses default if not provided)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dictionary with analytics data and success status
        """
        if not self.client:
            return self._get_empty_response("GA4 client not initialized")
        
        property_id = property_id or self.property_id
        
        # Default to last 30 days
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        try:
            # Fetch daily metrics
            daily_data = self._fetch_daily_metrics(property_id, start_date, end_date)
            
            # Fetch traffic sources
            traffic_sources = self._fetch_traffic_sources(property_id, start_date, end_date)
            
            # Fetch top pages
            top_pages = self._fetch_top_pages(property_id, start_date, end_date)
            
            # Calculate summary
            summary = self._calculate_summary(daily_data)
            
            return {
                "success": True,
                "property_id": property_id,
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "summary": summary,
                "daily_data": daily_data,
                "traffic_sources": traffic_sources,
                "top_pages": top_pages
            }
            
        except Exception as e:
            logger.error(f"Error fetching GA4 data: {str(e)}")
            return self._get_empty_response(str(e))
    
    def _fetch_daily_metrics(
        self, 
        property_id: str, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Fetch daily metrics from GA4"""
        try:
            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="date")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="totalUsers"),
                    Metric(name="newUsers"),
                    Metric(name="screenPageViews"),
                    Metric(name="bounceRate"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="conversions"),
                    Metric(name="engagedSessions")
                ],
                order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))]
            )
            
            response = self.client.run_report(request)
            
            daily_data = []
            for row in response.rows:
                date_str = row.dimension_values[0].value
                # Convert YYYYMMDD to YYYY-MM-DD
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                daily_data.append({
                    "date": formatted_date,
                    "sessions": int(row.metric_values[0].value or 0),
                    "users": int(row.metric_values[1].value or 0),
                    "new_users": int(row.metric_values[2].value or 0),
                    "page_views": int(row.metric_values[3].value or 0),
                    "bounce_rate": round(float(row.metric_values[4].value or 0) * 100, 2),
                    "avg_session_duration": round(float(row.metric_values[5].value or 0), 2),
                    "conversions": int(row.metric_values[6].value or 0),
                    "engaged_sessions": int(row.metric_values[7].value or 0)
                })
            
            return daily_data
            
        except Exception as e:
            logger.error(f"Error fetching daily metrics: {str(e)}")
            return []
    
    def _fetch_traffic_sources(
        self, 
        property_id: str, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Fetch traffic source breakdown"""
        try:
            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="sessionDefaultChannelGroup")],
                metrics=[
                    Metric(name="sessions"),
                    Metric(name="totalUsers"),
                    Metric(name="conversions")
                ],
                order_bys=[OrderBy(
                    metric=OrderBy.MetricOrderBy(metric_name="sessions"),
                    desc=True
                )],
                limit=10
            )
            
            response = self.client.run_report(request)
            
            sources = []
            for row in response.rows:
                sources.append({
                    "channel": row.dimension_values[0].value,
                    "sessions": int(row.metric_values[0].value or 0),
                    "users": int(row.metric_values[1].value or 0),
                    "conversions": int(row.metric_values[2].value or 0)
                })
            
            return sources
            
        except Exception as e:
            logger.error(f"Error fetching traffic sources: {str(e)}")
            return []
    
    def _fetch_top_pages(
        self, 
        property_id: str, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Fetch top performing pages"""
        try:
            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="pagePath")],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="bounceRate")
                ],
                order_bys=[OrderBy(
                    metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"),
                    desc=True
                )],
                limit=10
            )
            
            response = self.client.run_report(request)
            
            pages = []
            for row in response.rows:
                pages.append({
                    "page_path": row.dimension_values[0].value,
                    "page_views": int(row.metric_values[0].value or 0),
                    "avg_time_on_page": round(float(row.metric_values[1].value or 0), 2),
                    "bounce_rate": round(float(row.metric_values[2].value or 0) * 100, 2)
                })
            
            return pages
            
        except Exception as e:
            logger.error(f"Error fetching top pages: {str(e)}")
            return []
    
    def _calculate_summary(self, daily_data: List[Dict]) -> Dict[str, Any]:
        """Calculate summary metrics from daily data"""
        if not daily_data:
            return {
                "total_sessions": 0,
                "total_users": 0,
                "total_page_views": 0,
                "avg_bounce_rate": 0,
                "avg_session_duration": 0,
                "total_conversions": 0
            }
        
        total_sessions = sum(d['sessions'] for d in daily_data)
        total_users = sum(d['users'] for d in daily_data)
        total_page_views = sum(d['page_views'] for d in daily_data)
        total_conversions = sum(d['conversions'] for d in daily_data)
        avg_bounce_rate = sum(d['bounce_rate'] for d in daily_data) / len(daily_data)
        avg_session_duration = sum(d['avg_session_duration'] for d in daily_data) / len(daily_data)
        
        return {
            "total_sessions": total_sessions,
            "total_users": total_users,
            "total_page_views": total_page_views,
            "avg_bounce_rate": round(avg_bounce_rate, 2),
            "avg_session_duration": round(avg_session_duration, 2),
            "total_conversions": total_conversions
        }
    
    def _get_empty_response(self, error_message: str = None) -> Dict[str, Any]:
        """Return empty response structure"""
        return {
            "success": False,
            "error": error_message,
            "summary": {
                "total_sessions": 0,
                "total_users": 0,
                "total_page_views": 0,
                "avg_bounce_rate": 0,
                "avg_session_duration": 0,
                "total_conversions": 0
            },
            "daily_data": [],
            "traffic_sources": [],
            "top_pages": []
        }


# Convenience function for quick access
def get_ga4_data(start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """Quick function to get GA4 data with default settings"""
    service = GoogleAnalyticsService()
    return service.get_analytics_data(start_date=start_date, end_date=end_date)