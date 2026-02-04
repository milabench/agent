#!/bin/bash
# Quick-start deployment script
# Usage: ./deploy.sh <inventory_file> [extra_vars]

set -e

INVENTORY="${1:-.inventory.ini}"
EXTRA_VARS="${2:-}"

if [ ! -f "$INVENTORY" ]; then
    echo "Error: Inventory file '$INVENTORY' not found"
    echo "Usage: $0 <inventory_file> [extra_vars]"
    echo ""
    echo "Example:"
    echo "  $0 inventory.ini"
    echo "  $0 inventory.ini '-e agent_server_port=8080'"
    exit 1
fi

echo "Deploying Milabench Agent..."
echo "Inventory: $INVENTORY"

# Verify Ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    echo "Error: ansible-playbook not found. Please install Ansible."
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the playbook
if [ -n "$EXTRA_VARS" ]; then
    ansible-playbook "$SCRIPT_DIR/playbook.yml" -i "$INVENTORY" $EXTRA_VARS
else
    ansible-playbook "$SCRIPT_DIR/playbook.yml" -i "$INVENTORY"
fi

echo ""
echo "✓ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Verify the service is running:"
echo "   ssh <your-host> sudo systemctl status milabench-agent"
echo ""
echo "2. Check the API endpoint:"
echo "   curl http://<your-host>:5000/config"
echo ""
echo "3. View service logs:"
echo "   ssh <your-host> sudo journalctl -u milabench-agent -f"
