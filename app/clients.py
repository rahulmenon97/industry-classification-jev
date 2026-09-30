import httpx

from app.config import Settings


class ProviderError(Exception):
    pass


class ProviderClients:
    def __init__(self, settings: Settings):
        self.settings = settings

    def ready(self):
        return all(
            v and not v.startswith("paste_")
            for v in (
                self.settings.exa_api_key.get_secret_value(),
                self.settings.typesafe_api_key.get_secret_value(),
            )
        )

    def post(self, provider, payload):
        if provider == "exa":
            url = "https://api.exa.ai/search"
            headers = {"x-api-key": self.settings.exa_api_key.get_secret_value()}
        else:
            url = "https://api.typesafe.ai/v1/systemone"
            headers = {
                "Authorization": "Bearer " + self.settings.typesafe_api_key.get_secret_value()
            }
        try:
            with httpx.Client(
                timeout=httpx.Timeout(45, connect=10), follow_redirects=False
            ) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError()
                return result
        except httpx.HTTPStatusError as e:
            raise ProviderError(
                "%s returned HTTP %s; check account access, quota, or request format."
                % (provider, e.response.status_code)
            ) from None
        except (httpx.HTTPError, ValueError):
            raise ProviderError(
                "%s connection or response failed. No automatic retries." % provider
            ) from None

    def redact(self, value):
        import json

        text = json.dumps(value)
        for key in (self.settings.exa_api_key, self.settings.typesafe_api_key):
            if key.get_secret_value():
                text = text.replace(key.get_secret_value(), "[REDACTED]")
        return json.loads(text)
