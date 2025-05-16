#!/bin/bash

# Script d'installation de Linux Admin Assistant

set -e

echo "Installation de Linux Admin Assistant..."

# Vérifier les prérequis
echo "Vérification des prérequis..."

# Vérifier Python
python_version=$(python3 --version 2>/dev/null | cut -d" " -f2)
if [[ -z "$python_version" ]]; then
    echo "ERREUR: Python 3 n'est pas installé. Veuillez installer Python 3.9 ou supérieur."
    exit 1
fi

major=$(echo $python_version | cut -d. -f1)
minor=$(echo $python_version | cut -d. -f2)
if [[ $major -lt 3 || ($major -eq 3 && $minor -lt 9) ]]; then
    echo "ERREUR: Python 3.9 ou supérieur est requis. Version détectée: $python_version"
    exit 1
fi

echo "Python version $python_version détectée."

# Vérifier pip
if ! command -v pip3 &> /dev/null; then
    echo "ERREUR: pip3 n'est pas installé. Veuillez installer pip pour Python 3."
    exit 1
fi

# Vérifier Ollama
if ! command -v ollama &> /dev/null; then
    echo "ATTENTION: Ollama n'est pas trouvé dans le PATH."
    echo "Voulez-vous installer Ollama maintenant? (o/n)"
    read -r install_ollama
    if [[ "$install_ollama" == "o" || "$install_ollama" == "O" ]]; then
        echo "Installation d'Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
    else
        echo "ATTENTION: Ollama est requis pour exécuter l'assistant. Veuillez l'installer manuellement."
        echo "Consultez https://ollama.com pour les instructions d'installation."
    fi
fi

# Télécharger le modèle qwen
if command -v ollama &> /dev/null; then
    echo "Vérification du modèle qwen2.5-coder:7b..."
    if ! ollama list | grep -q "qwen2.5-coder:7b"; then
        echo "Téléchargement du modèle qwen2.5-coder:7b..."
        ollama pull qwen2.5-coder:7b
    else
        echo "Le modèle qwen2.5-coder:7b est déjà installé."
    fi
fi

# Installer l'environnement virtuel Python (optionnel)
echo "Voulez-vous installer dans un environnement virtuel? (recommandé) (o/n)"
read -r use_venv
if [[ "$use_venv" == "o" || "$use_venv" == "O" ]]; then
    # Vérifier que venv est disponible
    if ! python3 -c "import venv" &> /dev/null; then
        echo "ERREUR: Le module 'venv' n'est pas disponible. Veuillez l'installer."
        exit 1
    fi
    
    # Créer et activer l'environnement virtuel
    echo "Création de l'environnement virtuel..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Environnement virtuel activé."
fi

# Installer les dépendances Python
echo "Installation des dépendances Python..."
pip3 install -r requirements.txt

# Installer le package
echo "Installation du package linux-assistant..."
pip3 install -e .

# Créer les répertoires de configuration et de logs
echo "Création des répertoires de l'application..."
mkdir -p ~/.config/linux-assistant
mkdir -p ~/.local/share/linux-assistant/logs
mkdir -p ~/.local/share/linux-assistant/sessions
mkdir -p ~/.local/share/linux-assistant/wikis

# Générer la configuration par défaut
if [ ! -f ~/.config/linux-assistant/config.yaml ]; then
    echo "Création du fichier de configuration par défaut..."
    cat > ~/.config/linux-assistant/config.yaml << EOF
ollama:
  model: qwen2.5-coder:7b
  base_url: http://localhost:11434
  timeout: 60
  max_tokens: 2048
ui:
  prompt: "🐧> "
  colors:
    info: blue
    warning: yellow
    error: red
    command: green
    explanation: cyan
behavior:
  step_by_step: true
  safety_checks: true
  session_history: true
  history_size: 100
logging:
  level: INFO
  file: ~/.local/share/linux-assistant/logs/assistant.log
EOF
fi

echo ""
echo "Installation terminée avec succès!"
echo ""
echo "Pour lancer l'assistant, exécutez:"
echo "  linux-assistant"
echo ""
echo "Si vous avez installé dans un environnement virtuel, activez-le d'abord avec:"
echo "  source venv/bin/activate"
echo ""
echo "Bonnes administrations système!"
