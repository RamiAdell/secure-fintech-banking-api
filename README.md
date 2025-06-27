# 💳 Banking FinTech API — Secure Django REST API for Financial Platforms

A complete **Banking & FinTech API** built with Django REST Framework and Docker, integrating production-ready tools like Celery, Redis, RabbitMQ, Flower, NGINX, and PostgreSQL. Secure, scalable, and ready for deployment 🚀

---

## 🧠 Topics Covered in This Project

- ✅ Used **Docker** with Django, PostgreSQL, Redis, and RabbitMQ
- ✅ Set up **Celery** with **RabbitMQ** and **Redis** for background tasks
- ✅ Integrated **Flower** to monitor Celery workers
- ✅ Served static and media files via **NGINX**
- ✅ Secured the API using **HTTPS (SSL Certificates)** with Let's Encrypt
- ✅ Configured **reverse proxy** and **load balancing** using NGINX
- ✅ Managed Docker containers in production using **Portainer**
- ✅ Backed up PostgreSQL using automated **shell scripts**
- ✅ Deployed the Django app on an **Ubuntu server with a custom domain**
- ✅ Built reusable Docker-related commands using **Makefiles**
- ✅ Implemented centralized logging with **Loguru**
- ✅ Automated and monitored services using **Bash scripts**

---

## 🚀 Tech Stack

| Tech         | Purpose                             |
|--------------|-------------------------------------|
| Django       | Web framework (DRF)                 |
| DRF          | REST API backend                    |
| Redis        | Celery broker (can use RabbitMQ too)|
| RabbitMQ     | Optional message broker             |
| Postgres     | Database                            |
| Docker       | Containerization                    |
| NGINX        | Reverse proxy and static serving    |
| Flower       | Task monitoring UI                  |
| Portainer    | Docker container manager UI         |
| Loguru       | Logging system                      |
| Let's Encrypt| Free SSL certificates               |
| Shell Scripts| Automation and backups              |
| Makefile     | Simplify Docker commands            |

---

## 🚦 Setup & Installation

### 1. Clone the Repository

```bash
   git clone https://github.com/RamiAdell/banking-fintech-api.git
   cd banking-fintech-api
```
### 2. Copy and configure environment variables

```bash
   cp .env.example .env
```
Edit `.env` and fill in  secrets, DB config, email backend, etc.

### 3. Build and run local containers

```bash
   docker compose -f local.yml up --build
```
### 4. Run migrations & create superuser

```bash
   docker compose -f local.yml run --rm api python manage.py migrate
   docker compose -f local.yml run --rm api python manage.py createsuperuser
```

---

## 🌱 Environment Structure

```
banking-fintech-api/
│
├── .env/
│   └── .env.example
│
├── local.yml
│
├── backups/
│
├── config/
│   └── settings/
│       ├── base.py
│       ├── local.py
│       └── production.py
│
├── core_apps/
│   ├── user_auth/
│   ├── user_profile/
│   └── ... other Django apps ...
│
├── docker/
│   ├── local/
│   │   ├── django/
│   │   │   ├── Dockerfile
│   │   │   ├── entrypoint.sh
│   │   │   ├── start.sh
│   │   │   └── celery/
│   │   │       ├── worker.sh
│   │   │       └── beat.sh
│   │   ├── nginx/
│   │   │   ├── Dockerfile
│   │   │   └── nginx.conf
│   │   └── postgres/
│   │       ├── Dockerfile
│   │       └── maintenance/
│   │           └── ... backup scripts ...
│   └── production/
│       └── ... production configs ...
```

---

## 🔁 Celery Setup

### Start Celery Worker

```bash
   docker compose -f local.yml run --rm api celery -A core worker -l info
```
### Start Flower Monitoring

### Flower runs at:
http://localhost:5555

---

## 🔐 Production Deployment

1. Point  domain (e.g., `api.mybank.com`) to the server IP
2. Configure NGINX with SSL via Let's Encrypt
3. Run the stack using production compose:

```bash
   docker compose -f production.yml up -d --build
```
---

## 📥 PostgreSQL Backup Script

Shell script in `scripts/backup_postgres.sh` for scheduled backups.
Add to cron to run daily or weekly.

---

## 🔧 Makefile Shortcuts

```bash
   make build
   make up
   make down
   make migrate
   make createsuperuser
   make test
```
---

## 📡 NGINX Setup

NGINX acts as:
- SSL terminator
- Reverse proxy to Django app
- Static/media files handler
