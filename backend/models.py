"""SQLAlchemy models for RentalPro (13 tables, per Deliverable 2 ERD)."""
import calendar
import uuid
from datetime import date, datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from backend.extensions import db

PASSWORD_HASH_METHOD = "pbkdf2:sha256:600000"


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.utcnow()


# --- Role / status constants -------------------------------------------------

ROLE_ADMIN = "ADMIN"
ROLE_OWNER = "PROPERTY_OWNER"
ROLE_MANAGER = "PROPERTY_MANAGER"
ROLE_STAFF = "MAINTENANCE_STAFF"
ROLE_TENANT = "TENANT"
ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER, ROLE_STAFF, ROLE_TENANT)
MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)

PROPERTY_TYPES = ("RESIDENTIAL", "COMMERCIAL", "MIXED")
PROPERTY_STATUSES = ("ACTIVE", "ARCHIVED")
LATE_FEE_TYPES = ("NONE", "FIXED", "PERCENTAGE")

UNIT_TYPES = ("STUDIO", "1BR", "2BR", "3BR", "SHOP", "OFFICE")
UNIT_STATUSES = ("VACANT", "OCCUPIED", "UNDER_MAINTENANCE", "ARCHIVED")

LEASE_STATUSES = ("ACTIVE", "TERMINATED", "EXPIRED")

PAYMENT_METHODS = ("CASH", "BANK_TRANSFER", "ONLINE", "CHEQUE")

CHARGE_TYPES = ("OPERATIONAL", "SUNDRY", "ELECTRICITY")

EXPENSE_CATEGORIES = ("MAINTENANCE", "TAX", "INSURANCE", "UTILITIES", "MANAGEMENT_FEE", "OTHER")

