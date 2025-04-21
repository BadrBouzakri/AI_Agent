import datetime
import os
import logging
import time
from typing import List, Dict, Any

# Define missing constants
TASKS_DIR = '/path/to/tasks'  # Replace with the actual path
APP_NAME = 'MistralAgentDevops'

# Define a placeholder for SystemInfo class
class SystemInfo:
    @staticmethod
    def get_full_system_info():
        return {
            "os": {},
            "cpu": {},
            "memory": {},
            "network": {},
            "disks": [],
            "services": [],
            "containers": []
        }

class DevOpsAgent:
    def __init__(self):
        self.config = {}
        self.system_info = {}
        self.templates = {}
        self.history = []
        self.model = "default"

    def select_commands(self, commands, checked_commands, choice):
        confirmation = ""
        if self.config.get("safe_mode", True) and any(cmd[1] for cmd in checked_commands):
            print("\n⚠️ ATTENTION: Certaines commandes sont potentiellement dangereuses! ⚠️")
            confirmation = input("Êtes-vous sûr de vouloir exécuter TOUTES ces commandes? (tapez 'CONFIRMER' pour continuer): ")

        if not self.config.get("safe_mode", True) or confirmation == "CONFIRMER" or not any(cmd[1] for cmd in checked_commands):
            return commands
        else:
            print("Exécution annulée.")
            return []

        try:
            indices = [int(x) for x in choice.split()]
            selected = []

            for idx in indices:
                if 1 <= idx <= len(commands):
                    selected.append(commands[idx-1])
                else:
                    print(f"Erreur: Le numéro {idx} est hors limites.")

            if selected:
                dangerous_selected = []
                if self.config.get("check_commands", True):
                    for i, cmd in enumerate(selected):
                        idx = commands.index(cmd)
                        if checked_commands[idx][1]:
                            dangerous_selected.append((cmd, checked_commands[idx][2]))

                print("\nCommandes sélectionnées:")
                for cmd in selected:
                    print(f"- {cmd}")

                confirmation = "oui"
                if dangerous_selected and self.config.get("safe_mode", True):
                    print("\n⚠️ ATTENTION: Les commandes suivantes sont potentiellement dangereuses:")
                    for cmd, reason in dangerous_selected:
                        print(f"- {cmd} ({reason})")
                    confirmation = input("\nÊtes-vous sûr de vouloir exécuter ces commandes? (oui/non): ").lower()
                else:
                    confirmation = input("\nConfirmer l'exécution? (oui/non): ").lower()

                if confirmation in ("oui", "o", "yes", "y"):
                    return selected

            return []

        except ValueError:
            try:
                idx = int(choice)
                if 1 <= idx <= len(commands):
                    selected = commands[idx-1]

                    warning = ""
                    if self.config.get("check_commands", True) and checked_commands[idx-1][1]:
                        warning = f"\n⚠️ ATTENTION: {checked_commands[idx-1][2]}"

                    confirm = input(f"\nConfirmer l'exécution de: \n[{selected}]{warning}\n(oui/non): ").lower()
                    return [selected] if confirm in ("oui", "o", "yes", "y") else []
                else:
                    print(f"Erreur: Le numéro {idx} est hors limites.")
            except ValueError:
                print("Entrée invalide. Veuillez utiliser les options proposées.")

    def save_script(self, filename: str, content: str) -> str:
        """Sauvegarde un script dans le répertoire tasks."""
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"script_{timestamp}.sh"
        
        # Assurer une extension appropriée
        if not any(filename.endswith(ext) for ext in ['.sh', '.py', '.pl', '.rb']):
            filename += '.sh'
        
        file_path = os.path.join(TASKS_DIR, filename)
        
        try:
            with open(file_path, "w") as f:
                f.write(content)
            
            # Rendre le fichier exécutable si c'est un script shell
            if filename.endswith(('.sh', '.py', '.pl', '.rb')):
                os.chmod(file_path, 0o755)
            
            print(f"Script sauvegardé: {file_path}")
            return file_path
        except Exception as e:
            error_msg = f"Erreur lors de la sauvegarde du script: {e}"
            print(error_msg)
            logging.error(error_msg)
            return ""
    
    def detect_task_type(self, query: str) -> str:
        """Détecte automatiquement le type de tâche en fonction de la requête."""
        keywords = {
            "diagnostic": ["diagnostic", "problème", "erreur", "bug", "debug", "dépanner"],
            "maintenance": ["maintenance", "nettoyer", "mettre à jour", "upgrade", "update"],
            "docker": ["docker", "conteneur", "container", "image", "dockerfile", "podman"],
            "kubernetes": ["kubernetes", "k8s", "kubectl", "pod", "deployment", "service"],
            "network": ["réseau", "network", "ip", "route", "dns", "firewall", "port"],
            "monitoring": ["monitoring", "surveillance", "prometheus", "grafana", "alertes", "metrics"],
            "backup": ["backup", "sauvegarde", "archiver", "restore", "restaurer"],
            "script": ["script", "automatiser", "automation", "cron", "tâche planifiée"],
            "ansible": ["ansible", "playbook", "role", "inventory"],
            "terraform": ["terraform", "infrastructure", "iac", "aws", "cloud"],
            "ci_cd": ["ci", "cd", "pipeline", "jenkins", "gitlab", "github actions"],
            "security": ["security", "sécurité", "firewall", "ssl", "tls", "certificat"],
            "database": ["database", "base de données", "mysql", "postgresql", "mongodb", "redis"]
        }
        
        query_lower = query.lower()
        scores = {task_type: 0 for task_type in keywords}
        
        for task_type, words in keywords.items():
            for word in words:
                if word.lower() in query_lower:
                    scores[task_type] += 1
        
        # Trouver le type avec le score le plus élevé
        max_score = max(scores.values())
        if max_score > 0:
            # En cas d'égalité, prendre le premier
            for task_type, score in scores.items():
                if score == max_score:
                    return task_type
        
        # Aucun type spécifique détecté, utiliser le type par défaut
        return self.config.get("default_task_type", "general")
    
    def generate_system_prompt(self, task_type: str, query: str) -> str:
        """Génère un prompt système adapté au type de tâche."""
        if task_type in self.templates:
            template = self.templates[task_type]
        else:
            template = self.templates["general"]
        
        # Remplacer les variables dans le template
        prompt = template.format(
            query=query,
            os_type=self.os_type
        )
        
        # Ajouter des informations contextuelles
        system_context = f"Tu es un assistant spécialisé en administration système et DevOps sur {self.os_type}. "
        
        # Ajouter des informations spécifiques selon le type de tâche
        if task_type == "diagnostic":
            # Ajouter des informations système pertinentes pour le diagnostic
            system_context += "\nInformations système pertinentes:\n"
            system_context += f"- OS: {self.os_type}\n"
            if self.system_info["cpu"]:
                system_context += f"- CPU: {self.system_info['cpu'].get('physical_cores', 'N/A')} cœurs physiques\n"
            if self.system_info["memory"]:
                system_context += f"- Mémoire: {self.system_info['memory'].get('total_gb', 'N/A')} GB (Utilisé: {self.system_info['memory'].get('used_percent', 'N/A')}%)\n"
            
            # Ajouter les services en cours d'exécution
            if self.system_info["services"]:
                system_context += "- Services actifs: " + ", ".join(service["name"] for service in self.system_info["services"][:5]) + "\n"
            
            # Ajouter les conteneurs en cours d'exécution
            if self.system_info["containers"]:
                system_context += "- Conteneurs actifs: " + ", ".join(container["name"] for container in self.system_info["containers"][:5]) + "\n"
        
        elif task_type in ["docker", "kubernetes"]:
            # Ajouter des informations sur les conteneurs en cours d'exécution
            if self.system_info["containers"]:
                system_context += "\nConteneurs actifs:\n"
                for container in self.system_info["containers"][:5]:
                    system_context += f"- {container['name']} ({container['image']})\n"
        
        elif task_type == "network":
            # Ajouter des informations réseau
            if self.system_info["network"]:
                system_context += "\nInformations réseau:\n"
                system_context += f"- Hostname: {self.system_info['network'].get('hostname', 'N/A')}\n"
                if "external_ip" in self.system_info["network"]:
                    system_context += f"- IP externe: {self.system_info['network']['external_ip']}\n"
                
                # Ajouter les interfaces réseau principales
                if "interfaces" in self.system_info["network"]:
                    for interface, info in list(self.system_info["network"]["interfaces"].items())[:3]:
                        addresses = [addr["address"] for addr in info.get("addresses", []) if "address" in addr]
                        if addresses:
                            system_context += f"- Interface {interface}: {', '.join(addresses)}\n"
        
        return system_context + "\n" + prompt
    
    def execute_commands(self, commands: List[str]) -> List[Dict[str, Any]]:
        """Exécute une liste de commandes et retourne les résultats."""
        results = []
        
        for cmd in commands:
            # Exécuter la commande
            start_time = time.time()
            success, stdout, stderr = self.run_shell_command(cmd)
            elapsed_time = time.time() - start_time
            
            # Enregistrer le résultat
            result = {
                "command": cmd,
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "execution_time": elapsed_time
            }
            
            # Ajouter à l'historique
            self._save_history({
                "type": "command",
                "command": cmd,
                "success": success,
                "timestamp": datetime.datetime.now().isoformat()
            })
            
            results.append(result)
        
        return results
    
    def analyze_results(self, query: str, results: List[Dict[str, Any]]) -> str:
        """Analyse les résultats des commandes et génère un rapport d'exécution."""
        if not results:
            return "Aucune commande exécutée."
        
        # Rassembler les informations pour l'analyse
        commands_data = []
        for result in results:
            commands_data.append({
                "command": result["command"],
                "success": result["success"],
                "output": result["stdout"],
                "error": result["stderr"],
                "execution_time": f"{result['execution_time']:.2f}s"
            })
        
        # Créer le prompt pour l'analyse
        analysis_prompt = (
            f"Analyse les résultats des commandes suivantes exécutées en réponse à cette requête: '{query}'\n\n"
            "Résultats des commandes:\n"
        )
        
        for i, data in enumerate(commands_data, 1):
            analysis_prompt += f"--- Commande {i} ---\n"
            analysis_prompt += f"$ {data['command']}\n"
            analysis_prompt += f"Statut: {'Succès' if data["success"] else 'Échec'} ({data['execution_time']})\n"
            
            if data["output"]:
                output_sample = data["output"]
                if len(output_sample) > 500:
                    output_sample = output_sample[:500] + "... (résultat tronqué)"
                analysis_prompt += f"Sortie: {output_sample}\n"
            
            if data["error"]:
                analysis_prompt += f"Erreur: {data['error']}\n"
            
            analysis_prompt += "\n"
        
        analysis_prompt += (
            "Fournir une analyse concise des résultats, en expliquant ce que les commandes ont fait, "
            "si elles ont réussi, et ce que signifient les sorties/erreurs importantes. "
            "Si des erreurs sont survenues, suggérer des solutions possibles. "
            "Résumer les actions accomplies et indiquer les prochaines étapes si nécessaire."
        )
        
        # Utiliser le LLM pour analyser les résultats
        system_context = (
            f"Tu es un assistant DevOps expert pour {self.os_type}. "
            "Tu analyses les résultats des commandes exécutées et fournit une explication claire et utile. "
            "Sois précis dans tes analyses et suggère des solutions concrètes aux problèmes identifiés."
        )
        
        analysis = self.ask_llm(analysis_prompt, system_context)
        return analysis
    
    def show_dashboard(self) -> None:
        """Affiche un tableau de bord système."""
        # Mettre à jour les informations système
        self.system_info = SystemInfo.get_full_system_info()
        
        print("\n" + "=" * 60)
        print(f"{APP_NAME} - TABLEAU DE BORD SYSTÈME")
        print("=" * 60)
        
        # Informations OS
        os_info = self.system_info["os"]
        print(f"\n📊 SYSTÈME: {os_info.get('system', 'Inconnu')} {os_info.get('release', '')}")
        if "distribution" in os_info:
            print(f"   Distribution: {os_info.get('distribution', '')} {os_info.get('dist_version', '')}")
        print(f"   Hostname: {self.system_info['network'].get('hostname', 'Inconnu')}")
        if "external_ip" in self.system_info["network"]:
            print(f"   IP Externe: {self.system_info['network']['external_ip']}")
        
        # Informations CPU/Mémoire
        cpu_info = self.system_info["cpu"]
        mem_info = self.system_info["memory"]
        
        if cpu_info:
            print(f"\n💻 RESSOURCES:")
            print(f"   CPU: {cpu_info.get('physical_cores', 'N/A')} cœurs ({cpu_info.get('usage_percent', 'N/A')}% utilisé)")
        
        if mem_info:
            print(f"   RAM: {mem_info.get('total_gb', 'N/A')} GB total, {mem_info.get('used_percent', 'N/A')}% utilisé")
            print(f"   Swap: {mem_info.get('swap_total_gb', 'N/A')} GB total, {mem_info.get('swap_used_percent', 'N/A')}% utilisé")
        
        # Disques
        if self.system_info["disks"]:
            print("\n💾 STOCKAGE:")
            for disk in self.system_info["disks"][:5]:  # Limiter aux 5 premiers disques
                print(f"   {disk.get('mountpoint', 'Inconnu')}: {disk.get('total_gb', 'N/A')} GB total, {disk.get('used_percent', 'N/A')}% utilisé")
        
        # Conteneurs
        if self.system_info["containers"]:
            print("\n🐳 CONTENEURS ACTIFS:")
            for container in self.system_info["containers"][:5]:  # Limiter aux 5 premiers conteneurs
                print(f"   {container.get('name', 'Inconnu')} ({container.get('image', 'Inconnu')})")
        
        # Services
        if self.system_info["services"]:
            print("\n🔧 SERVICES ACTIFS:")
            services_str = ", ".join(service["name"] for service in self.system_info["services"][:10])
            print(f"   {services_str}")
        
        # Modèle et stats
        print("\n🤖 AGENT:")
        print(f"   Modèle: {self.model}")
        print(f"   Commandes exécutées: {len([h for h in self.history if h.get('type') == 'command'])}")
        print(f"   Safe Mode: {'Activé' if self.config.get('safe_mode', True) else 'Désactivé'}")
        
        print("\n" + "=" * 60)
        print("Tapez '!help' pour afficher les commandes disponibles.\n")
    
    def show_help(self) -> None:
        """Affiche l'aide avec les commandes disponibles."""
        print("\n" + "=" * 60)
        print(f"{APP_NAME} - AIDE")
        print("=" * 60)
        print("\nCommandes système:")
        print("  !help     - Affiche cette aide")
        print("  !info     - Affiche le tableau de bord système")
        print("  !history  - Affiche l'historique des commandes")
        print("  !config   - Affiche/modifie la configuration")
        print("  !model X  - Change le modèle LLM (ex: !model llama3)")
        print("  !safe X   - Active/désactive le mode sécurisé (ex: !safe off)")
        print("  !script X - Sauvegarde un script (ex: !script backup.sh)")
        print("  !run X    - Exécute un script sauvegardé (ex: !run backup.sh)")
        print("  !task X   - Spécifie le type de tâche (ex: !task docker)")
        print("  !exit     - Quitte l'application")
        
        print("\nTypes de tâches disponibles:")
        task_types = sorted(self.templates.keys())
        print("  " + ", ".join(task_types))
        
        print("\nExemples d'utilisation:")
        print("  > Vérifier l'espace disque disponible")
        print("  > !task docker")
        print("  > Lister tous les conteneurs et les nettoyer")
        print("  > !script backup.sh Créer un script de backup pour /var/www")
        print("  > !safe off")
        print("  > Redémarrer le service nginx et vider les logs")
        
        print("\n" + "=" * 60)
    
    def show_history(self, count: int = 10) -> None:
        """Affiche l'historique des commandes."""
        if not self.history:
            print("L'historique est vide.")
            return
        
        print("\n=== Historique des commandes ===")
        
        # Filtrer pour n'afficher que les commandes
        command_history = [h for h in self.history if h.get("type") == "command"]
        
        # Afficher les dernières commandes
        for i, entry in enumerate(command_history[-count:], 1):
            timestamp = entry.get("timestamp", "")
            if timestamp:
                try:
                    dt = datetime.datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            status = "✅" if entry.get("success", False) else "❌"
            print(f"{i}. [{timestamp}] {status} {entry.get('command', 'N/A')}")
    
    def edit_config(self, key: str = None, value: str = None) -> None:
        """Affiche ou modifie la configuration."""
        if key is None:
            # Afficher la configuration actuelle
            print("\n=== Configuration actuelle ===")
            for k, v in self.config.items():
                print(f"{k}: {v}")
            
            # Proposer des modifications
            print("\nPour modifier un paramètre, utilisez: !config [clé] [valeur]")
            print("Exemple: !config safe_mode False")
            return
        
        # Modifier un paramètre
        if key not in self.config:
            print(f"Erreur: Paramètre '{key}' inconnu.")
            return
        
        # Convertir la valeur au type approprié
        original_value = self.config[key]
        
        if value is None:
            print(f"Valeur actuelle de '{key}': {original_value}")
            return
        
        try:
            # Convertir au type d'origine
            if isinstance(original_value, bool):
                converted_value = value.lower() in ("true", "yes", "y", "1", "on")
            elif isinstance(original_value, int):
                converted_value = int(value)
            elif isinstance(original_value, float):
                converted_value = float(value)
            elif isinstance(original_value, list):
                # Séparer par des virgules
                converted_value = [item.strip() for item in value.split(",")]
            else:
                converted_value = value
            
            # Mettre à jour la configuration
            self.config[key] = converted_value
            self._save_config()
            
            print(f"Configuration mise à jour: {key} = {converted_value}")
            
            # Mettre à jour les variables spécifiques si nécessaire
            if key == "model":
                self.model = converted_value
            
        except Exception as e:
            print(f"Erreur lors de la modification de la configuration: {e}")
    
    def main(self) -> None:
        """Fonction principale du programme."""
        print("\n" + "=" * 60)
        print(f"Bienvenue dans {APP_NAME} - Votre assistant DevOps")
        print("=" * 60)
        print(f"\nOS détecté: {self.os_type}")
        print(f"Modèle LLM: {self.model}")
        print("\nUtilisez '!help' pour afficher les commandes disponibles.")
        print("Pour commencer, décrivez simplement la tâche que vous souhaitez accomplir.")
        
        current_task_type = self.config.get("default_task_type", "general")
        
        while True:
            try:
                # Afficher le type de tâche actuel dans le prompt
                task_indicator = f"[{current_task_type}]" if current_task_type != "general" else ""
                user_input = input(f"\n🔍 {task_indicator} Que voulez-vous faire ? (!help, !exit) : ").strip()
                
                if not user_input:
                    continue
                
                # Commandes spéciales
                if user_input.startswith("!"):
                    parts = user_input.split(maxsplit=2)
                    command = parts[0].lower()
                    arg1 = parts[1] if len(parts) > 1 else None
                    arg2 = parts[2] if len(parts) > 2 else None
                    
                    if command in ("!exit", "!quit"):
                        print("Au revoir!")
                        break
                    
                    elif command == "!help":
                        self.show_help()
                        continue
                    
                    elif command == "!info":
                        self.show_dashboard()
                        continue
                    
                    elif command == "!history":
                        count = 10
                        if arg1 and arg1.isdigit():
                            count = int(arg1)
                        self.show_history(count)
                        continue
                    
                    elif command == "!config":
                        self.edit_config(arg1, arg2)
                        continue
                    
                    elif command == "!model":
                        if arg1:
                            self.model = arg1
                            self.config["model"] = arg1
                            self._save_config()
                            print(f"Modèle changé pour: {self.model}")
                        else:
                            print(f"Modèle actuel: {self.model}")
                        continue
                    
                    elif command == "!safe":
                        if arg1 in ("on", "true", "yes", "1"):
                            self.config["safe_mode"] = True
                            self._save_config()
                            print("Mode sécurisé activé.")
                        elif arg1 in ("off", "false", "no", "0"):
                            self.config["safe_mode"] = False
                            self._save_config()
                            print("Mode sécurisé désactivé. Soyez prudent!")
                        else:
                            status = "activé" if self.config.get("safe_mode", True) else "désactivé"
                            print(f"Mode sécurisé: {status}")
                        continue
                    
                    elif command == "!task":
                        if arg1 and arg1 in self.templates:
                            current_task_type = arg1
                            print(f"Type de tâche changé pour: {current_task_type}")
                        elif arg1:
                            print(f"Type de tâche '{arg1}' non reconnu. Types disponibles:")
                            print(", ".join(sorted(self.templates.keys())))
                        else:
                            print(f"Type de tâche actuel: {current_task_type}")
                            print("Types disponibles:")
                            print(", ".join(sorted(self.templates.keys())))
                        continue
                    
                    elif command == "!script":
                        if not arg1:
                            print("Erreur: Nom de fichier requis. Usage: !script nom_fichier [description]")
                            continue
                        
                        script_description = arg2 if arg2 else input("Description du script à générer: ")
                        
                        script_prompt = (
                            f"Écris un script Bash ou Python pour: {script_description}\n\n"
                            "Le script doit être complet, robuste, avec gestion d'erreurs et bien commenté. "
                            "Ajoutez une section d'aide et la gestion des arguments si nécessaire."
                        )
                        
                        system_context = (
                            f"Tu es un expert en scripting pour {self.os_type}. "
                            "Tu crées des scripts complets et professionnels. "
                            "Assure-toi d'inclure des commentaires, la gestion des erreurs et une documentation."
                        )
                        
                        print(f"\nGénération du script '{arg1}'...")
                        script_content = self.ask_llm(script_prompt, system_context)
                        
                        if script_content:
                            # Nettoyer le contenu (retirer balises markdown, etc.)
                            if "```" in script_content:
                                script_parts = script_content.split("```")
                                if len(script_parts) >= 3:
                                    # Extraire le contenu entre les balises de code
                                    script_content = script_parts[1]
                                    # Supprimer le langage de la première ligne si présent
                                    if script_content.startswith(("bash", "python", "sh")):
                                        script_content = script_content.split("\n", 1)[1]
                            
                            # Enregistrer le script
                            script_path = self.save_script(arg1, script_content)
                            
                            if script_path:
                                print(f"Script créé: {script_path}")
                                print("Pour exécuter: !run " + os.path.basename(script_path))
                        
                        continue
                    
                    elif command == "!run":
                        if not arg1:
                            # Lister les scripts disponibles
                            scripts = [f for f in os.listdir(TASKS_DIR) if f.endswith(('.sh', '.py', '.pl', '.rb'))]
                            if scripts:
                                print("Scripts disponibles:")
                                for script in scripts:
                                    print(f"- {script}")
                                print("\nPour exécuter: !run nom_script")
                            else:
                                print("Aucun script disponible. Utilisez !script pour en créer un.")
                            continue
                        
                        script_path = os.path.join(TASKS_DIR, arg1)
                        if not os.path.exists(script_path):
                            # Essayer avec l'extension .sh
                            if not arg1.endswith(('.sh', '.py', '.pl', '.rb')):
                                script_path = os.path.join(TASKS_DIR, arg1 + '.sh')
                        
                        if os.path.exists(script_path):
                            print(f"Exécution du script: {script_path}")
                            
                            # Déterminer comment exécuter le script
                            cmd = ""
                            if script_path.endswith('.py'):
                                cmd = f"python3 {script_path}"
                            elif script_path.endswith('.sh'):
                                cmd = f"bash {script_path}"
                            elif script_path.endswith('.pl'):
                                cmd = f"perl {script_path}"
                            elif script_path.endswith('.rb'):
                                cmd = f"ruby {script_path}"
                            else:
                                cmd = script_path  # Exécution directe
                            
                            # Exécuter avec les arguments additionnels s'il y en a
                            if arg2:
                                cmd += f" {arg2}"
                            
                            success, stdout, stderr = self.run_shell_command(cmd)
                            
                            # Enregistrer dans l'historique
                            self._save_history({
                                "type": "script",
                                "script": arg1,
                                "command": cmd,
                                "success": success,
                                "timestamp": datetime.datetime.now().isoformat()
                            })
                        else:
                            print(f"Erreur: Script '{arg1}' introuvable.")
                        
                        continue
                
                # Traitement des demandes normales
                # Détecter automatiquement le type de tâche si ce n'est pas déjà spécifié
                if current_task_type == "general":
                    detected_type = self.detect_task_type(user_input)
                    if detected_type != "general":
                        print(f"Type de tâche détecté: {detected_type}")
                        current_task_type = detected_type
                
                # Générer le prompt système adapté au type de tâche
                system_prompt = self.generate_system_prompt(current_task_type, user_input)
                
                # Demander au LLM de générer des commandes
                print(f"\nRecherche de solutions pour: {user_input}")
                command_output = self.ask_llm(user_input, system_prompt)
                
                if not command_output:
                    print("Aucune commande suggérée.")
                    continue
                
                print("\n=== Solution(s) suggérée(s) ===")
                print(command_output)
                
                # Nettoyer et extraire les commandes
                commands = self.clean_command_output(command_output)
                
                if not commands:
                    # Peut-être que c'est un script ou quelque chose qui n'est pas une commande
                    if "```" in command_output and len(command_output) > 100:
                        # Semble être un script, proposer de le sauvegarder
                        print("\nLe modèle a généré ce qui semble être un script.")
                        save_option = input("Voulez-vous enregistrer ce contenu comme un script? (oui/non): ").lower()
                        
                        if save_option in ("oui", "o", "yes", "y"):
                            filename = input("Nom du fichier pour sauvegarder le script: ")
                            
                            # Extraire le contenu du script
                            script_content = command_output
                            if "```" in command_output:
                                script_parts = command_output.split("```")
                                if len(script_parts) >= 3:
                                    # Extraire le contenu entre les balises de code
                                    script_content = script_parts[1]
                                    # Supprimer le langage de la première ligne si présent
                                    if script_content.startswith(("bash", "python", "sh")):
                                        script_content = script_content.split("\n", 1)[1]
                            
                            script_path = self.save_script(filename, script_content)
                            if script_path:
                                print(f"Script sauvegardé: {script_path}")
                    else:
                        print("Aucune commande valide n'a été extraite.")
                    
                    continue
                
                # Sélection et exécution des commandes
                selected_commands = self.select_commands(commands)
                
                if selected_commands:
                    print("\n=== Exécution en cours ===")
                    results = self.execute_commands(selected_commands)
                    
                    # Analyser les résultats
                    if self.config.get("analyze_results", True):
                        print("\n=== Analyse des résultats ===")
                        analysis = self.analyze_results(user_input, results)
                        print(analysis)
                else:
                    print("Aucune commande n'a été exécutée.")
                
                # Réinitialiser au type général pour la prochaine requête?
                if current_task_type != self.config.get("default_task_type", "general"):
                    reset = input("\nRéinitialiser le type de tâche pour la prochaine requête? (oui/non): ").lower()
                    if reset in ("oui", "o", "yes", "y"):
                        current_task_type = self.config.get("default_task_type", "general")
                        print(f"Type de tâche réinitialisé à: {current_task_type}")
                    
            except KeyboardInterrupt:
                print("\nOpération annulée.")
            except Exception as e:
                print(f"Erreur inattendue: {e}")
                logging.error(f"Erreur inattendue: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        agent = DevOpsAgent()
        agent.main()
    except KeyboardInterrupt:
        print("\n\nFermeture du programme.")
    except Exception as e:
        print(f"Erreur critique: {e}")
        logging.error(f"Erreur critique: {e}", exc_info=True)