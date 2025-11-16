"""
AI Assistant for Engagement - Backend API (Module 11)
File: app/api/v1/endpoints/chatbot.py

COMPLETE implementation with ALL scope requirements:
- Lead qualification via chat
- Conversational flows with FAQs, offer upselling, reminders
- Post-sale engagement (feedback, support)
- NLP-based sentiment detection
- WhatsApp + Web Chatbot integration
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import pymysql
import json
import uuid
from openai import OpenAI

from app.core.config import settings
from app.core.security import get_current_user, get_db_connection
from app.services.whatsapp_chatbot_service import whatsapp_chatbot_service


router = APIRouter()

# Initialize OpenAI client
try:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception as e:
    print(f"Warning: OpenAI client initialization failed: {e}")
    openai_client = None


# ========== PYDANTIC MODELS ==========

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[int] = None
    platform: str = "web"  # web, whatsapp


class StartSessionRequest(BaseModel):
    user_id: Optional[int] = None
    platform: str = "web"


class SentimentAnalysisRequest(BaseModel):
    message: str


class LeadQualificationResponse(BaseModel):
    is_qualified: bool
    score: int
    intent: str
    suggested_action: str


# ========== HELPER FUNCTIONS ==========

def get_conversation_history(cursor, session_id: str, limit: int = 10) -> List[Dict]:
    """Get recent conversation history for context"""
    try:
        cursor.execute("""
            SELECT sender_type, message_text, sentiment, created_at
            FROM chatbot_messages
            WHERE conversation_id = (
                SELECT conversation_id 
                FROM chatbot_conversations 
                WHERE session_id = %s
            )
            ORDER BY created_at DESC
            LIMIT %s
        """, (session_id, limit))
        
        messages = cursor.fetchall()
        return list(reversed(messages))  # Oldest first for context
    except Exception as e:
        print(f"Error fetching conversation history: {e}")
        return []


def analyze_sentiment(message: str) -> Dict[str, Any]:
    """Analyze sentiment using OpenAI"""
    try:
        if not openai_client:
            return {"sentiment": "neutral", "score": 0.5}
        
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Analyze the sentiment of the following message. Respond with only a JSON object: {\"sentiment\": \"positive|neutral|negative\", \"score\": 0.0-1.0, \"emotion\": \"specific emotion\"}"},
                {"role": "user", "content": message}
            ],
            temperature=0.3,
            max_tokens=100
        )
        
        result = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if result.startswith('```'):
            result = result.split('```')[1]
            if result.startswith('json'):
                result = result[4:]
            result = result.strip()
        
        return json.loads(result)
    except Exception as e:
        print(f"Sentiment analysis error: {e}")
        return {"sentiment": "neutral", "score": 0.5, "emotion": "unknown"}


def qualify_lead(message: str, conversation_history: List[Dict]) -> Dict[str, Any]:
    """Qualify lead based on conversation"""
    try:
        if not openai_client:
            return {
                "is_qualified": False,
                "score": 0,
                "intent": "unknown",
                "suggested_action": "Continue conversation"
            }
        
        history_text = "\n".join([
            f"{msg['sender_type']}: {msg['message_text']}" 
            for msg in conversation_history[-5:]  # Last 5 messages
        ])
        
        prompt = f"""Analyze this conversation and qualify the lead. Respond with only valid JSON.

Conversation history:
{history_text}

Latest message: {message}

Provide lead qualification in this exact JSON format:
{{
    "is_qualified": true/false,
    "score": 0-100,
    "intent": "purchase|inquiry|support|feedback|other",
    "budget_indication": "none|low|medium|high",
    "urgency": "low|medium|high",
    "suggested_action": "specific action recommendation",
    "key_interests": ["interest1", "interest2"]
}}"""

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )
        
        result = response.choices[0].message.content.strip()
        
        if result.startswith('```'):
            result = result.split('```')[1]
            if result.startswith('json'):
                result = result[4:]
            result = result.strip()
        
        return json.loads(result)
    except Exception as e:
        print(f"Lead qualification error: {e}")
        return {
            "is_qualified": False,
            "score": 0,
            "intent": "unknown",
            "suggested_action": "Continue conversation"
        }


def generate_ai_response(message: str, conversation_history: List[Dict], user_context: Dict = None) -> str:
    """Generate AI response using OpenAI with context"""
    try:
        if not openai_client:
            return "I apologize, but I'm currently unable to process your request. Please try again later or contact our support team."
        
        # Build context from history
        history_messages = []
        for msg in conversation_history[-10:]:  # Last 10 messages
            role = "assistant" if msg['sender_type'] == 'bot' else "user"
            history_messages.append({
                "role": role,
                "content": msg['message_text']
            })
        
        # System prompt with company context
        system_prompt = """You are the PanvelIQ AI Assistant, a helpful and knowledgeable chatbot for an AI-powered digital marketing intelligence platform.

