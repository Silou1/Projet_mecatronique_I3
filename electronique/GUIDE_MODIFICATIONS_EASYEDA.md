# Guide de modifications EasyEDA -- Pour jeanrdc

> **Objectif** : Corriger le schema et le PCB sur EasyEDA pour refleter le materiel reel
> et les corrections identifiees par l'audit.
>
> **Projet EasyEDA** : `mecatronique` (Sheet_1, rev 1.0, 2026-02-16)
>
> **Temps estime** : ~30 minutes pour le schema, pas de changement au routage PCB

---

## Tableau des modifications

| # | Quoi | Ou | Avant | Apres | Priorite |
|---|------|-----|-------|-------|----------|
| 1 | Remplacer composant ESP32 | U1 | ESP32-WROVER-Dev | ESP32-WROOM | Haute |
| 2 | Reconnecter signal LED | U1 → H1 | IO34 (pin 5) | **IO32** (pin 7) | Critique |
| 3 | Reconnecter signal Servo | U1 → U2 | IO35 (pin 6) | **IO33** (pin 8) | Critique |
| 4 | Corriger net alimentation | H2.4 | "+5" | **"5V"** | Critique |
| 5 | Mettre a jour labels spare | H1 | SUPP1/SUPP2 libres | SUPP1=LED, SUPP2=SERVO | Moyenne |
| 6 | Documenter GPIO16/17 | U1 | Non affiches | Marquer comme disponibles | Basse |

---

## Modification 1 -- Remplacer le composant ESP32

**Probleme** : Le composant importe est un ESP32-WROVER-Dev. Le module reel est un ESP32-WROOM.

**Etapes dans EasyEDA** :

1. Cliquer sur le composant U1 (le gros module ESP32 a droite du schema)
2. Verifier le nom : il dit "ESP32-WROVER-DEV FREENOVE MODULE V1.6 LBOT"
3. **Option A (recommandee)** : Changer uniquement le texte du composant
   - Double-cliquer sur le nom du composant
   - Remplacer "WROVER" par "WROOM" dans le nom et la description
   - Le footprint (empreinte 40 pins) est **identique**, donc pas besoin de changer le composant lui-meme
4. **Option B (plus propre)** : Supprimer U1 et reimporter un composant WROOM
   - Attention : il faudra reconnecter tous les fils (12 boutons, I2C, UART, LED, servo, spare)
   - Deconseille sauf si tu veux refaire les connexions

**Pourquoi le footprint ne change pas** : Les cartes Freenove WROVER et WROOM ont exactement le meme brochage 40 pins. Seul le module ESP32 dessus est different (WROVER a du PSRAM en plus, qui utilise GPIO16/17 en interne). Le PCB physique est donc compatible tel quel.

---

## Modification 2 -- Reconnecter le signal LED (CRITIQUE)

**Probleme** : GPIO34 (IO34, pin 5) est un pin **input-only**. Il ne peut pas emettre de signal pour piloter des LEDs (NeoPixel ou autre).

**Etapes dans EasyEDA** :

1. Trouver le fil qui va de U1 pin 5 (IO34) vers le label "Led"
2. **Supprimer** ce fil
3. Tracer un nouveau fil depuis **U1 pin 7 (IO32)** vers le label "Led"
4. Supprimer le label "Supp1" qui etait sur IO32 (pin 7) car ce pin n'est plus spare
5. Le signal "Led" arrive toujours sur H1.4 via le label -- pas besoin de toucher H1

**Verification** : Apres modif, le net "Led" doit connecter U1 pin 7 (IO32) a H1 pin 4.

**Schema avant/apres** :
```
AVANT :                          APRES :
U1 pin 5 (IO34) ---[Led]        U1 pin 5 (IO34) --- (rien)
U1 pin 7 (IO32) ---[Supp1]      U1 pin 7 (IO32) ---[Led]
```

---

## Modification 3 -- Reconnecter le signal Servo (CRITIQUE)

**Probleme** : GPIO35 (IO35, pin 6) est aussi **input-only**. Il ne peut pas generer de PWM pour le servo SG90.

**Etapes dans EasyEDA** :

1. Trouver le fil qui va de U1 pin 6 (IO35) vers le label "Servomot"
2. **Supprimer** ce fil
3. Tracer un nouveau fil depuis **U1 pin 8 (IO33)** vers le label "Servomot"
4. Supprimer le label "Supp2" qui etait sur IO33 (pin 8) car ce pin n'est plus spare
5. Le label "Servomot" rejoint toujours U2 pin 2 (GPIO du servo) -- pas besoin de toucher U2

**Verification** : Apres modif, le net "Servomot" doit connecter U1 pin 8 (IO33) a U2 pin 2.

**Schema avant/apres** :
```
AVANT :                              APRES :
U1 pin 6 (IO35) ---[Servomot]       U1 pin 6 (IO35) --- (rien)
U1 pin 8 (IO33) ---[Supp2]          U1 pin 8 (IO33) ---[Servomot]
```

