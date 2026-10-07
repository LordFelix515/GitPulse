import time
from typing import Dict, List, Optional, Tuple
import requests

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str):
        self.token = token.strip()
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AutoGithub-Client/1.0",
        })
        if self.token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}"
            })

    def check_connection(self, max_retries: int = 3, retry_delay: int = 3) -> bool:
        """
        İnternet bağlantısını ve GitHub API erişimini kontrol eder.
        Bilgisayar yeni açıldığında internet henüz bağlanmamış olabileceğinden yeniden dener.
        """
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(f"{GITHUB_API_BASE}/zen", timeout=5)
                if resp.status_code == 200:
                    return True
            except requests.RequestException:
                pass

            if attempt < max_retries:
                time.sleep(retry_delay)

        return False

    def verify_token(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Token'ın geçerliliğini ve kullanıcı adını doğrular.
        Dönüş: (başarılı_mı, kullanıcı_adı, hata_mesajı)
        """
        if not self.token:
            return False, None, "GitHub Token belirtilmedi."

        try:
            resp = self.session.get(f"{GITHUB_API_BASE}/user", timeout=10)
            if resp.status_code == 200:
                user_data = resp.json()
                return True, user_data.get("login"), None
            elif resp.status_code == 401:
                return False, None, "Geçersiz GitHub Token (401 Unauthorized)."
            elif resp.status_code == 403:
                return False, None, "Erişim engellendi veya API istek limiti aşıldı (403 Forbidden)."
            else:
                return False, None, f"GitHub API Hatası: {resp.status_code} - {resp.text}"
        except requests.RequestException as e:
            return False, None, f"Bağlantı hatası: {e}"

    def get_user_repositories(
        self,
        include_forks: bool = True,
        include_archived: bool = False
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Kullanıcının sahip olduğu veya erişebildiği tüm depoları (public & private) getirir.
        Sayfalama (pagination) destekler.
        """
        all_repos = []
        page = 1
        per_page = 100

        while True:
            url = f"{GITHUB_API_BASE}/user/repos"
            params = {
                "per_page": per_page,
                "page": page,
                "affiliation": "owner",  # Sadece kullanıcının kendi açtığı repolar
                "visibility": "all",     # Hem public hem private repolar
                "sort": "updated",
                "direction": "desc",
            }

            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code != 200:
                    return all_repos, f"Depolar alınırken hata oluştu ({resp.status_code}): {resp.text}"

                data = resp.json()
                if not data:
                    break

                for r in data:
                    is_fork = r.get("fork", False)
                    is_archived = r.get("archived", False)

                    if not include_forks and is_fork:
                        continue
                    if not include_archived and is_archived:
                        continue

                    all_repos.append({
                        "name": r.get("name"),
                        "full_name": r.get("full_name"),
                        "clone_url": r.get("clone_url"),
                        "ssh_url": r.get("ssh_url"),
                        "private": r.get("private", False),
                        "default_branch": r.get("default_branch", "main"),
                        "updated_at": r.get("updated_at", ""),
                        "description": r.get("description") or "",
                        "fork": is_fork,
                        "archived": is_archived
                    })

                if len(data) < per_page:
                    break

                page += 1

            except requests.RequestException as e:
                return all_repos, f"Ağ bağlantısı koptu: {e}"

        return all_repos, None
