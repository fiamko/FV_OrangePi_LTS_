- Odesílá MQTT zprávy na témata jako `fve/spotrebice/bojler/set`. **Vířivka** je
  osazena ESP32, které poslouchá `fve/spotrebice/virivka/set` a posílá zpět
  změřený proud (SCT013) a teplotu (DS18B20) na `spinac/VIRIVKA_OHREV/stav`.
- Stav spotřebičů se zapisuje i do `current_data`, takže dashboard vidí, co je
  zapnuté. U vířivky zobrazuje reálný změřený výkon místo konstanty.