# TMB Metro Barcelona - Revisión Manual de Datos

**Fecha:** 2026-01-31
**Paso:** 4 - Revisión manual (ESTRUCTURA_PROCESO.md)

---

## Resumen

| Fuente | Andenes | Accesos | Estaciones |
|--------|---------|---------|------------|
| **BD (GTFS)** | 165 | 504 | 139 |
| **OSM (solo metro)** | 106 | 215 | 67 con andenes |

**Decisión:** Solo usar datos de METRO. Buses ignorados.

---

## 1. Andenes BD que necesitan coordenadas OSM

### 1.1 Andenes con coordenadas = estación padre (109 de 165)

Estos andenes tienen coordenadas idénticas a su estación padre en el GTFS.
**→ Necesitan coordenadas reales de OSM**

| ID BD | Nombre | Lat | Lon | Estación Padre |
|-------|--------|-----|-----|----------------|
| `TMB_METRO_1.901` | Aeroport T1 | 41.288295 | 2.071152 | `TMB_METRO_P.6660901` |
| `TMB_METRO_1.903` | Aeroport T2 | 41.303823 | 2.073113 | `TMB_METRO_P.6660903` |
| `TMB_METRO_1.429` | Alfons X | 41.412377 | 2.166382 | `TMB_METRO_P.6660429` |
| `TMB_METRO_1.223` | Artigues \| Sant Adrià | 41.433848 | 2.217772 | `TMB_METRO_P.6660223` |
| `TMB_METRO_1.113` | Av. Carrilet | 41.358553 | 2.102632 | `TMB_METRO_P.6660113` |
| `TMB_METRO_1.219` | Bac de Roda | 41.415162 | 2.195503 | `TMB_METRO_P.6660219` |
| `TMB_METRO_1.516` | Badal | 41.375581 | 2.127402 | `TMB_METRO_P.6660516` |
| `TMB_METRO_1.227` | Badalona Pompeu Fabra | 41.449054 | 2.244097 | `TMB_METRO_P.6660227` |
| `TMB_METRO_1.138` | Baró de Viver | 41.449936 | 2.199563 | `TMB_METRO_P.6660138` |
| `TMB_METRO_1.112` | Bellvitge | 41.350975 | 2.110917 | `TMB_METRO_P.6660112` |
| `TMB_METRO_1.414` | Besòs | 41.419901 | 2.210231 | `TMB_METRO_P.6660414` |
| `TMB_METRO_1.415` | Besòs Mar | 41.415099 | 2.216082 | `TMB_METRO_P.6660415` |
| `TMB_METRO_1.420` | Bogatell | 41.395107 | 2.192012 | `TMB_METRO_P.6660420` |
| `TMB_METRO_1.933` | Bon Pastor | 41.436203 | 2.205294 | `TMB_METRO_P.6660933` |
| `TMB_METRO_1.525` | Camp de l'Arpa | 41.415060 | 2.181497 | `TMB_METRO_P.6660525` |
| `TMB_METRO_1.512` | Can Boixeres | 41.366571 | 2.091506 | `TMB_METRO_P.6660512` |
| `TMB_METRO_1.1140` | Can Cuiàs | 41.462413 | 2.173059 | `TMB_METRO_P.6661140` |
| `TMB_METRO_1.940` | Can Peixauet | 41.443986 | 2.210027 | `TMB_METRO_P.6660940` |
| `TMB_METRO_1.115` | Can Serra | 41.367694 | 2.102758 | `TMB_METRO_P.6660115` |
| `TMB_METRO_1.914` | Can Tries \| Gornal | 41.360894 | 2.117993 | `TMB_METRO_P.6660914` |
| `TMB_METRO_1.513` | Can Vidalet | 41.371279 | 2.099445 | `TMB_METRO_P.6660513` |
| `TMB_METRO_1.945` | Can Zam | 41.456666 | 2.198569 | `TMB_METRO_P.6660945` |
| `TMB_METRO_1.337` | Canyelles | 41.441754 | 2.166388 | `TMB_METRO_P.6660337` |
| `TMB_METRO_1.421` | Ciutadella \| Vila Olímpica | 41.386687 | 2.192991 | `TMB_METRO_P.6660421` |
| `TMB_METRO_1.1139` | Ciutat Meridiana | 41.460808 | 2.174650 | `TMB_METRO_P.6661139` |
| `TMB_METRO_1.958` | Ciutat de la Justícia | 41.363137 | 2.132315 | `TMB_METRO_P.6660958` |
| `TMB_METRO_1.527` | Congrés | 41.423440 | 2.181186 | `TMB_METRO_P.6660527` |
| `TMB_METRO_1.509` | Cornellà Centre | 41.357290 | 2.070428 | `TMB_METRO_P.6660509` |
| `TMB_METRO_1.906` | Cèntric | 41.322250 | 2.093463 | `TMB_METRO_P.6660906` |
| `TMB_METRO_1.324` | Drassanes | 41.376538 | 2.175664 | `TMB_METRO_P.6660324` |
| `TMB_METRO_1.952` | Ecoparc | 41.330159 | 2.137071 | `TMB_METRO_P.6660952` |
| `TMB_METRO_1.532` | El Carmel | 41.424450 | 2.155099 | `TMB_METRO_P.6660532` |
| `TMB_METRO_1.533` | El Coll \| La Teixonera | 41.421997 | 2.148348 | `TMB_METRO_P.6660533` |
| `TMB_METRO_1.416` | El Maresme \| Fòrum | 41.411780 | 2.216692 | `TMB_METRO_P.6660416` |
| `TMB_METRO_1.907` | El Prat Estació | 41.331993 | 2.089927 | `TMB_METRO_P.6660907` |
| `TMB_METRO_1.217` | Encants | 41.407236 | 2.182700 | `TMB_METRO_P.6660217` |
| `TMB_METRO_1.519` | Entença | 41.384467 | 2.145619 | `TMB_METRO_P.6660519` |
| `TMB_METRO_1.943` | Església Major | 41.454797 | 2.212177 | `TMB_METRO_P.6660943` |
| `TMB_METRO_1.913` | Europa \| Fira | 41.357560 | 2.125924 | `TMB_METRO_P.6660913` |
| `TMB_METRO_1.134` | Fabra i Puig | 41.429633 | 2.183661 | `TMB_METRO_P.6660134` |
| `TMB_METRO_1.912` | Fira | 41.351988 | 2.130452 | `TMB_METRO_P.6660912` |
| `TMB_METRO_1.956` | Foc | 41.356161 | 2.141804 | `TMB_METRO_P.6660956` |
| `TMB_METRO_1.942` | Fondo | 41.451876 | 2.218485 | `TMB_METRO_P.6660140` |
| `TMB_METRO_1.957` | Foneria | 41.361099 | 2.138229 | `TMB_METRO_P.6660957` |
| `TMB_METRO_1.510` | Gavarra | 41.357993 | 2.079269 | `TMB_METRO_P.6660510` |
| `TMB_METRO_1.426` | Girona | 41.394920 | 2.170825 | `TMB_METRO_P.6660426` |
| `TMB_METRO_1.130` | Glòries | 41.402277 | 2.187537 | `TMB_METRO_P.6660130` |
| `TMB_METRO_1.936` | Gorg | 41.440443 | 2.233892 | `TMB_METRO_P.6660225` |
| `TMB_METRO_1.430` | Guinardó \| Hospital de Sant Pau | 41.415962 | 2.173989 | `TMB_METRO_P.6660430` |
| `TMB_METRO_1.531` | Horta | 41.429692 | 2.159974 | `TMB_METRO_P.6660531` |
| `TMB_METRO_1.111` | Hospital de Bellvitge | 41.344677 | 2.107242 | `TMB_METRO_P.6660111` |
| `TMB_METRO_1.121` | Hostafrancs | 41.375254 | 2.143291 | `TMB_METRO_P.6660121` |
| `TMB_METRO_1.423` | Jaume I | 41.384126 | 2.178531 | `TMB_METRO_P.6660423` |
| `TMB_METRO_1.428` | Joanic | 41.406427 | 2.163225 | `TMB_METRO_P.6660428` |
| `TMB_METRO_1.221` | La Pau | 41.424033 | 2.205608 | `TMB_METRO_P.6660221` |
| `TMB_METRO_1.935` | La Salut | 41.442817 | 2.224737 | `TMB_METRO_P.6660935` |
| `TMB_METRO_1.909` | Les Moreres | 41.329119 | 2.103073 | `TMB_METRO_P.6660909` |
| `TMB_METRO_1.330` | Lesseps | 41.405738 | 2.150407 | `TMB_METRO_P.6660330` |
| `TMB_METRO_1.325` | Liceu | 41.381445 | 2.173030 | `TMB_METRO_P.6660325` |
| `TMB_METRO_1.419` | Llacuna | 41.399425 | 2.197712 | `TMB_METRO_P.6660419` |
| `TMB_METRO_1.934` | Llefià | 41.441360 | 2.216906 | `TMB_METRO_P.6660934` |
| `TMB_METRO_1.432` | Llucmajor | 41.436985 | 2.173343 | `TMB_METRO_P.6660432` |
| `TMB_METRO_1.431` | Maragall | 41.423104 | 2.177397 | `TMB_METRO_P.6660431` |
| `TMB_METRO_1.316` | Maria Cristina | 41.387816 | 2.125791 | `TMB_METRO_P.6660316` |
| `TMB_METRO_1.129` | Marina | 41.394725 | 2.185801 | `TMB_METRO_P.6660129` |
| `TMB_METRO_1.904` | Mas Blau | 41.311225 | 2.073471 | `TMB_METRO_P.6660904` |
| `TMB_METRO_1.910` | Mercabarna | 41.333485 | 2.111254 | `TMB_METRO_P.6660910` |
| `TMB_METRO_1.119` | Mercat Nou | 41.373003 | 2.133536 | `TMB_METRO_P.6660119` |
| `TMB_METRO_1.334` | Montbau | 41.430620 | 2.145039 | `TMB_METRO_P.6660334` |
| `TMB_METRO_1.215` | Monumental | 41.400524 | 2.179462 | `TMB_METRO_P.6660215` |
| `TMB_METRO_1.335` | Mundet | 41.435645 | 2.148472 | `TMB_METRO_P.6660335` |
| `TMB_METRO_1.132` | Navas | 41.416187 | 2.187057 | `TMB_METRO_P.6660132` |
| `TMB_METRO_1.932` | Onze de Setembre | 41.429559 | 2.193564 | `TMB_METRO_P.6660932` |
| `TMB_METRO_1.315` | Palau Reial | 41.385980 | 2.118538 | `TMB_METRO_P.6660315` |
| `TMB_METRO_1.911` | Parc Logístic | 41.341664 | 2.127401 | `TMB_METRO_P.6660911` |
| `TMB_METRO_1.905` | Parc Nou | 41.316628 | 2.087929 | `TMB_METRO_P.6660905` |
| `TMB_METRO_1.9902` | Parc de Montjuïc | 41.368956 | 2.163269 | `TMB_METRO_P.6669902` |
| `TMB_METRO_1.332` | Penitents | 41.418279 | 2.140972 | `TMB_METRO_P.6660332` |
| `TMB_METRO_1.226` | Pep Ventura | 41.443905 | 2.237959 | `TMB_METRO_P.6660226` |
| `TMB_METRO_1.120` | Plaça de Sants | 41.375353 | 2.138154 | `TMB_METRO_P.6660120` |
| `TMB_METRO_1.322` | Poble Sec | 41.374996 | 2.160245 | `TMB_METRO_P.6660322` |
| `TMB_METRO_1.418` | Poblenou | 41.403716 | 2.203371 | `TMB_METRO_P.6660418` |
| `TMB_METRO_1.953` | Port Comercial \| La Factoria | 41.335983 | 2.140657 | `TMB_METRO_P.6660953` |
| `TMB_METRO_1.959` | Provençana | 41.361354 | 2.124100 | `TMB_METRO_P.6660959` |
| `TMB_METRO_1.114` | Rambla Just Oliveras | 41.364090 | 2.099749 | `TMB_METRO_P.6660114` |
| `TMB_METRO_1.123` | Rocafort | 41.379232 | 2.154562 | `TMB_METRO_P.6660123` |
| `TMB_METRO_1.211` | Sant Antoni | 41.379833 | 2.163241 | `TMB_METRO_P.6660211` |
| `TMB_METRO_1.511` | Sant Ildefons | 41.363381 | 2.084393 | `TMB_METRO_P.6660511` |
| `TMB_METRO_1.524` | Sant Pau \| Dos de Maig | 41.410753 | 2.176016 | `TMB_METRO_P.6660524` |
| `TMB_METRO_1.224` | Sant Roc | 41.435831 | 2.228606 | `TMB_METRO_P.6660224` |
| `TMB_METRO_1.139` | Santa Coloma | 41.451067 | 2.207969 | `TMB_METRO_P.6660139` |
| `TMB_METRO_1.118` | Santa Eulàlia | 41.368816 | 2.128617 | `TMB_METRO_P.6660118` |
| `TMB_METRO_1.941` | Santa Rosa | 41.446850 | 2.215809 | `TMB_METRO_P.6660941` |
| `TMB_METRO_1.417` | Selva de Mar | 41.408001 | 2.209122 | `TMB_METRO_P.6660417` |
| `TMB_METRO_1.944` | Singuerlín | 41.459413 | 2.205429 | `TMB_METRO_P.6660944` |
| `TMB_METRO_1.214` | Tetuan | 41.394887 | 2.175559 | `TMB_METRO_P.6660214` |
| `TMB_METRO_1.136` | Torras i Bages | 41.443225 | 2.190671 | `TMB_METRO_P.6660136` |
| `TMB_METRO_1.915` | Torrassa | 41.368223 | 2.115756 | `TMB_METRO_P.6660117` |
| `TMB_METRO_1.1138` | Torre Baró \| Vallbona | 41.459196 | 2.179884 | `TMB_METRO_P.6661138` |
| `TMB_METRO_1.137` | Trinitat Vella | 41.448956 | 2.193837 | `TMB_METRO_P.6660137` |
| `TMB_METRO_1.124` | Urgell | 41.382487 | 2.158891 | `TMB_METRO_P.6660124` |
| `TMB_METRO_1.333` | Vall d'Hebron | 41.425283 | 2.142565 | `TMB_METRO_P.6660333` |
| `TMB_METRO_1.331` | Vallcarca | 41.411975 | 2.144337 | `TMB_METRO_P.6660331` |
| `TMB_METRO_1.336` | Valldaura | 41.437996 | 2.156878 | `TMB_METRO_P.6660336` |
| `TMB_METRO_1.222` | Verneda | 41.430004 | 2.209883 | `TMB_METRO_P.6660222` |
| `TMB_METRO_1.433` | Via Júlia | 41.443730 | 2.178550 | `TMB_METRO_P.6660433` |
| `TMB_METRO_1.530` | Vilapicina | 41.430465 | 2.167619 | `TMB_METRO_P.6660530` |
| `TMB_METRO_1.951` | ZAL \| Riu Vell | 41.323706 | 2.133095 | `TMB_METRO_P.6660951` |
| `TMB_METRO_1.954` | Zona Franca | 41.342976 | 2.144964 | `TMB_METRO_P.6660954` |

