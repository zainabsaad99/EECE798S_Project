# EECE798S Project - Fall 2025-2026
## Team Members
**Aline Hassan**

**Jenny Haddad**

**Zeinab Saad**


A comprehensive full-stack AI-powered application for automated content generation, LinkedIn automation, gap analysis, and social media management. This project leverages multiple AI agents, web scraping, and cloud services to provide intelligent content creation and business intelligence capabilities.

## 📋 Project Overview

This application provides a suite of AI-powered tools designed to streamline content creation and business analysis workflows:

### Core Functionalities

1. **LinkedIn Content Agent**
   - Automated LinkedIn profile scraping and analysis
   - Intelligent post generation based on user's writing style
   - Keyword extraction from LinkedIn activity
   - Trend analysis and integration
   - Automated posting to LinkedIn via PhantomBuster
   - Google Sheets integration for content management

2. **Social Media Content Generation**
   - Multi-platform content creation (LinkedIn, Twitter, Instagram, Facebook)
   - AI-generated images with logo placement
   - Customizable content styles and formats
   - Reference image-based styling

3. **Proposal Generation**
   - Automated proposal content creation
   - Image generation for proposals
   - Customizable templates and formats

4. **Gap Analysis**
   - Market trend identification
   - Competitive analysis
   - Business opportunity detection
   - Keyword-based trend analysis
   - Semantic similarity analysis

5. **Website Data Extraction**
   - Automated website scraping
   - Product and company information extraction
   - Trend keyword identification
   - Data storage and management

6. **User Management**
   - User authentication and registration
   - Activity tracking
   - Dashboard with statistics
   - Data persistence

---

## 📊 Evaluation Metrics

To measure the quality and reliability of our system, we built a semantic evaluation pipeline powered by embedding. To validate the quality, reliability, and alignment of our system's outputs, we developed a multi-stage evaluation framework:

### 1. Evaluation Dataset Construction

We curated a structured evaluation dataset containing:

- Ground-truth business profiles
- Ground-truth market trends
- Expected keyword associations
- Gold-standard proposals and outputs

This dataset is used consistently across all evaluation components to benchmark system performance.

### 2. Keyword & Profile Matching (Bi-gram + Rule-Based Checks)

We used bi-gram extraction and matching to compare:

- Extracted company profiles vs. ground truth
- Generated keyword sets vs. gold-standard keywords

**Accuracy: 93%**

### 3. Trend Alignment Evaluation (LLM-as-a-Judge)

To measure how well the system identifies relevant trends, we use an LLM evaluator that:

- Compares system-extracted trends with the reference trends
- Judges relevance, correctness, and contextual alignment

**Accuracy: 84%**

### 4. Coverage Classification Using Embeddings + Cosine Similarity

To verify the correctness of predicted covered, weak coverage, and gap labels, we compute:

- Embedding vectors for products and trends
- Cosine similarity between them
- Threshold-based classification

**Accuracy: 79%**

### 5. Proposal Quality Evaluation (LLM-as-a-Judge)

For each generated proposal, an LLM performs a structured evaluation and assigns a 1–10 score for each dimension across six strategic dimensions:

- Strategic Fit
- Market Relevance
- Gap Exploitation
- Feasibility
- Differentiation
- Clarity

**Score: 7/10**

### 6. Content Creation

We evaluated our system on 306 posts across Instagram, Twitter, TikTok, and LinkedIn using a hybrid evaluation method combining cosine similarity and an LLM-as-a-Judge framework.

The average performance scores are:

| Metric            | Average Score |
|-------------------|---------------|
| Tone Match        | 89.09         |
| Format Fit        | 90.45         |
| Writing Quality   | 89.16         |
| Human-Likeness    | 94.15         |
| Final Score       | 90.02         |

---

## 🚀 Quick Start

### Option 1: Use the Deployed Version (Recommended)

**We highly recommend using the deployed version for the best experience without any setup hassle.**

**Frontend URL:** https://frontend-app.politesmoke-54b92664.eastus.azurecontainerapps.io

Simply open the URL in your browser to start using all the application features immediately. No installation or configuration required!

