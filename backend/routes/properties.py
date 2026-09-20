from flask import Blueprint, flash, redirect, render_template, request, url_for

from backend.extensions import db
from backend.models import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, PROPERTY_TYPES, UNIT_TYPES, Lease, Property, Unit
from backend.security import assert_owner, audit_log, current_user, role_required, validate

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_OWNER, ROLE_MANAGER)

bp = Blueprint("properties", __name__, url_prefix="/properties")


def _visible_query(user):
    q = Property.query
    if user.role == ROLE_OWNER:
        q = q.filter_by(owner_id=user.id)
    return q


@bp.route("")
@role_required(*MANAGEMENT_ROLES)
def index():
    properties = _visible_query(current_user()).order_by(Property.created_at.desc()).all()
    return render_template("properties/list.html", properties=properties)


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
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("properties/add.html", types=PROPERTY_TYPES, form=request.form)

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
        )
        db.session.add(prop)
        db.session.commit()
        audit_log("property_created", "Property", prop.id, new_value={"name": name})
        flash(f"Property {prop.property_code} created.", "success")
        return redirect(url_for("properties.detail", property_id=prop.id))
    return render_template("properties/add.html", types=PROPERTY_TYPES, form={})


@bp.route("/<property_id>")
@role_required(*MANAGEMENT_ROLES)
def detail(property_id):
    assert_owner(property_id)
    prop = Property.query.get_or_404(property_id)
    units = prop.units.order_by(Unit.unit_number).all()
    return render_template("properties/detail.html", property=prop, units=units)


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
        db.session.commit()
        audit_log("unit_created", "Unit", unit.id, new_value={"unit_number": unit_number})
        flash(f"Unit {unit.unit_code} added.", "success")
        return redirect(url_for("properties.detail", property_id=prop.id))
    return render_template("properties/add_unit.html", property=prop, types=UNIT_TYPES, form={})


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
