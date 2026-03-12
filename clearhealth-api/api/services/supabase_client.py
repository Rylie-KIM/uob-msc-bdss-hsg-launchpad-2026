import os
from supabase import create_client, Client

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SECRET_KEY"]
        _client = create_client(url, key)
    return _client


def verify_user_token(token: str) -> str:
    """Verify a Supabase JWT and return the user_id (sub claim)."""
    client = get_client()
    response = client.auth.get_user(token)
    if response.user is None:
        raise ValueError("Invalid or expired token")
    return response.user.id
