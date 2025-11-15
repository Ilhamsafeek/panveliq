import asyncio
from app.services.meta_ads_reporting import MetaAdsReportingService
from app.services.google_ads_reporting import GoogleAdsReportingService
from app.services.google_analytics_service import GoogleAnalyticsService
from app.services.moz_api_service import MozAPIService

async def test_apis():
    # Test Meta Ads
    print("Testing Meta Ads API...")
    meta = MetaAdsReportingService()
    meta_result = meta.get_campaign_performance(
        ad_account_id="act_YOUR_ACCOUNT_ID",
        start_date="2025-01-01",
        end_date="2025-01-31"
    )
    print("Meta Ads:", "✓ Connected" if meta_result.get('success') else "✗ Failed")
    
    # Test Google Ads
    print("Testing Google Ads API...")
    google_ads = GoogleAdsReportingService()
    ga_result = google_ads.get_campaign_performance(
        start_date="2025-01-01",
        end_date="2025-01-31"
    )
    print("Google Ads:", "✓ Connected" if ga_result.get('success') else "✗ Failed")
    
    # Test GA4
    print("Testing Google Analytics 4...")
    ga4 = GoogleAnalyticsService()
    ga4_result = ga4.get_website_metrics(
        start_date="2025-01-01",
        end_date="2025-01-31"
    )
    print("GA4:", "✓ Connected" if ga4_result.get('success') else "✗ Failed")
    
    # Test Moz
    print("Testing Moz API...")
    moz = MozAPIService()
    moz_result = moz.get_url_metrics("https://example.com")
    print("Moz:", "✓ Connected" if moz_result.get('success') else "✗ Failed")

asyncio.run(test_apis())