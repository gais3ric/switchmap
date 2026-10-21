---
title: Plan des ports et connexions
category: devices
order: 4
summary: Lire le plan du commutateur, dessiner les connexions via les panneaux de brassage, marquer les trunks et les VLAN.
keywords: plan port couleur panneau de brassage connexion câble trunk sfp rj45 vlan modifier pdf export baie
---
# Lire le plan {#read}

La page du commutateur affiche la **vue de la baie** : le commutateur et ses panneaux de brassage, port par port comme en façade.

| Ce que vous voyez | Ce que cela signifie |
|---|---|
| Port vif | Il y a un lien : quelque chose est branché et allumé |
| Port pâle | Pas de lien (d’après la dernière interrogation) |
| Barre de couleur en bas du port | Utilisation : jusqu’à 30 %, jusqu’à 60 %, jusqu’au seuil et au-delà — couleurs dans la légende au-dessus du plan |
| Contour rouge | Utilisation au-dessus du seuil d’alerte |
| Lettre **T** à côté du numéro | Le port est marqué comme trunk (uplink vers un autre commutateur) |
| Port avec une « languette » en bas | SFP (fibre) ; un port normal est RJ-45 (cuivre) |
| Marque de couleur sur le port | Le VLAN du port (une couleur peut être attribuée à chaque VLAN) |

Survolez un port pour voir une info-bulle : nom de l’interface, description, vitesse, utilisation, erreurs et équipements branchés. L’interrupteur **Utilisation des ports** affiche ou masque les barres de couleur.

# Connexions via les panneaux de brassage {#connections}

Le commutateur ne sait pas où va un câble après le panneau de brassage. Vous, si : dessinez-le une fois.

1. Cliquez sur **Modifier**.
2. S’il n’y a pas encore de panneau : **Réglages → Panneaux de brassage → Ajouter un panneau de brassage** : nom, nombre de ports, position (au-dessus ou au-dessous du commutateur).
3. Cliquez sur un port du commutateur puis sur un port du panneau.
4. Indiquez où va la ligne (« Bureau 214, imprimante ») et la couleur du câble.
5. Cliquez sur **Enregistrer**.

Si un câble va directement à un équipement sans panneau, faites un clic droit sur le port → **Attribuer directement…**

Toutes les connexions sont listées dans **Réglages → Commutateur → Connexions des ports**. On peut les y modifier ou les supprimer.

# Type de port et trunk {#trunk}

Clic droit sur un port du commutateur :

- **RJ-45 (cuivre)** ou **SFP (fibre)** : uniquement l’apparence sur le plan ;
- **Marquer comme trunk** : pour un port qui relie un autre commutateur. Les trunks comptent comme ports importants pour les [notifications](/help/notifications), et la recherche d’équipements comprend que tout un réseau se trouve derrière un tel port, et non un seul équipement.

# VLAN {#vlan}

Après une interrogation SNMP, **Réglages → VLAN** liste les VLAN du commutateur. Cliquez sur le carré de couleur à côté d’un VLAN et choisissez une couleur : les marques des ports de ce VLAN prendront cette couleur sur le plan. Le filtre VLAN estompe tous les autres ports. Le VLAN de chaque port figure aussi dans le tableau **Ports**.

# Équipements sur les ports {#devices}

Après un clic sur **Interroger en SNMP**, le panneau **Ports et équipements (SNMP)** s’ouvre à droite : toutes les interfaces et les adresses MAC que le commutateur voit sur chaque port, avec IP et nom lorsqu’ils sont connus. Cliquez sur un port du panneau pour déplier la liste de ses équipements. **Attribuer au port** fixe un équipement à un port avec votre note : la [recherche](/help/search) le trouvera même éteint.

# Export {#export}

Le menu **Exporter** :

- **Excel** : ports, connexions, panneaux de brassage et équipements sur des feuilles séparées ;
- **Fiche PDF** : un plan des connexions à imprimer ou à transmettre à un prestataire ;
- **CSV** : des tableaux séparés pour vos propres rapports ;
- **Historique des modifications** : toutes les modifications de ce commutateur dans le [journal](/help/backups#audit).
