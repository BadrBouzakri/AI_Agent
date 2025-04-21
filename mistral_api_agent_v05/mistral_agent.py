#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mistral Agent DevOps - Un assistant IA pour terminal Linux
Utilise le modèle Mistral pour assister dans les tâches DevOps et SysAdmin
"""

import os
import sys
import re
import json
import logging
import readline
import subprocess
import requests
from datetime import datetime
import argparse
from typing import List, Dict, Any, Optional, Tuple
import shlex
import signal

# Bibliothèques pour l'interface
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.syntax import Syntax
    from rich import box
    import typer
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("Pour une meilleure expérience visuelle, installez rich et typer: pip install rich typer")

# Paramètres constants
API_KEY = "n46jy69eatOFdxAI7Rb0PXsj6jrVv16K"
API_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-large-latest"
SCRIPTS_DIR = os.path.expanduser("~/tech/scripts")
LOG_FILE = os.path.expanduser("~/.ia_agent_logs.log")
HISTORY_FILE = os.path.expanduser("~/.ia_agent_history.json")
MAX_HISTORY_ENTRIES = 20
DANGEROUS_COMMANDS = ["rm", "mv", "dd", "mkfs", "fdisk", ">", "2>", "truncate", "rmdir", "pkill", "kill", 
                     "shutdown", "reboot", "halt", "systemctl stop", "systemctl restart", "chown", "chmod", 
                     "userdel", "groupdel", "deluser", "passwd", "parted", "lvremove", "vgremove", "pvremove",
                     "iptables -F", "ufw disable"]

# Extensions de fichiers pour les différents types de scripts
SCRIPT_EXTENSIONS = {
    "python": ".py",
    "bash": ".sh",
    "shell": ".sh",
    "yaml": ".yaml",
    "yml": ".yml",
    "docker": ".dockerfile",
    "dockerfile": ".dockerfile",
    "terraform": ".tf",
    "json": ".json",
    "js": ".js",
    "ansible": ".yml",
    "php": ".php",
    "ruby": ".rb",
    "go": ".go",
    "java": ".java",
    "c": ".c",
    "cpp": ".cpp",
    "csharp": ".cs",
    "sql": ".sql",
    "kubernetes": ".yaml",
    "k8s": ".yaml",
    "helm": ".yaml",
    "nginx": ".conf",
    "apache": ".conf",
    "systemd": ".service",
    "prometheus": ".yml",
    "grafana": ".json",
    "jenkins": "Jenkinsfile",
    "gitlab-ci": ".gitlab-ci.yml",
    "github-workflow": ".yml",
}

# Modèles pour différentes tâches DevOps
TEMPLATES = {
    "docker": """FROM alpine:latest

LABEL maintainer="Your Name <your.email@example.com>"

RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY . .

CMD ["sh"]
""",
    "terraform": """provider "aws" {
  region = "us-west-2"
}

resource "aws_instance" "example" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"
  
  tags = {
    Name = "example-instance"
  }
}
""",
    "kubernetes": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  labels:
    app: nginx
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.14.2
        ports:
        - containerPort: 80
""",
    "ansible": """---
- name: Example Playbook
  hosts: all
  become: yes
  tasks:
    - name: Ensure a package is installed
      apt:
        name: nginx
        state: present
      when: ansible_os_family == "Debian"
    
    - name: Ensure a service is running
      service:
        name: nginx
        state: started
        enabled: yes
"""
}

# Commandes rapides pour les tâches courantes
QUICK_COMMANDS = {
    # Gestion des services
    "service-status": "systemctl status {service}",
    "service-start": "systemctl start {service}",
    "service-stop": "systemctl stop {service}",
    "service-restart": "systemctl restart {service}",
    "service-enable": "systemctl enable {service}",
    "service-disable": "systemctl disable {service}",
    "service-list": "systemctl list-units --type=service",
    
    # Supervision système
    "cpu-info": "lscpu",
    "mem-info": "free -h",
    "disk-usage": "df -h",
    "top-processes": "ps aux | sort -nrk 3,3 | head -n 10",
    "check-port": "ss -tuln | grep {port}",
    "cpu-load": "mpstat 1 5",
    "io-stats": "iostat -xz 1 5",
    
    # Réseau
    "ping-host": "ping -c 4 {host}",
    "check-ip": "ip addr show",
    "route-table": "ip route",
    "dns-lookup": "dig {domain}",
    "open-ports": "netstat -tuln",
    "traceroute": "traceroute {host}",
    
    # Docker
    "docker-ps": "docker ps",
    "docker-images": "docker images",
    "docker-stats": "docker stats --no-stream",
    "docker-prune": "docker system prune -f",
    
    # Kubernetes
    "k8s-pods": "kubectl get pods",
    "k8s-nodes": "kubectl get nodes",
    "k8s-deployments": "kubectl get deployments",
    "k8s-services": "kubectl get services",
    
    # Journaux
    "logs-system": "journalctl -xe",
    "logs-service": "journalctl -u {service} -f",
    "logs-auth": "tail -n 50 /var/log/auth.log",
    "logs-kernel": "dmesg | tail -n 50",
    
    # Gestion des paquets
    "apt-update": "sudo apt update && sudo apt list --upgradable",
    "apt-upgrade": "sudo apt upgrade -y",
    "pkg-installed": "dpkg -l | grep {package}",
    
    # Surveillance fichiers
    "find-large-files": "find {path} -type f -size +{size}M -exec ls -lh {} \\;",
    "tail-file": "tail -f {file}",
    "find-modified": "find {path} -type f -mtime -{days} -ls",
    
    # Git
    "git-status": "git status",
    "git-log": "git log --oneline --graph --decorate -n 10",
}

