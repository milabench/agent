# Milabench Agent Deployment

This directory contains Ansible playbooks and configuration files to deploy the Milabench Agent on remote machines.

## Overview

The Milabench Agent is a remote work scheduler that runs as a service on target machines. It provides a Flask-based HTTP API for scheduling and monitoring command execution.

## Directory Structure

```
deploy/
├── playbook.yml              # Main Ansible playbook
├── group_vars/
│   └── all.yml               # Default variables for all hosts
├── templates/
│   ├── milabench-agent.service.j2  # Systemd service file template
│   ├── agent.env.j2          # Environment variables template
│   └── agent.conf.j2         # Configuration file template
└── README.md                 # This file
```

## Prerequisites

- Ansible 2.9+
- Target machines with:
  - Ubuntu 20.04+ or RHEL/CentOS 8+
  - SSH access with sudo privileges
  - Python 3.8+

## Installation

### 1. Set Up Ansible Inventory

Create an `inventory.ini` file with your target hosts:

```ini
[agent_servers]
agent1.example.com
agent2.example.com
agent3.example.com

[agent_servers:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/id_rsa
```

### 2. Customize Configuration (Optional)

To override default settings, create a group-specific variables file or pass variables on the command line.

#### Option A: Group Variables File

Create `deploy/group_vars/agent_servers.yml`:

```yaml
---
milabench_base: /opt/milabench
agent_job_dir: /opt/milabench/jobrunner
agent_server_port: 5000
agent_server_host: "0.0.0.0"
```

#### Option B: Command Line Variables

```bash
# Development mode (default)
ansible-playbook deploy/playbook.yml -i inventory.ini

# Production mode
ansible-playbook deploy/playbook.yml -i inventory.ini -e agent_deployment_mode=prod

# Custom paths
ansible-playbook deploy/playbook.yml -i inventory.ini \
  -e agent_deployment_mode=prod \
  -e milabench_base=/custom/path \
  -e agent_job_dir=/custom/jobs
```

### 3. Run the Playbook

```bash
ansible-playbook deploy/playbook.yml -i inventory.ini
```

For verbose output:

```bash
ansible-playbook deploy/playbook.yml -i inventory.ini -v
```

## Deployment Modes

The playbook supports two deployment modes:

### Development Mode (Default)

```bash
ansible-playbook deploy/playbook.yml -i inventory.ini -e agent_deployment_mode=dev
```

**Characteristics:**
- Uses Flask development server with debug mode enabled
- Editable install (`-e` flag) - code changes reload automatically
- Hot-reloading enabled for rapid development
- Suitable for testing and development environments

**Server command:**
```
python -c "from agent.server.server import server; app = server(); app.run(host='0.0.0.0', port=5000, debug=True)"
```

### Production Mode

```bash
ansible-playbook deploy/playbook.yml -i inventory.ini -e agent_deployment_mode=prod
```

**Characteristics:**
- Uses Waitress WSGI server (production-grade)
- Standard install (not editable)
- Multi-threaded request handling
- Better performance and stability
- Suitable for production deployments

**Server command:**
```
waitress-serve --host 0.0.0.0 --port 5000 --threads 4 agent.server:server
```

**Notes:**
- The number of threads is controlled by `agent_server_workers` variable
- Waitress is more robust than Flask's development server
- Better suited for handling concurrent requests

## Configuration Variables

Default values are defined in `deploy/group_vars/all.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `agent_deployment_mode` | `dev` | Deployment mode: `dev` (Flask with debug) or `prod` (Waitress WSGI server) |
| `milabench_base` | `/opt/milabench` | Base installation directory |
| `agent_install_dir` | `{{ milabench_base }}/agent` | Agent repository location |
| `agent_venv_dir` | `{{ agent_install_dir }}/.venv` | Virtual environment location |
| `agent_job_dir` | `{{ milabench_base }}/jobrunner` | Job execution directory |
| `agent_user` | `milabench` | Service user |
| `agent_group` | `milabench` | Service group |
| `agent_server_host` | `0.0.0.0` | Server listen address |
| `agent_server_port` | `5000` | Server port |
| `agent_server_workers` | `4` | Number of worker threads (prod mode only) |
| `python_version` | `3.12` | Python version to install |
| `agent_repo_url` | `https://github.com/milabench/agent.git` | Agent repository URL |
| `agent_repo_branch` | `main` | Repository branch to clone |

## What the Playbook Does