**Total: 109 andenes que necesitan coordenadas reales**

---

### 1.2 Andenes BD con coordenadas propias (ya correctos)

Estos 7 andenes YA tienen coordenadas distintas a su estación padre (intercambiadores).
**→ No necesitan actualización**

| ID BD | Nombre | Lat Andén | Lon Andén | Lat Padre | Lon Padre |
|-------|--------|-----------|-----------|-----------|-----------|
| `TMB_METRO_1.515` | Collblanc | 41.375743 | 2.119195 | 41.376056 | 2.118397 |
| `TMB_METRO_1.140` | Fondo | 41.451583 | 2.218435 | 41.451876 | 2.218485 |
| `TMB_METRO_1.225` | Gorg | 41.440237 | 2.233441 | 41.440443 | 2.233892 |
| `TMB_METRO_1.413` | La Pau | 41.423678 | 2.205194 | 41.424033 | 2.205608 |
| `TMB_METRO_1.517` | Plaça de Sants | 41.375727 | 2.135159 | 41.375353 | 2.138154 |
| `TMB_METRO_1.117` | Torrassa | 41.368396 | 2.116594 | 41.368223 | 2.115756 |
| `TMB_METRO_1.534` | Vall d'Hebron | 41.424993 | 2.142356 | 41.425283 | 2.142565 |

