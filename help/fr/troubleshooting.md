---
title: Dépannage
category: problems
order: 1
summary: Un commutateur ne répond pas, erreurs SNMPv3, pas d’adresses MAC, notifications qui n’arrivent pas, etc.
keywords: erreur ne fonctionne pas pas de réponse timeout snmp v3 mot de passe utilisateur mac pas de données notifications n’arrivent pas telegram e-mail erreurs de port lent
---
# Un commutateur ne répond pas en SNMP {#no-response}

« Le commutateur n’a pas répondu » signifie qu’aucune réponse n’est arrivée dans le délai prévu. Étape par étape :

1. **Y a-t-il une connexion ?** Sur la page du commutateur, cliquez sur **Vérifier la joignabilité**. « Injoignable » signifie aucune réponse ni en SNMP ni au ping : le problème vient du réseau, de l’alimentation ou de l’adresse. « Ping uniquement » signifie que le réseau fonctionne et que le problème vient du SNMP (étapes 2 à 5).
2. **L’UDP 161 est-il ouvert ?** Un pare-feu entre le serveur SwitchMap et le commutateur doit laisser passer l’UDP 161 vers le commutateur et les réponses en retour.
3. **L’adresse du serveur est-elle autorisée sur le commutateur ?** De nombreux commutateurs ne répondent en SNMP qu’aux adresses d’une liste (ACL). Ajoutez l’IP du serveur SwitchMap.
4. **Les identifiants correspondent-ils ?** La community et les mots de passe sont sensibles à la casse. Un commutateur qui reçoit une mauvaise community se tait simplement : l’erreur ressemble donc à une absence de connectivité.
5. **SNMP est-il activé ?** Voir [Activer SNMP](/help/snmp-vendors).

> **Astuce :** si le ping fonctionne mais pas SNMP, c’est presque toujours les points 3 à 5. SwitchMap l’indique directement dans l’événement « commutateur injoignable ».

# Un commutateur déconnecté répond au ping {#fake-ping}

Le statut **En ligne** signifie que le commutateur a répondu en SNMP. S’il répond seulement au ping, le statut est **Ping uniquement** (jaune).

Si « Ping uniquement » s’affiche pour un commutateur assurément déconnecté, c’est quelqu’un d’autre qui répond au ping. Les VPN et proxys en mode TUN (Happ, v2rayN, sing-box et autres) le font : ils interceptent le trafic et répondent au ping pour n’importe quelle adresse. Vérifiez depuis le serveur : `ping 10.123.45.67` — si une adresse inexistante « répond », c’est la cause. Excluez les réseaux locaux du VPN (option « Contourner le LAN » ou routes pour 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) ou désactivez le mode TUN.

# Erreurs SNMPv3 {#v3}

| Message | À vérifier |
|---|---|
| utilisateur SNMPv3 inconnu | Le nom d’utilisateur ; l’utilisateur existe-t-il sur le commutateur |
| mot de passe ou protocole d’authentification incorrect | Le mot de passe et l’algorithme (SHA, SHA-256, MD5) |
| mot de passe ou protocole de chiffrement incorrect | Le mot de passe et l’algorithme de chiffrement (AES128, DES) |
| niveau de sécurité non pris en charge | Le groupe du commutateur a un autre niveau : par exemple, l’utilisateur a été créé sans chiffrement mais il est activé dans SwitchMap |

# Pas d’adresses MAC ni de VLAN {#no-mac}

- Les équipements n’apparaissent qu’une fois leur MAC dans la table du commutateur : l’équipement doit être allumé et émettre des données.
- Sur **Cisco**, les adresses MAC de chaque VLAN sont stockées séparément : en SNMPv3, autorisez les contextes VLAN (voir [Cisco](/help/snmp-vendors#cisco)).
- Les commutateurs simples et non administrables (« smart ») ne fournissent parfois pas du tout la table MAC en SNMP.

# Pas d’utilisation des ports {#no-util}

L’utilisation se calcule à partir de la différence des compteurs de trafic entre deux interrogations. Après la première, elle n’existe pas encore : attendez la deuxième ou activez l’[interrogation périodique](/help/monitoring#polling).

# Erreurs sur un port {#port-errors}

Des erreurs de réception et d’émission en hausse signalent généralement un problème physique :

- un câble endommagé ou trop long, un mauvais connecteur, une prise murale défectueuse ;
- une incohérence de vitesse ou de duplex (un côté en « auto », l’autre réglé à la main) ;
- un module SFP défectueux ou un connecteur fibre sale.

Commencez par remplacer le cordon de brassage et vérifiez les réglages de vitesse aux deux extrémités.

# Les notifications n’arrivent pas {#notifications}

1. L’**Interrogation périodique** est-elle activée dans les **Réglages** ? Sans interrogations, pas d’événements.
2. Le canal est-il activé et les bons événements sont-ils choisis sur la page **Notifications** ?
3. Consultez l’**Historique des envois** en bas de la page : la cause de l’erreur y figure.
4. **Telegram :** le serveur doit pouvoir accéder à `api.telegram.org` (HTTPS). Sinon, configurez un proxy.
5. **E-mail :** Gmail, Yandex, Mail.ru et Outlook exigent un mot de passe d’application, pas votre mot de passe habituel.
6. Vérifiez les filtres : **Ports importants uniquement**, **Heures de silence**, **Port instable**.

# Impossible de se connecter {#login}

- Après 5 tentatives échouées, la connexion avec ce nom est bloquée pendant 5 minutes.
- Un mot de passe administrateur oublié se redéfinit depuis la ligne de commande du serveur : voir [Utilisateurs](/help/users#reset).

# Où trouver le journal du programme {#logs}

Les détails des pannes figurent dans le journal du programme : `logs\switchmap.log` dans le dossier de données (voir [Installation et configuration](/help/installation#files)). Sous Linux, également `journalctl -u switchmap`. Pour un journal plus détaillé, indiquez `SWITCHMAP_LOG_LEVEL=DEBUG` dans le fichier de réglages et redémarrez le service.
