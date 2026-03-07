#!/bin/bash
# Wordhord Desktop Entry Installation Script

echo "📦 Installing Wordhord desktop entry..."

# Create directories
mkdir -p ~/.local/bin
mkdir -p ~/.local/share/applications
mkdir -p ~/.local/share/icons/hicolor/256x256/apps

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Copy launcher script
cp "$SCRIPT_DIR/wordhord-launcher.sh" ~/.local/bin/wordhord
chmod +x ~/.local/bin/wordhord
echo "✓ Launcher script installed to ~/.local/bin/wordhord"

# Copy icon
if [ -f "$SCRIPT_DIR/wordhord.svg" ]; then
  cp "$SCRIPT_DIR/wordhord.svg" ~/.local/share/icons/hicolor/256x256/apps/wordhord.svg
  echo "✓ Icon installed"
fi

# Install desktop entry
cp "$SCRIPT_DIR/wordhord.desktop" ~/.local/share/applications/wordhord.desktop
chmod 644 ~/.local/share/applications/wordhord.desktop
echo "✓ Desktop entry installed"

# Update icon cache if available
if command -v gtk-update-icon-cache &> /dev/null; then
  gtk-update-icon-cache ~/.local/share/icons/hicolor/ 2>/dev/null
  echo "✓ Icon cache updated"
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
  update-desktop-database ~/.local/share/applications/ 2>/dev/null
  echo "✓ Desktop database updated"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "You can now launch Wordhord from your application menu or by running:"
echo "  wordhord"
echo ""