---

## 2. Comparación estaciones OSM vs BD

### 2.1 Estaciones con diferente número de andenes

**Motivo probable:** BD cuenta 1 andén por estación simple, OSM cuenta 2 (uno por sentido/dirección).

| Estación OSM | Estación BD | OSM | BD | Acción |
|--------------|-------------|-----|-----|--------|
| La Pau | La Pau | 4 | 2 | Criterio diferente (cruce L2/L4) |
| Badal | Badal | 2 | 1 | Criterio diferente |
| Baró de Viver | Baró de Viver | 2 | 1 | Criterio diferente |
| Can Serra | Can Serra | 2 | 1 | Criterio diferente |
| Cornellà Centre | Cornellà Centre | 2 | 1 | Criterio diferente |
| Drassanes | Drassanes | 2 | 1 | Criterio diferente |
| El Carmel | El Carmel | 2 | 1 | Criterio diferente |
| Hostafrancs | Hostafrancs | 2 | 1 | Criterio diferente |
| Liceu | Liceu | 2 | 1 | Criterio diferente |
| Marina | Marina | 2 | 1 | Criterio diferente |
| Monumental | Monumental | 2 | 1 | Criterio diferente |
| Rambla Just Oliveras | Rambla Just Oliveras | 2 | 1 | Criterio diferente |
| Rocafort | Rocafort | 2 | 1 | Criterio diferente |
| Urgell | Urgell | 2 | 1 | Criterio diferente |

