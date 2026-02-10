# Gunicorn configuration for OTT RADAR production deployment
# Usage: gunicorn -c gunicorn_config.py app:app

import multiprocessing
import os
from dotenv import load_dotenv

load_dotenv()

# Server socket
bind = "0.0.0.0:5001"
family = "socket.AF_INET"

# Worker processes - use (2 x CPU_count + 1)
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "ott-radar"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190

# SSL (optional, use with reverse proxy like Nginx)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Application
forwarded_allow_ips = "*"
secure_scheme_header = "X-FORWARDED-PROTO"

# Environment
raw_env = [
    "FLASK_ENV=production",
]

print("Gunicorn configuration loaded")
print(f"Workers: {workers}")
print(f"Bind: {bind}")
