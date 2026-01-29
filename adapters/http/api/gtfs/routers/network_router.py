"""Network metadata API endpoints."""
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from src.gtfs_bc.network.infrastructure.models import NetworkModel
from src.gtfs_bc.route.infrastructure.models import RouteModel
from adapters.http.api.gtfs.utils.text_utils import normalize_route_long_name


router = APIRouter(prefix="/gtfs/networks", tags=["networks"])


def natural_sort_key(line_code: str) -> tuple:
    """
    Natural sort key for line codes like C1, C2, C10, C4a, C4b.
    Returns tuple for proper sorting: ('C', 1, '') for C1, ('C', 4, 'a') for C4a.
    """
    match = re.match(r'([A-Za-z]+)(\d+)([a-z]*)', line_code)
    if match:
        prefix, number, suffix = match.groups()
        return (prefix, int(number), suffix)
    return (line_code, 0, '')


class NetworkResponse(BaseModel):
    """Response model for network."""

    code: str
    name: str
    region: str
    color: str
    text_color: str
    transport_type: str  # cercanias, metro, metro_ligero, tranvia, fgc, euskotren, other
    logo_url: Optional[str] = None
    wikipedia_url: Optional[str] = None
    description: Optional[str] = None
    nucleo_id_renfe: Optional[int] = None
    route_count: int = 0

    class Config:
        from_attributes = True


class LineResponse(BaseModel):
    """Response model for a line within a network."""

    line_code: str  # e.g., "C1", "C2"
    color: str
    text_color: str
    sort_order: Optional[int] = None
    route_count: int
    routes: List[dict]


class NetworkDetailResponse(NetworkResponse):
    """Detailed network response with lines."""

    lines: List[LineResponse] = []


@router.get("", response_model=List[NetworkResponse])
async def get_networks(db: Session = Depends(get_db)):
    """Get all transit networks with route counts."""
    networks = db.query(NetworkModel).all()

    results = []
    for network in networks:
        # Count routes directly via network_id
        route_count = (
            db.query(RouteModel)
            .filter(RouteModel.network_id == network.code)
            .count()
        )

        results.append(
            NetworkResponse(
                code=network.code,
                name=network.name,
                region=network.region,
                color=network.color,
                text_color=network.text_color,
                transport_type=network.transport_type,
                logo_url=network.logo_url,
                wikipedia_url=network.wikipedia_url,
                description=network.description,
                nucleo_id_renfe=network.nucleo_id_renfe,
                route_count=route_count,
            )
        )

    return results


@router.get("/{code}", response_model=NetworkDetailResponse)
async def get_network(code: str, db: Session = Depends(get_db)):
    """Get network details with all lines and their colors."""
    network = db.query(NetworkModel).filter(NetworkModel.code == code).first()

    if not network:
        raise HTTPException(status_code=404, detail=f"Network {code} not found")

    # Get all routes for this network via network_id
    routes = (
        db.query(RouteModel)
        .filter(RouteModel.network_id == code)
        .order_by(RouteModel.sort_order.nulls_last(), RouteModel.short_name)
        .all()
    )

    # Group routes by line code
    lines_dict = {}
    for route in routes:
        line_code = route.short_name
        if line_code not in lines_dict:
            lines_dict[line_code] = {
                "line_code": line_code,
                "color": route.color or network.color,
                "text_color": route.text_color or network.text_color,
                "sort_order": route.sort_order,
                "routes": [],
            }
        lines_dict[line_code]["routes"].append(
            {
                "id": route.id,
                "long_name": normalize_route_long_name(route.long_name),
                "color": route.color,
            }
        )

    # Filter out generic C4/C8 lines when variants exist (Cercanías only)
    # C4 splits into C4a (Alcobendas) and C4b (Colmenar Viejo)
    # C8 splits into C8a (El Escorial) and C8b (Cercedilla)
    lines_to_exclude = set()
    if 'C4a' in lines_dict or 'C4b' in lines_dict:
        lines_to_exclude.add('C4')
    if 'C8a' in lines_dict or 'C8b' in lines_dict:
        lines_to_exclude.add('C8')
    for line_code in lines_to_exclude:
        lines_dict.pop(line_code, None)

    # Convert to list and sort by sort_order (fallback to natural sort)
    lines = sorted(
        [
            LineResponse(
                line_code=data["line_code"],
                color=data["color"],
                text_color=data["text_color"],
                sort_order=data["sort_order"],
                route_count=len(data["routes"]),
                routes=data["routes"],
            )
            for data in lines_dict.values()
        ],
        key=lambda x: (x.sort_order if x.sort_order is not None else 9999, natural_sort_key(x.line_code))
    )

    return NetworkDetailResponse(
        code=network.code,
        name=network.name,
        region=network.region,
        color=network.color,
        text_color=network.text_color,
        transport_type=network.transport_type,
        logo_url=network.logo_url,
        wikipedia_url=network.wikipedia_url,
        description=network.description,
        nucleo_id_renfe=network.nucleo_id_renfe,
        route_count=len(routes),
        lines=lines,
    )


@router.get("/{code}/lines", response_model=List[LineResponse])
async def get_network_lines(code: str, db: Session = Depends(get_db)):
    """Get all lines for a network with their colors."""
    network = db.query(NetworkModel).filter(NetworkModel.code == code).first()

    if not network:
        raise HTTPException(status_code=404, detail=f"Network {code} not found")

    # Get all routes for this network via network_id
    routes = (
        db.query(RouteModel)
        .filter(RouteModel.network_id == code)
        .order_by(RouteModel.sort_order.nulls_last(), RouteModel.short_name)
        .all()
    )

    # Group routes by line code
    lines_dict = {}
    for route in routes:
        line_code = route.short_name
        if line_code not in lines_dict:
            lines_dict[line_code] = {
                "line_code": line_code,
                "color": route.color or network.color,
                "text_color": route.text_color or network.text_color,
                "sort_order": route.sort_order,
                "routes": [],
            }
        lines_dict[line_code]["routes"].append(
            {
                "id": route.id,
                "long_name": normalize_route_long_name(route.long_name),
                "color": route.color,
            }
        )

    # Filter out generic C4/C8 lines when variants exist (Cercanías only)
    # C4 splits into C4a (Alcobendas) and C4b (Colmenar Viejo)
    # C8 splits into C8a (El Escorial) and C8b (Cercedilla)
    lines_to_exclude = set()
    if 'C4a' in lines_dict or 'C4b' in lines_dict:
        lines_to_exclude.add('C4')
    if 'C8a' in lines_dict or 'C8b' in lines_dict:
        lines_to_exclude.add('C8')
    for line_code in lines_to_exclude:
        lines_dict.pop(line_code, None)

    return sorted(
        [
            LineResponse(
                line_code=data["line_code"],
                color=data["color"],
                text_color=data["text_color"],
                sort_order=data["sort_order"],
                route_count=len(data["routes"]),
                routes=data["routes"],
            )
            for data in lines_dict.values()
        ],
        key=lambda x: (x.sort_order if x.sort_order is not None else 9999, natural_sort_key(x.line_code))
    )
