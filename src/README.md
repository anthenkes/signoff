# Application Structure

This directory contains the modularized time card sign-off automation application.

## Directory Structure

```
src/
├── play/                    # Playwright automation module
│   ├── pages/               # Page Object Models
│   │   ├── base_page.py
│   │   ├── login_page.py
│   │   ├── dashboard_page.py
│   │   ├── employee_page.py
│   │   └── signoff_confirmation_page.py
│   └── tests/              # Playwright tests
│       ├── test_login_page.py
│       ├── test_dashboard_page.py
│       ├── test_employee_page.py
│       ├── test_signoff_confirmation_page.py
│       ├── test_blue_check_mark.py
│       └── test_utils.py
│
├── db/                      # Database module (PostgreSQL + SQLAlchemy)
│   ├── __init__.py
│   ├── config.py           # Database configuration
│   ├── database.py         # Database connection & session management
│   └── models.py           # SQLAlchemy models
│
├── mail/                     # Email module
│   ├── __init__.py
│   ├── config.py          # Email configuration (Resend API)
│   └── email_service.py   # Email service implementation
│
├── endpoints/              # FastAPI application
│   ├── __init__.py
│   ├── config.py          # API configuration
│   └── main.py            # FastAPI app instance
│
├── config.py               # Base/shared configuration
├── models.py              # Shared data models (User, SignOffResult)
├── utils.py               # Shared utility functions
├── signoff_timecard.py    # Main automation script (used by Celery tasks)
├── env.example            # Example environment variables
└── users.json.example     # Example user configuration
```

## Module Descriptions

### `play/` - Playwright Automation
Contains all Playwright-related code for browser automation:
- **pages/**: Page Object Models for interacting with web pages
- **tests/**: Test scripts for validating page interactions

### `db/` - Database Module
PostgreSQL database integration using SQLAlchemy:
- **config.py**: Database connection configuration (reads from `DATABASE_URL` or individual `DB_*` env vars)
- **database.py**: SQLAlchemy engine, session factory, and connection management
- **models.py**: SQLAlchemy ORM models (add your database models here)

### `mail/` - Email Module
Email notification service using Resend API:
- **config.py**: Email configuration (Resend API key, from email, etc.)
- **email_service.py**: Service for sending sign-off result emails

### `endpoints/` - FastAPI Application
REST API endpoints:
- **config.py**: API configuration (title, description, host, port, etc.)
- **main.py**: FastAPI application instance with basic endpoints

### Root Files
- **config.py**: Base configuration (app settings, user loading, validation)
- **models.py**: Shared data models (User, SignOffResult dataclasses)
- **utils.py**: Shared utilities (logging, scheduling, formatting, etc.)
- **signoff_timecard.py**: Main script for automating time card sign-off (used by Celery tasks)