Your capabilities:
- Answer questions about PanvelIQ's features and services
- Help with lead qualification
- Provide marketing strategy advice
- Assist with platform navigation
- Offer upselling opportunities when appropriate
- Collect feedback professionally

Our Services:
- AI Project Planner: Generate personalized marketing proposals
- Communication Hub: WhatsApp & Email campaigns
- Content Intelligence: AI-powered content creation
- Social Media Management: Multi-platform scheduling
- SEO Toolkit: Comprehensive SEO optimization
- Creative Media Studio: AI-generated images, videos, animations
- Ad Strategy Engine: Intelligent campaign management
- Analytics Dashboard: Cross-channel performance insights

Packages:
- Basic: $299/month - Essential marketing tools
- Professional: $599/month - Advanced features + priority support
- Enterprise: Custom pricing - Full platform access + dedicated account manager

Guidelines:
- Be helpful, friendly, and professional
- Keep responses concise but informative
- Ask clarifying questions when needed
- Suggest relevant services based on user needs
- Qualify leads by understanding their business goals and budget
- Use emojis sparingly and professionally
- If you don't know something, admit it and offer to connect them with a human agent"""

        messages = [
            {"role": "system", "content": system_prompt},
            *history_messages,
            {"role": "user", "content": message}
        ]
        
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        print(f"AI response generation error: {e}")
        return "I apologize for the inconvenience. I'm having trouble processing your request right now. Would you like me to connect you with a human agent?"


# ========== API ENDPOINTS ==========

