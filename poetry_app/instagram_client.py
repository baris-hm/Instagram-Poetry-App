"""Small Instagram Platform API client for image and carousel publishing."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

JsonObject = dict[str, Any]
Transport = Callable[[str, str, dict[str, str], bytes | None, float], JsonObject]


class InstagramAPIError(RuntimeError):
    """A sanitized Instagram API failure suitable for application logs/UI."""


@dataclass(frozen=True, slots=True)
class InstagramAccount:
    user_id: str
    username: str


@dataclass(frozen=True, slots=True)
class PublishedPost:
    media_id: str
    permalink: str = ""


def urllib_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> JsonObject:
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
            details = payload.get("error", {})
            message = details.get("message") or "Instagram isteği reddedildi."
            code = details.get("code")
            subcode = details.get("error_subcode")
            suffix = ", ".join(
                part for part in (f"kod {code}" if code else "", f"alt kod {subcode}" if subcode else "") if part
            )
            raise InstagramAPIError(f"{message}{f' ({suffix})' if suffix else ''}") from error
        except json.JSONDecodeError:
            raise InstagramAPIError(f"Instagram HTTP {error.code} hatası döndürdü.") from error
    except json.JSONDecodeError as error:
        raise InstagramAPIError("Instagram API geçersiz bir yanıt döndürdü.") from error
    except (URLError, TimeoutError) as error:
        raise InstagramAPIError("Instagram API bağlantısı kurulamadı.") from error

    if not isinstance(payload, dict):
        raise InstagramAPIError("Instagram API beklenmeyen bir yanıt döndürdü.")
    return payload


class InstagramClient:
    def __init__(
        self,
        access_token: str,
        *,
        api_version: str = "v26.0",
        base_url: str = "https://graph.instagram.com",
        user_id: str = "",
        timeout: float = 30,
        status_timeout: float = 60,
        poll_interval: float = 1,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required")
        self._access_token = access_token
        self._api_version = api_version.strip("/")
        self._base_url = base_url.rstrip("/")
        self._configured_user_id = user_id
        self._timeout = timeout
        self._status_timeout = status_timeout
        self._poll_interval = poll_interval
        self._transport = transport
        self._sleep = sleep

    def get_account(self) -> InstagramAccount:
        payload = self._request("GET", "me", query={"fields": "user_id,username"})
        user_id = str(payload.get("user_id") or payload.get("id") or "")
        if not user_id:
            raise InstagramAPIError("Instagram hesap kimliği alınamadı.")
        return InstagramAccount(user_id=user_id, username=str(payload.get("username") or ""))

    def publish_images(self, image_urls: list[str], caption: str = "") -> PublishedPost:
        if not 1 <= len(image_urls) <= 10:
            raise ValueError("Instagram gönderisi 1 ile 10 görsel içermelidir.")
        if any(not url.startswith("https://") for url in image_urls):
            raise ValueError("Instagram görsellerinin tümü HTTPS üzerinden sunulmalıdır.")

        user_id = self._configured_user_id or self.get_account().user_id
        if len(image_urls) == 1:
            try:
                container_id = self._create_image_container(
                    user_id,
                    image_urls[0],
                    caption=caption,
                    carousel_item=False,
                )
            except InstagramAPIError as error:
                raise InstagramAPIError(f"Tek görsel kapsayıcısı oluşturulurken: {error}") from error
            try:
                self._wait_until_ready(container_id)
            except InstagramAPIError as error:
                raise InstagramAPIError(f"Tek görsel işlenirken: {error}") from error
            try:
                return self._publish_container(user_id, container_id)
            except InstagramAPIError as error:
                raise InstagramAPIError(f"Tek görsel yayınlanırken: {error}") from error

        child_ids: list[str] = []
        for index, image_url in enumerate(image_urls, start=1):
            try:
                child_id = self._create_image_container(user_id, image_url, carousel_item=True)
            except InstagramAPIError as error:
                raise InstagramAPIError(
                    f"Karuselin {index}. karesi için kapsayıcı oluşturulurken: {error}"
                ) from error
            child_ids.append(child_id)

        for index, child_id in enumerate(child_ids, start=1):
            try:
                self._wait_until_ready(child_id)
            except InstagramAPIError as error:
                raise InstagramAPIError(f"Karuselin {index}. karesi işlenirken: {error}") from error

        try:
            carousel = self._request(
                "POST",
                f"{user_id}/media",
                payload={
                    "caption": caption,
                    "children": ",".join(child_ids),
                    "media_type": "CAROUSEL",
                },
            )
        except InstagramAPIError as error:
            raise InstagramAPIError(f"Karusel kapsayıcısı oluşturulurken: {error}") from error
        carousel_id = self._require_id(carousel, "Karusel kapsayıcısı oluşturulamadı.")
        try:
            self._wait_until_ready(carousel_id)
        except InstagramAPIError as error:
            raise InstagramAPIError(f"Karusel işlenirken: {error}") from error
        try:
            return self._publish_container(user_id, carousel_id)
        except InstagramAPIError as error:
            raise InstagramAPIError(f"Karusel yayınlanırken: {error}") from error

    def _create_image_container(
        self,
        user_id: str,
        image_url: str,
        *,
        caption: str = "",
        carousel_item: bool,
    ) -> str:
        payload: JsonObject = {"image_url": image_url}
        if caption:
            payload["caption"] = caption
        if carousel_item:
            payload["is_carousel_item"] = True
        response = self._request("POST", f"{user_id}/media", payload=payload)
        return self._require_id(response, "Görsel kapsayıcısı oluşturulamadı.")

    def _wait_until_ready(self, container_id: str) -> None:
        deadline = time.monotonic() + self._status_timeout
        while time.monotonic() < deadline:
            response = self._request(
                "GET",
                container_id,
                query={"fields": "status_code,status"},
            )
            status = str(response.get("status_code") or "").upper()
            if status in {"FINISHED", "PUBLISHED"}:
                return
            if status in {"ERROR", "EXPIRED"}:
                detail = str(response.get("status") or status)
                raise InstagramAPIError(f"Instagram görseli işleyemedi: {detail}")
            self._sleep(self._poll_interval)
        raise InstagramAPIError("Instagram görsel işleme süresi aşıldı.")

    def _publish_container(self, user_id: str, container_id: str) -> PublishedPost:
        response = self._request(
            "POST",
            f"{user_id}/media_publish",
            payload={"creation_id": container_id},
        )
        media_id = self._require_id(response, "Instagram gönderiyi yayınlamadı.")
        permalink = ""
        try:
            media = self._request("GET", media_id, query={"fields": "permalink"})
            permalink = str(media.get("permalink") or "")
        except InstagramAPIError:
            pass
        return PublishedPost(media_id=media_id, permalink=permalink)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: JsonObject | None = None,
        query: dict[str, str] | None = None,
    ) -> JsonObject:
        url = f"{self._base_url}/{self._api_version}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{urlencode(query)}"
        body = None
        if payload is not None:
            form_payload = {
                key: json.dumps(value) if isinstance(value, bool) else str(value)
                for key, value in payload.items()
            }
            body = urlencode(form_payload).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": "Siirden-Karelere/0.2",
        }
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return self._transport(method, url, headers, body, self._timeout)

    @staticmethod
    def _require_id(response: JsonObject, message: str) -> str:
        identifier = str(response.get("id") or "")
        if not identifier:
            raise InstagramAPIError(message)
        return identifier
