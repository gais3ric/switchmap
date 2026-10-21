---
title: Premiers pas
category: start
order: 1
summary: Ce que fait SwitchMap et comment voir vos commutateurs en 10 minutes.
keywords: démarrage début rapide introduction aperçu
---
SwitchMap présente les commutateurs de votre réseau sous forme de plan clair : quels ports sont utilisés, où va chaque câble, quel équipement est branché où et si un port est surchargé. Les données viennent des commutateurs eux-mêmes via SNMP : rien à installer dessus, il suffit d’activer SNMP.

# Ce qu’il vous faut {#requirements}

- Un ordinateur ou serveur exécutant SwitchMap, avec un accès réseau aux commutateurs (port UDP 161).
- SNMP activé sur les commutateurs en lecture seule. Comment faire selon les modèles : [Activer SNMP sur les commutateurs](/help/snmp-vendors).
- Les adresses IP d’administration des commutateurs. S’il y en a beaucoup ou que vous ne les connaissez pas toutes, SwitchMap les trouvera.

# Étape 1. Ajouter les commutateurs {#add}

Deux façons :

1. **Un par un.** Sur la page d’accueil, cliquez sur **Ajouter un commutateur**, saisissez l’adresse IP et les réglages SNMP puis cliquez sur **Vérifier et remplir** : le nom, le nombre de ports et le modèle se remplissent tout seuls.
2. **Tous d’un coup.** Cliquez sur **Rechercher sur le réseau**, indiquez un réseau (par exemple `192.168.1.0/24`) : SwitchMap vérifie chaque adresse et liste les commutateurs trouvés. Cochez ceux qu’il vous faut et cliquez sur **Ajouter la sélection**.

Si vous utilisez NetBox, vous pouvez en importer les commutateurs : voir [Import depuis NetBox](/help/netbox).

# Étape 2. Interroger le commutateur {#poll}

Ouvrez un commutateur et cliquez sur **Interroger en SNMP**. En quelques secondes, le plan affiche l’état des ports : les ports vifs ont un lien, les pâles non. Le tableau **Ports** indique la vitesse, l’utilisation, les erreurs et le VLAN de chaque port.

Pour que les données se mettent à jour toutes seules, ouvrez les **Réglages** (l’engrenage en bas à gauche) et activez l’**Interrogation périodique**. Cinq minutes conviennent à presque tout le monde.

# Étape 3. Dessiner les connexions {#connections}

Le plan montre aussi ce que le commutateur ignore : où va chaque port via le panneau de brassage. Cliquez sur **Modifier**, ajoutez un panneau de brassage, puis cliquez sur un port du commutateur et sur un port du panneau, et nommez la connexion (« Comptabilité, bureau 214 »). En savoir plus : [Plan des ports et connexions](/help/port-map).

# Et ensuite {#next}

- [Rechercher un équipement](/help/search) par MAC, IP ou nom : voyez sur quel port il est branché.
- [Notifications](/help/notifications) par Telegram ou e-mail quand un commutateur est injoignable ou qu’un port tombe.
- [Topologie](/help/topology) : plan des liens entre commutateurs basé sur LLDP.
- [Utilisateurs](/help/users) : donnez à vos collègues un accès en lecture seule.

> **Astuce :** chaque champ complexe a une icône **?** : survolez-la pour voir une courte explication. Chaque page a en haut à droite un bouton d’aide sur cette page.