**Total: 14 estaciones**

---

### 2.2 Estaciones OSM sin correspondencia en BD

**Solo revisar estaciones de METRO. Buses descartados.**

#### A) Estaciones METRO - MAPEO VERIFICADO ✅

**Revisado:** 2026-01-31

| # | OSM | BD (GTFS) | Acción | Estado |
|---|-----|-----------|--------|--------|
| 1 | Arc de Triomf | Arc de Triomf | Match directe | ✅ |
| 2 | Catalunya | Plaça de Catalunya | Cambiar nombre (OSM usa corto) | ✅ |
| 3 | Espanya L1 | Espanya | Vincular al nodo padre | ✅ |
| 4 | Espanya L3 | Espanya | Vincular al nodo padre | ✅ |
| 5 | La Sagrera | La Sagrera | Match directe | ✅ |
| 6 | Metro Urquinaona | Urquinaona | Eliminar prefijo "Metro" | ✅ |
| 7 | Paral·lel | Paral·lel | Match directe | ✅ |
| 8 | Passeig de Gràcia | Passeig de Gràcia | Match directe (L2/L3/L4 al mismo padre) | ✅ |
| 9 | Sagrada Família | Sagrada Família | Match directe | ✅ |
| 10 | Trinitat Nova | Trinitat Nova | Match directe | ✅ |
| 11 | Universitat | Universitat | Match directe | ✅ |
| 12 | Urquinaona | Urquinaona | Match directe | ✅ |
| 13 | Verdaguer | Verdaguer | Match directe | ✅ |
| 14 | Virrei Amat | Virrei Amat | Match directe | ✅ |

