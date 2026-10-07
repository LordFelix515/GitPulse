import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Set, Tuple

import colorama
from colorama import Fore, Style

from config import get_config_path, load_config, save_config, setup_interactive
from git_manager import GitManager
from github_client import GitHubClient
from ignore_manager import (
    add_to_ignore,
    get_all_ignored,
    get_ignore_file_path,
    is_repo_ignored,
    load_ignored_repos,
    remove_from_ignore,
)
from startup_manager import add_to_startup, is_in_startup, remove_from_startup

# Windows konsolunda UTF-8 karakterlerin sorunsuz yazdırılması için
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

# Colorama Windows desteğini başlat
colorama.init(autoreset=True)


def print_banner():
    """Şık karşılama başlığı."""
    print(Fore.CYAN + Style.BRIGHT + """
 ╔══════════════════════════════════════════════════════════╗
 ║                   ⚡ GitPulse v1.0.0                      ║
 ║      GitHub Proje Eşitleyici ve Otomatik Güncelleyici     ║
 ╚══════════════════════════════════════════════════════════╝
    """ + Style.RESET_ALL)


def parse_user_selection(input_str: str, max_count: int) -> Tuple[str, List[int]]:
    """
    Kullanıcının girdiği komutu analiz eder.
    Örnekler:
      - '1' -> ('download', [1])
      - '1 3' veya '1, 3' -> ('download', [1, 3])
      - '1 ignore' veya '1 3 ignore' -> ('ignore', [1, 3])
      - 'ignore 1 3' -> ('ignore', [1, 3])
      - 'all' -> ('download', [1..max_count])
      - 'all ignore' -> ('ignore', [1..max_count])
      - '' (boş) -> ('skip', [])
    """
    raw = input_str.strip()
    if not raw:
        return "skip", []

    is_ignore_command = "ignore" in raw.lower()
    cleaned = re.sub(r"(?i)\bignore\b", "", raw).strip()

    # 'all' veya 'hepsi' kontrolü
    if "all" in cleaned.lower() or "hepsi" in cleaned.lower():
        selected = list(range(1, max_count + 1))
        return ("ignore" if is_ignore_command else "download"), selected

    # Sayıları ayıkla
    numbers = []
    tokens = re.findall(r"\d+", cleaned)
    for tok in tokens:
        try:
            num = int(tok)
            if 1 <= num <= max_count and num not in numbers:
                numbers.append(num)
        except ValueError:
            pass

    if not numbers:
        return "invalid", []

    action = "ignore" if is_ignore_command else "download"
    return action, sorted(numbers)


