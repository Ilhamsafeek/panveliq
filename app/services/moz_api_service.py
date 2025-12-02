"""
Moz API Service for Unified Analytics Dashboard
File: app/services/moz_api_service.py

Fetches SEO metrics including Domain Authority, Page Authority, backlinks, etc.
"""

from typing import Dict, List, Optional, Any
import requests
import hashlib
import hmac
import base64
import time
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class MozAPIService:
    """Service for fetching SEO metrics from Moz API"""
    
    def __init__(self):
        """Initialize Moz API credentials"""
        self.access_id = settings.MOZ_ACCESS_ID
        self.secret_key = settings.MOZ_SECRET_KEY
        self.base_url = "https://lsapi.seomoz.com/v2"
        
    
    def _generate_auth_header(self) -> str:
        """
        Generate authentication header for Moz API
        
        Returns:
            Base64 encoded authentication string
        """
        # Current timestamp
        expires = int(time.time()) + 300  # 5 minutes from now
        
        # Create string to sign
        string_to_sign = f"{self.access_id}\n{expires}"
        
        # Generate HMAC signature
        binary_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        # Base64 encode the signature
        signature = base64.b64encode(binary_signature).decode('utf-8')
        
        # Create authorization header
        auth_header = f"Basic {base64.b64encode(f'{self.access_id}:{signature}'.encode()).decode()}"
        
        return auth_header
    
    
    def get_url_metrics(self, url: str) -> Dict[str, Any]:
        """
        Get comprehensive SEO metrics for a specific URL
        
        Args:
            url: The URL to analyze
            
        Returns:
            Dictionary containing SEO metrics
        """
        try:
            endpoint = f"{self.base_url}/url_metrics"
            
            headers = {
                "Authorization": self._generate_auth_header(),
                "Content-Type": "application/json"
            }
            
            payload = {
                "targets": [url]
            }
            
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('results') and len(data['results']) > 0:
                result = data['results'][0]
                
                return {
                    'success': True,
                    'url': url,
                    'domain_authority': result.get('domain_authority', 0),
                    'page_authority': result.get('page_authority', 0),
                    'spam_score': result.get('spam_score', 0),
                    'root_domains_to_page': result.get('root_domains_to_page', 0),
                    'root_domains_to_subdomain': result.get('root_domains_to_subdomain', 0),
                    'external_pages_to_page': result.get('external_pages_to_page', 0),
                    'external_pages_to_subdomain': result.get('external_pages_to_subdomain', 0),
                    'deleted_pages_to_page': result.get('deleted_pages_to_page', 0),
                    'last_crawled': result.get('last_crawled', None)
                }
            else:
                return self._get_empty_url_metrics(url)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Moz API request error: {str(e)}")
            return self._get_empty_url_metrics(url)
        except Exception as e:
            logger.error(f"Error fetching Moz URL metrics: {str(e)}")
            return self._get_empty_url_metrics(url)
    
    
    def get_backlink_metrics(self, url: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get backlink data for a specific URL
        
        Args:
            url: The URL to analyze
            limit: Maximum number of backlinks to return
            
        Returns:
            Dictionary containing backlink metrics
        """
        try:
            endpoint = f"{self.base_url}/anchor_text"
            
            headers = {
                "Authorization": self._generate_auth_header(),
                "Content-Type": "application/json"
            }
            
            payload = {
                "target": url,
                "scope": "page",
                "limit": limit
            }
            
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            backlinks = []
            total_backlinks = 0
            
            if data.get('results'):
                for result in data['results']:
                    backlinks.append({
                        'anchor_text': result.get('anchor_text', ''),
                        'external_pages': result.get('external_pages', 0),
                        'external_root_domains': result.get('external_root_domains', 0)
                    })
                    total_backlinks += result.get('external_pages', 0)
            
            return {
                'success': True,
                'url': url,
                'total_backlinks': total_backlinks,
                'unique_domains': len(backlinks),
                'backlinks': backlinks
            }
            
        except Exception as e:
            logger.error(f"Error fetching Moz backlink metrics: {str(e)}")
            return {
                'success': False,
                'url': url,
                'total_backlinks': 0,
                'unique_domains': 0,
                'backlinks': []
            }
    
    
    def get_domain_metrics(self, domain: str) -> Dict[str, Any]:
        """
        Get domain-level SEO metrics
        
        Args:
            domain: The domain to analyze (e.g., example.com)
            
        Returns:
            Dictionary containing domain metrics
        """
        try:
            # Ensure domain has protocol
            if not domain.startswith('http'):
                domain = f"https://{domain}"
            
            endpoint = f"{self.base_url}/url_metrics"
            
            headers = {
                "Authorization": self._generate_auth_header(),
                "Content-Type": "application/json"
            }
            
            payload = {
                "targets": [domain]
            }
            
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('results') and len(data['results']) > 0:
                result = data['results'][0]
                
                return {
                    'success': True,
                    'domain': domain,
                    'domain_authority': result.get('domain_authority', 0),
                    'spam_score': result.get('spam_score', 0),
                    'root_domains_linking': result.get('root_domains_to_root_domain', 0),
                    'total_backlinks': result.get('external_pages_to_root_domain', 0),
                    'ranking_keywords': result.get('pages', 0),
                    'last_crawled': result.get('last_crawled', None)
                }
            else:
                return self._get_empty_domain_metrics(domain)
                
        except Exception as e:
            logger.error(f"Error fetching Moz domain metrics: {str(e)}")
            return self._get_empty_domain_metrics(domain)
    
    
    def get_top_pages(self, domain: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top performing pages for a domain
        
        Args:
            domain: The domain to analyze
            limit: Maximum number of pages to return
            
        Returns:
            List of top pages with metrics
        """
        try:
            # Ensure domain has protocol
            if not domain.startswith('http'):
                domain = f"https://{domain}"
            
            endpoint = f"{self.base_url}/top_pages"
            
            headers = {
                "Authorization": self._generate_auth_header(),
                "Content-Type": "application/json"
            }
            
            payload = {
                "target": domain,
                "limit": limit
            }
            
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            top_pages = []
            if data.get('results'):
                for page in data['results']:
                    top_pages.append({
                        'url': page.get('url', ''),
                        'page_authority': page.get('page_authority', 0),
                        'external_links': page.get('external_pages_to_page', 0),
                        'root_domains_linking': page.get('root_domains_to_page', 0),
                        'spam_score': page.get('spam_score', 0)
                    })
            
            return top_pages
            
        except Exception as e:
            logger.error(f"Error fetching top pages: {str(e)}")
            return []
    
    
    def get_keyword_rankings(self, domain: str) -> Dict[str, Any]:
        """
        Get keyword ranking overview for a domain
        
        Args:
            domain: The domain to analyze
            
        Returns:
            Dictionary containing keyword metrics
        """
        try:
            # Moz API v2 doesn't have direct keyword rankings
            # This would require Moz Pro API or rank tracking integration
            # Returning basic structure for future implementation
            
            domain_metrics = self.get_domain_metrics(domain)
            
            return {
                'success': True,
                'domain': domain,
                'total_ranking_keywords': domain_metrics.get('ranking_keywords', 0),
                'domain_authority': domain_metrics.get('domain_authority', 0),
                'note': 'Detailed keyword rankings require Moz Pro API integration'
            }
            
        except Exception as e:
            logger.error(f"Error fetching keyword rankings: {str(e)}")
            return {
                'success': False,
                'domain': domain,
                'total_ranking_keywords': 0
            }
    
    
    def get_competitor_analysis(
        self,
        domain: str,
        competitor_domains: List[str]
    ) -> Dict[str, Any]:
        """
        Compare domain metrics with competitors
        
        Args:
            domain: Your domain
            competitor_domains: List of competitor domains
            
        Returns:
            Comparison metrics
        """
        try:
            # Get metrics for primary domain
            primary_metrics = self.get_domain_metrics(domain)
            
            # Get metrics for competitors
            competitors = []
            for comp_domain in competitor_domains[:5]:  # Limit to 5 competitors
                comp_metrics = self.get_domain_metrics(comp_domain)
                competitors.append(comp_metrics)
            
            return {
                'success': True,
                'primary_domain': primary_metrics,
                'competitors': competitors,
                'analysis': {
                    'da_gap': self._calculate_gap(
                        primary_metrics.get('domain_authority', 0),
                        [c.get('domain_authority', 0) for c in competitors]
                    ),
                    'backlink_gap': self._calculate_gap(
                        primary_metrics.get('total_backlinks', 0),
                        [c.get('total_backlinks', 0) for c in competitors]
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error performing competitor analysis: {str(e)}")
            return {
                'success': False,
                'primary_domain': {},
                'competitors': []
            }
    
    
    def _calculate_gap(self, primary_value: float, competitor_values: List[float]) -> Dict[str, Any]:
        """Calculate gap between primary and competitor average"""
        if not competitor_values:
            return {'gap': 0, 'percentage': 0}
        
        avg_competitor = sum(competitor_values) / len(competitor_values)
        gap = primary_value - avg_competitor
        percentage = (gap / avg_competitor * 100) if avg_competitor > 0 else 0
        
        return {
            'gap': round(gap, 2),
            'percentage': round(percentage, 2),
            'status': 'ahead' if gap > 0 else 'behind'
        }
    
    
    def _get_empty_url_metrics(self, url: str) -> Dict[str, Any]:
        """Return empty URL metrics structure"""
        return {
            'success': False,
            'url': url,
            'domain_authority': 0,
            'page_authority': 0,
            'spam_score': 0,
            'root_domains_to_page': 0,
            'external_pages_to_page': 0
        }
    
    
    def _get_empty_domain_metrics(self, domain: str) -> Dict[str, Any]:
        """Return empty domain metrics structure"""
        return {
            'success': False,
            'domain': domain,
            'domain_authority': 0,
            'spam_score': 0,
            'root_domains_linking': 0,
            'total_backlinks': 0
        }



    def get_keyword_difficulty(self, keyword: str) -> Dict[str, Any]:
        """
        Analyze keyword metrics using AI (since Mozscape doesn't include keyword data)
        
        Note: Mozscape API (Links API) does not include keyword difficulty data.
        This method uses OpenAI to provide intelligent estimates.
        
        Args:
            keyword: The keyword to analyze
            
        Returns:
            Dictionary containing estimated keyword metrics
        """
        try:
            from openai import OpenAI
            from app.core.config import settings
            
            logger.info(f"📊 Analyzing keyword with AI: {keyword}")
            
            # Check if OpenAI is configured
            if not settings.OPENAI_API_KEY:
                logger.error("OpenAI API key not configured")
                raise Exception("OpenAI API key required for keyword analysis")
            
            # Initialize OpenAI client
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Use AI to analyze the keyword
            prompt = f"""
    Analyze this SEO keyword: "{keyword}"

    Provide accurate SEO metrics estimation in JSON format:
    {{
    "search_volume": 5000,
    "difficulty": 65,
    "organic_ctr": 25.0,
    "priority": 45,
    "keyword_type": "commercial",
    "competition_level": "medium"
    }}

    Guidelines for estimation:
    - search_volume: Realistic monthly searches based on keyword specificity
    - difficulty: SEO competition (0-100, consider word count, commercial intent, competition)
    - organic_ctr: Expected click-through rate percentage
    - priority: Opportunity score (balance of volume and difficulty)
    - keyword_type: informational/commercial/navigational/transactional/local
    - competition_level: low/medium/high

    Analyze the keyword comprehensively and provide realistic estimates.

    Return ONLY valid JSON with no markdown.
    """
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert SEO analyst. Analyze keywords and provide accurate metric estimates in JSON format only."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # Get response
            response_content = response.choices[0].message.content.strip()
            
            # Remove markdown if present
            if response_content.startswith('```'):
                response_content = response_content.split('```')[1]
                if response_content.startswith('json'):
                    response_content = response_content[4:]
                response_content = response_content.strip()
            
            # Parse JSON
            import json
            analysis = json.loads(response_content)
            
            logger.info(f"✅ AI keyword analysis complete:")
            logger.info(f"   Keyword: {keyword}")
            logger.info(f"   Volume: {analysis.get('search_volume', 0):,}")
            logger.info(f"   Difficulty: {analysis.get('difficulty', 0)}/100")
            logger.info(f"   Type: {analysis.get('keyword_type', 'unknown')}")
            
            return {
                'success': True,
                'keyword': keyword,
                'search_volume': analysis.get('search_volume', 0),
                'difficulty': analysis.get('difficulty', 50),
                'organic_ctr': analysis.get('organic_ctr', 25.0),
                'priority': analysis.get('priority', 50),
                'cpc': 0,
                'keyword_type': analysis.get('keyword_type', 'informational'),
                'competition_level': analysis.get('competition_level', 'medium'),
                'data_source': 'AI-powered analysis (OpenAI GPT-4)',
                'note': 'Estimates generated by AI. For real data, Moz Keyword Explorer API required (separate subscription).'
            }
            
        except Exception as e:
            logger.error(f"Keyword analysis failed: {str(e)}")
            raise Exception(f"Failed to analyze keyword: {str(e)}")


    def _get_empty_keyword_metrics(self, keyword: str) -> Dict[str, Any]:
        """
        Return empty keyword metrics structure
        
        Args:
            keyword: The keyword
            
        Returns:
            Dictionary with empty/default keyword metrics
        """
        return {
            'success': False,
            'keyword': keyword,
            'search_volume': 0,
            'difficulty': 0,
            'organic_ctr': 0,
            'priority': 0,
            'cpc': 0,
            'error': 'No data available'
        }