**Notas técnicas:**
- **Espanya:** OSM separa L1/L3, BD tiene estación padre única. Asignar ambos OSM_ID al mismo GTFS_ID.
- **Catalunya:** Nombre oficial BD es "Plaça de Catalunya", OSM usa "Catalunya".
- **Prefijos "Metro...":** Error común en OSM, ignorar siempre.

#### B) Buses y otros - IGNORAR (32)

**DECISIÓN: No usar datos de bus. Solo metro.**

| Estación OSM | Tipo |
|--------------|------|
| Diagonal - Francesc Macià | Bus |
| Aribau - Còrsega | Bus |
| Arístides Maillol - Trav. de les Corts | Bus |
| Balmes - Rosselló | Bus |
| Les Corts - Aurora Bertrana | Bus |
| Pl Catalunya - Pg de Gràcia | Bus |
| Pl Catalunya - Rambla Catalunya | Bus |
| Pl Urquinaona - Pau Claris | Bus |
| Rda. Sant Pere - Pl. de Catalunya | Bus |
| Riera Blanca - Regent Mendieta | Bus |
| Riera Blanca - Trav de Les Corts | Bus |
| Ronda Sant Pere - Pau Claris | Bus |
| Ronda Sant Pere - Pl Urquinaona | Bus |
| Ronda St Pere - Pg de Gràcia | Bus |
| Ronda Universitat - Pl Universitat | Bus |
| Travessera de les Corts - Comte de Güell | Bus |
| Bucle Entrada Recinte Cementiri | Bus cementerio |
| Bucle Sortida Recinte Cementiri | Bus cementerio |
| Ctra Cementiri Collserola - Camí Vall de St Iscle | Bus cementerio |
| Ctra Cementiri Collserola - Residència Joan XXIII | Bus cementerio |
| Ctra del Cementiri de Collserola - Recinte Hebreu | Bus cementerio |
| Agrupació número 1.2 - Jardí del Repòs | Bus |
| Casa de l'Aigua | Bus |
| Ctra de Vallvidrera - St Cugat | Bus |
| Palau Sant Jordi | Bus |
| Pg Olímpic - Palau Sant Jordi | Bus |
| Pl Coll de la Creu d'en Blau, direcció El Rectoret | Funicular |
| Pl Coll de la Creu d'en Blau, direcció Vallvidrera | Funicular |
| Pl Urquinaona | Duplicado |
| Pl del Complex Funerari, direcció Barcelona | Bus |
| Pl del Complex Funerari, direcció Recinte | Bus |
| Residència Joan XXIII | Bus |

---

### 2.3 Estaciones BD sin datos de andenes en OSM (89)

Estas estaciones existen en BD pero no se encontraron andenes en OSM.
**Motivo:** OSM incompleto o timeouts durante extracción.

