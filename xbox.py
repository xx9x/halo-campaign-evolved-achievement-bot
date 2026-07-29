from typing import Any

import requests


class XboxAPIError(Exception):
    """Raised when an Xbox achievement request fails."""


class HaloAchievementClient:
    BASE_URL = "https://achievements.xboxlive.com"

    def __init__(self, title_id: str) -> None:
        if not title_id:
            raise ValueError(
                "HALO_CAMPAIGN_EVOLVED_TITLE_ID is missing."
            )

        self.title_id = title_id

    @staticmethod
    def get_gamerscore(achievement: dict[str, Any]) -> int:
        for reward in achievement.get("rewards", []):
            if reward.get("type") == "Gamerscore":
                try:
                    return int(reward.get("value", 0))
                except (TypeError, ValueError):
                    return 0

        return 0

    @staticmethod
    def get_icon_url(achievement: dict[str, Any]) -> str:
        for asset in achievement.get("mediaAssets", []):
            if asset.get("type") == "Icon":
                return str(asset.get("url", ""))

        return ""

    @staticmethod
    def is_unlocked(achievement: dict[str, Any]) -> bool:
        return achievement.get("progressState") == "Achieved"

    def get_all_achievements(
        self,
        xbox_data: dict[str, str],
    ) -> list[dict[str, Any]]:
        achievements: list[dict[str, Any]] = []
        continuation_token: str | None = None

        while True:
            page = self._get_achievement_page(
                xbox_data=xbox_data,
                continuation_token=continuation_token,
            )

            achievements.extend(page.get("achievements", []))

            paging_info = page.get("pagingInfo", {})
            continuation_token = paging_info.get("continuationToken")

            if not continuation_token:
                break

        return achievements

    def _get_achievement_page(
        self,
        xbox_data: dict[str, str],
        continuation_token: str | None,
    ) -> dict[str, Any]:
        xuid = xbox_data["xuid"]

        url = f"{self.BASE_URL}/users/xuid({xuid})/achievements"

        headers = {
            "Authorization": (
                f"XBL3.0 x={xbox_data['user_hash']};"
                f"{xbox_data['token']}"
            ),
            "x-xbl-contract-version": "2",
            "Accept": "application/json",
            "Accept-Language": "en-US",
        }

        params = {
            "titleId": self.title_id,
            "maxItems": 100,
            "orderBy": "Title",
        }

        if continuation_token:
            params["continuationToken"] = continuation_token

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )

        if not response.ok:
            raise XboxAPIError(
                "Xbox achievement request failed "
                f"with status {response.status_code}: "
                f"{response.text[:300]}"
            )

        return response.json()

    def get_summary(
        self,
        achievements: list[dict[str, Any]],
    ) -> dict[str, int | float]:
        unlocked = [
            achievement
            for achievement in achievements
            if self.is_unlocked(achievement)
        ]

        total_gamerscore = sum(
            self.get_gamerscore(achievement)
            for achievement in achievements
        )

        unlocked_gamerscore = sum(
            self.get_gamerscore(achievement)
            for achievement in unlocked
        )

        completion = (
            len(unlocked) / len(achievements) * 100
            if achievements
            else 0
        )

        return {
            "unlocked": len(unlocked),
            "total": len(achievements),
            "unlocked_gamerscore": unlocked_gamerscore,
            "total_gamerscore": total_gamerscore,
            "completion": completion,
        }

    def search(
        self,
        achievements: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        normalized_query = query.casefold().strip()

        return [
            achievement
            for achievement in achievements
            if normalized_query
            in str(achievement.get("name", "")).casefold()
        ]