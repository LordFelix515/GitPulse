from pathlib import Path
from typing import List, Set

IGNORE_FILENAMES = ["dwnignore.txt", ".dwnignore", "dwnignore"]


def get_base_dir() -> Path:
    return Path(__file__).resolve().parent


def get_ignore_file_path() -> Path:
    """Mevcut bir ignore dosyası varsa onu döndürür, yoksa varsayılan dwnignore.txt dosyasını döndürür."""
    base = get_base_dir()
    for name in IGNORE_FILENAMES:
        p = base / name
        if p.exists():
            return p
    return base / "dwnignore.txt"


def load_ignored_repos() -> Set[str]:
    """
    Ignore dosyasındaki repo adlarını küçük harfe çevrilmiş ve temizlenmiş bir küme olarak döndürür.
    Satır başı '#' olan yorumlar ve boş satırlar atlanır.
    """
    path = get_ignore_file_path()
    ignored = set()
    if not path.exists():
        return ignored

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                cleaned = line.strip()
                if not cleaned or cleaned.startswith("#"):
                    continue
                # Eğer kullanıcı 'owner/repo' yazdıysa veya sadece 'repo' yazdıysa
                ignored.add(cleaned.lower())
                if "/" in cleaned:
                    ignored.add(cleaned.split("/")[-1].lower())
    except Exception as e:
        print(f"[UYARI] Ignore dosyası okunamadı ({e}).")

    return ignored


def is_repo_ignored(repo_name: str, full_name: str = "", ignored_set: Set[str] = None) -> bool:
    """Belirli bir reponun ignore listesinde olup olmadığını kontrol eder."""
    if ignored_set is None:
        ignored_set = load_ignored_repos()

    name_lower = repo_name.strip().lower()
    full_lower = full_name.strip().lower() if full_name else ""

    return name_lower in ignored_set or (bool(full_lower) and full_lower in ignored_set)


def add_to_ignore(repo_names: List[str]) -> List[str]:
    """
    Verilen repo adlarını dwnignore.txt dosyasına ekler.
    Eklenenleri liste olarak döndürür.
    """
    path = get_ignore_file_path()
    current = load_ignored_repos()
    added = []

    to_write = []
    for name in repo_names:
        clean = name.strip()
        if clean and clean.lower() not in current:
            to_write.append(clean)
            added.append(clean)
            current.add(clean.lower())

    if to_write:
        # Dosya yoksa başlık ekle
        needs_header = not path.exists() or path.stat().st_size == 0
        with open(path, "a", encoding="utf-8") as f:
            if needs_header:
                f.write("# AutoGithub dwnignore Listesi\n")
                f.write("# Bu listedeki projeler otomatik indirilmez ve sorulmaz.\n\n")
            for item in to_write:
                f.write(f"{item}\n")

    return added


def remove_from_ignore(repo_name: str) -> bool:
    """Belirtilen depoyu ignore dosyasından siler."""
    path = get_ignore_file_path()
    if not path.exists():
        return False

    name_lower = repo_name.strip().lower()
    lines = []
    found = False

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                cleaned = line.strip()
                if cleaned and not cleaned.startswith("#") and cleaned.lower() == name_lower:
                    found = True
                    continue
                lines.append(line)

        if found:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
    except Exception as e:
        print(f"[HATA] Ignore dosyasından silinemedi: {e}")

    return False


def get_all_ignored() -> List[str]:
    """Tüm ignore edilen girdileri liste olarak döndürür."""
    path = get_ignore_file_path()
    if not path.exists():
        return []

    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                items.append(cleaned)
    return items
