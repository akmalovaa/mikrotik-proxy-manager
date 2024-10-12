# mikrotik-proxy-manager

> **status:** in development

Built-in router, simple reverse proxy
Managing proxy hosts with winbox

Uses containers in [RouterOS](https://help.mikrotik.com/docs/display/ROS/Container)

**For the service to work, you need:**
- RouterOS with enabled container feature (arm64, x86)
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

- registry-1.docker.io
- ghcr.io 

no space to extract layer -> need root-dir

example commands:
```shell
# mount test
/container/mounts/add name=traefik_static src=usb1/traefik/traefik.yml dst=/etc/traefik/traefik.yml

# NGINX
/container/add remote-image=nginx:latest interface=veth1 root-dir=usb1/docker/nginx logging=yes


/container/add remote-image=traefik:v3.2 interface=veth1 root-dir=usb1/traefik mounts=traefik_static logging=yes

# python iamge for run and shell exec
/container/add remote-image=python:3.12.7-slim interface=veth1 root-dir=usb1/docker/python logging=yes cmd="tail -f /dev/null"

# test
/container/add remote-image=akmalovaa/mikrotik-proxy-manager:1.0.0 interface=veth1 root-dir=usb1/mpm logging=yes start-on-boot=yes hostname=mpm dns=1.1.1.1
```
