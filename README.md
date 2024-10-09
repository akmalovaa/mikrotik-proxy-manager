# mikrotik-proxy-manager

> **status:** in development

Built-in router, simple reverse proxy
Managing proxy hosts with winbox

Uses containers in [RouterOS](https://help.mikrotik.com/docs/display/ROS/Container)

**For the service to work, you need:**
- RouterOS with enabled container feature (arm, arm64, x86)
- Public ip address
- Domain name

### Goal

Adding hosts in the winbox interface automatically creates a dynamic configuration for traefik

Obtaining SSL certificates via letsEncrypt or wildcard certs Clouflare API

Containers:
- traefik
- mikrotik-proxy-manager (python app) 

### dev commands 

```
python -m mikrotik-proxy-manager
```