# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Multi-agent architecture with Finance, Strategy, and Data Engineer agents
- Router agent for intent-based request delegation
- Streamlit UI ("Wealth OS | Quant Terminal") with analytics dashboard
- Pydantic AI web interface with Swagger API documentation
- Finance Clerk CLI for natural language expense tracking
- Wealth Director CLI for strategic planning with multi-agent coordination
- Supabase integration with separate expense and income repositories
- MLflow observability for agent run tracing and evaluation
- Domain-driven design structure with models, services, and repositories
- Category mapping service for natural language to financial categories
- Budget planning with 50/30/20 rule
- Financial analytics: burn rate, runway, savings ratio
- Data seeder for generating 90 days of synthetic financial data
- Data integrity validation via Data Engineer Agent
- Multiple LLM provider support (Ollama, Gemini, OpenAI)
- Dependency injection container for agent configuration
- Error handling and logging decorator for agent tools
- Currency selector in Streamlit UI (USD, INR, EUR, GBP, JPY, KRW, BTC)
- Data purge and seeding tools in Streamlit Data Lab

### Architecture
- Finance domain package (`finance/`) with models, services, repositories
- Core services (`core/`) for settings, container, dependencies, observability
- Agent layer (`agents/`) with specialized AI agents
- Data layer (`data/`) with Supabase repository implementations
- Application layer (`application/`) with DTOs