**⚠️ Important Note for Deployed Version:**
- If you experience any issues with **fetching websites** or **gap analysis** features, this likely means the available Firecrawl API credits have been exhausted. In this case, please run the application locally and use your own Firecrawl API key (see Step 5 in the local setup instructions below).

---

### Option 2: Run Locally

If you want to run the application locally for development or customization, follow the comprehensive setup guide below.

#### Prerequisites

- [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/) installed
- Git (to clone the repository)
- Accounts for the following services (setup instructions provided below):
  - OpenAI (with image model access)
  - PhantomBuster
  - Firecrawl
  - Google Cloud Platform (for Google Sheets integration)

---

## 📦 Local Setup Instructions

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd EECE798S_Project
```

### Step 2: Create Google Sheet and Set Up Google Cloud

1. **Create a Google Sheet**
   - Go to [Google Sheets](https://sheets.google.com)
   - Create a new spreadsheet
   - Note the URL (you'll need it later for `GOOGLE_SHEET_URL`)

2. **Set Up Google Cloud Console**
   
   Follow these steps to get your Google Service Account credentials:

   1. **Visit Google Cloud Console**
      - Go to [Google Cloud Console](https://console.cloud.google.com/)

   2. **Create a New Project**
      - Click on the project dropdown at the top
      - Click "New Project"
      - Enter a project name (e.g., "EECE798S-Project")
      - Click "Create"

   3. **Go to API and Services**
      - In the left sidebar, navigate to "APIs & Services" → "Library"

   4. **Enable Google Sheets API**
      - Search for "Google Sheets API"
      - Click on it and press "Enable"

   5. **Create Service Account Credentials**
      - Go to "APIs & Services" → "Credentials"
      - Click "Create Credentials" → "Service Account"
      - Enter a name for the service account (e.g., "sheets-service")
      - Click "Create and Continue"
      - Skip optional steps and click "Done"

   6. **Download the JSON Key File**
      - Click on the created service account
      - Go to the "Keys" tab
      - Click "Add Key" → "Create new key"
      - Select "JSON" format
      - Click "Create" - the JSON file will download automatically

   7. **Share Google Sheet with Service Account**
      - Open the downloaded JSON file
      - Copy the `client_email` value (e.g., `your-service-account@project-id.iam.gserviceaccount.com`)
      - Open your Google Sheet
      - Click "Share" button
      - Paste the service account email
      - Give it "Editor" permissions
      - Click "Send"

### Step 3: Get OpenAI API Key

1. **Create/Login to OpenAI Account**
   - Go to [OpenAI Platform](https://platform.openai.com/)
   - Sign up or log in

2. **Get API Key**
   - Navigate to [API Keys](https://platform.openai.com/api-keys)
   - Click "Create new secret key"
   - Copy the API key (you won't be able to see it again)

3. **Verify Image Model Access**
   - Go to your [Organization Settings](https://platform.openai.com/org-settings)
   - Verify that your organization has access to image generation models (DALL-E)
   - If not, you may need to upgrade your plan or request access
   - **Important:** The application requires access to OpenAI's image models for content generation

### Step 4: Set Up PhantomBuster

1. **Create PhantomBuster Account**
   - Go to [PhantomBuster](https://www.phantombuster.com/)
   - Sign up for an account

2. **Activate Developer Mode**
   - Log in to your PhantomBuster account
   - Go to your Profile → Advanced Settings
   - Enable "Developer Mode"
   - This will give you access to API keys and phantom management

3. **Get API Key**
   - After enabling Developer Mode, go to your account settings
   - Find your API key in the API section
   - Copy the API key

4. **Create Required Phantoms**
   
   You need to create two phantoms in PhantomBuster:

   a. **LinkedIn Activity Extractor**
      - Go to PhantomBuster dashboard
      - Click "Create a Phantom"
      - Search for "LinkedIn Activity Extractor" or similar
      - Create and configure the phantom
      - Note the Phantom ID (found in the phantom's URL or settings)

   b. **LinkedIn Auto Poster**
      - Create another phantom
      - Search for "LinkedIn Auto Poster" or similar
      - Create and configure the phantom
      - Note the Phantom ID

5. **Update Phantom IDs in Code**
   - Open `backend/linkedin_agent.py`
   - Find these lines (around line 44-45):
     ```python
     SCRAPE_AGENT_ID = "157605755168271"  # LinkedIn Activities Scraper
     POST_AGENT_ID = "4269915876888936"    # LinkedIn Auto Poster
     ```
   - Replace `SCRAPE_AGENT_ID` with your LinkedIn Activity Extractor phantom ID
   - Replace `POST_AGENT_ID` with your LinkedIn Auto Poster phantom ID

### Step 5: Get Firecrawl API Key

1. **Create Firecrawl Account**
   - Go to [Firecrawl](https://www.firecrawl.dev/)
   - Sign up for an account

2. **Get API Key**
   - After signing up, navigate to your dashboard
   - Find your API key in the API section
   - Copy the API key

### Step 6: Get LinkedIn Session Cookie

1. **Log in to LinkedIn**
   - Open LinkedIn in your browser
   - Log in to your account

2. **Extract Session Cookie**
   - Open Developer Tools (F12 or Right-click → Inspect)
   - Go to the "Application" tab (Chrome) or "Storage" tab (Firefox)
   - In the left sidebar, expand "Cookies" → `https://www.linkedin.com`
   - Find the cookie named `li_at`
   - Copy the entire value of the `li_at` cookie
   - **Note:** This cookie is used for scraping LinkedIn profiles. Keep it secure and don't share it.

