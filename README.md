# 📊 ChurnGuard AI Agent

An intelligent customer retention platform with modular architecture that combines AI-powered data analysis with multi-channel campaign management.

## 🏗️ Project Structure (Modular Design)

```
churnguard-ai/
│
├── app.py                          # Main Streamlit application entry point
├── .env                            # Environment variables
├── requirements.txt                # Python dependencies
├── README.md                       # This file
│
├── config/
│   ├── __init__.py
│   └── settings.py                 # Configuration management
│
├── core/
│   ├── __init__.py
│   ├── data_processor.py           # CSV preprocessing and validation
│   ├── query_generator.py          # Natural language to pandas conversion
│   └── code_executor.py            # Safe code execution sandbox
│
├── campaigns/
│   ├── __init__.py
│   ├── base_campaign.py            # Abstract base campaign class
│   ├── sms_campaign.py             # Twilio SMS implementation
│   ├── email_campaign.py           # Gmail SMTP implementation
│   └── voice_campaign.py           # Twilio voice call implementation
│
├── ui/
│   ├── __init__.py
│   ├── sidebar.py                  # Sidebar rendering
│   ├── chat.py                     # Chat interface components
│   ├── campaign_ui.py              # Campaign launch UI
│   └── monitor.py                  # Monitoring dashboard
│
├── utils/
│   ├── __init__.py
│   ├── validators.py               # Phone/email validation
│   ├── logger.py                   # Custom logging setup
│   └── helpers.py                  # Utility functions
│
└── data/
    └── sample_customers.csv        # Sample dataset
```

## 📦 Module Breakdown

### 1️⃣ **config/** - Configuration Management
```python
config/
├── __init__.py
└── settings.py
```

**Purpose**: Centralized configuration and environment variable management

**Key Classes/Functions**:
- `Config`: Main configuration class
- `load_env_vars()`: Load and validate environment variables
- `get_api_keys()`: Return API credentials

**Usage**:
```python
from config.settings import Config
config = Config()
gemini_key = config.GEMINI_API_KEY
```

---

### 2️⃣ **core/** - Core Data Processing
```python
core/
├── __init__.py
├── data_processor.py
├── query_generator.py
└── code_executor.py
```

#### **data_processor.py**
**Purpose**: CSV data preprocessing and cleaning

**Key Functions**:
- `preprocess_csv(uploaded_file) -> pd.DataFrame`
- `validate_schema(df) -> bool`
- `clean_data(df) -> pd.DataFrame`

#### **query_generator.py**
**Purpose**: Convert natural language to pandas queries

**Key Classes**:
- `QueryGenerator`: Generate pandas code from NL
- Methods: `generate_query()`, `build_context()`, `sanitize_code()`

#### **code_executor.py**
**Purpose**: Safe execution of generated pandas code

**Key Classes**:
- `SafeExecutor`: Sandboxed code execution
- Methods: `execute()`, `validate_safety()`

---

### 3️⃣ **campaigns/** - Campaign Management
```python
campaigns/
├── __init__.py
├── base_campaign.py
├── sms_campaign.py
├── email_campaign.py
└── voice_campaign.py
```

#### **base_campaign.py**
**Purpose**: Abstract base class for all campaigns

**Key Class**:
```python
class BaseCampaign(ABC):
    @abstractmethod
    def validate_targets(self, df, required_cols)
    
    @abstractmethod
    def send(self, targets_df)
    
    def log_campaign(self, result)
```

#### **sms_campaign.py**
**Purpose**: SMS campaign implementation via Twilio

**Key Class**:
```python
class SMSCampaign(BaseCampaign):
    def __init__(self, account_sid, auth_token, from_phone)
    def send(self, targets_df, phone_col, name_col)
    def validate_phone(self, phone_number)
```

#### **email_campaign.py**
**Purpose**: Email campaign via Gmail SMTP

**Key Class**:
```python
class EmailCampaign(BaseCampaign):
    def __init__(self, email_user, email_pass, smtp_server)
    def send(self, targets_df, email_col, name_col)
    def create_html_message(self, name)
```

#### **voice_campaign.py**
**Purpose**: Voice call campaigns via Twilio

**Key Class**:
```python
class VoiceCampaign(BaseCampaign):
    def __init__(self, account_sid, auth_token, from_phone)
    def send(self, targets_df, phone_col)
    def create_twiml_message(self, message_text)
```

---

### 4️⃣ **ui/** - User Interface Components
```python
ui/
├── __init__.py
├── sidebar.py
├── chat.py
├── campaign_ui.py
└── monitor.py
```

#### **sidebar.py**
**Purpose**: Sidebar rendering and file upload

**Key Functions**:
- `render_sidebar() -> model`
- `handle_file_upload()`
- `display_data_preview(df)`

#### **chat.py**
**Purpose**: Chat interface and message handling

