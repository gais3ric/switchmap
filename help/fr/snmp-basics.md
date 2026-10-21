---
title: Qu’est-ce que SNMP
category: devices
order: 2
summary: Une explication simple : versions v2c et v3, community, utilisateurs et mots de passe, sécurité.
keywords: snmp v2c v3 community utilisateur authentification chiffrement sha aes md5 des contexte sécurité udp 161
---
**SNMP** (Simple Network Management Protocol) est la manière standard d’interroger un équipement réseau sur son état : la liste des ports, s’ils sont actifs, la quantité de trafic écoulé, les adresses MAC vues, la charge CPU et la température. Pratiquement tous les commutateurs administrables le prennent en charge.

SwitchMap ne fait que **lire** les données : il ne modifie jamais rien sur les commutateurs. Un accès en lecture seule suffit.

Les requêtes sont envoyées au **port UDP 161** du commutateur.

# v2c ou v3 {#v2c-or-v3}

| | SNMP v2c | SNMP v3 |
|---|---|---|
| Vérification de l’accès | Par un mot de passe partagé : la **community** | Utilisateur et mot de passe |
| Chiffrement des données | Aucun : tout circule en clair | Oui (AES, DES) |
| Configuration | Une ligne sur le commutateur | Quelques lignes |
| Quand le choisir | Un réseau d’administration isolé | Dans tous les autres cas |

> **Attention :** tout le monde connaît la community `public`. Si vous utilisez v2c, définissez votre propre community robuste et limitez l’accès SNMP à l’adresse du serveur SwitchMap.

# Community {#community}

Une community est simplement une chaîne que le commutateur compare à celle qu’il reçoit. Pour la lecture, on crée généralement une community avec des droits **RO** (lecture seule). Dans SwitchMap, elle se saisit dans le champ **Community**. Pour la recherche sur le réseau, vous pouvez en indiquer plusieurs séparées par des virgules.

# SNMPv3 {#snmpv3}

En v3, on crée sur le commutateur un **utilisateur** avec deux mots de passe :

- **Authentification** (SHA, SHA-256 et autres, l’ancien MD5) : prouve que la requête vient de vous et n’a pas été modifiée en chemin.
- **Chiffrement** (AES128 et autres, l’ancien DES) : masque le contenu des réponses.

Niveaux de sécurité :

| Niveau | Authentification | Chiffrement |
|---|---|---|
| noAuthNoPriv | non | non |
| authNoPriv | oui | non |
| authPriv | oui | oui — recommandé |

Dans SwitchMap, indiquez le même **algorithme** et les mêmes **mots de passe** que sur le commutateur. Les mots de passe doivent comporter au moins 8 caractères (exigence de la norme).

Le **contexte** reste généralement vide. Il est nécessaire par exemple sur les commutateurs Cisco, où la table MAC d’un VLAN se lit via le contexte `vlan-10`.

Les mots de passe SNMPv3 sont stockés chiffrés dans la base de SwitchMap, et la clé de chiffrement est conservée dans un fichier séparé, `switchmap.secret`.

# Ce que lit SwitchMap {#what}

| Données | Source (MIB) |
|---|---|
| Nom, description, emplacement | SNMPv2-MIB (system) |
| Ports, état, vitesse, compteurs de trafic et d’erreurs | IF-MIB |
| Descriptions des ports (ifAlias) | IF-MIB |
| Adresses MAC sur les ports | BRIDGE-MIB, Q-BRIDGE-MIB |
| VLAN des ports | Q-BRIDGE-MIB |
| Voisins | LLDP-MIB |
| CPU, mémoire, température | variable : dépend du constructeur |
| PoE | POWER-ETHERNET-MIB |

S’il manque certaines données, le commutateur ne les fournit pas en SNMP ou elles nécessitent un autre contexte. Tout le reste fonctionne quand même.
