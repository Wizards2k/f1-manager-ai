# F1 Manager AI

An AI-powered Formula 1 management simulation game.

## Project Overview

This project will be developed from scratch as an interactive F1 management game with AI assistance.

## Getting Started

Project initialization in progress...

## Circuit Selection & Dynamic Loading

- Open `/` to choose a circuit from the selection page.
- The race view is served at `/race?circuit=<circuit_id>`.
- The backend loads the selected GeoJSON from `circuits/<circuit_id>.json` via `/api/circuit?circuit=<circuit_id>`.
- Cars start in the garage and exit with staggered timing (30–300s) when a session begins.

## Sector Config Checklist

The following circuits are present in `circuits/` but missing entries in `sectors_config.json`:

- [ ] ae-2009_yas_marina
- [ ] ar-1952_buenos_aires
- [ ] at-1969_spielberg
- [ ] au-1953_melbourne
- [ ] az-2016_baku
- [ ] be-1925_spa_francorchamps
- [ ] bh-2002_sakhir
- [ ] br-1940_sao_paulo
- [ ] br-1977_jacarepaguá
- [ ] ca-1978_montreal
- [ ] cn-2004_shanghai
- [ ] de-1927_nürburg
- [ ] de-1932_hockenheim
- [ ] es-1991_barcelona
- [ ] es-2026_madrid
- [ ] fr-1960_magny_cours
- [ ] fr-1969_le_castellet
- [ ] gb-1948_silverstone
- [ ] hu-1986_budapest
- [ ] it-1914_scarperia_e_san_piero
- [ ] it-1922_monza
- [ ] it-1953_imola
- [ ] jp-1962_suzuka
- [ ] mc-1929_monaco
- [ ] mx-1962_mexico_city
- [ ] my-1999_sepang
- [ ] nl-1948_zandvoort
- [ ] pt-1972_estoril
- [ ] pt-2008_portimão
- [ ] qa-2004_lusail
- [ ] ru-2014_sochi
- [ ] sa-2021_jeddah
- [ ] sg-2008_singapore
- [ ] tr-2005_istanbul
- [ ] us-1909_indianapolis
- [ ] us-1956_dix
- [ ] us-2012_austin
- [ ] us-2022_miami
- [ ] us-2023_las_vegas
- [ ] za-1961_johannesburg

## Technologies

To be determined based on project requirements.

## License

MIT
