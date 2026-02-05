# Wochenkorb-Menuplaner

Wöchentliche Menüvorschläge basierend auf dem Gemüse- und Früchtekorb von [Emma und Söhne](https://emmaundsoehne.ch).

## Verfügbare Chefs

Verwende je nach gewünschtem Küchenstil den passenden Chef:

| Küchenstil | Datei | Befehl |
|------------|-------|--------|
| **Schweizer/Europäisch** | [chefs/CHEF-SCHWEIZ.md](chefs/CHEF-SCHWEIZ.md) | "Erstelle Menüs für KW XX" |
| **Asiatisch** | [chefs/CHEF-ASIA.md](chefs/CHEF-ASIA.md) | "Erstelle asiatische Menüs für KW XX" |
| **Mexikanisch** | [chefs/CHEF-MEXICO.md](chefs/CHEF-MEXICO.md) | "Erstelle mexikanische Menüs für KW XX" |
| **Meal Prep** | [chefs/CHEF-MEALPREP.md](chefs/CHEF-MEALPREP.md) | "Erstelle Meal Prep für KW XX" |

## Projektstruktur

```
koerbe/           # Wöchentliche Korbinhalte (korb-YYYYWW.md)
menus/            # Generierte Menüpläne
chefs/            # Chef-Personas
```

## Workflow

1. Korbinhalt in `koerbe/korb-YYYYWW.md` eintragen
2. Gewünschten Küchenstil wählen und Menüs erstellen lassen
3. Chef erstellt Menüplan in `menus/` und aktualisiert README.md
