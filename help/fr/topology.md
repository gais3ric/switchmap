---
title: Topologie du réseau
category: monitoring
order: 3
summary: Un plan des liens entre commutateurs basé sur LLDP : comment l’activer et le lire.
keywords: topologie carte schéma réseau lldp voisins cdp liens graphe
---
La page **Topologie** dessine quel commutateur est relié à quel autre et par quels ports. Les données viennent de **LLDP**, un protocole par lequel les équipements voisins se présentent les uns aux autres.

# Ce qu’il vous faut {#requirements}

1. Activer LLDP sur les commutateurs : les commandes des différents constructeurs sont dans [Activer SNMP](/help/snmp-vendors). De nombreux modèles l’ont activé par défaut.
2. Les commutateurs doivent être ajoutés à SwitchMap avec une adresse IP et un accès SNMP.

# Lire le plan {#read}

La légende se trouve dans un coin du plan :

| Repère | Ce que c’est |
|---|---|
| Barre bleue | Un commutateur de SwitchMap ; le point indique s’il est joignable |
| Barre bleu clair | Un serveur ou un équipement attribué à un port |
| Barre orange | Un voisin LLDP inconnu : un équipement absent de SwitchMap (point d’accès, téléphone IP, autre commutateur) |
| Trait plein | Un lien physique selon LLDP |
| Pointillés | Un équipement attribué à un port à la main |

Survolez une ligne pour voir les ports aux deux extrémités.

Déplacez le plan à la souris, zoomez avec la molette, et le bouton **Ajuster** remet tout le plan à l’écran. Un clic sur un commutateur ouvre une fiche avec le bouton **Ouvrir le commutateur**.

> **Astuce :** avec **Suivre les voisins LLDP** activé lors de la [recherche sur le réseau](/help/add-switch#discovery), SwitchMap trouve lui-même les commutateurs qui apparaissent comme voisins sur ce plan.

# Fraîcheur du plan {#freshness}

Le plan est construit à partir des voisins que SwitchMap a mémorisés lors des dernières interrogations des commutateurs ; il s’ouvre donc instantanément, même sur un grand réseau. Les voisins sont mis à jour par l’interrogation périodique (au plus toutes les 10 minutes, ou une fois par heure en mode « une fois par heure », voir [Supervision et alertes](/help/monitoring#polling)) et par **Interroger en SNMP** sur la page du commutateur.

Le bouton **Actualiser** du plan interroge à nouveau LLDP sur tous les commutateurs — utilisez-le si vous venez de déplacer des câbles.

# S’il n’y a pas de liens {#empty}

- Le commutateur n’a pas encore été interrogé depuis le démarrage de SwitchMap — cliquez sur **Actualiser**.
- LLDP est désactivé sur le commutateur ou sur certains ports.
- Le commutateur ne fournit pas LLDP-MIB en SNMP (c’est le cas des modèles simples).
- Certains équipements Cisco n’utilisent que CDP par défaut : activez LLDP avec `lldp run`.
