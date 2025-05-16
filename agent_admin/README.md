# Linux Admin Assistant

Un agent IA pour terminal, basé sur Python, utilisant Ollama avec le modèle qwen2.5-coder:7b, destiné à assister les administrateurs système Linux dans leurs tâches quotidiennes de support technique.

## Prérequis

- Python 3.9+
- Ollama installé et configuré
- Le modèle qwen2.5-coder:7b téléchargé via Ollama

## Installation

```bash
# Installer Ollama si nécessaire (voir https://ollama.ai)
# Télécharger le modèle
ollama pull qwen2.5-coder:7b

# Installer l'application
pip install -e .
```

## Utilisation

```bash
# Lancer l'assistant
linux-assistant

# Commandes disponibles dans l'interface
/ticket - Analyser un nouveau ticket
/alerte - Analyser une alerte Nagios
/wiki - Générer un wiki pour l'intervention en cours
/historique - Afficher l'historique de la session
/aide - Afficher l'aide et les commandes disponibles
```

## Configuration

Modifier le fichier `~/.config/linux-assistant/config.yaml` pour personnaliser le comportement de l'assistant.