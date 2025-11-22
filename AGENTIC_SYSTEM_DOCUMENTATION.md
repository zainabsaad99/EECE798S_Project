# Agentic System Architecture Documentation

## Overview

This LinkedIn Content Agent uses an **agentic system** powered by OpenAI's function calling API. The agent orchestrates multiple tools to automate LinkedIn content generation workflows.

## Location

The agentic system is implemented in:
- **`backend/linkedin_agent.py`** - Core agent logic and tool implementations
- **`backend/app.py`** - API endpoints that trigger the agent

## How It Works

### Agent Orchestration

The main agent function is `run_agent_sequence()` in `backend/linkedin_agent.py` (lines 612-757). This function:

1. **Uses OpenAI Function Calling**: The agent uses GPT-4o-mini with function calling enabled to decide which tools to use and in what order.

2. **Orchestrates Tool Execution**: Instead of hardcoding a sequence, the AI agent decides:
   - When to scrape profiles
   - When to extract keywords
   - When to infer writing style
   - When to fetch trends

3. **Maintains Conversation History**: The agent maintains a conversation history with the LLM, including:
   - System prompts with instructions
   - Tool function calls and their results
   - Final JSON response with all extracted data

### Available Tools

The system defines 4 tools that the agent can call:

#### 1. `scrape_profile_tool`
- **Purpose**: Scrapes LinkedIn profile posts using PhantomBuster
- **Location**: `backend/linkedin_agent.py` (lines 486-501)
- **Function**: `scrape_profile_tool(phantom_api_key, session_cookie, user_agent, profile_url)`
- **Returns**: JSON URL and array of posts

#### 2. `extract_keywords_tool`
- **Purpose**: Extracts recurring interest phrases from posts using OpenAI
- **Location**: `backend/linkedin_agent.py` (lines 504-510)
- **Function**: `extract_keywords_tool(openai_api_key, posts)`
- **Returns**: Array of keyword phrases

#### 3. `infer_style_tool`
- **Purpose**: Infers writing style from LinkedIn posts using OpenAI
- **Location**: `backend/linkedin_agent.py` (lines 513-519)
- **Function**: `infer_style_tool(openai_api_key, posts)`
- **Returns**: Style notes describing writing tone and structure

#### 4. `fetch_trends_firecrawl_tool`
- **Purpose**: Fetches trending topics using Firecrawl search and OpenAI
- **Location**: `backend/linkedin_agent.py` (lines 522-529)
- **Function**: `fetch_trends_firecrawl_tool(firecrawl_api_key, openai_api_key, keywords, topic)`
- **Returns**: Array of trend items with titles and URLs

### Tool Schema Definition

Tool schemas are defined in `make_functions_schema()` (lines 549-608). These schemas tell OpenAI:
- What each tool does
- What parameters it requires
- How to call it

### Agent Workflow

The agent follows this general workflow:

1. **System Prompt**: Agent receives instructions on what steps to perform
2. **Tool Selection**: Agent decides which tool to call based on the current state
3. **Tool Execution**: Tool is executed and results are returned
4. **History Update**: Tool call and result are added to conversation history
5. **Next Decision**: Agent decides next action based on results
6. **Completion**: Agent returns final JSON with all extracted data

### Example Agent Sequence

When `run_agent_sequence()` is called:

```
Step 1: Agent calls scrape_profile_tool → Gets posts
Step 2: Agent calls extract_keywords_tool → Gets keywords
Step 3: Agent calls infer_style_tool → Gets style notes
Step 4: Agent calls fetch_trends_firecrawl_tool → Gets trends
Step 5: Agent returns final JSON with all data
```

### Key Features

1. **Intelligent Orchestration**: The agent can optimize workflows (e.g., if user profile and style profile are the same, it only scrapes once)

2. **Error Handling**: Each tool call is wrapped in error handling, and the agent can retry or adapt

3. **Flexible Execution**: The agent can adapt the sequence based on available data (e.g., using saved keywords instead of scraping)

4. **Function Calling**: Uses OpenAI's native function calling API, which allows the LLM to:
   - Understand available tools
   - Decide when to use them
   - Pass correct parameters
   - Handle results appropriately

## API Integration

The agent is triggered via:
- **Endpoint**: `POST /api/linkedin/run-agent`
- **Location**: `backend/app.py` (lines 370-501)
- **Flow**: Frontend → Backend API → `run_agent_sequence()` → Tools → Results

## Benefits of Agentic Approach

1. **Adaptability**: Agent can adjust workflow based on inputs
2. **Maintainability**: Adding new tools is easy - just add to schema
3. **Intelligence**: Agent can optimize and make decisions
4. **Extensibility**: New capabilities can be added as tools

## Tool Implementation Details

Each tool is implemented as a Python function that:
- Takes specific parameters
- Performs the operation (API calls, LLM calls, etc.)
- Returns structured data
- Handles errors gracefully

Tools are called via `call_tool_by_name()` (lines 532-546), which dispatches to the appropriate tool function.