def handle_new_repositories(
    missing_repos: List[dict],
    git_manager: GitManager,
    local_dir: Path
):
    """
    Yerelde olmayan ve ignore listesinde bulunmayan repoları numaralı olarak listeler
    ve kullanıcının seçimine göre indirir veya dwnignore listesine ekler.
    """
    if not missing_repos:
        return

    print("\n" + Fore.YELLOW + Style.BRIGHT + f"📦 Bilgisayarınızda bulunmayan {len(missing_repos)} yeni GitHub projesi tespit edildi:" + Style.RESET_ALL)
    print(Fore.YELLOW + "─" * 65 + Style.RESET_ALL)

    for idx, repo in enumerate(missing_repos, start=1):
        visibility = Fore.RED + "[Private]" if repo.get("private") else Fore.GREEN + "[Public ]"
        desc = f" - {repo.get('description')[:45]}..." if repo.get("description") else ""
        print(f"  {Fore.CYAN}[{idx}]{Style.RESET_ALL} {visibility} {Fore.WHITE}{Style.BRIGHT}{repo['name']}{Style.RESET_ALL}{Fore.LIGHTBLACK_EX}{desc}{Style.RESET_ALL}")

    print(Fore.YELLOW + "─" * 65 + Style.RESET_ALL)
    print(Fore.LIGHTCYAN_EX + "Komut Seçenekleri:" + Style.RESET_ALL)
    print("  • İndirmek için: " + Fore.GREEN + "1 3" + Style.RESET_ALL + " ya da " + Fore.GREEN + "1" + Style.RESET_ALL + " (veya 'all')")
    print("  • Ignore listesine eklemek için: " + Fore.MAGENTA + "1 ignore" + Style.RESET_ALL + " ya da " + Fore.MAGENTA + "1 3 ignore" + Style.RESET_ALL)
    print("  • Şimdilik atlamak için: " + Fore.LIGHTBLACK_EX + "Enter" + Style.RESET_ALL + " tuşuna basın\n")

    user_input = input(Fore.LIGHTYELLOW_EX + "Seçiminiz: " + Style.RESET_ALL).strip()
    action, indices = parse_user_selection(user_input, len(missing_repos))

    if action == "skip":
        print(Fore.LIGHTBLACK_EX + "ℹ️  Yeni projeler şimdilik atlandı (daha sonra tekrar sorulacak)." + Style.RESET_ALL)
        return

    if action == "invalid":
        print(Fore.RED + "❌ Geçersiz seçim yapıldı. İşlem atlandı." + Style.RESET_ALL)
        return

    selected_repos = [missing_repos[i - 1] for i in indices]

    if action == "ignore":
        names_to_ignore = [r["name"] for r in selected_repos]
        added = add_to_ignore(names_to_ignore)
        print(Fore.MAGENTA + Style.BRIGHT + f"\n✓ {len(added)} proje dwnignore listesine eklendi:" + Style.RESET_ALL)
        for name in added:
            print(Fore.MAGENTA + f"   - {name}" + Style.RESET_ALL)

    elif action == "download":
        print(Fore.GREEN + Style.BRIGHT + f"\n⏳ {len(selected_repos)} proje indiriliyor..." + Style.RESET_ALL)
        for r in selected_repos:
            target_path = local_dir / r["name"]
            print(f"  → Klonlanıyor: {Fore.CYAN}{r['name']}{Style.RESET_ALL} ... ", end="", flush=True)
            success, msg = git_manager.clone_repo(r["clone_url"], target_path)
            if success:
                print(Fore.GREEN + "[BAŞARILI]" + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[HATA: {msg}]" + Style.RESET_ALL)


def sync_repositories(is_startup_mode: bool = False):
    """
    Ana senkronizasyon akışı:
    1. İnternet ve API kontrolü
    2. GitHub'daki repoları çek
    3. Yerelde olanları git fetch/pull ile güncelle
    4. Yerelde olmayanları dwnignore filtresinden geçir ve kullanıcıya sor
    """
    config = load_config()

    if not config.get("github_token") or not config.get("local_repos_dir"):
        config = setup_interactive()

    token = config.get("github_token", "")
    local_dir_str = config.get("local_repos_dir", "")

    if not token or not local_dir_str:
        print(Fore.RED + "❌ Hata: GitHub Token veya Proje Klasörü yapılandırılmamış." + Style.RESET_ALL)
        print("Lütfen 'python gitpulse.py --setup' komutu ile ayarları tamamlayın.")
        return

    local_dir = Path(local_dir_str)
    local_dir.mkdir(parents=True, exist_ok=True)

    gh_client = GitHubClient(token)
    git_manager = GitManager(token)

    # 1. İnternet bağlantısı kontrolü (Başlangıç modunda birkaç deneme yap)
    print(Fore.LIGHTBLUE_EX + "🔍 İnternet ve GitHub bağlantısı kontrol ediliyor..." + Style.RESET_ALL)
    max_retries = 5 if is_startup_mode else 2
    if not gh_client.check_connection(max_retries=max_retries, retry_delay=3):
        print(Fore.RED + "❌ GitHub'a bağlanılamadı. Lütfen internet bağlantınızı kontrol edin." + Style.RESET_ALL)
        return

    # Token kontrolü
    is_valid, username, err_msg = gh_client.verify_token()
    if not is_valid:
        print(Fore.RED + f"❌ GitHub Yetkilendirme Hatası: {err_msg}" + Style.RESET_ALL)
        return

    print(Fore.GREEN + f"✓ Giriş yapıldı: {Fore.WHITE}{Style.BRIGHT}@{username}{Style.RESET_ALL}")
    print(Fore.LIGHTBLACK_EX + f"📁 Yerel Proje Dizini: {local_dir}" + Style.RESET_ALL + "\n")

    # 2. GitHub repolarını çek
    print(Fore.LIGHTBLUE_EX + "📡 GitHub depoları taranıyor..." + Style.RESET_ALL)
    repos, err = gh_client.get_user_repositories(
        include_forks=config.get("include_forks", True),
        include_archived=config.get("include_archived", False)
    )

    if err:
        print(Fore.RED + f"❌ {err}" + Style.RESET_ALL)
        return

    print(Fore.CYAN + f"✓ GitHub üzerinde toplam {len(repos)} deponuz bulundu.\n" + Style.RESET_ALL)

    ignored_set = load_ignored_repos()

    existing_repos = []
    missing_repos = []

    for r in repos:
        repo_name = r["name"]
        repo_path = local_dir / repo_name

        if repo_path.exists():
            existing_repos.append((r, repo_path))
        else:
            # dwnignore dosyasında var mı kontrol et
            if not is_repo_ignored(repo_name, r.get("full_name", ""), ignored_set):
                missing_repos.append(r)

    # 3. Yerelde var olan repoları kontrol et ve güncelle
    print(Fore.BLUE + Style.BRIGHT + f"🔄 Yereldeki Projeler Kontrol Ediliyor ({len(existing_repos)} proje)..." + Style.RESET_ALL)
    print("─" * 65)

    updated_count = 0
    uptodate_count = 0
    warning_count = 0

    for r, repo_path in existing_repos:
        repo_name = r["name"]
        status_info = git_manager.check_sync_status(repo_path)

        if not status_info.get("is_git"):
            print(f"  {Fore.YELLOW}[ATLANDI]{Style.RESET_ALL} {repo_name} (Geçerli bir Git deposu değil)")
            continue

        st = status_info.get("status")
        branch = status_info.get("current_branch", "main")

        if st == "UP_TO_DATE":
            uptodate_count += 1
            print(f"  {Fore.GREEN}[GÜNCEL]{Style.RESET_ALL}   {Fore.WHITE}{repo_name}{Style.RESET_ALL} ({branch})")

        elif st == "BEHIND":
            behind = status_info.get("behind_count", 0)
            if status_info.get("has_changes"):
                warning_count += 1
                print(f"  {Fore.YELLOW}[UYARI]{Style.RESET_ALL}    {Fore.WHITE}{repo_name}{Style.RESET_ALL} ({behind} yeni commit var, ancak yerelde kaydedilmemiş değişiklikler olduğu için çekilmedi)")
            else:
                # Güncelle
                print(f"  {Fore.CYAN}[GÜNCELLENİYOR]{Style.RESET_ALL} {Fore.WHITE}{repo_name}{Style.RESET_ALL} ({behind} yeni commit)... ", end="", flush=True)
                pull_ok, pull_msg, restored_env = git_manager.pull_repo(repo_path)
                if pull_ok:
                    updated_count += 1
                    env_info = ""
                    if restored_env:
                        env_info = f" {Fore.GREEN}(🛡️ {len(restored_env)} .env korundu: {', '.join(restored_env)}){Style.RESET_ALL}"
                    print(Fore.GREEN + "[GÜNCELLENDİ]" + Style.RESET_ALL + env_info)
                else:
                    warning_count += 1
                    print(Fore.RED + f"[HATA: {pull_msg}]" + Style.RESET_ALL)

        elif st == "AHEAD":
            ahead = status_info.get("ahead_count", 0)
            print(f"  {Fore.BLUE}[İLERİDE]{Style.RESET_ALL}   {Fore.WHITE}{repo_name}{Style.RESET_ALL} (Yerelde {ahead} gönderilmemiş commit var)")

        elif st == "DIVERGED":
            warning_count += 1
            print(f"  {Fore.MAGENTA}[AYRIŞMIŞ]{Style.RESET_ALL}  {Fore.WHITE}{repo_name}{Style.RESET_ALL} (Yerel ve uzak dallar ayrışmış, manuel merge gerekir)")

        else:
            msg = status_info.get("message", "")
            print(f"  {Fore.LIGHTBLACK_EX}[BİLGİ]{Style.RESET_ALL}    {Fore.WHITE}{repo_name}{Style.RESET_ALL} ({msg or st})")

    print("─" * 65)
    print(Fore.LIGHTCYAN_EX + f"📊 Özet: {Fore.GREEN}{uptodate_count} Güncel{Style.RESET_ALL} | {Fore.CYAN}{updated_count} Güncellendi{Style.RESET_ALL} | {Fore.YELLOW}{warning_count} Dikkat Gerektiren{Style.RESET_ALL}")

    # 4. Yerelde olmayan ve dwnignore'da yer almayan projeler
    handle_new_repositories(missing_repos, git_manager, local_dir)

    print("\n" + Fore.GREEN + Style.BRIGHT + "🎉 Tüm işlemler tamamlandı!" + Style.RESET_ALL)

    if is_startup_mode:
        countdown = config.get("startup_countdown_seconds", 10)
        print(Fore.LIGHTBLACK_EX + f"\n(Bu pencere {countdown} saniye sonra otomatik kapanacaktır. Kapatmak için herhangi bir tuşa basabilirsiniz...)" + Style.RESET_ALL)
        try:
            for sec in range(countdown, 0, -1):
                time.sleep(1)
        except KeyboardInterrupt:
            pass


def show_status():
    """Mevcut yapılandırma ve başlangıç durumunu görüntüler."""
    print_banner()
    config = load_config()
    print(Fore.LIGHTCYAN_EX + "📋 GitPulse Mevcut Durum:" + Style.RESET_ALL)
    print("─" * 50)
    has_token = bool(config.get("github_token"))
    token_display = config.get("github_token")[:8] + "..." if has_token else Fore.RED + "Tanımlanmamış" + Style.RESET_ALL
    print(f" • GitHub Token        : {token_display}")
    print(f" • Projeler Dizini     : {config.get('local_repos_dir') or Fore.RED + 'Tanımlanmamış' + Style.RESET_ALL}")
    print(f" • Fork'lar Dahil mi   : {'Evet' if config.get('include_forks') else 'Hayır'}")
    print(f" • Windows Başlangıcı  : {Fore.GREEN + 'AKTİF' if is_in_startup() else Fore.YELLOW + 'PASİF' + Style.RESET_ALL}")

    ignored = get_all_ignored()
    print(f" • dwnignore Sayısı    : {len(ignored)} proje")
    print(f" • Ignore Dosyası      : {get_ignore_file_path()}")
    print("─" * 50)


def list_ignored_command():
    """Ignore listesindeki projeleri ekrana yazdırır."""
    ignored = get_all_ignored()
    print("\n" + Fore.MAGENTA + Style.BRIGHT + f"📑 dwnignore Listesi ({len(ignored)} Proje):" + Style.RESET_ALL)
    if not ignored:
        print(Fore.LIGHTBLACK_EX + "  Listeniz henüz boş." + Style.RESET_ALL)
        return
    for idx, item in enumerate(ignored, 1):
        print(f"  [{idx}] {item}")
    print()


def unignore_command(repo_name: str):
    """Bir projeyi dwnignore listesinden çıkarır."""
    if remove_from_ignore(repo_name):
        print(Fore.GREEN + f"✓ '{repo_name}' dwnignore listesinden çıkarıldı." + Style.RESET_ALL)
    else:
        print(Fore.RED + f"❌ '{repo_name}' ignore listesinde bulunamadı." + Style.RESET_ALL)


def main():
    parser = argparse.ArgumentParser(
        description="GitPulse - Bilgisayar açılışında GitHub projelerini otomatik denetler ve günceller."
    )
    parser.add_argument("--startup", action="store_true", help="Windows başlangıç modunda çalıştır")
    parser.add_argument("--setup", action="store_true", help="Ayarları sıfırdan yapılandır")
    parser.add_argument("--status", action="store_true", help="Mevcut durum ve ayarları göster")
    parser.add_argument("--add-startup", action="store_true", help="Windows başlangıcına ekle")
    parser.add_argument("--remove-startup", action="store_true", help="Windows başlangıcından kaldır")
    parser.add_argument("--list-ignored", action="store_true", help="dwnignore listesini göster")
    parser.add_argument("--unignore", type=str, metavar="REPO", help="Bir projeyi dwnignore listesinden çıkar")

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.setup:
        print_banner()
        setup_interactive(force=True)
        return

    if args.add_startup:
        print_banner()
        ok, msg = add_to_startup()
        if ok:
            print(Fore.GREEN + f"✓ GitPulse başarıyla Windows Başlangıç klasörüne eklendi!\n  Dosya: {msg}" + Style.RESET_ALL)
        else:
            print(Fore.RED + f"❌ Başlangıca eklenemedi: {msg}" + Style.RESET_ALL)
        return

    if args.remove_startup:
        print_banner()
        ok, msg = remove_from_startup()
        if ok:
            print(Fore.GREEN + f"✓ {msg}" + Style.RESET_ALL)
        else:
            print(Fore.RED + f"❌ {msg}" + Style.RESET_ALL)
        return

    if args.list_ignored:
        list_ignored_command()
        return

    if args.unignore:
        unignore_command(args.unignore)
        return

    print_banner()
    sync_repositories(is_startup_mode=args.startup)


if __name__ == "__main__":
    main()
