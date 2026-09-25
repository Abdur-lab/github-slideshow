from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from backend.extensions import db
from backend.models import (
    EXPENSE_CATEGORIES,
    LATE_FEE_TYPES,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_OWNER,
    PROPERTY_TYPES,
    UNIT_TYPES,
    Lease,
    Property,
    PropertyExpense,
    Unit,
)
from backend.security import assert_owner, audit_log, current_user, role_required, validate, validate_upload
from backend.services.storage import save_uploads, serve_upload

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)
MAX_PROPERTY_PHOTOS = 10
MAX_UNIT_PHOTOS = 5
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
MAX_IMAGE_BYTES = 5 * 1024 * 1024

bp = Blueprint("properties", __name__, url_prefix="/properties")


def _visible_query(user):
    q = Property.query
    if user.role == ROLE_OWNER:
        q = q.filter_by(owner_id=user.id)
    return q


def _valid_photos(files, max_count):
    """Returns (valid_files, errors) — any file beyond max_count or that
    fails image validation is reported rather than silently dropped."""
    files = [f for f in files if f and f.filename]
    errors = []
    if len(files) > max_count:
        errors.append(f"You may upload at most {max_count} photos at a time.")
        files = files[:max_count]
    for f in files:
        if not validate_upload(f, allowed_ext=IMAGE_EXTENSIONS, max_bytes=MAX_IMAGE_BYTES):
            errors.append(f'"{f.filename}" is not a valid JPG/PNG under 5 MB and was not uploaded.')
    valid = [f for f in files if validate_upload(f, allowed_ext=IMAGE_EXTENSIONS, max_bytes=MAX_IMAGE_BYTES)]
    return valid, errors


@bp.route("")
@role_required(*MANAGEMENT_ROLES)
def index():
    properties = _visible_query(current_user()).order_by(Property.created_at.desc()).all()
    return render_template("properties/list.html", properties=properties)


@bp.route("/map")
@role_required(*MANAGEMENT_ROLES)
def map_view():
    properties = _visible_query(current_user()).order_by(Property.name).all()
    located = [p for p in properties if p.has_location]
    return render_template("properties/map.html", properties=properties, located=located)


@bp.route("/add", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_OWNER)
def add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        country = request.form.get("country", "").strip()
        ptype = request.form.get("type", "RESIDENTIAL")
        currency = (request.form.get("currency", "USD").strip() or "USD").upper()
        description = request.form.get("description", "").strip()
        late_fee_type = request.form.get("late_fee_type", "NONE")
        late_fee_amount = request.form.get("late_fee_amount") or "0"
        latitude = request.form.get("latitude", "").strip()
        longitude = request.form.get("longitude", "").strip()
        owner = current_user()

        errors = []
        if not name:
            errors.append("Property name is required.")
        if not address:
            errors.append("Address is required.")
        if not city:
            errors.append("City is required.")
        if not country:
            errors.append("Country is required.")
        if name and Property.query.filter_by(owner_id=owner.id, name=name).first():
            errors.append("You already have a property with this name.")
        if late_fee_type not in LATE_FEE_TYPES:
            late_fee_type = "NONE"
        if late_fee_type != "NONE" and not validate("positive_float", late_fee_amount):
            errors.append("Late fee amount must be a positive number when a late fee type is selected.")
        if bool(latitude) != bool(longitude):
            errors.append("Set both latitude and longitude, or leave the map location blank.")
        elif latitude and (not validate("latitude", latitude) or not validate("longitude", longitude)):
            errors.append("Map location is invalid — latitude must be -90 to 90 and longitude -180 to 180.")
        photos, photo_errors = _valid_photos(request.files.getlist("photos"), MAX_PROPERTY_PHOTOS)
        errors.extend(photo_errors)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("properties/add.html", types=PROPERTY_TYPES, late_fee_types=LATE_FEE_TYPES, form=request.form)

        prop = Property(
            owner_id=owner.id,
            name=name,
            address=address,
            city=city,
            country=country,
            type=ptype if ptype in PROPERTY_TYPES else "RESIDENTIAL",
            currency=currency,
            description=description,
            property_code=Property.generate_property_code(),
            late_fee_type=late_fee_type,
            late_fee_amount=float(late_fee_amount or 0) if late_fee_type != "NONE" else 0.0,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
        )
        db.session.add(prop)
        db.session.flush()
        prop.photo_paths = save_uploads(photos, f"properties/{prop.id}", MAX_PROPERTY_PHOTOS)
        db.session.commit()
        audit_log("property_created", "Property", prop.id, new_value={"name": name})
        flash(f"Property {prop.property_code} created.", "success")
        return redirect(url_for("properties.detail", property_id=prop.id))
    return render_template("properties/add.html", types=PROPERTY_TYPES, late_fee_types=LATE_FEE_TYPES, form={})


