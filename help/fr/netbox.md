---
title: Import depuis NetBox
category: devices
order: 5
summary: Connexion à NetBox, choix des équipements, correspondance et synchronisation.
keywords: netbox import jeton api site rôle étiquette synchronisation dcim
---
Si vos commutateurs sont recensés dans NetBox, vous pouvez les importer dans SwitchMap avec leurs noms, adresses IP et nombre de ports. Rubrique **Recherche et import → NetBox** (administrateurs uniquement).

# Connexion {#token}

1. **URL de NetBox** : par exemple `https://netbox.company.local`.
2. **Jeton d’API** : créez-le dans NetBox : profil utilisateur (en haut à droite) → **API Tokens** → **Add a token**. Un jeton en **lecture seule** suffit. Les deux formats de jeton fonctionnent (classique et le nouveau `nbt_…`).
3. Si NetBox utilise un certificat auto-signé, décochez **Vérifier le certificat du serveur**.
4. Cliquez sur **Vérifier et enregistrer**.

Le jeton est stocké chiffré sur le serveur SwitchMap et n’est jamais envoyé au navigateur.

# Import {#import}

1. Choisissez les filtres : **site**, **rôle** (par exemple « Access switch »), **étiquette**. **Uniquement au statut « Active »** masque les équipements retirés et planifiés.
2. Cliquez sur **Afficher les équipements**.
3. Cochez ceux qu’il vous faut (les nouveaux équipements avec IP sont cochés par défaut) et cliquez sur **Importer la sélection**.

L’adresse IP provient de la **Primary IP** de l’équipement, le nombre de ports de ses interfaces physiques. Indiquez les réglages SNMP sur la même page : ils s’appliquent à tous les commutateurs importés.

# Correspondance {#matching}

Un équipement NetBox est considéré comme déjà ajouté si l’un de ces éléments correspond :

1. le lien (le commutateur a déjà été importé depuis NetBox) ;
2. ou l’adresse IP ;
3. ou le nom.

Pour ces équipements, vous voyez ce qui va changer. **Pour ceux déjà ajoutés, mettre à jour le nom et l’IP depuis NetBox** active la mise à jour. Le plan des ports, les connexions et l’historique ne changent pas.

# Synchronisation {#sync}

Le bloc **Commutateurs liés** : **Synchroniser maintenant** met à jour depuis NetBox les noms et IP de tous les commutateurs liés. **Automatiquement toutes les heures** le fait selon un planning. Les nouveaux équipements ne sont pas ajoutés automatiquement : seulement par import.

La page d’un commutateur lié comporte un lien **NetBox** vers sa fiche NetBox.
