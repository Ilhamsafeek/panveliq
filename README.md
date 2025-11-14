# PanvelIQ - AI-powered Digital Marketing Intelligence Platform

![PanvelIQ Logo](static/images/logo.png)

## 📋 Overview

PanvelIQ is a comprehensive AI-powered digital marketing intelligence platform designed to streamline and automate marketing operations. Built with FastAPI and MySQL, it integrates 11 powerful modules to manage everything from content creation to analytics.

## ✨ Features

### Core Modules

1. **AI Project Planner** - Generate personalized project proposals with AI-powered strategy recommendations
2. **Intelligent Onboarding** - Streamlined client onboarding with verification system
3. **Role-Based Dashboards** - Separate interfaces for Clients, Admins, and Employees
4. **Communication Hub** - WhatsApp & Email campaigns with triggered automation flows
5. **Content Intelligence** - AI-powered content creation and optimization
6. **Social Media Command Center** - Multi-platform scheduling with trend monitoring
7. **Smart SEO Toolkit** - Comprehensive SEO management with real-time tracking
8. **Creative Media Studio** - AI-driven media generation (text-to-image/video)
9. **Ad Strategy Engine** - Intelligent ad campaign management with forecasting
10. **Unified Analytics Dashboard** - Cross-channel performance insights
11. **AI Assistant** - Chatbot for lead qualification and engagement

## 🚀 Tech Stack

