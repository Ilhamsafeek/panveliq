"""
Financial P&L API Endpoints
File: app/api/v1/endpoints/finance.py
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta
from jose import JWTError, jwt
import pymysql
from app.core.config import settings

router = APIRouter()

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/{settings.API_VERSION}/auth/login")


# ============================================
# DATABASE CONNECTION
# ============================================

def get_db_connection():
    """Get MySQL database connection"""
    try:
        connection = pymysql.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {str(e)}"
        )


# ============================================
# AUTHENTICATION
# ============================================

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    connection = None
    cursor = None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if email is None or user_id is None:
            raise credentials_exception
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(
            "SELECT user_id, email, full_name, role, status FROM users WHERE user_id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        
        if user is None:
            raise credentials_exception
        
        if user['status'] == 'suspended':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended"
            )
        
        return user
    
    except JWTError:
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ============================================
# PYDANTIC MODELS
# ============================================

class TransactionCreate(BaseModel):
    client_id: int
    transaction_type: str  # 'revenue' or 'expense'
    amount: float
    description: str
    transaction_date: date


# ============================================
# PROFIT & LOSS ENDPOINTS
# ============================================

@router.get("/profit-loss", summary="Get Profit & Loss statement")
async def get_profit_loss(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate comprehensive Profit & Loss statement
    Shows revenue, expenses, and net profit for a given period
    """
    connection = None
    cursor = None
    
    try:
        # Verify admin role
        if current_user['role'] not in ['admin', 'employee']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Default to current month if no dates provided
        if not start_date:
            start_date = date.today().replace(day=1).isoformat()
        if not end_date:
            end_date = date.today().isoformat()
        
        # ========== REVENUE SECTION ==========
        
        # Total revenue from subscriptions
        cursor.execute("""
            SELECT SUM(p.price) as total_revenue
            FROM client_subscriptions cs
            JOIN packages p ON cs.package_id = p.package_id
            WHERE cs.status = 'active'
            AND cs.start_date BETWEEN %s AND %s
        """, (start_date, end_date))
        subscription_revenue = cursor.fetchone()
        subscription_revenue_amount = float(subscription_revenue['total_revenue'] or 0)
        
        # Revenue transactions
        cursor.execute("""
            SELECT SUM(amount) as total_revenue
            FROM financial_transactions
            WHERE transaction_type = 'revenue'
            AND transaction_date BETWEEN %s AND %s
        """, (start_date, end_date))
        transaction_revenue = cursor.fetchone()
        transaction_revenue_amount = float(transaction_revenue['total_revenue'] or 0)
        
        # Revenue by package tier
        cursor.execute("""
            SELECT 
                p.package_tier,
                COUNT(*) as count,
                SUM(p.price) as revenue
            FROM client_subscriptions cs
            JOIN packages p ON cs.package_id = p.package_id
            WHERE cs.status = 'active'
            AND cs.start_date BETWEEN %s AND %s
            GROUP BY p.package_tier
        """, (start_date, end_date))
        revenue_by_tier = cursor.fetchall()
        
        # ========== EXPENSE SECTION ==========
        
        # Total expenses
        cursor.execute("""
            SELECT 
                SUM(amount) as total_expenses,
                COUNT(*) as expense_count
            FROM financial_transactions
            WHERE transaction_type = 'expense'
            AND transaction_date BETWEEN %s AND %s
        """, (start_date, end_date))
        expense_data = cursor.fetchone()
        total_expenses = float(expense_data['total_expenses'] or 0)
        
        # Expenses by category
        cursor.execute("""
            SELECT 
                description as category,
                SUM(amount) as amount,
                COUNT(*) as count
            FROM financial_transactions
            WHERE transaction_type = 'expense'
            AND transaction_date BETWEEN %s AND %s
            GROUP BY description
            ORDER BY amount DESC
        """, (start_date, end_date))
        expenses_by_category = cursor.fetchall()
        
        # ========== CALCULATE METRICS ==========
        
        total_revenue = subscription_revenue_amount + transaction_revenue_amount
        net_profit = total_revenue - total_expenses
        profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # ========== MONTHLY TREND ==========
        
        # Get last 6 months trend
        cursor.execute("""
            SELECT 
                DATE_FORMAT(transaction_date, '%Y-%m') as month,
                SUM(CASE WHEN transaction_type = 'revenue' THEN amount ELSE 0 END) as revenue,
                SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END) as expenses
            FROM financial_transactions
            WHERE transaction_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
            ORDER BY month
        """)
        monthly_trend = cursor.fetchall()
        
        # ========== CLIENT METRICS ==========
        
        # Active clients
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM client_subscriptions
            WHERE status = 'active'
            AND start_date BETWEEN %s AND %s
        """, (start_date, end_date))
        new_clients = cursor.fetchone()['count']
        
        # Average revenue per client
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM client_subscriptions
            WHERE status = 'active'
        """)
        total_active_clients = cursor.fetchone()['count']
        avg_revenue_per_client = total_revenue / total_active_clients if total_active_clients > 0 else 0
        
        return {
            "success": True,
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "revenue": {
                "subscription_revenue": round(subscription_revenue_amount, 2),
                "transaction_revenue": round(transaction_revenue_amount, 2),
                "total_revenue": round(total_revenue, 2),
                "revenue_by_tier": [
                    {
                        "tier": row['package_tier'],
                        "count": row['count'],
                        "revenue": round(float(row['revenue']), 2)
                    }
                    for row in revenue_by_tier
                ]
            },
            "expenses": {
                "total_expenses": round(total_expenses, 2),
                "expense_count": expense_data['expense_count'],
                "by_category": [
                    {
                        "category": row['category'],
                        "amount": round(float(row['amount']), 2),
                        "count": row['count']
                    }
                    for row in expenses_by_category
                ]
            },
            "profit": {
                "net_profit": round(net_profit, 2),
                "profit_margin": round(profit_margin, 2)
            },
            "metrics": {
                "new_clients": new_clients,
                "total_active_clients": total_active_clients,
                "avg_revenue_per_client": round(avg_revenue_per_client, 2)
            },
            "monthly_trend": [
                {
                    "month": row['month'],
                    "revenue": round(float(row['revenue'] or 0), 2),
                    "expenses": round(float(row['expenses'] or 0), 2),
                    "profit": round(float(row['revenue'] or 0) - float(row['expenses'] or 0), 2)
                }
                for row in monthly_trend
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating P&L: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate P&L: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# ============================================
# TRANSACTION MANAGEMENT
# ============================================

@router.post("/transactions", summary="Create financial transaction")
async def create_transaction(
    transaction: TransactionCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new financial transaction (revenue or expense)"""
    connection = None
    cursor = None
    
    try:
        # Verify admin role
        if current_user['role'] not in ['admin', 'employee']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Validate client exists
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (transaction.client_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Insert transaction
        cursor.execute("""
            INSERT INTO financial_transactions 
            (client_id, transaction_type, amount, description, transaction_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            transaction.client_id,
            transaction.transaction_type,
            transaction.amount,
            transaction.description,
            transaction.transaction_date
        ))
        
        connection.commit()
        transaction_id = cursor.lastrowid
        
        return {
            "success": True,
            "message": "Transaction created successfully",
            "transaction_id": transaction_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error creating transaction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transaction: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.get("/transactions", summary="Get all transactions")
async def get_transactions(
    transaction_type: Optional[str] = None,
    client_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get transactions with optional filters"""
    connection = None
    cursor = None
    
    try:
        # Verify admin role
        if current_user['role'] not in ['admin', 'employee']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT 
                ft.*,
                u.full_name as client_name,
                u.email as client_email
            FROM financial_transactions ft
            JOIN users u ON ft.client_id = u.user_id
            WHERE 1=1
        """
        params = []
        
        if transaction_type:
            query += " AND ft.transaction_type = %s"
            params.append(transaction_type)
        
        if client_id:
            query += " AND ft.client_id = %s"
            params.append(client_id)
        
        if start_date:
            query += " AND ft.transaction_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND ft.transaction_date <= %s"
            params.append(end_date)
        
        query += " ORDER BY ft.transaction_date DESC, ft.created_at DESC"
        
        cursor.execute(query, params)
        transactions = cursor.fetchall()
        
        # Convert dates to strings
        for t in transactions:
            if t['transaction_date']:
                t['transaction_date'] = t['transaction_date'].isoformat()
            if t['created_at']:
                t['created_at'] = t['created_at'].isoformat()
            t['amount'] = float(t['amount'])
        
        return {
            "success": True,
            "transactions": transactions,
            "total": len(transactions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching transactions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch transactions: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@router.delete("/transactions/{transaction_id}", summary="Delete transaction")
async def delete_transaction(
    transaction_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a financial transaction"""
    connection = None
    cursor = None
    
    try:
        # Verify admin role
        if current_user['role'] not in ['admin', 'employee']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute(
            "DELETE FROM financial_transactions WHERE transaction_id = %s",
            (transaction_id,)
        )
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        connection.commit()
        
        return {
            "success": True,
            "message": "Transaction deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"Error deleting transaction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete transaction: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()