@bp.route("/<property_id>")
@role_required(*MANAGEMENT_ROLES)
def detail(property_id):
    assert_owner(property_id)
    prop = Property.query.get_or_404(property_id)
    units = prop.units.order_by(Unit.unit_number).all()
    expenses = prop.expenses.order_by(PropertyExpense.incurred_at.desc()).all()
    return render_template(
        "properties/detail.html", property=prop, units=units, expenses=expenses, expense_categories=EXPENSE_CATEGORIES
    )


@bp.route("/<property_id>/expenses/add", methods=["POST"])
@role_required(*MANAGEMENT_ROLES)
def add_expense(property_id):
    assert_owner(property_id)
    prop = Property.query.get_or_404(property_id)
    category = request.form.get("category", "OTHER")
    description = request.form.get("description", "").strip()
    amount = request.form.get("amount")
    incurred_at_raw = request.form.get("incurred_at")

    errors = []
    if category not in EXPENSE_CATEGORIES:
        category = "OTHER"
    if not description:
        errors.append("A description is required for the expense.")
    if not validate("positive_float", amount):
        errors.append("Expense amount must be a positive number.")
    incurred_at = date.today()
    if incurred_at_raw:
        if not validate("date", incurred_at_raw):
            errors.append("Expense date is invalid.")
        else:
            incurred_at = date.fromisoformat(incurred_at_raw)
    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("properties.detail", property_id=prop.id))

    expense = PropertyExpense(
        property_id=prop.id,
        category=category,
        description=description,
        amount=float(amount),
        incurred_at=incurred_at,
        recorded_by=current_user().id,
    )
    db.session.add(expense)
    db.session.commit()
    audit_log("property_expense_added", "PropertyExpense", expense.id, new_value={"category": category, "amount": float(amount)})
    flash(f"{category.replace('_', ' ').title()} expense of {expense.amount:.2f} recorded.", "success")
    return redirect(url_for("properties.detail", property_id=prop.id))


