# 📊 ChurnGuard AI Agent Platform

An intelligent customer retention platform that combines AI-powered data analysis with multi-channel campaign management. Features LLM-driven database queries, automated SMS/Email/Call campaigns, and real-time transcription via Twilio.

## ✨ Key Features

- **🤖 AI-Powered Data Analysis**: Natural language queries with LLM-driven SQL generation
- **📊 Turso DB Integration**: Dynamic schema generation and data storage
- **📱 Multi-Channel Campaigns**: SMS, Email, and LLM-powered Voice Call campaigns
- **🎙️ Call Transcription**: Automatic call recording and transcription via Twilio API
- **💬 Intelligent Chat**: General Q&A and data-specific queries with context awareness
- **📈 Campaign Monitoring**: Real-time dashboard with campaign analytics

## 🏗️ Project Structure

```
churnguard-ai/
│
├── app.py                          # Main Streamlit application entry point
├── chat.py                         # Chat functionality with Turso DB integration
├── .env                            # Environment variables
├── requirements.txt                # Python dependencies
├── README.md                       # This file
│
├── core/
│   ├── __init__.py
│   ├── llm.py                      # LLM utilities (sanitize, summarize, execute)
│   └── call_script_generator.py   # LLM-powered call script generation
│
├── db/
│   ├── __init__.py
│   └── turso.py                   # Turso DB integration (schema, queries, inserts)
│
├── campaigns/
│   ├── __init__.py
│   ├── sms.py                     # SMS campaign (Twilio)
│   ├── email.py                   # Email campaign (Gmail SMTP)
│   └── calls.py                   # LLM-powered call campaign with transcription
│
└── ui/
    ├── __init__.py
    ├── sidebar.py                 # Data upload and configuration
    └── monitor.py                 # Campaign monitoring dashboard
```

## 📦 Module Breakdown

### 1️⃣ **core/** - Core AI & LLM Functions

**llm.py**
- `sanitize_code()`: Clean LLM-generated code
- `build_chat_context()`: Build conversation context
- `generate_pandas_query()`: Generate pandas queries from natural language
- `safe_eval()`: Safe code execution
- `execute_and_summarize()`: Execute query and generate summary

**call_script_generator.py**
- `generate_call_script()`: Generate personalized call greetings and feedback questions using LLM

### 2️⃣ **db/** - Database Integration

**turso.py**
- `get_turso_client()`: Create Turso DB client
- `generate_create_table_sql()`: LLM-driven SQL schema generation
- `create_table_if_needed()`: Create table with unique names per upload
- `batch_insert_dataframe()`: Efficient data insertion
- `get_table_schema_sql()`: Retrieve table schema
- `generate_select_sql_from_prompt()`: LLM-driven SQL query generation
- `execute_select()`: Execute SELECT queries with DISTINCT

### 3️⃣ **campaigns/** - Campaign Management

**sms.py**
- `send_sms_campaign()`: Send SMS via Twilio
- `render_sms_campaign()`: SMS campaign UI with DB targeting

**email.py**
- `send_email_campaign()`: Send emails via Gmail SMTP
- `render_email_campaign()`: Email campaign UI with DB targeting

**calls.py**
- `send_call_campaign()`: LLM-powered voice calls with recording
- `fetch_transcripts_from_twilio()`: Fetch call transcripts via Twilio API
- `render_call_campaign()`: Call campaign UI with transcript fetching
- `_detect_name_column()`: Auto-detect customer name columns
- `_create_call_twiml()`: Generate TwiML for calls

### 4️⃣ **ui/** - User Interface

**sidebar.py**
- `render_sidebar()`: Render sidebar with data upload
- `preprocess_csv()`: CSV preprocessing and validation
- Turso DB sync integration

**monitor.py**
- `render_monitor()`: Campaign monitoring dashboard

### 5️⃣ **chat.py** - Chat Functionality

- `render_chat_history()`: Display chat messages with code/data
- `handle_user_query()`: Process user queries with DB/LLM routing
- `_is_data_availability_query()`: Detect data availability questions
- `_wants_actual_data()`: Detect requests to view data
- `_is_general_question()`: Detect general knowledge questions
- `_answer_general_question()`: Handle general Q&A

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
Create `.env` file in the project root:
```env
# AI Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# Turso Database
TURSO_DB_URL=libsql://your-database-name.turso.io
TURSO_DB_AUTH_TOKEN=your_turso_auth_token

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Email Configuration
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_gmail_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
```