- **Backend**: Python 3.9+, FastAPI
- **Database**: MySQL 8.0+
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Design**: Gilroy Font, Linear Gradient (#9926F3, #1DD8FC)
- **Icons**: Tabler Icons 3.34.0
- **AI Integration**: OpenAI API
- **External APIs**: 
  - WhatsApp Business API
  - Mailchimp
  - Meta Ads API
  - Google Ads API
  - Google Analytics
  - Social Media APIs

## 📦 Installation

### Prerequisites

- Python 3.9 or higher
- MySQL 8.0 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Step 1: Clone the Repository

```bash
git clone https://github.com/panvelconsulting/panveliq.git
cd panveliq
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
# Database
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/panveliq_db

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI Service
OPENAI_API_KEY=your-openai-api-key

# Email Service
SENDGRID_API_KEY=your-sendgrid-key
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587

# WhatsApp Business
WHATSAPP_API_KEY=your-whatsapp-key
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id

# Social Media APIs
META_ACCESS_TOKEN=your-meta-token
LINKEDIN_ACCESS_TOKEN=your-linkedin-token
TWITTER_API_KEY=your-twitter-key

# Google Services
GOOGLE_ADS_CLIENT_ID=your-client-id
GOOGLE_ADS_CLIENT_SECRET=your-client-secret
GOOGLE_ANALYTICS_PROPERTY_ID=your-property-id

# SEO Tools
AHREFS_API_KEY=your-ahrefs-key
MOZ_ACCESS_ID=your-moz-id
MOZ_SECRET_KEY=your-moz-secret
```

### Step 5: Initialize Database

```bash
# Create database
mysql -u root -p -e "CREATE DATABASE panveliq_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Run the database schema
mysql -u root -p panveliq_db < database_schema.sql

# Or use the initialization script
python scripts/init_db.py
```

### Step 6: Create Admin User

```bash
python scripts/create_admin.py
```

**Default Admin Credentials:**
- Email: admin@panveliq.com
- Password: password

⚠️ **Change the default password immediately after first login!**

### Step 7: Run the Application

```bash
# Development mode
python run.py

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at: `http://localhost:8000`

## 🐳 Docker Installation

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down
```

## 📚 API Documentation

Once the application is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🗂️ Project Structure

```
panveliq/
├── app/                    # Application code
│   ├── api/               # API endpoints
│   ├── core/              # Core functionality
│   ├── db/                # Database configuration
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   ├── crud/              # Database operations
│   ├── services/          # Business logic
│   └── utils/             # Utility functions
├── static/                # Static files (CSS, JS, images)
├── templates/             # HTML templates
├── tests/                 # Test files
├── scripts/               # Utility scripts
└── alembic/              # Database migrations
```

## 🔧 Configuration

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_api/test_auth.py
```

## 👥 User Roles

### Client
- View package details and subscription
- Access campaign performance reports
- Communicate with assigned employee
- Manage account settings

### Employee
- Access assigned clients
- Manage tasks and deadlines
- Create and schedule content
- Run campaigns and analyze performance

### Admin
- Manage all users and clients
- View profit & loss reports
- Assign tasks to employees
- Configure system settings
- Access control management

## 🎨 Design System

- **Font**: Gilroy (Regular, Medium, Bold, SemiBold)
- **Color Gradient**: Linear gradient from #9926F3 to #1DD8FC
- **Icons**: Tabler Icons 3.34.0
- **Responsive**: Mobile-first design approach

## 📊 Module Details

### Module 1: AI Project Planner
- Discovery prompt template
- AI-generated strategy recommendations
- Competitive differentiator analysis
- Editable proposal drafts
- PDF export functionality

### Module 2: Intelligent Onboarding
- 3-tier package selection (Basic, Professional, Enterprise)
- Document verification
- Real-time discussion interface
- Automated client confirmation

### Module 3: Role-Based Dashboards
- Client: Package overview, reports, team communication
- Admin: Financial management, user control, task assignment
- Employee: Task management, client access, productivity tools

### Module 4: Communication Hub
- WhatsApp campaigns with templates
- Email marketing with A/B testing
- Triggered automation flows
- Audience segmentation

### Module 5: Content Intelligence Hub
- Platform-specific content creation
- AI-powered content suggestions
- Hashtag and headline optimization
- Multi-format support (text, image, video, carousel)

### Module 6: Social Media Command Center
- Multi-platform post scheduling
- Best-time recommendations
- Trend monitoring
- Performance analytics per platform

### Module 7: Smart SEO Toolkit
- AI-based content optimization
- On-page audits with recommendations
- Backlink management and outreach
- Real-time SERP tracking
- Voice and semantic search optimization

### Module 8: Creative Media Studio
- Text-to-image generation
- Text-to-video creation
- Image-to-video conversion
- Image-to-animation
- AI presentation builder

### Module 9: Ad Strategy & Suggestion Engine
- Audience segmentation
- Platform selection recommendations
- AI-generated ad copy
- Placement optimization
- Performance forecasting (CTR, ROAS, CPC)

### Module 10: Unified Analytics Dashboard
- Cross-channel performance tracking
- Ad performance metrics
- SEO traffic analysis
- Conversion funnel visualization
- Automated performance alerts

### Module 11: AI Assistant for Engagement
- Lead qualification via chat
- Conversational flows with FAQs
- Post-sale engagement
- NLP-based sentiment detection

## 🔐 Security

- JWT-based authentication
- Password hashing with bcrypt
- Role-based access control
- SQL injection prevention
- CORS protection
- Rate limiting
- Input validation

## 🚀 Deployment

### Production Checklist

- [ ] Set strong SECRET_KEY
- [ ] Change default admin password
- [ ] Configure production database
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up backup procedures
- [ ] Configure monitoring and logging
- [ ] Set up CDN for static files
- [ ] Enable rate limiting
- [ ] Configure email service

### Environment Variables for Production

```env
ENVIRONMENT=production
DEBUG=False
DATABASE_URL=mysql+pymysql://user:password@host:3306/panveliq_db
SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

## 📝 API Integration Guide

### WhatsApp Business API
Documentation: https://developers.facebook.com/docs/whatsapp

### SendGrid Email API
Documentation: https://docs.sendgrid.com/

### Meta Ads API
Documentation: https://developers.facebook.com/docs/marketing-apis

### Google Ads API
Documentation: https://developers.google.com/google-ads/api

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is proprietary software owned by Panvel Consulting.

## 📞 Support

For support and queries:
- Email: support@panveliq.com
- Website: https://panveliq.com
- Documentation: https://docs.panveliq.com

## 🙏 Acknowledgments

- FastAPI for the amazing framework
- OpenAI for AI capabilities
- Tabler Icons for the beautiful icon set
- All open-source contributors

---

**Built with ❤️ by Hashnate Software Engineering**

**Version**: 1.0.0  
**Last Updated**: June 2025