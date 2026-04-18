from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware.error_handler import domain_exception_handler
from app.domain.common.exceptions import DomainException
from app.domain.users.exceptions import InvalidTokenError


def test_domain_exception_handler_returns_http_response():
    app = FastAPI()
    app.add_exception_handler(DomainException, domain_exception_handler)

    @app.get("/verify-email")
    async def verify_email():
        raise InvalidTokenError("Invalid or expired verification token.")

    client = TestClient(app)

    response = client.get("/verify-email")

    assert response.status_code == 401
    assert response.json() == {
        "error": "InvalidTokenError",
        "message": "Invalid or expired verification token.",
        "details": {},
    }
