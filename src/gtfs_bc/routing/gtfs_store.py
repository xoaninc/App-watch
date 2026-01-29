"""GTFSStore - Singleton de datos GTFS en memoria para RAPTOR.

Este módulo implementa un almacén de datos en RAM que se carga una sola vez
al iniciar el servidor, eliminando las queries SQL de cada petición.

Optimizaciones implementadas:
- Tuplas nativas en lugar de objetos (menor memoria)
- sys.intern() para strings repetidos (20-30% menos RAM)
- gc.freeze() para evitar overhead del GC
- Raw SQL en lugar de ORM para carga rápida

Uso de memoria estimado: ~300-400 MB para 260k trips / 2M stop_times

Author: Claude (Anthropic)
Date: 2026-01-28
"""

import gc
import sys
import time
import threading
from collections import defaultdict
from datetime import date
from typing import Dict, List, Set, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class GTFSStore:
    """Singleton que mantiene datos GTFS en memoria para RAPTOR.

    Estructuras optimizadas para acceso O(1) en el algoritmo.
    Usa tipos nativos Python (dict, list, tuple) para minimizar memoria.

    Thread-safe para lectura concurrente (múltiples requests).
    Usa Lock para recargas seguras.
    """

    _instance: Optional['GTFSStore'] = None
    _lock = threading.Lock()

    def __init__(self):
        # ===== ESTRUCTURAS PARA RAPTOR (PATTERNS) =====

        # 1. Trips agrupados por PATTERN (secuencia unica de paradas)
        # {pattern_id: [(departure_seconds, trip_id), ...]} ordenado por departure
        self.trips_by_pattern: Dict[str, List[Tuple[int, str]]] = {}

        # 2. Secuencia de paradas de cada pattern
        # {pattern_id: [stop_id, stop_id, ...]}
        self.stops_by_pattern: Dict[str, List[str]] = {}

        # 3. Indice inverso: que patterns pasan por cada parada
        # {stop_id: {pattern_id, pattern_id, ...}}
        self.patterns_by_stop: Dict[str, Set[str]] = defaultdict(set)

        # 4. Stop times por trip (necesario para buscar horarios exactos)
        # {trip_id: [(stop_id, arrival_sec, departure_sec), ...]} ordenado por sequence
        self.stop_times_by_trip: Dict[str, List[Tuple[str, int, int]]] = {}

        # 5. Transbordos (footpaths)
        # {from_stop_id: [(to_stop_id, walk_seconds), ...]}
        self.transfers: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

        # ===== ESTRUCTURAS AUXILIARES =====

        # 6. Info de trips para reconstrucción de ruta
        # {trip_id: (route_id, headsign, service_id)} - tupla para menor memoria
        self.trips_info: Dict[str, Tuple[str, Optional[str], str]] = {}

        # 7. Info de paradas para respuesta API
        # {stop_id: (name, lat, lon)} - tupla para menor memoria
        self.stops_info: Dict[str, Tuple[str, float, float]] = {}

        # 8. Info de rutas para respuesta API
        # {route_id: (short_name, color, route_type)}
        self.routes_info: Dict[str, Tuple[str, Optional[str], int]] = {}

        # 9. Calendarios activos por día de semana
        # {'monday': {service_id, ...}, 'tuesday': {...}, ...}
        self.services_by_weekday: Dict[str, Set[str]] = {
            'monday': set(), 'tuesday': set(), 'wednesday': set(),
            'thursday': set(), 'friday': set(), 'saturday': set(), 'sunday': set()
        }

        # 10. Excepciones de calendario (calendar_dates)
        # {date_str: {'added': {service_ids}, 'removed': {service_ids}}}
        self.calendar_exceptions: Dict[str, Dict[str, Set[str]]] = {}

        # 11. Hijos por padre (para resolver estaciones -> andenes)
        # {parent_station_id: [child_stop_id, ...]}
        self.children_by_parent: Dict[str, List[str]] = defaultdict(list)

        # Estado
        self.is_loaded = False
        self.load_time_seconds = 0.0
        self.stats: Dict[str, int] = {}
        self._reload_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'GTFSStore':
        """Obtener instancia singleton (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Resetear singleton (para tests o recarga completa)."""
        with cls._lock:
            cls._instance = None

    def load_data(self, db_session: 'Session') -> None:
        """Cargar todos los datos GTFS en memoria.

        Este método se ejecuta UNA SOLA VEZ al iniciar el servidor.
        Tiempo estimado: 30-60 segundos para ~260k trips.

        Args:
            db_session: Sesión de SQLAlchemy
        """
        if self.is_loaded:
            return

        with self._reload_lock:
            if self.is_loaded:  # Double-check
                return

            self._do_load(db_session)

    def reload_data(self, db_session: 'Session') -> None:
        """Recargar datos (para actualización sin reiniciar servidor).

        Thread-safe: usa lock para evitar corrupción durante recarga.
        """
        with self._reload_lock:
            # Limpiar estructuras
            self._clear_data()
            self.is_loaded = False

            # Recargar
            self._do_load(db_session)

    def _clear_data(self) -> None:
        """Limpiar todas las estructuras de datos."""
        self.trips_by_pattern.clear()
        self.stops_by_pattern.clear()
        self.patterns_by_stop.clear()
        self.stop_times_by_trip.clear()
        self.transfers.clear()
        self.trips_info.clear()
        self.stops_info.clear()
        self.routes_info.clear()
        self.children_by_parent.clear()
        for day in self.services_by_weekday:
            self.services_by_weekday[day].clear()
        self.calendar_exceptions.clear()
        self.stats.clear()

    def _do_load(self, db_session: 'Session') -> None:
        """Implementación interna de carga de datos."""
        from sqlalchemy import text

        start = time.time()
        print("🚀 Iniciando carga de GTFS en memoria...")

        # 1. Cargar paradas
        print("  📍 Cargando paradas...")
        result = db_session.execute(text("""
            SELECT id, name, lat, lon, parent_station_id FROM gtfs_stops
        """))

        for row in result:
            stop_id = sys.intern(row[0])  # Interning para ahorrar RAM
            name = row[1] or ""
            lat = float(row[2]) if row[2] else 0.0
            lon = float(row[3]) if row[3] else 0.0
            parent_id = sys.intern(row[4]) if row[4] else None

            self.stops_info[stop_id] = (name, lat, lon)

            # Indexar hijo si tiene padre
            if parent_id:
                self.children_by_parent[parent_id].append(stop_id)

        self.stats['stops'] = len(self.stops_info)
        print(f"    ✓ {self.stats['stops']:,} paradas")

        # 2. Cargar rutas
        print("  🚇 Cargando rutas...")
        result = db_session.execute(text("""
            SELECT id, short_name, color, route_type FROM gtfs_routes
        """))

        for row in result:
            route_id = sys.intern(row[0])
            short_name = (row[1] or "").strip()
            color = row[2]
            route_type = row[3] or 0
            self.routes_info[route_id] = (short_name, color, route_type)

        self.stats['routes'] = len(self.routes_info)
        print(f"    ✓ {self.stats['routes']:,} rutas")

        # 3. Cargar calendarios
        print("  📅 Cargando calendarios...")
        today = date.today()

        result = db_session.execute(text("""
            SELECT service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday
            FROM gtfs_calendar
            WHERE start_date <= :today AND end_date >= :today
        """), {'today': today})

        calendar_count = 0
        for row in result:
            service_id = sys.intern(row[0])
            if row[1]: self.services_by_weekday['monday'].add(service_id)
            if row[2]: self.services_by_weekday['tuesday'].add(service_id)
            if row[3]: self.services_by_weekday['wednesday'].add(service_id)
            if row[4]: self.services_by_weekday['thursday'].add(service_id)
            if row[5]: self.services_by_weekday['friday'].add(service_id)
            if row[6]: self.services_by_weekday['saturday'].add(service_id)
            if row[7]: self.services_by_weekday['sunday'].add(service_id)
            calendar_count += 1

        self.stats['calendars'] = calendar_count
        print(f"    ✓ {calendar_count:,} calendarios activos")

        # 4. Cargar excepciones de calendario (calendar_dates)
        print("  📅 Cargando excepciones de calendario...")
        result = db_session.execute(text("""
            SELECT service_id, date, exception_type
            FROM gtfs_calendar_dates
        """))

        exception_count = 0
        for row in result:
            service_id = sys.intern(row[0])
            date_str = str(row[1])
            exception_type = row[2]

            if date_str not in self.calendar_exceptions:
                self.calendar_exceptions[date_str] = {'added': set(), 'removed': set()}

            if exception_type == 1:
                self.calendar_exceptions[date_str]['added'].add(service_id)
            elif exception_type == 2:
                self.calendar_exceptions[date_str]['removed'].add(service_id)

            exception_count += 1

        self.stats['calendar_exceptions'] = exception_count
        print(f"    ✓ {exception_count:,} excepciones")

        # 5. Cargar trips
        print("  🚆 Cargando trips...")
        result = db_session.execute(text("""
            SELECT id, route_id, service_id, headsign FROM gtfs_trips
        """))

        trip_to_route: Dict[str, str] = {}
        for row in result:
            trip_id = sys.intern(row[0])
            route_id = sys.intern(row[1])
            service_id = sys.intern(row[2]) if row[2] else ""
            headsign = row[3]

            trip_to_route[trip_id] = route_id
            self.trips_info[trip_id] = (route_id, headsign, service_id)

        self.stats['trips'] = len(self.trips_info)
        print(f"    ✓ {self.stats['trips']:,} trips")

        # 6. Cargar stop_times (la tabla más grande)
        print("  ⏱️  Cargando stop_times (~2M registros)...")

        # Query optimizada: solo campos necesarios, ordenado por trip y sequence
        result = db_session.execute(text("""
            SELECT trip_id, stop_id, arrival_seconds, departure_seconds
            FROM gtfs_stop_times
            ORDER BY trip_id, stop_sequence
        """))

        # Procesar y construir estructuras
        temp_stop_times: Dict[str, List[Tuple[str, int, int]]] = defaultdict(list)
        count = 0

        for row in result:
            trip_id = sys.intern(row[0])
            stop_id = sys.intern(row[1])
            arr_sec = row[2] or 0
            dep_sec = row[3] or 0

            temp_stop_times[trip_id].append((stop_id, arr_sec, dep_sec))

            count += 1
            if count % 500000 == 0:
                print(f"      Procesados {count:,} stop_times...")

        self.stop_times_by_trip = dict(temp_stop_times)
        self.stats['stop_times'] = count
        print(f"    ✓ {count:,} stop_times")

        # 7. Construir PATTERNS (Rutas unicas por secuencia de paradas)
        print("  🔄 Construyendo Patterns (Rutas unicas)...")

        # Diccionario temporal para agrupar:
        # Clave: (route_id, tupla_de_paradas)
        # Valor: lista de trip_ids
        temp_patterns: Dict[Tuple[str, Tuple[str, ...]], List[str]] = defaultdict(list)

        # Iterar todos los trips para sacar su firma (secuencia de paradas)
        for trip_id, stops_data in self.stop_times_by_trip.items():
            if not stops_data:
                continue

            # stops_data es lista de (stop_id, arr, dep). Extraemos solo stop_id.
            stop_sequence = tuple(s[0] for s in stops_data)

            # Obtener route_id de trips_info (index 0 es route_id)
            trip_info = self.trips_info.get(trip_id)
            if not trip_info:
                continue
            route_id = trip_info[0]

            # Agrupar
            temp_patterns[(route_id, stop_sequence)].append(trip_id)

        # Procesar los grupos para crear los patterns finales
        for i, ((route_id, stop_seq), trips) in enumerate(temp_patterns.items()):
            # Crear ID unico para el pattern (ej: METRO_1_0, METRO_1_1)
            # Usamos sys.intern para ahorrar memoria en keys repetidas
            pattern_id = sys.intern(f"{route_id}_{i}")

            # 1. Guardar la secuencia de paradas
            self.stops_by_pattern[pattern_id] = list(stop_seq)

            # 2. Indexar paradas -> patterns
            for stop_id in stop_seq:
                self.patterns_by_stop[stop_id].add(pattern_id)

            # 3. Guardar trips del pattern ordenados por hora
            trip_list = []
            for t_id in trips:
                # Obtener hora de salida de la PRIMERA parada
                first_departure = self.stop_times_by_trip[t_id][0][2]  # index 2 = departure
                trip_list.append((first_departure, t_id))

            # Ordenar por tiempo (CRITICO para RAPTOR)
            trip_list.sort(key=lambda x: x[0])
            self.trips_by_pattern[pattern_id] = trip_list

        self.stats['patterns'] = len(self.trips_by_pattern)
        print(f"    ✓ {len(self.trips_by_pattern):,} patterns creados a partir de {len(self.trips_info):,} trips")

        # Limpiar memoria temporal
        del temp_patterns

        # 8. Cargar transbordos (CON EXPANSIÓN INTELIGENTE)
        print("  🚶 Cargando transbordos y expandiendo a andenes...")
        result = db_session.execute(text("""
            SELECT from_stop_id, to_stop_id, walk_time_s
            FROM stop_correspondence
            WHERE walk_time_s IS NOT NULL
        """))

        transfer_count = 0
        for row in result:
            raw_from = sys.intern(row[0])
            raw_to = sys.intern(row[1])
            walk_secs = row[2]

            if raw_from == raw_to or walk_secs <= 0:
                continue

            # 1. Expandir ORIGEN
            # Si 'raw_from' es un padre, obtenemos sus hijos. Si no, usamos 'raw_from' tal cual.
            from_stops = self.children_by_parent.get(raw_from)
            if not from_stops:
                from_stops = [raw_from]

            # 2. Expandir DESTINO
            # Si 'raw_to' es un padre (ej. METRO_BILBAO_7), obtenemos sus andenes (7.0, 7.1).
            to_stops = self.children_by_parent.get(raw_to)
            if not to_stops:
                to_stops = [raw_to]

            # 3. Producto Cartesiano: Conectar TODOS con TODOS
            # Esto asegura que si llego al Andén 1, puedo transbordar al Andén 2 de la otra línea
            for f in from_stops:
                for t in to_stops:
                    if f != t:
                        self.transfers[f].append((t, walk_secs))
                        transfer_count += 1

        self.stats['transfers'] = transfer_count
        print(f"    ✓ {transfer_count:,} transbordos (tras expansión)")

        # 9. Cargar accesos de Metro Madrid y Metro Ligero como puntos de entrada virtuales
        print("  🚪 Cargando accesos de Metro Madrid y Metro Ligero...")
        from adapters.http.api.gtfs.utils.shape_utils import haversine_distance

        access_result = db_session.execute(text("""
            SELECT id, stop_id, name, lat, lon
            FROM stop_access
            WHERE stop_id LIKE 'METRO\\_%' OR stop_id LIKE 'ML\\_%'
        """))

        access_count = 0
        access_transfers = 0

        for row in access_result:
            access_id = row[0]
            station_id = row[1]  # e.g., METRO_SOL
            access_name = row[2]
            access_lat = row[3]
            access_lon = row[4]

            # Crear ID virtual para el acceso
            virtual_access_id = sys.intern(f"ACCESS_{access_id}")

            # Añadir a stops_info para que RAPTOR pueda usarlo
            self.stops_info[virtual_access_id] = (access_name, access_lat, access_lon)
            access_count += 1

            # Buscar plataformas de esta estación
            # Primero intentar hijos directos
            platform_ids = self.children_by_parent.get(station_id, [])

            # Si no hay hijos, la estación es la plataforma
            if not platform_ids:
                platform_ids = [station_id] if station_id in self.stops_info else []

            # Crear transfers bidireccionales acceso <-> plataformas
            for platform_id in platform_ids:
                platform_info = self.stops_info.get(platform_id)
                if not platform_info:
                    continue

                platform_lat = platform_info[1]
                platform_lon = platform_info[2]

                # Calcular distancia y tiempo de caminata
                distance_m = haversine_distance(access_lat, access_lon, platform_lat, platform_lon)
                walk_seconds = int(distance_m / 1.25)  # 4.5 km/h = 1.25 m/s

                # Mínimo 30 segundos (tiempo de bajar escaleras, etc.)
                walk_seconds = max(walk_seconds, 30)

                # Añadir transfer acceso -> plataforma
                if virtual_access_id not in self.transfers:
                    self.transfers[virtual_access_id] = []
                self.transfers[virtual_access_id].append((platform_id, walk_seconds))

                # Añadir transfer plataforma -> acceso (para salir)
                if platform_id not in self.transfers:
                    self.transfers[platform_id] = []
                self.transfers[platform_id].append((virtual_access_id, walk_seconds))

                access_transfers += 2

        self.stats['accesses'] = access_count
        self.stats['access_transfers'] = access_transfers
        print(f"    ✓ {access_count:,} accesos cargados, {access_transfers:,} transfers creados")

        # Limpiar memoria temporal
        del trip_to_route
        del temp_stop_times

        # Convertir defaultdicts a dicts normales
        self.patterns_by_stop = dict(self.patterns_by_stop)
        self.transfers = dict(self.transfers)

        # Finalizar
        self.is_loaded = True
        self.load_time_seconds = time.time() - start

        # Garbage collection optimization
        gc.collect()
        gc.freeze()  # Mueve objetos a generación permanente

        print(f"✅ GTFS cargado en {self.load_time_seconds:.1f}s")
        print(f"   Estadísticas: {self.stats}")

    # =========================================================================
    # MÉTODOS DE ACCESO RÁPIDO PARA RAPTOR
    # =========================================================================

    def get_active_services(self, travel_date: date) -> Set[str]:
        """Obtener service_ids activos para una fecha.

        Args:
            travel_date: Fecha de viaje

        Returns:
            Set de service_ids activos
        """
        weekday = travel_date.weekday()
        weekday_names = ['monday', 'tuesday', 'wednesday', 'thursday',
                         'friday', 'saturday', 'sunday']

        active = self.services_by_weekday[weekday_names[weekday]].copy()

        # Aplicar excepciones
        date_str = travel_date.isoformat()
        if date_str in self.calendar_exceptions:
            exc = self.calendar_exceptions[date_str]
            active.update(exc.get('added', set()))
            active -= exc.get('removed', set())

        return active

    def get_earliest_trip(
        self,
        pattern_id: str,
        stop_index: int,
        min_departure: int,
        active_services: Set[str]
    ) -> Optional[str]:
        """Encontrar el trip mas temprano en un PATTERN desde una parada especifica.

        Esta es la operacion mas frecuente en RAPTOR.
        Complejidad: O(n) donde n = trips en el pattern.

        Args:
            pattern_id: ID del pattern (ej: METRO_1_0)
            stop_index: Indice de la parada en la secuencia del pattern (0, 1, 2...)
            min_departure: Tiempo minimo de salida desde ESA parada
            active_services: Set de service_ids activos hoy

        Returns:
            trip_id del primer trip valido, o None
        """
        trips = self.trips_by_pattern.get(pattern_id, [])

        for _, trip_id in trips:
            # Acceso directo por indice O(1)
            # Todos los trips del pattern tienen la misma secuencia de paradas
            try:
                stop_time_data = self.stop_times_by_trip[trip_id][stop_index]
                # stop_time_data es (stop_id, arrival, departure) -> index 2 es departure
                real_departure = stop_time_data[2]
            except (IndexError, KeyError):
                continue

            if real_departure >= min_departure:
                # Verificar que el servicio esta activo
                trip_info = self.trips_info.get(trip_id)
                if trip_info and trip_info[2] in active_services:
                    return trip_id

        return None

    def get_patterns_at_stop(self, stop_id: str) -> Set[str]:
        """Obtener patterns que pasan por una parada.

        Complejidad: O(1)

        Args:
            stop_id: ID de la parada

        Returns:
            Set de pattern_ids (vacio si no hay patterns)
        """
        return self.patterns_by_stop.get(stop_id, set())

    def get_pattern_stops(self, pattern_id: str) -> List[str]:
        """Obtener secuencia de paradas de un pattern.

        Complejidad: O(1)

        Args:
            pattern_id: ID del pattern

        Returns:
            Lista ordenada de stop_ids
        """
        return self.stops_by_pattern.get(pattern_id, [])

    def get_stop_times(self, trip_id: str) -> List[Tuple[str, int, int]]:
        """Obtener secuencia de paradas de un trip.

        Complejidad: O(1)

        Args:
            trip_id: ID del trip

        Returns:
            Lista de tuplas (stop_id, arrival_seconds, departure_seconds)
        """
        return self.stop_times_by_trip.get(trip_id, [])

    def get_transfers(self, stop_id: str) -> List[Tuple[str, int]]:
        """Obtener transbordos desde una parada.

        Complejidad: O(1)

        Args:
            stop_id: ID de la parada origen

        Returns:
            Lista de tuplas (to_stop_id, walk_seconds)
        """
        return self.transfers.get(stop_id, [])

    def get_trip_info(self, trip_id: str) -> Optional[Tuple[str, Optional[str], str]]:
        """Obtener información de un trip.

        Args:
            trip_id: ID del trip

        Returns:
            Tupla (route_id, headsign, service_id) o None
        """
        return self.trips_info.get(trip_id)

    def get_stop_info(self, stop_id: str) -> Optional[Tuple[str, float, float]]:
        """Obtener información de una parada.

        Args:
            stop_id: ID de la parada

        Returns:
            Tupla (name, lat, lon) o None
        """
        return self.stops_info.get(stop_id)

    def get_route_info(self, route_id: str) -> Optional[Tuple[str, Optional[str], int]]:
        """Obtener información de una ruta.

        Args:
            route_id: ID de la ruta

        Returns:
            Tupla (short_name, color, route_type) o None
        """
        return self.routes_info.get(route_id)

    def get_children_stops(self, stop_id: str) -> List[str]:
        """Obtener IDs de andenes hijos para una estación padre.

        Args:
            stop_id: ID de la estación padre

        Returns:
            Lista de IDs de andenes hijos (vacía si no tiene hijos)
        """
        return self.children_by_parent.get(stop_id, [])


# Singleton global para importación directa
gtfs_store = GTFSStore.get_instance()
