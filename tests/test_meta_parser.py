from app.parsers.meta import parse_inbound


def test_parse_text_message() -> None:
    """Standard inbound text message from Meta webhook."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "123456",
                            },
                            "contacts": [
                                {"profile": {"name": "Test User"}, "wa_id": "27123456789"}
                            ],
                            "messages": [
                                {
                                    "from": "27123456789",
                                    "id": "wamid.test123",
                                    "timestamp": "1677721200",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    inbound = parse_inbound(payload)

    assert inbound is not None
    assert inbound.sender_id == "27123456789"
    assert inbound.text == "Hello"
    assert inbound.image_url is None


def test_parse_status_update_returns_none() -> None:
    """Status updates (delivered/read) should be skipped."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "123456",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.test123",
                                    "status": "delivered",
                                    "timestamp": "1677721300",
                                    "recipient_id": "27123456789",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    inbound = parse_inbound(payload)
    assert inbound is None


def test_parse_missing_sender_returns_none() -> None:
    """If sender cannot be extracted, return None."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.test",
                                    "type": "text",
                                    "text": {"body": "hello"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }

    inbound = parse_inbound(payload)
    assert inbound is None


def test_parse_empty_payload_returns_none() -> None:
    inbound = parse_inbound({})
    assert inbound is None


def test_parse_sender_fallback_to_contacts() -> None:
    """If message.from is missing, fall back to contacts[0].wa_id."""
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "27999999999"}],
                            "messages": [
                                {
                                    "type": "text",
                                    "text": {"body": "fallback test"},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }

    inbound = parse_inbound(payload)

    assert inbound is not None
    assert inbound.sender_id == "27999999999"
    assert inbound.text == "fallback test"
