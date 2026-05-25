import requests
from requests.auth import HTTPBasicAuth


class DHIS2Client:
    def __init__(self, base_url: str, username: str, password: str):
        url = base_url.rstrip("/")
        if not url.endswith("/api"):
            url += "/api"
        self.base_url = url
        self._auth = HTTPBasicAuth(username, password)
        self._session = requests.Session()
        self._session.auth = self._auth
        self._session.headers.update({"Content-Type": "application/json"})

    def get(self, path: str, params: dict = None, timeout: int = 60) -> dict:
        """
        GET request. params values may be lists — each list item is sent as a
        separate query param (requests behaviour), which is correct for DHIS2's
        multiple filter= syntax:
            params={"filter": ["name:ilike:mal", "domainType:eq:AGGREGATE"]}
            → ?filter=name:ilike:mal&filter=domainType:eq:AGGREGATE
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self._session.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, payload: dict, timeout: int = 30) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self._session.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def put(self, path: str, payload: dict, timeout: int = 30) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self._session.put(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def test_connection(self) -> dict:
        """Returns the authenticated user's basic info."""
        return self.get("me.json", params={"fields": "id,name,username"})