MAINT_CATEGORIES = ("PLUMBING", "ELECTRICAL", "STRUCTURAL", "HVAC", "PEST_CONTROL", "OTHER")
MAINT_SEVERITIES = ("LOW", "MEDIUM", "HIGH", "EMERGENCY")
MAINT_STATUSES = ("SUBMITTED", "ACKNOWLEDGED", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CLOSED")

NOTIFICATION_TYPES = ("EMAIL", "SMS")
NOTIFICATION_STATUSES = ("PENDING", "SENT", "FAILED")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    opt_out_sms = db.Column(db.Boolean, nullable=False, default=False)
    opt_out_email = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    tenant_profile = db.relationship(
        "Tenant", backref="user", uselist=False, cascade="all, delete-orphan"
    )
    properties = db.relationship("Property", backref="owner", lazy="dynamic")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method=PASSWORD_HASH_METHOD)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > utcnow())

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    owner_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(300), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False, default="RESIDENTIAL")
    currency = db.Column(db.String(3), nullable=False, default="USD")
    description = db.Column(db.Text, nullable=True)
    property_code = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    photo_paths = db.Column(db.JSON, nullable=False, default=list)
    late_fee_type = db.Column(db.String(10), nullable=False, default="NONE")
    late_fee_amount = db.Column(db.Float, nullable=False, default=0)
    electricity_rate = db.Column(db.Float, nullable=False, default=0)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    units = db.relationship("Unit", backref="property", cascade="all, delete-orphan", lazy="dynamic")
    expenses = db.relationship("PropertyExpense", backref="property", cascade="all, delete-orphan", lazy="dynamic")

    def late_fee_for(self, monthly_rent: float) -> float:
        if self.late_fee_type == "FIXED":
            return round(self.late_fee_amount, 2)
        if self.late_fee_type == "PERCENTAGE":
            return round(monthly_rent * (self.late_fee_amount / 100.0), 2)
        return 0.0

    @staticmethod
    def generate_property_code() -> str:
        return f"PROP-{uuid.uuid4().hex[:4].upper()}"

    @property
    def occupancy_rate(self) -> float:
        units = self.units.filter(Unit.status != "ARCHIVED").all()
        if not units:
            return 0.0
        occupied = sum(1 for u in units if u.status == "OCCUPIED")
        return round((occupied / len(units)) * 100, 1)

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class Unit(db.Model):
    __tablename__ = "units"
    __table_args__ = (
        db.UniqueConstraint("property_id", "unit_number", name="uq_unit_property_number"),
        db.Index("ix_unit_property_status", "property_id", "status"),
    )

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    property_id = db.Column(db.String(36), db.ForeignKey("properties.id"), nullable=False)
    unit_number = db.Column(db.String(20), nullable=False)
    floor = db.Column(db.String(10), nullable=True)
    type = db.Column(db.String(20), nullable=False, default="STUDIO")
    size_sqm = db.Column(db.Float, nullable=True)
    monthly_rent = db.Column(db.Float, nullable=False)
    deposit = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="VACANT")
    unit_code = db.Column(db.String(30), unique=True, nullable=False)
    photo_paths = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    leases = db.relationship("Lease", backref="unit", lazy="dynamic")
    maintenance_requests = db.relationship("MaintenanceRequest", backref="unit", lazy="dynamic")
    meter_readings = db.relationship("MeterReading", backref="unit", lazy="dynamic")

    @staticmethod
    def generate_unit_code(property_code: str, unit_number: str) -> str:
        return f"{property_code}-U{uuid.uuid4().hex[:4].upper()}"

    @property
    def active_lease(self):
        return self.leases.filter_by(status="ACTIVE").order_by(Lease.start_date.desc()).first()

    @property
    def latest_meter_reading(self):
        return self.meter_readings.order_by(MeterReading.reading_date.desc(), MeterReading.created_at.desc()).first()


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), unique=True, nullable=False)
    national_id = db.Column(db.String(50), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    emergency_contact = db.Column(db.String(200), nullable=True)
    is_blacklisted = db.Column(db.Boolean, nullable=False, default=False)
    blacklist_reason = db.Column(db.String(300), nullable=True)
    id_document_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    leases = db.relationship("Lease", backref="tenant", lazy="dynamic")
    maintenance_requests = db.relationship("MaintenanceRequest", backref="tenant", lazy="dynamic")

    @property
    def active_lease(self):
        return self.leases.filter_by(status="ACTIVE").order_by(Lease.start_date.desc()).first()


class TenantInvitation(db.Model):
    __tablename__ = "tenant_invitations"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    unit_id = db.Column(db.String(36), db.ForeignKey("units.id"), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    unit = db.relationship("Unit")

    @staticmethod
    def new_token_expiry(hours: int = 48) -> datetime:
        return utcnow() + timedelta(hours=hours)

    @property
    def is_valid(self) -> bool:
        return (not self.accepted) and self.expires_at > utcnow()


class PasswordReset(db.Model):
    __tablename__ = "password_resets"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    @staticmethod
    def new_token_expiry(hours: int = 1) -> datetime:
        return utcnow() + timedelta(hours=hours)

    @property
    def is_valid(self) -> bool:
        return (not self.used) and self.expires_at > utcnow()


class Lease(db.Model):
    __tablename__ = "leases"
    __table_args__ = (
        db.Index("ix_lease_unit_status", "unit_id", "status"),
        db.Index("ix_lease_tenant", "tenant_id"),
        db.Index("ix_lease_end_date", "end_date", "status"),
    )

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    unit_id = db.Column(db.String(36), db.ForeignKey("units.id"), nullable=False)
    tenant_id = db.Column(db.String(36), db.ForeignKey("tenants.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    monthly_rent = db.Column(db.Float, nullable=False)
    deposit = db.Column(db.Float, nullable=False, default=0)
    due_day = db.Column(db.Integer, nullable=False, default=1)
    pro_rata = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    document_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    payments = db.relationship("RentPayment", backref="lease", lazy="dynamic")
    charges = db.relationship("LeaseCharge", backref="lease", lazy="dynamic")
    rent_revisions = db.relationship("RentRevision", backref="lease", lazy="dynamic")
    invoices = db.relationship("RentInvoice", backref="lease", lazy="dynamic")

    def _clip_day(self, year: int, month: int) -> int:
        last_day = calendar.monthrange(year, month)[1]
        return min(self.due_day, last_day)

    def first_due_date(self) -> date:
        """First rent due date on/after the lease start, honouring due_day
        with month-end clipping (e.g. due_day=31 in February)."""
        year, month = self.start_date.year, self.start_date.month
        day = self._clip_day(year, month)
        candidate = date(year, month, day)
        if candidate < self.start_date:
            month += 1
            if month > 12:
                month = 1
                year += 1
            day = self._clip_day(year, month)
            candidate = date(year, month, day)
        return candidate

    def _advance_month(self, d: date) -> date:
        year, month = d.year, d.month + 1
        if month > 12:
            month, year = 1, year + 1
        return date(year, month, self._clip_day(year, month))

    def first_period_amount(self, monthly_rent: float = None) -> float:
        """Rent owed for the lease's first, potentially partial, calendar
        month — a daily rate applied to the days from start_date to the end
        of that calendar month. Equals monthly_rent in full when the lease
        starts on the 1st. Only used when pro_rata proration is enabled."""
        monthly_rent = self.monthly_rent if monthly_rent is None else monthly_rent
        days_in_month = calendar.monthrange(self.start_date.year, self.start_date.month)[1]
        days_occupied = days_in_month - self.start_date.day + 1
        daily_rate = monthly_rent / days_in_month
        return round(daily_rate * days_occupied, 2)

    def rent_at(self, as_of: date = None) -> float:
        """The monthly rent in effect on the given date: the most recent
        RentRevision effective on/before that date, or the lease's base
        monthly_rent if no revision has taken effect yet. Lets a lease's
        rent change over its term (e.g. an annual escalation) without
        altering the original amount recorded on the lease itself."""
        as_of = as_of or date.today()
        revision = (
            self.rent_revisions.filter(RentRevision.effective_date <= as_of)
            .order_by(RentRevision.effective_date.desc(), RentRevision.created_at.desc())
            .first()
        )
        return revision.monthly_rent if revision else self.monthly_rent

    @property
    def current_monthly_rent(self) -> float:
        return self.rent_at(date.today())

    def due_dates_to_date(self, as_of: date = None) -> list:
        """All billing due dates from first_due_date through as_of,
        inclusive. Used by the auto-billing job to generate one invoice
        per elapsed period; kept in lockstep with total_due_to_date's own
        period-walking loop below."""
        as_of = as_of or date.today()
        first_due = self.first_due_date()
        if as_of < first_due:
            return []
        dates = [first_due]
        due = first_due
        while True:
            due = self._advance_month(due)
            if due > as_of:
                break
            dates.append(due)
        return dates

    def amount_for_period(self, due_date: date) -> float:
        """Rent billed for a single period ending at due_date: the
        prorated first-period amount when pro_rata is enabled and this is
        the lease's first period, otherwise the rent in effect on that
        date (see rent_at)."""
        rent = self.rent_at(due_date)
        if self.pro_rata and due_date == self.first_due_date():
            return self.first_period_amount(rent)
        return rent

    def total_due_to_date(self, as_of: date = None) -> float:
        """Sum of rent owed for each elapsed billing period (inclusive),
        using the rent in effect at each period's due date (see rent_at),
        with the first period prorated to a partial-month daily rate when
        pro_rata is enabled on this lease."""
        as_of = as_of or date.today()
        first_due = self.first_due_date()
        if as_of < first_due:
            return 0.0
        first_rent = self.rent_at(first_due)
        total = self.first_period_amount(first_rent) if self.pro_rata else first_rent
        due = first_due
        while True:
            due = self._advance_month(due)
            if due > as_of:
                break
            total += self.rent_at(due)
        return round(total, 2)

    def current_due_date(self, as_of: date = None):
        """Due date of the most recently started billing period, or None
        if the lease has not started its first period yet."""
        as_of = as_of or date.today()
        first_due = self.first_due_date()
        if as_of < first_due:
            return None
        current = first_due
        while True:
            nxt = self._advance_month(current)
            if nxt > as_of:
                return current
            current = nxt

    def next_due_date(self, as_of: date = None) -> date:
        """Due date of the next not-yet-started billing period."""
        as_of = as_of or date.today()
        d = self.first_due_date()
        while d <= as_of:
            d = self._advance_month(d)
        return d

    @property
    def total_paid(self) -> float:
        total = db.session.query(db.func.coalesce(db.func.sum(RentPayment.amount), 0.0)).filter(
            RentPayment.lease_id == self.id
        ).scalar()
        return round(float(total or 0.0), 2)

    def late_fee_due(self, as_of: date = None) -> float:
        """A configured late fee (Property.late_fee_type/late_fee_amount)
        applies once the current billing period is unpaid past its due
        date. Defaults to NONE, so this is 0.0 unless a property owner has
        explicitly configured a fee (Section 5, FR-022)."""
        as_of = as_of or date.today()
        current_due = self.current_due_date(as_of)
        if current_due is None or current_due >= as_of:
            return 0.0
        if self.total_due_to_date(as_of) <= self.total_paid:
            return 0.0
        return self.unit.property.late_fee_for(self.rent_at(as_of))

    @property
    def total_charges(self) -> float:
        """Sum of ad-hoc operational/sundry charges levied against this
        lease, in addition to recurring rent."""
        total = db.session.query(db.func.coalesce(db.func.sum(LeaseCharge.amount), 0.0)).filter(
            LeaseCharge.lease_id == self.id
        ).scalar()
        return round(float(total or 0.0), 2)

    @property
    def balance(self) -> float:
        return max(0.0, round(self.total_due_to_date() + self.late_fee_due() + self.total_charges - self.total_paid, 2))

    @property
    def credit(self) -> float:
        return max(0.0, round(self.total_paid - self.total_due_to_date() - self.late_fee_due() - self.total_charges, 2))

    @property
    def is_overdue(self) -> bool:
        return self.status == "ACTIVE" and self.balance > 0


class RentPayment(db.Model):
    __tablename__ = "rent_payments"
    __table_args__ = (db.Index("ix_payment_lease_date", "lease_id", "paid_at"),)

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    lease_id = db.Column(db.String(36), db.ForeignKey("leases.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(20), nullable=False)
    receipt_number = db.Column(db.String(40), unique=True, nullable=False)
    gateway_ref = db.Column(db.String(120), unique=True, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    recorded_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    notes = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    @staticmethod
    def generate_receipt_number() -> str:
        return f"RCP-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class LeaseCharge(db.Model):
    """An ad-hoc, one-off charge levied against a lease in addition to
    recurring rent — operational charges (e.g. common-area cleaning) and
    sundries (e.g. a one-time call-out fee). Added to Lease.balance
    alongside rent and any configured late fee."""

    __tablename__ = "lease_charges"
    __table_args__ = (db.Index("ix_charge_lease_date", "lease_id", "charged_at"),)

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    lease_id = db.Column(db.String(36), db.ForeignKey("leases.id"), nullable=False)
    charge_type = db.Column(db.String(20), nullable=False, default="OPERATIONAL")
    description = db.Column(db.String(300), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    charged_at = db.Column(db.Date, nullable=False, default=date.today)
    recorded_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class PropertyExpense(db.Model):
    """An operating expense the owner incurs against a property — taxes,
    insurance, management fees, utilities paid by the landlord, general
    upkeep — as distinct from a LeaseCharge (billed TO a tenant) or a
    MaintenanceCost (tied to a specific repair ticket). Feeds into
    property/portfolio net income reporting alongside maintenance costs."""

    __tablename__ = "property_expenses"
    __table_args__ = (db.Index("ix_expense_property_date", "property_id", "incurred_at"),)

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    property_id = db.Column(db.String(36), db.ForeignKey("properties.id"), nullable=False)
    category = db.Column(db.String(20), nullable=False, default="OTHER")
    description = db.Column(db.String(300), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    incurred_at = db.Column(db.Date, nullable=False, default=date.today)
    recorded_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class RentRevision(db.Model):
    """A scheduled change to a lease's monthly rent, effective from a
    given date onward (e.g. an annual escalation or a mid-term
    adjustment). The lease's own monthly_rent stays the original/base
    amount; Lease.rent_at(date) and Lease.total_due_to_date() resolve
    the rent actually billed for each period from the latest revision
    effective on/before that period's due date."""

    __tablename__ = "rent_revisions"
    __table_args__ = (db.Index("ix_revision_lease_date", "lease_id", "effective_date"),)

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    lease_id = db.Column(db.String(36), db.ForeignKey("leases.id"), nullable=False)
    effective_date = db.Column(db.Date, nullable=False)
    monthly_rent = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(300), nullable=True)
    recorded_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class RentInvoice(db.Model):
    """A record that the automated billing job generated a bill for one
    lease's billing period, on that period's due date, at the rent rate
    in effect that day (Lease.amount_for_period). Makes the scheduler job
    idempotent — a period already invoiced is never billed twice, even if
    the job is re-run or catches up on days it missed — and gives owners
    and tenants a paper trail of exactly what was invoiced and when, even
    after a later rent revision changes the lease's current rate."""

    __tablename__ = "rent_invoices"
    __table_args__ = (
        db.UniqueConstraint("lease_id", "period_due_date", name="uq_invoice_lease_period"),
        db.Index("ix_invoice_lease_date", "lease_id", "period_due_date"),
    )

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    lease_id = db.Column(db.String(36), db.ForeignKey("leases.id"), nullable=False)
    period_due_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    generated_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class MeterReading(db.Model):
    """A manually-captured electricity meter reading for a unit. When a
    prior reading exists, the consumption since that reading is billed to
    the unit's active lease as an ELECTRICITY LeaseCharge, at the
    property's electricity_rate in effect at the time of capture."""

    __tablename__ = "meter_readings"
    __table_args__ = (db.Index("ix_meter_unit_date", "unit_id", "reading_date"),)

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    unit_id = db.Column(db.String(36), db.ForeignKey("units.id"), nullable=False)
    reading_date = db.Column(db.Date, nullable=False, default=date.today)
    reading_value = db.Column(db.Float, nullable=False)
    consumption = db.Column(db.Float, nullable=True)
    rate_applied = db.Column(db.Float, nullable=True)
    charge_id = db.Column(db.String(36), db.ForeignKey("lease_charges.id"), nullable=True)
    recorded_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    charge = db.relationship("LeaseCharge")


class MaintenanceRequest(db.Model):
    __tablename__ = "maintenance_requests"
    __table_args__ = (
        db.Index("ix_maint_assigned_status", "assigned_to", "status"),
        db.Index("ix_maint_target_status", "target_date", "status"),
    )

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    unit_id = db.Column(db.String(36), db.ForeignKey("units.id"), nullable=False)
    tenant_id = db.Column(db.String(36), db.ForeignKey("tenants.id"), nullable=False)
    ticket_number = db.Column(db.String(40), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20), nullable=False, default="OTHER")
    severity = db.Column(db.String(20), nullable=False, default="MEDIUM")
    status = db.Column(db.String(20), nullable=False, default="SUBMITTED")
    assigned_to = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    target_date = db.Column(db.Date, nullable=True)
    escalated = db.Column(db.Boolean, nullable=False, default=False)
    satisfaction_rating = db.Column(db.Integer, nullable=True)
    photo_paths = db.Column(db.JSON, nullable=False, default=list)
    completion_photo_paths = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    costs = db.relationship("MaintenanceCost", backref="request", cascade="all, delete-orphan", lazy="dynamic")
    notes_log = db.relationship("MaintenanceNote", backref="request", cascade="all, delete-orphan", lazy="dynamic")
    assignee = db.relationship("User", foreign_keys=[assigned_to])

    @staticmethod
    def generate_ticket_number() -> str:
        return f"MNT-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    @property
    def total_cost(self) -> float:
        total = db.session.query(db.func.coalesce(db.func.sum(MaintenanceCost.amount), 0.0)).filter(
            MaintenanceCost.request_id == self.id
        ).scalar()
        return round(float(total or 0.0), 2)

    @property
    def is_overdue(self) -> bool:
        return (
            self.target_date is not None
            and self.status not in ("COMPLETED", "CLOSED")
            and self.target_date < date.today()
        )


class MaintenanceCost(db.Model):
    __tablename__ = "maintenance_costs"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    request_id = db.Column(db.String(36), db.ForeignKey("maintenance_requests.id"), nullable=False)
    category = db.Column(db.String(30), nullable=False, default="OTHER")
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")
    description = db.Column(db.String(300), nullable=True)
    incurred_at = db.Column(db.Date, nullable=False, default=date.today)
    recorded_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class MaintenanceNote(db.Model):
    __tablename__ = "maintenance_notes"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    request_id = db.Column(db.String(36), db.ForeignKey("maintenance_requests.id"), nullable=False)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    author = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (db.Index("ix_notification_recipient_status", "recipient_id", "status"),)

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    recipient_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(10), nullable=False, default="EMAIL")
    subject = db.Column(db.String(200), nullable=True)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="PENDING")
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (
        db.Index("ix_audit_entity", "entity_type", "entity_id"),
        db.Index("ix_audit_user_created", "user_id", "created_at"),
    )

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.String(36), nullable=True)
    old_value = db.Column(db.JSON, nullable=True)
    new_value = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
