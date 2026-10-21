---
title: Présentation de l’interface
category: start
order: 2
summary: Où se trouve chaque chose : menu, recherche, événements, réglages et langue.
keywords: menu navigation pages icônes thème langue raccourcis clavier
---
# Menu latéral {#menu}

| Icône | Rubrique | Contenu |
|---|---|---|
| Serveur | Commutateurs | La liste des commutateurs avec leur disponibilité, leur utilisation et leurs alertes. C’est ici qu’on en ajoute. |
| Schéma | Topologie | Un plan des liens entre commutateurs basé sur LLDP. |
| Horloge | Journal des modifications | Qui a modifié quoi et quand ; annulation des modifications. |
| Base de données | Données et sauvegardes | Conservation de l’historique, sauvegardes, restauration. |
| Radar | Recherche et import | Recherche sur le réseau et import depuis NetBox (administrateurs uniquement). |
| Avion en papier | Notifications | Messages Telegram et e-mail (administrateurs uniquement). |
| Loupe | Rechercher un équipement | Recherche par MAC, IP, nom et description de port. |

En bas du menu : **Aide**, le bascule thème clair/sombre, les **Réglages** (interrogation et seuils d’alerte) et votre profil.

# Profil et langue {#language}

Cliquez sur le cercle avec vos initiales en bas du menu. Vous pouvez y changer votre mot de passe, ouvrir l’aide et choisir la **langue de l’interface**. « Comme le système » utilise la langue du navigateur, qui correspond généralement à celle du système d’exploitation.

Le journal des modifications, les événements et les messages Telegram et e-mail sont rédigés dans une langue commune : un administrateur la choisit dans **Réglages → Langue**.

# Événements {#events}

La cloche de la barre supérieure montre les événements récents : un port est tombé ou remonté, utilisation élevée, erreurs sur un port, commutateur injoignable. Le chiffre sur la cloche indique les non lus. Cliquer sur un événement ouvre le commutateur et met le port en évidence.

# Raccourcis clavier {#keys}

| Touches | Action |
|---|---|
| [[Ctrl]] + [[K]] ou [[/]] | Rechercher un équipement |
| [[Échap]] | Fermer une fenêtre ou un menu |
| [[↑]] [[↓]] [[Entrée]] | Choisir un résultat de recherche |

# Rôles {#roles}

Un **Administrateur** peut tout faire. Un **Observateur** voit toutes les pages et peut interroger les commutateurs, mais ne peut rien modifier : les boutons de modification lui sont masqués. En savoir plus : [Utilisateurs et rôles](/help/users).
