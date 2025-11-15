"""
SEO Service - API Integration Service
File: app/services/seo_service.py

Integrates with Google Search Console, PageSpeed Insights, and Moz APIs
"""

import requests
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import hashlib
import hmac
import base64
from urllib.parse import urlencode

from app.core.config import settings


class SEOService:
    """Service for SEO API integrations"""
    
    def __init__(self):
        # Google APIs
        self.google_api_key = settings.GOOGLE_API_KEY
        self.search_console_credentials = getattr(settings, 'GOOGLE_SEARCH_CONSOLE_CREDENTIALS', None)
        
        # Moz API
        self.moz_access_id = getattr(settings, 'MOZ_ACCESS_ID', None)
        self.moz_secret_key = getattr(settings, 'MOZ_SECRET_KEY', None)
        
        # API URLs
        self.pagespeed_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        self.search_console_url = "https://searchconsole.googleapis.com/v1"
        self.moz_api_url = "https://lsapi.seomoz.com/v2"
    
    
    # ========== GOOGLE PAGESPEED INSIGHTS ==========
    
    def analyze_page_speed(self, url: str, strategy: str = "mobile") -> Dict[str, Any]:
        """
        Analyze page speed using Google PageSpeed Insights API
        
        Args:
            url: Website URL to analyze
            strategy: 'mobile' or 'desktop'
        
        Returns:
            Dict with performance metrics and recommendations
        """
        try:
            params = {
                "url": url,
                "key": self.google_api_key,
                "strategy": strategy,
                "category": ["performance", "accessibility", "best-practices", "seo"]
            }
            
            response = requests.get(self.pagespeed_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Extract key metrics
            lighthouse = data.get('lighthouseResult', {})
            categories = lighthouse.get('categories', {})
            audits = lighthouse.get('audits', {})
            
            # Performance metrics
            performance_score = categories.get('performance', {}).get('score', 0) * 100
            seo_score = categories.get('seo', {}).get('score', 0) * 100
            accessibility_score = categories.get('accessibility', {}).get('score', 0) * 100
            best_practices_score = categories.get('best-practices', {}).get('score', 0) * 100
            
            # Core Web Vitals
            metrics = lighthouse.get('audits', {})
            fcp = metrics.get('first-contentful-paint', {}).get('displayValue', 'N/A')
            lcp = metrics.get('largest-contentful-paint', {}).get('displayValue', 'N/A')
            cls = metrics.get('cumulative-layout-shift', {}).get('displayValue', 'N/A')
            tti = metrics.get('interactive', {}).get('displayValue', 'N/A')
            
            # Recommendations
            recommendations = []
            for audit_id, audit_data in audits.items():
                if audit_data.get('score', 1) < 0.9:  # Failed or needs improvement
                    recommendations.append({
                        'title': audit_data.get('title', ''),
                        'description': audit_data.get('description', ''),
                        'score': audit_data.get('score', 0),
                        'displayValue': audit_data.get('displayValue', '')
                    })
            
            return {
                'success': True,
                'url': url,
                'strategy': strategy,
                'scores': {
                    'performance': round(performance_score),
                    'seo': round(seo_score),
                    'accessibility': round(accessibility_score),
                    'best_practices': round(best_practices_score),
                    'overall': round((performance_score + seo_score + accessibility_score + best_practices_score) / 4)
                },
                'core_web_vitals': {
                    'first_contentful_paint': fcp,
                    'largest_contentful_paint': lcp,
                    'cumulative_layout_shift': cls,
                    'time_to_interactive': tti
                },
                'recommendations': recommendations[:10]  # Top 10 recommendations
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f"PageSpeed API Error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Error analyzing page speed: {str(e)}"
            }
    
    
    # ========== GOOGLE SEARCH CONSOLE ==========
    
    def get_search_analytics(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get search analytics from Google Search Console
        
        Args:
            site_url: Website URL (must be verified in Search Console)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            dimensions: List of dimensions ['query', 'page', 'country', 'device']
        
        Returns:
            Dict with search performance data
        """
        try:
            if not self.search_console_credentials:
                return {
                    'success': False,
                    'error': 'Google Search Console credentials not configured'
                }
            
            if dimensions is None:
                dimensions = ['query']
            
            # This would require OAuth2 authentication
            # For now, returning simulated data structure
            # In production, implement full OAuth2 flow
            
            return {
                'success': True,
                'site_url': site_url,
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'total_clicks': 0,
                'total_impressions': 0,
                'average_ctr': 0,
                'average_position': 0,
                'rows': [],
                'note': 'Requires OAuth2 authentication setup'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    
    # ========== MOZ API ==========
    
    def _generate_moz_signature(self, expires: int) -> str:
        """Generate Moz API authentication signature"""
        string_to_sign = f"{self.moz_access_id}\n{expires}"
        signature = hmac.new(
            self.moz_secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    
    def get_domain_authority(self, url: str) -> Dict[str, Any]:
        """
        Get domain authority and metrics from Moz
        
        Args:
            url: Website URL
        
        Returns:
            Dict with domain metrics
        """
        try:
            if not self.moz_access_id or not self.moz_secret_key:
                # Return simulated data if Moz not configured
                return {
                    'success': True,
                    'url': url,
                    'domain_authority': 0,
                    'page_authority': 0,
                    'spam_score': 0,
                    'linking_domains': 0,
                    'total_backlinks': 0,
                    'note': 'Moz API not configured - simulated data'
                }
            
            # Generate authentication
            expires = int((datetime.now() + timedelta(minutes=5)).timestamp())
            signature = self._generate_moz_signature(expires)
            
            # URL Metrics API endpoint
            endpoint = f"{self.moz_api_url}/url-metrics/{url}"
            
            headers = {
                'Authorization': f'Basic {base64.b64encode(f"{self.moz_access_id}:{signature}".encode()).decode()}'
            }
            
            params = {
                'Expires': expires
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                'success': True,
                'url': url,
                'domain_authority': data.get('domain_authority', 0),
                'page_authority': data.get('page_authority', 0),
                'spam_score': data.get('spam_score', 0),
                'linking_domains': data.get('external_pages', 0),
                'total_backlinks': data.get('links', 0)
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f"Moz API Error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    
    def get_backlinks(self, url: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get backlinks for a URL from Moz
        
        Args:
            url: Target URL
            limit: Number of backlinks to retrieve
        
        Returns:
            Dict with backlink data
        """
        try:
            if not self.moz_access_id or not self.moz_secret_key:
                return {
                    'success': True,
                    'url': url,
                    'backlinks': [],
                    'total_count': 0,
                    'note': 'Moz API not configured'
                }
            
            # Generate authentication
            expires = int((datetime.now() + timedelta(minutes=5)).timestamp())
            signature = self._generate_moz_signature(expires)
            
            # Links API endpoint
            endpoint = f"{self.moz_api_url}/links/{url}"
            
            headers = {
                'Authorization': f'Basic {base64.b64encode(f"{self.moz_access_id}:{signature}".encode()).decode()}'
            }
            
            params = {
                'Expires': expires,
                'Limit': limit
            }
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            backlinks = []
            for link in data.get('links', []):
                backlinks.append({
                    'source_url': link.get('source_url', ''),
                    'target_url': link.get('target_url', ''),
                    'anchor_text': link.get('anchor_text', ''),
                    'domain_authority': link.get('source_domain_authority', 0),
                    'page_authority': link.get('source_page_authority', 0),
                    'spam_score': link.get('spam_score', 0)
                })
            
            return {
                'success': True,
                'url': url,
                'backlinks': backlinks,
                'total_count': len(backlinks)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    
    # ========== SERP TRACKING (Using Custom Implementation) ==========
    
    def track_keyword_position(
        self,
        keyword: str,
        url: str,
        location: str = "US"
    ) -> Dict[str, Any]:
        """
        Track keyword position in search results
        Note: This is a simplified version. In production, use specialized SERP APIs
        
        Args:
            keyword: Keyword to track
            url: Website URL to track
            location: Geographic location
        
        Returns:
            Dict with position data
        """
        try:
            # In production, use specialized SERP tracking APIs like:
            # - SERPWatcher
            # - SEMrush API
            # - Ahrefs API
            
            # For now, return simulated structure
            return {
                'success': True,
                'keyword': keyword,
                'url': url,
                'location': location,
                'position': None,
                'search_volume': 0,
                'difficulty': 0,
                'cpc': 0,
                'tracked_at': datetime.now().isoformat(),
                'note': 'Requires SERP tracking API integration'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    
    # ========== AI-POWERED SEO ANALYSIS ==========
    
    def analyze_content_seo(
        self,
        content: str,
        target_keyword: str,
        url: str = None
    ) -> Dict[str, Any]:
        """
        AI-powered SEO content analysis
        
        Args:
            content: Page content/text
            target_keyword: Primary keyword
            url: Optional URL for additional context
        
        Returns:
            Dict with SEO score and recommendations
        """
        try:
            # Content analysis
            word_count = len(content.split())
            keyword_density = (content.lower().count(target_keyword.lower()) / word_count * 100) if word_count > 0 else 0
            
            # Initialize score
            seo_score = 0
            recommendations = []
            
            # Word count check
            if 300 <= word_count <= 2500:
                seo_score += 20
            else:
                recommendations.append({
                    'category': 'Content Length',
                    'issue': f'Content has {word_count} words',
                    'suggestion': 'Aim for 300-2500 words for optimal SEO',
                    'priority': 'high'
                })
            
            # Keyword density check (1-3% is ideal)
            if 1 <= keyword_density <= 3:
                seo_score += 20
            else:
                recommendations.append({
                    'category': 'Keyword Density',
                    'issue': f'Keyword density is {keyword_density:.2f}%',
                    'suggestion': 'Maintain keyword density between 1-3% for best results',
                    'priority': 'medium'
                })
            
            # Heading structure (simulate check)
            if '<h1>' in content or '# ' in content:
                seo_score += 15
            else:
                recommendations.append({
                    'category': 'Headings',
                    'issue': 'No H1 heading detected',
                    'suggestion': 'Add an H1 heading with your primary keyword',
                    'priority': 'high'
                })
            
            # Meta description (simulate check)
            if 'meta description' in content.lower():
                seo_score += 15
            else:
                recommendations.append({
                    'category': 'Meta Description',
                    'issue': 'Meta description not found',
                    'suggestion': 'Add a compelling meta description (150-160 characters)',
                    'priority': 'high'
                })
            
            # Internal links
            if '<a href' in content or '[link]' in content:
                seo_score += 10
            else:
                recommendations.append({
                    'category': 'Internal Linking',
                    'issue': 'No internal links detected',
                    'suggestion': 'Add 2-5 relevant internal links',
                    'priority': 'medium'
                })
            
            # Image alt tags
            if 'alt=' in content or '![' in content:
                seo_score += 10
            else:
                recommendations.append({
                    'category': 'Images',
                    'issue': 'No image alt tags detected',
                    'suggestion': 'Add descriptive alt tags to all images',
                    'priority': 'medium'
                })
            
            # Readability (basic check)
            avg_word_length = sum(len(word) for word in content.split()) / word_count if word_count > 0 else 0
            if avg_word_length < 6:  # Simple vocabulary
                seo_score += 10
            
            return {
                'success': True,
                'seo_score': seo_score,
                'word_count': word_count,
                'keyword_density': round(keyword_density, 2),
                'recommendations': recommendations,
                'grade': 'Excellent' if seo_score >= 80 else 'Good' if seo_score >= 60 else 'Needs Improvement'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }