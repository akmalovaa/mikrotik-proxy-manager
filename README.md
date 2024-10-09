# mikrotik-proxy-manager

Built-in router, simple reverse proxy

> **status:** in development

Uses containers in [RouterOS](https://help.mikrotik.com/docs/display/ROS/Container)

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