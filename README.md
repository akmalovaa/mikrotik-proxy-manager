# mikrotik-proxy-manager

Simple reverse proxy, managing hosts from winbox

Adding hosts in the winbox interface automatically creates a dynamic configuration for traefik

![scheme](./images/scheme.excalidraw.png)

Obtaining SSL certificates via letsEncrypt or wildcard certs Clouflare API


Uses containers in [RouterOS](https://help.mikrotik.com/docs/display/ROS/Container):
- traefik
- mikrotik-proxy-manager (python app) 

**For the service to work, you need:**
- RouterOS with enabled container feature (arm64, x86)
- Public ip address
- Domain name

## Guide 

> **status:** in progress

### dev commands 

python
```
poetry install 
poetry shell
python -m mikrotik_proxy_manager
```

registry-url: https://registry-1.docker.io


example commands:
```shell
# mount test
/container/mounts/add name=traefik_static src=usb1/traefik/traefik.yml dst=/etc/traefik/traefik.yml

# NGINX
/container/add remote-image=nginx:latest interface=veth1 root-dir=usb1/docker/nginx logging=yes


/container/add remote-image=traefik:v3.1.6 interface=veth1 root-dir=usb1/root1 mounts=traefik_static,traefik_dynamic start-on-boot=yes logging=yes

# test
/container/add remote-image=akmalovaa/mikrotik-proxy-manager interface=veth1 root-dir=usb1/docker/mpm mounts=mpm_logs,mpm_config logging=yes start-on-boot=yes

# python iamge for run and shell exec
/container/add remote-image=python:3.12.7-slim interface=veth1 root-dir=usb1/docker/python logging=yes cmd="tail -f /dev/null"
```

> [!WARNING] 
> **RouterOS bags v7.16:**
> - If change ram-high `/container config set ram-high=200`, container logs will be lost, ram-high must be = 0
> - There is no way to passthrough a specific volume one file, only the entire directory
>