3. **Get User Agent**
   - While in Developer Tools, go to the "Console" tab
   - Type: `navigator.userAgent` and press Enter
   - Copy the returned value
   - Alternatively, visit [WhatIsMyBrowser.com](https://www.whatismybrowser.com/detect/what-is-my-user-agent) to get your user agent

**⚠️ Important Note for Linux/Mac Users:**
- If you are working on **Linux or Mac** and experience any issues with **posting on LinkedIn**, make sure you sign in to LinkedIn on **Windows** to get the session cookie. The LinkedIn session cookie format may differ between operating systems, and using a Windows-generated cookie ensures compatibility with the posting functionality.

### Step 7: Create .env File

Create a `.env` file in the project root directory (`EECE798S_Project/.env`) with the following content:

```env


# OpenAI API Key
# Get from: https://platform.openai.com/api-keys
# Make sure your organization has access to image models
OPENAI_API_KEY=

# PhantomBuster API Key
# Get from: https://www.phantombuster.com/ (after enabling Developer Mode)
PHANTOMBUSTER_API_KEY=

# Firecrawl API Key
# Get from: https://www.firecrawl.dev/
FIRECRAWL_API_KEY=

# LinkedIn Credentials
# Get li_at cookie from browser Developer Tools (Application → Cookies → linkedin.com)
LINKEDIN_SESSION_COOKIE=

# Browser User Agent
# Get from browser Developer Tools console: navigator.userAgent
USER_AGENT=

# Google Service Account Credentials
# Extract from the downloaded JSON file from Google Cloud Console
GOOGLE_SERVICE_ACCOUNT_TYPE=
GOOGLE_SERVICE_ACCOUNT_PROJECT_ID=
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_ID=
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY=""
GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL=
GOOGLE_SERVICE_ACCOUNT_CLIENT_ID=
GOOGLE_SERVICE_ACCOUNT_AUTH_URI=
GOOGLE_SERVICE_ACCOUNT_TOKEN_URI=
GOOGLE_SERVICE_ACCOUNT_AUTH_PROVIDER_X509_CERT_URL=
GOOGLE_SERVICE_ACCOUNT_CLIENT_X509_CERT_URL=
GOOGLE_SERVICE_ACCOUNT_UNIVERSE_DOMAIN=

# Google Sheet URL
# The URL of the Google Sheet you created (make sure it's shared with the service account email) and the shared URL provide editor mode.
GOOGLE_SHEET_URL=
```

**How to Fill Google Service Account Variables:**

Open the JSON file you downloaded from Google Cloud Console. It will look like this:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "key-id-here",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service@project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/...",
  "universe_domain": "googleapis.com"
}
```

Copy each value to the corresponding `.env` variable:
- `type` → `GOOGLE_SERVICE_ACCOUNT_TYPE`
- `project_id` → `GOOGLE_SERVICE_ACCOUNT_PROJECT_ID`
- `private_key_id` → `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_ID`
- `private_key` → `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY` (keep the `\n` characters as they are)
- `client_email` → `GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL`
- `client_id` → `GOOGLE_SERVICE_ACCOUNT_CLIENT_ID`
- `auth_uri` → `GOOGLE_SERVICE_ACCOUNT_AUTH_URI`
- `token_uri` → `GOOGLE_SERVICE_ACCOUNT_TOKEN_URI`
- `auth_provider_x509_cert_url` → `GOOGLE_SERVICE_ACCOUNT_AUTH_PROVIDER_X509_CERT_URL`
- `client_x509_cert_url` → `GOOGLE_SERVICE_ACCOUNT_CLIENT_X509_CERT_URL`
- `universe_domain` → `GOOGLE_SERVICE_ACCOUNT_UNIVERSE_DOMAIN`

**Important Notes:**
- For `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY`, keep the entire value including `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----` and all `\n` characters
- Make sure there are no extra spaces or quotes around the values
- The `GOOGLE_SHEET_URL` should be the full URL of your Google Sheet (e.g., `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`)

### Step 8: Build and Run with Docker Compose

1. **Build and start all services:**
   ```bash
   docker-compose up --build
   ```

   This command will:
   - Build Docker images for all services (frontend, backend, database, fetch_website, trend_keywords)
   - Start the MySQL database
   - Start the backend API
   - Start the frontend application
   - Start the Fetch_Website service
   - Start the trend_keywords service

2. **Wait for the build to complete**
   - The first build may take several minutes
   - Wait until you see messages indicating all services are running
   - Look for "Running on http://0.0.0.0:3000" for the frontend

3. **Access the application**
   - Open your browser and navigate to:
     ```
     http://localhost:3000
     ```
   - The application should now be running locally!

### Step 9: Start Experiencing the Functions

Once the application is running, you can:

- **Sign up/Sign in** to create an account
- **Use the LinkedIn Agent** to scrape profiles, generate posts, and auto-post
- **Generate Social Media Content** for multiple platforms
- **Create Proposals** with AI-generated content and images
- **Run Gap Analysis** to identify market opportunities
- **Extract Website Data** and analyze trends
- **View Dashboard Statistics** and track your activity

---

## 🧪 Testing Gap Analysis with Example Businesses

To help you get started with the Gap Analysis feature, we've included example business profiles that you can use for testing. These examples demonstrate real small businesses that you can analyze.

### Example Businesses

1. **[3abayad](https://3abayad.com)** - A premium Lebanese egg white product company offering pasteurized liquid egg whites in glass bottles.

2. **[GetEnergyze](https://getenergyze.com)** - A health and wellness brand specializing in moringa powder supplements for energy, gut health, and immunity.

### Using Example Business Profiles

1. **Locate the Example Files**
   - Navigate to the `businesses_examples/` folder in the repository
   - You'll find JSON files for each example business:
     - `3abayad_description.json`
     - `energy_description.json`

2. **Upload a Business Profile**
   - Go to the **Upload Profile** page in the application (for Gap Analysis)
   - Download one of the JSON files from the `businesses_examples/` folder
   - Upload the JSON file to test the gap analysis functionality
   - The system will analyze the business and identify market opportunities

3. **Testing Different Businesses**
   - If you want to test with different businesses, you'll need to create a JSON file following the same structure
   - The JSON file should contain an array with business objects that include:
     - `name`: Business name
     - `strapline`: Business mission or tagline
     - `audience`: Target audience description
     - `products`: Array of product objects, each with:
       - `name`: Product name
       - `description`: Detailed product description

   **Example JSON Structure:**
   ```json
   [
     {
       "name": "Your Business Name",
       "strapline": "Your business mission or tagline",
       "audience": "Description of your target audience",
       "products": [
         {
           "name": "Product Name",
           "description": "Detailed description of the product"
         }
       ]
     }
   ]
   ```

4. **What the Gap Analysis Does**
   - Analyzes your business profile against current market trends
   - Identifies gaps in your product offerings
   - Suggests opportunities based on trending keywords
   - Provides insights on market positioning

---

## 🎥 Demo Video

A demo video (`Demo_eece798.mp4`) is available to showcase the different functionalities of the application. The video demonstrates all features at high speed, giving you a quick overview of what the application can do.

---

## 📁 Project Structure

```
EECE798S_Project/
├── frontend/              # Flask frontend application
│   ├── static/           # CSS, JS, and other static files
│   └── templates/        # HTML templates
├── backend/              # Flask backend API
│   ├── app.py           # Main Flask application
│   ├── linkedin_agent.py # LinkedIn automation agent
│   ├── content_agent.py  # Social media content generation
│   ├── proposal_agent.py # Proposal generation
│   ├── gap_analysis.py   # Gap analysis functionality
│   └── Dockerfile        # Backend Docker configuration
├── Fetch_Website/        # Website extraction service
├── trend_keywords/       # Trend keywords and LLM service
├── businesses_examples/  # Example business JSON files for gap analysis testing
│   ├── 3abayad_description.json
│   └── energy_description.json
├── mysql/                # Database schema
│   └── schema.sql       # Database initialization script
├── docker-compose.yml    # Docker Compose configuration
└── .env                  # Environment variables (create this)
```

---

## 🔌 Service Ports

When running locally:

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:5000
- **MySQL Database:** localhost:3306
- **Fetch Website Service:** http://localhost:3001
- **Trend Keywords Service:** http://localhost:3002

---

## 🛠️ Troubleshooting

### Port Already in Use

If you encounter port conflicts:
- Check if ports 3000, 5000, 3001, 3002, or 3306 are already in use
- Stop conflicting services or modify ports in `docker-compose.yml`

### Database Connection Issues

- Ensure MySQL container is running: `docker-compose ps`
- Check database credentials in `.env` file
- Verify the database schema is initialized (check `mysql/schema.sql`)

### API Key Issues

- Ensure all required API keys are set in the `.env` file
- Verify OpenAI API key has image model access
- Check PhantomBuster API key is valid and Developer Mode is enabled
- Verify Google Service Account JSON credentials are correctly formatted
- Ensure LinkedIn session cookie (`li_at`) is valid and not expired
- **For Linux/Mac users:** If LinkedIn posting fails, try getting the session cookie from a Windows machine, as cookie formats may differ between operating systems
- **For deployed version:** If website fetching or gap analysis fails, the Firecrawl API credits may be exhausted - run locally with your own API key

### Google Sheets Issues

- Verify the Google Sheet is shared with the service account email
- Check that Google Sheets API is enabled in Google Cloud Console
- Ensure all Google Service Account variables are correctly set in `.env`
- Verify the `GOOGLE_SHEET_URL` is correct

### PhantomBuster Issues

- Ensure Developer Mode is enabled in PhantomBuster
- Verify the Phantom IDs are correctly updated in `backend/linkedin_agent.py`
- Check that both phantoms (LinkedIn Activity Extractor and Auto Poster) are created and configured

### Docker Build Issues

- Make sure Docker and Docker Compose are properly installed
- Try cleaning Docker cache: `docker system prune -a`
- Rebuild without cache: `docker-compose build --no-cache`

---

## 📝 Additional Notes

- The application uses Docker Compose for orchestration
- All services communicate through a Docker network
- The database schema is automatically initialized on first run
- Environment variables are loaded from the `.env` file in the project root
- The LinkedIn session cookie may expire - you'll need to update it periodically
- Some features require valid API keys to function properly

---

## 🔒 Security Notes

- **Never commit your `.env` file** to version control
- Keep your API keys secure and don't share them
- The LinkedIn session cookie provides access to your LinkedIn account - treat it as a password
- Regularly rotate API keys for security
- The `.env` file is already in `.gitignore` to prevent accidental commits

---

## 📄 License

This project is part of EECE798S coursework.
