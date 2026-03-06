"""Configuration constants."""

# API
API_V1_PREFIX = "/api/v1"

# Security
JWT_ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_VERIFICATION = "verification"
TOKEN_TYPE_PASSWORD_RESET = "password_reset"

# File Upload
ALLOWED_DOCUMENT_EXTENSIONS = {
    '.pdf', '.docx', '.doc', '.pptx', '.ppt',
    '.xlsx', '.xls', '.md', '.txt', '.html', '.htm'
}

DOCUMENT_MIME_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'text/markdown',
    'text/plain',
    'text/html',
}

# Database
DB_ECHO = False
DB_FUTURE = True

# Email
EMAIL_TIMEOUT = 10

# RAG / Document Processing
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_TOP_K = 5

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1
