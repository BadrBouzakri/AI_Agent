#!/bin/bash

# Script d'installation pour l'agent Mistral IA
# Ce script installe les dépendances nécessaires et configure l'agent Mistral

set -e

# Fonction pour afficher des messages colorés
print_message() {
    local color=$1
    local message=$2
    case $color in
        "green") echo -e "\033[0;32m$message\033[0m" ;;
        "blue") echo -e "\033[0;34m$message\033[0m" ;;
        "yellow") echo -e "\033[0;33m$message\033[0m" ;;
        "red") echo -e "\033[0;31m$message\033[0m" ;;
        *) echo "$message" ;;
    esac
}

print_message "blue" "🤖 Installation de l'agent Mistral IA..."

# Vérifier si Python est installé
if ! command -v python3 &> /dev/null; then
    print_message "yellow" "❌ Python 3 n'est pas installé. Installation en cours..."
    sudo apt update
    sudo apt install -y python3 python3-pip
else
    print_message "green" "✅ Python 3 est déjà installé"
fi

# Créer les répertoires principaux pour l'agent
AGENT_DIR="$HOME/.mistral_agent"
SCRIPTS_DIR="$HOME/tech/scripts"
LOG_DIR="$AGENT_DIR/logs"
CONFIG_DIR="$AGENT_DIR/config"

# Créer tous les répertoires nécessaires
mkdir -p "$AGENT_DIR"
mkdir -p "$SCRIPTS_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$CONFIG_DIR"

print_message "blue" "📁 Création de l'environnement virtuel..."
python3 -m venv "$AGENT_DIR/venv"
source "$AGENT_DIR/venv/bin/activate"

# Installer les dépendances
print_message "blue" "📦 Installation des dépendances..."
pip install rich typer requests click prompt_toolkit colorama

# Configurer l'agent
print_message "blue" "📝 Configuration de l'agent..."
cp mistral_agent.py "$AGENT_DIR/"
chmod +x "$AGENT_DIR/mistral_agent.py"

# Déterminer le shell de l'utilisateur
SHELL_CONFIG="$HOME/.bashrc"
if [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
fi

# Vérifier si l'alias existe déjà
if ! grep -q "alias mistral=" "$SHELL_CONFIG"; then
    print_message "blue" "🔧 Ajout de l'alias 'mistral' à $SHELL_CONFIG..."
    echo "" >> "$SHELL_CONFIG"
    echo "# Agent Mistral IA" >> "$SHELL_CONFIG"
    echo "alias mistral='$AGENT_DIR/venv/bin/python3 $AGENT_DIR/mistral_agent.py'" >> "$SHELL_CONFIG"
    echo 'export PATH="$PATH:$HOME/tech/scripts"' >> "$SHELL_CONFIG"
else
    print_message "green" "✅ L'alias 'mistral' existe déjà dans $SHELL_CONFIG"
fi

# Création du fichier d'exécution
cat > "$AGENT_DIR/run.sh" << 'EOF'
#!/bin/bash
source "$HOME/.mistral_agent/venv/bin/activate"
python3 "$HOME/.mistral_agent/mistral_agent.py" "$@"
EOF

chmod +x "$AGENT_DIR/run.sh"

# Créer un lien symbolique dans /usr/local/bin
print_message "blue" "🔗 Création d'un lien symbolique pour l'agent..."
if [ -w "/usr/local/bin" ]; then
    sudo ln -sf "$AGENT_DIR/run.sh" /usr/local/bin/mistral
else
    print_message "yellow" "⚠️ Impossible de créer le lien symbolique dans /usr/local/bin (besoin de droits sudo)"
    print_message "yellow" "   Vous pouvez utiliser l'alias 'mistral' après avoir rechargé votre shell"
fi

# Installation de la complétion shell
print_message "blue" "🔄 Installation de la complétion shell..."
if [[ "$SHELL" == *"bash"* ]]; then
    # Complétion pour Bash
    COMPLETION_DIR="$HOME/.bash_completion.d"
    mkdir -p "$COMPLETION_DIR"
    
    cat > "$COMPLETION_DIR/mistral" << 'EOF'
# Complétion Bash pour l'agent Mistral
_mistral_completions()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Commandes de base
    opts="help exit quit clear pwd cd set-prompt set-api-key save-context load-context list-contexts config theme alias history system-info"
    
    # Complétion contextuelle
    case "${prev}" in
        cd)
            # Complétion des répertoires
            COMPREPLY=( $(compgen -d -- "${cur}") )
            return 0
            ;;
        theme)
            # Complétion des thèmes
            COMPREPLY=( $(compgen -W "default dark light hacker" -- "${cur}") )
            return 0
            ;;
        config)
            # Complétion des sous-commandes de config
            COMPREPLY=( $(compgen -W "set get reset" -- "${cur}") )
            return 0
            ;;
        alias)
            # Complétion des sous-commandes d'alias
            COMPREPLY=( $(compgen -W "set remove reset" -- "${cur}") )
            return 0
            ;;
        history)
            # Complétion des sous-commandes d'history
            COMPREPLY=( $(compgen -W "clear" -- "${cur}") )
            return 0
            ;;
        *)
            ;;
    esac
    
    # Complétion générale
    COMPREPLY=( $(compgen -W "${opts}" -- "${cur}") )
    return 0
}

