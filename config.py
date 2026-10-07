import json
import os
from pathlib import Path

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "github_token": "",
    "local_repos_dir": "",
    "auto_pull_existing": True,
    "include_forks": True,
    "include_archived": False,
    "startup_countdown_seconds": 10
}


def get_base_dir() -> Path:
    """Uygulamanın çalıştığı ana dizini döndürür."""
    return Path(__file__).resolve().parent


def get_config_path() -> Path:
    return get_base_dir() / CONFIG_FILE


def load_config() -> dict:
    """Mevcut yapılandırmayı yükler, yoksa varsayılanı döndürür."""
    path = get_config_path()
    if not path.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Varsayılan eksik alanları tamamla
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
    except Exception as e:
        print(f"[UYARI] config.json okunamadı ({e}). Varsayılan ayarlar kullanılıyor.")
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Yapılandırmayı config.json dosyasına kaydeder."""
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[HATA] config.json kaydedilemedi: {e}")
        return False


def setup_interactive(force: bool = False) -> dict:
    """
    Kullanıcıdan ilk kurulum bilgilerini (GitHub Token ve Proje Klasörü) ister.
    """
    config = load_config()
    if not force and config.get("github_token") and config.get("local_repos_dir"):
        return config

    print("\n" + "=" * 60)
    print("      GitPulse - İlk Kurulum ve Yapılandırma")
    print("=" * 60)
    print("GitHub projelerinizin taranması ve güncellenmesi için")
    print("bir GitHub Personal Access Token (PAT) gereklidir.\n")
    print("Token almak için:")
    print("1. https://github.com/settings/tokens adresine gidin")
    print("2. 'Generate new token (classic)' seçin")
    print("3. 'repo' yetkilerini işaretleyin ve token'ı kopyalayın.\n")

    current_token = config.get("github_token", "")
    token_prompt = f"GitHub Token [{current_token[:6]}...]: " if current_token else "GitHub Personal Access Token: "
    token_input = input(token_prompt).strip()
    if token_input:
        config["github_token"] = token_input

    # Varsayılan yerel kod klasörü (bir üst dizin veya kullanıcı klasörü)
    default_dir = config.get("local_repos_dir")
    if not default_dir:
        # GitPulse'ın bulunduğu bir üst dizin (örneğin C:\Users\Administrator\Desktop\code)
        parent_dir = str(get_base_dir().parent)
        default_dir = parent_dir

    print(f"\nProjelerinizin bilgisayarınızda saklanacağı ana klasör yolu:")
    dir_input = input(f"Yerel Proje Klasörü [{default_dir}]: ").strip()
    if dir_input:
        config["local_repos_dir"] = os.path.abspath(dir_input)
    else:
        config["local_repos_dir"] = os.path.abspath(default_dir)

    os.makedirs(config["local_repos_dir"], exist_ok=True)
    save_config(config)

    print("\n[OK] Ayarlar başarıyla config.json dosyasına kaydedildi!")
    print("=" * 60 + "\n")
    return config
