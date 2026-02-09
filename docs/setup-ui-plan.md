# Piano UI per pannello setup pilota
Definiamo l’interfaccia per aprire e modificare il setup delle auto tramite una vista contestuale sovrapposta alla card del pilota.

## Obiettivi
1. Aggiungere un entry point chiaro sulla tile pilota (bottone "Setup") disponibile solo quando l’auto è in BOX.
2. Visualizzare un pannello overlay con slider/indicatori setup senza perdere il contesto del pilota.
3. Mantenere feedback colore/messaggi e range consigliati direttamente nella stessa vista.
4. Garantire accessibilità e compatibilità con il layout attuale (desktop first, responsive minimo).

## Indicatori raccolta dati setup
- Mostrare una chip "SETUP" (o "DATA") sempre visibile accanto allo stato giro (HOT/OUT/IN).
- Colori: rosso (0–33% info raccolte), giallo (34–66%), verde (≥67%; lampeggia quando il target informativo è raggiunto).
- La chip legge `info_progress/info_target` dal backend e comunica all'utente quanta telemetria utile è stata raccolta per aggiornare il feedback.
- Nel pannello overlay replicare lo stato con barra/label coerente e testo "Gathering more data..." finché non si passa al verde.
- Al cambio slider/Apply la chip torna rossa e il contatore riparte.

## Sequenza proposta
1. **Trigger & stato UI**
   - Inserire un pulsante "Setup" accanto ai bottoni Send/Box nella card.
   - Stato locale `isSetupOpen` per pilota (gestito da PlayerGarage) che abilita/disabilita la vista.
2. **Overlay nella card**
   - Sovrapporre un pannello semi-trasparente sopra la card esistente (modal interno) senza reflow dell’intero layout.
   - Header con nome pilota, stato box e icona chiusura.
3. **Controlli setup**
   - Slider verticali o coppie (front/rear) con etichette: Front/Rear Wing, Ride Height F/R, Suspension F/R.
   - Visualizzare delta rispetto al range ottimale (badge colore + testo breve), eventuale tooltip per messaggi pilota.
   - Pulsanti "Reset" (torna al valore salvato) e "Applica" (chiama API `/setup`).
4. **Validazioni e feedback**
   - Bloccare il pannello se l’auto lascia i box (overlay mostra warning e chiude automaticamente).
   - Toast/notifica in fondo card per confermare salvataggio o mostrare errori REST.
5. **Accessibilità & responsive**
   - Navigazione tastiera (Tab order, Enter per Apply, Esc per chiudere).
   - In mobile/tablet, overlay diventa full-width panel sopra le card (fallback).
