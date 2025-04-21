import os
import subprocess
import sys
import venv
import platform

def create_virtual_env():
    """Crée un environnement virtuel pour l'agent."""
    env_dir = os.path.expanduser("~/devopsagent_env")
    if os.path.exists(env_dir):
        print(f"L'environnement virtuel existe déjà dans {env_dir}")
    else:
        print(f"Création de l'environnement virtuel dans {env_dir}...")
        # S'assurer que venv est créé avec pip
        venv.create(env_dir, with_pip=True, system_site_packages=False, clear=True)
        print("Environnement virtuel créé avec succès!")
    
    return env_dir

def get_venv_python(env_dir):
    """Obtient le chemin vers l'exécutable Python de l'environnement virtuel."""
    if os.name == 'nt':  # Windows
        return os.path.join(env_dir, 'Scripts', 'python.exe')
    else:  # Unix/Linux/MacOS
        return os.path.join(env_dir, 'bin', 'python')

def install_pip_manually(env_dir):
    """Installe pip manuellement dans l'environnement virtuel si nécessaire."""
    python_exec = get_venv_python(env_dir)
    
    print("Installation manuelle de pip...")
    try:
        # Télécharger get-pip.py
        subprocess.check_call(["curl", "https://bootstrap.pypa.io/get-pip.py", "-o", "get-pip.py"])
        # Installer pip dans l'environnement virtuel
        subprocess.check_call([python_exec, "get-pip.py"])
        # Supprimer get-pip.py
        os.remove("get-pip.py")
        print("Pip installé avec succès!")
        return True
    except Exception as e:
        print(f"Erreur lors de l'installation manuelle de pip: {e}")
        return False

def ensure_pip(env_dir):
    """S'assure que pip est disponible dans l'environnement virtuel."""
    python_exec = get_venv_python(env_dir)
    
    # Vérifier si pip est disponible
    try:
        subprocess.check_call([python_exec, "-m", "pip", "--version"], stdout=subprocess.DEVNULL)
        print("Pip est déjà installé.")
        return True
    except:
        print("Pip n'est pas disponible. Installation en cours...")
        
        # S'assurer que les packages nécessaires pour venv sont installés
        try:
            subprocess.check_call(["sudo", "apt", "install", "-y", "python3-venv", "python3-pip"])
        except:
            print("Impossible d'installer python3-venv avec apt. Continuons...")
        
        # Recréer l'environnement virtuel
        try:
            print("Recréation de l'environnement virtuel avec pip...")
            import shutil
            shutil.rmtree(env_dir)
            venv.create(env_dir, with_pip=True)
            
            # Vérifier à nouveau pip
            try:
                subprocess.check_call([python_exec, "-m", "pip", "--version"], stdout=subprocess.DEVNULL)
                print("Pip a été installé avec succès!")
                return True
            except:
                return install_pip_manually(env_dir)
                
        except Exception as e:
            print(f"Erreur lors de la recréation de l'environnement virtuel: {e}")
            return install_pip_manually(env_dir)

def install_requirements(env_dir):
    """Installe les dépendances requises dans l'environnement virtuel."""
    required_packages = [
        "requests",
        "psutil",
        "pyyaml",
    ]
    
    python_exec = get_venv_python(env_dir)
    
    # S'assurer que pip est disponible
    if not ensure_pip(env_dir):
        print("Impossible d'installer pip. L'installation des dépendances échoue.")
        sys.exit(1)
    
    print(f"Installation des dépendances avec {python_exec}...")
    
    try:
        subprocess.check_call([python_exec, "-m", "pip", "install", "--upgrade"] + required_packages)
        print("Dépendances installées avec succès!")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'installation des dépendances: {e}")
        sys.exit(1)

def create_directories():
    """Crée les répertoires nécessaires."""
    app_name = "DevOpsAgent"
    config_dir = os.path.expanduser(f"~/.config/{app_name.lower()}")
    dirs = [
        config_dir,
        os.path.join(config_dir, "templates"),
        os.path.join(config_dir, "logs"),
        os.path.join(config_dir, "tasks"),
    ]
    
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)
        print(f"Créé: {directory}")

def create_default_templates():
    """Crée les templates par défaut."""
    app_name = "DevOpsAgent"
    templates_dir = os.path.expanduser(f"~/.config/{app_name.lower()}/templates")
    
    templates = {
        "diagnostic.txt": (
            "Tu es un expert en diagnostic système Linux/Unix. "
            "Analyse ce problème et suggère des commandes pour diagnostiquer : '{query}'. "
            "Fournir uniquement des commandes Bash précises qui aideront à identifier la cause du problème."
        ),
        "docker.txt": (
            "Tu es un expert Docker et conteneurisation. "
            "Propose des commandes Docker/Podman pour : '{query}'. "
            "Assure-toi que tes commandes suivent les bonnes pratiques."
        ),
        "kubernetes.txt": (
            "Tu es un expert Kubernetes. "
            "Propose des commandes kubectl ou des manifestes YAML pour : '{query}'. "
            "Si tu suggères un manifeste YAML, indique aussi comment l'appliquer."
        ),
        "network.txt": (
            "Tu es un expert en réseaux et sécurité. "
            "Propose des commandes pour diagnostiquer ou configurer : '{query}'. "
            "Inclus des commandes pour la configuration du pare-feu si nécessaire."
        )
    }
    
    for filename, content in templates.items():
        with open(os.path.join(templates_dir, filename), "w") as f:
            f.write(content)
        print(f"Template créé: {filename}")

def create_launcher_script(env_dir):
    """Crée un script launcher pour démarrer l'agent."""
    launcher_path = os.path.expanduser("~/devopsagent.sh")
    agent_path = os.path.abspath("devops_agent.py")
    
    python_exec = get_venv_python(env_dir)
    
    with open(launcher_path, "w") as f:
        f.write(f"""#!/bin/bash
# Script de lancement de DevOpsAgent
{python_exec} {agent_path} "$@"
""")
    
    # Rendre le script exécutable
    os.chmod(launcher_path, 0o755)
    print(f"Script de lancement créé: {launcher_path}")

def main():
    """Fonction principale d'installation."""
    print("=== Installation de DevOpsAgent ===")
    
    # Vérifier que python3-venv est installé
    try:
        import ensurepip
        print("Module ensurepip disponible.")
    except ImportError:
        print("Module ensurepip non disponible. Installation de python3-venv...")
        try:
            subprocess.check_call(["sudo", "apt", "install", "-y", "python3-venv", "python3-pip"])
        except:
            print("ATTENTION: Impossible d'installer python3-venv automatiquement.")
            print("Veuillez l'installer manuellement avec: sudo apt install python3-venv python3-pip")
            if input("Continuer quand même? (o/n): ").lower() != 'o':
                sys.exit(1)
    
    env_dir = create_virtual_env()
    install_requirements(env_dir)
    create_directories()
    create_default_templates()
    create_launcher_script(env_dir)
    
    print("\nInstallation terminée avec succès!")
    print(f"Pour lancer l'agent, exécutez: ~/devopsagent.sh")

if __name__ == "__main__":
    main()