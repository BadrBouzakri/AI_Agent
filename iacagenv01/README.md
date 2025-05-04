# IacAgent - Assistant IA CLI pour DevOps

IacAgent est un assistant IA en ligne de commande pour les professionnels DevOps, capable de générer de l'infrastructure as code (IaC), créer des fichiers et exécuter des commandes via des instructions en langage naturel, en utilisant l'API Mistral.

## Fonctionnalités

- 🤖 Interprétation d'instructions en langage naturel
- 📝 Génération de code Infrastructure as Code (Terraform, Ansible, Docker, K8s...)
- 🔄 Exécution de commandes shell
- 📂 Création et modification de fichiers système
- 🔍 Détection automatique du type d'infrastructure demandé
- 📊 Historique des interactions
- ⚠️ Mode "dry-run" pour validation avant exécution
- 🔒 Vérification de sécurité pour les commandes potentiellement dangereuses

## Prérequis

- Python 3.7 ou supérieur
- Linux (testé sur Debian/Ubuntu)
- Clé API Mistral

## Installation

1. Clonez ce dépôt ou téléchargez les fichiers source
2. Exécutez le script d'installation avec les droits d'utilisateur standard :

```bash
chmod +x install.sh
./install.sh
```

3. Suivez les instructions pour configurer votre clé API Mistral

## Utilisation

### En mode interactif

Lancez simplement la commande `iacagent` dans votre terminal :

```bash
iacagent
```

Puis saisissez vos instructions en langage naturel.

### En mode direct

Vous pouvez également utiliser IacAgent avec une commande directe :

```bash
iacagent "crée un fichier Terraform pour un bucket S3 avec versioning activé dans ~/projets/s3/main.tf"
```

### Options

- `--api-key KEY` : Spécifier directement la clé API
- `--dry-run` : Demander confirmation avant chaque action (recommandé pour les nouveaux utilisateurs)

## Exemples d'utilisation

### Génération de fichier Terraform

```
> crée un fichier Terraform pour un bucket S3 avec versioning activé dans ~/projets/s3/main.tf
```

### Ansible Playbook

```
> génère un playbook Ansible pour installer et configurer Nginx
```

### Docker Compose

```
> crée un docker-compose.yml pour une application WordPress avec MySQL
```

### Kubernetes

```
> écris un manifeste Kubernetes pour déployer 3 replicas d'une application Node.js avec un service LoadBalancer
```

## Configuration

Le fichier de configuration principal est situé dans `~/iacagent/config.json`. Vous pouvez également configurer votre clé API dans `~/iacagent/.env`.

## Logs et Historique

- Logs : `~/iacagent/iacagent.log`
- Historique des interactions : `~/iacagent/history.json`

## Service Systemd

Un service systemd utilisateur est installé, que vous pouvez activer avec :

```bash
systemctl --user enable iacagent
systemctl --user start iacagent
```

## Sécurité

IacAgent intègre plusieurs mesures de sécurité :

- Vérification des commandes potentiellement dangereuses
- Mode dry-run optionnel pour validation avant exécution
- Exécution en tant qu'utilisateur normal (pas de privilèges root)

## Limitations

- IacAgent nécessite une connexion internet pour fonctionner (API Mistral)
- La qualité des résultats dépend du modèle Mistral sous-jacent
- L'exécution de commandes de longue durée peut entraîner des timeouts

## Contribuer

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## Licence

Ce projet est sous licence MIT.