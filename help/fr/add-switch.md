---
title: Ajouter des commutateurs
category: devices
order: 1
summary: À la main, par recherche sur le réseau ou depuis NetBox ; que faire si un commutateur est introuvable.
keywords: ajouter nouveau commutateur découverte recherche scan plage réseau lldp
---
# À la main {#manual}

1. Sur la page d’accueil, cliquez sur **Ajouter un commutateur**.
2. Saisissez l’**adresse IP** d’administration et les réglages SNMP (version, community ou utilisateur v3).
3. Cliquez sur **Vérifier et remplir**. Si le commutateur répond, SwitchMap remplit son nom, son nombre de ports et son modèle. Sinon, vous verrez pourquoi (par exemple « mot de passe SNMPv3 incorrect »).
4. Ajoutez des panneaux de brassage si besoin et cliquez sur **Créer le commutateur**.

Vous pouvez aussi ajouter un commutateur sans adresse IP, comme plan pour documenter le câblage. Mais il n’y aura alors ni état des ports, ni utilisation, ni recherche d’équipements.

# Recherche sur le réseau {#discovery}

La rubrique **Recherche et import** (icône radar) vérifie de nombreuses adresses à la fois.

1. Dans **Réseaux et adresses**, indiquez où chercher, séparé par des virgules ou des retours à la ligne :
   - un réseau : `192.168.1.0/24` ;
   - une plage : `10.0.0.1-10.0.0.50` ou en abrégé `10.0.0.1-50` ;
   - des adresses isolées : `10.0.5.7`.
2. Saisissez les réglages SNMP. En v2c, vous pouvez indiquer plusieurs communities séparées par des virgules : toutes sont essayées.
3. **Suivre les voisins LLDP** : les commutateurs trouvés indiquent les adresses de leurs voisins, qui sont vérifiées à leur tour. On trouve ainsi des commutateurs dans des réseaux non indiqués.
4. Cliquez sur **Lancer la recherche**. La recherche s’exécute sur le serveur : vous pouvez fermer la page et revenir plus tard.
5. Dans le tableau des résultats, cochez les équipements voulus, modifiez les noms si nécessaire et cliquez sur **Ajouter la sélection**.

Une recherche vérifie jusqu’à 4096 adresses (un réseau /20). Les commutateurs déjà ajoutés sont marqués « déjà ajouté » et ne sont pas dupliqués.

> **Astuce :** le filtre **Commutateurs / Tous les équipements** : par défaut, seuls les équipements qui ressemblent à des commutateurs sont affichés. Les imprimantes, onduleurs et serveurs qui répondent aussi en SNMP sont masqués.

# Depuis NetBox {#netbox}

Si vos commutateurs sont déjà dans NetBox, importez-les avec leurs noms, adresses IP et nombre de ports. Voir [Import depuis NetBox](/help/netbox).

# Un commutateur est introuvable {#not-found}

- Vérifiez que le port **UDP 161** du commutateur est joignable depuis le serveur SwitchMap (pare-feu, ACL sur le commutateur).
- Assurez-vous que SNMP est activé sur le commutateur et que l’adresse du serveur SwitchMap est autorisée : de nombreux modèles n’acceptent que les requêtes d’une liste d’adresses autorisées.
- Vérifiez la community ou les identifiants v3 : ils sont sensibles à la casse.

En savoir plus : [Dépannage](/help/troubleshooting).
