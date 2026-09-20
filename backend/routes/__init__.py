from backend.routes.api import bp as api_bp
from backend.routes.auth import bp as auth_bp
from backend.routes.dashboard import bp as dashboard_bp
from backend.routes.maintenance import bp as maintenance_bp
from backend.routes.portal import bp as portal_bp
from backend.routes.properties import bp as properties_bp
from backend.routes.rent import bp as rent_bp
from backend.routes.reports import bp as reports_bp
from backend.routes.tenants import bp as tenants_bp

ALL_BLUEPRINTS = (
    auth_bp,
    dashboard_bp,
    properties_bp,
    tenants_bp,
    rent_bp,
    portal_bp,
    maintenance_bp,
    reports_bp,
    api_bp,
)
