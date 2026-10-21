---
title: Retrouver un équipement sur le réseau
category: monitoring
order: 4
summary: Comment savoir sur quel port un équipement est branché à partir de sa MAC, de son IP ou de son nom.
keywords: recherche trouver équipement mac ip nom hostname port description uplink trunk où est-il branché
---
Le champ de recherche de la barre supérieure (ou [[Ctrl]] + [[K]]) cherche dans tous les commutateurs à la fois :

- **adresse MAC**, complète ou partielle, avec ou sans deux-points : `00:1a:2b`, `001a2b3c` ;
- **adresse IP** ou une partie ;
- **nom de l’équipement** (s’il a pu être résolu par DNS) ;
- **description du port** sur le commutateur (ifAlias) et libellés de connexion du plan.

Le résultat est un commutateur et un port. Un clic ouvre le commutateur et met le port en évidence sur le plan.

# D’où viennent les données {#data}

Un commutateur retient les adresses MAC des équipements qu’il voit sur chaque port. SwitchMap lit ces tables à chaque interrogation SNMP. Par conséquent :

- un équipement n’est trouvé que s’il était sur le réseau lors de la dernière interrogation ;
- avec l’interrogation périodique activée, les données se mettent à jour toutes seules.

Un équipement qui doit toujours être trouvé (même éteint) peut être **attribué à un port** à la main : voir [Plan des ports](/help/port-map#devices).

# La mention uplink {#uplink}

Si un équipement est vu sur un port où l’on voit aussi beaucoup d’autres adresses MAC, ou si le port est marqué comme trunk, il s’agit très probablement non pas du port où l’équipement est branché, mais d’un lien vers un autre commutateur. Ces résultats portent la mention **uplink** et sont affichés plus bas. Cherchez la même MAC sur le commutateur suivant : le vrai port s’y trouve.
