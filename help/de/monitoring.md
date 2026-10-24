---
title: Monitoring und Alarme
category: monitoring
order: 1
summary: Geplante Abfrage, Portauslastung und -fehler, CPU und Temperatur, Ereignisschwellen, Diagramme.
keywords: abfrage intervall auslastung verkehr fehler cpu speicher temperatur schwelle ereignis diagramm statistik poe
---
# Regelmäßige Abfrage {#polling}

Öffnen Sie die **Einstellungen** (Zahnrad unten im Menü) und aktivieren Sie **Switches regelmäßig per SNMP abfragen**. SwitchMap fragt dann alle Switches mit IP-Adresse im gewählten Intervall ab.

| Intervall | Wann passend |
|---|---|
| 1–2 Minuten | Kleines Netz, genaue Diagramme gewünscht |
| 5 Minuten | Für fast alle |
| 10–15 Minuten | Hunderte Switches oder langsame Leitungen |

Ohne regelmäßige Abfrage werden Daten nur über die Schaltfläche **Per SNMP abfragen** auf der Switch-Seite aktualisiert.

**Portnamen, Beschreibungen und VLANs** – wie oft selten geänderte Daten gelesen werden: Portnamen und -beschreibungen, VLANs, LLDP-Nachbarn (für die Topologie).

| Modus | Wann wählen |
|---|---|
| Bei jeder Abfrage | Das Netz wird aufgebaut, erweitert oder repariert – Änderungen sind sofort sichtbar |
| Einmal pro Stunde | Das Netz ist stabil – fast halb so viele Anfragen an die Switches, weniger Last auf deren CPU |

Portstatus, Datenverkehr, Fehler und MAC-Adressen werden in beiden Modi bei jeder Abfrage gelesen. **Per SNMP abfragen** auf der Switch-Seite liest immer alles – drücken Sie es nach einer Änderung am Switch, statt eine Stunde zu warten.

# Was gemessen wird {#metrics}

- **Portstatus** — Link oder kein Link. Eine Änderung erzeugt das Ereignis „Port ausgefallen“ oder „Port aktiv“.
- **Auslastung** — die Datenrate in Prozent der Portgeschwindigkeit. Sie wird aus der Zählerdifferenz zwischen zwei Abfragen berechnet und erscheint daher ab der zweiten Abfrage.
- **Fehler** — wie viele Empfangs- und Sendefehler seit der letzten Abfrage aufgelaufen sind.
- **CPU, Speicher, Temperatur** — sofern der Switch sie per SNMP meldet (herstellerabhängig).
- **PoE** — Verbrauch pro Port, sofern der Switch POWER-ETHERNET-MIB unterstützt.

# Alarmschwellen {#thresholds}

Unter **Einstellungen → Alarmschwellen**:

| Schwelle | Ereignis |
|---|---|
| Portauslastung, % | Verkehr über diesem Prozentsatz der Portgeschwindigkeit |
| Portfehler zwischen Abfragen | Die Fehler nehmen zu — oft ein schlechtes Kabel |
| CPU-Last, % | Die CPU des Switches ist überlastet |
| Temperatur, °C | Überhitzung |

Beim Überschreiten einer Schwelle entsteht ein Ereignis und ein weiteres, wenn der Wert wieder normal ist. **0** schaltet eine Schwelle ab. Antwortet ein Switch nicht mehr, erklärt das Ereignis „Switch nicht erreichbar“, ob er noch auf Ping reagiert (dann liegt es an den SNMP-Einstellungen) oder nicht (dann am Netz oder an der Stromversorgung). „Antwortet“ ein sicher getrennter Switch auf Ping, siehe [Ein getrennter Switch antwortet auf Ping](/help/troubleshooting#fake-ping).

# Diagramme {#charts}

Auf der Switch-Seite öffnet die Schaltfläche **Statistik** die Diagramme:

- die Datenrate jedes Ports (eingehend und ausgehend);
- CPU, Speicher und Temperatur des Switches.

Die Zeiträume reichen von 1 Stunde bis 1 Jahr. Lange Zeiträume nutzen Stundenwerte, daher laden die Diagramme schnell. Wie viel Verlauf aufbewahrt wird — siehe [Daten und Sicherungen](/help/backups#retention).

# Ereignisse {#events}

Alle Ereignisse erscheinen unter der Glocke in der oberen Leiste und in der Spalte **Alarme** auf der Startseite. Um sie per Telegram oder E-Mail zu erhalten, richten Sie [Benachrichtigungen](/help/notifications) ein.
