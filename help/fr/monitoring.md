---
title: Supervision et alertes
category: monitoring
order: 1
summary: Interrogation planifiée, utilisation et erreurs des ports, CPU et température, seuils d’événements, graphiques.
keywords: interrogation intervalle utilisation trafic erreurs cpu mémoire température seuil événement graphique statistiques poe
---
# Interrogation périodique {#polling}

Ouvrez les **Réglages** (l’engrenage en bas du menu) et activez **Interroger périodiquement les commutateurs en SNMP**. SwitchMap interrogera tous les commutateurs ayant une adresse IP à l’intervalle choisi.

| Intervalle | Quand l’utiliser |
|---|---|
| 1–2 minutes | Un petit réseau où des graphiques détaillés sont utiles |
| 5 minutes | Presque tout le monde |
| 10–15 minutes | Des centaines de commutateurs ou des liaisons lentes |

Sans interrogation périodique, les données ne sont mises à jour que par le bouton **Interroger en SNMP** de la page du commutateur.

**Noms de ports, descriptions et VLAN** — à quelle fréquence lire les données qui changent rarement : noms et descriptions des ports, VLAN, voisins LLDP (pour la topologie).

| Mode | Quand le choisir |
|---|---|
| À chaque interrogation | Le réseau est en construction, en extension ou en réparation — les changements apparaissent tout de suite |
| Une fois par heure | Le réseau est stable — presque deux fois moins de requêtes vers les commutateurs, moins de charge sur leur processeur |

L’état des ports, le trafic, les erreurs et les adresses MAC sont lus à chaque interrogation dans les deux modes. **Interroger en SNMP** sur la page du commutateur lit toujours tout — utilisez-le après une modification sur un commutateur au lieu d’attendre une heure.

# Ce qui est mesuré {#metrics}

- **État du port** : lien ou pas de lien. Un changement crée l’événement « port tombé » ou « port actif ».
- **Utilisation** : le débit en pourcentage de la vitesse du port. Calculée à partir de la différence des compteurs entre deux interrogations, elle apparaît donc dès la deuxième.
- **Erreurs** : le nombre d’erreurs de réception et d’émission accumulées depuis la dernière interrogation.
- **CPU, mémoire, température** : si le commutateur les communique en SNMP (selon le constructeur).
- **PoE** : la consommation par port, si le commutateur prend en charge POWER-ETHERNET-MIB.

# Seuils d’alerte {#thresholds}

Dans **Réglages → Seuils d’alerte** :

| Seuil | Événement |
|---|---|
| Utilisation du port, % | Trafic au-dessus de ce pourcentage de la vitesse du port |
| Erreurs du port entre deux interrogations | Les erreurs augmentent : souvent un câble défectueux |
| Charge CPU, % | Le CPU du commutateur est surchargé |
| Température, °C | Surchauffe |

Un événement est créé quand un seuil est dépassé et un autre quand la valeur revient à la normale. **0** désactive un seuil. Si un commutateur ne répond plus, l’événement « commutateur injoignable » précise s’il répond encore au ping (le problème vient alors des réglages SNMP) ou non (il vient alors du réseau ou de l’alimentation).

# Graphiques {#charts}

Sur la page du commutateur, le bouton **Statistiques** ouvre les graphiques :

- le débit de n’importe quel port (entrant et sortant) ;
- le CPU, la mémoire et la température du commutateur.

Les périodes vont d’une heure à un an. Les longues périodes utilisent les données horaires, d’où un affichage rapide. Combien d’historique est conservé : voir [Données et sauvegardes](/help/backups#retention).

# Événements {#events}

Tous les événements apparaissent sous la cloche de la barre supérieure et dans la colonne **Alertes** de la page d’accueil. Pour les recevoir par Telegram ou e-mail, configurez les [notifications](/help/notifications).
