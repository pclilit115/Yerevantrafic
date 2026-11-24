# Yerevan 3D Traffic Simulation

Interactive three.js simulation of Yerevan traffic (Kentron, Arabkir, Kanaker-Zeytun, Malatia-Sebastia, Nor Nork, Nork-Marash): IDM car-following, lane changes, signals, buses/taxis/minibuses/trolleybuses, existing and proposed bus lanes, calibrated to the Yerevan Traffic & Mobility Data Report 2026.

- `docs/` – the site (`index.html` + `net.json`, `bld.txt`, `yerevan_traffic_data.json`). Serve the folder with any static server, e.g. `python3 -m http.server -d docs`.
- `tools/` – scripts and source data (OSM extracts, KML) used to build `net.json`.

Data: OpenStreetMap contributors. Signals, on-road share and hot-street share are model assumptions.
