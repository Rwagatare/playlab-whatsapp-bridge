from app.parsers.twilio import parse_inbound


def test_parse_inbound_twilio_message() -> None:
    form_data = {"From": "whatsapp:+123", "Body": "hello"}

    inbound = parse_inbound(form_data)

    assert inbound is not None
    assert inbound.sender_id == "whatsapp:+123"
    assert inbound.text == "hello"
    assert inbound.image_url is None
