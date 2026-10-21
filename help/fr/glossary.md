---
title: Glossaire
category: start
order: 3
summary: Des explications simples des termes réseau utilisés dans SwitchMap.
keywords: glossaire termes qu’est-ce que vlan trunk uplink mac ip lldp snmp sfp poe panneau de brassage ifalias duplex
---
| Terme | De quoi il s’agit |
|---|---|
| **Commutateur (switch)** | Un équipement auquel on branche par câble ordinateurs, téléphones, points d’accès et autres commutateurs. Il fait circuler les données entre eux |
| **Port** | Une prise du commutateur pour un câble |
| **Lien** | Le port est branché et un équipement allumé se trouve à l’autre bout |
| **Panneau de brassage** | Une rangée de prises dans la baie où arrivent les câbles des bureaux. Il est relié au commutateur par des câbles courts (cordons de brassage) |
| **RJ-45** | Le connecteur réseau en cuivre habituel (paire torsadée) |
| **SFP** | Un emplacement pour un module amovible, généralement en fibre, pour de plus grandes distances et vitesses |
| **Adresse MAC** | Le « numéro de série » unique d’un équipement réseau, comme `00:1A:2B:3C:4D:5E`. Un commutateur retient quelle MAC se trouve derrière quel port |
| **Adresse IP** | L’adresse d’un équipement sur le réseau, comme `192.168.1.25` |
| **VLAN** | Un « sous-réseau » logique dans le commutateur : les ports de VLAN différents ne se voient pas directement. Par exemple VLAN 10 pour la comptabilité, VLAN 20 pour les téléphones |
| **Trunk** | Un port qui transporte plusieurs VLAN à la fois, généralement le lien vers un autre commutateur |
| **Uplink** | Un port qui mène « vers le haut » : vers un autre commutateur ou le cœur du réseau |
| **SNMP** | Le protocole avec lequel SwitchMap interroge un commutateur sur son état. Voir [Qu’est-ce que SNMP](/help/snmp-basics) |
| **Community** | Le « mot de passe » de SNMP v2c |
| **LLDP** | Un protocole par lequel les équipements voisins se présentent les uns aux autres. La [topologie](/help/topology) est construite à partir de lui |
| **Description du port (ifAlias)** | Une étiquette de port définie dans la configuration du commutateur (par exemple « uplink-core ») |
| **Utilisation du port** | La part de la vitesse du port occupée par le trafic, en pourcentage |
| **Erreurs du port** | Des données endommagées pendant la transmission. Généralement le signe d’un câble ou d’un connecteur défectueux |
| **Vitesse et duplex** | La vitesse du port (100 Mbit/s, 1 Gbit/s, 10 Gbit/s) et le mode « dans les deux sens à la fois ». Ils doivent être identiques aux deux extrémités du câble |
| **PoE** | L’alimentation des équipements (téléphones, caméras, points d’accès) par le câble réseau |
| **Ping** | Une vérification simple : l’équipement répond-il sur le réseau ? |
| **NetBox** | Un système d’inventaire des équipements réseau. SwitchMap peut en [importer](/help/netbox) les commutateurs |
