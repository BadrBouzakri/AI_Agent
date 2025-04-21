#!/bin/bash

# Script d'installation pour l'agent Mistral IA
# Ce script installe les dépendances nécessaires et configure l'agent Mistral

set -e

echo "🤖 Installation de l'agent Mistral IA..."

# Vérifier si Python est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé. Installation en cours..."
    sudo apt update
    sudo apt install -y python3 python3-pip
else
    echo "✅ Python 3 est déjà installé"
fi

# Créer un environnement virtuel pour l'agent
AGENT_DIR="$HOME/.mistral_agent"
mkdir -p "$AGENT_DIR"

echo "📁 Création de l'environnement virtuel..."
python3 -m venv "$AGENT_DIR/venv"
source "$AGENT_DIR/venv/bin/activate"

# Installer les dépendances
echo "📦 Installation des dépendances..."
pip install rich typer requests

# Créer le répertoire pour les scripts
SCRIPTS_DIR="$HOME/tech/scripts"
mkdir -p "$SCRIPTS_DIR"
echo "📁 Répertoire de scripts créé: $SCRIPTS_DIR"

# Copier le script principal
echo "📝 Configuration de l'agent..."
cp mistral_agent.py "$AGENT_DIR/"
chmod +x "$AGENT_DIR/mistral_agent.py"

# Créer un alias pour l'agent
SHELL_CONFIG="$HOME/.bashrc"
if [ -f "$HOME/.zshrc" ]; then
    SHELL_CONFIG="$HOME/.zshrc"
fi

# Vérifier si l'alias existe déjà
if ! grep -q "alias mistral=" "$SHELL_CONFIG"; then
    echo "🔧 Ajout de l'alias 'mistral' à $SHELL_CONFIG..."
    echo "" >> "$SHELL_CONFIG"
    echo "# Agent Mistral IA" >> "$SHELL_CONFIG"
    echo "alias mistral='$AGENT_DIR/venv/bin/python3 $AGENT_DIR/mistral_agent.py'" >> "$SHELL_CONFIG"
    echo 'export PATH="$PATH:$HOME/tech/scripts"' >> "$SHELL_CONFIG"
else
    echo "✅ L'alias 'mistral' existe déjà dans $SHELL_CONFIG"
fi

# Création du fichier d'exécution
cat > "$AGENT_DIR/run.sh" << 'EOF'
#!/bin/bash
source "$HOME/.mistral_agent/venv/bin/activate"
python3 "$HOME/.mistral_agent/mistral_agent.py" "$@"
EOF

chmod +x "$AGENT_DIR/run.sh"

# Créer un lien symbolique dans /usr/local/bin
echo "🔗 Création d'un lien symbolique pour l'agent..."
if [ -w "/usr/local/bin" ]; then
    sudo ln -sf "$AGENT_DIR/run.sh" /usr/local/bin/mistral
else
    echo "⚠️ Impossible de créer le lien symbolique dans /usr/local/bin (besoin de droits sudo)"
    echo "   Vous pouvez utiliser l'alias 'mistral' après avoir rechargé votre shell"
fi

echo ""
echo "✅ Installation terminée!"
echo "🚀 Pour démarrer l'agent, vous pouvez:"
echo "   1. Recharger votre shell avec 'source $SHELL_CONFIG' puis utiliser la commande 'mistral'"
echo "   2. Ou exécuter directement '$AGENT_DIR/run.sh'"
echo ""
echo "Options disponibles:"
echo "   --lang fr|en    : Définir la langue (français par défaut)"
echo "   --debug         : Activer le mode debug"
echo "   --scripts-dir   : Spécifier un dossier pour les scripts"
echo ""
echo "Exemple: mistral --lang en"

# Recharger le shell si possible
if [[ "$0" = "$BASH_SOURCE" ]]; then
    echo "Rechargement du shell..."
    exec "$SHELL"
fi