| Estación BD | ID | Andenes BD |
|-------------|-----|------------|
| Aeroport T1 | `TMB_METRO_P.6660901` | 1 |
| Aeroport T2 | `TMB_METRO_P.6660903` | 1 |
| Alfons X | `TMB_METRO_P.6660429` | 1 |
| Artigues \| Sant Adrià | `TMB_METRO_P.6660223` | 1 |
| Av. Carrilet | `TMB_METRO_P.6660113` | 1 |
| Bac de Roda | `TMB_METRO_P.6660219` | 1 |
| Bellvitge | `TMB_METRO_P.6660112` | 1 |
| Besòs | `TMB_METRO_P.6660414` | 1 |
| Besòs Mar | `TMB_METRO_P.6660415` | 1 |
| Bogatell | `TMB_METRO_P.6660420` | 1 |
| Bon Pastor | `TMB_METRO_P.6660933` | 1 |
| Camp de l'Arpa | `TMB_METRO_P.6660525` | 1 |
| Can Boixeres | `TMB_METRO_P.6660512` | 1 |
| Can Cuiàs | `TMB_METRO_P.6661140` | 1 |
| Can Peixauet | `TMB_METRO_P.6660940` | 1 |
| Can Tries \| Gornal | `TMB_METRO_P.6660914` | 1 |
| Can Vidalet | `TMB_METRO_P.6660513` | 1 |
| Can Zam | `TMB_METRO_P.6660945` | 1 |
| Canyelles | `TMB_METRO_P.6660337` | 1 |
| Ciutadella \| Vila Olímpica | `TMB_METRO_P.6660421` | 1 |
| Ciutat Meridiana | `TMB_METRO_P.6661139` | 1 |
| Ciutat de la Justícia | `TMB_METRO_P.6660958` | 1 |
| Congrés | `TMB_METRO_P.6660527` | 1 |
| Cèntric | `TMB_METRO_P.6660906` | 1 |
| Ecoparc | `TMB_METRO_P.6660952` | 1 |
| El Coll \| La Teixonera | `TMB_METRO_P.6660533` | 1 |
| El Maresme \| Fòrum | `TMB_METRO_P.6660416` | 1 |
| El Prat Estació | `TMB_METRO_P.6660907` | 1 |
| Encants | `TMB_METRO_P.6660217` | 1 |
| Entença | `TMB_METRO_P.6660519` | 1 |
| Església Major | `TMB_METRO_P.6660943` | 1 |
| Europa \| Fira | `TMB_METRO_P.6660913` | 1 |
| Fabra i Puig | `TMB_METRO_P.6660134` | 1 |
| Fira | `TMB_METRO_P.6660912` | 1 |
| Foc | `TMB_METRO_P.6660956` | 1 |
| Fondo | `TMB_METRO_P.6660140` | 2 |
| Foneria | `TMB_METRO_P.6660957` | 1 |
| Gavarra | `TMB_METRO_P.6660510` | 1 |
| Glòries | `TMB_METRO_P.6660130` | 1 |
| Gorg | `TMB_METRO_P.6660225` | 2 |
| Guinardó \| Hospital de Sant Pau | `TMB_METRO_P.6660430` | 1 |
| Hospital de Bellvitge | `TMB_METRO_P.6660111` | 1 |
| Jaume I | `TMB_METRO_P.6660423` | 1 |
| Joanic | `TMB_METRO_P.6660428` | 1 |
| La Salut | `TMB_METRO_P.6660935` | 1 |
| Les Moreres | `TMB_METRO_P.6660909` | 1 |
| Lesseps | `TMB_METRO_P.6660330` | 1 |
| Llacuna | `TMB_METRO_P.6660419` | 1 |
| Llefià | `TMB_METRO_P.6660934` | 1 |
| Llucmajor | `TMB_METRO_P.6660432` | 1 |
| Maragall | `TMB_METRO_P.6660431` | 1 |
| Maria Cristina | `TMB_METRO_P.6660316` | 1 |
| Mas Blau | `TMB_METRO_P.6660904` | 1 |
| Mercabarna | `TMB_METRO_P.6660910` | 1 |
| Montbau | `TMB_METRO_P.6660334` | 1 |
| Mundet | `TMB_METRO_P.6660335` | 1 |
| Navas | `TMB_METRO_P.6660132` | 1 |
| Onze de Setembre | `TMB_METRO_P.6660932` | 1 |
| Palau Reial | `TMB_METRO_P.6660315` | 1 |
| Parc Logístic | `TMB_METRO_P.6660911` | 1 |
| Parc Nou | `TMB_METRO_P.6660905` | 1 |
| Parc de Montjuïc | `TMB_METRO_P.6669902` | 1 |
| Penitents | `TMB_METRO_P.6660332` | 1 |
| Pep Ventura | `TMB_METRO_P.6660226` | 1 |
| Poble Sec | `TMB_METRO_P.6660322` | 1 |
| Poblenou | `TMB_METRO_P.6660418` | 1 |
| Port Comercial \| La Factoria | `TMB_METRO_P.6660953` | 1 |
| Provençana | `TMB_METRO_P.6660959` | 1 |
| Sant Ildefons | `TMB_METRO_P.6660511` | 1 |
| Sant Pau \| Dos de Maig | `TMB_METRO_P.6660524` | 1 |
| Sant Roc | `TMB_METRO_P.6660224` | 1 |
| Santa Coloma | `TMB_METRO_P.6660139` | 1 |
| Santa Eulàlia | `TMB_METRO_P.6660118` | 1 |
| Santa Rosa | `TMB_METRO_P.6660941` | 1 |
| Selva de Mar | `TMB_METRO_P.6660417` | 1 |
| Singuerlín | `TMB_METRO_P.6660944` | 1 |
| Tetuan | `TMB_METRO_P.6660214` | 1 |
| Torras i Bages | `TMB_METRO_P.6660136` | 1 |
| Torrassa | `TMB_METRO_P.6660117` | 2 |
| Torre Baró \| Vallbona | `TMB_METRO_P.6661138` | 1 |
| Trinitat Vella | `TMB_METRO_P.6660137` | 1 |
| Vall d'Hebron | `TMB_METRO_P.6660333` | 2 |
| Vallcarca | `TMB_METRO_P.6660331` | 1 |
| Valldaura | `TMB_METRO_P.6660336` | 1 |
| Verneda | `TMB_METRO_P.6660222` | 1 |
| Via Júlia | `TMB_METRO_P.6660433` | 1 |
| Vilapicina | `TMB_METRO_P.6660530` | 1 |
| ZAL \| Riu Vell | `TMB_METRO_P.6660951` | 1 |
| Zona Franca | `TMB_METRO_P.6660954` | 1 |

