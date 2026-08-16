from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class ESVError(RuntimeError):
    pass


@dataclass(frozen=True)
class ESVPassage:
    canonical: str
    text: str


@dataclass
class ESVClient:
    api_key: str
    base_url: str = "https://api.esv.org/v3/passage/text/"
    timeout: float = 20.0

    def fetch_many(self, references: list[str]) -> list[ESVPassage]:
        clean = [r.strip() for r in references if r.strip()]
        if not clean:
            return []
        if not self.api_key.strip():
            raise ESVError("ESV API key is not configured.")
        query = ";".join(clean)
        params = urllib.parse.urlencode({
            "q": query,
            "include-passage-references": "true",
            "include-verse-numbers": "true",
            "include-first-verse-numbers": "true",
            "include-footnotes": "false",
            "include-footnote-body": "false",
            "include-headings": "false",
            "include-short-copyright": "true",
            "include-copyright": "false",
            "indent-poetry": "false",
            "line-length": "0",
        })
        req = urllib.request.Request(
            self.base_url + "?" + params,
            headers={"Authorization": f"Token {self.api_key}", "User-Agent": "BibleEngine/0.3"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ESVError("The ESV API key was rejected. Open Settings and save a valid ESV API key.") from exc
            if exc.code == 429:
                raise ESVError("The ESV API rate limit was reached. Try again shortly.") from exc
            raise ESVError(f"ESV API returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ESVError(f"Could not reach the ESV API: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise ESVError("The ESV API returned an unreadable response.") from exc

        passages = payload.get("passages") or []
        if not passages:
            raise ESVError("The ESV API returned no passages for the retrieved canonical references.")
        # The endpoint returns passages in query order for semicolon-separated references.
        out: list[ESVPassage] = []
        for i, text in enumerate(passages):
            fallback = clean[i] if i < len(clean) else str(payload.get("canonical") or "ESV passage")
            out.append(ESVPassage(fallback, str(text).strip()))
        return out

    def fetch(self, reference: str) -> ESVPassage:
        rows = self.fetch_many([reference])
        return rows[0]
