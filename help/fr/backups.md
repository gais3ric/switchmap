---
title: Données, sauvegardes et journal des modifications
category: data
order: 1
summary: Durée de conservation de l’historique, création et restauration des sauvegardes, journal des modifications et annulation.
keywords: sauvegarde backup restaurer conservation historique journal audit annuler migration base compacter
---
# Conservation de l’historique {#retention}

Rubrique **Données et sauvegardes** (icône base de données). Chaque interrogation enregistre le trafic, les erreurs et l’état des ports. Pour que la base ne grossisse pas indéfiniment :

| Données | Par défaut | Ensuite |
|---|---|---|
| Historique détaillé (chaque interrogation) | 7 jours | Regroupé en valeurs horaires (moyenne et maximum) |
| Historique horaire | 365 jours | Supprimé |
| Événements | 90 jours | Supprimés |

La maintenance de la base s’exécute automatiquement toutes les heures. **Lancer la maintenance** la démarre immédiatement ; **compacter le fichier de la base** libère de l’espace disque après la suppression d’anciennes données.

# Sauvegardes {#backups}

- **Sauvegarde automatique quotidienne** : une fois par jour ; on conserve autant de sauvegardes qu’indiqué dans **Sauvegardes à conserver** (14 par défaut), les plus anciennes sont supprimées.
- **Créer une sauvegarde** : à la main, par exemple avant de grosses modifications.
- Une sauvegarde est aussi créée automatiquement : au démarrage d’une nouvelle version si la structure de la base change, et avant la restauration d’une autre sauvegarde.

Chaque sauvegarde peut être **téléchargée**, **restaurée** ou **supprimée**. **Restaurer depuis un fichier** envoie une sauvegarde téléchargée auparavant ou créée sur un autre serveur.

> **Attention :** les sauvegardes sont sur le même disque que la base (dossier `backups` dans le dossier de données). Téléchargez-les régulièrement ou copiez le dossier sur un autre serveur : des copies à côté de la base ne survivent pas à une panne de disque.

Les clés de chiffrement (fichier `switchmap.secret`) **ne sont pas** incluses dans les sauvegardes : une sauvegarde peut donc être conservée et transmise sans risque. Mais sans ce fichier, les mots de passe SNMPv3, e-mail, Telegram et NetBox de la sauvegarde devront être saisis à nouveau. Conservez `switchmap.secret` séparément, en lieu sûr.

# Restauration {#restore}

Cliquez sur **Restaurer** à côté de la sauvegarde voulue. La base actuelle est d’abord enregistrée dans une sauvegarde distincte (« avant restauration »), on peut donc annuler une restauration en restaurant cette sauvegarde. Les utilisateurs et leurs mots de passe ne sont pas rétablis si la sauvegarde n’en contient pas.

# Migrer vers un autre serveur {#move}

1. Arrêtez SwitchMap sur l’ancien serveur.
2. Copiez `switches.db` et `switchmap.secret` depuis le dossier de données.
3. Installez SwitchMap sur le nouveau serveur, arrêtez le service, placez les fichiers dans son dossier de données et démarrez le service.

Où se trouve le dossier de données : voir [Installation et configuration](/help/installation#files).

# Journal des modifications {#audit}

La rubrique **Journal des modifications** (icône horloge) montre qui a modifié quoi et quand : commutateurs, connexions, réglages, utilisateurs, ainsi que les tentatives de connexion échouées. On peut filtrer par commutateur et par type.

**Annuler** à côté d’une modification de commutateur rétablit les valeurs précédentes. Un commutateur supprimé peut être **restauré** avec ses connexions et ses équipements.
