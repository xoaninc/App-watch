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
        # ===== ESTRUCTURAS PARA RAPTOR =====

        # 1. Trips ordenados por ruta y hora de salida
        # {route_id: [(departure_seconds, trip_id), ...]} ordenado por departure
        self.trips_by_route: Dict[str, List[Tuple[int, str]]] = {}

        # 2. Stop times por trip (secuencia de paradas)
        # {trip_id: [(stop_id, arrival_sec, departure_sec), ...]} ordenado por sequence
        self.stop_times_by_trip: Dict[str, List[Tuple[str, int, int]]] = {}

        # 3. Índice inverso: qué rutas pasan por cada parada
        # {stop_id: {route_id, route_id, ...}}
        self.routes_by_stop: Dict[str, Set[str]] = defaultdict(set)

        # 4. Transbordos (footpaths)
        # {from_stop_id: [(to_stop_id, walk_seconds), ...]}
        self.transfers: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

        # ===== ESTRUCTURAS AUXILIARES =====

        # 5. Info de trips para reconstrucción de ruta
        # {trip_id: (route_id, headsign, service_id)} - tupla para menor memoria
        self.trips_info: Dict[str, Tuple[str, Optional[str], str]] = {}

        # 6. Info de paradas para respuesta API
        # {stop_id: (name, lat, lon)} - tupla para menor memoria
        self.stops_info: Dict[str, Tuple[str, float, float]] = {}

        # 7. Info de rutas para respuesta API
        # {route_id: (short_name, color, route_type)}
        self.routes_info: Dict[str, Tuple[str, Optional[str], int]] = {}

        # 8. Calendarios activos por día de semana
        # {'monday': {service_id, ...}, 'tuesday': {...}, ...}
        self.services_by_weekday: Dict[str, Set[str]] = {
            'monday': set(), 'tuesday': set(), 'wednesday': set(),
            'thursday': set(), 'friday': set(), 'saturday': set(), 'sunday': set()
        }

        # 9. Excepciones de calendario (calendar_dates)
        # {date_str: {'added': {service_ids}, 'removed': {service_ids}}}
        self.calendar_exceptions: Dict[str, Dict[str, Set[str]]] = {}

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
        self.trips_by_route.clear()
        self.stop_times_by_trip.clear()
        self.routes_by_stop.clear()
        self.transfers.clear()
        self.trips_info.clear()
        self.stops_info.clear()
        self.routes_info.clear()
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
            SELECT id, name, lat, lon FROM gtfs_stops
        """))

        for row in result:
            stop_id = sys.intern(row[0])  # Interning para ahorrar RAM
            name = row[1] or ""
            lat = float(row[2]) if row[2] else 0.0
            lon = float(row[3]) if row[3] else 0.0
            self.stops_info[stop_id] = (name, lat, lon)

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

            # Índice inverso: routes_by_stop
            if trip_id in trip_to_route:
                route_id = trip_to_route[trip_id]
                self.routes_by_stop[stop_id].add(route_id)

            count += 1
            if count % 500000 == 0:
                print(f"      Procesados {count:,} stop_times...")

        self.stop_times_by_trip = dict(temp_stop_times)
        self.stats['stop_times'] = count
        print(f"    ✓ {count:,} stop_times")

        # 7. Construir trips_by_route ordenados por hora
        print("  🔄 Construyendo índice trips_by_route...")
        temp_trips_by_route: Dict[str, List[Tuple[int, str]]] = defaultdict(list)

        for trip_id, stops in self.stop_times_by_trip.items():
            if not stops or trip_id not in trip_to_route:
                continue

            route_id = trip_to_route[trip_id]
            first_departure = stops[0][2]  # índice 2 = departure_seconds
            temp_trips_by_route[route_id].append((first_departure, trip_id))

        # Ordenar cada lista por hora de salida
        for route_id, trip_list in temp_trips_by_route.items():
            trip_list.sort(key=lambda x: x[0])
            self.trips_by_route[route_id] = trip_list

        print(f"    ✓ {len(self.trips_by_route):,} rutas indexadas")

        # 8. Cargar transbordos
        print("  🚶 Cargando transbordos...")
        result = db_session.execute(text("""
            SELECT from_stop_id, to_stop_id, walk_time_s
            FROM stop_correspondence
            WHERE walk_time_s IS NOT NULL
        """))

        transfer_count = 0
        for row in result:
            from_stop = sys.intern(row[0])
            to_stop = sys.intern(row[1])
            walk_secs = row[2]

            # Sanity check: evitar transbordos A->A o con tiempo 0
            if from_stop != to_stop and walk_secs > 0:
                self.transfers[from_stop].append((to_stop, walk_secs))
                transfer_count += 1

        self.stats['transfers'] = transfer_count
        print(f"    ✓ {transfer_count:,} transbordos")

        # Limpiar memoria temporal
        del trip_to_route
        del temp_stop_times
        del temp_trips_by_route

        # Convertir routes_by_stop de defaultdict a dict normal
        self.routes_by_stop = dict(self.routes_by_stop)
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
        route_id: str,
        min_departure: int,
        active_services: Set[str]
    ) -> Optional[str]:
        """Encontrar el trip más temprano que sale después de min_departure.

        Esta es la operación más frecuente en RAPTOR.
        Complejidad: O(n) donde n = trips en la ruta.

        Args:
            route_id: ID de la ruta
            min_departure: Tiempo mínimo de salida (segundos desde medianoche)
            active_services: Set de service_ids activos hoy

        Returns:
            trip_id del primer trip válido, o None
        """
        trips = self.trips_by_route.get(route_id, [])

        for departure_sec, trip_id in trips:
            if departure_sec >= min_departure:
                # Verificar que el servicio está activo
                trip_info = self.trips_info.get(trip_id)
                if trip_info and trip_info[2] in active_services:  # índice 2 = service_id
                    return trip_id

        return None

    def get_routes_at_stop(self, stop_id: str) -> Set[str]:
        """Obtener rutas que pasan por una parada.

        Complejidad: O(1)

        Args:
            stop_id: ID de la parada

        Returns:
            Set de route_ids (vacío si no hay rutas)
        """
        return self.routes_by_stop.get(stop_id, set())

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


# Singleton global para importación directa
gtfs_store = GTFSStore.get_instance()
