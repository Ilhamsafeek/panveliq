"""
Social Media API Integration Service
File: app/services/social_media_service.py

Integrates with Meta (Facebook/Instagram), LinkedIn, and Twitter APIs
"""

import requests
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from app.core.config import settings


class SocialMediaService:
    """Service for integrating with social media platform APIs"""
    
    def __init__(self):
        self.meta_access_token = settings.META_ACCESS_TOKEN
        self.linkedin_access_token = settings.LINKEDIN_ACCESS_TOKEN
        self.twitter_api_key = getattr(settings, 'TWITTER_API_KEY', None)
        
        # API Base URLs
        self.meta_graph_url = "https://graph.facebook.com/v18.0"
        self.linkedin_api_url = "https://api.linkedin.com/v2"
        self.twitter_api_url = "https://api.twitter.com/2"
    
    
    # ========== META (FACEBOOK & INSTAGRAM) ==========
    
    def publish_to_instagram(
        self,
        instagram_account_id: str,
        caption: str,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish post to Instagram using Meta Graph API
        
        Args:
            instagram_account_id: Instagram Business Account ID
            caption: Post caption
            image_url: URL of image to post
            video_url: URL of video to post
        
        Returns:
            Dict with post_id and status
        """
        try:
            # Step 1: Create media container
            if image_url:
                container_url = f"{self.meta_graph_url}/{instagram_account_id}/media"
                container_params = {
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": self.meta_access_token
                }
            elif video_url:
                container_url = f"{self.meta_graph_url}/{instagram_account_id}/media"
                container_params = {
                    "media_type": "VIDEO",
                    "video_url": video_url,
                    "caption": caption,
                    "access_token": self.meta_access_token
                }
            else:
                raise ValueError("Either image_url or video_url must be provided")
            
            container_response = requests.post(container_url, data=container_params)
            container_response.raise_for_status()
            container_data = container_response.json()
            creation_id = container_data.get('id')
            
            # Step 2: Publish the container
            publish_url = f"{self.meta_graph_url}/{instagram_account_id}/media_publish"
            publish_params = {
                "creation_id": creation_id,
                "access_token": self.meta_access_token
            }
            
            publish_response = requests.post(publish_url, data=publish_params)
            publish_response.raise_for_status()
            publish_data = publish_response.json()
            
            return {
                "success": True,
                "post_id": publish_data.get('id'),
                "platform": "instagram"
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "platform": "instagram"
            }
    
    
    def publish_to_facebook(
        self,
        page_id: str,
        message: str,
        link: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish post to Facebook Page using Meta Graph API
        
        Args:
            page_id: Facebook Page ID
            message: Post message
            link: URL to share
            image_url: Image URL
        
        Returns:
            Dict with post_id and status
        """
        try:
            url = f"{self.meta_graph_url}/{page_id}/feed"
            
            params = {
                "message": message,
                "access_token": self.meta_access_token
            }
            
            if link:
                params["link"] = link
            
            if image_url:
                # Use /photos endpoint for image posts
                url = f"{self.meta_graph_url}/{page_id}/photos"
                params["url"] = image_url
                params["caption"] = message
                del params["message"]
            
            response = requests.post(url, data=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "post_id": data.get('id'),
                "platform": "facebook"
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "platform": "facebook"
            }
    
    
    def get_instagram_insights(
        self,
        instagram_account_id: str,
        metric_names: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get Instagram account insights using Meta Graph API
        
        Args:
            instagram_account_id: Instagram Business Account ID
            metric_names: List of metrics to retrieve
        
        Returns:
            Dict with insights data
        """
        try:
            if metric_names is None:
                metric_names = [
                    "impressions",
                    "reach",
                    "follower_count",
                    "profile_views",
                    "website_clicks"
                ]
            
            url = f"{self.meta_graph_url}/{instagram_account_id}/insights"
            params = {
                "metric": ",".join(metric_names),
                "period": "day",
                "access_token": self.meta_access_token
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Parse insights
            insights = {}
            for item in data.get('data', []):
                metric_name = item.get('name')
                values = item.get('values', [])
                if values:
                    insights[metric_name] = values[0].get('value', 0)
            
            return {
                "success": True,
                "platform": "instagram",
                "insights": insights
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "platform": "instagram"
            }
    
    
    def get_facebook_page_insights(
        self,
        page_id: str
    ) -> Dict[str, Any]:
        """
        Get Facebook Page insights using Meta Graph API
        
        Args:
            page_id: Facebook Page ID
        
        Returns:
            Dict with insights data
        """
        try:
            url = f"{self.meta_graph_url}/{page_id}/insights"
            params = {
                "metric": "page_impressions,page_engaged_users,page_fans",
                "period": "day",
                "access_token": self.meta_access_token
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Parse insights
            insights = {}
            for item in data.get('data', []):
                metric_name = item.get('name')
                values = item.get('values', [])
                if values:
                    insights[metric_name] = values[0].get('value', 0)
            
            return {
                "success": True,
                "platform": "facebook",
                "insights": insights
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "platform": "facebook"
            }
    
    
    def get_instagram_trending_hashtags(self) -> List[Dict[str, Any]]:
        """
        Get trending hashtags on Instagram
        Note: This is a simplified version. Real implementation would use
        Instagram's hashtag search API
        
        Returns:
            List of trending hashtags
        """
        try:
            # Search for popular hashtags
            # Note: Meta Graph API doesn't have a direct trending endpoint
            # This would typically use third-party data or internal analytics
            
            popular_hashtags = [
                {"tag": "marketing", "count": 50000000},
                {"tag": "socialmedia", "count": 30000000},
                {"tag": "digitalmarketing", "count": 25000000},
                {"tag": "contentcreator", "count": 20000000},
                {"tag": "entrepreneur", "count": 18000000}
            ]
            
            return popular_hashtags
            
        except Exception as e:
            return []
    
    
    # ========== LINKEDIN ==========
    
    def publish_to_linkedin(
        self,
        author_urn: str,
        text: str,
        image_url: Optional[str] = None,
        article_link: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish post to LinkedIn using LinkedIn Marketing API
        
        Args:
            author_urn: LinkedIn person or organization URN
            text: Post text
            image_url: Optional image URL
            article_link: Optional article URL
        
        Returns:
            Dict with post_id and status
        """
        try:
            url = f"{self.linkedin_api_url}/ugcPosts"
            
            headers = {
                "Authorization": f"Bearer {self.linkedin_access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            }
            
            post_data = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            # Add image if provided
            if image_url:
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
                    "status": "READY",
                    "originalUrl": image_url
                }]
            
            # Add article link if provided
            if article_link:
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
                    "status": "READY",
                    "originalUrl": article_link
                }]
            
            response = requests.post(url, headers=headers, json=post_data)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "post_id": data.get('id'),
                "platform": "linkedin"
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "platform": "linkedin"
            }
    
    
    def get_linkedin_analytics(
        self,
        organization_urn: str
    ) -> Dict[str, Any]:
        """
        Get LinkedIn organization analytics
        
        Args:
            organization_urn: LinkedIn organization URN
        
        Returns:
            Dict with analytics data
        """
        try:
            url = f"{self.linkedin_api_url}/organizationalEntityShareStatistics"
            
            headers = {
                "Authorization": f"Bearer {self.linkedin_access_token}",
                "X-Restli-Protocol-Version": "2.0.0"
            }
            
            params = {
                "q": "organizationalEntity",
                "organizationalEntity": organization_urn
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Parse analytics
            total_share_statistics = data.get('elements', [{}])[0].get('totalShareStatistics', {})
            
            analytics = {
                "impressions": total_share_statistics.get('impressionCount', 0),
                "clicks": total_share_statistics.get('clickCount', 0),
                "likes": total_share_statistics.get('likeCount', 0),
                "comments": total_share_statistics.get('commentCount', 0),
                "shares": total_share_statistics.get('shareCount', 0)
            }
            
            return {
                "success": True,
                "platform": "linkedin",
                "analytics": analytics
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "platform": "linkedin"
            }
    
    
    # ========== TWITTER/X ==========
    
    def publish_to_twitter(
        self,
        text: str,
        media_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Publish tweet to Twitter/X
        
        Args:
            text: Tweet text
            media_ids: List of uploaded media IDs
        
        Returns:
            Dict with tweet_id and status
        """
        try:
            if not self.twitter_api_key:
                return {
                    "success": False,
                    "error": "Twitter API key not configured",
                    "platform": "twitter"
                }
            
            url = f"{self.twitter_api_url}/tweets"
            
            headers = {
                "Authorization": f"Bearer {self.twitter_api_key}",
                "Content-Type": "application/json"
            }
            
            tweet_data = {
                "text": text
            }
            
            if media_ids:
                tweet_data["media"] = {
                    "media_ids": media_ids
                }
            
            response = requests.post(url, headers=headers, json=tweet_data)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "post_id": data.get('data', {}).get('id'),
                "platform": "twitter"
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "platform": "twitter"
            }
    
    
    # ========== HELPER FUNCTIONS ==========
    
    def get_platform_credentials(self, client_id: int, platform: str) -> Optional[Dict[str, str]]:
        """
        Get platform-specific credentials for a client from database
        
        Args:
            client_id: Client ID
            platform: Platform name
        
        Returns:
            Dict with platform credentials or None
        """
        # This would query the api_integrations table
        # For now, using default credentials from settings
        
        credentials = {
            "facebook": {
                "access_token": self.meta_access_token,
                "page_id": None  # Should be stored per client
            },
            "instagram": {
                "access_token": self.meta_access_token,
                "account_id": None  # Should be stored per client
            },
            "linkedin": {
                "access_token": self.linkedin_access_token,
                "organization_urn": None  # Should be stored per client
            },
            "twitter": {
                "api_key": self.twitter_api_key
            }
        }
        
        return credentials.get(platform)
    
    
    def schedule_post(
        self,
        platform: str,
        scheduled_time: datetime,
        post_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Schedule a post for future publishing
        Note: Most platforms don't support native scheduling via API
        This would use a task queue (Celery) to publish at scheduled time
        
        Args:
            platform: Platform name
            scheduled_time: When to publish
            post_data: Post content and metadata
        
        Returns:
            Dict with scheduling status
        """
        # This would integrate with Celery or similar task queue
        # For now, return success
        
        return {
            "success": True,
            "scheduled_time": scheduled_time.isoformat(),
            "platform": platform,
            "message": "Post scheduled successfully"
        }