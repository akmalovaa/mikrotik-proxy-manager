# Mikrotik Proxy Manager

## Mikrotik containers prepare guide

### API SSL

Create certifcates

```routeros
/certificate
add name=CA common-name=CA key-usage=key-cert-sign,crl-sign
add name=Server common-name=server
add name=Client common-name=client
```

Certificates should be signed.
**Change your RouterOS host address**

```routeros
/certificate
sign CA
sign Client
sign Server ca-crl-host=192.168.88.1 name=CA
```

Enable API-SSL. **Change api access address**

```routeros
/ip service
set api-ssl address=192.168.88.0/24 certificate=Server
```

Create group for only read API info + create a user for that group

```routeros
/user group
add name=api policy=local,read,api,rest-api,!write,!telnet,!ssh,!ftp,!reboot,!policy,!test,!winbox,!password,!web,!sniff,!sensitive,!romon
/user add name=user-api group=api password=password
```

### Network

Create separate bridge + ip address - **Change YOUR IP Addresses**

```routeros
/interface/bridge/add name=br-container
/ip/address/add address=10.0.0.1/24 interface=br-container
```

Create virtal interface

```routeros
/interface/veth/add name=veth1 address=10.0.0.10/24 gateway=10.0.0.1
/interface/bridge/port/add bridge=br-container interface=veth1
```

NAT config

```routeros
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=10.0.0.0/24
```

Firewall forward 80, 443 port to traefik proxy

```routeros
/ip firewall/nat/
add action=dst-nat chain=dstnat comment=http dst-port=80 protocol=tcp to-addresses=10.0.0.10 to-ports=80
add action=dst-nat chain=dstnat comment=https dst-port=443 protocol=tcp to-addresses=10.0.0.10 to-ports=44
```

### Containers

RouterOS - https://help.mikrotik.com/docs/display/ROS/Container

Container package needs to be installed (enable container mode)

> [!NOTE]  
> External disk is highly recommended (formatting USB on ext4)
