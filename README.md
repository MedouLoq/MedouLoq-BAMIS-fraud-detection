# BAMIS Enhanced Banking Fraud Detection Platform

![BAMIS Logo](static/images/bamis-logo.png)

## 🏦 Overview

The BAMIS Enhanced Banking Fraud Detection Platform is a comprehensive, AI-powered solution designed to detect, analyze, and prevent banking fraud in real-time. Built with Django and enhanced with modern web technologies, this platform provides banking institutions with professional-grade fraud detection capabilities.

## ✨ Key Features

### 🔐 **Secure Authentication & Role-Based Access**
- Multi-level user authentication system
- Role-based permissions (Admin, Analyst, Viewer)
- Session management and security controls

### 📊 **Real-Time Dashboard**
- Live fraud detection metrics
- Transaction volume monitoring
- Risk assessment indicators
- Priority alert system

### 🔍 **Advanced Analytics**
- Time series analysis with interactive charts
- Transaction pattern recognition
- Client behavior analysis
- Fraud trend visualization
- Customizable reporting periods

### 🤖 **AI-Powered Analysis**
- Integration with Anthropic Claude API for intelligent fraud interpretation
- Machine learning model framework for real-time predictions
- Risk scoring and confidence levels
- Automated pattern detection

### 👥 **Comprehensive Client Management**
- Detailed client profiles with transaction history
- Risk level assessment and monitoring
- Behavioral pattern analysis
- Multi-bank relationship tracking

### 💳 **Transaction Processing**
- Real-time transaction monitoring
- CSV data import capabilities
- Advanced filtering and search
- Detailed transaction analysis

### 🎨 **Professional Design**
- BAMIS brand colors and styling
- Responsive design for all devices
- Modern, banking-professional interface
- Intuitive user experience

## 🚀 Technology Stack

- **Backend**: Django 5.2.4
- **Database**: SQLite (development) / PostgreSQL (production ready)
- **AI Integration**: Anthropic Claude API
- **ML Framework**: Scikit-learn, Pandas
- **Frontend**: Bootstrap 5.3.0, Chart.js, Font Awesome
- **Charts**: Plotly.js for interactive visualizations
- **Styling**: Custom BAMIS theme with CSS3

## 📋 Requirements

### System Requirements
- Python 3.11+
- 4GB RAM minimum (8GB recommended)
- 2GB disk space
- Internet connection for AI features

### Dependencies
```
Django==5.2.4
anthropic==0.34.0
pandas==2.2.2
plotly==5.17.0
scikit-learn==1.7.1
joblib==1.5.1
python-dotenv==1.1.1
django-cors-headers==4.3.1
python-decouple==3.8
```

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd enhanced_banking_platform
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file in the project root:
```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# API Keys
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Database (for production)
DATABASE_URL=postgresql://user:password@localhost:5432/bamis_fraud_db
```

### 5. Database Setup
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Load Sample Data (Optional)
```bash
python manage.py loaddata sample_data.json
```

### 7. Run Development Server
```bash
python manage.py runserver
```

Visit `http://localhost:8000` to access the platform.

## 👤 Default Accounts

### Demo Accounts
- **Admin**: `admin` / `admin123`
- **Analyst**: `analyst` / `analyst123`
- **Viewer**: `viewer` / `viewer123`

## 🔧 Configuration

### Claude API Integration
1. Obtain an API key from Anthropic
2. Add the key to your `.env` file
3. Restart the Django server

### Machine Learning Model Integration
1. Place your trained model file in `fraud_detection/ml_models/trained_models/`
2. Update the model path in `fraud_detection/ml_models/model_interface.py`
3. Restart the application

### Production Deployment
1. Set `DEBUG=False` in settings
2. Configure a production database (PostgreSQL recommended)
3. Set up static file serving
4. Configure HTTPS and security headers
5. Set up monitoring and logging

## 📊 Data Import

### CSV Format
The platform accepts CSV files with the following columns:
```
trx,montant,trx_type,trx_time,client_i,client_b,bank_i,bank_b,etat,mls
```

### Import Process
1. Navigate to "Upload Data" in the main menu
2. Select your CSV file
3. Review the data preview
4. Confirm import
5. Monitor processing progress

## 🔍 Usage Guide

### Dashboard
- View real-time fraud metrics
- Monitor recent transactions
- Review priority alerts
- Access quick actions

### Analytics
- Select analysis period
- Filter by transaction type
- View time series charts
- Generate insights with AI

### Transactions
- Browse all transactions
- Apply filters and search
- View detailed transaction information
- Export data for analysis

### Clients
- Manage client profiles
- Monitor risk levels
- Analyze transaction patterns
- Generate client reports

## 🎨 BAMIS Branding