complete -F _mistral_completions mistral
EOF

    # Ajouter au .bashrc si nécessaire
    if ! grep -q "bash_completion.d/mistral" "$HOME/.bashrc"; then
        echo "" >> "$HOME/.bashrc"
        echo "# Complétion Mistral" >> "$HOME/.bashrc"
        echo "if [ -f $COMPLETION_DIR/mistral ]; then" >> "$HOME/.bashrc"
        echo "    . $COMPLETION_DIR/mistral" >> "$HOME/.bashrc"
        echo "fi" >> "$HOME/.bashrc"
    fi
    
    print_message "green" "✅ Complétion Bash installée"
    
elif [[ "$SHELL" == *"zsh"* ]]; then
    # Complétion pour Zsh
    ZSH_COMPLETION_DIR="$HOME/.zsh/completions"
    mkdir -p "$ZSH_COMPLETION_DIR"
    
    cat > "$ZSH_COMPLETION_DIR/_mistral" << 'EOF'
#compdef mistral

_mistral() {
    local -a commands
    commands=(
        'help:Affiche l\'aide'
        'exit:Quitter l\'agent'
        'quit:Quitter l\'agent'
        'clear:Effacer l\'écran'
        'pwd:Afficher le répertoire courant'
        'cd:Changer de répertoire'
        'set-prompt:Définir un nouveau prompt système'
        'set-api-key:Définir une nouvelle clé API'
        'save-context:Sauvegarder le contexte actuel'
        'load-context:Charger un contexte sauvegardé'
        'list-contexts:Lister les contextes sauvegardés'
        'config:Gérer la configuration'
        'theme:Gérer le thème'
        'alias:Gérer les alias'
        'history:Gérer l\'historique'
        'system-info:Afficher les informations système'
    )
    
    _arguments -C \
        "1: :{_describe 'command' commands}" \
        "*::arg:->args"
    
    case $line[1] in
        cd)
            _files -/
            ;;
        theme)
            _values 'theme' default dark light hacker
            ;;
        config)
            _values 'config_cmd' set get reset
            ;;
        alias)
            _values 'alias_cmd' set remove reset
            ;;
        history)
            _values 'history_cmd' clear
            ;;
    esac
}

_mistral
EOF

    # Vérifier si fpath contient déjà le répertoire
    if ! grep -q "fpath=($ZSH_COMPLETION_DIR" "$HOME/.zshrc"; then
        echo "" >> "$HOME/.zshrc"
        echo "# Complétion Mistral" >> "$HOME/.zshrc"
        echo "fpath=($ZSH_COMPLETION_DIR \$fpath)" >> "$HOME/.zshrc"
        echo "autoload -Uz compinit" >> "$HOME/.zshrc"
        echo "compinit" >> "$HOME/.zshrc"
    fi
    
    print_message "green" "✅ Complétion Zsh installée"
fi

print_message "green" ""
print_message "green" "✅ Installation terminée!"
print_message "green" "🚀 Pour démarrer l'agent, vous pouvez:"
print_message "green" "   1. Recharger votre shell avec 'source $SHELL_CONFIG' puis utiliser la commande 'mistral'"
print_message "green" "   2. Ou exécuter directement '$AGENT_DIR/run.sh'"
print_message "green" ""
print_message "blue" "Options disponibles:"
print_message "blue" "   --lang fr|en    : Définir la langue (français par défaut)"
print_message "blue" "   --debug         : Activer le mode debug"
print_message "blue" "   --scripts-dir   : Spécifier un dossier pour les scripts"
print_message "blue" "   --start-dir     : Définir le répertoire de démarrage"
print_message "blue" "   --theme         : Choisir un thème (default, dark, light, hacker)"
print_message "blue" "   --shell-completion : Installer la complétion shell"
print_message "blue" "   --long-prompt   : Utiliser un prompt système détaillé"
print_message "blue" ""
print_message "blue" "📋 Exemples:"
print_message "blue" "   mistral --lang en"
print_message "blue" "   mistral --start-dir ~/projets"
print_message "blue" "   mistral --theme dark"
print_message "blue" ""
print_message "blue" "🔍 Fonctionnalités avancées:"
print_message "blue" "   - Autocomplétion des commandes et chemins"
print_message "blue" "   - Gestion des alias personnalisés"
print_message "blue" "   - Sauvegarde et chargement de contextes"
print_message "blue" "   - Thèmes visuels personnalisables"
print_message "blue" "   - Support du streaming pour affichage progressif des réponses"

# Recharger le shell si possible
if [[ "$0" = "$BASH_SOURCE" ]]; then
    print_message "yellow" "Rechargement du shell..."
    exec "$SHELL"
fi