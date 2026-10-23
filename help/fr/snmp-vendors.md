---
title: Activer SNMP sur les commutateurs
category: devices
order: 3
summary: Des commandes prêtes à l’emploi pour Cisco, HPE/Aruba, Juniper, MikroTik, Huawei, D-Link, TP-Link, Eltex et autres.
keywords: configurer activer snmp cisco ios catalyst hpe aruba procurve comware h3c juniper junos mikrotik routeros huawei d-link dlink tp-link eltex ubiquiti unifi lldp community
---
Voici la configuration minimale : accès en **lecture seule**, limité à l’adresse du serveur SwitchMap, et **LLDP** activé pour la [topologie](/help/topology). Dans les exemples :

| Valeur | À remplacer par |
|---|---|
| `192.168.1.10` | l’adresse IP du serveur SwitchMap |
| `MyStr0ngRO` | votre propre community (pour v2c) |
| `swmap` | le nom de l’utilisateur SNMPv3 |
| `AuthPass123`, `PrivPass123` | vos propres mots de passe v3, d’au moins 8 caractères |

> **Attention :** les commandes peuvent varier légèrement selon le modèle et la version du micrologiciel. Si une commande est refusée, cherchez la section « SNMP » dans la documentation du constructeur : les noms des paramètres seront proches.

Après la configuration, ajoutez le commutateur dans SwitchMap et cliquez sur **Vérifier et remplir** : vous verrez tout de suite si l’accès fonctionne.

# Cisco IOS et IOS-XE (Catalyst) {#cisco}