---

## Modification 4 -- Corriger le net d'alimentation 5V (CRITIQUE)

**Probleme** : Le connecteur d'alimentation H2 pin 4 utilise le label "+5", mais tous les composants (servo, MCP23017, A4988, LEDs) utilisent le label "5V". Dans EasyEDA, **deux labels differents = deux nets separees = pas de connexion electrique**.

**Resultat** : L'alimentation externe 5V n'arrive peut-etre pas aux composants.

**Etapes dans EasyEDA** :

1. Trouver le label "+5" qui est sur le fil de H2 pin 4
2. **Double-cliquer** sur le label "+5"
3. Changer le texte en **"5V"** (exactement comme les autres)
4. Verifier que le net s'appelle maintenant "5V" partout

**Verification** : Ouvrir le netlist (Design → Netlist) et verifier que H2.4 apparait dans le meme net que H1.3, U2.3, U3.10, U4.10, U6.14.

**IMPORTANT** : Avant de modifier, verifie d'abord avec un multimetre si le PCB actuel a deja la continuite entre H2.4 et le VIN du MCP23017. Si oui, ca veut dire que le routage PCB a corrige l'erreur du schema, et la modif est cosmetique. Si non, il faudra aussi mettre a jour le routage PCB (ajouter une piste entre H2.4 et le rail 5V).

---

## Modification 5 -- Mettre a jour les labels des spares

**Contexte** : Apres les modifs 2 et 3, IO32 et IO33 ne sont plus des "spare". Les vrais spare deviennent IO34, IO35 (input-only, usage limite), IO23 et IO19.

**Etapes** :

1. Supprimer les labels "Supp1" et "Supp2" (deja fait dans les modifs 2 et 3)
2. Sur U1 pin 5 (IO34) : tu peux ajouter un label "NC_IO34" ou juste laisser non connecte
3. Sur U1 pin 6 (IO35) : pareil, "NC_IO35" ou non connecte
4. Sur le connecteur H1 :
   - H1.5 : renommer de "SUPP1" a "LED" (car IO32 y arrive maintenant)
   - H1.6 : renommer de "SUPP2" a "SERVO" (car IO33 y arrive)
   - H1.7 (IO19) et H1.8 (IO23) restent spare

---

## Modification 6 -- Documenter GPIO16/17 (optionnel)

**Contexte** : Avec le WROOM, GPIO16 et GPIO17 sont disponibles (pas de PSRAM). Ils servent pour UART2 (communication avec le Raspberry Pi en option).

**Etapes** :

1. Sur le schema, pres de U1, ajouter un texte/commentaire :
   ```
   GPIO16 (UART2 RX) - disponible (WROOM)
   GPIO17 (UART2 TX) - disponible (WROOM)
   ```
2. Ces pins ne sont pas routes sur le PCB, donc pas de piste a ajouter
3. Si on veut les utiliser plus tard, il faudra ajouter un connecteur ou des pads

---

## Impact sur le PCB (routage)

### Ce qui NE change PAS :
- Le footprint de l'ESP32 (meme 40 pins, meme espacement)
- Les pistes de la matrice de boutons (12 GPIO inchanges)
- Les pistes I2C (IO21/IO22 → MCP23017)
- Les pistes UART (GPIO1/3)
- Les pistes vers les moteurs et MCP23017
- Le placement des composants

### Ce qui CHANGE (schema uniquement, sauf #4) :
- Le fil LED passe de pin 5 a pin 7 du module ESP32
- Le fil Servo passe de pin 6 a pin 8 du module ESP32
- Les pins 5-6 et 7-8 sont **adjacents** sur le meme cote du module, donc le routage PCB devrait etre simple a modifier (pistes courtes)

### Ce qui CHANGE PEUT-ETRE (a verifier) :
- La piste +5V depuis H2.4 vers le rail 5V (modif #4) -- seulement si le multimetre montre qu'elle manque

---

## Checklist pour jeanrdc

- [ ] Modifier le nom du composant U1 : WROVER → WROOM
- [ ] Deconnecter IO34 (pin 5) du signal LED
- [ ] Connecter IO32 (pin 7) au signal LED
- [ ] Deconnecter IO35 (pin 6) du signal Servomot
- [ ] Connecter IO33 (pin 8) au signal Servomot
- [ ] Renommer le label "+5" en "5V" sur H2.4
- [ ] Verifier le netlist : LED = {U1.7, H1.4}, Servomot = {U1.8, U2.2}, 5V = {H2.4, H1.3, U2.3, U3.10, U4.10, U6.14}
- [ ] Mettre a jour le routage PCB pour les 2-3 pistes modifiees (LED, Servo, +5V si besoin)
- [ ] Exporter les nouveaux PDF (schema + PCB) et netlist
- [ ] Mettre a jour la BOM (nom du composant U1)