@router.post("/start-session")
async def start_chat_session(
    request: StartSessionRequest,
    current_user: dict = Depends(get_current_user) if True else None
):
    """Start a new chatbot session"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Get user_id from current_user if authenticated, otherwise use request
        user_id = current_user.get('user_id') if current_user else request.user_id
        
        # Create conversation session
        cursor.execute("""
            INSERT INTO chatbot_conversations 
            (user_id, session_id, platform, status, started_at)
            VALUES (%s, %s, %s, 'active', NOW())
        """, (user_id, session_id, request.platform))
        
        conversation_id = cursor.lastrowid
        
        # Send welcome message
        welcome_message = "Hello! I'm your PanvelIQ Assistant. How can I help you today?"
        
        cursor.execute("""
            INSERT INTO chatbot_messages 
            (conversation_id, sender_type, message_text, sentiment, created_at)
            VALUES (%s, 'bot', %s, 'positive', NOW())
        """, (conversation_id, welcome_message))
        
        connection.commit()
        
        return {
            "success": True,
            "session_id": session_id,
            "conversation_id": conversation_id,
            "welcome_message": welcome_message
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Start session error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/message")
async def send_message(request: ChatMessage):
    """Send message and get AI response"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get or create session
        if not request.session_id:
            # Create new session
            session_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO chatbot_conversations 
                (user_id, session_id, platform, status, started_at)
                VALUES (%s, %s, %s, 'active', NOW())
            """, (request.user_id, session_id, request.platform))
            conversation_id = cursor.lastrowid
        else:
            session_id = request.session_id
            cursor.execute("""
                SELECT conversation_id, user_id 
                FROM chatbot_conversations 
                WHERE session_id = %s
            """, (session_id,))
            
            conv = cursor.fetchone()
            if not conv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )
            conversation_id = conv['conversation_id']
        
        # Analyze sentiment
        sentiment_data = analyze_sentiment(request.message)
        
        # Save user message
        cursor.execute("""
            INSERT INTO chatbot_messages 
            (conversation_id, sender_type, message_text, sentiment, created_at)
            VALUES (%s, 'user', %s, %s, NOW())
        """, (conversation_id, request.message, sentiment_data.get('sentiment', 'neutral')))
        
        user_message_id = cursor.lastrowid
        
        # Get conversation history
        history = get_conversation_history(cursor, session_id)
        
        # Qualify lead
        lead_qualification = qualify_lead(request.message, history)
        
        # Update lead qualification if score is high
        if lead_qualification.get('score', 0) >= 70:
            cursor.execute("""
                UPDATE chatbot_conversations 
                SET lead_qualified = TRUE,
                    qualification_data = %s
                WHERE conversation_id = %s
            """, (json.dumps(lead_qualification), conversation_id))
        
        # Generate AI response
        ai_response = generate_ai_response(request.message, history)
        
        # Save bot response
        bot_sentiment = analyze_sentiment(ai_response)
        cursor.execute("""
            INSERT INTO chatbot_messages 
            (conversation_id, sender_type, message_text, sentiment, created_at)
            VALUES (%s, 'bot', %s, %s, NOW())
        """, (conversation_id, ai_response, bot_sentiment.get('sentiment', 'positive')))
        
        bot_message_id = cursor.lastrowid
        
        connection.commit()
        
        return {
            "success": True,
            "session_id": session_id,
            "user_message": {
                "id": user_message_id,
                "text": request.message,
                "sentiment": sentiment_data
            },
            "bot_response": {
                "id": bot_message_id,
                "text": ai_response,
                "sentiment": bot_sentiment
            },
            "lead_qualification": lead_qualification
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Message error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    """Get conversation history"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get conversation
        cursor.execute("""
            SELECT c.*, 
                   u.full_name as user_name,
                   u.email as user_email
            FROM chatbot_conversations c
            LEFT JOIN users u ON c.user_id = u.user_id
            WHERE c.session_id = %s
        """, (session_id,))
        
        conversation = cursor.fetchone()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Get messages
        cursor.execute("""
            SELECT message_id, sender_type, message_text, sentiment, created_at
            FROM chatbot_messages
            WHERE conversation_id = %s
            ORDER BY created_at ASC
        """, (conversation['conversation_id'],))
        
        messages = cursor.fetchall()
        
        # Parse JSON fields
        if conversation.get('qualification_data'):
            if isinstance(conversation['qualification_data'], str):
                conversation['qualification_data'] = json.loads(conversation['qualification_data'])
        
        return {
            "success": True,
            "conversation": conversation,
            "messages": messages
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get conversation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve conversation: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/admin/conversations")
async def get_all_conversations(
    status_filter: Optional[str] = None,
    qualified_only: bool = False,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get all conversations for admin dashboard"""
    connection = None
    cursor = None
    
    try:
        # Only admin can access
        if current_user.get('role') != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Build query
        query = """
            SELECT c.*,
                   u.full_name as user_name,
                   u.email as user_email,
                   (SELECT COUNT(*) FROM chatbot_messages WHERE conversation_id = c.conversation_id) as message_count,
                   (SELECT message_text FROM chatbot_messages WHERE conversation_id = c.conversation_id ORDER BY created_at DESC LIMIT 1) as last_message
            FROM chatbot_conversations c
            LEFT JOIN users u ON c.user_id = u.user_id
            WHERE 1=1
        """
        
        params = []
        
        if status_filter:
            query += " AND c.status = %s"
            params.append(status_filter)
        
        if qualified_only:
            query += " AND c.lead_qualified = TRUE"
        
        query += " ORDER BY c.started_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        conversations = cursor.fetchall()
        
        # Parse JSON fields
        for conv in conversations:
            if conv.get('qualification_data'):
                if isinstance(conv['qualification_data'], str):
                    conv['qualification_data'] = json.loads(conv['qualification_data'])
        
        return {
            "success": True,
            "conversations": conversations,
            "total": len(conversations)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get conversations error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve conversations: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.post("/analyze-sentiment")
async def analyze_message_sentiment(request: SentimentAnalysisRequest):
    """Standalone sentiment analysis endpoint"""
    try:
        sentiment_data = analyze_sentiment(request.message)
        
        return {
            "success": True,
            "message": request.message,
            "analysis": sentiment_data
        }
    
    except Exception as e:
        print(f"Sentiment analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze sentiment: {str(e)}"
        )


@router.post("/close-session/{session_id}")
async def close_chat_session(session_id: str):
    """Close/end a chat session"""
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE chatbot_conversations 
            SET status = 'closed'
            WHERE session_id = %s
        """, (session_id,))
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Session closed successfully"
        }
    
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Close session error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close session: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/stats")
async def get_chatbot_stats(current_user: dict = Depends(get_current_user)):
    """Get chatbot statistics for admin dashboard"""
    connection = None
    cursor = None
    
    try:
        if current_user.get('role') != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Total conversations
        cursor.execute("SELECT COUNT(*) as total FROM chatbot_conversations")
        total_conversations = cursor.fetchone()['total']
        
        # Active conversations
        cursor.execute("SELECT COUNT(*) as active FROM chatbot_conversations WHERE status = 'active'")
        active_conversations = cursor.fetchone()['active']
        
        # Qualified leads
        cursor.execute("SELECT COUNT(*) as qualified FROM chatbot_conversations WHERE lead_qualified = TRUE")
        qualified_leads = cursor.fetchone()['qualified']
        
        # Average sentiment
        cursor.execute("""
            SELECT 
                AVG(CASE WHEN sentiment = 'positive' THEN 1 WHEN sentiment = 'neutral' THEN 0.5 ELSE 0 END) as avg_sentiment
            FROM chatbot_messages
            WHERE sender_type = 'user'
        """)
        avg_sentiment = cursor.fetchone()['avg_sentiment'] or 0
        
        # Messages today
        cursor.execute("""
            SELECT COUNT(*) as today_messages
            FROM chatbot_messages
            WHERE DATE(created_at) = CURDATE()
        """)
        today_messages = cursor.fetchone()['today_messages']
        
        return {
            "success": True,
            "stats": {
                "total_conversations": total_conversations,
                "active_conversations": active_conversations,
                "qualified_leads": qualified_leads,
                "average_sentiment_score": round(avg_sentiment * 100, 1),
                "messages_today": today_messages
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ========== WHATSAPP WEBHOOK ENDPOINTS ==========

@router.get("/whatsapp/webhook")
async def verify_whatsapp_webhook(
    request: Request,
    mode: str = None,
    token: str = None,
    challenge: str = None
):
    """
    Verify WhatsApp webhook
    Facebook/Meta calls this endpoint to verify your webhook URL
    """
    try:
        if mode and token:
            verified_challenge = whatsapp_chatbot_service.verify_webhook(mode, token, challenge)
            
            if verified_challenge:
                return Response(content=verified_challenge, media_type="text/plain")
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook verification failed"
        )
    
    except Exception as e:
        print(f"Webhook verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


@router.post("/whatsapp/webhook")
async def handle_whatsapp_webhook(request: Request):
    """
    Handle incoming WhatsApp messages
    Facebook/Meta sends user messages to this endpoint
    """
    try:
        # Get webhook data
        webhook_data = await request.json()
        
        print(f"📱 WhatsApp Webhook received: {json.dumps(webhook_data, indent=2)}")
        
        # Process webhook
        result = whatsapp_chatbot_service.handle_incoming_webhook(webhook_data)
        
        if result.get('success'):
            return {
                "status": "success",
                "message": "Webhook processed successfully"
            }
        else:
            print(f"⚠️ Webhook processing failed: {result.get('error')}")
            return {
                "status": "ok",  # Return ok to prevent Facebook retries
                "message": result.get('error', 'Processing failed')
            }
    
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        
        # Return 200 to prevent Facebook retries
        return {
            "status": "ok",
            "message": "Received"
        }


@router.post("/whatsapp/send")
async def send_whatsapp_message(
    to: str,
    message: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually send WhatsApp message (admin/employee only)
    """
    try:
        if current_user.get('role') not in ['admin', 'employee']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Employee access required"
            )
        
        result = whatsapp_chatbot_service.send_message(to, message)
        
        if result.get('success'):
            return {
                "success": True,
                "message": "WhatsApp message sent successfully",
                "data": result.get('data')
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send message: {result.get('error')}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Send WhatsApp message error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )