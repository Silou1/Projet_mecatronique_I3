# Plan de correction du PCB et schema electronique

> Ce plan est a suivre dans une nouvelle session Claude Code.
> Pre-requis : EasyEDA Pro ouvert avec le projet Mecatronique.

---

## Phase 1 -- Connecter EasyEDA Pro au MCP

### Etape 1.1 : Lancer le serveur MCP
```bash
node ~/.easyeda-mcp/dist/mcp-server/index.js
```
Verifier que le message `WebSocket Server listening on port 15168` apparait.

### Etape 1.2 : Ouvrir EasyEDA Pro et le projet
1. Ouvrir EasyEDA Pro (/Applications/EasyEDA-Pro.app)
2. Ouvrir le projet Mecatronique
3. Double-cliquer sur Schematic1 pour ouvrir le schema

### Etape 1.3 : Connecter Claude
1. Menu Claude → Connect Claude
2. Verifier que la connexion est etablie (message dans le terminal du MCP)

### Etape 1.4 : Lancer Claude Code
Ouvrir une nouvelle session Claude Code pour qu'il detecte les outils MCP EasyEDA.

---

## Phase 2 -- Corriger le schema electrique

### Etape 2.1 : Lire l'etat actuel du schema
- Utiliser les outils `sch_read_*` pour lister tous les composants et verifier leur etat
- Identifier les IDs des fils a modifier (LED sur IO34, Servo sur IO35)
- Identifier le net label "+5" sur H2.4

### Etape 2.2 : Corriger le signal LED (IO34 → IO32)
1. Trouver le fil qui connecte U1 pin 5 (IO34) au label "Led"
2. Supprimer ce fil (`sch_delete_wire`)
3. Creer un nouveau fil de U1 pin 7 (IO32) vers le label "Led" (`sch_create_wire`)
4. Supprimer le label "Supp1" sur IO32 si present

### Etape 2.3 : Corriger le signal Servo (IO35 → IO33)
1. Trouver le fil qui connecte U1 pin 6 (IO35) au label "Servomot"
2. Supprimer ce fil (`sch_delete_wire`)
3. Creer un nouveau fil de U1 pin 8 (IO33) vers le label "Servomot" (`sch_create_wire`)
4. Supprimer le label "Supp2" sur IO33 si present

### Etape 2.4 : Corriger le net d'alimentation 5V
1. Trouver le net flag/label "+5" sur H2 pin 4
2. Modifier son nom de "+5" a "5V" (pour unifier avec le net des composants)

### Etape 2.5 : Mettre a jour le nom du composant U1
1. Modifier le nom/description de U1 : remplacer "WROVER" par "WROOM"
   (`sch_modify_component` avec le champ `name`)

### Etape 2.6 : Sauvegarder
- `sch_save` pour sauvegarder le schema

---

## Phase 3 -- Mettre a jour le PCB (si necessaire)

### Etape 3.1 : Ouvrir le PCB
- Double-cliquer sur PCB1
- Importer les changements du schema (Design → Import Changes from Schematic)

### Etape 3.2 : Re-router les pistes modifiees
- La piste LED passe de pin 5 a pin 7 (adjacents, re-routage court)
- La piste Servo passe de pin 6 a pin 8 (adjacents, re-routage court)
- La piste +5V doit rejoindre le rail 5V (si pas deja fait)

### Etape 3.3 : Sauvegarder et exporter
- Sauvegarder le PCB
- Exporter les PDF mis a jour (Schema + PCB)
- Exporter la nouvelle netlist

---

## Phase 4 -- Verification

### Etape 4.1 : Verifier la netlist corrigee
- Le net "Led" doit connecter U1.7 (IO32) a H1.4
- Le net "Servomot" doit connecter U1.8 (IO33) a U2.2
- Le net "5V" doit inclure H2.4, H1.3, U2.3, U3.10, U4.10, U6.14
- Le composant U1 doit s'appeler WROOM

### Etape 4.2 : Lancer un DRC (Design Rule Check)
- Verifier qu'il n'y a pas de nouvelles erreurs

---

## Phase 5 -- Adapter le code du jeu

### Etape 5.1 : Code ESP32 (Arduino C++)
A ecrire dans PlatformIO/src/main.cpp :
- Scan matrice 6x6 boutons avec gestion strapping pins
- Pilotage LEDs via IO32 (NeoPixel ou autre)
- Pilotage servo via IO33 (PWM)
- Commande moteurs X/Y via MCP23017 I2C (adresse 0x20)
  - Port A = moteur Y, Port B = moteur X
- Communication UART avec RPi (Serial a 115200 baud)
- Protocole de messages (format a definir)

### Etape 5.2 : Code RPi (Python)
Adapter main.py :
- Remplacer l'interface console par une interface serie (pyserial)
- Envoyer les coups de l'IA au ESP32
- Recevoir les appuis boutons du ESP32
- Garder le moteur de jeu et l'IA intacts

### Etape 5.3 : Tests
- Tester la communication UART entre RPi et ESP32
- Tester le scan de la matrice de boutons
- Tester le pilotage des moteurs
- Tester les LEDs et le servo

---

## Fichiers de reference

| Fichier | Contenu |
|---------|---------|
| `electronique/AUDIT_PCB.md` | 15 anomalies detaillees |
| `electronique/SOLUTIONS_CORRECTIONS.md` | Solutions hardware + software |
| `electronique/PIN_MAPPING_VERIFIE.md` | Mapping corrige + defines C++ |
| `electronique/GUIDE_MODIFICATIONS_EASYEDA.md` | Instructions pour jeanrdc |
| `electronique/SCHEMA_CORRIGE.md` | Schema ASCII de reference |
| `CLAUDE.md` | Instructions projet (mis a jour) |
