import base64
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple


class GitManager:
    def __init__(self, token: str = ""):
        self.token = token.strip()
        self._auth_args = []
        if self.token:
            # GitHub Git HTTP Basic Auth base64(x-access-token:<token>) formatını gerektirir.
            # Düz token veya 'basic <raw_token>' gönderilmesi GitHub tarafından HTTP 400 ile reddedilir.
            b64_creds = base64.b64encode(f"x-access-token:{self.token}".encode("utf-8")).decode("ascii")
            self._auth_args = ["-c", f"http.extraHeader=AUTHORIZATION: basic {b64_creds}"]

    def _run_git(self, args: list, cwd: Path, timeout: int = 45) -> Tuple[int, str, str]:
        """Git komutunu çalıştırır ve (exit_code, stdout, stderr) döndürür."""
        try:
            env = os.environ.copy()
            # Windows UTF-8 desteği
            env["PYTHONIOENCODING"] = "utf-8"
            
            result = subprocess.run(
                ["git"] + args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "İşlem zaman aşımına uğradı."
        except FileNotFoundError:
            return -2, "", "Git komutu bulunamadı. Lütfen Git'in kurulu ve PATH'te olduğundan emin olun."
        except Exception as e:
            return -3, "", str(e)

    def is_git_repo(self, repo_path: Path) -> bool:
        """Belirtilen klasörün geçerli bir git deposu olup olmadığını kontrol eder."""
        if not repo_path.is_dir():
            return False
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            return False
        code, out, _ = self._run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_path)
        return code == 0 and out == "true"

    def has_uncommitted_changes(self, repo_path: Path) -> bool:
        """Kaydedilmemiş (staged / unstaged) değişiklik olup olmadığını kontrol eder."""
        code, out, _ = self._run_git(["status", "--porcelain"], cwd=repo_path)
        return code == 0 and len(out) > 0

    def get_current_branch(self, repo_path: Path) -> str:
        """Mevcut aktif branch adını döndürür."""
        code, out, _ = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
        return out if code == 0 else "main"

    def fetch_remote(self, repo_path: Path) -> Tuple[bool, str]:
        """Uzak depodan (origin) son commit bilgilerini çeker."""
        args = list(self._auth_args) + ["fetch", "origin", "--quiet"]
        code, _, err = self._run_git(args, cwd=repo_path, timeout=30)
        if code != 0:
            return False, err or "Fetch başarısız oldu."
        return True, ""

    def check_sync_status(self, repo_path: Path) -> Dict:
        """
        Deponun yerel ve uzak durumunu analiz eder.
        Dönüş:
          - is_git: bool
          - current_branch: str
          - has_changes: bool (yerelde kaydedilmemiş değişiklikler)
          - behind_count: int (uzak depoda olup yerelde olmayan commit sayısı)
          - ahead_count: int (yerelde olup uzakta olmayan commit sayısı)
          - status: 'UP_TO_DATE' | 'BEHIND' | 'AHEAD' | 'DIVERGED' | 'NO_UPSTREAM' | 'ERROR'
          - message: str
        """
        if not self.is_git_repo(repo_path):
            return {"is_git": False, "status": "NOT_GIT", "message": "Git deposu değil"}

        branch = self.get_current_branch(repo_path)
        has_dirty = self.has_uncommitted_changes(repo_path)

        # Uzak depoyu güncelle (fetch)
        fetch_ok, fetch_err = self.fetch_remote(repo_path)
        if not fetch_ok:
            return {
                "is_git": True,
                "current_branch": branch,
                "has_changes": has_dirty,
                "status": "FETCH_FAILED",
                "message": f"Uzak depoya erişilemedi: {fetch_err}"
            }

        # Upstream branch kontrolü
        code, upstream, _ = self._run_git(["rev-parse", "--abbrev-ref", "@{u}"], cwd=repo_path)
        if code != 0 or not upstream:
            # Upstream yoksa origin/<branch> dene
            upstream = f"origin/{branch}"

        # Behind count (HEAD..upstream)
        code_b, out_b, _ = self._run_git(["rev-list", "--count", f"HEAD..{upstream}"], cwd=repo_path)
        behind = int(out_b) if code_b == 0 and out_b.isdigit() else 0

        # Ahead count (upstream..HEAD)
        code_a, out_a, _ = self._run_git(["rev-list", "--count", f"{upstream}..HEAD"], cwd=repo_path)
        ahead = int(out_a) if code_a == 0 and out_a.isdigit() else 0

        if code_b != 0:
            return {
                "is_git": True,
                "current_branch": branch,
                "has_changes": has_dirty,
                "status": "NO_UPSTREAM",
                "message": "Uzak dal (upstream) bulunamadı."
            }

        status = "UP_TO_DATE"
        if behind > 0 and ahead > 0:
            status = "DIVERGED"
        elif behind > 0:
            status = "BEHIND"
        elif ahead > 0:
            status = "AHEAD"

        return {
            "is_git": True,
            "current_branch": branch,
            "has_changes": has_dirty,
            "behind_count": behind,
            "ahead_count": ahead,
            "status": status,
            "message": ""
        }

    def pull_repo(self, repo_path: Path) -> Tuple[bool, str, list]:
        """
        Depoyu günceller (git pull).
        Güncelleme öncesinde .gitignore ve proje içerisindeki .env dosyalarını
        otomatik olarak yedekler ve işlem bitince projeye geri yükler.
        """
        from env_guard import backup_env_files, restore_env_files

        # 1. Güncelleme öncesi .env dosyalarını yedekle
        env_backups = backup_env_files(repo_path)

        args = list(self._auth_args) + ["pull", "--ff-only"]
        code, out, err = self._run_git(args, cwd=repo_path, timeout=60)
        pull_ok = False
        pull_msg = ""

        if code == 0:
            pull_ok = True
            pull_msg = out or "Başarıyla güncellendi."
        else:
            # ff-only başarısız olduysa normal pull dene
            args2 = list(self._auth_args) + ["pull"]
            code2, out2, err2 = self._run_git(args2, cwd=repo_path, timeout=60)
            if code2 == 0:
                pull_ok = True
                pull_msg = out2 or "Başarıyla güncellendi."
            else:
                pull_ok = False
                pull_msg = err2 or err or "Pull işlemi başarısız."

        # 2. Güncelleme sonrası .env dosyalarını geri yükle ve koru
        restored = restore_env_files(repo_path, env_backups)

        return pull_ok, pull_msg, restored

    def clone_repo(self, clone_url: str, target_dir: Path) -> Tuple[bool, str]:
        """
        Depoyu hedeflenen klasöre klonlar.
        Auth header kullanarak token'ın config ve URL içinde açık kalmasını önler.
        """
        target_dir.parent.mkdir(parents=True, exist_ok=True)

        cmd = ["git"] + list(self._auth_args) + ["clone", clone_url, str(target_dir)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )

            if result.returncode == 0:
                return True, "Klonlama başarılı."
            else:
                # Hata mesajından token'ı temizle
                safe_err = result.stderr.replace(self.token, "***") if self.token else result.stderr
                return False, safe_err.strip()

        except subprocess.TimeoutExpired:
            return False, "Klonlama işlemi zaman aşımına uğradı."
        except Exception as e:
            return False, str(e)

