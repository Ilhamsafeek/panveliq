"""
Email Service Integration (Mailchimp)
File: app/services/email_service.py
"""

import requests
from typing import List, Dict, Any, Optional
from app.core.config import settings


class EmailService:
    """Email service supporting Mailchimp"""
    
    def __init__(self, provider: str = "mailchimp"):
        """
        Initialize email service
        
        Args:
            provider: Email provider (mailchimp)
        """
        self.provider = provider.lower()
        
        if self.provider == "mailchimp":
            if not settings.MAILCHIMP_API_KEY or not settings.MAILCHIMP_SERVER_PREFIX:
                raise ValueError("Mailchimp credentials not configured")
            self.api_key = settings.MAILCHIMP_API_KEY
            self.server_prefix = settings.MAILCHIMP_SERVER_PREFIX
            self.base_url = f"https://{self.server_prefix}.api.mailchimp.com/3.0"
    
    # =====================================================
    # MAILCHIMP METHODS
    # =====================================================
    
    async def send_email_mailchimp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: str = "noreply@panveliq.com",
        from_name: str = "PanvelIQ"
    ) -> Dict[str, Any]:
        """
        Send transactional email using Mailchimp Transactional API (Mandrill)
        
        Args:
            to_email: Recipient email
            subject: Email subject
            html_content: HTML email content
            from_email: Sender email
            from_name: Sender name
            
        Returns:
            Response from Mailchimp
        """
        try:
            url = "https://mandrillapp.com/api/1.0/messages/send"
            
            payload = {
                "key": self.api_key,
                "message": {
                    "html": html_content,
                    "subject": subject,
                    "from_email": from_email,
                    "from_name": from_name,
                    "to": [
                        {
                            "email": to_email,
                            "type": "to"
                        }
                    ],
                    "track_opens": True,
                    "track_clicks": True
                }
            }
            
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()[0]
            
            return {
                "success": result["status"] in ["sent", "queued"],
                "status": result["status"],
                "message_id": result.get("_id"),
                "recipient": to_email
            }
        
        except Exception as e:
            print(f"Mailchimp Error for {to_email}: {e}")
            return {
                "success": False,
                "error": str(e),
                "recipient": to_email
            }
    
    async def create_mailchimp_campaign(
        self,
        list_id: str,
        subject: str,
        from_name: str,
        from_email: str,
        html_content: str
    ) -> Dict[str, Any]:
        """
        Create email campaign in Mailchimp
        
        Args:
            list_id: Mailchimp audience/list ID
            subject: Email subject
            from_name: Sender name
            from_email: Sender email
            html_content: Email HTML content
            
        Returns:
            Campaign creation response
        """
        try:
            url = f"{self.base_url}/campaigns"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "type": "regular",
                "recipients": {
                    "list_id": list_id
                },
                "settings": {
                    "subject_line": subject,
                    "from_name": from_name,
                    "reply_to": from_email
                }
            }
            
            # Create campaign
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            campaign = response.json()
            campaign_id = campaign["id"]
            
            # Set campaign content
            content_url = f"{self.base_url}/campaigns/{campaign_id}/content"
            content_payload = {
                "html": html_content
            }
            
            content_response = requests.put(content_url, headers=headers, json=content_payload)
            content_response.raise_for_status()
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "status": "draft"
            }
        
        except Exception as e:
            print(f"Mailchimp Campaign Creation Error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_mailchimp_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """
        Send a Mailchimp campaign
        
        Args:
            campaign_id: Mailchimp campaign ID
            
        Returns:
            Send response
        """
        try:
            url = f"{self.base_url}/campaigns/{campaign_id}/actions/send"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "status": "sent"
            }
        
        except Exception as e:
            print(f"Mailchimp Campaign Send Error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def add_subscriber_to_list(
        self,
        email: str,
        list_id: str,
        merge_fields: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Add subscriber to Mailchimp audience/list
        
        Args:
            email: Subscriber email
            list_id: Mailchimp list ID
            merge_fields: Additional subscriber data (FNAME, LNAME, etc.)
            
        Returns:
            Subscription response
        """
        try:
            url = f"{self.base_url}/lists/{list_id}/members"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "email_address": email,
                "status": "subscribed"
            }
            
            if merge_fields:
                payload["merge_fields"] = merge_fields
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            return {
                "success": True,
                "subscriber_id": response.json().get("id"),
                "email": email
            }
        
        except Exception as e:
            print(f"Mailchimp Add Subscriber Error: {e}")
            return {
                "success": False,
                "error": str(e),
                "email": email
            }
    
    async def get_campaign_reports(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get campaign statistics from Mailchimp
        
        Args:
            campaign_id: Mailchimp campaign ID
            
        Returns:
            Campaign statistics
        """
        try:
            url = f"{self.base_url}/reports/{campaign_id}"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            report = response.json()
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "stats": {
                    "emails_sent": report.get("emails_sent", 0),
                    "opens": report.get("opens", {}).get("opens_total", 0),
                    "unique_opens": report.get("opens", {}).get("unique_opens", 0),
                    "open_rate": report.get("opens", {}).get("open_rate", 0),
                    "clicks": report.get("clicks", {}).get("clicks_total", 0),
                    "unique_clicks": report.get("clicks", {}).get("unique_clicks", 0),
                    "click_rate": report.get("clicks", {}).get("click_rate", 0)
                }
            }
        
        except Exception as e:
            print(f"Mailchimp Reports Error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # =====================================================
    # UNIFIED INTERFACE
    # =====================================================
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: str = "noreply@panveliq.com",
        from_name: str = "PanvelIQ"
    ) -> Dict[str, Any]:
        """
        Send email using configured provider
        
        Args:
            to_email: Recipient email
            subject: Email subject
            html_content: HTML email content
            from_email: Sender email
            from_name: Sender name
            
        Returns:
            Response from email provider
        """
        if self.provider == "mailchimp":
            return await self.send_email_mailchimp(
                to_email, subject, html_content, from_email, from_name
            )
        else:
            return {
                "success": False,
                "error": f"Unsupported provider: {self.provider}"
            }
    
    async def send_bulk_emails(
        self,
        recipients: List[str],
        subject: str,
        html_content: str,
        from_email: str = "noreply@panveliq.com",
        from_name: str = "PanvelIQ"
    ) -> Dict[str, Any]:
        """
        Send bulk emails using configured provider
        
        Args:
            recipients: List of recipient emails
            subject: Email subject
            html_content: HTML email content
            from_email: Sender email
            from_name: Sender name
            
        Returns:
            Summary of sent emails
        """
        if self.provider == "mailchimp":
            # For Mailchimp, send individually
            results = {
                "total": len(recipients),
                "successful": 0,
                "failed": 0,
                "details": []
            }
            
            for recipient in recipients:
                result = await self.send_email_mailchimp(
                    to_email=recipient,
                    subject=subject,
                    html_content=html_content,
                    from_email=from_email,
                    from_name=from_name
                )
                
                if result["success"]:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                
                results["details"].append(result)
            
            return results