### Color Scheme
- **Primary Green**: `#2E7D32` (BAMIS brand green)
- **Secondary Orange**: `#FF8C00` (BAMIS brand orange)
- **Success**: `#4CAF50`
- **Warning**: `#FF9800`
- **Danger**: `#F44336`
- **Info**: `#2196F3`

### Typography
- **Primary Font**: Inter (Google Fonts)
- **Headings**: 600 weight
- **Body**: 400 weight
- **Emphasis**: 500 weight

## 🔒 Security Features

- CSRF protection
- SQL injection prevention
- XSS protection
- Secure session management
- Input validation and sanitization
- Rate limiting for API endpoints

## 📈 Performance Optimization

- Database indexing for fast queries
- Efficient pagination
- Lazy loading for large datasets
- Caching for frequently accessed data
- Optimized static file serving

## 🧪 Testing

### Run Tests
```bash
python manage.py test
```

### Test Coverage
```bash
coverage run --source='.' manage.py test
coverage report
```

## 📝 API Documentation

### Endpoints
- `/api/transactions/` - Transaction data API
- `/api/clients/` - Client information API
- `/api/analytics/` - Analytics data API
- `/api/fraud-analysis/` - AI fraud analysis API

### Authentication
All API endpoints require authentication. Use Django's built-in authentication or implement token-based authentication for external integrations.

## 🚀 Deployment

### Docker Deployment
```bash
docker build -t bamis-fraud-detection .
docker run -p 8000:8000 bamis-fraud-detection
```

### Production Checklist
- [ ] Set `DEBUG=False`
- [ ] Configure production database
- [ ] Set up static file serving
- [ ] Configure HTTPS
- [ ] Set up monitoring
- [ ] Configure backup strategy
- [ ] Set up logging
- [ ] Configure email notifications

## 🔄 Model Integration

### Adding Your Trained Model

1. **Prepare Your Model**
   ```python
   # Save your trained model
   import joblib
   joblib.dump(your_model, 'fraud_detection/ml_models/trained_models/fraud_model.pkl')
   ```

2. **Update Model Interface**
   Edit `fraud_detection/ml_models/model_interface.py`:
   ```python
   MODEL_PATH = os.path.join(BASE_DIR, 'fraud_detection/ml_models/trained_models/fraud_model.pkl')
   ```

3. **Feature Engineering**
   Ensure your model expects the same features as defined in the interface:
   - Transaction amount
   - Transaction type
   - Time features
   - Client features
   - Bank features

4. **Test Integration**
   ```bash
   python manage.py shell
   >>> from fraud_detection.utils import apply_fraud_detection_model
   >>> # Test with sample transaction
   ```

## 🤖 Claude AI Integration

### Features
- Real-time transaction analysis
- Risk assessment explanations
- Pattern recognition insights
- Behavioral analysis reports
- Daily summary generation

### Configuration
1. Obtain Anthropic API key
2. Set `ANTHROPIC_API_KEY` in environment
3. Configure analysis parameters in `utils.py`

## 📊 Analytics & Reporting

### Available Charts
- Transaction volume over time
- Fraud detection trends
- Client risk distribution
- Bank performance metrics
- Transaction type analysis

### Export Options
- PDF reports
- CSV data export
- Excel spreadsheets
- JSON data dumps

## 🛠️ Customization

### Adding New Features
1. Create new Django apps for major features
2. Follow the existing code structure
3. Update navigation in base templates
4. Add appropriate tests

### Styling Customization
1. Edit `static/css/bamis-theme.css`
2. Maintain BAMIS brand consistency
3. Test responsive design
4. Update color variables

## 📞 Support & Maintenance

### Logging
Logs are stored in `logs/` directory:
- `django.log` - Application logs
- `fraud_detection.log` - Fraud detection specific logs
- `claude_api.log` - AI integration logs

### Monitoring
- Database performance
- API response times
- Fraud detection accuracy
- User activity

### Backup Strategy
- Daily database backups
- Model versioning
- Configuration backups
- Log rotation

## 🔮 Future Enhancements

### Planned Features
- Real-time notifications
- Mobile application
- Advanced ML models
- Blockchain integration
- Multi-language support
- Advanced reporting
- API rate limiting
- Webhook integrations

### Scalability
- Microservices architecture
- Load balancing
- Database sharding
- Caching layers
- CDN integration

## 📄 License

This project is proprietary software developed for BAMIS. All rights reserved.

## 👥 Contributors

- **Development Team**: BAMIS Technology Division
- **AI Integration**: Machine Learning Team
- **Design**: UX/UI Design Team
- **Testing**: Quality Assurance Team

## 📞 Contact

For technical support or questions:
- **Email**: support@bamis.com
- **Documentation**: https://docs.bamis.com/fraud-detection
- **Support Portal**: https://support.bamis.com

---

**© 2024 BAMIS. All rights reserved.**

*Powered by artificial intelligence and machine learning for next-generation fraud detection.*

