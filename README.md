<p align="center"><img src="assets/tatamidesk_icon.png" width="96" alt="Tatami Desk"></p>

# Tatami Desk

> **Auteur :** Vincent Chapeau
> **Licence :** MIT
> **Plateforme :** Windows 10 / 11

Tatami Desk range les raccourcis, fichiers et dossiers du bureau Windows dans des **zones à onglets**, posées sur le fond d'écran. Comme les tatamis découpent une pièce en rectangles bien ordonnés, l'application découpe le bureau en zones claires : un onglet par outil, par projet ou par thème.

L'application est légère : elle ne fait aucun calcul quand on ne la touche pas, n'envoie rien sur Internet et garde toutes ses données en local.

![Thèmes](assets/screenshot_themes.png)

---

## Fonctionnalités

**Zones et onglets**
- Glisser un raccourci, un fichier ou un dossier du bureau dans une zone : il quitte le bureau et s'affiche dans l'onglet actif.
- Plusieurs onglets par zone, séparés et cliquables. Survoler un onglet pendant un glisser l'ouvre, lâcher sur son nom range l'élément dedans.
- Fusion : amener une zone par sa barre sur la barre d'une autre transforme ses onglets en onglets de l'autre. « Détacher en nouvelle zone » fait l'inverse.
- Repli d'une zone sur sa barre (double-clic), tri par nom, couleur d'accent par zone.
- Éléments Windows : Corbeille (avec sa vraie icône vide ou pleine et « Vider la corbeille »), Ce PC, Réseau, Documents, Téléchargements, Panneau de configuration, Paramètres.

**Bureau**
- Double-clic sur un endroit vide du bureau : masque les icônes et/ou les zones, re-double-clic pour tout réafficher. Les icônes ne sont cachées que temporairement.
- Les zones restent visibles avec Win+D.

**Disposition**
- Aimantation entre zones et aux bords de l'écran, avec espacement régulier.
- Redimensionnement calé sur la taille des zones voisines et sur un nombre entier de colonnes et de lignes d'icônes. « Même taille que » pour aligner deux zones d'un clic. Maj pour couper l'aimant.
- Position mémorisée **pour chaque configuration d'écrans** : les zones reprennent leur place quand on branche ou débranche un écran. « Envoyer vers l'écran » dans le clic droit.

**Rangement automatique**
- Règles par type (dossiers, documents, images, musique et vidéo, archives, raccourcis, liens web) ou par nom, vers la zone et l'onglet de son choix.
- Rangement à la demande ou automatique pour les nouveaux éléments qui arrivent sur le bureau.

**Apparence**
- 13 thèmes : Sombre, Classique, Verre clair, Minimal, Néon, Graphite, Zen (papier washi), Zen nuit, Futuriste (HUD), Néon Sunset, Palmiers au crépuscule, Cyber, Rouge & anthracite.
- Chaque thème est personnalisable en direct : opacité, couleurs, accent, arrondi, forme, bordure, halo, style des onglets, police, décoration.
- Flou d'arrière-plan géré par Windows (aucun coût pour l'application).

**Sécurité des données**
- Sauvegarde quotidienne de la disposition (15 jours gardés) et restauration depuis les paramètres.
- Les fichiers rangés sont stockés dans `%APPDATA%\TatamiDesk\items` et peuvent être remis sur le bureau à tout moment.

![Paramètres](assets/screenshot_settings.png)

---

## Installation

### Option 1 : l'installeur Windows `TatamiDesk-Setup.exe` (recommandé)

1. Télécharger `TatamiDesk-Setup.exe` dans la page [Releases](../../releases).
2. Double-cliquer dessus pour lancer l'assistant d'installation (aucune ligne de commande requise). Windows peut afficher « Windows a protégé votre ordinateur » car l'exécutable n'est pas signé : cliquer sur « Informations complémentaires » puis « Exécuter quand même ».
3. L'installeur installe Tatami Desk, crée le raccourci dans le menu Démarrer et propose le lancement automatique au démarrage de Windows.

### Option 2 : exécutable portable (`TatamiDesk.exe`)

1. Télécharger `TatamiDesk.exe` dans la page [Releases](../../releases).
2. Le lancer directement (sans installation) ou utiliser **Paramètres > Général > Installer**.

### Option 3 : depuis le code source

```
pip install -r requirements.txt
```
```
python tatamidesk.pyw
```

---

## Utilisation rapide

| Action | Geste |
|---|---|
| Ouvrir les paramètres | Double-clic sur l'icône près de l'horloge |
| Afficher / masquer toutes les zones | Clic sur l'icône près de l'horloge |
| Nouvelle zone | Clic droit sur une zone ou sur l'icône près de l'horloge |
| Nouvel onglet | « + » à droite de la barre d'onglets |
| Renommer un onglet | Clic droit sur l'onglet |
| Déplacer une zone | Glisser sa barre d'onglets |
| Fusionner deux zones | Glisser la barre d'une zone sur la barre d'une autre |
| Replier une zone | Double-clic sur sa barre |
| Couper l'aimant | Maintenir Maj pendant le déplacement |
| Tout masquer | Double-clic sur un endroit vide du bureau |

---

## Mise à jour

La configuration (`%APPDATA%\TatamiDesk`) est séparée du programme. Pour mettre à jour : quitter Tatami Desk (clic droit sur l'icône près de l'horloge), lancer le nouvel `TatamiDesk.exe`, puis **Paramètres > Général > Installer**.

---

## Compiler l'exécutable

L'exécutable est construit automatiquement par GitHub Actions à chaque version publiée (tag `v*`). Pour le construire à la main sous Windows :

```
pip install -r requirements.txt pyinstaller
```
```
python -m PyInstaller --onefile --windowed --name TatamiDesk --icon assets/tatamidesk.ico tatamidesk.pyw
```

L'exécutable se trouve ensuite dans `dist\TatamiDesk.exe`.

---

## Licence

MIT, voir [LICENSE](LICENSE).
