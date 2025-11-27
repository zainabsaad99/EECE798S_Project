# EECE798S Project

A full-stack application with Flask frontend, backend API, and multiple microservices for content generation, LinkedIn agent functionality, and gap analysis.

## 🚀 Quick Start

### Option 1: Use the Deployed Version (Recommended)

You can access the live application without any local setup:

**Frontend URL:** https://frontend-app.politesmoke-54b92664.eastus.azurecontainerapps.io

Simply open the URL in your browser to start using the application.

---

### Option 2: Run Locally

Follow these steps to run the application on your local machine:

#### Prerequisites

- [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/) installed
- Git (to clone the repository)

#### Setup Steps

1. **Clone the repository** (if you haven't already)
   ```bash
   git clone <repository-url>
   cd EECE798S_Project
   ```

2. **Create a `.env` file** in the project root directory
   
   Create a `.env` file with the following environment variables:
   ```env
   # Database Configuration
   MYSQL_DATABASE=NextGenAI
   MYSQL_ROOT_PASSWORD=password
   
   # Flask Configuration
   SECRET_KEY=your-secret-key-here
   FLASK_ENV=development
   
   # ============================================
   # REQUIRED API KEYS
   # ============================================
   
   # OpenAI API Key - Get from: https://platform.openai.com/api-keys
   OPENAI_API_KEY=sk-proj-ta6plQ0FIr9YkpRXT3CUTya4HLA1sycGw**-dMO9jFzKMGwFlrybabVXpa5CHBvtEsm3e3I81gT3BlbkFJCSJIXxBTFMMyAQoTksOU6v4x3BNH7S7w2K_u6JKxfhI_sAkJQa94CBu1gN_jr_oHcSfhnHXkgA
   # Replace ** with: AQ
   
   # PhantomBuster API Key - Get from: https://www.phantombuster.com/
   PHANTOMBUSTER_API_KEY=Pyu5Vs**IJ58AGePW6gK68pwEDTNlHPYNCWOOmxccX4
   # Replace ** with: El
   
   # Firecrawl API Key - Get from: https://www.firecrawl.dev/
   FIRECRAWL_API_KEY=fc-**8e3d8da9bf4560a320ca55cfa483a9
   # Replace ** with: 79
   
   # ============================================
   # REQUIRED LINKEDIN CREDENTIALS
   # ============================================
   
   # LinkedIn Session Cookie
   # How to get: F12 → Application → Cookies → linkedin.com → Copy "li_at" value
   LINKEDIN_SESSION_COOKIE=AQEDAV_V5FYA**PWAAABmeNAxoYAAAGav4JyV04AB0dHLZkJjmEOeY1v6oXTpJ6RPG2DbJU1WdcuQ6cdrExVBfA6BQ-CCTlxVhi66n91WNscgAeMW67mXNgv333Jk9IqYuvZ8RqhqXU-3imYKQF0LDeX
   # Replace ** with: gs
   
   # Browser User Agent
   # Get from: https://www.whatismybrowser.com/detect/what-is-my-user-agent
   USER_AGENT=Mo**illa/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36
   # Replace ** with: zz
   
   # Google Sheets (Optional)
   GOOGLE_SHEET_URL=your-google-sheet-url
   ```

3. **Build and start the services**
   ```bash
   docker-compose up --build
   ```

   This command will:
   - Build Docker images for all services
   - Start the MySQL database
   - Start the backend API
   - Start the frontend application
   - Start the Fetch_Website service
   - Start the trend_keywords service

4. **Access the application**
   
   Once all containers are running, open your browser and navigate to:
   ```
   http://localhost:3000
   ```

#### Service Ports

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:5000
- **MySQL Database:** localhost:3306
- **Fetch Website Service:** http://localhost:3001
- **Trend Keywords Service:** http://localhost:3002

#### Stopping the Application

To stop all services:
```bash
docker-compose down
```

To stop and remove volumes (this will delete the database data):
```bash
docker-compose down -v
```

#### Viewing Logs

To view logs from all services:
```bash
docker-compose logs -f
```

To view logs from a specific service:
```bash
docker-compose logs -f frontend
docker-compose logs -f backend
docker-compose logs -f db
```

---

## 📁 Project Structure

```
EECE798S_Project/
├── frontend/          # Flask frontend application
├── backend/           # Flask backend API
├── Fetch_Website/     # Website extraction service
├── trend_keywords/    # Trend keywords and LLM service
├── mysql/             # Database schema
├── docker-compose.yml # Docker Compose configuration
└── .env              # Environment variables (create this)
```

---

## 🔧 Troubleshooting

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
- Some features may not work without valid API keys

---

## 📝 Notes

- The application uses Docker Compose for orchestration
- All services communicate through a Docker network
- The database schema is automatically initialized on first run
- Environment variables are loaded from the `.env` file in the project root

---

## DEMO Video
Demo_eece798.mp4
