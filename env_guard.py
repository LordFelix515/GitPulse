import os
import shutil
from pathlib import Path
from typing import Dict, List, Set

# Taranmayacak büyük/sistem klasörleri
EXCLUDED_DIRS = {".git", "node_modules", "venv", ".venv", "env", "__pycache__", ".idea", ".vscode", "dist", "build"}


def get_ignored_env_patterns_from_gitignore(repo_path: Path) -> Set[str]:
    """
    Projedeki .gitignore dosyasını okuyarak env ile ilgili desenleri toplar.
    """
    gitignore_path = repo_path / ".gitignore"
    patterns = set()
    if not gitignore_path.exists():
        return patterns

    try:
        with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # env içeren veya local konfigürasyon belirten kurallar
                if "env" in line.lower() or "local" in line.lower() or "secret" in line.lower():
                    clean_pattern = line.lstrip("/")
                    patterns.add(clean_pattern)
    except Exception:
        pass

    return patterns


def find_env_files(repo_path: Path) -> List[Path]:
    """
    Proje içerisindeki tüm .env ve benzeri ortam yapılandırma dosyalarını bulur.
    Örn: .env, .env.local, .env.development, .env.production, backend/.env vb.
    """
    env_files = []
    if not repo_path.is_dir():
        return env_files

    for root, dirs, files in os.walk(repo_path):
        # Taranmaması gereken klasörleri filtrele
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        for file in files:
            name_lower = file.lower()
            # .env veya .env.* veya *.env veya env.local dosyaları
            if (
                name_lower == ".env"
                or name_lower.startswith(".env.")
                or name_lower.endswith(".env")
                or name_lower.endswith(".env.local")
            ):
                full_path = Path(root) / file
                env_files.append(full_path)

    return env_files


def backup_env_files(repo_path: Path) -> Dict[str, bytes]:
    """
    Güncelleme yapılmadan önce projedeki tüm .env dosyalarını belleğe yedekler.
    Dönüş: {göreli_yol: dosya_baytları}
    """
    backups: Dict[str, bytes] = {}
    found_files = find_env_files(repo_path)

    for file_path in found_files:
        try:
            rel_path = str(file_path.relative_to(repo_path))
            with open(file_path, "rb") as f:
                backups[rel_path] = f.read()
        except Exception as e:
            print(f"[UYARI] {file_path.name} yedeklenirken hata oluştu: {e}")

    return backups


def restore_env_files(repo_path: Path, backups: Dict[str, bytes]) -> List[str]:
    """
    Güncelleme bittikten sonra yedeklenen .env dosyalarını projeye geri yazar.
    Geri yüklenen dosyaların listesini döndürür.
    """
    restored = []
    if not backups:
        return restored

    for rel_path, data in backups.items():
        try:
            target_path = repo_path / rel_path
            # Üst klasör yoksa oluştur
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with open(target_path, "wb") as f:
                f.write(data)
            restored.append(rel_path)
        except Exception as e:
            print(f"[HATA] {rel_path} geri yüklenemedi: {e}")

    return restored