### 5. Run Application
```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

## 📋 Requirements

```txt
streamlit
pandas
numpy
google-generativeai
twilio
python-dotenv
libsql-client
```

## 🔥 Key Features Explained

### 🤖 LLM-Powered Database Queries

The platform uses Gemini LLM to:
- **Generate SQL schemas** dynamically based on uploaded CSV structure
- **Create SQL queries** from natural language prompts
- **Handle LIKE/WHERE/DISTINCT** clauses intelligently
- **Provide fallback heuristics** when LLM output is invalid

### 📊 Turso DB Integration

- **Dynamic Schema Generation**: Each CSV upload creates a unique table
- **Automatic Data Sync**: Data uploaded once, queried infinitely
- **LLM-Driven Queries**: Natural language → SQL conversion
- **Duplicate Prevention**: SELECT DISTINCT enforced

### 📞 LLM-Powered Call Campaigns

- **Personalized Scripts**: AI generates custom greetings per customer
- **Feedback Collection**: Automated feedback questions
- **Call Recording**: All calls recorded automatically
- **Transcription**: Transcripts fetched via Twilio API (no webhook needed)
- **JSON Format**: Transcripts stored in structured JSON format

### 💬 Intelligent Chat

- **Dual-Mode**: Handles both data queries and general questions
- **Context Awareness**: Routes to DB → Pandas → General LLM as needed
- **Data Display**: Shows actual data when requested
- **Concise Summaries**: LLM provides clear, actionable answers

## 📊 Data Flow

```
CSV Upload → Preprocessing → Turso DB (Dynamic Schema)
                                      ↓
                              Chat Query / Campaign
                                      ↓
                          LLM: Natural Language → SQL
                                      ↓
                              Execute Query → Results
                                      ↓
                    [Display Data] or [Launch Campaign]
                                      ↓
                    [SMS/Email/Call] → Monitor Dashboard
```

## 🎯 Usage Guide

### Uploading Data

1. Click "Upload CSV" in the sidebar
2. Select your customer data file
3. Data is automatically synced to Turso DB
4. Unique table created per upload

### Asking Questions

**Data Queries:**
- "How many customers have churn_probability > 0.8?"
- "Show me customers from Mumbai with high monthly charges"
- "Count total customers by subscription type"

**General Questions:**
- "What is customer churn?"
- "How do I improve retention?"
- Any general knowledge question

### Launching Campaigns

1. Go to "🚀 Campaigns" tab
2. Select campaign type (SMS/Email/Call)
3. Enter targeting condition in natural language
4. Preview target customers
5. Launch campaign
6. Monitor results in "📊 Monitor" tab

### Call Transcripts

1. Launch a call campaign
2. Wait 1-2 minutes for transcription
3. Click "🔄 Fetch Recent Transcripts" or "🔄 Fetch Transcripts for Last Campaign"
4. View transcripts in JSON format

## 🔧 Development

### Adding a New Campaign Type

1. Create `campaigns/new_campaign.py`:
```python
def send_new_campaign(targets_df, col, model=None):
    # Implementation
    pass

def render_new_campaign(df, model):
    # UI implementation
    pass
```

2. Register in `app.py`:
```python
from campaigns.new_campaign import render_new_campaign

if campaign_type == "New Campaign":
    render_new_campaign(df, model)
```

### Extending Database Functions

Add to `db/turso.py`:
```python
def new_turso_function(client, table_name, params):
    # Implementation
    pass
```

## 🛠️ Troubleshooting

### Turso DB Connection Issues
- Verify `TURSO_DB_URL` and `TURSO_DB_AUTH_TOKEN` in `.env`
- Check network connectivity
- Ensure Turso database is active

### Transcript Fetching
- Wait 1-2 minutes after calls complete
- Verify Twilio credentials are correct
- Check call status in Twilio console

### LLM Query Generation
- Verify `GEMINI_API_KEY` is set
- Check API quota/limits
- Review logs for error messages

## 📚 API Reference

### Database Functions
```python
from db.turso import get_turso_client, execute_select

client = get_turso_client()
rows, cols = execute_select(client, "SELECT * FROM table")
```

### Campaign Functions
```python
from campaigns.sms import send_sms_campaign
from campaigns.email import send_email_campaign
from campaigns.calls import send_call_campaign

result = send_sms_campaign(df, "PhoneNo", model=model)
```

### LLM Functions
```python
from core.llm import execute_and_summarize

response = execute_and_summarize(prompt, df, model)
```

## 🔐 Security Best Practices

1. **Environment Variables**: Never commit `.env` file
2. **API Keys**: Store securely, rotate regularly
3. **Input Validation**: All queries sanitized before execution
4. **Safe Execution**: Sandboxed code execution
5. **Logging**: Comprehensive audit trail

## 🚀 Deployment

### Streamlit Cloud

1. Push to GitHub
2. Connect to Streamlit Cloud
3. Add environment variables in dashboard
4. Deploy!

## 📝 Changelog

### Latest Updates
- ✅ LLM-powered call script generation
- ✅ Twilio API transcript fetching (no webhook needed)
- ✅ Auto-detection of customer name columns
- ✅ Enhanced chat with general Q&A support
- ✅ Improved SQL query generation with fallbacks
- ✅ Duplicate prevention in queries


