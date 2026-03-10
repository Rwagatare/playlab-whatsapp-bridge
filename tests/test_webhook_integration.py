"""Integration tests for webhook endpoints (Meta + Twilio signature verification)."""

import base64
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    """Set MOCK_MODE so settings don't require real credentials."""
    monkeypatch.setenv("MOCK_MODE", "1")


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


# --- Meta webhook verification (GET /webhook) ---


class TestMetaVerification:
    def test_valid_token(self, client, monkeypatch):
        monkeypatch.setenv("META_VERIFY_TOKEN", "test-verify-token")
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token",
                "hub.challenge": "challenge123",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "challenge123"

    def test_invalid_token(self, client, monkeypatch):
        monkeypatch.setenv("META_VERIFY_TOKEN", "correct-token")
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "challenge123",
            },
        )
        assert resp.status_code == 403

    def test_missing_params(self, client):
        resp = client.get("/webhook")
        assert resp.status_code == 400


# --- Meta webhook POST (signature verification) ---


class TestMetaWebhookPost:
    def _sign_meta(self, body: bytes, secret: str) -> str:
        return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_valid_signature(self, client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PROVIDER", "meta")
        secret = "test-app-secret"
        monkeypatch.setenv("META_APP_SECRET", secret)

        # Minimal valid Meta webhook payload (status update, no message)
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"id": "123", "changes": [{"value": {"statuses": []}, "field": "messages"}]}],
        }
        body = json.dumps(payload).encode()
        sig = self._sign_meta(body, secret)

        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
        )
        assert resp.status_code == 200

    def test_invalid_signature_rejected(self, client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PROVIDER", "meta")
        monkeypatch.setenv("META_APP_SECRET", "real-secret")

        body = b'{"object": "whatsapp_business_account"}'
        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=wrong",
            },
        )
        assert resp.status_code == 403

    def test_missing_signature_rejected(self, client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PROVIDER", "meta")
        monkeypatch.setenv("META_APP_SECRET", "real-secret")

        resp = client.post(
            "/webhook",
            content=b'{"object": "test"}',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 403


# --- Twilio webhook POST (signature verification) ---


class TestTwilioWebhookPost:
    def _sign_twilio(self, url: str, params: dict[str, str], auth_token: str) -> str:
        data_str = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
        return base64.b64encode(
            hmac.new(auth_token.encode(), data_str.encode("utf-8"), hashlib.sha1).digest()
        ).decode()

    def test_valid_signature(self, client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
        token = "test-auth-token"
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", token)

        params = {"From": "whatsapp:+1234567890", "Body": "hello"}
        # TestClient uses http://testserver by default
        url = "http://testserver/webhook"
        sig = self._sign_twilio(url, params, token)

        resp = client.post(
            "/webhook",
            data=params,
            headers={"X-Twilio-Signature": sig},
        )
        assert resp.status_code == 200

    def test_invalid_signature_rejected(self, client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "real-token")

        resp = client.post(
            "/webhook",
            data={"From": "whatsapp:+1234567890", "Body": "hello"},
            headers={"X-Twilio-Signature": "bad-signature"},
        )
        assert resp.status_code == 403

    def test_missing_signature_rejected(self, client, monkeypatch):
        monkeypatch.setenv("WHATSAPP_PROVIDER", "twilio")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "real-token")

        resp = client.post(
            "/webhook",
            data={"From": "whatsapp:+1234567890", "Body": "hello"},
        )
        assert resp.status_code == 403
