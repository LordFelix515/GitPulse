import os
import sys
from pathlib import Path
from typing import Tuple

STARTUP_FILE_NAME = "GitPulse-Startup.bat"
OLD_STARTUP_FILE_NAME = "AutoGithub-Startup.bat"


def get_windows_startup_dir() -> Path:
    """Windows Başlangıç (Startup) klasörünün yolunu döndürür."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    # Alternatif yol
    userprofile = os.environ.get("USERPROFILE", "")
    return Path(userprofile) / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def get_startup_file_path() -> Path:
    return get_windows_startup_dir() / STARTUP_FILE_NAME


def is_in_startup() -> bool:
    """Uygulamanın Windows başlangıcına ekli olup olmadığını kontrol eder."""
    return get_startup_file_path().exists()


def add_to_startup() -> Tuple[bool, str]:
    """
    Windows başlangıç klasörüne GitPulse'ı çalıştıracak BAT dosyasını oluşturur.
    """
    startup_dir = get_windows_startup_dir()
    if not startup_dir.exists():
        try:
            startup_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f"Başlangıç klasörü oluşturulamadı: {e}"

    # Eski isimli bat varsa temizle
    old_file = startup_dir / OLD_STARTUP_FILE_NAME
    if old_file.exists():
        try:
            old_file.unlink()
        except Exception:
            pass

    target_file = get_startup_file_path()
    current_dir = Path(__file__).resolve().parent
    main_script = current_dir / "gitpulse.py"

    # Python yürütülebilir yolu
    python_exe = sys.executable

    # BAT dosyası içeriği
    # UTF-8 desteği için chcp 65001, dizine git ve python gitpulse.py --startup çalıştır
    bat_content = f"""@echo off
chcp 65001 > nul
title GitPulse - Otomatik Proje Senkronizasyonu
cd /d "{current_dir}"
"{python_exe}" "{main_script}" --startup
"""

    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(bat_content)
        return True, str(target_file)
    except Exception as e:
        return False, str(e)


def remove_from_startup() -> Tuple[bool, str]:
    """Windows başlangıcındaki BAT dosyasını siler."""
    target_file = get_startup_file_path()
    if not target_file.exists():
        return True, "Başlangıçta zaten kayıtlı değil."

    try:
        target_file.unlink()
        return True, "Windows başlangıcından başarıyla kaldırıldı."
    except Exception as e:
        return False, f"Silinemedi: {e}"
