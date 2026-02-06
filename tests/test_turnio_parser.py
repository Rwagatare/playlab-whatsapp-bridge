from app.parsers.turnio import parse_inbound


def test_parse_inbound_text_message() -> None:
    payload = {
        "messages": [
            {
                "from": "12345",
                "text": {"body": "hello"},
            }
        ],
        "contacts": [{"wa_id": "12345"}],
    }

    inbound = parse_inbound(payload)

    assert inbound is not None
    assert inbound.sender_id == "12345"
    assert inbound.text == "hello"
    assert inbound.image_url is None