SNMP v2c :

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server community MyStr0ngRO RO 10
lldp run
end
write memory
```

SNMP v3 (recommandé) :

```
configure terminal
access-list 10 permit 192.168.1.10
snmp-server group SWMAP v3 priv access 10
snmp-server user swmap SWMAP v3 auth sha AuthPass123 priv aes 128 PrivPass123
lldp run
end
write memory
```

Les utilisateurs SNMPv3 n’apparaissent pas dans `show running-config` : c’est normal. Pour vérifier : `show snmp user`.

Cisco conserve une table MAC distincte par VLAN — SwitchMap interroge lui-même chaque VLAN. En v2c, rien à configurer. En v3, autorisez les contextes VLAN : `snmp-server group SWMAP v3 priv context vlan- match prefix`, et laissez vide le champ « Contexte » dans SwitchMap.

# Cisco Business et Small Business (CBS, SG) {#cisco-sb}

Interface web : **SNMP → Engine ID** (laisser la valeur par défaut), **SNMP → Communities** ou **SNMP → Users** (pour v3). Pour activer SNMP : **Security → TCP/UDP Services → SNMP Service**. LLDP : **Administration → Discovery – LLDP → Properties**.

# HPE Aruba (ArubaOS-Switch, ProCurve) {#aruba}

```
configure
snmp-server community "MyStr0ngRO" operator restricted
snmpv3 enable
snmpv3 user swmap auth sha AuthPass123 priv aes PrivPass123
snmpv3 group operatorauth user swmap sec-model ver3
lldp run
write memory
```

`snmpv3 enable` peut demander des mots de passe initiaux : saisissez-en n’importe lesquels, puis supprimez l’utilisateur initial `initial`.

# HPE Aruba CX (AOS-CX) {#aruba-cx}

```
configure
snmp-server vrf default
snmp-server community MyStr0ngRO
snmpv3 user swmap auth sha auth-pass plaintext AuthPass123 priv aes priv-pass plaintext PrivPass123
lldp
write memory
```

Si l’administration passe par le port mgmt, utilisez `snmp-server vrf mgmt`.

# HPE Comware et H3C (HPE 5130, 5140, 1950 et autres) {#comware}

```
system-view
snmp-agent
snmp-agent sys-info version v2c v3
snmp-agent community read MyStr0ngRO
snmp-agent group v3 swmap-grp privacy
snmp-agent usm-user v3 swmap swmap-grp simple authentication-mode sha AuthPass123 privacy-mode aes128 PrivPass123
lldp global enable
save
```

# Juniper (Junos, EX et QFX) {#juniper}

SNMP v2c :

```
set snmp community MyStr0ngRO authorization read-only
set snmp community MyStr0ngRO clients 192.168.1.10/32
set protocols lldp interface all
commit
```

SNMP v3 :

```
set snmp v3 usm local-engine user swmap authentication-sha authentication-password AuthPass123
set snmp v3 usm local-engine user swmap privacy-aes128 privacy-password PrivPass123
set snmp v3 vacm security-to-group security-model usm security-name swmap group swmap-grp
set snmp v3 vacm access group swmap-grp default-context-prefix security-model any security-level privacy read-view all
set snmp view all oid .1 include
commit
```

# MikroTik (RouterOS) {#mikrotik}

SNMP v2c :

```
/snmp set enabled=yes
/snmp community set [find default=yes] name=MyStr0ngRO addresses=192.168.1.10/32 read-access=yes write-access=no
```

SNMP v3 (RouterOS 7) : dans RouterOS, le nom de la community est aussi le nom de l’utilisateur v3.

```
/snmp community add name=swmap addresses=192.168.1.10/32 security=private authentication-protocol=SHA1 authentication-password=AuthPass123 encryption-protocol=AES encryption-password=PrivPass123
```

LLDP (RouterOS 7) : `/ip neighbor discovery-settings set protocol=cdp,lldp,mndp`.

# Huawei (VRP, série S) {#huawei}

```
system-view
snmp-agent
snmp-agent sys-info version v2c v3
snmp-agent community read cipher MyStr0ngRO
snmp-agent group v3 swmap-grp privacy
snmp-agent usm-user v3 swmap group swmap-grp
snmp-agent usm-user v3 swmap authentication-mode sha
snmp-agent usm-user v3 swmap privacy-mode aes128
lldp enable
save
```

Les deux dernières commandes demandent les mots de passe.

# D-Link (DGS, DES) {#dlink}

En ligne de commande (la plupart des modèles DGS-1210/3000/3100) :

```
enable snmp
create snmp community MyStr0ngRO view CommunityView read_only
enable lldp
save
```

Dans l’interface web : **Management → SNMP Settings** (activer SNMP, ajouter une community ou un utilisateur v3). Pour v3, l’interface web est plus pratique.

# TP-Link (JetStream, Omada) {#tplink}

Interface web : **Maintenance → SNMP → Global Config** : activer SNMP ; **SNMP → Community** : ajouter une community en **lecture seule** ; pour v3 : **SNMP User**. LLDP : **L2 Features → LLDP**. Les commutateurs gérés par un contrôleur Omada se configurent dans le contrôleur : **Settings → Services → SNMP**.

# Eltex (MES) {#eltex}

```
configure
snmp-server server
snmp-server community MyStr0ngRO ro 192.168.1.10
lldp run
end
write
```

# Ubiquiti UniFi {#unifi}

SNMP s’active dans le contrôleur UniFi : **Settings → System → SNMP** (community v1/v2c ou utilisateur v3). Le réglage s’applique à tous les commutateurs du site.

# Vérification depuis le serveur {#check}

Si vous disposez des outils Net-SNMP, vous pouvez tester l’accès ainsi :

```
snmpget -v2c -c MyStr0ngRO 192.0.2.5 1.3.6.1.2.1.1.5.0
snmpget -v3 -l authPriv -u swmap -a SHA -A AuthPass123 -x AES -X PrivPass123 192.0.2.5 1.3.6.1.2.1.1.5.0
```

La réponse est le nom du commutateur. « Timeout » signifie : pas d’accès réseau, community ou utilisateur incorrect. En savoir plus : [Dépannage](/help/troubleshooting).
