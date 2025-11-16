"""
WhatsApp Chatbot Service - Module 11 Integration
File: app/services/whatsapp_chatbot_service.py

Handles WhatsApp Business API integration for AI Assistant
"""

import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime
import pymysql

from app.core.config import settings
from app.core.security import get_db_connection


class WhatsAppChatbotService:
    """WhatsApp Business API integration for chatbot"""
    
    def __init__(self):
        self.api_url = "https://graph.facebook.com/v18.0"
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_API_KEY
        
    
    def send_message(self, to: str, message: str) -> Dict[str, Any]:
        """Send WhatsApp message"""
        try:
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {
                    "body": message
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                return {
                    "success": False,
                    "error": response.text
                }
        
        except Exception as e:
            print(f"WhatsApp send error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def send_template_message(self, to: str, template_name: str, language: str = "en", components: list = None) -> Dict[str, Any]:
        """Send WhatsApp template message"""
        try:
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language
                    }
                }
            }
            
            if components:
                data["template"]["components"] = components
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                return {
                    "success": False,
                    "error": response.text
                }
        
        except Exception as e:
            print(f"WhatsApp template send error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def handle_incoming_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming WhatsApp webhook
        Process user messages and trigger chatbot response
        """
        try:
            # Extract message data
            if not webhook_data.get('entry'):
                return {"success": False, "error": "No entry in webhook"}
            
            entry = webhook_data['entry'][0]
            changes = entry.get('changes', [])
            
            if not changes:
                return {"success": False, "error": "No changes in webhook"}
            
            change = changes[0]
            value = change.get('value', {})
            
            # Get message
            messages = value.get('messages', [])
            if not messages:
                return {"success": True, "message": "No messages to process"}
            
            message_data = messages[0]
            
            # Extract details
            from_number = message_data.get('from')
            message_id = message_data.get('id')
            timestamp = message_data.get('timestamp')
            message_type = message_data.get('type')
            
            # Get message text
            message_text = None
            if message_type == 'text':
                message_text = message_data.get('text', {}).get('body')
            
            if not message_text:
                return {"success": False, "error": "No message text"}
            
            # Process with chatbot
            from app.api.v1.endpoints.chatbot import analyze_sentiment, generate_ai_response, qualify_lead
            
            # Store in database
            connection = get_db_connection()
            cursor = connection.cursor()
            
            try:
                # Check if conversation exists for this number
                cursor.execute("""
                    SELECT conversation_id, session_id 
                    FROM chatbot_conversations 
                    WHERE platform = 'whatsapp' 
                    AND user_id IS NULL
                    AND status = 'active'
                    ORDER BY started_at DESC
                    LIMIT 1
                """)
                
                conv = cursor.fetchone()
                
                if not conv:
                    # Create new conversation
                    import uuid
                    session_id = str(uuid.uuid4())
                    
                    cursor.execute("""
                        INSERT INTO chatbot_conversations 
                        (session_id, platform, status, started_at)
                        VALUES (%s, 'whatsapp', 'active', NOW())
                    """, (session_id,))
                    
                    conversation_id = cursor.lastrowid
                else:
                    conversation_id = conv['conversation_id']
                    session_id = conv['session_id']
                
                # Analyze sentiment
                sentiment_data = analyze_sentiment(message_text)
                
                # Save user message
                cursor.execute("""
                    INSERT INTO chatbot_messages 
                    (conversation_id, sender_type, message_text, sentiment, created_at)
                    VALUES (%s, 'user', %s, %s, NOW())
                """, (conversation_id, message_text, sentiment_data.get('sentiment', 'neutral')))
                
                # Get conversation history
                cursor.execute("""
                    SELECT sender_type, message_text, sentiment
                    FROM chatbot_messages
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (conversation_id,))
                
                history = list(reversed(cursor.fetchall()))
                
                # Generate AI response
                ai_response = generate_ai_response(message_text, history)
                
                # Save bot response
                bot_sentiment = analyze_sentiment(ai_response)
                cursor.execute("""
                    INSERT INTO chatbot_messages 
                    (conversation_id, sender_type, message_text, sentiment, created_at)
                    VALUES (%s, 'bot', %s, %s, NOW())
                """, (conversation_id, ai_response, bot_sentiment.get('sentiment', 'positive')))
                
                # Qualify lead
                lead_qualification = qualify_lead(message_text, history)
                
                if lead_qualification.get('score', 0) >= 70:
                    cursor.execute("""
                        UPDATE chatbot_conversations 
                        SET lead_qualified = TRUE,
                            qualification_data = %s
                        WHERE conversation_id = %s
                    """, (json.dumps(lead_qualification), conversation_id))
                
                connection.commit()
                
                # Send response via WhatsApp
                send_result = self.send_message(from_number, ai_response)
                
                return {
                    "success": True,
                    "conversation_id": conversation_id,
                    "response_sent": send_result.get('success', False),
                    "lead_qualification": lead_qualification
                }
            
            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()
        
        except Exception as e:
            print(f"Webhook handling error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """
        Verify WhatsApp webhook
        Called when Facebook sends verification request
        """
        verify_token = settings.WHATSAPP_VERIFY_TOKEN
        
        if mode == "subscribe" and token == verify_token:
            return challenge
        
        return None
    
    
    def mark_message_read(self, message_id: str) -> Dict[str, Any]:
        """Mark WhatsApp message as read"""
        try:
            url = f"{self.api_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            return {
                "success": response.status_code == 200,
                "data": response.json() if response.status_code == 200 else None
            }
        
        except Exception as e:
            print(f"Mark read error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Singleton instance
whatsapp_chatbot_service = WhatsAppChatbotService()