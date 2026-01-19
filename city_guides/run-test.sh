#!/usr/bin/env bash
set -e
cd /home/markm/TravelLand/city_guides

# Verify we're in WSL
if ! grep -qi microsoft /proc/version 2>/dev/null; then
  echo "Warning: you do not appear to be running inside WSL. Open a WSL terminal and retry."
  exit 1
fi

# Install nvm+node
echo "Installing nvm and Node LTS (this may take a few minutes)..."
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm install --lts
nvm use --lts

echo "Using node: $(node -v)  npm: $(npm -v)"

# Install jest + jsdom locally
npm install --save-dev jest jsdom --no-audit --no-fund

# Run the test (runInBand prevents worker/socket issues)
npx jest tests/frontend/main.test.js --env=jsdom --runInBand --colors