**Key Functions**:
- `render_chat_history()`
- `handle_user_query(prompt, df, model)`
- `display_response(response)`

#### **campaign_ui.py**
**Purpose**: Campaign launch interface

**Key Functions**:
- `render_campaigns()`
- `render_sms_campaign(df, model)`
- `render_email_campaign(df, model)`
- `render_voice_campaign(df, model)`

#### **monitor.py**
**Purpose**: Monitoring dashboard and analytics

**Key Functions**:
- `render_monitor()`
- `display_metrics()`
- `display_campaign_logs()`
- `export_logs()`

---

### 5️⃣ **utils/** - Utility Functions
```python
utils/
├── __init__.py
├── validators.py
├── logger.py
└── helpers.py
```

#### **validators.py**
**Purpose**: Input validation

**Key Functions**:
- `validate_phone_number(phone) -> bool`
- `validate_email(email) -> bool`
- `sanitize_input(text) -> str`

#### **logger.py**
**Purpose**: Custom logging configuration

**Key Functions**:
- `setup_logger(name) -> Logger`
- `log_campaign_activity(campaign_type, result)`

#### **helpers.py**
**Purpose**: Miscellaneous utility functions

**Key Functions**:
- `format_timestamp() -> str`
- `calculate_success_rate(sent, failed) -> float`
- `truncate_text(text, max_length) -> str`

---

## 🚀 Installation & Setup

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/churnguard-ai.git
cd churnguard-ai
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create `.env` file:
```env
# AI Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Email Configuration
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
```

### 5. Run Application
```bash
streamlit run app.py
```

---

## 📋 requirements.txt

```txt
streamlit==1.28.0
pandas==2.0.3
numpy==1.24.3
google-generativeai==0.3.1
twilio==8.10.0
python-dotenv==1.0.0
```

---

## 🔧 Module Development Guide

### Adding a New Campaign Type

1. **Create campaign module**: `campaigns/new_campaign.py`
```python
from campaigns.base_campaign import BaseCampaign

class NewCampaign(BaseCampaign):
    def __init__(self, *args):
        super().__init__()
        # Initialize API clients
    
    def validate_targets(self, df, required_cols):
        # Validation logic
        pass
    
    def send(self, targets_df):
        # Implementation
        pass
```

2. **Add UI component**: `ui/campaign_ui.py`
```python
def render_new_campaign(df, model):
    # UI implementation
    pass
```

3. **Register in main app**: `app.py`
```python
from campaigns.new_campaign import NewCampaign

# Add to campaign type selection
campaign_type = st.radio(
    "Select Campaign Type",
    ["SMS", "Email", "Voice", "New Type"]
)
```

### Adding a New Data Processor

1. **Create processor**: `core/new_processor.py`
```python
class NewProcessor:
    def process(self, df):
        # Processing logic
        return processed_df
```

2. **Integrate**: Update `core/__init__.py`
```python
from .new_processor import NewProcessor
```

---

## 🧪 Testing Structure

```
tests/
├── __init__.py
├── test_data_processor.py
├── test_query_generator.py
├── test_campaigns.py
└── test_validators.py
```

### Example Test
```python
# tests/test_validators.py
import pytest
from utils.validators import validate_phone_number

def test_valid_phone():
    assert validate_phone_number("9876543210") == True

def test_invalid_phone():
    assert validate_phone_number("123") == False
```

---

## 📊 Data Flow Architecture

```
User Input → Query Generator → Code Executor → Results
                                      ↓
                              Campaign Manager
                                      ↓
                          [SMS | Email | Voice]
                                      ↓
                              Monitor/Logger
```

---

## 🔐 Security Best Practices

1. **Environment Variables**: Never commit `.env` file
2. **Input Validation**: All user inputs validated before execution
3. **Safe Execution**: Sandboxed pandas query execution
4. **API Rate Limiting**: Implemented in campaign modules
5. **Logging**: Comprehensive audit trail

---

## 🚀 Deployment

### Docker Deployment
```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["streamlit", "run", "app.py"]
```

### Docker Compose
```yaml
# docker-compose.yml
version: '3.8'
services:
  churnguard:
    build: .
    ports:
      - "8501:8501"
    env_file:
      - .env
```

---

## 📚 API Reference

### Config Module
```python
from config.settings import Config
config = Config()
```

### Core Module
```python
from core.data_processor import preprocess_csv
from core.query_generator import QueryGenerator
from core.code_executor import SafeExecutor
```

### Campaign Module
```python
from campaigns.sms_campaign import SMSCampaign
from campaigns.email_campaign import EmailCampaign
from campaigns.voice_campaign import VoiceCampaign
```

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-module`
3. Follow module structure guidelines
4. Add tests for new modules
5. Submit pull request

---

## 📄 License

MIT License - See LICENSE file for details

---

**Built with modular architecture for scalability and maintainability**

*Last Updated: October 2025*