**Total: 89 estaciones sin datos OSM**

---

## 3. Andenes OSM disponibles para actualizar coordenadas

Estos andenes OSM tienen match con estaciones BD y pueden usarse para actualizar coordenadas.

| Estación | Línea | OSM ID | Lat | Lon | Acción |
|----------|-------|--------|-----|-----|--------|
| Badal | ? | 1462108627 | 41.375543 | 2.127334 | ⬜ Usar |
| Badal | ? | 1462108628 | 41.375628 | 2.127335 | ⬜ Usar |
| Baró de Viver | ? | 879345341 | 41.449891 | 2.199536 | ⬜ Usar |
| Baró de Viver | ? | 879345342 | 41.449983 | 2.199564 | ⬜ Usar |
| Can Serra | ? | 1267720241 | 41.367647 | 2.102778 | ⬜ Usar |
| Can Serra | ? | 1267720242 | 41.367742 | 2.102739 | ⬜ Usar |
| Cornellà Centre | L5 | 1463163716 | 41.357347 | 2.070435 | ⬜ Usar |
| Cornellà Centre | L5 | 1463163717 | 41.357246 | 2.070440 | ⬜ Usar |
| Drassanes | ? | 1215124988 | 41.376513 | 2.175712 | ⬜ Usar |
| Drassanes | ? | 1215124989 | 41.376559 | 2.175607 | ⬜ Usar |
| El Carmel | ? | 908321209 | 41.424403 | 2.155179 | ⬜ Usar |
| El Carmel | ? | 908321210 | 41.424397 | 2.155050 | ⬜ Usar |
| Horta | ? | 1463163722 | 41.429674 | 2.160370 | ⬜ Usar |
| Hostafrancs | ? | 1233408731 | 41.375208 | 2.143429 | ⬜ Usar |
| Hostafrancs | ? | 1233408732 | 41.375287 | 2.143433 | ⬜ Usar |
| La Pau | L4 | 882897751 | 41.423648 | 2.205157 | ⬜ Usar |
| La Pau | L4 | 882897752 | 41.423709 | 2.205242 | ⬜ Usar |
| La Pau | L2 | 882897741 | 41.424022 | 2.205553 | ⬜ Usar |
| La Pau | L2 | 882897742 | 41.424056 | 2.205676 | ⬜ Usar |
| Liceu | ? | 1210421932 | 41.381452 | 2.172961 | ⬜ Usar |
| Liceu | ? | 1210421933 | 41.381493 | 2.173048 | ⬜ Usar |
| Marina | ? | 867486260 | 41.394733 | 2.185804 | ⬜ Usar |
| Marina | ? | 867486261 | 41.394765 | 2.185778 | ⬜ Usar |
| Mercat Nou | ? | 812545730 | 41.373117 | 2.133615 | ⬜ Usar |
| Monumental | ? | 895527694 | 41.400437 | 2.179337 | ⬜ Usar |
| Monumental | ? | 895527695 | 41.400612 | 2.179585 | ⬜ Usar |
| Plaça de Sants | L1 | 1232876458 | 41.375337 | 2.137984 | ⬜ Usar |
| Plaça de Sants | L1 | 1232876459 | 41.375412 | 2.137988 | ⬜ Usar |
| Rambla Just Oliveras | ? | 563932501 | 41.364016 | 2.099883 | ⬜ Usar |
| Rambla Just Oliveras | ? | 563932503 | 41.364001 | 2.099817 | ⬜ Usar |
| Rocafort | ? | 867472389 | 41.379200 | 2.154619 | ⬜ Usar |
| Rocafort | ? | 867472390 | 41.379273 | 2.154526 | ⬜ Usar |
| Sant Antoni | ? | 1461308278 | 41.379790 | 2.163269 | ⬜ Usar |
| Urgell | ? | 867477476 | 41.382456 | 2.158944 | ⬜ Usar |
| Urgell | ? | 867477477 | 41.382527 | 2.158848 | ⬜ Usar |

---

## 4. Checklist de revisión

