"""
WhatsApp Business API Integration Service
File: app/services/whatsapp_service.py
"""

import requests
import json
from typing import List, Dict, Any, Optional
from app.core.config import settings


class WhatsAppService:
    """WhatsApp Business API integration for sending messages"""
    
    def __init__(self):
        """Initialize WhatsApp service"""
        self.api_key = settings.WHATSAPP_API_KEY
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.base_url = "https://graph.facebook.com/v18.0"
        
        if not self.api_key or not self.phone_number_id:
            raise ValueError("WhatsApp API credentials not configured")
    
    async def send_message(
        self,
        recipient: str,
        message: str,
        template_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message to a recipient
        
        Args:
            recipient: Phone number with country code (e.g., +1234567890)
            message: Message content
            template_name: Optional template name for approved templates
            
        Returns:
            Response from WhatsApp API
        """
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # If template is provided, use template messaging
            if template_name:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {
                            "code": "en"
                        }
                    }
                }
            else:
                # Use text messaging
                payload = {
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "text",
                    "text": {
                        "body": message
                    }
                }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            return {
                "success": True,
                "message_id": response.json().get("messages", [{}])[0].get("id"),
                "recipient": recipient
            }
        
        except requests.exceptions.RequestException as e:
            print(f"WhatsApp API Error for {recipient}: {e}")
            return {
                "success": False,
                "error": str(e),
                "recipient": recipient
            }
    
    async def send_bulk_messages(
        self,
        recipients: List[str],
        message: str,
        template_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send WhatsApp messages to multiple recipients
        
        Args:
            recipients: List of phone numbers
            message: Message content
            template_name: Optional template name
            
        Returns:
            Summary of sent messages
        """
        results = {
            "total": len(recipients),
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        for recipient in recipients:
            result = await self.send_message(recipient, message, template_name)
            
            if result["success"]:
                results["successful"] += 1
            else:
                results["failed"] += 1
            
            results["details"].append(result)
        
        return results
    
    async def send_media_message(
        self,
        recipient: str,
        media_type: str,
        media_url: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send media message (image, video, document)
        
        Args:
            recipient: Phone number with country code
            media_type: Type of media (image, video, document)
            media_url: URL of the media file
            caption: Optional caption for the media
            
        Returns:
            Response from WhatsApp API
        """
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": media_type,
                media_type: {
                    "link": media_url
                }
            }
            
            if caption and media_type in ["image", "video"]:
                payload[media_type]["caption"] = caption
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            return {
                "success": True,
                "message_id": response.json().get("messages", [{}])[0].get("id"),
                "recipient": recipient
            }
        
        except requests.exceptions.RequestException as e:
            print(f"WhatsApp Media API Error for {recipient}: {e}")
            return {
                "success": False,
                "error": str(e),
                "recipient": recipient
            }
    
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """
        Get delivery status of a message
        
        Args:
            message_id: WhatsApp message ID
            
        Returns:
            Message status information
        """
        try:
            url = f"{self.base_url}/{message_id}"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            return {
                "success": True,
                "status": response.json()
            }
        
        except requests.exceptions.RequestException as e:
            print(f"WhatsApp Status API Error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def validate_phone_number(self, phone: str) -> bool:
        """
        Validate phone number format
        
        Args:
            phone: Phone number to validate
            
        Returns:
            True if valid format
        """
        # Remove spaces and special characters
        cleaned = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Should start with + and have 10-15 digits
        if cleaned.startswith("+") and 10 <= len(cleaned[1:]) <= 15:
            return cleaned[1:].isdigit()
        
        return False
    
    async def create_template(
        self,
        template_name: str,
        category: str,
        language: str,
        components: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a WhatsApp message template (requires approval)
        
        Args:
            template_name: Name for the template
            category: Template category (MARKETING, UTILITY, AUTHENTICATION)
            language: Language code (e.g., en, es)
            components: Template components (header, body, footer, buttons)
            
        Returns:
            Template creation response
        """
        try:
            # Note: This requires WhatsApp Business Account ID
            url = f"{self.base_url}/YOUR_WABA_ID/message_templates"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "name": template_name,
                "category": category,
                "language": language,
                "components": components
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            return {
                "success": True,
                "template_id": response.json().get("id"),
                "status": "pending_approval"
            }
        
        except requests.exceptions.RequestException as e:
            print(f"WhatsApp Template Creation Error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_template_status(self, template_name: str) -> Dict[str, Any]:
        """
        Check approval status of a template
        
        Args:
            template_name: Name of the template
            
        Returns:
            Template status
        """
        try:
            url = f"{self.base_url}/YOUR_WABA_ID/message_templates"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            params = {
                "name": template_name
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            templates = response.json().get("data", [])
            
            if templates:
                return {
                    "success": True,
                    "template": templates[0]
                }
            else:
                return {
                    "success": False,
                    "error": "Template not found"
                }
        
        except requests.exceptions.RequestException as e:
            print(f"WhatsApp Template Status Error: {e}")
            return {
                "success": False,
                "error": str(e)
            }