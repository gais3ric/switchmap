---
title: Installation et configuration
category: admin
order: 2
summary: Programmes d’installation pour Windows et Linux, le service, le fichier de réglages, l’accès réseau, HTTPS, les mises à jour.
keywords: installer programme d’installation service windows linux deb rpm ubuntu debian rhel réglages switchmap.conf port https caddy proxy certificat mise à jour journal logs
---
# Installation {#install}

Les programmes d’installation se trouvent dans la rubrique **Releases** du dépôt SwitchMap. Inutile d’installer Python : il est inclus dans le programme.

| Système | Fichier | Installation |
|---|---|---|
| Windows 10/11, Server 2016+ | `SwitchMap-Setup-X.Y.Z.exe` | Exécuter en tant qu’administrateur |
| Debian 12+, Ubuntu 22.04+ | `switchmap_X.Y.Z-1_amd64.deb` | `sudo apt install ./switchmap_X.Y.Z-1_amd64.deb` |
| RHEL, AlmaLinux, Rocky Linux 9+ | `switchmap-X.Y.Z-1.x86_64.rpm` | `sudo dnf install ./switchmap-X.Y.Z-1.x86_64.rpm` |

Le programme d’installation Windows demande d’où SwitchMap pourra être ouvert (uniquement depuis cet ordinateur ou depuis le réseau, auquel cas il ouvre le port dans le pare-feu) et le numéro de port.

> **Astuce :** Windows peut afficher l’avertissement SmartScreen « Éditeur inconnu » : le programme d’installation n’est pas signé avec un certificat payant. Cliquez sur **Informations complémentaires → Exécuter quand même**.

Après l’installation, ouvrez `http://localhost:5000` et créez un administrateur.

# Service {#service}

SwitchMap fonctionne comme un service : il démarre avec le système et redémarre après une panne.

| Action | Windows (PowerShell en administrateur) | Linux |
|---|---|---|
| État | `Get-Service SwitchMap` | `systemctl status switchmap` |
| Redémarrer | `Restart-Service SwitchMap` | `sudo systemctl restart switchmap` |
| Arrêter | `Stop-Service SwitchMap` | `sudo systemctl stop switchmap` |

Sous Windows, le service s’exécute avec le compte restreint **LocalService** ; sous Linux, avec l’utilisateur dédié `switchmap`, qui ne peut écrire que dans son dossier de données.

# Fichiers {#files}

| | Windows | Linux |
|---|---|---|
| Programme | `C:\Program Files\SwitchMap` | `/opt/switchmap` |
| Réglages | `C:\ProgramData\SwitchMap\switchmap.conf` | `/etc/switchmap/switchmap.conf` |
| Base de données | `C:\ProgramData\SwitchMap\switches.db` | `/var/lib/switchmap/switches.db` |
| Clés de chiffrement | `…\switchmap.secret` | `/var/lib/switchmap/switchmap.secret` |
| Sauvegardes | `…\backups` | `/var/lib/switchmap/backups` |
| Journal du programme | `…\logs\switchmap.log` | `/var/lib/switchmap/logs/switchmap.log` et `journalctl -u switchmap` |

La commande `switchmap --paths` affiche les chemins sur un serveur donné.

# Réglages {#config}

Le fichier `switchmap.conf` contient des lignes du type `CLÉ=valeur`. Redémarrez le service après une modification.

| Clé | Valeur |
|---|---|
| `SWITCHMAP_HOST` | `127.0.0.1` : cet ordinateur uniquement ; `0.0.0.0` : depuis le réseau |
| `SWITCHMAP_PORT` | Port de l’interface web, `5000` par défaut |
| `SWITCHMAP_HTTPS` | `1` : SwitchMap fonctionne derrière un proxy HTTPS |
| `SWITCHMAP_PROXY` | `1` : prendre l’adresse de l’utilisateur dans les en-têtes du proxy |
| `SWITCHMAP_DATA` | Un autre dossier de données |
| `SWITCHMAP_LOG_LEVEL` | Niveau de détail du journal : `DEBUG`, `INFO`, `WARNING` |
| `SWITCHMAP_UPDATE_CHECK` | `0` : ne jamais vérifier les nouvelles versions (réseau isolé) |

Sous Linux, pour autoriser l’accès réseau, après `SWITCHMAP_HOST=0.0.0.0` ouvrez le port dans le pare-feu : `sudo firewall-cmd --permanent --add-port=5000/tcp && sudo firewall-cmd --reload` (RHEL) ou `sudo ufw allow 5000/tcp` (Ubuntu).

# HTTPS {#https}

SwitchMap parle HTTP. Si l’on s’y connecte depuis d’autres ordinateurs, placez un proxy HTTPS devant, sinon les mots de passe circulent en clair sur le réseau. Le plus simple est **Caddy** (gratuit, il obtient et renouvelle les certificats tout seul).

1. Dans `switchmap.conf`, indiquez :
   ```
   SWITCHMAP_HOST=127.0.0.1
   SWITCHMAP_HTTPS=1
   SWITCHMAP_PROXY=1
   ```
   puis redémarrez SwitchMap.
2. Installez Caddy : sous Debian et Ubuntu, `sudo apt install caddy` ; sur les autres systèmes, suivez les instructions de caddyserver.com.
3. Configurez le `Caddyfile` (sous Linux, `/etc/caddy/Caddyfile`) :
   ```
   switchmap.company.local {
       tls internal
       reverse_proxy 127.0.0.1:5000
   }
   ```
   Avec `tls internal`, Caddy émet son propre certificat pour le réseau interne (les navigateurs demandent une fois de lui faire confiance). Pour un domaine accessible depuis Internet, supprimez cette ligne : Caddy obtiendra lui-même un certificat Let’s Encrypt.
4. Rechargez Caddy (`sudo systemctl reload caddy`) et ouvrez `https://switchmap.company.local`.

Si vous avez déjà nginx ou IIS, configurez un proxy inverse vers `http://127.0.0.1:5000` qui transmet les en-têtes `X-Forwarded-For` et `X-Forwarded-Proto`.

# Mise à jour {#update}

Installez la nouvelle version par-dessus l’ancienne avec le même programme d’installation ou paquet. Les données et réglages sont conservés, et une sauvegarde est créée automatiquement avant toute modification de la structure de la base. La version est affichée dans le menu de profil.

Une fois par jour, SwitchMap vérifie sur GitHub si une nouvelle version est sortie et affiche aux administrateurs un bandeau « Une nouvelle version est disponible » avec un lien vers la page de téléchargement. Il ne télécharge ni n’installe rien lui-même et ne transmet aucune information sur votre réseau. Vous pouvez désactiver la vérification dans **Réglages → Mises à jour**, ou l’interdire complètement sur un réseau isolé avec `SWITCHMAP_UPDATE_CHECK=0` dans le fichier de réglages. Pour passer par un proxy, définissez la variable d’environnement `HTTPS_PROXY`.

# Désinstallation {#uninstall}

La désinstallation ne touche pas aux données : la base, les clés et les sauvegardes restent dans le dossier de données. Supprimez-le à la main si vous n’en avez plus besoin.