### 4.1 Estaciones OSM sin match - VERIFICADO ✅
- [x] Arc de Triomf → Match directo
- [x] Catalunya → BD usa "Plaça de Catalunya"
- [x] Espanya L1/L3 → Vincular a "Espanya" padre
- [x] La Sagrera → Match directo
- [x] Metro Urquinaona → Eliminar prefijo, usar "Urquinaona"
- [x] Passeig de Gràcia → Match directo (L2/L3/L4 al mismo padre)
- [x] Sagrada Família → Match directo
- [x] Trinitat Nova → Match directo
- [x] Universitat → Match directo
- [x] Urquinaona → Match directo
- [x] Verdaguer → Match directo
- [x] Virrei Amat → Match directo
- [x] Paral·lel → Match directo

### 4.2 Decisiones tomadas
- [x] ~~¿Ignorar estaciones bus en OSM?~~ → **SÍ, solo metro**
- [x] ~~¿Mapeo estaciones OSM sin match?~~ → **VERIFICADO, 14 estaciones mapeadas**
- [ ] ¿Actualizar coordenadas de andenes BD con OSM donde hay match?
- [ ] ¿Re-ejecutar extracción OSM para obtener datos faltantes (89 estaciones)?

---

## Notas

- **Extracción OSM:** Hubo timeouts (429/504), datos parciales
- **89 estaciones BD sin OSM:** Pueden obtenerse con otra extracción
- **32 estaciones OSM de bus:** IGNORADAS (solo metro)
- **14 estaciones OSM metro sin match:** ✅ VERIFICADAS Y MAPEADAS

**Siguiente paso:** Población con datos OSM (actualizar coordenadas andenes).

---

## 5. INCONSISTENCIAS POST-POBLACIÓN (Revisión 2026-01-31)

### 5.1 Andenes sin coordenadas OSM (120 de 165) - RESUELTO

**Causa REAL:** OSM no tiene datos de andenes mapeados para 109 estaciones TMB.
No es timeout - es falta de datos en OpenStreetMap.

**Re-extracción ejecutada (2026-01-31 04:50):** Sin timeouts, mismo resultado.
- OSM tiene datos para: 67 estaciones (108 andenes)
- OSM NO tiene datos para: 109 estaciones

**Decisión:** Opción B - Aceptar como está (coords de estación padre como aproximación).

**Estaciones principales SIN datos OSM:**
Aeroport T1/T2, Barceloneta, Diagonal, Clot, Sants Estació,
Bogatell, Ciutadella, Congrés, Fabra i Puig, Fondo, etc.

---

### 5.2 Correspondencias con distancia > 500m - RESUELTO

**Problema:** TMB Passeig de Gràcia ↔ FGC Provença = 874m (demasiado lejos)

**Decisión:** Opción A - ELIMINADAS

**Ejecutado (2026-01-31):**
```sql
DELETE FROM stop_correspondence
WHERE (from_stop_id LIKE 'TMB_METRO_%' AND to_stop_id LIKE 'FGC_PR%')
   OR (from_stop_id LIKE 'FGC_PR%' AND to_stop_id LIKE 'TMB_METRO_%');
-- 8 correspondencias eliminadas
```

**Nota:** El transbordo real a FGC desde Passeig de Gràcia es vía RENFE, no FGC Provença.
Diagonal (L3/L5) sí tiene conexión directa con FGC Provença.

---

### 5.3 Andenes complejos sin datos OSM - RESUELTO

**Decisión:** Opción A - Coordenadas manuales aplicadas

**Ejecutado (2026-01-31):**
```sql
UPDATE gtfs_stops SET lat = 41.3900, lon = 2.1679 WHERE id = 'TMB_METRO_1.425';
-- Passeig de Gràcia L4 (Sector Gran Via/Consell de Cent)

UPDATE gtfs_stops SET lat = 41.3750, lon = 2.1608 WHERE id = 'TMB_METRO_1.9901';
-- Paral·lel Funicular (Mismo nivel que andenes metro)
```

| ID | Estación | Línea | Coords aplicadas |
|----|----------|-------|------------------|
| TMB_METRO_1.425 | Passeig de Gràcia | L4 | 41.3900, 2.1679 ✅ |
| TMB_METRO_1.9901 | Paral·lel | Funi | 41.3750, 2.1608 ✅ |

---

### 5.4 Verificación de correspondencias FGC/RENFE

**Todas las paradas referenciadas EXISTEN en BD:** ✅

| Operador | Paradas | Estado |
|----------|---------|--------|
| FGC | 13 | ✅ Todas existen |
| RENFE | 6 | ✅ Todas existen |

---

## Checklist de Revisión

- [x] 5.1 Andenes sin OSM → Aceptado (OSM no tiene datos, no es timeout)
- [x] 5.2 Passeig de Gràcia ↔ Provença → ELIMINADO (874m demasiado lejos)
- [x] 5.3 Andenes L4 PdG y Funicular → COORDS MANUALES aplicadas

**Revisión completada 2026-01-31.**

