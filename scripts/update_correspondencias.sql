-- =====================================================
-- Script para actualizar correspondencias (cor_*) en gtfs_stops
-- Generado automáticamente desde GTFS oficiales
-- Fecha: 2026-01-26
-- =====================================================

BEGIN;

-- =====================================================
-- EUSKOTREN - cor_cercanias (líneas E1-E5, FCC, L3, TR, TG1, TG2, 41, FE)
-- =====================================================

-- Atxuri (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Atxuri%' AND id LIKE 'EUSKOTREN%';

-- Uribitarte (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Uribitarte%' AND id LIKE 'EUSKOTREN%';

-- San Mames (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%San Mames%' AND id LIKE 'EUSKOTREN%';

-- Abando (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Abando%' AND id LIKE 'EUSKOTREN%';

-- Hospital/Ospitalea (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Hospital/Ospitalea%' AND id LIKE 'EUSKOTREN%';

-- Ribera (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Ribera%' AND id LIKE 'EUSKOTREN%';

-- Sabino Arana (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Sabino Arana%' AND id LIKE 'EUSKOTREN%';

-- Abandoibarra (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Abandoibarra%' AND id LIKE 'EUSKOTREN%';

-- Guggenheim (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Guggenheim%' AND id LIKE 'EUSKOTREN%';

-- La Casilla (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%La Casilla%' AND id LIKE 'EUSKOTREN%';

-- Pio Baroja (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Pio Baroja%' AND id LIKE 'EUSKOTREN%';

-- Euskalduna (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Euskalduna%' AND id LIKE 'EUSKOTREN%';

-- Arriaga (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Arriaga%' AND id LIKE 'EUSKOTREN%';

-- Basurto (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Basurto%' AND id LIKE 'EUSKOTREN%';

-- Gernikako Arbola (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG1' WHERE name ILIKE '%Gernikako Arbola%' AND id LIKE 'EUSKOTREN%';

-- Abetxuko (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG1' WHERE name ILIKE '%Abetxuko%' AND id LIKE 'EUSKOTREN%';

-- Lovaina (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG1, TG2' WHERE name ILIKE '%Lovaina%' AND id LIKE 'EUSKOTREN%';

-- Landaberde (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG2' WHERE name ILIKE '%Landaberde%' AND id LIKE 'EUSKOTREN%';

-- Forondako Atea/Portal De Foronda (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG1' WHERE name ILIKE '%Forondako Atea/Portal De Foronda%' AND id LIKE 'EUSKOTREN%';

-- Legebiltzarra/Parlamento (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG1, TG2' WHERE name ILIKE '%Legebiltzarra/Parlamento%' AND id LIKE 'EUSKOTREN%';

-- Ibaiondo (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG2' WHERE name ILIKE '%Ibaiondo%' AND id LIKE 'EUSKOTREN%';

-- Europa (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG1, TG2' WHERE name ILIKE '%Europa%' AND id LIKE 'EUSKOTREN%';

-- Lakuabizkarra (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG2' WHERE name ILIKE '%Lakuabizkarra%' AND id LIKE 'EUSKOTREN%';

-- Kristo (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG1' WHERE name ILIKE '%Kristo%' AND id LIKE 'EUSKOTREN%';

-- Artapadura (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG1' WHERE name ILIKE '%Artapadura%' AND id LIKE 'EUSKOTREN%';

-- Arriaga (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG1' WHERE name ILIKE '%Arriaga%' AND id LIKE 'EUSKOTREN%';

-- Intermodal (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG1' WHERE name ILIKE '%Intermodal%' AND id LIKE 'EUSKOTREN%';

-- Honduras (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG1, TG2' WHERE name ILIKE '%Honduras%' AND id LIKE 'EUSKOTREN%';

-- Angulema (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG1, TG2' WHERE name ILIKE '%Angulema%' AND id LIKE 'EUSKOTREN%';

-- Euskal Herria (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG2' WHERE name ILIKE '%Euskal Herria%' AND id LIKE 'EUSKOTREN%';

-- Antso Jakituna/Sancho El Sabio (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG1, TG2' WHERE name ILIKE '%Antso Jakituna/Sancho El Sabio%' AND id LIKE 'EUSKOTREN%';

-- Wellington (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG2' WHERE name ILIKE '%Wellington%' AND id LIKE 'EUSKOTREN%';

-- Kañabenta (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG1' WHERE name ILIKE '%Kañabenta%' AND id LIKE 'EUSKOTREN%';

-- Txagorritxu (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG2' WHERE name ILIKE '%Txagorritxu%' AND id LIKE 'EUSKOTREN%';

-- La Escontrilla
UPDATE gtfs_stops SET cor_cercanias = 'FE' WHERE name ILIKE '%La Escontrilla%' AND id LIKE 'EUSKOTREN%';

-- Larreineta
UPDATE gtfs_stops SET cor_cercanias = 'FE' WHERE name ILIKE '%Larreineta%' AND id LIKE 'EUSKOTREN%';

-- Lutxana-Erandio
UPDATE gtfs_stops SET cor_cercanias = 'E3a' WHERE name ILIKE '%Lutxana-Erandio%' AND id LIKE 'EUSKOTREN%';

-- Zazpikaleak/Casco Viejo-Bilbao
UPDATE gtfs_stops SET cor_cercanias = 'E1, E3, E4, FCC, L3' WHERE name ILIKE '%Zazpikaleak/Casco Viejo-Bilbao%' AND id LIKE 'EUSKOTREN%';

-- Bermeo
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Bermeo%' AND id LIKE 'EUSKOTREN%';

-- Lasarte-Oria
UPDATE gtfs_stops SET cor_cercanias = 'E2, FCC' WHERE name ILIKE '%Lasarte-Oria%' AND id LIKE 'EUSKOTREN%';

-- Amara-Donostia
UPDATE gtfs_stops SET cor_cercanias = 'E1, E2, E5, FCC' WHERE name ILIKE '%Amara-Donostia%' AND id LIKE 'EUSKOTREN%';

-- Hendaia
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Hendaia%' AND id LIKE 'EUSKOTREN%';

-- San Pelaio-Zarautz
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%San Pelaio-Zarautz%' AND id LIKE 'EUSKOTREN%';

-- Ola-Sondika
UPDATE gtfs_stops SET cor_cercanias = 'E3, FCC' WHERE name ILIKE '%Ola-Sondika%' AND id LIKE 'EUSKOTREN%';

-- Amorebieta Geralekua
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Amorebieta Geralekua%' AND id LIKE 'EUSKOTREN%';

-- Lemoa
UPDATE gtfs_stops SET cor_cercanias = 'E1, E4, FCC' WHERE name ILIKE '%Lemoa%' AND id LIKE 'EUSKOTREN%';

-- Lurgorri-Gernika
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Lurgorri-Gernika%' AND id LIKE 'EUSKOTREN%';

-- Irun
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Irun%' AND id LIKE 'EUSKOTREN%';

-- Anoeta-Donostia
UPDATE gtfs_stops SET cor_cercanias = 'E2, E5, FCC' WHERE name ILIKE '%Anoeta-Donostia%' AND id LIKE 'EUSKOTREN%';

-- Etxebarri
UPDATE gtfs_stops SET cor_cercanias = 'E1, E4, FCC' WHERE name ILIKE '%Etxebarri%' AND id LIKE 'EUSKOTREN%';

-- Aia-Orio
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%Aia-Orio%' AND id LIKE 'EUSKOTREN%';

-- Institutoa-Gernika
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Institutoa-Gernika%' AND id LIKE 'EUSKOTREN%';

-- Unibertsitatea-Eibar
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Unibertsitatea-Eibar%' AND id LIKE 'EUSKOTREN%';

-- Sondika
UPDATE gtfs_stops SET cor_cercanias = 'E3, E3a, FCC' WHERE name ILIKE '%Sondika%' AND id LIKE 'EUSKOTREN%';

-- Muxika
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Muxika%' AND id LIKE 'EUSKOTREN%';

-- Matiko-Bilbao
UPDATE gtfs_stops SET cor_cercanias = 'E1, E3, E4, FCC, L3' WHERE name ILIKE '%Matiko-Bilbao%' AND id LIKE 'EUSKOTREN%';

-- Zuhatzu-Galdakao
UPDATE gtfs_stops SET cor_cercanias = 'E1, E4, FCC' WHERE name ILIKE '%Zuhatzu-Galdakao%' AND id LIKE 'EUSKOTREN%';

-- Itsasbegi-Busturia
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Itsasbegi-Busturia%' AND id LIKE 'EUSKOTREN%';

-- Berriz
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%Berriz%' AND id LIKE 'EUSKOTREN%';

-- Larrondo-Loiu
UPDATE gtfs_stops SET cor_cercanias = 'E3, FCC' WHERE name ILIKE '%Larrondo-Loiu%' AND id LIKE 'EUSKOTREN%';

-- Errotabarri-Ermua
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Errotabarri-Ermua%' AND id LIKE 'EUSKOTREN%';

-- Traña-Abadiño
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%Traña-Abadiño%' AND id LIKE 'EUSKOTREN%';

-- Zumaia
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%Zumaia%' AND id LIKE 'EUSKOTREN%';

-- Euba-Amorebieta
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%Euba-Amorebieta%' AND id LIKE 'EUSKOTREN%';

-- Lezama
UPDATE gtfs_stops SET cor_cercanias = 'E3, FCC' WHERE name ILIKE '%Lezama%' AND id LIKE 'EUSKOTREN%';

-- Loiola-Donostia
UPDATE gtfs_stops SET cor_cercanias = 'E2, E5, FCC' WHERE name ILIKE '%Loiola-Donostia%' AND id LIKE 'EUSKOTREN%';

-- Txurdinaga-Bilbao
UPDATE gtfs_stops SET cor_cercanias = 'E1, E3, E4, FCC, L3' WHERE name ILIKE '%Txurdinaga-Bilbao%' AND id LIKE 'EUSKOTREN%';

-- Galtzaraborda-Errenteria
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Galtzaraborda-Errenteria%' AND id LIKE 'EUSKOTREN%';

-- Zangroiz-Sondika
UPDATE gtfs_stops SET cor_cercanias = 'E3a' WHERE name ILIKE '%Zangroiz-Sondika%' AND id LIKE 'EUSKOTREN%';

-- Oiartzun
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Oiartzun%' AND id LIKE 'EUSKOTREN%';

-- Arroa-Zestoa
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Arroa-Zestoa%' AND id LIKE 'EUSKOTREN%';

-- Derio
UPDATE gtfs_stops SET cor_cercanias = 'E3, FCC' WHERE name ILIKE '%Derio%' AND id LIKE 'EUSKOTREN%';

-- Axpe-Busturia
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Axpe-Busturia%' AND id LIKE 'EUSKOTREN%';

-- Mundaka
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Mundaka%' AND id LIKE 'EUSKOTREN%';

-- Zurbaranbarri-Bilbao
UPDATE gtfs_stops SET cor_cercanias = 'E1, E3, E4, FCC, L3' WHERE name ILIKE '%Zurbaranbarri-Bilbao%' AND id LIKE 'EUSKOTREN%';

-- Durango
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%Durango%' AND id LIKE 'EUSKOTREN%';

-- Eibar
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Eibar%' AND id LIKE 'EUSKOTREN%';

-- Bedia
UPDATE gtfs_stops SET cor_cercanias = 'E1, E4, FCC' WHERE name ILIKE '%Bedia%' AND id LIKE 'EUSKOTREN%';

-- Lugaritz-Donostia
UPDATE gtfs_stops SET cor_cercanias = 'E1, E2, FCC' WHERE name ILIKE '%Lugaritz-Donostia%' AND id LIKE 'EUSKOTREN%';

-- Elgoibar
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Elgoibar%' AND id LIKE 'EUSKOTREN%';

-- Herrera-Donostia
UPDATE gtfs_stops SET cor_cercanias = 'E2, E5, FCC' WHERE name ILIKE '%Herrera-Donostia%' AND id LIKE 'EUSKOTREN%';

-- Fanderia-Errenteria
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Fanderia-Errenteria%' AND id LIKE 'EUSKOTREN%';

-- Altzola-Elgoibar
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Altzola-Elgoibar%' AND id LIKE 'EUSKOTREN%';

-- San Lorentzo-Ermua
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%San Lorentzo-Ermua%' AND id LIKE 'EUSKOTREN%';

-- Elotxelerri-Loiu
UPDATE gtfs_stops SET cor_cercanias = 'E3, FCC' WHERE name ILIKE '%Elotxelerri-Loiu%' AND id LIKE 'EUSKOTREN%';

-- Altza-Donostia
UPDATE gtfs_stops SET cor_cercanias = 'E5, FCC' WHERE name ILIKE '%Altza-Donostia%' AND id LIKE 'EUSKOTREN%';

-- Bentak-Irun
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Bentak-Irun%' AND id LIKE 'EUSKOTREN%';

-- Deba
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Deba%' AND id LIKE 'EUSKOTREN%';

-- Amaña-Eibar
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Amaña-Eibar%' AND id LIKE 'EUSKOTREN%';

-- Belaskoenea-Irun
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Belaskoenea-Irun%' AND id LIKE 'EUSKOTREN%';

-- Amorebieta Geltokia
UPDATE gtfs_stops SET cor_cercanias = 'E1, E4, FCC' WHERE name ILIKE '%Amorebieta Geltokia%' AND id LIKE 'EUSKOTREN%';

-- Kurtzea-Lezama
UPDATE gtfs_stops SET cor_cercanias = 'E3, FCC' WHERE name ILIKE '%Kurtzea-Lezama%' AND id LIKE 'EUSKOTREN%';

-- Kukullaga-Etxebarri
UPDATE gtfs_stops SET cor_cercanias = 'E1, E3, E4, FCC, L3' WHERE name ILIKE '%Kukullaga-Etxebarri%' AND id LIKE 'EUSKOTREN%';

-- Azitain-Eibar
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Azitain-Eibar%' AND id LIKE 'EUSKOTREN%';

-- Uribarri-Bilbao
UPDATE gtfs_stops SET cor_cercanias = 'E1, E3, E4, FCC, L3' WHERE name ILIKE '%Uribarri-Bilbao%' AND id LIKE 'EUSKOTREN%';

-- Zamudio
UPDATE gtfs_stops SET cor_cercanias = 'E3, FCC' WHERE name ILIKE '%Zamudio%' AND id LIKE 'EUSKOTREN%';

-- Forua
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Forua%' AND id LIKE 'EUSKOTREN%';

-- Gernika
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Gernika%' AND id LIKE 'EUSKOTREN%';

-- Ariz-Basauri
UPDATE gtfs_stops SET cor_cercanias = 'E1, E4, FCC' WHERE name ILIKE '%Ariz-Basauri%' AND id LIKE 'EUSKOTREN%';

-- Añorga-Donostia
UPDATE gtfs_stops SET cor_cercanias = 'E1, E2, FCC' WHERE name ILIKE '%Añorga-Donostia%' AND id LIKE 'EUSKOTREN%';

-- Intxaurrondo-Donostia
UPDATE gtfs_stops SET cor_cercanias = 'E2, E5, FCC' WHERE name ILIKE '%Intxaurrondo-Donostia%' AND id LIKE 'EUSKOTREN%';

-- Ficoba-Irun
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Ficoba-Irun%' AND id LIKE 'EUSKOTREN%';

-- Mendaro
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Mendaro%' AND id LIKE 'EUSKOTREN%';

-- Errekalde-Donostia
UPDATE gtfs_stops SET cor_cercanias = 'E1, E2, FCC' WHERE name ILIKE '%Errekalde-Donostia%' AND id LIKE 'EUSKOTREN%';

-- Lekunbiz-Zamudio
UPDATE gtfs_stops SET cor_cercanias = 'E3, FCC' WHERE name ILIKE '%Lekunbiz-Zamudio%' AND id LIKE 'EUSKOTREN%';

-- Usurbil
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%Usurbil%' AND id LIKE 'EUSKOTREN%';

-- Gaintxurizketa-Lezo
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Gaintxurizketa-Lezo%' AND id LIKE 'EUSKOTREN%';

-- Zaldibar
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%Zaldibar%' AND id LIKE 'EUSKOTREN%';

-- Ardantza-Eibar
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Ardantza-Eibar%' AND id LIKE 'EUSKOTREN%';

-- Zugaztieta-Muxika
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%Zugaztieta-Muxika%' AND id LIKE 'EUSKOTREN%';

-- Toletxegain-Elgoibar
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Toletxegain-Elgoibar%' AND id LIKE 'EUSKOTREN%';

-- San Kristobal-Busturia
UPDATE gtfs_stops SET cor_cercanias = 'E4, FCC' WHERE name ILIKE '%San Kristobal-Busturia%' AND id LIKE 'EUSKOTREN%';

-- Usansolo
UPDATE gtfs_stops SET cor_cercanias = 'E1, E4, FCC' WHERE name ILIKE '%Usansolo%' AND id LIKE 'EUSKOTREN%';

-- Otxarkoaga-Bilbao
UPDATE gtfs_stops SET cor_cercanias = 'E1, E3, E4, FCC, L3' WHERE name ILIKE '%Otxarkoaga-Bilbao%' AND id LIKE 'EUSKOTREN%';

-- Zarautz
UPDATE gtfs_stops SET cor_cercanias = 'E1, FCC' WHERE name ILIKE '%Zarautz%' AND id LIKE 'EUSKOTREN%';

-- Errenteria
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Errenteria%' AND id LIKE 'EUSKOTREN%';

-- Ermua
UPDATE gtfs_stops SET cor_cercanias = 'E1' WHERE name ILIKE '%Ermua%' AND id LIKE 'EUSKOTREN%';

-- Pasaia
UPDATE gtfs_stops SET cor_cercanias = 'E2' WHERE name ILIKE '%Pasaia%' AND id LIKE 'EUSKOTREN%';

-- Hegoalde (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG1' WHERE name ILIKE '%Hegoalde%' AND id LIKE 'EUSKOTREN%';

-- Florida (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG1, TG2' WHERE name ILIKE '%Florida%' AND id LIKE 'EUSKOTREN%';

-- Unibertsitatea (tranvía)
UPDATE gtfs_stops SET cor_tranvia = '41, TG1' WHERE name ILIKE '%Unibertsitatea%' AND id LIKE 'EUSKOTREN%';

-- Abusu (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Abusu%' AND id LIKE 'EUSKOTREN%';

-- Bolueta (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TR' WHERE name ILIKE '%Bolueta%' AND id LIKE 'EUSKOTREN%';

-- Salburua (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG2' WHERE name ILIKE '%Salburua%' AND id LIKE 'EUSKOTREN%';

-- La Unión (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG2' WHERE name ILIKE '%La Unión%' AND id LIKE 'EUSKOTREN%';

-- Santa Luzia (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG2' WHERE name ILIKE '%Santa Luzia%' AND id LIKE 'EUSKOTREN%';

-- Iliada (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG2' WHERE name ILIKE '%Iliada%' AND id LIKE 'EUSKOTREN%';

-- Nikosia (tranvía)
UPDATE gtfs_stops SET cor_tranvia = 'TG2' WHERE name ILIKE '%Nikosia%' AND id LIKE 'EUSKOTREN%';


-- =====================================================
-- METRO BILBAO - cor_metro (líneas L1, L2, L3)
-- Nota: El GTFS de Metro Bilbao no distingue líneas,
-- hay que asignarlas manualmente basándose en las estaciones
-- =====================================================

-- L1: Etxebarri - Plentzia
-- L2: Basauri - Kabiezes
-- L3: Matiko - Kukullaga (compartida con Euskotren)

-- Estaciones solo L1
UPDATE gtfs_stops SET cor_metro = 'L1' WHERE id LIKE 'METRO_BILBAO%' AND name IN (
    'Plentzia', 'Sopela', 'Larrabasterra', 'Urduliz', 'Berango', 'Neguri', 'Aiboa',
    'Algorta', 'Bidezabal', 'Gobela', 'Neguri', 'Areeta', 'Las Arenas', 'Lamiako',
    'Leioa', 'Erandio', 'Astrabudua', 'Peñota', 'Lutxana', 'Bolueta', 'Etxebarri'
);

-- Estaciones solo L2
UPDATE gtfs_stops SET cor_metro = 'L2' WHERE id LIKE 'METRO_BILBAO%' AND name IN (
    'Kabiezes', 'Peñota', 'Santurtzi', 'Barakaldo', 'Bagatza', 'Cruces',
    'Ansio', 'Basauri', 'Ariz'
);

-- Estaciones L1 + L2 (troncal común)
UPDATE gtfs_stops SET cor_metro = 'L1, L2' WHERE id LIKE 'METRO_BILBAO%' AND name IN (
    'Abando', 'Moyua', 'Indautxu', 'San Mames', 'Deustu', 'Sarriko', 'Zazpikaleak/Casco Viejo'
);

-- Estaciones L3
UPDATE gtfs_stops SET cor_metro = 'L3' WHERE id LIKE 'METRO_BILBAO%' AND name IN (
    'Matiko', 'Uribarri', 'Zurbaranbarri', 'Txurdinaga', 'Kukullaga'
);


-- =====================================================
-- CORRESPONDENCIAS ENTRE REDES (intercambiadores)
-- =====================================================

-- Abando: Metro Bilbao + Euskotren Tranvía + Renfe Cercanías
UPDATE gtfs_stops SET cor_metro = 'L1, L2', cor_tranvia = 'TR'
WHERE id LIKE 'EUSKOTREN%' AND name ILIKE '%Abando%';

UPDATE gtfs_stops SET cor_cercanias = 'C4'
WHERE id LIKE 'METRO_BILBAO%' AND name ILIKE '%Abando%';

-- San Mamés: Metro Bilbao + Euskotren Tranvía + Renfe Cercanías
UPDATE gtfs_stops SET cor_metro = 'L1, L2', cor_tranvia = 'TR'
WHERE id LIKE 'EUSKOTREN%' AND name ILIKE '%San Mames%';

UPDATE gtfs_stops SET cor_cercanias = 'C3'
WHERE id LIKE 'METRO_BILBAO%' AND name ILIKE '%San Mames%';

-- Zazpikaleak/Casco Viejo: Metro Bilbao + Euskotren
UPDATE gtfs_stops SET cor_metro = 'L1, L2'
WHERE id LIKE 'EUSKOTREN%' AND name ILIKE '%Zazpikaleak%';

UPDATE gtfs_stops SET cor_cercanias = 'E1, E3, E4, L3'
WHERE id LIKE 'METRO_BILBAO%' AND name ILIKE '%Casco Viejo%';

-- Bolueta: Metro Bilbao + Euskotren Tranvía
UPDATE gtfs_stops SET cor_metro = 'L1, L2'
WHERE id LIKE 'EUSKOTREN%' AND name ILIKE '%Bolueta%';

COMMIT;

-- =====================================================
-- FIN DEL SCRIPT
-- =====================================================
