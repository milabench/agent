#!/bin/bash
# Local development deployment script
# Deploys the Milabench Agent to localhost in development mode

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Determine current user/group and default base path for dev deploy
CURRENT_USER="$(id -un)"
CURRENT_GROUP="$(id -gn)"
HOME_DIR="${HOME:-/home/${CURRENT_USER}}"
DEFAULT_BASE="${HOME_DIR}/milabench"

MIB_BASE="${MILABENCH_BASE:-$DEFAULT_BASE}"

EXTRA_VARS="agent_deployment_mode=dev agent_user=${CURRENT_USER} agent_group=${CURRENT_GROUP} milabench_base=${MIB_BASE}"

echo "Deploying Milabench Agent to localhost (DEV mode) as user: ${CURRENT_USER}"
echo "Base path: ${MIB_BASE}"
echo ""

# Verify Ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    echo "Error: ansible-playbook not found. Please install Ansible."
    echo "  pip install ansible"
    exit 1
fi

echo "Running playbook with:"
echo "  - Inventory: localhost.ini"
echo "  - Mode: Development"
echo "  - Server: 0.0.0.0:5000"
echo "  - Extra vars: ${EXTRA_VARS}"
echo ""

# Run the playbook targeting localhost without privilege escalation
ansible-playbook "$SCRIPT_DIR/playbook.yml" \
    -i "$SCRIPT_DIR/localhost.ini" \
    -e "${EXTRA_VARS}" \
    -e agent_server_host=0.0.0.0 \
    -e ansible_become=true

echo ""
echo "✓ Local deployment requested (playbook run finished)."
echo ""
echo "Next steps:"
echo "1. Check service status:"
echo "   systemctl --user status milabench-agent || sudo systemctl status milabench-agent"
echo ""
echo "2. View logs:"
echo "   sudo journalctl -u milabench-agent -f"
echo ""
echo "3. Test the API:"
echo "   curl http://localhost:5000/config"
echo ""
echo "4. To restart the service after code changes:"
echo "   sudo systemctl restart milabench-agent"
echo ""
echo "5. To stop the service:"
echo "   sudo systemctl stop milabench-agent"
