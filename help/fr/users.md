---
title: Utilisateurs et rôles
category: admin
order: 1
summary: Administrateurs et observateurs, mots de passe, blocage et que faire en cas d’oubli de mot de passe.
keywords: utilisateur rôle administrateur observateur mot de passe connexion bloquer réinitialiser oublié session
---
# Rôles {#roles}

| Rôle | Peut |
|---|---|
| **Administrateur** | Tout : ajouter et modifier des commutateurs, les réglages, les notifications, les utilisateurs, restaurer des sauvegardes |
| **Observateur** | Consulter toutes les pages, interroger les commutateurs, rechercher des équipements, vérifier la joignabilité. Ne modifie rien |

Le rôle d’observateur convient aux équipes d’astreinte, au support et aux prestataires. Les boutons de modification leur sont masqués, et le serveur vérifie en plus les droits à chaque action.

# Ajouter un utilisateur {#add}

Rubrique **Utilisateurs** (menu de profil → **Utilisateurs**, administrateurs uniquement) → **Ajouter un utilisateur** : nom, rôle, mot de passe d’au moins 8 caractères. Communiquez le mot de passe à l’utilisateur : il pourra le changer lui-même dans le menu de profil.

# Blocage et mots de passe {#manage}

- **Bloquer** : l’utilisateur perd immédiatement l’accès mais reste dans la liste (ses actions dans le journal sont conservées).
- **Définir le mot de passe** : un nouveau mot de passe ; toutes les sessions de l’utilisateur sur d’autres ordinateurs sont fermées.
- Le dernier administrateur ne peut être ni supprimé, ni bloqué, ni rétrogradé : il y a ainsi toujours un moyen de se connecter.

Après 5 tentatives de connexion échouées d’affilée, la connexion avec ce nom depuis cette adresse est temporairement bloquée. Les tentatives échouées sont consignées dans le journal des modifications.

# Mot de passe administrateur oublié {#reset}

Définissez un nouveau mot de passe en ligne de commande sur le serveur où SwitchMap est installé :

| Système | Commande |
|---|---|
| Windows (en administrateur) | `& "C:\Program Files\SwitchMap\switchmap.exe" reset-password admin` |
| Linux | `sudo switchmap reset-password admin` |
| Depuis les sources | `python app.py reset-password admin` |

S’il n’existe pas d’utilisateur portant ce nom, la commande propose de créer un administrateur.

# Sessions {#sessions}

Sans **Se souvenir de moi pendant 30 jours**, une session se termine après 12 heures d’inactivité ; avec, au bout de 30 jours.