@bp.route("/<property_id>/edit", methods=["GET", "POST"])
@role_required(*MANAGEMENT_ROLES)
def edit(property_id):
    assert_owner(property_id)
    prop = Property.query.get_or_404(property_id)
    if request.method == "POST":
        description = request.form.get("description", "").strip()
        late_fee_type = request.form.get("late_fee_type", "NONE")
        late_fee_amount = request.form.get("late_fee_amount") or "0"
        electricity_rate = request.form.get("electricity_rate") or "0"
        latitude = request.form.get("latitude", "").strip()
        longitude = request.form.get("longitude", "").strip()

        errors = []
        if late_fee_type not in LATE_FEE_TYPES:
            late_fee_type = "NONE"
        if late_fee_type != "NONE" and not validate("positive_float", late_fee_amount):
            errors.append("Late fee amount must be a positive number when a late fee type is selected.")
        try:
            electricity_rate_val = float(electricity_rate)
            if electricity_rate_val < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append("Electricity rate must be a non-negative number.")
            electricity_rate_val = prop.electricity_rate
        if bool(latitude) != bool(longitude):
            errors.append("Set both latitude and longitude, or leave the map location blank.")
        elif latitude and (not validate("latitude", latitude) or not validate("longitude", longitude)):
            errors.append("Map location is invalid — latitude must be -90 to 90 and longitude -180 to 180.")
        new_photos, photo_errors = _valid_photos(request.files.getlist("photos"), MAX_PROPERTY_PHOTOS)
        errors.extend(photo_errors)
        existing = len(prop.photo_paths or [])
        if existing + len(new_photos) > MAX_PROPERTY_PHOTOS:
            errors.append(f"A property may have at most {MAX_PROPERTY_PHOTOS} photos in total.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("properties/edit.html", property=prop, late_fee_types=LATE_FEE_TYPES)

        prop.description = description
        prop.late_fee_type = late_fee_type
        prop.late_fee_amount = float(late_fee_amount or 0) if late_fee_type != "NONE" else 0.0
        prop.electricity_rate = electricity_rate_val
        prop.latitude = float(latitude) if latitude else None
        prop.longitude = float(longitude) if longitude else None
        if new_photos:
            saved = save_uploads(new_photos, f"properties/{prop.id}", MAX_PROPERTY_PHOTOS)
            prop.photo_paths = list(prop.photo_paths or []) + saved
        db.session.commit()
        audit_log("property_updated", "Property", prop.id, new_value={"late_fee_type": late_fee_type})
        flash("Property updated.", "success")
        return redirect(url_for("properties.detail", property_id=prop.id))
    return render_template("properties/edit.html", property=prop, late_fee_types=LATE_FEE_TYPES)


@bp.route("/<property_id>/add-unit", methods=["GET", "POST"])
@role_required(*MANAGEMENT_ROLES)
def add_unit(property_id):
    assert_owner(property_id)
    prop = Property.query.get_or_404(property_id)
    if request.method == "POST":
        unit_number = request.form.get("unit_number", "").strip()
        floor = request.form.get("floor", "").strip()
        utype = request.form.get("type", "STUDIO")
        size_sqm = request.form.get("size_sqm") or None
        monthly_rent = request.form.get("monthly_rent")
        deposit = request.form.get("deposit") or "0"

        errors = []
        if not unit_number:
            errors.append("Unit number is required.")
        elif Unit.query.filter_by(property_id=prop.id, unit_number=unit_number).first():
            errors.append("Unit number already in use in this property.")
        if not validate("positive_float", monthly_rent):
            errors.append("Monthly rent must be a positive number.")
        photos, photo_errors = _valid_photos(request.files.getlist("photos"), MAX_UNIT_PHOTOS)
        errors.extend(photo_errors)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("properties/add_unit.html", property=prop, types=UNIT_TYPES, form=request.form)

        unit = Unit(
            property_id=prop.id,
            unit_number=unit_number,
            floor=floor,
            type=utype if utype in UNIT_TYPES else "STUDIO",
            size_sqm=float(size_sqm) if size_sqm else None,
            monthly_rent=float(monthly_rent),
            deposit=float(deposit or 0),
            unit_code=Unit.generate_unit_code(prop.property_code, unit_number),
        )
        db.session.add(unit)
        db.session.flush()
        unit.photo_paths = save_uploads(photos, f"units/{unit.id}", MAX_UNIT_PHOTOS)
        db.session.commit()
        audit_log("unit_created", "Unit", unit.id, new_value={"unit_number": unit_number})
        flash(f"Unit {unit.unit_code} added.", "success")
        return redirect(url_for("properties.detail", property_id=prop.id))
    return render_template("properties/add_unit.html", property=prop, types=UNIT_TYPES, form={})


@bp.route("/<property_id>/units/<unit_id>/edit", methods=["GET", "POST"])
@role_required(*MANAGEMENT_ROLES)
def edit_unit(property_id, unit_id):
    assert_owner(property_id)
    prop = Property.query.get_or_404(property_id)
    unit = Unit.query.filter_by(id=unit_id, property_id=property_id).first_or_404()
    if request.method == "POST":
        floor = request.form.get("floor", "").strip()
        utype = request.form.get("type", unit.type)
        size_sqm = request.form.get("size_sqm") or None
        monthly_rent = request.form.get("monthly_rent")
        deposit = request.form.get("deposit") or "0"
        new_status = request.form.get("status", unit.status)

        errors = []
        if not validate("positive_float", monthly_rent):
            errors.append("Monthly rent must be a positive number.")
        if new_status == "OCCUPIED" and not unit.active_lease:
            errors.append("Occupancy status is set automatically when a lease is activated; it cannot be set to Occupied here.")
            new_status = unit.status
        if new_status == "VACANT" and unit.active_lease:
            errors.append("This unit has an active lease and cannot be manually set to Vacant.")
            new_status = unit.status
        new_photos, photo_errors = _valid_photos(request.files.getlist("photos"), MAX_UNIT_PHOTOS)
        errors.extend(photo_errors)
        existing = len(unit.photo_paths or [])
        if existing + len(new_photos) > MAX_UNIT_PHOTOS:
            errors.append(f"A unit may have at most {MAX_UNIT_PHOTOS} photos in total.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("properties/edit_unit.html", property=prop, unit=unit, types=UNIT_TYPES)

        unit.floor = floor
        unit.type = utype if utype in UNIT_TYPES else unit.type
        unit.size_sqm = float(size_sqm) if size_sqm else None
        unit.monthly_rent = float(monthly_rent)
        unit.deposit = float(deposit or 0)
        if new_status in ("VACANT", "UNDER_MAINTENANCE") and unit.status != "ARCHIVED":
            unit.status = new_status
        if new_photos:
            saved = save_uploads(new_photos, f"units/{unit.id}", MAX_UNIT_PHOTOS)
            unit.photo_paths = list(unit.photo_paths or []) + saved
        db.session.commit()
        audit_log("unit_updated", "Unit", unit.id, new_value={"status": unit.status, "monthly_rent": unit.monthly_rent})
        flash("Unit updated.", "success")
        return redirect(url_for("properties.detail", property_id=prop.id))
    return render_template("properties/edit_unit.html", property=prop, unit=unit, types=UNIT_TYPES)


@bp.route("/<property_id>/archive", methods=["POST"])
@role_required(*MANAGEMENT_ROLES)
def archive(property_id):
    assert_owner(property_id)
    prop = Property.query.get_or_404(property_id)
    active_leases = Lease.query.join(Unit).filter(Unit.property_id == prop.id, Lease.status == "ACTIVE").count()
    if active_leases:
        flash("This property has active leases. Terminate them before archiving.", "error")
        return redirect(url_for("properties.detail", property_id=property_id))
    prop.status = "ARCHIVED"
    for u in prop.units:
        if u.status != "ARCHIVED":
            u.status = "ARCHIVED"
    db.session.commit()
    audit_log("property_archived", "Property", prop.id)
    flash("Property archived.", "success")
    return redirect(url_for("properties.index"))


@bp.route("/<property_id>/units/<unit_id>/archive", methods=["POST"])
@role_required(*MANAGEMENT_ROLES)
def archive_unit(property_id, unit_id):
    assert_owner(property_id)
    unit = Unit.query.filter_by(id=unit_id, property_id=property_id).first_or_404()
    if unit.active_lease:
        flash("This unit has an active lease. Please terminate the lease before archiving.", "error")
        return redirect(url_for("properties.detail", property_id=property_id))
    unit.status = "ARCHIVED"
    db.session.commit()
    audit_log("unit_archived", "Unit", unit.id)
    flash("Unit archived.", "success")
    return redirect(url_for("properties.detail", property_id=property_id))


@bp.route("/<property_id>/photos/<path:relpath>")
@role_required(*MANAGEMENT_ROLES)
def property_photo(property_id, relpath):
    assert_owner(property_id)
    prop = Property.query.get_or_404(property_id)
    full = f"properties/{property_id}/{relpath}"
    if full not in (prop.photo_paths or []):
        abort(404)
    return serve_upload(full)


@bp.route("/<property_id>/units/<unit_id>/photos/<path:relpath>")
@role_required(*MANAGEMENT_ROLES)
def unit_photo(property_id, unit_id, relpath):
    assert_owner(property_id)
    unit = Unit.query.filter_by(id=unit_id, property_id=property_id).first_or_404()
    full = f"units/{unit_id}/{relpath}"
    if full not in (unit.photo_paths or []):
        abort(404)
    return serve_upload(full)
