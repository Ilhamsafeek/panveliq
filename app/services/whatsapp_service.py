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
        """Initialize WhatsApp service with credentials from .env"""
        self.api_key = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.base_url = "https://graph.facebook.com/v18.0"
        
        if not self.api_key:
            print("WARNING: WHATSAPP_API_KEY not configured in .env file")
        if not self.phone_number_id:
            print("WARNING: WHATSAPP_PHONE_NUMBER_ID not configured in .env file")
    
    async def send_message(
        self,
        recipient: str,
        message: str,
        template_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message to a recipient
        
        Args:
            recipient: Phone number with country code (e.g., +94777140803)
            message: Message content
            template_name: Optional template name for approved templates
            
        Returns:
            Response from WhatsApp API
        """
        # Check if credentials are configured
        if not self.api_key or not self.phone_number_id:
            return {
                "success": False,
                "error": "WhatsApp API credentials not configured in .env file",
                "recipient": recipient
            }
        
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Clean phone number - remove spaces and ensure it has country code
            clean_recipient = recipient.strip().replace(" ", "").replace("-", "")
            if not clean_recipient.startswith("+"):
                clean_recipient = "+" + clean_recipient
            
            # Remove + for API (WhatsApp API expects number without +)
            api_recipient = clean_recipient.replace("+", "")
            
            # If template is provided, use template messaging
            if template_name:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": api_recipient,
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
                    "to": api_recipient,
                    "type": "text",
                    "text": {
                        "body": message
                    }
                }
            
            # Log the request for debugging
            print(f"WhatsApp API Request URL: {url}")
            print(f"WhatsApp API Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, headers=headers, json=payload)
            
            # Get detailed error information
            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                error_code = error_data.get('error', {}).get('code', 'Unknown')
                
                print(f"WhatsApp API Error Response: {response.status_code}")
                print(f"Error Details: {json.dumps(error_data, indent=2)}")
                
                return {
                    "success": False,
                    "error": f"WhatsApp API Error ({error_code}): {error_message}",
                    "error_code": error_code,
                    "status_code": response.status_code,
                    "recipient": recipient,
                    "details": error_data
                }
            
            response.raise_for_status()
            response_data = response.json()
            
            return {
                "success": True,
                "message_id": response_data.get("messages", [{}])[0].get("id"),
                "recipient": recipient
            }
        
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            print(f"WhatsApp API Request Exception for {recipient}: {error_msg}")
            
            # Try to extract more details from response
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = f"{error_data.get('error', {}).get('message', error_msg)}"
                    print(f"Error Details: {json.dumps(error_data, indent=2)}")
                except:
                    pass
            
            return {
                "success": False,
                "error": error_msg,
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
        
        # Also accept without + if it's 10-15 digits
        if 10 <= len(cleaned) <= 15 and cleaned.isdigit():
            return True
        
        return False