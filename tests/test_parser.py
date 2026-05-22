from app.parser import parse_record_payload


def test_parse_record_payload_from_key_value_body():
    record = parse_record_payload(
        {
            "id": "payload-1",
            "body": {
                "content": """
                Title: Manual approval blocked
                Source: Operations
                Category: Workflow
                Status: Review
                Owner: Team Alpha
                Resource: Queue A
                Summary: Waiting on approval
                Details: The generic parser maps key-value text into records.
                """
            },
        }
    )

    assert record.external_id == "payload-1"
    assert record.title == "Manual approval blocked"
    assert record.source == "Operations"
    assert record.category == "Workflow"
    assert record.status == "Review"
    assert record.owner == "Team Alpha"
    assert record.resource == "Queue A"


def test_parse_record_payload_uses_mapping_values_first():
    record = parse_record_payload(
        {
            "id": "payload-2",
            "title": "Mapped title",
            "source": "Mapped source",
            "category": "Mapped category",
            "status": "Mapped status",
            "body": "Title: Body title\nSource: Body source",
        }
    )

    assert record.title == "Mapped title"
    assert record.source == "Mapped source"
    assert record.category == "Mapped category"
    assert record.status == "Mapped status"