# Commandes pour récupérer des informations système
SYSTEM_INFO_COMMANDS = {
    "os-version": "cat /etc/os-release",
    "kernel-version": "uname -a",
    "hostname": "hostname -f",
    "uptime": "uptime",
    "cpu-model": "cat /proc/cpuinfo | grep 'model name' | head -n 1 | cut -d ':' -f 2 | xargs",
    "total-memory": "free -h | grep Mem | awk '{print $2}'",
    "used-memory": "free -h | grep Mem | awk '{print $3}'",
    "disk-usage-root": "df -h / | tail -n 1 | awk '{print $5}'",
    "load-average": "cat /proc/loadavg | awk '{print $1, $2, $3}'",
    "users-logged-in": "who | wc -l",
    "process-count": "ps aux | wc -l",
    "network-interfaces": "ip -br addr show",
}

# Initialisation du logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Ajouter les fonctions utilitaires pour les tâches DevOps courantes
class DevOpsTools:
    """Classe contenant des outils/utilitaires pour les tâches DevOps courantes"""
    
    @staticmethod
    def monitor_ressources(duration=5, interval=1):
        """Surveille les ressources système pendant une durée donnée"""
        import time
        import psutil
        
        try:
            # Vérifier si psutil est installé
            if not 'psutil' in sys.modules:
                return "Module psutil requis. Installez-le avec: pip install psutil"
                
            results = []
            print(f"Surveillance des ressources pendant {duration} secondes...")
            
            for i in range(duration):
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                results.append({
                    'time': i,
                    'cpu': cpu,
                    'mem_percent': mem.percent,
                    'disk_percent': disk.percent
                })
                
                print(f"CPU: {cpu}% | MEM: {mem.percent}% | DISK: {disk.percent}%")
                
                if i < duration - 1:
                    time.sleep(interval)
                    
            # Calculer les moyennes
            avg_cpu = sum(r['cpu'] for r in results) / len(results)
            avg_mem = sum(r['mem_percent'] for r in results) / len(results)
            avg_disk = sum(r['disk_percent'] for r in results) / len(results)
            
            summary = f"""
Résumé de la surveillance ({duration} secondes):
- CPU moyenne: {avg_cpu:.1f}%
- Mémoire moyenne: {avg_mem:.1f}%
- Utilisation disque: {avg_disk:.1f}%
"""
            return summary
        except Exception as e:
            return f"Erreur lors de la surveillance des ressources: {str(e)}"
    
    @staticmethod
    def analyze_logs(log_file, pattern=None, tail=None, head=None):
        """Analyse un fichier de logs et extrait des informations pertinentes"""
        try:
            # Vérifier si le fichier existe
            if not os.path.exists(log_file):
                return f"Fichier de logs introuvable: {log_file}"
                
            # Lire le fichier
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                if tail:
                    # Lire les dernières lignes
                    lines = f.readlines()[-tail:]
                elif head:
                    # Lire les premières lignes
                    lines = []
                    for i, line in enumerate(f):
                        if i >= head:
                            break
                        lines.append(line)
                else:
                    # Lire tout le fichier
                    lines = f.readlines()
            
            # Filtrer par motif si demandé
            if pattern:
                filtered_lines = [line for line in lines if pattern in line]
                
                # Statistiques sur les motifs trouvés
                stats = f"Motif '{pattern}' trouvé dans {len(filtered_lines)} lignes sur {len(lines)} ({len(filtered_lines)/len(lines)*100:.1f}%)"
                
                # Limiter le nombre de lignes retournées
                if len(filtered_lines) > 100:
                    filtered_lines = filtered_lines[:100]
                    stats += " (affichage limité aux 100 premières lignes)"
                    
                return stats + "\n\n" + "".join(filtered_lines)
            else:
                # Limiter le nombre de lignes retournées
                if len(lines) > 100:
                    stats = f"Fichier contient {len(lines)} lignes (affichage limité aux 100 premières lignes)"
                    lines = lines[:100]
                    return stats + "\n\n" + "".join(lines)
                else:
                    return "".join(lines)
        except Exception as e:
            return f"Erreur lors de l'analyse des logs: {str(e)}"
    
    @staticmethod
    def docker_info():
        """Récupère des informations sur Docker"""
        try:
            # Vérifier si Docker est installé
            docker_version = subprocess.run(['docker', '--version'], capture_output=True, text=True)
            if docker_version.returncode != 0:
                return "Docker n'est pas installé ou accessible"
                
            # Récupérer les informations Docker
            docker_info = subprocess.run(['docker', 'info'], capture_output=True, text=True)
            containers = subprocess.run(['docker', 'ps', '-a'], capture_output=True, text=True)
            images = subprocess.run(['docker', 'images'], capture_output=True, text=True)
            
            return f"""
=== Docker ===
{docker_version.stdout}

=== Informations système Docker ===
{docker_info.stdout}

=== Conteneurs ===
{containers.stdout}

=== Images ===
{images.stdout}
"""
        except Exception as e:
            return f"Erreur lors de la récupération des informations Docker: {str(e)}"
    
    @staticmethod
    def k8s_info():
        """Récupère des informations sur Kubernetes"""
        try:
            # Vérifier si kubectl est installé
            kubectl_version = subprocess.run(['kubectl', 'version', '--client'], capture_output=True, text=True)
            if kubectl_version.returncode != 0:
                return "kubectl n'est pas installé ou accessible"
                
            # Récupérer les informations K8s
            try:
                nodes = subprocess.run(['kubectl', 'get', 'nodes'], capture_output=True, text=True, timeout=5)
                pods = subprocess.run(['kubectl', 'get', 'pods', '--all-namespaces'], capture_output=True, text=True, timeout=5)
                deployments = subprocess.run(['kubectl', 'get', 'deployments', '--all-namespaces'], capture_output=True, text=True, timeout=5)
                services = subprocess.run(['kubectl', 'get', 'services', '--all-namespaces'], capture_output=True, text=True, timeout=5)
                
                return f"""
=== Kubernetes ===
{kubectl_version.stdout}

=== Nœuds ===
{nodes.stdout}

=== Pods ===
{pods.stdout}

=== Déploiements ===
{deployments.stdout}

=== Services ===
{services.stdout}
"""
            except subprocess.TimeoutExpired:
                return "Erreur de délai d'attente lors de la communication avec Kubernetes. Le cluster est-il accessible?"
        except Exception as e:
            return f"Erreur lors de la récupération des informations Kubernetes: {str(e)}"
    
    @staticmethod
    def network_scan(target):
        """Effectue un scan réseau basique"""
        try:
            # Vérifier si ping est disponible
            ping_cmd = 'ping' if os.name != 'nt' else 'ping -n'
            
            if '/' in target:  # C'est un réseau CIDR
                return "Scan CIDR non implémenté pour l'instant"
            else:  # C'est un hôte unique
                ping = subprocess.run(f'{ping_cmd} 4 {target}', shell=True, capture_output=True, text=True)
                
                # Vérifier les ports ouverts avec nc si disponible
                try:
                    common_ports = [22, 80, 443, 3306, 5432, 8080]
                    open_ports = []
                    
                    for port in common_ports:
                        nc = subprocess.run(f'nc -z -w 1 {target} {port}', shell=True, capture_output=True, text=True)
                        if nc.returncode == 0:
                            open_ports.append(port)
                    
                    ports_info = f"\n\nPorts ouverts: {', '.join(map(str, open_ports)) if open_ports else 'Aucun trouvé'}"
                except:
                    ports_info = "\n\nVérification des ports impossible (nc non disponible)"
                    
                return f"""
=== Scan réseau pour {target} ===
{ping.stdout}
{ports_info}
"""
        except Exception as e:
            return f"Erreur lors du scan réseau: {str(e)}"
    
    @staticmethod
    def generate_ssl_cert(domain, output_dir=None):
        """Génère un certificat SSL auto-signé"""
        try:
            if output_dir is None:
                output_dir = os.getcwd()
                
            # Construire le chemin des fichiers
            key_file = os.path.join(output_dir, f"{domain}.key")
            cert_file = os.path.join(output_dir, f"{domain}.crt")
            
            # Générer la clé privée
            openssl_cmd = f"openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout {key_file} -out {cert_file} -subj '/CN={domain}'"
            result = subprocess.run(openssl_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                return f"Erreur lors de la génération du certificat: {result.stderr}"
                
            return f"""
Certificat SSL auto-signé généré avec succès:
- Clé privée: {key_file}
- Certificat: {cert_file}
- Validité: 365 jours
- Domaine: {domain}
"""
        except Exception as e:
            return f"Erreur lors de la génération du certificat SSL: {str(e)}"

# Classe principale de l'agent
class MistralAgent:
    def __init__(self, language="fr", debug=False):
        # Création du répertoire pour les scripts s'il n'existe pas
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        
        self.debug = debug
        self.language = language
        self.console = Console() if HAS_RICH else None
        self.conversation_history = []
        self.load_history()
        self.setup_signal_handlers()
        
        # Conserver le répertoire de travail actuel
        self.current_dir = os.getcwd()
        
        # Informations système
        self.system_info = {}
        self.collect_system_info()
        
        # Outils DevOps
        self.devops_tools = DevOpsTools()
        
        # Message système initial qui explique le rôle de l'agent
        self.system_message = f"""
Tu es un agent IA d'administration système et DevOps basé sur le modèle Mistral, conçu pour assister dans les tâches Linux et DevOps avancées.
Tu es un expert en gestion de systèmes Linux, réseau, Docker, Kubernetes, CI/CD, automatisation, et déploiement.

Tu travailles actuellement sur un système avec les caractéristiques suivantes:
- OS: {self.system_info.get('os-version', 'Linux')}
- Kernel: {self.system_info.get('kernel-version', 'Unknown')}
- Hostname: {self.system_info.get('hostname', 'Unknown')}
- CPU: {self.system_info.get('cpu-model', 'Unknown')}
- Mémoire: {self.system_info.get('total-memory', 'Unknown')}

Tu peux exécuter des commandes shell, créer des scripts et naviguer dans le système de fichiers.
Voici comment tu dois répondre:

1. Pour une commande à exécuter directement: [EXEC] commande [/EXEC]
2. Pour créer un script: [SCRIPT type nom_fichier] contenu [/SCRIPT]
3. Pour du texte normal: Réponds simplement sans aucun tag spécial
4. Pour naviguer entre les répertoires: [EXEC] cd chemin [/EXEC]
5. Pour utiliser un modèle: [TEMPLATE type nom_fichier]
6. Pour lancer une commande rapide: [QUICKCMD nom_commande paramètres]
7. Pour utiliser des outils DevOps intégrés: [DEVOPS outil paramètres]

N'utilise pas de formatage markdown complexe. Sois concis et précis.
Lorsque l'utilisateur demande de l'aide sur un sujet, donne des exemples pratiques et concrets.
Pour les commandes dangereuses, avertis l'utilisateur d'abord et demande confirmation.

Outils DevOps disponibles:
- [DEVOPS monitor_ressources [durée]]
- [DEVOPS analyze_logs fichier [pattern] [tail=N]]
- [DEVOPS docker_info]
- [DEVOPS k8s_info]
- [DEVOPS network_scan target]
- [DEVOPS generate_ssl_cert domaine]
"""
        # Personnalisation selon la langue
        self.prompt_prefix = "🤖 DevOps@" if language == "fr" else "🤖 DevOps@"
        
        # Charger ou créer le fichier de configuration
        self.config_file = os.path.expanduser("~/.mistral_agent_config.json")
        self.config = self.load_config()
        
    def load_config(self):
        """Charge ou crée le fichier de configuration"""
        default_config = {
            "theme": "dark",
            "max_history": MAX_HISTORY_ENTRIES,
            "default_scripts_dir": SCRIPTS_DIR,
            "custom_commands": {},
            "aliases": {},
            "favorites": []
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Erreur lors du chargement de la configuration: {e}")
                return default_config
        else:
            # Créer le fichier de configuration avec les valeurs par défaut
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
            except Exception as e:
                logging.error(f"Erreur lors de la création de la configuration: {e}")
                return default_config
    
    def save_config(self):
        """Sauvegarde le fichier de configuration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde de la configuration: {e}")
            
    def collect_system_info(self):
        """Collecte des informations sur le système"""
        for key, command in SYSTEM_INFO_COMMANDS.items():
            try:
                result = subprocess.run(command, shell=True, text=True, capture_output=True)
                if result.returncode == 0:
                    self.system_info[key] = result.stdout.strip()
                else:
                    self.system_info[key] = "Non disponible"
            except Exception:
                self.system_info[key] = "Erreur"

    def setup_signal_handlers(self):
        """Configure les gestionnaires de signaux pour une sortie propre"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Gère les signaux d'interruption"""
        print("\nFermeture propre de l'agent Mistral...")
        self.save_history()
        sys.exit(0)

    def load_history(self):
        """Charge l'historique des conversations"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.conversation_history = json.load(f)
                    # Limiter la taille de l'historique
                    if len(self.conversation_history) > MAX_HISTORY_ENTRIES:
                        self.conversation_history = self.conversation_history[-MAX_HISTORY_ENTRIES:]
            except Exception as e:
                logging.error(f"Erreur lors du chargement de l'historique: {e}")
                self.conversation_history = []
    
    def save_history(self):
        """Sauvegarde l'historique des conversations"""
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde de l'historique: {e}")

    def get_prompt(self):
        """Affiche le prompt personnalisé avec le répertoire courant"""
        # Mettre à jour le prompt avec le répertoire actuel
        dir_name = os.path.basename(self.current_dir)
        if dir_name == "":  # Si on est à la racine
            dir_name = "/"
            
        # Collecter des infos système pour l'affichage dans le prompt
        try:
            current_load = self.system_info.get('load-average', '').split()[0]
            memory_used = self.system_info.get('used-memory', 'N/A')
            disk_usage = self.system_info.get('disk-usage-root', 'N/A')
        except (IndexError, KeyError):
            current_load = "N/A"
            memory_used = "N/A"
            disk_usage = "N/A"
            
        # Prompt complet avec infos système
        if self.language == "fr":
            status_info = f"[L:{current_load}|M:{memory_used}|D:{disk_usage}]"
        else:
            status_info = f"[L:{current_load}|M:{memory_used}|D:{disk_usage}]"
            
        prompt = f"{self.prompt_prefix}{dir_name} {status_info} $ "
        
        if HAS_RICH:
            # Colorisation du prompt en fonction de la charge système
            try:
                load = float(current_load)
                if load < 1.0:
                    load_color = "green"
                elif load < 2.0:
                    load_color = "yellow"
                else:
                    load_color = "red"
            except (ValueError, TypeError):
                load_color = "cyan"
                
            # Formater le prompt avec Rich
            prompt_styled = f"[bold cyan]{self.prompt_prefix}[/bold cyan][bold blue]{dir_name}[/bold blue] [bold {load_color}]{status_info}[/bold {load_color}] $ "
            return self.console.input(prompt_styled)
        else:
            return input(prompt)

    def is_dangerous_command(self, command):
        """Vérifie si une commande est potentiellement dangereuse"""
        command_parts = shlex.split(command)
        if not command_parts:
            return False
            
        base_cmd = command_parts[0]
        
        # Vérifier les commandes dangereuses directes
        if base_cmd in DANGEROUS_COMMANDS:
            return True
            
        # Vérifier les redirections et pipes dangereux
        if ">" in command or "|" in command and ("rm" in command or "mv" in command):
            return True
            
        # Vérifier les options dangereuses spécifiques
        if base_cmd == "rm" and "-rf" in command_parts:
            return True
            
        return False

    def execute_command(self, command):
        """Exécute une commande shell et retourne le résultat"""
        logging.info(f"Exécution de la commande: {command}")
        
        # Vérifier les alias personnalisés
        for alias, cmd in self.config.get("aliases", {}).items():
            if command.strip() == alias or command.strip().startswith(f"{alias} "):
                # Remplacer l'alias par la commande complète
                command = command.replace(alias, cmd, 1)
                break
        
        # Gestion spéciale pour la commande cd
        if command.strip().startswith("cd "):
            try:
                # Extraire le chemin cible
                target_dir = command.strip()[3:].strip()
                
                # Gestion des chemins relatifs ou absolus
                if target_dir.startswith('/'):
                    new_dir = target_dir  # Chemin absolu
                else:
                    new_dir = os.path.join(self.current_dir, target_dir)
                
                # Résoudre les chemins comme ../ ou ./
                new_dir = os.path.abspath(new_dir)
                
                # Vérifier si le répertoire existe
                if os.path.isdir(new_dir):
                    os.chdir(new_dir)
                    self.current_dir = new_dir
                    # Mettre à jour les informations système
                    self.collect_system_info()
                    return f"Répertoire courant : {new_dir}"
                else:
                    return f"Erreur: Le répertoire {new_dir} n'existe pas."
            except Exception as e:
                logging.error(f"Erreur lors du changement de répertoire: {e}")
                return f"Erreur lors du changement de répertoire: {str(e)}"
        
        # Ajout à l'historique des commandes
        if command not in ['pwd', 'clear'] and not command.startswith('ls'):
            if 'command_history' not in self.config:
                self.config['command_history'] = []
            
            # Ajouter la commande à l'historique avec horodatage
            self.config['command_history'].append({
                'command': command,
                'timestamp': datetime.now().isoformat(),
                'directory': self.current_dir
            })
            
            # Limiter la taille de l'historique
            if len(self.config['command_history']) > 100:
                self.config['command_history'] = self.config['command_history'][-100:]
                
            # Sauvegarder la configuration
            self.save_config()
        
        # Pour les autres commandes, vérifier si elles sont dangereuses
        if self.is_dangerous_command(command):
            if HAS_RICH:
                self.console.print(f"[bold yellow]⚠️ Commande potentiellement dangereuse:[/bold yellow] {command}")
                self.console.print("[bold yellow]Cette commande pourrait avoir des effets destructifs sur votre système.[/bold yellow]")
                confirm = Confirm.ask("Confirmer l'exécution?")
            else:
                print(f"⚠️ Commande potentiellement dangereuse: {command}")
                print("Cette commande pourrait avoir des effets destructifs sur votre système.")
                confirm = input("Confirmer l'exécution? [o/N] ").lower() == 'o'
            
            if not confirm:
                return "Commande annulée par l'utilisateur."
        
        try:
            # Exécuter la commande dans le répertoire courant
            process = subprocess.Popen(
                command, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                cwd=self.current_dir  # Utiliser le répertoire courant
            )
            stdout, stderr = process.communicate()
            
            result = stdout.decode('utf-8')
            error = stderr.decode('utf-8')
            
            if process.returncode != 0:
                return f"Erreur (code {process.returncode}):\n{error}"
            else:
                # Mettre à jour les informations système après certaines commandes
                if any(cmd in command for cmd in ['apt', 'yum', 'dnf', 'systemctl', 'docker', 'kubectl']):
                    self.collect_system_info()
                return result
        except Exception as e:
            logging.error(f"Erreur lors de l'exécution de la commande: {e}")
            return f"Erreur: {str(e)}"

    def save_script(self, script_type, filename, content):
        """Sauvegarde un script généré dans le répertoire approprié"""
        # Détermination de l'extension appropriée
        has_extension = "." in filename
        
        # Si pas d'extension et qu'on a un type connu, ajouter l'extension
        if not has_extension and script_type.lower() in SCRIPT_EXTENSIONS:
            filename = filename + SCRIPT_EXTENSIONS[script_type.lower()]
            
        # Chemin complet du fichier
        filepath = os.path.join(SCRIPTS_DIR, filename)
        
        # Sauvegarde du fichier
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Rendre exécutable les scripts appropriés
            if script_type.lower() in ["bash", "shell", "python", "sh", "py"]:
                os.chmod(filepath, 0o755)
                
            logging.info(f"Script {script_type} sauvegardé: {filepath}")
            return filepath
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde du script: {e}")
            return f"Erreur lors de la sauvegarde: {str(e)}"
            
    def create_from_template(self, template_type, filename):
        """Crée un fichier à partir d'un modèle prédéfini"""
        template_type = template_type.lower()
        
        if template_type not in TEMPLATES:
            return f"Erreur: Modèle '{template_type}' non disponible. Templates disponibles: {', '.join(TEMPLATES.keys())}"
        
        # Détermination de l'extension appropriée
        has_extension = "." in filename
        
        # Si pas d'extension et qu'on a un type connu, ajouter l'extension
        if not has_extension and template_type in SCRIPT_EXTENSIONS:
            filename = filename + SCRIPT_EXTENSIONS[template_type]
            
        # Chemin complet du fichier
        filepath = os.path.join(self.current_dir, filename)
        
        # Sauvegarde du fichier
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(TEMPLATES[template_type])
                
            logging.info(f"Fichier créé à partir du modèle {template_type}: {filepath}")
            return f"Fichier créé à partir du modèle {template_type}: {filepath}"
        except Exception as e:
            logging.error(f"Erreur lors de la création du fichier: {e}")
            return f"Erreur lors de la création: {str(e)}"
            
    def execute_quick_command(self, cmd_name, *args):
        """Exécute une commande rapide prédéfinie"""
        if cmd_name not in QUICK_COMMANDS and cmd_name not in self.config.get("custom_commands", {}):
            available_commands = list(QUICK_COMMANDS.keys()) + list(self.config.get("custom_commands", {}).keys())
            return f"Erreur: Commande '{cmd_name}' non disponible. Commandes disponibles: {', '.join(sorted(available_commands))}"
            
        # Utiliser une commande personnalisée si disponible, sinon utiliser une commande prédéfinie
        if cmd_name in self.config.get("custom_commands", {}):
            cmd_template = self.config["custom_commands"][cmd_name]
        else:
            cmd_template = QUICK_COMMANDS[cmd_name]
            
        # Remplacement des paramètres dans le modèle de commande
        if "{" in cmd_template and "}" in cmd_template:
            # Extraire les noms des paramètres du modèle
            param_names = re.findall(r'\{([^}]+)\}', cmd_template)
            
            # Vérifier si nous avons suffisamment d'arguments
            if len(args) < len(param_names):
                return f"Erreur: La commande '{cmd_name}' nécessite les paramètres suivants: {', '.join(param_names)}"
                
            # Créer un dictionnaire des paramètres
            params = {}
            for i, name in enumerate(param_names):
                if i < len(args):
                    params[name] = args[i]
                    
            # Remplacer les paramètres dans le modèle
            try:
                cmd = cmd_template.format(**params)
            except KeyError as e:
                return f"Erreur: Paramètre manquant: {e}"
        else:
            # Pas de paramètres à remplacer
            cmd = cmd_template
            
        # Exécuter la commande
        return self.execute_command(cmd)
        
    def execute_devops_tool(self, tool_name, *args):
        """Exécute un outil DevOps intégré"""
        try:
            if tool_name == "monitor_ressources":
                # Surveiller les ressources système
                duration = int(args[0]) if args else 5  # Durée par défaut: 5 secondes
                return self.devops_tools.monitor_ressources(duration=duration)
                
            elif tool_name == "analyze_logs":
                # Analyser un fichier de logs
                if not args:
                    return "Erreur: Veuillez spécifier un fichier de logs"
                    
                log_file = args[0]
                pattern = args[1] if len(args) > 1 else None
                tail_param = None
                
                # Vérifier si on a un paramètre tail
                if len(args) > 2 and args[2].startswith("tail="):
                    try:
                        tail_param = int(args[2].split("=")[1])
                    except (ValueError, IndexError):
                        return "Erreur: Format incorrect pour le paramètre tail (exemple: tail=100)"
                
                return self.devops_tools.analyze_logs(log_file, pattern, tail_param)
                
            elif tool_name == "docker_info":
                # Informations Docker
                return self.devops_tools.docker_info()
                
            elif tool_name == "k8s_info":
                # Informations Kubernetes
                return self.devops_tools.k8s_info()
                
            elif tool_name == "network_scan":
                # Scan réseau
                if not args:
                    return "Erreur: Veuillez spécifier une cible (ex: 192.168.1.1)"
                    
                target = args[0]
                return self.devops_tools.network_scan(target)
                
            elif tool_name == "generate_ssl_cert":
                # Générer un certificat SSL
                if not args:
                    return "Erreur: Veuillez spécifier un nom de domaine"
                    
                domain = args[0]
                output_dir = args[1] if len(args) > 1 else None
                return self.devops_tools.generate_ssl_cert(domain, output_dir)
                
            else:
                available_tools = ["monitor_ressources", "analyze_logs", "docker_info", "k8s_info", "network_scan", "generate_ssl_cert"]
                return f"Erreur: Outil '{tool_name}' non reconnu. Outils disponibles: {', '.join(available_tools)}"
                
        except Exception as e:
            logging.error(f"Erreur lors de l'exécution de l'outil DevOps {tool_name}: {str(e)}")
            return f"Erreur lors de l'exécution de l'outil DevOps {tool_name}: {str(e)}"
            
    def call_mistral_api(self, user_message):
        """Appelle l'API Mistral pour obtenir une réponse"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        # Préparer les messages pour l'API
        messages = [
            {"role": "system", "content": self.system_message}
        ]
        
        # Ajouter l'historique de conversation
        for entry in self.conversation_history:
            messages.append(entry)
            
        # Ajouter le message de l'utilisateur
        messages.append({"role": "user", "content": user_message})
        
        payload = {
            "model": MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(API_URL, headers=headers, json=payload)
            
            if response.status_code == 200:
                response_data = response.json()
                if self.debug:
                    print(json.dumps(response_data, indent=2))
                    
                assistant_message = response_data['choices'][0]['message']['content']
                
                # Mettre à jour l'historique de conversation
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": assistant_message})
                
                # Limiter la taille de l'historique
                if len(self.conversation_history) > MAX_HISTORY_ENTRIES * 2:
                    self.conversation_history = self.conversation_history[-MAX_HISTORY_ENTRIES * 2:]
                    
                return assistant_message
            else:
                error_message = f"Erreur API ({response.status_code}): {response.text}"
                logging.error(error_message)
                return f"Erreur lors de l'appel à l'API Mistral: {error_message}"
        except Exception as e:
            logging.error(f"Exception lors de l'appel à l'API: {str(e)}")
            return f"Erreur de connexion à l'API Mistral: {str(e)}"

    def process_response(self, response):
        """Traite la réponse de l'API pour exécuter des commandes ou créer des scripts"""
        # Rechercher les commandes à exécuter
        exec_pattern = r"\[EXEC\](.*?)\[\/EXEC\]"
        script_pattern = r"\[SCRIPT\s+(\w+)\s+([^\]]+)\](.*?)\[\/SCRIPT\]"
        template_pattern = r"\[TEMPLATE\s+(\w+)\s+([^\]]+)\]"
        quickcmd_pattern = r"\[QUICKCMD\s+(\w+)(?:\s+([^\]]+))?\]"
        devops_pattern = r"\[DEVOPS\s+(\w+)(?:\s+([^\]]+))?\]"
        
        # Exécution des commandes
        for match in re.finditer(exec_pattern, response, re.DOTALL):
            command = match.group(1).strip()
            result = self.execute_command(command)
            
            if HAS_RICH:
                self.console.print("\n[bold green]Commande:[/bold green]")
                self.console.print(Syntax(command, "bash"))
                self.console.print("\n[bold green]Résultat:[/bold green]")
                
                # Détection du type de contenu pour un affichage adapté
                if re.search(r'^\s*<\?xml|^\s*<html|^\s*<!DOCTYPE', result, re.IGNORECASE):
                    # Contenu XML/HTML
                    self.console.print(Syntax(result, "xml"))
                elif re.search(r'^\s*\{|\}\s*', result) and '":' in result:
                    # Contenu JSON potentiel
                    try:
                        formatted_json = json.dumps(json.loads(result), indent=2)
                        self.console.print(Syntax(formatted_json, "json"))
                    except:
                        self.console.print(result)
                elif command.startswith("ls") and not command.endswith("| grep"):
                    # Résultat de ls - affichage en colonnes
                    files = result.strip().split("\n")
                    # Créer un tableau avec Rich
                    from rich.table import Table
                    table = Table(show_header=False, box=None)
                    # Diviser en colonnes (ajuster selon la largeur du terminal)
                    col_count = 3
                    for i in range(0, len(files), col_count):
                        row = files[i:i+col_count]
                        while len(row) < col_count:  # Padding
                            row.append("")
                        table.add_row(*row)
                    self.console.print(table)
                else:
                    self.console.print(result)
            else:
                print(f"\nCommande: {command}")
                print(f"Résultat: {result}")
        
        # Création de scripts
        for match in re.finditer(script_pattern, response, re.DOTALL):
            script_type = match.group(1).strip()
            script_name = match.group(2).strip()
            script_content = match.group(3).strip()
            
            filepath = self.save_script(script_type, script_name, script_content)
            
            if HAS_RICH:
                self.console.print(f"\n[bold green]Script {script_type} créé:[/bold green] {filepath}")
                self.console.print(Syntax(script_content, script_type.lower()))
                
                # Demander si l'utilisateur veut exécuter le script
                if script_type.lower() in ["bash", "shell", "python", "sh", "py"]:
                    if Confirm.ask("Voulez-vous exécuter ce script maintenant?"):
                        if script_type.lower() in ["python", "py"]:
                            cmd = f"python3 {filepath}"
                        else:
                            cmd = filepath
                            
                        result = self.execute_command(cmd)
                        self.console.print("\n[bold green]Résultat de l'exécution:[/bold green]")
                        self.console.print(result)
            else:
                print(f"\nScript {script_type} créé: {filepath}")
                print(f"\n--- Début du script ---\n{script_content}\n--- Fin du script ---")
                
                # Demander si l'utilisateur veut exécuter le script
                if script_type.lower() in ["bash", "shell", "python", "sh", "py"]:
                    if input("Voulez-vous exécuter ce script maintenant? [o/N] ").lower() == 'o':
                        if script_type.lower() in ["python", "py"]:
                            cmd = f"python3 {filepath}"
                        else:
                            cmd = filepath
                            
                        result = self.execute_command(cmd)
                        print(f"\nRésultat de l'exécution:\n{result}")
                        
        # Création à partir de modèles
        for match in re.finditer(template_pattern, response, re.DOTALL):
            template_type = match.group(1).strip()
            filename = match.group(2).strip()
            
            result = self.create_from_template(template_type, filename)
            
            if HAS_RICH:
                self.console.print(f"\n[bold green]Utilisation du modèle {template_type}:[/bold green]")
                self.console.print(result)
            else:
                print(f"\nUtilisation du modèle {template_type}: {result}")
                
        # Exécution de commandes rapides
        for match in re.finditer(quickcmd_pattern, response, re.DOTALL):
            cmd_name = match.group(1).strip()
            args = match.group(2).strip().split() if match.group(2) else []
            
            result = self.execute_quick_command(cmd_name, *args)
            
            if HAS_RICH:
                self.console.print(f"\n[bold green]Commande rapide '{cmd_name}':[/bold green]")
                self.console.print(result)
            else:
                print(f"\nCommande rapide '{cmd_name}':")
                print(result)
                
        # Exécution des outils DevOps
        for match in re.finditer(devops_pattern, response, re.DOTALL):
            tool_name = match.group(1).strip()
            args = match.group(2).strip().split() if match.group(2) else []
            
            result = self.execute_devops_tool(tool_name, *args)
            
            if HAS_RICH:
                self.console.print(f"\n[bold blue]Outil DevOps '{tool_name}':[/bold blue]")
                self.console.print(result)
            else:
                print(f"\nOutil DevOps '{tool_name}':")
                print(result)
        
        # Afficher le texte normal (sans les tags spéciaux)
        clean_response = re.sub(exec_pattern, "", response)
        clean_response = re.sub(script_pattern, "", clean_response)
        clean_response = re.sub(template_pattern, "", clean_response)
        clean_response = re.sub(quickcmd_pattern, "", clean_response)
        clean_response = re.sub(devops_pattern, "", clean_response)
        clean_response = clean_response.strip()
        
        if clean_response:
            if HAS_RICH:
                self.console.print(Panel(clean_response, border_style="cyan", box=box.ROUNDED))
            else:
                print(f"\n{clean_response}\n")