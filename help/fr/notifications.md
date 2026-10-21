---
title: Notifications Telegram et e-mail
category: monitoring
order: 2
summary: Créer un bot, trouver une discussion, configurer l’e-mail et ne pas crouler sous les messages.
keywords: notifications alertes telegram bot botfather discussion groupe e-mail smtp gmail yandex mot de passe d’application heures de silence port instable
---
Les notifications signalent les mêmes événements que la cloche : commutateur injoignable, port tombé, utilisation élevée, erreurs, surchauffe. Elles se configurent sur la page **Notifications** (icône avion en papier, administrateurs uniquement).

> **Attention :** les événements n’apparaissent que lorsque les commutateurs sont interrogés. Activez l’**Interrogation périodique** dans les **Réglages**, sinon il n’y aura rien à signaler.

# Telegram {#telegram}

1. Dans Telegram, ouvrez **@BotFather**, envoyez `/newbot` et choisissez un nom pour le bot. BotFather répond avec un **jeton** du type `123456789:AAH…` : collez-le dans **Jeton du bot**.
2. Envoyez un message quelconque à votre bot (par exemple `/start`). Pour un groupe : ajoutez le bot au groupe et écrivez-y quelque chose.
3. Cliquez sur **Rechercher les discussions** et ajoutez celle qu’il vous faut. Vous pouvez aussi saisir un identifiant de discussion à la main : ceux des groupes commencent par un signe moins.
4. Activez le canal, choisissez les événements et cliquez sur **Enregistrer**. **Envoyer un message de test** vérifie que tout fonctionne.

Le serveur SwitchMap a besoin d’un accès HTTPS à `api.telegram.org`. S’il accède à Internet via un proxy, indiquez-le dans **Proxy HTTP** (`http://proxy:3128` ou `http://identifiant:motdepasse@proxy:3128`).

# E-mail {#email}

1. Cliquez sur le bouton de votre service de messagerie : le serveur, le port et le chiffrement se remplissent. Pour un serveur d’entreprise, indiquez-les vous-même.
2. L’**identifiant** est généralement l’adresse e-mail. **Mot de passe d’application** : voir ci-dessous.
3. **Destinataires** : une ou plusieurs adresses séparées par des virgules.
4. Cliquez sur **Envoyer un e-mail de test**, puis sur **Enregistrer**.

| Port | Chiffrement |
|---|---|
| 465 | SSL |
| 587 | STARTTLS |
| 25 | Aucun (serveurs internes uniquement) |

> **Attention :** Gmail, Yandex, Mail.ru et Outlook n’acceptent pas le mot de passe habituel de la messagerie. Créez un **mot de passe d’application** dans les paramètres de sécurité de la boîte et utilisez-le.

# Éviter trop de messages {#filters}

| Réglage | Effet |
|---|---|
| Choix des événements | Par exemple, seulement « commutateur injoignable » et « port tombé » |
| Messages de rétablissement | Signaler ou non « port actif », « de nouveau joignable » |
| Ports importants uniquement | Seulement les ports avec une description sur le commutateur, une connexion sur le plan ou un trunk : pas les ordinateurs des utilisateurs |
| Heures de silence | La nuit, seuls les événements critiques sont envoyés |
| Port instable | Un port qui tombe et remonte souvent en une heure produit un seul avertissement au lieu de dizaines de messages |

Plusieurs événements d’une même interrogation arrivent en un seul message. Si le réseau ou Telegram étaient indisponibles, les messages partent plus tard : SwitchMap réessaie. Les anciens événements (plus d’un jour) ne sont pas envoyés en retard : ils figurent dans le journal des événements.

# Historique des envois {#log}

En bas de la page : les derniers messages envoyés et les erreurs. La cause d’une erreur est expliquée simplement : « Telegram a refusé le jeton », « le serveur a refusé l’identifiant ou le mot de passe », etc.