1. **System Setup**
   - Installs Python 3.12, build tools, and curl
   - Creates `milabench` user and group
   - Configures passwordless sudo for the `milabench` user
   - Creates directory structure at `/opt/milabench`

2. **Agent Installation**
   - Installs UV package manager
   - Clones the agent repository to `/opt/milabench/agent`
   - Creates Python virtual environment at `/opt/milabench/agent/.venv` using UV
   - Installs agent package and dependencies (Flask, APScheduler, filelock) using UV

3. **Service Configuration**
   - Creates systemd service file: `/etc/systemd/system/milabench-agent.service`
   - Creates environment file: `/opt/milabench/.env`
   - Creates configuration file: `/opt/milabench/agent.conf`
   - Enables and starts the service

4. **Directory Setup**
   - Job directory: `/opt/milabench/jobrunner`
   - Log directory: `/var/log/milabench`
   - Sets appropriate permissions and ownership

## Service Management

After deployment, manage the service using standard systemd commands:

```bash
# Start the service
sudo systemctl start milabench-agent

# Stop the service
sudo systemctl stop milabench-agent

# Restart the service
sudo systemctl restart milabench-agent

# Check service status
sudo systemctl status milabench-agent

# View service logs
sudo journalctl -u milabench-agent -f

# Enable auto-start on boot
sudo systemctl enable milabench-agent
```

## API Endpoints

Once deployed and running, the agent provides:

- `POST /popen` - Schedule a command execution
  - Request body: `{"cmd": "command string", "options": {}}`
  - Returns: Job information with job_id

- `GET /config` - Get agent configuration
  - Returns: Agent hostname, remote folder, and config details

### Example Usage

```bash
# Check if agent is running
curl http://localhost:5000/config

# Schedule a command
curl -X POST http://localhost:5000/popen \
  -H "Content-Type: application/json" \
  -d '{"cmd": "echo Hello", "options": {}}'
```

## Directory Structure on Target

After deployment:

```
/opt/milabench/
├── agent/                    # Cloned repository
│   └── .venv/                # Python virtual environment (created by UV)
├── jobrunner/                # Job execution directory
│   └── */                    # Individual job directories
├── .env                      # Environment variables
└── agent.conf                # Configuration file

/var/log/milabench/           # Log directory
```

## Troubleshooting

### Service won't start

Check the service status and logs:

```bash
sudo systemctl status milabench-agent
sudo journalctl -u milabench-agent -n 50
```

### Permission issues

Ensure proper ownership:

```bash
sudo chown -R milabench:milabench /opt/milabench
sudo chown -R milabench:milabench /var/log/milabench
```

### Job directory not found

Verify the job directory exists and is writable:

```bash
ls -la /opt/milabench/jobrunner
```

## Production Considerations

For production deployments:

1. **Use Gunicorn or uWSGI** instead of Flask's development server
   - Modify `ExecStart` in the service template

2. **Configure reverse proxy** (nginx/Apache)
   - Proxy requests to the Flask server
   - Handle SSL/TLS termination

3. **Monitor logs and metrics**
   - Use log aggregation (ELK, Splunk, etc.)
   - Set up monitoring and alerting

4. **Backup job data**
   - Configure automatic backups of `/opt/milabench/jobrunner`

5. **Update repository regularly**
   - Set up cron jobs or CI/CD to pull latest changes

## Security Considerations

The systemd service includes several security hardening measures:

- Runs with restricted user (`milabench`)
- Uses `ProtectSystem=strict` to restrict filesystem access
- Enables `PrivateTmp` for isolated temporary files
- Uses `NoNewPrivileges=true`
- Only allows write access to job and log directories

## Updating the Agent

To update to a new version:

```bash
# Pull latest changes
cd /opt/milabench/agent
sudo -u milabench git pull origin main

# Reinstall package with UV
sudo /opt/milabench/agent/.venv/bin/uv pip install -e .

# Restart service
sudo systemctl restart milabench-agent
```

Or re-run the playbook with updated variables.

## Uninstallation

To remove the agent:

```bash
# Stop and disable service
sudo systemctl stop milabench-agent
sudo systemctl disable milabench-agent

# Remove service file
sudo rm /etc/systemd/system/milabench-agent.service
sudo systemctl daemon-reload

# Remove installation directory (careful!)
sudo rm -rf /opt/milabench

# Remove user and group
sudo userdel -r milabench
sudo groupdel milabench
```

## Support

For issues, feature requests, or contributions, visit the [agent repository](https://github.com/milabench/agent).
