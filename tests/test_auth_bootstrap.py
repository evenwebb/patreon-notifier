import json
from unittest.mock import MagicMock

import patreon_notifier.auth as auth


def test_extract_csrf_reads_session_csrf_signature() -> None:
    html = (
        '<script id="__NEXT_DATA__" type="application/json" nonce="abc">'
        '{"props":{"pageProps":{"bootstrapEnvelope":{"session":'
        '{"csrf_signature":"sig-from-session","user_id":"2715867"}}}}}'
        "</script>"
    )
    session = MagicMock()
    session.get.return_value.text = html
    assert auth.extract_csrf_token(session) == "sig-from-session"


def test_validate_authentication_reads_user_id_from_session() -> None:
    next_data = {
        "props": {
            "pageProps": {
                "bootstrapEnvelope": {
                    "session": {"user_id": "2715867"},
                    "commonBootstrap": {
                        "currentUser": {
                            "data": {
                                "attributes": {
                                    "full_name": "Test User",
                                    "email": "u@example.com",
                                },
                                "relationships": {
                                    "pledges": {"data": [{"id": "1"}, {"id": "2"}]}
                                },
                            }
                        }
                    },
                }
            }
        }
    }
    html = (
        '<script id="__NEXT_DATA__" type="application/json" nonce="abc">'
        f"{json.dumps(next_data)}"
        "</script>"
    )
    session = MagicMock()
    session.get.return_value.text = html
    info = auth.validate_authentication(session, "sig")
    assert info["user_id"] == "2715867"
    assert info["name"] == "Test User"
    assert info["email"] == "u@example.com"
    assert info["pledge_count"] == 2
